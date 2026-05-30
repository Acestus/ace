#!/usr/bin/env python3
"""
sdp_set_flow.py — Update the flow:* tag on an SDP request, optionally
transitioning the SDP native status to match.

Mirror of jira_set_flow.py. Removes all existing flow:* tags and adds the new one.

Usage:
    python3 scripts/sdp_set_flow.py --id 33903 --flow active
    python3 scripts/sdp_set_flow.py --id 33903 --flow done --transition
    python3 scripts/sdp_set_flow.py --id 33903 --flow waiting --transition --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, resolve_long_id, fetch_request,
    get_tags, put_tags, transition_status, FLOW_TAGS, FLOW_STATUS_MAP,
    VALID_SDP_STATUSES, request_url, _txt,
)


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Set SDP flow tag (and optional status)")
    p.add_argument("--id", required=True, help="SDP display id or long id")
    p.add_argument("--flow", required=True, choices=["queue", "active", "waiting", "done"])
    p.add_argument("--transition", action="store_true",
                   help="Also transition the SDP native status to match flow")
    p.add_argument("--status",
                   help="Override status name (e.g. 'Waiting on End User', 'Closed'). "
                        "Implies --transition. Must be one of the valid SDP statuses.")
    p.add_argument("--resolution",
                   help="Resolution text for Resolved/Closed transitions. "
                        "Required by SDP — if omitted, a generic placeholder is used.")
    p.add_argument("--closure-code", default="Success",
                   help="Closure code for Closed transitions (default: Success).")
    p.add_argument("--closure-comments",
                   help="Closure comments for Closed transitions. "
                        "If omitted, falls back to --resolution.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.status:
        if args.status not in VALID_SDP_STATUSES:
            fail(
                f"'{args.status}' is not a valid SDP status",
                causes=["Typo in status name (SDP is case-sensitive)",
                        f"Status does not exist in this SDP instance"],
                try_=[f"python3 scripts/sdp_changelog.py --id {args.id}  # see past statuses",
                      f"Valid statuses: {sorted(VALID_SDP_STATUSES)}"],
            )
        args.transition = True

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)
    request = fetch_request(long_id, token)
    if not request:
        fail(
            f"SDP request {args.id} not found",
            causes=["Request was deleted or ID is wrong", "display_id vs long ID confusion"],
            try_=[f"python3 scripts/sdp_fetch_ticket.py --id {args.id}",
                  f"Verify: https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/{args.id}"],
        )

    current_tags = set(get_tags(request))
    new_flow_tag = f"flow:{args.flow}"
    new_tags = (current_tags - FLOW_TAGS) | {new_flow_tag}
    status_target = args.status if args.status else (
        FLOW_STATUS_MAP[args.flow] if args.transition else None
    )

    if args.dry_run:
        plan = {
            "id": long_id,
            "display_id": _txt(request.get("display_id")),
            "current_tags": sorted(current_tags),
            "new_tags": sorted(new_tags),
            "status_current": _txt(request.get("status")),
            "status_target": status_target,
            "dry_run": True,
        }
        print(json.dumps(plan, indent=2) if args.json else json.dumps(plan, indent=2))
        return

    # Status first (the user-visible action); tags second as best-effort.
    # Tag PUT can fail on SDP On-Demand if the tag isn't pre-registered in the
    # workspace catalog; we warn but don't block the status transition.
    if status_target:
        transition_status(
            long_id, status_target, token,
            resolution=args.resolution,
            closure_code=args.closure_code,
            closure_comments=args.closure_comments or args.resolution,
        )
        print(f"✓ Status → {status_target}")

    tags_ok = True
    try:
        put_tags(long_id, sorted(new_tags), token)
        print(f"✓ Tags updated: {sorted(new_tags)}")
    except Exception as e:
        tags_ok = False
        print(f"⚠ Tag update failed (status transition still applied): {e}",
              file=sys.stderr)

    if args.json:
        print(json.dumps({
            "id": long_id,
            "display_id": _txt(request.get("display_id")),
            "flow": args.flow,
            "tags": sorted(new_tags) if tags_ok else sorted(current_tags),
            "tags_applied": tags_ok,
            "status": status_target or _txt(request.get("status")),
            "url": request_url(long_id),
        }, indent=2))


if __name__ == "__main__":
    main()
