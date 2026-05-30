#!/usr/bin/env python3
"""
sdp_fetch_ticket.py — Fetch SDP ticket details by display ID or long API ID.

Lightweight retrieval script for use by skills (clerk, rounds, sdp-investigator).
Returns ticket subject, description, requester, status, and the long SDP ID.

Usage:
    python3 scripts/sdp_fetch_ticket.py --id 27750
    python3 scripts/sdp_fetch_ticket.py --id 27750 --json
    python3 scripts/sdp_fetch_ticket.py --long-id 110247000030379312
    python3 scripts/sdp_fetch_ticket.py --search "Fabric Pipeline Error"

Environment (reads from .env if not already set):
    WWEEKS_SDP — JSON: {"client_id":"...","client_secret":"...","refresh_token":"..."}
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, SDP_COMMON_CAUSES

REPO_ROOT = Path(__file__).parent.parent
SDP_BASE = "https://<YOUR_SDP>.sdpondemand.manageengine.com/app/698819937"
ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"


def load_env_file():
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def get_sdp_token() -> str:
    require_env("WWEEKS_SDP",
                hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    creds_raw = os.environ["WWEEKS_SDP"]
    # Accept raw JSON or base64-encoded JSON (matches sdp_lib._load_sdp_creds)
    try:
        creds = json.loads(creds_raw)
    except json.JSONDecodeError:
        try:
            import base64
            creds = json.loads(base64.b64decode(creds_raw, validate=True).decode("utf-8"))
        except Exception:
            fail(
                "WWEEKS_SDP is neither valid JSON nor base64-encoded JSON",
                causes=["Env var was truncated or corrupted during export",
                        "Missing quotes around JSON value in .env"],
                try_=["grep WWEEKS_SDP .env",
                      "python3 -c \"import os,json; json.loads(os.environ['WWEEKS_SDP'])\""],
            )

    body = urllib.parse.urlencode({
        "refresh_token": creds["refresh_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        ZOHO_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    token = data.get("access_token")
    if not token:
        fail(
            "Zoho OAuth token exchange returned no access_token",
            causes=["refresh_token is expired (Zoho tokens expire after ~1 year)",
                    "client_id or client_secret is wrong"],
            try_=["Regenerate OAuth credentials in Zoho API Console",
                  "grep WWEEKS_SDP .env  # confirm credentials are current"],
        )
    return token


def _txt(field) -> str:
    if isinstance(field, dict):
        return field.get("name") or field.get("value") or ""
    return str(field) if field else ""


def fetch_by_display_id(ticket_id: str, token: str) -> dict:
    """Fetch a request by display ID (the short human-facing number)."""
    params = urllib.parse.urlencode({
        "input_data": json.dumps({
            "list_info": {
                "row_count": 1,
                "search_fields": {"display_id": ticket_id},
                "fields_required": [
                    "id", "display_id", "subject", "description", "status",
                    "requester", "created_time", "resolved_time", "priority",
                    "group", "technician"
                ],
            }
        })
    })
    url = f"{SDP_BASE}/api/v3/requests?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="SDP", key=ticket_id, operation="GET /api/v3/requests",
                  common_causes=SDP_COMMON_CAUSES)

    requests = data.get("requests", [])
    if not requests:
        fail(
            f"No SDP ticket found with display ID {ticket_id}",
            causes=["Request was deleted or the ID is wrong",
                    "Wrong portal: SDP_PORTAL_NAME mismatched to SDP_AUTH_TOKEN"],
            try_=[f"Verify: https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/{ticket_id}",
                  "grep SDP_ .env"],
        )
    return requests[0]


def fetch_by_long_id(long_id: str, token: str) -> dict:
    """Fetch a request by the internal long API ID."""
    url = f"{SDP_BASE}/api/v3/requests/{long_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="SDP", key=long_id, operation="GET /api/v3/requests/{id}",
                  common_causes=SDP_COMMON_CAUSES)

    return data.get("request", {})


def search_tickets(query: str, token: str) -> list[dict]:
    """Search SDP tickets by subject keyword."""
    words = [w for w in re.split(r"\W+", query) if len(w) > 2][:5]
    if not words:
        return []

    params = urllib.parse.urlencode({
        "input_data": json.dumps({
            "list_info": {
                "row_count": 5,
                "search_fields": {"subject": " ".join(words)},
                "fields_required": [
                    "id", "display_id", "subject", "status",
                    "requester", "created_time"
                ],
            }
        })
    })
    url = f"{SDP_BASE}/api/v3/requests?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="SDP", operation="GET /api/v3/requests (search)",
                  common_causes=SDP_COMMON_CAUSES)

    return data.get("requests", [])


def format_ticket(ticket: dict) -> dict:
    """Extract a clean dict from an SDP ticket response."""
    return {
        "id": _txt(ticket.get("id", "")),
        "display_id": _txt(ticket.get("display_id", "")),
        "subject": _txt(ticket.get("subject", "")),
        "description": _txt(ticket.get("description", "")),
        "status": _txt(ticket.get("status", "")),
        "requester": _txt(ticket.get("requester", {}).get("name", "")),
        "created": _txt(ticket.get("created_time", {}).get("display_value", "")),
        "priority": _txt(ticket.get("priority", "")),
        "group": _txt(ticket.get("group", {}).get("name", "")),
        "technician": _txt(ticket.get("technician", {}).get("name", "")),
    }


def print_human(ticket: dict):
    """Print ticket in human-readable format."""
    t = format_ticket(ticket)
    print(f"\n📋  SDP #{t['display_id']} — {t['subject']}")
    print(f"    Long ID   : {t['id']}")
    print(f"    Requester : {t['requester']}")
    print(f"    Status    : {t['status']}  |  Priority: {t['priority']}")
    print(f"    Group     : {t['group']}  |  Tech: {t['technician']}")
    print(f"    Opened    : {t['created']}")
    if t["description"]:
        desc = t["description"].strip()
        preview = desc[:500] + "…" if len(desc) > 500 else desc
        print(f"\n    Description:\n    {preview}\n")


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Fetch SDP ticket details")
    parser.add_argument("--id", help="SDP display ticket ID (e.g. 27750)")
    parser.add_argument("--long-id", help="SDP internal long API ID")
    parser.add_argument("--search", help="Search tickets by subject keyword")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not any([args.id, args.long_id, args.search]):
        parser.error("Provide --id, --long-id, or --search")

    token = get_sdp_token()

    if args.search:
        results = search_tickets(args.search, token)
        if not results:
            fail(
                f"No SDP tickets found matching '{args.search}'",
                causes=["No requests with matching subject keywords",
                        "Search terms too specific — try fewer words"],
                try_=[f"python3 scripts/sdp_search.py --keyword \"{args.search}\"",
                      "python3 scripts/sdp_search.py --status Open"],
            )
        if args.json:
            print(json.dumps([format_ticket(r) for r in results], indent=2))
        else:
            print(f"\n🔍  Found {len(results)} ticket(s):")
            for r in results:
                t = format_ticket(r)
                print(f"    #{t['display_id']} [{t['status']}] — {t['subject']}")
        sys.exit(0)

    if args.long_id:
        ticket = fetch_by_long_id(args.long_id, token)
    else:
        ticket = fetch_by_display_id(args.id, token)

    if args.json:
        print(json.dumps(format_ticket(ticket), indent=2))
    else:
        print_human(ticket)


if __name__ == "__main__":
    main()
