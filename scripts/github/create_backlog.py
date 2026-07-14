#!/usr/bin/env python3
"""Create the KAVACH AI engineering backlog on GitHub from docs/planning/backlog/*.md.

Two-pass: (1) create issues in file order recording key->number in
docs/planning/issue-map.json, (2) replace {{KEY}} tokens in bodies with #N and
edit issues in place. Idempotent: keys already present in issue-map.json are
skipped on re-run.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/planning/backlog"
MAP_FILE = ROOT / "docs/planning/issue-map.json"

MILESTONES = {
    "M0": "M0 — Repository & Architecture Control",
    "M1": "M1 — FIR Data Foundation & ER Conformance",
    "M2": "M2 — Catalyst Platform Foundation",
    "M3": "M3 — Analytics Foundation & Provenance",
    "M4": "M4 — Spatiotemporal Intelligence",
    "M5": "M5 — MO Intelligence",
    "M6": "M6 — Association & Identity Intelligence",
    "M7": "M7 — Anomaly & Area Risk Intelligence",
    "M8": "M8 — Intelligence Visualization Experience",
    "M9": "M9 — Event-Driven Automation, Security & Governance",
    "M10": "M10 — Demo, Deployment & Submission",
}


def sh(args, check=True, capture=True):
    r = subprocess.run(args, capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed: {args}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip() if capture else ""


def parse_blocks():
    blocks = []
    for f in sorted(BACKLOG.glob("*.md")):
        text = f.read_text()
        for raw in re.split(r"^=== ISSUE ===\s*$", text, flags=re.M):
            raw = raw.strip()
            if not raw:
                continue
            meta_part, _, body = raw.partition("--- BODY ---")
            meta = {}
            for line in meta_part.strip().splitlines():
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
            blocks.append({
                "key": meta["key"],
                "title": meta["title"],
                "labels": [l.strip() for l in meta.get("labels", "").split(",") if l.strip()],
                "milestone": MILESTONES.get(meta.get("milestone", ""), None),
                "estimate": meta.get("estimate", "-"),
                "risk": meta.get("risk", "-"),
                "blocked_by": [b.strip() for b in meta.get("blocked_by", "").split(",") if b.strip()],
                "body": body.strip(),
            })
    return blocks


def header(b):
    dep = ", ".join("{{%s}}" % k for k in b["blocked_by"]) or "—"
    return (f"> **Key:** `{b['key']}` · **Estimate:** {b['estimate']} · "
            f"**Risk:** {b['risk']} · **Blocked by:** {dep}\n\n")


def main():
    blocks = parse_blocks()
    keys = [b["key"] for b in blocks]
    assert len(keys) == len(set(keys)), "duplicate keys"
    print(f"parsed {len(blocks)} issues")

    issue_map = json.loads(MAP_FILE.read_text()) if MAP_FILE.exists() else {}

    # pass 1: create
    for b in blocks:
        if b["key"] in issue_map:
            print(f"skip {b['key']} (exists as #{issue_map[b['key']]})")
            continue
        body = header(b) + b["body"]
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
            tf.write(body)
            path = tf.name
        args = ["gh", "issue", "create", "--title", b["title"], "--body-file", path]
        for l in b["labels"]:
            args += ["--label", l]
        if b["milestone"]:
            args += ["--milestone", b["milestone"]]
        url = sh(args)
        num = int(url.rstrip("/").rsplit("/", 1)[-1])
        issue_map[b["key"]] = num
        MAP_FILE.write_text(json.dumps(issue_map, indent=2) + "\n")
        print(f"created {b['key']} -> #{num}")

    # pass 2: resolve {{KEY}} tokens
    token = re.compile(r"\{\{([A-Z]+-[0-9A-Za-z]+)\}\}")
    for b in blocks:
        num = issue_map[b["key"]]
        body = header(b) + b["body"]
        resolved = token.sub(lambda m: f"#{issue_map[m.group(1)]}" if m.group(1) in issue_map else m.group(1), body)
        if resolved == body and "{{" not in body:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
            tf.write(resolved)
            path = tf.name
        sh(["gh", "issue", "edit", str(num), "--body-file", path])
        print(f"resolved refs in {b['key']} (#{num})")

    print(json.dumps({"total": len(blocks)}, indent=2))


if __name__ == "__main__":
    main()
