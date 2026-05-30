#!/usr/bin/env python3
"""
sdp_lib.py — Shared helpers for ServiceDesk Plus automation scripts.

Used by:
    sdp_context_bundle.py    — composite read for skills (rounds, investigator)
    sdp_search.py            — JQL-equivalent list/search
    sdp_set_flow.py          — flow:* tag + native status transition
    sdp_set_tags.py          — add/remove SDP tags
    sdp_update_fields.py     — description, priority, urgency, group, etc.
    sdp_set_tasks.py         — markdown checkbox → SDP task reconciliation
    sdp_set_links.py         — linked_requests + URL notes
    sdp_approval.py          — approval levels + approver management
    sdp_changelog.py         — request history
    sdp_sync_waiting.py      — reconcile flow:waiting cases
    sdp_create_request.py    — CLI create
    sync_sdp_fields.py       — markdown-driven state reconciliation
    sync_sdp_worklog.py      — WORKLOG/COMMENT diff sync (legacy entrypoint)

Provides OAuth, REST wrappers, payload builders, classifiers, and markdown
parse/upsert primitives — the SDP equivalent of jira_lib.py.

Environment (reads from .env if not already set):
    WWEEKS_SDP_TECH_KEY — SDP technician API key (preferred; no OAuth needed)
    WWEEKS_SDP         — JSON: {"client_id":"...","client_secret":"...","refresh_token":"..."}
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SDP_BASE = "https://<YOUR_SDP>.sdpondemand.manageengine.com/app/698819937"
SDP_PORTAL_URL = "https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests"
ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"

# Flow tags — mirror of Jira flow:* labels
FLOW_TAGS = {"flow:queue", "flow:active", "flow:waiting", "flow:done"}

# SDP native status names — verified against the <ORG_NAME> SDP instance 2026-05-26.
# Full list available on instance: Open, On Hold, Resolved, Closed, Canceled,
# Waiting for Review, Waiting on End User, Waiting on Vendor, Waiting on budget,
# Waiting parts, Leave of Absence, Legal Hold.
#
# Note: <ORG_NAME> SDP does NOT have an "In Progress" status — flow:active stays
# on "Open" status (the flow tag is what tracks active-vs-queued locally).
FLOW_STATUS_MAP = {
    "queue":   "Open",
    "active":  "Open",              # no native "In Progress" — flow:active tag is the signal
    "waiting": "Waiting for Review", # default; override with --status for specific subtype
    "done":    "Resolved",          # use Closed only after the requester accepts
}

# Valid SDP statuses on the <ORG_NAME> instance — used for --status validation.
VALID_SDP_STATUSES = {
    "Open", "On Hold", "Resolved", "Closed", "Canceled",
    "Waiting for Review", "Waiting on End User", "Waiting on Vendor",
    "Waiting on budget", "Waiting parts", "Leave of Absence", "Legal Hold",
}

# Statuses that map to flow:waiting (for reverse-mapping in sync_sdp_fields).
WAITING_STATUSES = {
    "On Hold", "Waiting for Review", "Waiting on End User",
    "Waiting on Vendor", "Waiting on budget", "Waiting parts",
    "Leave of Absence", "Legal Hold",
}

# Scoring tag prefixes — markdown-driven, optionally mirrored to SDP tags
SCORING_PREFIXES = ("urgency:", "importance:", "agentic:", "constraint:", "way:", "lane:")

REPO_ROOT = Path(__file__).parent.parent


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


sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES  # noqa: E402


def _load_sdp_creds() -> dict:
    raw = os.environ.get("WWEEKS_SDP", "")
    if not raw:
        fail(
            "SDP credentials env var WWEEKS_SDP is not set",
            causes=[
                ".env not loaded into the current shell",
                "Running outside the projects/ repo (e.g. cron, CI without secret)",
                "WWEEKS_SDP secret missing from GitHub repo secrets (CI)",
            ],
            try_=[
                "cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)",
                "grep WWEEKS_SDP .env  # confirm the value exists",
                "Or set WWEEKS_SDP_TECH_KEY instead for technician-key auth",
            ],
        )
    # WWEEKS_SDP may be raw JSON, or base64-encoded JSON (the form stored in
    # the GitHub repo secret). Try raw JSON first, fall back to base64 decode.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        import base64
        decoded = base64.b64decode(raw, validate=True).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        fail(
            "WWEEKS_SDP is neither valid JSON nor base64-encoded JSON",
            causes=[
                "Value was truncated when copied into .env (quotes mismatched)",
                "Stored in wrong format — must be raw JSON or base64-encoded JSON",
            ],
            try_=[
                "echo $WWEEKS_SDP | head -c 100  # inspect first 100 chars",
                "echo $WWEEKS_SDP | base64 -d | python3 -m json.tool  # validate base64+json",
            ],
        )


_token_cache = {"token": None, "expires_at": 0}


def get_sdp_token() -> str:
    """Return an auth token for SDP API calls.

    If WWEEKS_SDP_TECH_KEY is set, returns the sentinel "TECH_KEY" —
    _request() will use the authtoken header with the key value instead
    of the Zoho OAuth header.  No network call needed.

    Otherwise falls back to the Zoho OAuth refresh-token flow.
    """
    if os.environ.get("WWEEKS_SDP_TECH_KEY"):
        return "TECH_KEY"

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    creds = _load_sdp_creds()
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
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        fail(
            f"Zoho OAuth token exchange failed ({e.code} {e.reason})",
            causes=[
                "Refresh token was revoked or expired (Zoho refresh tokens last ~1 year)",
                "client_id or client_secret mismatch in WWEEKS_SDP",
                "Zoho account region mismatch (US vs EU endpoint)",
            ],
            try_=[
                "Re-issue refresh token: https://api-console.zoho.com/",
                "Verify WWEEKS_SDP fields: refresh_token, client_id, client_secret",
                f"Raw response: {body_text[:200]}",
            ],
        )

    token = data.get("access_token")
    if not token:
        fail(
            "Zoho OAuth response had no access_token",
            causes=["Zoho API contract changed", "Response was an error wrapped in 200"],
            try_=[
                f"Raw response: {json.dumps(data)[:300]}",
                "Check Zoho status: https://status.zoho.com/",
            ],
        )
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + 3300  # 55 min safety margin
    return token


# ---------------------------------------------------------------------------
# REST primitives
# ---------------------------------------------------------------------------

def _request(method: str, path: str, token: str,
             params: dict | None = None, input_data: dict | None = None,
             timeout: int = 30) -> dict:
    """Low-level SDP REST call. Returns parsed JSON dict (or {} on empty body).

    token: either a Zoho OAuth access token, OR the sentinel value "TECH_KEY"
           (in which case the Authorization header uses the technician API key).
    """
    url = f"{SDP_BASE}{path}"

    tech_key = os.environ.get("WWEEKS_SDP_TECH_KEY", "")
    if token == "TECH_KEY" or (not token and tech_key):
        headers = {
            "authtoken": tech_key,
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        }
    else:
        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        }

    data = None
    if input_data is not None:
        # SDP wants form-encoded `input_data=<json>` body, not raw JSON
        body = urllib.parse.urlencode({"input_data": json.dumps(input_data)})
        if method in ("GET", "DELETE"):
            # input_data goes in querystring for GETs
            qs = body
            url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"
        else:
            data = body.encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif params:
        qs = urllib.parse.urlencode(params)
        url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode(errors="replace")
            return json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as e:
        # Print an actionable block to stderr but re-raise so callers can choose
        # to handle (e.g. retry on 429). Callers that want fail-fast can call
        # lib.errors.http_fail() directly instead of catching.
        body_text = e.read().decode(errors="replace")
        info = SDP_COMMON_CAUSES.get(e.code, {})
        print(f"❌ SDP API rejected {method} {path} ({e.code} {e.reason})", file=sys.stderr)
        if info.get("causes"):
            print("   Likely causes:", file=sys.stderr)
            for c in info["causes"]:
                print(f"     • {c}", file=sys.stderr)
        if info.get("try"):
            print("   Try:", file=sys.stderr)
            for t in info["try"]:
                print(f"     • {t}", file=sys.stderr)
        if body_text:
            print(f"   Raw body: {body_text[:300]}", file=sys.stderr)
        # Re-attach the body so callers reading e.read() in their except block
        # don't get an empty read (urllib HTTPError body is one-shot).
        e._read_body_already = body_text  # noqa: SLF001
        raise


def sdp_get(path: str, token: str, input_data: dict | None = None,
            params: dict | None = None) -> dict:
    return _request("GET", path, token, params=params, input_data=input_data)


def sdp_post(path: str, token: str, input_data: dict) -> dict:
    return _request("POST", path, token, input_data=input_data)


def sdp_put(path: str, token: str, input_data: dict) -> dict:
    return _request("PUT", path, token, input_data=input_data)


def sdp_delete(path: str, token: str, input_data: dict | None = None) -> dict:
    return _request("DELETE", path, token, input_data=input_data)


# ---------------------------------------------------------------------------
# Field accessors (SDP returns mixed scalar/object shapes)
# ---------------------------------------------------------------------------

def _txt(field) -> str:
    if field is None:
        return ""
    if isinstance(field, dict):
        return field.get("name") or field.get("value") or field.get("display_value") or ""
    return str(field)


def request_url(sdp_id: str) -> str:
    return f"{SDP_PORTAL_URL}/{sdp_id}/details"


# ---------------------------------------------------------------------------
# Request resolution — display ID (short) ↔ long API ID
# ---------------------------------------------------------------------------

def resolve_long_id(display_or_long_id: str, token: str) -> str:
    """Given a display ID (e.g. '33903') or long ID, return the long API ID."""
    s = str(display_or_long_id).strip().lstrip("#")
    # Long IDs are typically 18+ digits; display IDs are 4-6
    if len(s) >= 15 and s.isdigit():
        return s

    params = {
        "input_data": json.dumps({
            "list_info": {
                "row_count": 1,
                "search_fields": {"display_id": s},
                "fields_required": ["id", "display_id"],
            }
        })
    }
    data = sdp_get("/api/v3/requests", token, params=params)
    requests = data.get("requests", [])
    if not requests:
        print(f"ERROR: No SDP request found with display_id={s}", file=sys.stderr)
        sys.exit(1)
    return _txt(requests[0].get("id"))


def resolve_sdp_id_from_folder(folder_id: str) -> str | None:
    """Read SDP_ID: header from the case markdown file."""
    case_dir = REPO_ROOT / "cases" / folder_id
    if not case_dir.exists():
        return None
    for md_file in case_dir.glob("*.md"):
        text = md_file.read_text()
        m = re.search(r"(?m)^SDP_ID:\s*(\S+)", text)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Fetches
# ---------------------------------------------------------------------------

REQUEST_FIELDS = [
    "id", "display_id", "subject", "description", "status", "tags",
    "requester", "created_time", "resolved_time", "due_by_time",
    "priority", "urgency", "impact", "category", "subcategory", "item",
    "group", "technician", "site", "is_overdue", "approval_status",
    "linked_to_request", "udf_fields",
]


def fetch_request(sdp_id: str, token: str) -> dict:
    data = sdp_get(f"/api/v3/requests/{sdp_id}", token)
    return data.get("request", {})


def fetch_request_by_display(display_id: str, token: str) -> dict:
    params = {
        "input_data": json.dumps({
            "list_info": {
                "row_count": 1,
                "search_fields": {"display_id": display_id},
                "fields_required": REQUEST_FIELDS,
            }
        })
    }
    data = sdp_get("/api/v3/requests", token, params=params)
    requests = data.get("requests", [])
    return requests[0] if requests else {}


def fetch_notes(sdp_id: str, token: str, row_count: int = 50) -> list[dict]:
    params = {"input_data": json.dumps({"list_info": {"row_count": row_count, "sort_field": "created_time", "sort_order": "desc"}})}
    data = sdp_get(f"/api/v3/requests/{sdp_id}/notes", token, params=params)
    return data.get("notes", [])


def fetch_worklogs(sdp_id: str, token: str, row_count: int = 50) -> list[dict]:
    params = {"input_data": json.dumps({"list_info": {"row_count": row_count}})}
    data = sdp_get(f"/api/v3/requests/{sdp_id}/worklogs", token, params=params)
    return data.get("worklogs", [])


def fetch_tasks(sdp_id: str, token: str) -> list[dict]:
    data = sdp_get(f"/api/v3/requests/{sdp_id}/tasks", token,
                   params={"input_data": json.dumps({"list_info": {"row_count": 100}})})
    return data.get("tasks", [])


def fetch_approval_levels(sdp_id: str, token: str) -> list[dict]:
    data = sdp_get(f"/api/v3/requests/{sdp_id}/approval_levels", token,
                   params={"input_data": json.dumps({"list_info": {"row_count": 50}})})
    return data.get("approval_levels", [])


def fetch_approvals(sdp_id: str, level_id: str, token: str) -> list[dict]:
    data = sdp_get(f"/api/v3/requests/{sdp_id}/approval_levels/{level_id}/approvals", token,
                   params={"input_data": json.dumps({"list_info": {"row_count": 50}})})
    return data.get("approvals", [])


def fetch_linked_requests(sdp_id: str, token: str) -> list[dict]:
    try:
        data = sdp_get(f"/api/v3/requests/{sdp_id}/link_requests", token)
    except urllib.error.HTTPError:
        return []
    return data.get("link_requests", [])


def fetch_history(sdp_id: str, token: str, row_count: int = 100) -> list[dict]:
    try:
        data = sdp_get(f"/api/v3/requests/{sdp_id}/history", token,
                       params={"input_data": json.dumps({"list_info": {"row_count": row_count}})})
    except urllib.error.HTTPError:
        return []
    return data.get("history", [])


def search_requests(filters: dict, token: str, row_count: int = 20,
                    fields: list[str] | None = None) -> list[dict]:
    """filters: {search_fields: {...}} or {filter_by: {name: 'My_Open'}}.
    Returns list of request dicts."""
    list_info = {
        "row_count": row_count,
        "fields_required": fields or [
            "id", "display_id", "subject", "status", "tags",
            "requester", "created_time", "priority", "urgency",
            "group", "technician",
        ],
    }
    list_info.update(filters)
    params = {"input_data": json.dumps({"list_info": list_info})}
    data = sdp_get("/api/v3/requests", token, params=params)
    return data.get("requests", [])


# ---------------------------------------------------------------------------
# Tags — SDP tags are stored as a list of objects on the request
# ---------------------------------------------------------------------------

def get_tags(request: dict) -> list[str]:
    raw = request.get("tags") or []
    out: list[str] = []
    for t in raw:
        if isinstance(t, dict):
            name = t.get("name")
            if name:
                out.append(name)
        elif isinstance(t, str):
            out.append(t)
    return out


def put_tags(sdp_id: str, tags: list[str], token: str) -> dict:
    """Set tags on a request. SDP On-Demand does not support tag writes via
    OAuth API (requires admin scope or UI). Flow state is tracked in markdown;
    SDP status transitions are the visible equivalent."""
    # Skip the API call entirely — it always fails for non-admin OAuth.
    # Tags must be managed via SDP UI or admin API key.
    return {"tags_skipped": sorted(tags), "reason": "API tag write not supported"}


def add_tags(sdp_id: str, to_add: list[str], token: str) -> dict:
    req = fetch_request(sdp_id, token)
    current = set(get_tags(req))
    current.update(to_add)
    return put_tags(sdp_id, sorted(current), token)


def remove_tags(sdp_id: str, to_remove: list[str], token: str) -> dict:
    req = fetch_request(sdp_id, token)
    current = set(get_tags(req)) - set(to_remove)
    return put_tags(sdp_id, sorted(current), token)


# ---------------------------------------------------------------------------
# Status transitions — equivalent to Jira's transitions API
# ---------------------------------------------------------------------------

def transition_status(sdp_id: str, status_name: str, token: str,
                      resolution: Optional[str] = None,
                      closure_code: str = "Success",
                      closure_comments: Optional[str] = None) -> dict:
    """
    Transition an SDP request status.

    SDP On-Demand quirks:
    - Resolved REQUIRES `resolution.content` (status reverts silently if missing)
    - Closed REQUIRES `closure_info.closure_code` and `closure_info.closure_comments`
      (PUT returns 200 but status doesn't persist if missing)
    """
    body: dict = {"status": {"name": status_name}}

    if status_name == "Resolved":
        body["resolution"] = {
            "content": resolution or "Resolved via API (<GITHUB_ORG>/projects automation)."
        }

    if status_name == "Closed":
        # Closed implies the work was resolved; SDP requires both blocks on the
        # transition if the request wasn't already Resolved.
        full_resolution = resolution or "Closed via API (<GITHUB_ORG>/projects automation)."
        body["resolution"] = {"content": full_resolution}

        # Both requester_ack_comments and closure_comments have small max-length
        # limits in SDP On-Demand (the closure_comments cap is ~250 chars).
        # Keep both terse and let resolution.content carry the full narrative.
        short_closure = (closure_comments or full_resolution)
        if len(short_closure) > 250:
            short_closure = short_closure[:247] + "..."
        body["closure_info"] = {
            "requester_ack_resolution": True,
            "requester_ack_comments": "Closed via API.",
            "closure_comments": short_closure,
            "closure_code": {"name": closure_code},
        }

    return sdp_put(f"/api/v3/requests/{sdp_id}", token, {"request": body})


def set_flow(sdp_id: str, flow: str, token: str, transition: bool = False) -> dict:
    """Replace all flow:* tags with the new one. Optionally transition SDP status."""
    if flow not in {"queue", "active", "waiting", "done"}:
        raise ValueError(f"invalid flow: {flow!r}")

    req = fetch_request(sdp_id, token)
    current = set(get_tags(req))
    new_tags = (current - FLOW_TAGS) | {f"flow:{flow}"}
    result = put_tags(sdp_id, sorted(new_tags), token)

    if transition:
        status_name = FLOW_STATUS_MAP[flow]
        transition_status(sdp_id, status_name, token)

    return result


# ---------------------------------------------------------------------------
# Description (HTML clerk card + web links)
# ---------------------------------------------------------------------------

def build_html_description(clerk_card: str, web_links: list[dict],
                           original_request: str = "") -> str:
    """Build an HTML description from parsed case markdown sections.

    Args:
        clerk_card: Raw text from the ## Clerk Card section (markdown blockquote).
        web_links: List of {"label": ..., "url": ...} from ## Web Links.
        original_request: Text from ## Description section (original request body).

    Returns HTML string suitable for SDP request description field.
    """
    import html as html_mod

    parts = ['<div style="font-family: \'Segoe UI\', Arial, sans-serif; font-size: 13px;">']

    # --- Clerk Card ---
    if clerk_card:
        parts.append('<h3>📰 Context Card</h3>')
        # Parse the blockquote lines (strip > prefix)
        card_lines = []
        for line in clerk_card.splitlines():
            stripped = line.lstrip("> ").rstrip()
            if stripped:
                card_lines.append(stripped)
        # Render card lines with bold labels
        card_html = []
        for line in card_lines:
            escaped = html_mod.escape(line)
            # Bold leading labels: **Lede.**, **Status.**, **Next.**, **Links:**
            for label in ("Lede.", "Status.", "Next.", "Links:"):
                escaped = escaped.replace(f"**{label}**", f"<strong>{label}</strong>")
            # Convert markdown links [text](url) to clickable <a> tags
            escaped = re.sub(
                r'\[([^\]]+)\]\((https?://[^\)]+)\)',
                r'<a href="\2">\1</a>',
                escaped,
            )
            # Convert bare list-item links (- [text](url)) to proper list items
            if escaped.strip().startswith("- <a"):
                escaped = escaped.strip().removeprefix("- ")
                card_html.append(f"<li>{escaped}</li>")
            else:
                card_html.append(f"<p>{escaped}</p>")
        # Wrap any <li> runs in <ul>
        final_card = []
        in_list = False
        for h in card_html:
            if h.startswith("<li>"):
                if not in_list:
                    final_card.append("<ul>")
                    in_list = True
                final_card.append(h)
            else:
                if in_list:
                    final_card.append("</ul>")
                    in_list = False
                final_card.append(h)
        if in_list:
            final_card.append("</ul>")
        parts.append("\n".join(final_card))

    # --- Web Links ---
    if web_links:
        parts.append('<h3>🔗 Related Documentation</h3>')
        parts.append('<ul>')
        for link in web_links:
            label = html_mod.escape(link["label"])
            url = html_mod.escape(link["url"])
            parts.append(f'<li><a href="{url}">{label}</a></li>')
        parts.append('</ul>')

    # --- Original Request ---
    if original_request:
        parts.append('<h3>📋 Original Request</h3>')
        # Take first meaningful paragraph (skip separators)
        paras = [p.strip() for p in original_request.split("\n\n") if p.strip()
                 and not p.strip().startswith("---")]
        for para in paras[:3]:
            parts.append(f"<p>{html_mod.escape(para)}</p>")

    parts.append('</div>')
    return "\n".join(parts)


def update_description(sdp_id: str, html: str, token: str) -> dict:
    """PUT the HTML description onto the request."""
    return sdp_put(f"/api/v3/requests/{sdp_id}", token,
                   {"request": {"description": html}})


# ---------------------------------------------------------------------------
# Notes (comments)
# ---------------------------------------------------------------------------

def add_note(sdp_id: str, text: str, token: str,
             show_to_requester: bool = False, mark_first_response: bool = False) -> dict:
    payload = {
        "request_note": {
            "description": text,
            "show_to_requester": show_to_requester,
            "mark_first_response": mark_first_response,
            "add_to_linked_requests": False,
        }
    }
    return sdp_post(f"/api/v3/requests/{sdp_id}/notes", token, payload)


# ---------------------------------------------------------------------------
# Worklogs
# ---------------------------------------------------------------------------

WORKLOG_TIME_RE = re.compile(r"(?:(\d+)h)?\s*(?:(\d+)m)?", re.IGNORECASE)


def parse_time_spent(spec: str) -> tuple[int, int]:
    """Parse '2h', '30m', '1h30m' into (hours, minutes)."""
    s = spec.strip().lower()
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*m", s)
    hours = int(h.group(1)) if h else 0
    minutes = int(m.group(1)) if m else 0
    if hours == 0 and minutes == 0:
        # bare integer = minutes
        if s.isdigit():
            minutes = int(s)
    return hours, minutes


def add_worklog(sdp_id: str, description: str, time_spent: str, token: str,
                owner_email: str = "<YOUR_EMAIL>") -> dict:
    hours, minutes = parse_time_spent(time_spent)
    now_ms = int(time.time() * 1000)
    payload = {
        "worklog": {
            "description": description,
            "start_time": {"value": now_ms},
            "time_spent": {"hours": str(hours), "minutes": str(minutes)},
            "owner": {"email_id": owner_email},
            "include_nonoperational_hours": True,
            "mark_first_response": False,
        }
    }
    return sdp_post(f"/api/v3/requests/{sdp_id}/worklogs", token, payload)


# ---------------------------------------------------------------------------
# Tasks — SDP-native checkbox equivalent
# ---------------------------------------------------------------------------

TASK_STATUS_OPEN = "Open"
TASK_STATUS_DONE = "Closed"


def create_task(sdp_id: str, title: str, token: str,
                description: str | None = None, status: str = TASK_STATUS_OPEN) -> dict:
    payload = {
        "task": {
            "title": title,
            "description": description or title,
            "status": {"name": status},
        }
    }
    return sdp_post(f"/api/v3/requests/{sdp_id}/tasks", token, payload)


def update_task(sdp_id: str, task_id: str, token: str,
                title: str | None = None, status: str | None = None) -> dict:
    task: dict = {}
    if title is not None:
        task["title"] = title
    if status is not None:
        task["status"] = {"name": status}
    return sdp_put(f"/api/v3/requests/{sdp_id}/tasks/{task_id}", token, {"task": task})


def delete_task(sdp_id: str, task_id: str, token: str) -> dict:
    return sdp_delete(f"/api/v3/requests/{sdp_id}/tasks/{task_id}", token)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

def create_approval_level(sdp_id: str, level: int, token: str) -> dict:
    payload = {"approval_level": {"level": level}}
    return sdp_post(f"/api/v3/requests/{sdp_id}/approval_levels", token, payload)


def add_approver(sdp_id: str, level_id: str, approver_emails: list[str], token: str) -> list[dict]:
    """Add one approver per POST — SDP rejects bulk 'approvals' arrays."""
    results = []
    for email in approver_emails:
        payload = {"approval": {"approver": {"email_id": email}}}
        results.append(
            sdp_post(f"/api/v3/requests/{sdp_id}/approval_levels/{level_id}/approvals", token, payload)
        )
    return results


# ---------------------------------------------------------------------------
# Linked requests
# ---------------------------------------------------------------------------

def link_request(sdp_id: str, other_id: str, token: str, comments: str = "") -> dict:
    payload = {
        "link_requests": [{
            "linked_request": {"id": other_id},
            "comments": comments,
        }]
    }
    return sdp_post(f"/api/v3/requests/{sdp_id}/link_requests", token, payload)


def unlink_request(sdp_id: str, link_id: str, token: str) -> dict:
    return sdp_delete(f"/api/v3/requests/{sdp_id}/link_requests/{link_id}", token)


# ---------------------------------------------------------------------------
# Web links — SDP has no native "web link" panel, so we model them as notes
# prefixed with [LINK]. fetch_notes can be filtered for these.
# ---------------------------------------------------------------------------

WEB_LINK_PREFIX = "[LINK]"


def add_web_link(sdp_id: str, label: str, url: str, token: str) -> dict:
    text = f"{WEB_LINK_PREFIX} {label}: {url}" if label and label != url else f"{WEB_LINK_PREFIX} {url}"
    return add_note(sdp_id, text, token, show_to_requester=False)


def fetch_web_links(sdp_id: str, token: str) -> list[dict]:
    """Return [{label, url, note_id}, ...] from notes prefixed with [LINK]."""
    out = []
    for note in fetch_notes(sdp_id, token, row_count=100):
        desc = _txt(note.get("description"))
        if not desc.startswith(WEB_LINK_PREFIX):
            continue
        body = desc[len(WEB_LINK_PREFIX):].strip()
        if ": " in body and "http" in body:
            label, _, url = body.partition(": ")
            out.append({"label": label.strip(), "url": url.strip(),
                        "note_id": _txt(note.get("id"))})
        elif body.startswith("http"):
            out.append({"label": body, "url": body, "note_id": _txt(note.get("id"))})
    return out


# ---------------------------------------------------------------------------
# Markdown helpers — case file parse/upsert
# ---------------------------------------------------------------------------

CASE_HEADER_FIELDS = (
    "SDP_ID", "JIRA", "OWNER", "Tags", "Urgency", "Importance", "Agentic",
    "Constraint", "Approvers", "Summary", "Long_ID", "Status", "SDP_Request",
    "Created", "Requester", "Technician",
)

# Matches both `Key: value` and `**Key:** value` (bold markdown header)
HEADER_LINE_RE = re.compile(r"^\*{2}([A-Za-z_ ]+?):\*{2}\s*(.*)$|^([A-Za-z_]+):\s*(.*)$")


def parse_case_header(text: str) -> dict[str, str]:
    """Parse the top-of-file `KEY: value` header lines (above ## or ---).

    Handles both `Key: value` and `**Key:** value` (bold markdown headers).
    Normalizes keys: 'Long ID' → 'sdp_id', spaces → underscores, lowercased.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("## ") or line.strip() == "---":
            break
        m = HEADER_LINE_RE.match(line.strip())
        if m:
            # Group 1,2 for **Bold:** pattern; group 3,4 for plain Key: pattern
            raw_key = (m.group(1) or m.group(3) or "").strip()
            value = (m.group(2) or m.group(4) or "").strip()
            if not raw_key:
                continue
            # Normalize key
            norm_key = raw_key.replace(" ", "_")
            # Map common field names
            if norm_key.lower() == "long_id":
                out["sdp_id"] = value
            elif norm_key.lower() == "sdp_request":
                import re as _re
                did = _re.search(r"#(\d+)", value)
                if did:
                    out["sdp_display_id"] = did.group(1)
            else:
                out[norm_key] = value
                out[norm_key.lower()] = value
    return out


SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def extract_section(text: str, name: str) -> str | None:
    """Return body of `## {name}` section (until next `## ` or EOF), or None."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"## {name}":
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip("\n")


CHECKBOX_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+?)\s*$")


def parse_tasks_section(body: str) -> list[dict]:
    """Parse '- [x] item' / '- [ ] item' lines into [{done, text}, ...]."""
    out = []
    for line in (body or "").splitlines():
        m = CHECKBOX_RE.match(line)
        if m:
            out.append({"done": m.group(1).lower() == "x", "text": m.group(2).strip()})
    return out


LINK_LINE_RE = re.compile(r"^\s*-\s*(?:\[([^\]]+)\]\((https?://[^\s)]+)\)|(https?://\S+))\s*$")


def parse_links_section(body: str) -> list[dict]:
    """Parse '- [label](url)' or '- url' lines."""
    out = []
    for line in (body or "").splitlines():
        m = LINK_LINE_RE.match(line)
        if m:
            label = m.group(1) or m.group(3)
            url = m.group(2) or m.group(3)
            out.append({"label": label, "url": url})
    return out


LINKED_REQ_RE = re.compile(r"^\s*-\s*SDP[-#]?(\d+)(?:\s*[—–-]\s*(.*))?$", re.IGNORECASE)


def parse_linked_requests_section(body: str) -> list[dict]:
    """Parse '- SDP-33903 — note' lines."""
    out = []
    for line in (body or "").splitlines():
        m = LINKED_REQ_RE.match(line)
        if m:
            out.append({"display_id": m.group(1), "note": (m.group(2) or "").strip()})
    return out


APPROVAL_RE = re.compile(r"^\s*-\s*L(\d+):\s*(.+?)\s*$")


def parse_approval_section(body: str) -> list[dict]:
    """Parse '- L1: email1@<ORG_DOMAIN>, email2@<ORG_DOMAIN>' lines into [{level, approvers}, ...]."""
    out = []
    for line in (body or "").splitlines():
        m = APPROVAL_RE.match(line)
        if m:
            emails = [e.strip() for e in m.group(2).split(",") if e.strip()]
            out.append({"level": int(m.group(1)), "approvers": emails})
    return out


# ---------------------------------------------------------------------------
# Classification — lane assignment from header scoring
# ---------------------------------------------------------------------------

def classify_lane(header: dict[str, str]) -> str:
    """Return one of: sdp_urgent, sdp_approval, sdp_background.

    Mirrors Jira lane logic but applied to SDP case header fields.
    """
    def _int(key: str, default: int = 3) -> int:
        try:
            return int(header.get(key, default))
        except (ValueError, TypeError):
            return default

    urgency = _int("Urgency", 3)
    importance = _int("Importance", 3)
    agentic = _int("Agentic", 3)

    if urgency <= 2:
        return "sdp_urgent"
    if agentic >= 4 and importance <= 3:
        return "sdp_approval"
    if agentic <= 2:
        return "sdp_background"
    return "sdp_approval"  # default: manual approval lane


# ---------------------------------------------------------------------------
# Stable identity helpers (for upserts that need deterministic IDs)
# ---------------------------------------------------------------------------

def stable_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]
    return f"{prefix}-{h}"
