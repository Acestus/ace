#!/usr/bin/env python3
"""
sdp_approval.py — Create approval levels and approvers on an SDP request,
poll status, and project current state for markdown sync.

Mirror of jira_approval.py.

Usage:
    # Create L1 approval and add 2 approvers
    python3 scripts/sdp_approval.py --id 33903 --create-level 1 \\
        --approvers ryan@<ORG_DOMAIN>,rajan@<ORG_DOMAIN>

    # Poll current approval state
    python3 scripts/sdp_approval.py --id 33903 --status

    # Reconcile from markdown ## Approval section
    python3 scripts/sdp_approval.py --id 33903 --reconcile
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    REPO_ROOT, load_env_file, get_sdp_token, resolve_long_id, fetch_request,
    fetch_approval_levels, fetch_approvals, create_approval_level, add_approver,
    extract_section, parse_approval_section, _txt,
)


def project_status(long_id: str, token: str) -> dict:
    levels = fetch_approval_levels(long_id, token)
    out = []
    for lv in levels:
        lv_id = _txt(lv.get("id"))
        approvers = fetch_approvals(long_id, lv_id, token) if lv_id else []
        out.append({
            "id": lv_id,
            "level": lv.get("level"),
            "status": _txt(lv.get("status")),
            "approvers": [{
                "email": _txt((a.get("approver") or {}).get("email_id")),
                "name": _txt((a.get("approver") or {}).get("name")),
                "status": _txt(a.get("status")),
            } for a in approvers],
        })
    return {"approval_levels": out}


def reconcile_from_markdown(long_id: str, display_id: str, token: str,
                            dry_run: bool = False) -> dict:
    case_dir = REPO_ROOT / "cases" / display_id
    md_files = list(case_dir.glob("*.md")) if case_dir.exists() else []
    if not md_files:
        return {"error": f"no markdown in cases/{display_id}/"}
    text = md_files[0].read_text()
    body = extract_section(text, "Approval") or ""
    desired = parse_approval_section(body)

    existing_levels = fetch_approval_levels(long_id, token)
    existing_by_level = {lv.get("level"): lv for lv in existing_levels}

    actions = {"create_levels": [], "add_approvers": [], "noop_levels": []}
    for d in desired:
        lv_num = d["level"]
        existing_lv = existing_by_level.get(lv_num)
        if not existing_lv:
            actions["create_levels"].append(lv_num)
            if not dry_run:
                resp = create_approval_level(long_id, lv_num, token)
                lv_id = _txt((resp.get("approval_level") or {}).get("id"))
            else:
                lv_id = f"<would-create-L{lv_num}>"
        else:
            lv_id = _txt(existing_lv.get("id"))
            actions["noop_levels"].append(lv_num)

        # add approvers not already on the level
        existing_approvers = fetch_approvals(long_id, lv_id, token) if (existing_lv and not dry_run) else []
        existing_emails = {
            _txt((a.get("approver") or {}).get("email_id")).lower()
            for a in existing_approvers
        }
        to_add = [e for e in d["approvers"] if e.lower() not in existing_emails]
        if to_add:
            actions["add_approvers"].append({"level": lv_num, "emails": to_add})
            if not dry_run:
                add_approver(long_id, lv_id, to_add, token)

    return {"dry_run": dry_run, "actions": actions}


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Manage SDP approvals")
    p.add_argument("--id", required=True)
    p.add_argument("--create-level", type=int)
    p.add_argument("--approvers", help="Comma-separated approver emails")
    p.add_argument("--status", action="store_true", help="Print current approval status")
    p.add_argument("--reconcile", action="store_true",
                   help="Reconcile from markdown ## Approval section")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)

    if args.status:
        print(json.dumps(project_status(long_id, token), indent=2))
        return

    if args.reconcile:
        request = fetch_request(long_id, token)
        display_id = _txt(request.get("display_id"))
        result = reconcile_from_markdown(long_id, display_id, token, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return

    if args.create_level:
        if not args.dry_run:
            resp = create_approval_level(long_id, args.create_level, token)
            print(f"✓ Created approval level {args.create_level}")
            if args.approvers:
                lv_id = _txt((resp.get("approval_level") or {}).get("id"))
                emails = [e.strip() for e in args.approvers.split(",") if e.strip()]
                add_approver(long_id, lv_id, emails, token)
                print(f"✓ Added {len(emails)} approver(s) to L{args.create_level}")
        else:
            print(json.dumps({"would_create_level": args.create_level,
                              "would_add_approvers": args.approvers.split(",") if args.approvers else []},
                             indent=2))
        return

    p.error("Pass --status, --reconcile, or --create-level")


if __name__ == "__main__":
    main()
