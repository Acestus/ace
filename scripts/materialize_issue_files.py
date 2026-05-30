#!/usr/bin/env python3
"""
materialize_issue_files.py — Pull current Jira state and write/update issue markdown.

For each requested key, fetch Notes / Checklist / Web Links / Linked Issues from
Jira and inject those four sections into `issues/<KEY> - <summary>/<KEY> - <summary>.md`.

  - If the file already exists, the four sections are inserted (or replaced) in
    the correct order without touching ## Description, ## Investigation,
    ## Actions, ## Follow-up, or any other content.
  - If the file does not exist, a new one is created with placeholder
    Description / Actions / Follow-up sections.

Section order in the final file:
    # KEY - summary
    ## Notes            (new)
    ## Description
    ## Investigation    (only if existing)
    ## Actions
    ## Checklist        (new)
    ## Web Links        (new)
    ## Linked Issues    (new)
    ## Follow-up        (always last)

Usage:
    python3 scripts/materialize_issue_files.py --key <PROJECT>-275
    python3 scripts/materialize_issue_files.py --keys <PROJECT>-275 <PROJECT>-368
    python3 scripts/materialize_issue_files.py --assigned-to-me
    python3 scripts/materialize_issue_files.py --all-local      # every key already in issues/
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from jira_lib import JIRA_BASE, load_env_file, auth_header

REPO_ROOT = Path(__file__).parent.parent
ISSUES_DIR = REPO_ROOT / "issues"
JIRA_KEY_RE = re.compile(r"^(INFRA-\d+)")

NEW_SECTIONS = ("Notes", "Checklist", "Web Links", "Linked Issues")
PRESERVED_ORDER = ("Notes", "Description", "Investigation", "Actions",
                   "Checklist", "Web Links", "Linked Issues", "Follow-up")

FIELDS = ("summary,status,assignee,labels,description,customfield_10246,"
          "customfield_10280,customfield_10060,parent,issuelinks")


# ---------------------------------------------------------------------------
# Jira fetch
# ---------------------------------------------------------------------------

def fetch_issue(key: str, auth: str) -> dict:
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def fetch_remote_links(key: str, auth: str) -> list[dict]:
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}/remotelink"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except Exception:
        return []


def search_assigned(auth: str) -> list[str]:
    jql = 'assignee = currentUser() AND statusCategory != Done'
    url = (f"{JIRA_BASE}/rest/api/3/search/jql"
           f"?jql={urllib.parse.quote(jql)}&fields=summary&maxResults=200")
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    return [issue["key"] for issue in data.get("issues", [])]


# ---------------------------------------------------------------------------
# ADF → markdown rendering
# ---------------------------------------------------------------------------

def adf_to_text(node: dict | None) -> str:
    """Render an ADF doc to plain text (paragraphs separated by blank lines)."""
    if not node:
        return ""

    def render(n: dict) -> str:
        t = n.get("type")
        if t == "text":
            text = n.get("text", "")
            for mark in n.get("marks") or []:
                if mark.get("type") == "link":
                    href = (mark.get("attrs") or {}).get("href")
                    if href and href != text:
                        text = f"[{text}]({href})"
            return text
        if t == "hardBreak":
            return "\n"
        if t == "paragraph":
            return "".join(render(c) for c in n.get("content") or [])
        if t == "bulletList":
            return "\n".join("- " + render(li).lstrip() for li in n.get("content") or [])
        if t == "orderedList":
            return "\n".join(f"{i+1}. " + render(li).lstrip()
                              for i, li in enumerate(n.get("content") or []))
        if t in ("listItem", "doc"):
            return "".join(render(c) for c in n.get("content") or [])
        return "".join(render(c) for c in n.get("content") or [])

    parts = []
    for block in node.get("content") or []:
        rendered = render(block).strip()
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Build new section bodies from Jira state
# ---------------------------------------------------------------------------

def build_notes_section(notes_adf: dict | None, next_steps: str | None) -> str:
    """Render the Notes ADF (lede paragraph + 'Status: ...' + 'Next: ...' lines)
    into ### Lede / ### Status / ### Next subsections."""
    raw = adf_to_text(notes_adf).strip() if notes_adf else ""
    lede_lines: list[str] = []
    status = ""
    nxt = ""
    for line in raw.splitlines():
        s = line.strip()
        if s.lower().startswith("status:"):
            status = s.split(":", 1)[1].strip()
        elif s.lower().startswith("next:"):
            nxt = s.split(":", 1)[1].strip()
        elif s.lower().startswith("waiting on:"):
            # Legacy format — treat as part of status
            waiting_val = s.split(":", 1)[1].strip()
            if not status:
                status = f"flow:waiting — {waiting_val}"
        elif s.lower().startswith("what:"):
            # Legacy format — extract what follows "What:" as lede content
            what_val = s.split(":", 1)[1].strip()
            # Skip if it's a placeholder
            if what_val and not what_val.startswith("_("):
                lede_lines.append(what_val)
        else:
            lede_lines.append(line)
    lede = "\n".join(lede_lines).strip()
    # Strip any remaining placeholder patterns from lede
    placeholder_patterns = ["_(no description yet)_", "_(none)_", "_(add a 2-3 sentence"]
    for pat in placeholder_patterns:
        if lede.startswith(pat):
            lede = ""
            break
    # Fall back to next_steps board field if Notes didn't carry a Next line
    if not nxt and next_steps:
        nxt = next_steps.strip()

    out = ["## Notes", ""]
    out.append("### Lede")
    out.append("")
    out.append(lede if lede else "_(NEEDS LEDE — synthesize from ticket summary and description)_")
    out.append("")
    out.append("### Status")
    out.append("")
    out.append(status if status else "_(one line: flow:active|waiting|done — current blocker or owner.)_")
    out.append("")
    out.append("### Next")
    out.append("")
    out.append(nxt if nxt else "_(one line: the literal next action.)_")
    return "\n".join(out)


CHECKLIST_LINE_RE = re.compile(r"^\s*\*\s*\[(open|done)\]\s*(.*)$", re.IGNORECASE)


def build_checklist_section(checklist_adf: dict | None) -> str:
    """Convert HeroCoders checklist ADF back to GitHub-style ` - [ ] ` markdown."""
    raw = adf_to_text(checklist_adf).strip() if checklist_adf else ""
    if not raw:
        return ""
    out = ["## Checklist", ""]
    for line in raw.replace("\u200b", "").splitlines():
        s = line.rstrip()
        if not s:
            continue
        if s.startswith("# "):
            out.append("")
            out.append("### " + s[2:].strip())
            out.append("")
            continue
        m = CHECKLIST_LINE_RE.match(s)
        if m:
            mark = "x" if m.group(1).lower() == "done" else " "
            out.append(f"- [{mark}] {m.group(2).strip()}")
            continue
        if s.startswith("* "):
            out.append(f"- [ ] {s[2:].strip()}")
            continue
        out.append(s)
    return "\n".join(out).rstrip()


def build_web_links_section(remote_links: list[dict]) -> str:
    if not remote_links:
        return ""
    out = ["## Web Links", ""]
    for rl in remote_links:
        obj = rl.get("object") or {}
        title = obj.get("title") or obj.get("url") or "(link)"
        url = obj.get("url", "")
        if not url:
            continue
        out.append(f"- [{title}]({url})")
    return "\n".join(out)


def build_linked_issues_section(issuelinks: list[dict]) -> str:
    """Render Jira issuelinks as ` - verb: KEY (Summary)` lines.

    `inwardIssue` present  → current is outward source → verb is type.outward
    `outwardIssue` present → current is inward target → verb is type.inward
    """
    if not issuelinks:
        return ""
    out = ["## Linked Issues", ""]
    for link in issuelinks:
        t = link.get("type") or {}
        if link.get("inwardIssue"):
            verb = t.get("outward", "relates to")
            other = link["inwardIssue"]
        else:
            verb = t.get("inward", "relates to")
            other = link.get("outwardIssue", {})
        of = other.get("fields", {}) or {}
        summary = of.get("summary", "")
        comment = f"  <!-- {summary[:80]} -->" if summary else ""
        out.append(f"- {verb}: {other.get('key')}{comment}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Markdown section surgery
# ---------------------------------------------------------------------------

H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a markdown file into (preamble, [(heading, body), ...]).

    preamble is everything before the first `## ` heading (i.e. `# Title` line
    and any HTML comments / blank lines).
    body for each section *includes* the `## Heading` line and everything up to
    the next `## `.
    """
    matches = list(H2_RE.finditer(text))
    if not matches:
        return text, []
    preamble = text[:matches[0].start()].rstrip() + "\n"
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].rstrip() + "\n"
        sections.append((heading, body))
    return preamble, sections


def ordered_index(heading: str) -> int:
    """Return the canonical position index for a heading; unknown headings sort
    after Actions (so user-invented sections sit between Actions and Checklist)."""
    if heading in PRESERVED_ORDER:
        return PRESERVED_ORDER.index(heading) * 10
    # Follow-up must always be LAST regardless of new sections
    return PRESERVED_ORDER.index("Actions") * 10 + 5


def rebuild_file(preamble: str, sections: list[tuple[str, str]],
                  overrides: dict[str, str]) -> str:
    """Replace/insert sections from `overrides` and emit in canonical order."""
    by_heading = {h: b for h, b in sections}
    # Replace
    for heading, body in overrides.items():
        if body:
            by_heading[heading] = body.rstrip() + "\n"
        else:
            # empty override means leave alone if not already present, skip if present
            by_heading.pop(heading, None)

    # Stable order: Follow-up always last; others by ordered_index then original order
    original_order = [h for h, _ in sections]
    for h in overrides:
        if h not in original_order and overrides[h]:
            original_order.append(h)

    def sort_key(h: str) -> tuple[int, int]:
        # primary: canonical bucket; secondary: original file order so unknowns are stable
        idx = ordered_index(h)
        try:
            secondary = original_order.index(h)
        except ValueError:
            secondary = 9999
        # Force Follow-up dead last
        if h == "Follow-up":
            return (10_000, secondary)
        return (idx, secondary)

    ordered = sorted([h for h in by_heading], key=sort_key)
    out = [preamble.rstrip(), ""]
    for h in ordered:
        out.append(by_heading[h].rstrip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def file_for_key(key: str) -> Path | None:
    for folder in ISSUES_DIR.glob(f"{key}*"):
        if folder.is_dir():
            for f in folder.glob("*.md"):
                m = JIRA_KEY_RE.match(f.stem)
                if m and m.group(1) == key:
                    return f
        elif folder.suffix == ".md":
            m = JIRA_KEY_RE.match(folder.stem)
            if m and m.group(1) == key:
                return folder
    return None


def all_local_keys() -> list[str]:
    keys = set()
    for folder in ISSUES_DIR.iterdir():
        m = JIRA_KEY_RE.match(folder.name)
        if m:
            keys.add(m.group(1))
    return sorted(keys, key=lambda k: int(k.split("-")[1]))


def safe_filename(s: str) -> str:
    return re.sub(r"[<>:\"/\\|?*]", "-", s).strip()


# ---------------------------------------------------------------------------
# Materialize one key
# ---------------------------------------------------------------------------

def materialize_one(key: str, auth: str, dry_run: bool = False) -> bool:
    try:
        issue = fetch_issue(key, auth)
    except Exception as e:
        print(f"  ERROR fetching {key}: {e}", file=sys.stderr)
        return False

    f = issue["fields"]
    summary = f.get("summary", "")
    remote_links = fetch_remote_links(key, auth)

    overrides: dict[str, str] = {}
    overrides["Notes"] = build_notes_section(
        f.get("customfield_10246"),
        f.get("customfield_10280"),
    )
    cl = build_checklist_section(f.get("customfield_10060"))
    if cl:
        overrides["Checklist"] = cl
    wl = build_web_links_section(remote_links)
    if wl:
        overrides["Web Links"] = wl
    il = build_linked_issues_section(f.get("issuelinks") or [])
    if il:
        overrides["Linked Issues"] = il

    path = file_for_key(key)
    is_new = path is None
    if is_new:
        folder = ISSUES_DIR / safe_filename(f"{key} - {summary}")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{safe_filename(key + ' - ' + summary)}.md"
        text = (f"# {key} - {summary}\n"
                f"<!-- jira: {key} -->\n"
                f"<!-- last_synced: 1970-01-01T00:00:00Z -->\n\n"
                f"## Description\n\n"
                f"## Actions\n\n"
                f"## Follow-up\n\nStatus: flow:queue\n\nTODO:\n")
    else:
        text = path.read_text()

    preamble, sections = parse_sections(text)
    new_text = rebuild_file(preamble, sections, overrides)
    if new_text == text:
        print(f"  • {key}: no changes")
        return True

    flag = "NEW" if is_new else "UPD"
    print(f"  • {key} [{flag}]: {', '.join(sorted(overrides))} → {path.relative_to(REPO_ROOT)}")
    if not dry_run:
        path.write_text(new_text)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--key", help="One Jira key")
    g.add_argument("--keys", nargs="+", help="Multiple Jira keys")
    g.add_argument("--assigned-to-me", action="store_true",
                   help="All open tickets assigned to current user")
    g.add_argument("--all-local", action="store_true",
                   help="Every key with a folder under issues/")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    auth = auth_header()

    if args.key:
        keys = [args.key.strip().upper()]
    elif args.keys:
        keys = [k.strip().upper() for k in args.keys]
    elif args.assigned_to_me:
        keys = search_assigned(auth)
    else:
        keys = all_local_keys()

    print(f"Materializing {len(keys)} ticket(s)" + (" (dry run)" if args.dry_run else ""))
    ok = 0
    for k in keys:
        if materialize_one(k, auth, dry_run=args.dry_run):
            ok += 1
    print(f"\n=== Done: {ok}/{len(keys)} ===")


if __name__ == "__main__":
    main()
