#!/usr/bin/env python3
"""Precompute MO profiles with Catalyst Zia, offline (MO-002/#38).

Why this exists: zcatalyst_sdk.initialize() requires Catalyst platform headers
that are only injected on authenticated requests. A browser hitting the AppSail
URL directly carries none, so the deployed runtime can never reach Zia on that
path — extraction there falls back to the deterministic extractor.

So Zia runs HERE, against the real project, through the authenticated CLI
session (scripts/catalyst/catalyst_api.js), and the validated profiles ship
with the deployment bundle. The demo is then genuinely Zia-derived, fast, and
reproducible — no live API call, no rate limit, no cold-start penalty
(also the demo-reliability requirement in #82).

Usage (from repo root, with `catalyst login` done):

    PYTHONPATH=backend python scripts/mo_precompute.py \
        --project-id 42171000000017001 --app-dir .catalyst-app

Writes data/mo_profiles.json. Re-run after changing the lexicon or bumping
MODEL_VERSION.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts/catalyst/catalyst_api.js"
DEFAULT_OUT = ROOT / "data/mo_profiles.json"

#: Zia accepts a list of documents and returns one entry per document, but
#: rejects oversized batches with "size of the input is in the correct range".
#: Measured against AI-KSP on 2026-07-21: 10 documents OK, 20 rejected.
BATCH_SIZE = 10


def call_zia(project_id: str, app_dir: Path, endpoint: str, documents: list[str]) -> list:
    """POST one batch to a Zia text-analytics endpoint via the CLI session."""
    payload = json.dumps({"document": documents})
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            "node",
            str(BRIDGE),
            "POST",
            f"/baas/v1/project/{project_id}/ml/text-analytics/{endpoint}",
            payload,
        ],
        capture_output=True,
        text=True,
        cwd=app_dir,
        timeout=180,
    )
    try:
        body = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise SystemExit(f"zia bridge failed: {proc.stdout}{proc.stderr}") from None
    if "error" in body:
        raise SystemExit(f"zia error on {endpoint}: {body['error']}")
    return body.get("body", {}).get("data") or []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--app-dir", default=str(ROOT / ".catalyst-app"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=None, help="first N narratives only")
    args = ap.parse_args(argv)

    from kavach.analytics.mo.extractor import MODEL_VERSION, ExtractionSkipped, extract
    from kavach.analytics.mo.schema import MoValidationError
    from kavach.analytics.mo.zia import parse_signal
    from kavach.api import data

    app_dir = Path(args.app_dir)
    if not (app_dir / "catalyst.json").is_file():
        raise SystemExit(f"{app_dir} is not a Catalyst app directory")

    narratives = sorted(data.case_narratives().items())
    if args.limit:
        narratives = narratives[: args.limit]
    if not narratives:
        raise SystemExit("no narratives found — generate the dataset first")

    print(f"extracting {len(narratives)} narratives with Zia (batches of {BATCH_SIZE})")

    profiles: list[dict] = []
    skipped = failed = zia_docs = 0

    for start in range(0, len(narratives), BATCH_SIZE):
        batch = narratives[start : start + BATCH_SIZE]
        documents = [text for _, text in batch]

        keywords = call_zia(args.project_id, app_dir, "keyword-extraction", documents)
        ner = call_zia(args.project_id, app_dir, "ner", documents)
        zia_docs += len(documents)

        for idx, (case_id, text) in enumerate(batch):
            # parse_signal expects a single-document payload
            signal = parse_signal(
                [keywords[idx]] if idx < len(keywords) else [],
                [ner[idx]] if idx < len(ner) else [],
            )
            try:
                result = extract(case_id, text, signal)
            except ExtractionSkipped:
                skipped += 1
                continue
            except MoValidationError as exc:
                failed += 1
                print(f"  case {case_id}: EXTRACTION_FAILED — {exc}", file=sys.stderr)
                continue
            profiles.append(json.loads(result.profile.model_dump_json()))

        done = min(start + BATCH_SIZE, len(narratives))
        print(f"  {done}/{len(narratives)}", end="\r", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "extractor": "ZIA_TEXT_ANALYTICS",
                "zia_documents": zia_docs,
                "profiles": profiles,
            },
            separators=(",", ":"),  # ships in the deploy bundle; keep it small
        )
    )
    print(
        f"\nwrote {len(profiles)} profiles -> {out} "
        f"(skipped {skipped}, failed {failed}, {out.stat().st_size // 1024} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
