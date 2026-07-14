#!/usr/bin/env python3
"""Generate the deterministic SYNTHETIC demo dataset (DATA-001/#14).

Usage: python scripts/generate_dataset.py [--seed 20260714] [--out data/synthetic]
Run from repo root with the backend venv on PYTHONPATH:
    PYTHONPATH=backend backend/.venv/bin/python scripts/generate_dataset.py
"""
import argparse
from pathlib import Path

from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=20260714)
    p.add_argument("--out", default=str(ROOT / "data/synthetic"))
    p.add_argument("--background-cases", type=int, default=2000)
    args = p.parse_args()
    gen = generate_dataset(args.out, ROOT / "docs/schema/schema-manifest.json",
                           seed=args.seed, background_cases=args.background_cases)
    dq = gen.ground_truth["data_quality"]
    print(f"generated {dq['total_cases']} cases -> {args.out} "
          f"(missing coords: {dq['missing_coordinate_cases']}, seed {args.seed})")
