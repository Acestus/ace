#!/usr/bin/env python3
"""
sdp_set_tags.py — Add or remove tags on an SDP request.

Mirror of jira_set_labels.py.

Usage:
    python3 scripts/sdp_set_tags.py --id 33903 --add way:flow --add lane:approval
    python3 scripts/sdp_set_tags.py --id 33903 --remove urgency:3 --add urgency:2
    python3 scripts/sdp_set_tags.py --id 33903 --replace urgency:2,importance:2,agentic:4
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    load_env_file, get_sdp_token, resolve_long_id, fetch_request,
    get_tags, put_tags, _txt,
)


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Manage SDP tags")
    p.add_argument("--id", required=True)
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    p.add_argument("--replace", help="Comma-separated tags to set as the full tag list")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not (args.add or args.remove or args.replace):
        p.error("Provide --add, --remove, or --replace")

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)
    request = fetch_request(long_id, token)
    current = set(get_tags(request))

    if args.replace is not None:
        new_tags = set(t.strip() for t in args.replace.split(",") if t.strip())
    else:
        new_tags = (current | set(args.add)) - set(args.remove)

    if args.dry_run:
        print(json.dumps({
            "id": long_id,
            "current_tags": sorted(current),
            "new_tags": sorted(new_tags),
            "dry_run": True,
        }, indent=2))
        return

    put_tags(long_id, sorted(new_tags), token)
    if args.json:
        print(json.dumps({"id": long_id, "tags": sorted(new_tags)}, indent=2))
    else:
        print(f"✓ Tags on SDP-{_txt(request.get('display_id'))}: {sorted(new_tags)}")


if __name__ == "__main__":
    main()
