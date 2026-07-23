# Keeping the request path fast on the Data Store (PERF-001)

Flipping `KAVACH_DATA_SOURCE=datastore` ([datastore-read-adapter.md](datastore-read-adapter.md))
made the heavy analytics endpoints slow or time out. This note explains the cause
and the in-process fix, and points at the production follow-up (EVT-003).

## The death-spiral

AppSail gives an HTTP handler **30 seconds**. A cold read of the whole dataset is
longer than that:

- CaseMaster is 16,652 rows and ZCQL caps a query at 300 rows, so one table is
  **56 sequential OAuth round-trips** (~20s); `enriched_cases()` joins 8 tables
  (~30s cold), and association/anomaly also pull Accused/Victim.
- `resolve_identities()` is an O(n²) pairwise compare over every accused record
  (~90s cold), and backs **both** `/identities` and `/associations`.

Because the cold read is longer than the request limit, it never finishes on the
request path → the cache never warms → the *next* request is cold too. The second
call was slower, not faster.

## The fix: warm off the request path, serve from memory

The request path never triggers a cold read. A background daemon does the slow
work (it is **not** bound by the 30s HTTP limit) and publishes the result in
memory; requests read that instantly.

- **`backend/kavach/api/snapshot.py`** — an in-memory, atomically-swappable set of
  the raw source tables, shaped exactly like the CSVs. `data._read` and
  `graph_store` serve from it when present.
- **`backend/kavach/api/warmer.py`** — a daemon thread started from the app's
  startup handler. On boot it publishes a **CSV bootstrap** snapshot synchronously (the
  store was seeded from those rows, so the app is usable immediately), then:
  - **primes** the expensive caches off the request path — `enriched_cases`,
    `accused_records`, `victim_records`, `resolve_identities` (the ~90s step),
    the graph context, and the memoized anomaly scan + area-risk forecast;
  - in Data Store mode, reads the tables **live** and atomically swaps the
    snapshot in, then refreshes every `KAVACH_DATASTORE_TTL` seconds. A failed
    refresh keeps the last-good snapshot — the app never regresses to timeouts.
- **Memoization** (`backend/kavach/api/ttl_cache.py::timed_cache_keyed`) caches the
  per-request analytics — the anomaly IsolationForest scan and the risk forecast —
  per parameters with the data TTL, so repeat requests and the warmer reuse one
  computed result instead of refitting the model and re-calling the LLM every time.
  The cache is **production-path only** (injected test clients always run fresh),
  and returns a shallow copy so a route adding its provenance envelope can't corrupt
  the cached dict.

Freshness is still the TTL: a console edit appears within `KAVACH_DATASTORE_TTL`
seconds, and the swap is atomic so a request never sees a half-built snapshot.

### Guards

- The warmer is a **no-op under pytest** (`"pytest" in sys.modules`) so the suite is
  never slowed or raced; set `KAVACH_WARMER_FORCE=1` to opt in (the warmer's own
  test does this).
- Rollback is instant and code-free: set `KAVACH_DATA_SOURCE=csv` and restart — the
  bundled snapshot serves, no Data Store involved.

## Production follow-up (EVT-003 + Object Store)

The in-process warmer is the scheduler **for a single instance**. For a multi-instance
production deployment each instance would warm its own copy; the Catalyst-native
answer is a scheduled job that snapshots the Data Store to shared storage:

- A **Catalyst Cron Function** (15-minute budget, well clear of the 30s HTTP limit)
  recomputes the snapshot and writes it to the **Object Store**; app instances pull
  the latest snapshot on boot/timer instead of each doing the cold read.
- This is tracked as **EVT-003** (Scheduled analytics recomputation via Catalyst
  Cron) in [../planning/backlog/13-evt.md](../planning/backlog/13-evt.md). It is
  **not** built in the PERF-001 PR — the in-process warmer already removes the
  timeouts for the demo's single instance.
