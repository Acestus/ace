#!/usr/bin/env python3
"""
sdp_investigate.py — Load an SDP ticket, create the case file skeleton, and surface context.

Fetches ticket details from ServiceDesk Plus, checks for an existing case file,
creates one if absent, and searches Jira for related tickets by keyword.

Usage:
    python3 scripts/sdp_investigate.py --id 27750
    python3 scripts/sdp_investigate.py --id 27750 --no-jira
    python3 scripts/sdp_investigate.py --id 27750 --create-case

Environment (reads from .env if not already set):
    WWEEKS_SDP              — JSON: {"client_id":"...","client_secret":"...","refresh_token":"..."}
    CONFLUENCE_EMAIL        — for Jira auth
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, SDP_COMMON_CAUSES, JIRA_COMMON_CAUSES

REPO_ROOT       = Path(__file__).parent.parent
CASES_DIR       = REPO_ROOT / "cases"
SDP_BASE        = "https://<YOUR_SDP>.sdpondemand.manageengine.com/app/698819937"
ZOHO_TOKEN_URL  = "https://accounts.zoho.com/oauth/v2/token"
JIRA_BASE       = "https://<YOUR_ATLASSIAN>.atlassian.net"


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SDP auth
# ---------------------------------------------------------------------------

def get_sdp_token() -> str:
    require_env("WWEEKS_SDP",
                hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    creds_raw = os.environ["WWEEKS_SDP"]
    try:
        creds = json.loads(creds_raw)
    except json.JSONDecodeError:
        fail(
            "WWEEKS_SDP is not valid JSON",
            causes=["Env var was truncated or corrupted during export",
                    "Missing quotes around JSON value in .env"],
            try_=["grep WWEEKS_SDP .env",
                  "python3 -c \"import os,json; json.loads(os.environ['WWEEKS_SDP'])\""],
        )

    body = urllib.parse.urlencode({
        "refresh_token": creds["refresh_token"],
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "grant_type":    "refresh_token",
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


def sdp_get(path: str, token: str) -> dict:
    url = f"{SDP_BASE}/api/v3/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="SDP", operation=f"GET {path}",
                  common_causes=SDP_COMMON_CAUSES)


# ---------------------------------------------------------------------------
# SDP ticket fetch
# ---------------------------------------------------------------------------

def fetch_ticket(ticket_id: str, token: str) -> dict:
    """Fetch a request by display ID (the short human-facing number)."""
    # Search by display_id
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


def _txt(field) -> str:
    """Extract string from SDP value-object or plain string."""
    if isinstance(field, dict):
        return field.get("name") or field.get("value") or ""
    return str(field) if field else ""


# ---------------------------------------------------------------------------
# Jira search
# ---------------------------------------------------------------------------

def jira_auth_header() -> str:
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("WWEEKS_CONFLUENCE_API_TOKEN", "")
    if not email or not token:
        return ""
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def search_jira(keywords: str) -> list[dict]:
    auth = jira_auth_header()
    if not auth:
        return []
    # Pull key words from subject (first 4 meaningful words)
    words = [w for w in re.split(r"\W+", keywords) if len(w) > 3][:4]
    if not words:
        return []
    phrase = " ".join(words)
    jql = f'project = INFRA AND text ~ "{phrase}" ORDER BY updated DESC'
    body = json.dumps({"jql": jql, "fields": ["key", "summary", "status", "labels"], "maxResults": 5}).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/search/jql",
        data=body,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        return data.get("issues", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Case file
# ---------------------------------------------------------------------------

def find_case_file(ticket_id: str) -> Path | None:
    case_dir = CASES_DIR / ticket_id
    if not case_dir.exists():
        return None
    for f in case_dir.iterdir():
        if f.suffix == ".md":
            return f
    return None


def build_summary(subject: str, description: str) -> str:
    """Build a 1-2 sentence summary of what the ticket is about."""
    # Start with the subject as the base
    summary = subject.strip()
    if description:
        # Grab the first meaningful sentence from description
        desc_clean = re.sub(r"<[^>]+>", "", description).strip()
        sentences = re.split(r"[.\n]", desc_clean)
        first_sentence = ""
        for s in sentences:
            s = s.strip()
            if len(s) > 15 and s.lower() != subject.lower():
                first_sentence = s
                break
        if first_sentence:
            summary = f"{subject.strip()}. {first_sentence.strip()}"
    # Cap at ~200 chars
    if len(summary) > 200:
        summary = summary[:197] + "…"
    return summary


def create_case_file(ticket_id: str, ticket: dict) -> Path:
    case_dir = CASES_DIR / ticket_id
    case_dir.mkdir(parents=True, exist_ok=True)

    subject    = _txt(ticket.get("subject", ""))
    requester  = _txt(ticket.get("requester", {}).get("name", ""))
    description = _txt(ticket.get("description", ""))
    status     = _txt(ticket.get("status", ""))
    created    = _txt(ticket.get("created_time", {}).get("display_value", ""))
    sdp_long   = ticket.get("id", "")
    summary    = build_summary(subject, description)
    today      = datetime.now().strftime("%Y-%m-%d %H:%M")

    case_path = case_dir / f"{ticket_id} - {subject}.md"

    content = f"""# {ticket_id} - {subject}

SDP_ID: {sdp_long}
Summary: {summary}

## Description

------------------------------------------------

Requested By: {requester} on {created}

{description}

## Actions

------------------------------------------------

### {today}

Initial investigation — opened case file.

## Follow-up

------------------------------------------------
Status: {status}
TODO:
- [ ] Investigate and respond
"""
    case_path.write_text(content)
    return case_path


# ---------------------------------------------------------------------------
# Linking SDP ↔ Jira
# ---------------------------------------------------------------------------

def link_sdp_jira(ticket_id: str, jira_key: str, subject: str):
    """Write SDP reference into Jira issue description and Jira key into case file."""
    auth = jira_auth_header()
    if not auth:
        print("    ⚠  Jira auth not available — skipping Jira side", file=sys.stderr)
    else:
        # Add SDP reference to Jira issue description
        sdp_ref = f"SDP #{ticket_id}"
        body = json.dumps({
            "update": {
                "description": [{
                    "set": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": f"Linked to {sdp_ref}"}]
                        }]
                    }
                }]
            }
        }).encode()
        # Simpler: just add a comment linking the SDP ticket
        comment_body = json.dumps({
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": f"Linked to SDP #{ticket_id} — {subject}"}]
                }]
            }
        }).encode()
        req = urllib.request.Request(
            f"{JIRA_BASE}/rest/api/3/issue/{jira_key}/comment",
            data=comment_body,
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "Accept": "application/vnd.manageengine.sdp.v3+json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                print(f"    ✓  Added SDP #{ticket_id} link as comment on {jira_key}")
        except urllib.error.HTTPError as e:
            print(f"    ⚠  Failed to comment on {jira_key}: HTTP {e.code}", file=sys.stderr)

    # Write Jira key into the case file
    case_file = find_case_file(ticket_id)
    if case_file:
        content = case_file.read_text()
        jira_link = f"Jira: [{jira_key}]({JIRA_BASE}/browse/{jira_key})"
        if jira_key not in content:
            # Insert after SDP_ID line
            content = content.replace(
                "## Description",
                f"{jira_link}\n\n## Description",
                1,
            )
            case_file.write_text(content)
            print(f"    ✓  Added {jira_key} reference to case file")
        else:
            print(f"    (case file already references {jira_key})")
    else:
        print(f"    ⚠  No case file to update — create one first")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_ticket(ticket: dict, ticket_id: str):
    subject   = _txt(ticket.get("subject", ""))
    requester = _txt(ticket.get("requester", {}).get("name", ""))
    status    = _txt(ticket.get("status", ""))
    group     = _txt(ticket.get("group", {}).get("name", ""))
    tech      = _txt(ticket.get("technician", {}).get("name", "Unknown"))
    created   = _txt(ticket.get("created_time", {}).get("display_value", ""))
    desc      = _txt(ticket.get("description", "")).strip()

    print(f"\n📋  SDP #{ticket_id} — {subject}")
    print(f"    Requester : {requester}")
    print(f"    Status    : {status}  |  Group: {group}  |  Tech: {tech}")
    print(f"    Opened    : {created}")
    if desc:
        # Trim long descriptions for display
        preview = desc[:400] + "…" if len(desc) > 400 else desc
        print(f"\n    {preview}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Investigate an SDP ticket")
    parser.add_argument("--id",          required=True, help="SDP display ticket ID (e.g. 27750)")
    parser.add_argument("--create-case", action="store_true", help="Create case file if missing")
    parser.add_argument("--no-jira",     action="store_true", help="Skip Jira search")
    parser.add_argument("--link",        metavar="JIRA_KEY", help="Link this SDP case to a Jira ticket (e.g. <PROJECT>-358)")
    args = parser.parse_args()

    ticket_id = args.id.strip()

    # 1 — Check for existing case file first (no auth needed)
    existing = find_case_file(ticket_id)
    if existing:
        print(f"\n📁  Existing case file: {existing.relative_to(REPO_ROOT)}")
        # Show first 20 lines
        lines = existing.read_text().splitlines()[:20]
        print("    " + "\n    ".join(lines))
    else:
        print(f"\n⚠   No case file found in cases/{ticket_id}/")

    # 2 — Fetch from SDP
    print(f"\n🔍  Fetching SDP #{ticket_id}…")
    token = get_sdp_token()
    ticket = fetch_ticket(ticket_id, token)
    display_ticket(ticket, ticket_id)

    # 3 — Create case file if requested or missing
    if args.create_case or not existing:
        if not existing:
            case_path = create_case_file(ticket_id, ticket)
            print(f"✓   Case file created: {case_path.relative_to(REPO_ROOT)}")
        else:
            print("    (case file already exists — not overwriting)")
    else:
        print("    (--create-case not set — skipping file creation)")

    # 4 — Jira search
    if not args.no_jira:
        subject = _txt(ticket.get("subject", ""))
        print(f"\n🔗  Searching Jira for related tickets…")
        related = search_jira(subject)
        if related:
            print(f"    Found {len(related)} related issue(s):")
            for issue in related:
                key     = issue["key"]
                summary = issue["fields"]["summary"]
                status  = issue["fields"]["status"]["name"]
                print(f"      {key} [{status}] — {summary}")
        else:
            print("    No related Jira tickets found.")

    # 5 — Link SDP ↔ Jira (bidirectional)
    if args.link:
        jira_key = args.link.strip()
        print(f"\n🔗  Linking SDP #{ticket_id} ↔ {jira_key}…")
        link_sdp_jira(ticket_id, jira_key, _txt(ticket.get("subject", "")))

    print()


if __name__ == "__main__":
    main()
