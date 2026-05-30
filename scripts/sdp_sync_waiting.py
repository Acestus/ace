#!/usr/bin/env python3
"""
sdp_sync_waiting.py — Reconcile SDP cases tagged flow:waiting.

For each flow:waiting case:
  - Pulls the request from SDP
  - Reports staleness (days since last activity)
  - Surfaces approval status
  - Reports current notes count

Mirror of jira_sync_waiting.py.

Usage:
    python3 scripts/sdp_sync_waiting.py
    python3 scripts/sdp_sync_waiting.py --json
    python3 scripts/sdp_sync_waiting.py --threshold-days 3
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, search_requests, fetch_request,
    fetch_notes, get_tags, _txt, request_url,
)


def _parse_sdp_ms(field) -> datetime | None:
    if not isinstance(field, dict):
        return None
    v = field.get("value")
    if not v:
        return None
    try:
        return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Sync flow:waiting SDP cases")
    p.add_argument("--threshold-days", type=int, default=3,
                   help="Flag cases stale beyond this many days")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    token = get_sdp_token()
    # Cast wide net by status; flow:waiting maps to On Hold (per FLOW_STATUS_MAP)
    requests = search_requests(
        {"search_fields": {"status.name": "On Hold"}},
        token, row_count=100,
    )
    # Filter to those actually tagged flow:waiting
    waiting = [r for r in requests if "flow:waiting" in get_tags(r)]

    now = datetime.now(timezone.utc)
    out = []
    for r in waiting:
        long_id = _txt(r.get("id"))
        # Fetch full record for tags + most recent note
        full = fetch_request(long_id, token)
        notes = fetch_notes(long_id, token, row_count=1)
        last_note_ts = _parse_sdp_ms((notes[0].get("created_time") or {}) if notes else None)
        created_ts = _parse_sdp_ms(full.get("created_time"))
        last_activity = last_note_ts or created_ts
        stale_days = (now - last_activity).days if last_activity else None
        item = {
            "id": long_id,
            "display_id": _txt(full.get("display_id")),
            "subject": _txt(full.get("subject")),
            "status": _txt(full.get("status")),
            "approval_status": _txt(full.get("approval_status")),
            "tags": get_tags(full),
            "stale_days": stale_days,
            "last_activity": last_activity.isoformat() if last_activity else None,
            "stale": stale_days is not None and stale_days >= args.threshold_days,
            "url": request_url(long_id),
        }
        out.append(item)

    out.sort(key=lambda x: x["stale_days"] or 0, reverse=True)

    if args.json:
        print(json.dumps(out, indent=2))
        return

    if not out:
        print("No flow:waiting SDP cases.")
        return

    print(f"\nflow:waiting SDP cases ({len(out)}):\n")
    for it in out:
        stale_marker = "⚠ " if it["stale"] else "  "
        print(f"{stale_marker}SDP-{it['display_id']:>6} [{(it['approval_status'] or it['status'])[:14]:>14}] "
              f"{it['stale_days'] or 0:>3}d  {it['subject'][:60]}")


if __name__ == "__main__":
    main()
