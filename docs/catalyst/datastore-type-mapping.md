# Catalyst Data Store Type Mapping (CAT-002/#18)

Physical **column names** in Catalyst Data Store are the documented ER names
verbatim (incl. `caste_master_id`, `latitude`, `csdate`) — name/meaning
adaptation is prohibited. **Type** adaptation is allowed and documented here;
this table is the single source for `scripts/catalyst/provision_datastore.py`.

| Documented ER type | Catalyst Data Store type | Notes |
|---|---|---|
| `INT` | `bigint` | All integer ids; bigint avoids range surprises |
| `BIT` | `boolean` | Matrix Q2 exception: `Victim.VictimPolice` is documented `VARCHAR` and stays `varchar` |
| `DATE` | `date` | |
| `DATETIME` | `datetime` | |
| `DECIMAL` | `double` | `CaseMaster.latitude/longitude` |
| `VARCHAR` | `varchar` | Data Store default length (255) |
| `CHAR` | `varchar` | |
| `NVARCHAR(MAX)` | `text` | `CaseMaster.BriefFacts` — exceeds varchar limits |

## Keys and system columns

- Catalyst adds system columns to every table: `ROWID` (system PK),
  `CREATORID`, `CREATEDTIME`, `MODIFIEDTIME`. These are excluded from the
  parity check.
- Documented ER primary keys (e.g. `CaseMasterID`) are stored as ordinary
  columns; uniqueness is enforced at the ingestion layer (DATA-002 rejects
  duplicate PKs per-row). Data Store does not support user-defined PKs.
- Documented FKs are recorded in `schema-manifest.json`; they are provisioned
  as plain columns (bigint), with referential integrity checked by the
  ingestion FK report — not by Data Store constraints.

## Scope

- All 26 source tables from `docs/schema/schema-manifest.json` (matrix §1).
- Referenced-but-undefined tables (matrix §2: `Inv_OccuranceTime`,
  `inv_arrestsurrenderaccused`) are **not** created.
- Derived tables currently provisioned (implemented by landed code):
  `IntelligenceRun`, `IntelligenceEvidence` (#24), `CrimeGraphNode`,
  `CrimeGraphEdge` (#43). Engine result tables (`HotspotResult`,
  `TrendAlert`, `AnomalyResult`, `AreaRiskScore`, …) are added by their
  engine issues.

## Deviation log

- **`GenderID` (Employee, ComplainantDetails, Victim, Accused): `INT` → `varchar`,
  not `bigint`.** The ER matrix documents `GenderID` as `INT` but annotates it
  with "values like m/f/t" / "M/F/T" — it carries single-char categorical codes,
  not numeric ids. `bigint` rejects `"M"`/`"F"`. Provisioned as `varchar` via
  `COLUMN_TYPE_OVERRIDES` in `provision_datastore.py`. Column **name** is
  unchanged (fidelity preserved); only the physical type is adapted.

No forced column renames (no Data Store reserved-word collisions encountered in
the documented schema).

## Drift policy

`provision_datastore.py` is create-if-missing. An existing table whose
physical columns differ from the documented columns is **reported and never
silently altered**; reconcile manually and re-run.
