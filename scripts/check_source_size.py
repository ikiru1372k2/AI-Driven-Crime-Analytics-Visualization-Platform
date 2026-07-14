#!/usr/bin/env python3
"""Source file size quality gate.

Human-maintained source files must stay <= 600 physical lines (hard gate);
401-600 lines require decomposition review. Generated/vendored/lockfiles are
excluded. Exit 1 on any QUALITY GATE FAILURE.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ["backend/kavach", "backend/tests", "frontend/src", "functions", "scripts"]
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
EXCLUDE_PARTS = {"node_modules", "dist", "build", ".venv", "__pycache__", "generated"}

BANDS = [(250, "NORMAL"), (400, "REVIEW RESPONSIBILITY"),
         (500, "HIGH COMPLEXITY REVIEW"), (600, "MANDATORY DECOMPOSITION REVIEW")]


def classify(n: int) -> str:
    for limit, label in BANDS:
        if n <= limit:
            return label
    return "QUALITY GATE FAILURE"


def main() -> int:
    failures = []
    reviews = []
    for d in SOURCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if f.suffix not in EXTENSIONS or not f.is_file():
                continue
            if EXCLUDE_PARTS.intersection(f.parts):
                continue
            n = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
            label = classify(n)
            rel = f.relative_to(ROOT)
            if label == "QUALITY GATE FAILURE":
                failures.append((rel, n))
            elif n > 400:
                reviews.append((rel, n, label))
    for rel, n, label in reviews:
        print(f"REVIEW  {rel}  {n} lines  [{label}]")
    for rel, n in failures:
        print(f"FAIL    {rel}  {n} lines  [QUALITY GATE FAILURE >600]")
    if failures:
        return 1
    print("source-size gate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
