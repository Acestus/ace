#!/usr/bin/env python3
"""
jira_lib.py — Shared helpers for Jira automation scripts.

Used by:
    jira_update_fields.py  — imperative CLI (legacy / escape hatch)
    sync_jira_fields.py    — markdown-driven state reconciliation (primary)

Provides ADF builders, classifiers, REST wrappers, and parse/upsert primitives
for Notes, Checklist, Remote Links, and Issue Links.
"""

import base64
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path


JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES  # noqa: E402


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def auth_header():
    require_env(
        "CONFLUENCE_EMAIL",
        "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)",
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
    return f"Basic {encoded}"


# ---------------------------------------------------------------------------
# ADF helpers
# ---------------------------------------------------------------------------

def text_node(text: str, href: str | None = None) -> dict:
    node = {"type": "text", "text": text}
    if href:
        node["marks"] = [{"type": "link", "attrs": {"href": href}}]
    return node


def hard_break() -> dict:
    return {"type": "hardBreak"}


def paragraph(*nodes: dict) -> dict:
    return {"type": "paragraph", "content": list(nodes)}


def adf_paragraph(text: str) -> dict:
    return {"type": "doc", "version": 1, "content": [paragraph(text_node(text))]}


def adf_bullet_list(items: list[str]) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [paragraph(text_node(item))]}
                    for item in items
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Notes doc — newspaper-lede card
# ---------------------------------------------------------------------------

def build_notes_doc(lead: str | None, status: str | None, next_line: str | None) -> dict:
    """Compose ADF doc: lede paragraph + Status/Next paragraph. NO link bullets
    (Jira's wiki renderer mangles ADF link marks — URLs go in Remote Links)."""
    content: list[dict] = []
    if lead:
        content.append(paragraph(text_node(lead)))

    meta_nodes: list[dict] = []
    if status:
        meta_nodes.append(text_node(f"Status: {status}"))
    if next_line:
        if meta_nodes:
            meta_nodes.append(hard_break())
        meta_nodes.append(text_node(f"Next: {next_line}"))
    if meta_nodes:
        content.append(paragraph(*meta_nodes))

    if not content:
        content.append(paragraph(text_node("")))

    return {"type": "doc", "version": 1, "content": content}


# ---------------------------------------------------------------------------
# Checklist (HeroCoders Issue Checklist plugin — customfield_10032)
# ---------------------------------------------------------------------------
#
# HeroCoders rendered syntax (one item per line, paragraphs in ADF doc):
#   # Section header        — visual grouping, doesn't count toward progress
#   * Item text             — open todo
#   * [x] Item text         — done

CHECKLIST_PREFIX_RE = re.compile(r"^\s*\[(?P<mark>[ xX])\]\s+(?P<text>.+)$")


def parse_checklist_item(raw: str) -> str:
    """Normalize loose input ('Do thing', '[x] Do thing', '- [ ] Do thing', '# Section')
    into HeroCoders line syntax ('* Do thing', '* [x] Do thing', '# Section')."""
    s = raw.strip()
    if s.startswith("#"):
        return s
    if s.startswith("- "):
        s = s[2:].lstrip()
    if s.startswith("* "):
        s = s[2:].lstrip()
    m = CHECKLIST_PREFIX_RE.match(s)
    if m:
        if m.group("mark").lower() == "x":
            return f"* [x] {m.group('text').strip()}"
        return f"* {m.group('text').strip()}"
    return f"* {s}"


def build_checklist_doc(items: list[str]) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [paragraph(text_node(parse_checklist_item(i))) for i in items],
    }


def empty_checklist_doc() -> dict:
    return {"type": "doc", "version": 1, "content": [paragraph(text_node(""))]}


# ---------------------------------------------------------------------------
# Related-link classification (kept for label-hint coverage, no longer for sorting)
# ---------------------------------------------------------------------------

RELATED_CATEGORIES = ["Parent / Epic", "Related Jira", "Confluence", "Microsoft docs", "Vendor / External"]

JIRA_BROWSE_RE = re.compile(r"https?://[^/]*atlassian\.net/browse/[A-Z]+-\d+")
CONFLUENCE_RE = re.compile(r"https?://([^/]*atlassian\.net/wiki/|wiki\.<org_short>\.us)")
MS_DOCS_RE = re.compile(r"https?://(learn|docs)\.microsoft\.com")


def classify_related(label: str, url: str) -> str:
    label_lower = label.lower()
    if "parent" in label_lower or "epic" in label_lower:
        return "Parent / Epic"
    if JIRA_BROWSE_RE.search(url):
        return "Related Jira"
    if CONFLUENCE_RE.search(url):
        return "Confluence"
    if MS_DOCS_RE.search(url):
        return "Microsoft docs"
    return "Vendor / External"


def parse_related(raw: str) -> tuple[str, str]:
    """Parse 'Label|URL' into (label, url). URL alone is allowed."""
    if "|" not in raw:
        return raw.strip(), raw.strip()
    label, _, url = raw.partition("|")
    return label.strip(), url.strip()


# ---------------------------------------------------------------------------
# Jira REST: field PUT
# ---------------------------------------------------------------------------

def jira_put(key: str, fields: dict, auth: str) -> None:
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}"
    payload = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            if body.strip():
                print(f"  WARN unexpected response: {body[:200]}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", key=key, operation="PUT /issue (update fields)",
                  common_causes=JIRA_COMMON_CAUSES)


# ---------------------------------------------------------------------------
# Remote Links (Web Links panel)
# ---------------------------------------------------------------------------

def favicon_for(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    host = m.group(1) if m else ""
    return f"https://www.google.com/s2/favicons?domain={host}&sz=16" if host else ""


def jira_upsert_remote_link(key: str, label: str, url: str, auth: str) -> None:
    """POST a remote link with a deterministic globalId so re-runs update in place."""
    global_id = "url-" + hashlib.sha1(url.encode()).hexdigest()
    payload = json.dumps({
        "globalId": global_id,
        "object": {
            "url": url,
            "title": label or url,
            "icon": {"url16x16": favicon_for(url), "title": "Link"},
        },
    }).encode()
    api = f"{JIRA_BASE}/rest/api/3/issue/{key}/remotelink"
    req = urllib.request.Request(
        api,
        data=payload,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  WARN remote link {url}: HTTP {e.code} {body[:200]}", file=sys.stderr)


def fetch_remote_links(key: str, auth: str) -> list[dict]:
    """Return [{globalId, title, url}, ...] for a given issue."""
    api = f"{JIRA_BASE}/rest/api/3/issue/{key}/remotelink"
    req = urllib.request.Request(api, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  WARN couldn't fetch remote links on {key}: {e.code}", file=sys.stderr)
        return []
    out = []
    for link in data:
        obj = link.get("object") or {}
        out.append({
            "id": link.get("id"),
            "globalId": link.get("globalId"),
            "title": obj.get("title", ""),
            "url": obj.get("url", ""),
        })
    return out


def jira_delete_remote_link(key: str, link_id: str, auth: str) -> None:
    api = f"{JIRA_BASE}/rest/api/3/issue/{key}/remotelink/{link_id}"
    req = urllib.request.Request(api, headers={"Authorization": auth}, method="DELETE")
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"  WARN couldn't delete remote link {link_id} on {key}: {e.code}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Issue Links (Linked Work Items)
# ---------------------------------------------------------------------------
#
# Direction semantics (Jira REST):
#   outwardIssue --[type.outward]--> inwardIssue
#   e.g. for type "Blocks": outwardIssue blocks inwardIssue
#                           inwardIssue is blocked by outwardIssue

LINK_VERB_MAP = {
    "blocks":            ("Blocks",    True),
    "blocked-by":        ("Blocks",    False),
    "is-blocked-by":     ("Blocks",    False),
    "relates":           ("Relates",   True),
    "relates-to":        ("Relates",   True),
    "duplicates":        ("Duplicate", True),
    "duplicated-by":     ("Duplicate", False),
    "is-duplicated-by":  ("Duplicate", False),
    "clones":            ("Cloners",   True),
    "cloned-by":         ("Cloners",   False),
    "is-cloned-by":      ("Cloners",   False),
}


def parse_link_spec(raw: str) -> tuple[str, str, bool]:
    """Parse 'verb:KEY' or 'Type Name:KEY' into (type_name, target_key, current_is_outward)."""
    if ":" not in raw:
        raise ValueError(f"link spec must be 'verb:KEY' (got {raw!r})")
    verb, _, target = raw.partition(":")
    verb = verb.strip().lower().replace(" ", "-")
    target = target.strip().upper()
    if verb in LINK_VERB_MAP:
        type_name, current_is_outward = LINK_VERB_MAP[verb]
        return type_name, target, current_is_outward
    return verb.title(), target, True


def fetch_existing_links(key: str, auth: str) -> list[tuple[str, str, bool]]:
    """Return [(type_name, other_key, current_is_outward), ...] for an issue.

    In Jira's issuelinks payload the field name describes the OTHER end:
      - link has `inwardIssue: X`  => current is outward, other (X) is inward
      - link has `outwardIssue: X` => current is inward,  other (X) is outward
    """
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}?fields=issuelinks"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  WARN couldn't fetch links on {key}: {e.code}", file=sys.stderr)
        return []
    out: list[tuple[str, str, bool]] = []
    for link in data.get("fields", {}).get("issuelinks") or []:
        type_name = (link.get("type") or {}).get("name", "")
        if link.get("inwardIssue"):
            out.append((type_name, link["inwardIssue"]["key"], True))
        elif link.get("outwardIssue"):
            out.append((type_name, link["outwardIssue"]["key"], False))
    return out


def jira_upsert_issue_link(key: str, type_name: str, target: str, current_is_outward: bool,
                            auth: str, existing: list[tuple[str, str, bool]]) -> str:
    """Create an issue link only if it doesn't already exist. Returns a status string."""
    sig = (type_name, target, current_is_outward)
    if sig in existing:
        return f"skip (exists): {type_name} {'→' if current_is_outward else '←'} {target}"

    if current_is_outward:
        payload = {"type": {"name": type_name},
                   "outwardIssue": {"key": key},
                   "inwardIssue": {"key": target}}
    else:
        payload = {"type": {"name": type_name},
                   "outwardIssue": {"key": target},
                   "inwardIssue": {"key": key}}

    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/issueLink",
        data=json.dumps(payload).encode(),
        headers={"Authorization": auth, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        existing.append(sig)
        return f"created: {type_name} {'→' if current_is_outward else '←'} {target}"
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return f"FAIL {e.code}: {type_name} -> {target}  {body[:200]}"
