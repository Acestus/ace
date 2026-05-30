#!/usr/bin/env python3
"""
sdp_search.py — Search/filter SDP requests (Jira jira_search analogue).

Usage:
    python3 scripts/sdp_search.py --status "Open"
    python3 scripts/sdp_search.py --tag "flow:queue"
    python3 scripts/sdp_search.py --keyword "fabric pipeline"
    python3 scripts/sdp_search.py --group "Infrastructure"
    python3 scripts/sdp_search.py --requester rarora@<ORG_PARENT_DOMAIN>
    python3 scripts/sdp_search.py --tag flow:waiting --json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, search_requests, _txt, request_url,
    get_tags,
)


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Search SDP requests")
    p.add_argument("--status", help="Status name (e.g. Open, On Hold, Resolved)")
    p.add_argument("--tag", action="append", default=[], help="Tag filter (repeatable)")
    p.add_argument("--keyword", help="Subject keyword")
    p.add_argument("--group", help="Group name")
    p.add_argument("--technician", help="Technician name")
    p.add_argument("--requester", help="Requester email")
    p.add_argument("--row-count", "--limit", dest="row_count", type=int, default=50)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    token = get_sdp_token()

    search_fields = {}
    if args.status:
        search_fields["status.name"] = args.status
    if args.keyword:
        search_fields["subject"] = args.keyword
    if args.group:
        search_fields["group.name"] = args.group
    if args.technician:
        search_fields["technician.name"] = args.technician
    if args.requester:
        search_fields["requester.email_id"] = args.requester
    # Tag filtering is server-side limited; we filter client-side after fetch
    filters = {"search_fields": search_fields} if search_fields else {}

    requests = search_requests(filters, token, row_count=args.row_count)

    if args.tag:
        wanted = set(args.tag)
        requests = [r for r in requests if wanted.issubset(set(get_tags(r)))]

    if args.json:
        out = [{
            "id": _txt(r.get("id")),
            "display_id": _txt(r.get("display_id")),
            "subject": _txt(r.get("subject")),
            "status": _txt(r.get("status")),
            "priority": _txt(r.get("priority")),
            "urgency": _txt(r.get("urgency")),
            "tags": get_tags(r),
            "requester": _txt((r.get("requester") or {}).get("name")),
            "group": _txt(r.get("group")),
            "technician": _txt(r.get("technician")),
            "url": request_url(_txt(r.get("id"))),
        } for r in requests]
        print(json.dumps(out, indent=2))
        return

    if not requests:
        print("No matching SDP requests.")
        return

    print(f"Found {len(requests)} SDP request(s):\n")
    for r in requests:
        did = _txt(r.get("display_id"))
        st = _txt(r.get("status"))
        sb = _txt(r.get("subject"))
        tg = ", ".join(get_tags(r))
        print(f"  SDP-{did:>6} [{st:>14}] {sb[:80]}")
        if tg:
            print(f"           tags: {tg}")


if __name__ == "__main__":
    main()
