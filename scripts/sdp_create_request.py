#!/usr/bin/env python3
"""
sdp_create_request.py — Create a new SDP request from CLI.

Mirror of jira_create_issue.py.

Usage:
    python3 scripts/sdp_create_request.py \\
        --subject "Grant Reader access to ws_loanetl" \\
        --requester user@<ORG_PARENT_DOMAIN> \\
        --description "Need read access to test Fabric pipelines" \\
        --group "CloudOps" \\
        --category "IT Support" \\
        --subcategory "Access & Credentials" \\
        --item "Account Creation & Deletion" \\
        --technician <YOUR_EMAIL> \\
        --approver <APPROVER_EMAIL>

Notes:
    - --category, --subcategory, --item are required by SDP when --group is set.
      Safe defaults: category="IT Support", subcategory="Access & Credentials",
      item="Account Creation & Deletion"
    - --approver creates an approval level 1 and adds the approver immediately.
      Use comma-separated emails for multiple approvers.
    - Approval POST uses singular {"approval": {...}} wrapper — SDP rejects bulk arrays.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, sdp_post, _txt, request_url,
    create_approval_level, add_approver,
)

# SDP requires category+subcategory+item when a group is assigned.
DEFAULT_CATEGORY = "IT Support"
DEFAULT_SUBCATEGORY = "Access & Credentials"
DEFAULT_ITEM = "Account Creation & Deletion"


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Create a new SDP request")
    p.add_argument("--subject", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--requester", required=True, help="Requester email")
    p.add_argument("--group", help="Group name (e.g. CloudOps)")
    p.add_argument("--technician", help="Technician email")
    p.add_argument("--priority", help="Priority name (e.g. Medium)")
    p.add_argument("--impact", help="Impact name")
    p.add_argument("--category", help=f"Category name (default: {DEFAULT_CATEGORY!r})")
    p.add_argument("--subcategory", help=f"Subcategory name (default: {DEFAULT_SUBCATEGORY!r})")
    p.add_argument("--item", help=f"Item name (default: {DEFAULT_ITEM!r})")
    p.add_argument("--approver", help="Comma-separated approver email(s) — creates L1 approval level")
    p.add_argument("--tags", help="Comma-separated tags to apply on create")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    request: dict = {
        "subject": args.subject,
        "description": args.description,
        "requester": {"email_id": args.requester},
    }
    if args.group:
        request["group"] = {"name": args.group}
        # SDP requires all three when group is set
        request["category"] = {"name": args.category or DEFAULT_CATEGORY}
        request["subcategory"] = {"name": args.subcategory or DEFAULT_SUBCATEGORY}
        request["item"] = {"name": args.item or DEFAULT_ITEM}
    else:
        if args.category:
            request["category"] = {"name": args.category}
        if args.subcategory:
            request["subcategory"] = {"name": args.subcategory}
        if args.item:
            request["item"] = {"name": args.item}

    if args.technician:
        request["technician"] = {"email_id": args.technician}
    if args.priority:
        request["priority"] = {"name": args.priority}
    if args.impact:
        request["impact"] = {"name": args.impact}
    if args.tags:
        request["tags"] = [{"name": t.strip()} for t in args.tags.split(",") if t.strip()]

    token = get_sdp_token()
    resp = sdp_post("/api/v3/requests", token, {"request": request})
    created = resp.get("request", {})
    long_id = _txt(created.get("id"))
    display_id = _txt(created.get("display_id"))

    approval_results = []
    if args.approver:
        emails = [e.strip() for e in args.approver.split(",") if e.strip()]
        lv = create_approval_level(long_id, 1, token)
        lv_id = _txt(lv.get("approval_level", {}).get("id"))
        approval_results = add_approver(long_id, lv_id, emails, token)

    if args.json:
        print(json.dumps({
            "id": long_id,
            "display_id": display_id,
            "subject": args.subject,
            "url": request_url(long_id),
            "approvers_added": [r.get("approval", {}).get("approver", {}).get("name") for r in approval_results],
        }, indent=2))
    else:
        print(f"✓ Created SDP-{display_id}")
        print(f"  Long ID: {long_id}")
        print(f"  URL    : {request_url(long_id)}")
        for r in approval_results:
            name = r.get("approval", {}).get("approver", {}).get("name", "?")
            print(f"  ✓ Approver added: {name}")


if __name__ == "__main__":
    main()
