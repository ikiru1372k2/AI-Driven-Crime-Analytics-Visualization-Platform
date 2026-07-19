#!/usr/bin/env python3
"""Seed the demo role assignments (CAT-003/#19).

Idempotent. Writes role assignments only — never credentials. Real
identities come from Catalyst Authentication; this maps an authenticated
user id to the scope it may read.

    PYTHONPATH=backend python scripts/seed_demo_roles.py [--list]
"""

from __future__ import annotations

import argparse
import sys

from kavach.auth.demo_users import DEMO_ASSIGNMENTS, seed_demo_assignments
from kavach.auth.dependency import role_repo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show assignments; write nothing")
    args = ap.parse_args(argv)

    if args.list:
        for a in DEMO_ASSIGNMENTS:
            scope = a.scope_type.value + (f":{a.scope_id}" if a.scope_id else "")
            print(f"  {a.user_id:<24} {a.role.value:<20} {scope}")
        return 0

    repo = role_repo()
    count = seed_demo_assignments(repo)
    print(f"seeded {count} demo role assignments")
    for a in DEMO_ASSIGNMENTS:
        effective = repo.effective_assignment(a.user_id)
        if effective is None:
            print(f"  FAILED to seed {a.user_id}", file=sys.stderr)
            return 1
        scope = effective.scope_type.value + (
            f":{effective.scope_id}" if effective.scope_id else ""
        )
        print(f"  {a.user_id:<24} {effective.role.value:<20} {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
