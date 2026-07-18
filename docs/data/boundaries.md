# District boundary geometry (provenance)

The district choropleth on the map (#61) uses approximate public boundary
polygons for the four districts present in the synthetic dataset.

- **File:** `frontend/public/karnataka-districts.geojson`
- **Source:** GADM v2 India district boundaries, via the public
  [`geohacker/india`](https://github.com/geohacker/india) dataset
  (`district/india_district.geojson`).
- **Processing:** filtered to the four districts in the demo data, coordinates
  simplified to ~3-decimal precision (~100 m) to keep the file small
  (~58 KB). Provenance is also embedded in the file's `_provenance` field.
- **Name mapping** (GADM legacy name → dataset district):
  Bangalore Urban → Bengaluru City (44), Mysore → Mysuru (20),
  Tumkur → Tumakuru (12), Belgaum → Belagavi (9).

## Limitations

Boundaries are **approximate** and for demonstration only — simplified, and from
a legacy administrative snapshot (pre-recent district reorganisation). They are
not authoritative and must not be used for any operational or legal purpose. All
crime data shown is SYNTHETIC (ADR-011).
