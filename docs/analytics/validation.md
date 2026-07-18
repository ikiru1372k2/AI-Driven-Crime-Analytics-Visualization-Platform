# Analytics validation summary

Automated, ground-truth validation of the analytics engines against the DATA-001
synthetic dataset. All suites run in CI and are **hermetic** — each generates a
fresh dataset into a temp dir and points the data layer at it, so no committed
data is required. The engines discover patterns from the data alone; the planted
answer key is read only inside the tests to *score* detection (ADR-011).

## Hotspot analytics (HOT-004 · #31)

Suite: `backend/tests/analytics/hotspot/test_hotspot_validation.py`
(DBSCAN, haversine, `eps=350 m`, `min_samples=8`, 90-day window).

| Criterion | Result |
|---|---|
| Ground-truth cluster recovered (recall ≥ 90%) | **100%** recall (57–61 / 60 members across eps range) |
| Impostor rate ≤ 10% | **~1.6%** |
| Cluster located at planted site | centroid within ~0.02° of (13.031, 77.5185) |
| Noise control: no false clusters | every non-hotspot crime type → **0 clusters**; unreachable `min_samples` → 0 |
| Cyclic midnight handling | night_share **0.98**; histogram populated on both sides of 00:00 |
| Coordinate-exclusion accounting | geolocated = total − documented missing, **exactly** |
| eps ±10% stability | ≥ **93%** membership retained (criterion: ≥ 80%) |

Out of scope (documented non-goal): a dedicated spatiotemporal *clustering* mode
(23:59 / 00:01 co-cluster fixtures). The engine clusters spatially and reports a
cyclic time-of-day profile per cluster; the midnight test validates that profile.

## Emerging trends (TREND · #35)

Suite: `backend/tests/analytics/test_trends.py` (robust weekly baseline,
median + MAD, modified z-score).

| Criterion | Result |
|---|---|
| Planted spike discovered & top-ranked | Robbery @ Peenya, **z ≈ 10**, severity critical |
| Baseline vs recent separation | recent weekly ≫ baseline median (≈ 4/wk) |
| Sensitivity | threshold above the spike's z → 0 alerts |
| Sparsity | `min_recent` above any series → 0 alerts |
| Stability | stationary background → ≤ 5 alerts at a high threshold |
