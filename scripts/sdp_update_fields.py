#!/usr/bin/env python3
"""
sdp_update_fields.py — Update SDP request fields (description, group,
category, priority, urgency, impact, technician).

Imperative CLI / escape hatch. For markdown-driven reconciliation use sync_sdp_fields.py.

Usage:
    python3 scripts/sdp_update_fields.py --id 33903 --urgency "2 - High"
    python3 scripts/sdp_update_fields.py --id 33903 --priority "Medium" --group "Infrastructure"
    python3 scripts/sdp_update_fields.py --id 33903 --technician <YOUR_EMAIL>
    python3 scripts/sdp_update_fields.py --id 33903 --description-file /tmp/new-desc.html
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, resolve_long_id, sdp_put, _txt, fetch_request,
)


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Update SDP request fields")
    p.add_argument("--id", required=True)
    p.add_argument("--subject")
    p.add_argument("--description")
    p.add_argument("--description-file", help="Read description body from file (HTML or plain)")
    p.add_argument("--priority", help="Priority name (e.g. Low, Medium, High)")
    p.add_argument("--urgency", help="Urgency name (e.g. '2 - High')")
    p.add_argument("--impact", help="Impact name")
    p.add_argument("--group", help="Group name")
    p.add_argument("--technician", help="Technician email")
    p.add_argument("--category", help="Category name")
    p.add_argument("--subcategory", help="Subcategory name")
    p.add_argument("--item", help="Item name")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    fields: dict = {}
    if args.subject:
        fields["subject"] = args.subject
    if args.description:
        fields["description"] = args.description
    if args.description_file:
        fields["description"] = Path(args.description_file).read_text()
    if args.priority:
        fields["priority"] = {"name": args.priority}
    if args.urgency:
        fields["urgency"] = {"name": args.urgency}
    if args.impact:
        fields["impact"] = {"name": args.impact}
    if args.group:
        fields["group"] = {"name": args.group}
    if args.technician:
        fields["technician"] = {"email_id": args.technician}
    if args.category:
        fields["category"] = {"name": args.category}
    if args.subcategory:
        fields["subcategory"] = {"name": args.subcategory}
    if args.item:
        fields["item"] = {"name": args.item}

    if not fields:
        p.error("At least one field to update is required")

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)

    payload = {"request": fields}
    if args.dry_run:
        print(json.dumps({"id": long_id, "payload": payload, "dry_run": True}, indent=2))
        return

    sdp_put(f"/api/v3/requests/{long_id}", token, payload)
    request = fetch_request(long_id, token)
    if args.json:
        print(json.dumps({
            "id": long_id,
            "display_id": _txt(request.get("display_id")),
            "updated": list(fields.keys()),
        }, indent=2))
    else:
        print(f"✓ Updated SDP-{_txt(request.get('display_id'))}: {list(fields.keys())}")


if __name__ == "__main__":
    main()
