#!/usr/bin/env python3
"""
sdp_changelog.py — Fetch request history (status, owner, field changes).

Mirror of jira_changelog.py.

Usage:
    python3 scripts/sdp_changelog.py --id 33903
    python3 scripts/sdp_changelog.py --id 33903 --json
    python3 scripts/sdp_changelog.py --id 33903 --field status
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, resolve_long_id, fetch_history, _txt,
)


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Fetch SDP request history")
    p.add_argument("--id", required=True)
    p.add_argument("--field", help="Filter to a single field (e.g. status, technician)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--rows", type=int, default=100)
    args = p.parse_args()

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)
    history = fetch_history(long_id, token, row_count=args.rows)

    if args.field:
        history = [h for h in history if any(
            (op.get("name") or op.get("field") or "").lower() == args.field.lower()
            for op in (h.get("operation") or [])
        )]

    if args.json:
        print(json.dumps(history, indent=2, default=str))
        return

    if not history:
        print("No history entries.")
        return

    for h in history:
        when = _txt((h.get("performed_time") or {}).get("display_value"))
        who = _txt((h.get("performed_by") or {}).get("name"))
        op = h.get("operation") or []
        if isinstance(op, list):
            ops_text = "; ".join(_txt(o) for o in op if o)
        else:
            ops_text = _txt(op)
        print(f"  [{when}] {who}: {ops_text[:200]}")


if __name__ == "__main__":
    main()
