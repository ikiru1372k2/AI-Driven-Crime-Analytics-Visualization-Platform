import { describe, expect, it } from "vitest";
import { AGE_BAND, buildPreFilter, type SeedAttrs } from "./graphPreFilter";

/** A seed case whose primary suspect has a name/age/gender — the name is the
 *  attribute that must NOT leak into place/charge expansions (Issue 2). */
const SEED: SeedAttrs = {
  subhead_id: "5",
  district_id: "44",
  station_id: "4430",
  accused_name: "Ravi Kumar",
  accused_age: 28,
  accused_gender: "M",
};

describe("buildPreFilter — no name pre-filter on place/charge expansions (Issue 2)", () => {
  it("does not pre-fill name_contains when expanding a DISTRICT", () => {
    const f = buildPreFilter("DISTRICT", SEED, []);
    expect(f.name_contains).toBeUndefined();
    // the district itself is redundant (every result shares it) so it's dropped,
    // but the rest of the similar-profile set is kept
    expect(f.district_id).toBeUndefined();
    expect(f.subhead_id).toBe("5");
    expect(f.gender).toBe("M");
    expect(f.age_min).toBe(28 - AGE_BAND);
    expect(f.age_max).toBe(28 + AGE_BAND);
  });

  it("does not pre-fill name_contains when expanding a POLICE_STATION", () => {
    const f = buildPreFilter("POLICE_STATION", SEED, []);
    expect(f.name_contains).toBeUndefined();
    expect(f.subhead_id).toBe("5");
    expect(f.district_id).toBe("44");
    expect(f.gender).toBe("M");
  });

  it("does not pre-fill name_contains when expanding a CRIME_SUBHEAD", () => {
    const f = buildPreFilter("CRIME_SUBHEAD", SEED, []);
    expect(f.name_contains).toBeUndefined();
    // the crime type is redundant here, so it's dropped; district is kept
    expect(f.subhead_id).toBeUndefined();
    expect(f.district_id).toBe("44");
  });

  it("does not pre-fill name_contains when expanding a CRIME_HEAD", () => {
    const f = buildPreFilter("CRIME_HEAD", SEED, []);
    expect(f.name_contains).toBeUndefined();
  });
});

describe("buildPreFilter — same-person channel is crime-type only", () => {
  it("scopes an ACCUSED_RECORD expansion to the crime type alone", () => {
    expect(buildPreFilter("ACCUSED_RECORD", SEED, [])).toEqual({ subhead_id: "5" });
  });

  it("scopes a VICTIM_RECORD expansion to the crime type alone", () => {
    expect(buildPreFilter("VICTIM_RECORD", SEED, [])).toEqual({ subhead_id: "5" });
  });
});
