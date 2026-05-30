#!/usr/bin/env python3
"""
sdp_set_links.py — Reconcile SDP linked requests + web links from markdown.

Reads cases/{display_id}/*.md sections:
    ## Linked Requests   — '- SDP-33920 — note text'
    ## Web Links         — '- [label](url)' or '- url'

Linked requests are SDP-native link_requests. Web links are stored as [LINK]
prefixed notes (SDP has no native web link panel).

Usage:
    python3 scripts/sdp_set_links.py --id 33903
    python3 scripts/sdp_set_links.py --id 33903 --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    REPO_ROOT, load_env_file, get_sdp_token, resolve_long_id, fetch_request,
    fetch_linked_requests, fetch_web_links, link_request, add_web_link,
    extract_section, parse_links_section, parse_linked_requests_section,
    resolve_sdp_id_from_folder, _txt,
)


def reconcile(long_id: str, display_id: str, token: str, dry_run: bool = False) -> dict:
    case_dir = REPO_ROOT / "cases" / display_id
    if not case_dir.exists():
        return {"error": f"cases/{display_id}/ not found"}
    md_files = list(case_dir.glob("*.md"))
    if not md_files:
        return {"error": f"no markdown in cases/{display_id}/"}
    text = md_files[0].read_text()

    # Linked requests
    linked_body = extract_section(text, "Linked Requests") or ""
    desired_linked = parse_linked_requests_section(linked_body)
    existing_linked = fetch_linked_requests(long_id, token)
    existing_display_ids = {
        _txt((lr.get("linked_request") or {}).get("display_id"))
        for lr in existing_linked
    }

    link_actions = {"create": [], "noop": []}
    for d in desired_linked:
        if d["display_id"] in existing_display_ids:
            link_actions["noop"].append(d["display_id"])
            continue
        # resolve to long ID
        other_long = resolve_sdp_id_from_folder(d["display_id"])
        if not other_long:
            other_long = d["display_id"]  # will be resolved by API
        link_actions["create"].append({
            "display_id": d["display_id"],
            "long_id": other_long,
            "note": d["note"],
        })

    # Web links — now handled by reconcile_description (HTML in description field).
    # Legacy note-based web links are preserved but no new ones created.
    links_body = extract_section(text, "Web Links") or ""
    desired_web = parse_links_section(links_body)
    web_actions = {"info": "web links now rendered in HTML description",
                   "count": len(desired_web)}

    if dry_run:
        return {
            "dry_run": True,
            "linked_requests": link_actions,
            "web_links": web_actions,
        }

    for la in link_actions["create"]:
        try:
            link_request(long_id, la["long_id"], token, comments=la["note"])
        except Exception as e:
            print(f"  WARN link {la['display_id']} failed: {e}", file=sys.stderr)

    return {"linked_requests": link_actions, "web_links": web_actions}


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Reconcile SDP links from markdown")
    p.add_argument("--id", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)
    request = fetch_request(long_id, token)
    display_id = _txt(request.get("display_id"))
    result = reconcile(long_id, display_id, token, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    if "error" in result:
        fail(
            result["error"],
            causes=["Case directory or markdown file missing for this SDP ID"],
            try_=[f"python3 scripts/sdp_create_stub.py --id {args.id}",
                  f"ls cases/{display_id}/"],
        )


if __name__ == "__main__":
    main()
