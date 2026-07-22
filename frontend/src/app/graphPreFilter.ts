/**
 * Similar-profile pre-filter for association-graph expansions.
 *
 * When the user expands an entity on the overview, we pre-apply the seed case's
 * own attributes (crime type, district, and the primary suspect's profile) so an
 * expansion answers "did SIMILAR cases / suspects turn up here?" rather than
 * dumping every unrelated case. The user widens any of it via the Filter control.
 */
import type { AssocFilters, GraphNode, NodeType } from "../lib/graphApi";

/** The seed case's own attributes + primary-accused profile, captured from the
 *  overview load, used to pre-fill the expansion filter. */
export interface SeedAttrs {
  subhead_id?: string;
  district_id?: string;
  station_id?: string;
  accused_name?: string | null;
  accused_age?: number | null;
  accused_gender?: string | null;
}

/** How far an "age band" reaches around the seed suspect's age (similar profile).
 *  MUST match `_AGE_BAND` in the backend association engine
 *  (backend/kavach/analytics/association/engine.py) so overview hint counts equal
 *  what an expansion actually shows. */
export const AGE_BAND = 5;

/**
 * Build the default filter for a fresh expansion of `type`.
 *
 * We pre-fill crime type, district, suspect gender, an age band and the
 * suspect's first name — dropping whatever the focus already fixes (redundant),
 * and, for the same-person (accused) channel, dropping everything but the crime
 * type so identity variants aren't filtered out.
 *
 * Seed attributes come from the overview load (`seed`); if that hasn't populated
 * yet we fall back to the graph's own crime-type + district nodes (`nodes`), so
 * crime/district pre-fill still works.
 */
export function buildPreFilter(
  type: NodeType,
  seed: SeedAttrs | null,
  nodes: Iterable<GraphNode>,
): AssocFilters {
  let subheadId = seed?.subhead_id;
  let districtId = seed?.district_id;
  if (!subheadId || !districtId) {
    for (const n of nodes) {
      if (n.node_type === "CRIME_SUBHEAD" && !subheadId) subheadId = n.entity_ref_id;
      if (n.node_type === "DISTRICT" && !districtId) districtId = n.entity_ref_id;
    }
  }

  // The accused channel is already the SAME person (entity resolution across
  // name variants). Only scope it to the seed's crime type — filtering on the
  // suspect's own name/age/gender would be redundant or drop valid variants.
  if (type === "ACCUSED_RECORD" || type === "VICTIM_RECORD") {
    return subheadId ? { subhead_id: subheadId } : {};
  }

  // Otherwise (district / crime / station) build the full similar-profile set.
  const f: AssocFilters = {};
  if (type !== "CRIME_SUBHEAD" && type !== "CRIME_HEAD" && subheadId) f.subhead_id = subheadId;
  if (type !== "DISTRICT" && districtId) f.district_id = districtId;
  if (seed?.accused_gender) f.gender = seed.accused_gender;
  if (seed?.accused_age != null) {
    f.age_min = Math.max(0, seed.accused_age - AGE_BAND);
    f.age_max = Math.min(120, seed.accused_age + AGE_BAND);
  }
  if (seed?.accused_name) {
    const firstName = seed.accused_name.trim().split(/\s+/)[0];
    if (firstName) f.name_contains = firstName;
  }
  return f;
}
