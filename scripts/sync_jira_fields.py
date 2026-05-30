#!/usr/bin/env python3
"""
sync_jira_fields.py — Reconcile structured Jira state from issue markdown.

Parses an `issues/<KEY> - <summary>/<KEY> - <summary>.md` file and pushes the
declared state to Jira:

  ## Notes
    ### Lede     → customfield_10246 (Notes) lede paragraph
    ### Status   → customfield_10246 (Notes) status line
    ### Next     → customfield_10246 (Notes) next-action line  +  customfield_10280

  ## Checklist  → customfield_10032 (HeroCoders Issue Checklist)

  ## Web Links  → Remote Links (clickable Web Links panel)
                  Markdown owns the full set: links NOT in the file are deleted
                  from Jira. Existing links written by other tools without a
                  `url-<sha1>` globalId are left untouched.

  ## Linked Issues → Jira issue links (Blocks / Relates / Duplicate / Cloners)
                     Markdown owns the full set: link types NOT in the file are
                     left untouched (we never delete issue links — too easy to
                     destroy human intent — but we do create missing ones).

The file is the source of truth. Re-running on an unchanged file is a no-op.

Usage:
    python3 scripts/sync_jira_fields.py --file 'issues/<PROJECT>-368 - .../<PROJECT>-368 - ....md'
    python3 scripts/sync_jira_fields.py --key <PROJECT>-368   # auto-locate file
    python3 scripts/sync_jira_fields.py --changed-since <SHA>   # all files changed in diff
    python3 scripts/sync_jira_fields.py --all                   # every file under issues/

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

from jira_lib import (
    JIRA_BASE,
    load_env_file, auth_header,
    build_notes_doc, build_checklist_doc, empty_checklist_doc,
    jira_put, jira_upsert_remote_link,
    fetch_remote_links, jira_delete_remote_link,
    parse_link_spec, fetch_existing_links, jira_upsert_issue_link,
)

REPO_ROOT = Path(__file__).parent.parent
ISSUES_DIR = REPO_ROOT / "issues"
JIRA_KEY_RE = re.compile(r"^(INFRA-\d+)")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
LINK_LINE_RE = re.compile(r"^\s*[-*]\s+([^:]+):\s*(INFRA-\d+)\b.*$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def split_top_level_sections(text: str) -> dict[str, str]:
    """Return {heading_text: body_text} for every `## Heading` in the file.

    Headings are case-preserving; body is everything from the heading line to
    the next `## ` (exclusive). Sub-headings (`### ...`) stay inside the body.
    """
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_body: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_body).strip()
            current_heading = m.group(1).strip()
            current_body = []
        else:
            if current_heading is not None:
                current_body.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_body).strip()
    return sections


def split_subsections(body: str) -> dict[str, str]:
    """Return {h3_heading_text: body_text} for every `### Heading` in a section body."""
    subs: dict[str, str] = {}
    current: str | None = None
    current_body: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                subs[current] = "\n".join(current_body).strip()
            current = m.group(1).strip()
            current_body = []
        else:
            if current is not None:
                current_body.append(line)
    if current is not None:
        subs[current] = "\n".join(current_body).strip()
    return subs


def strip_horizontal_rule(text: str) -> str:
    """Drop the leading `------` separator line that conventionally follows
    `## Section` headings in this repo's issue format."""
    lines = text.splitlines()
    while lines and (not lines[0].strip() or set(lines[0].strip()) <= {"-"}):
        lines.pop(0)
    return "\n".join(lines).strip()


def parse_notes_section(body: str) -> tuple[str | None, str | None, str | None]:
    """Extract (lede, status, next) from a ## Notes section.

    Supports two shapes:

      Shape A (sub-headings):
          ### Lede
          {paragraph(s)}
          ### Status
          {one line}
          ### Next
          {one line}

      Shape B (inline labels — backwards-compat with Notes-card prose):
          {lede paragraph}
          Status: ...
          Next: ...
    """
    body = strip_horizontal_rule(body)
    subs = split_subsections(body)
    if subs:
        return (
            _clean(subs.get("Lede")),
            _clean(subs.get("Status")),
            _clean(subs.get("Next")),
        )
    # Shape B: scan for Status:/Next: prefixes
    lede_lines: list[str] = []
    status: str | None = None
    nxt: str | None = None
    for line in body.splitlines():
        ls = line.strip()
        if ls.lower().startswith("status:"):
            status = ls.split(":", 1)[1].strip()
        elif ls.lower().startswith("next:"):
            nxt = ls.split(":", 1)[1].strip()
        else:
            lede_lines.append(line)
    return (_clean("\n".join(lede_lines)), status, nxt)


PLACEHOLDER_RE = re.compile(r"^_\(.*\)_\s*$")


def _clean(s: str | None) -> str | None:
    """Strip whitespace; treat placeholder lines (`_(...)_`) as empty."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    # If every non-blank line is a placeholder, treat as empty
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if lines and all(PLACEHOLDER_RE.match(ln) for ln in lines):
        return None
    return s


def parse_checklist_section(body: str) -> list[str]:
    """Parse a ## Checklist section into HeroCoders-ready item lines.

    Recognised patterns (one per line):
        - [ ] open item
        - [x] done item
        - plain item            (treated as open)
        * open / * [x] done     (alt bullets)
        ### Section header      → emitted as '# Section header' (HeroCoders syntax)

    Blank lines are skipped.
    """
    body = strip_horizontal_rule(body)
    items: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        # H3 → HeroCoders section header
        if s.startswith("### "):
            items.append("# " + s[4:].strip())
            continue
        if s.startswith("## "):
            # don't capture nested h2s as items
            continue
        # Strip list bullet
        for prefix in ("- ", "* ", "+ "):
            if s.startswith(prefix):
                s = s[len(prefix):]
                break
        if not s:
            continue
        # Already in [ ]/[x] form? Pass through; build_checklist_doc normalizes.
        items.append(s)
    return items


def parse_web_links_section(body: str) -> list[tuple[str, str]]:
    """Parse a ## Web Links section into [(label, url), ...].

    Recognised patterns (one link per line):
        - [Label](https://url)
        - https://url            (label = url)
        - Label: https://url
        - Label | https://url
    """
    body = strip_horizontal_rule(body)
    out: list[tuple[str, str]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        for prefix in ("- ", "* ", "+ "):
            if s.startswith(prefix):
                s = s[len(prefix):]
                break
        m = MD_LINK_RE.search(s)
        if m:
            out.append((m.group(1).strip(), m.group(2).strip()))
            continue
        if "|" in s:
            label, _, url = s.partition("|")
            url = url.strip()
            if url.startswith("http"):
                out.append((label.strip(), url))
                continue
        if ": http" in s:
            label, _, url = s.partition(":")
            out.append((label.strip(), url.strip()))
            continue
        if s.startswith("http"):
            out.append((s, s))
    return out


def parse_linked_issues_section(body: str) -> list[tuple[str, str, bool]]:
    """Parse a ## Linked Issues section into [(type_name, target_key, current_is_outward), ...]

    Recognised patterns (one per line):
        - blocks: <PROJECT>-275
        - is blocked by: <PROJECT>-263
        - relates to: <PROJECT>-188
        - duplicates: <PROJECT>-100
    """
    body = strip_horizontal_rule(body)
    out: list[tuple[str, str, bool]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        m = LINK_LINE_RE.match(s)
        if not m:
            continue
        verb = m.group(1).strip().lower()
        target = m.group(2).strip().upper()
        try:
            type_name, _t, outward = parse_link_spec(f"{verb}:{target}")
        except ValueError:
            print(f"  WARN: unrecognised link verb {verb!r} on line: {s}", file=sys.stderr)
            continue
        out.append((type_name, target, outward))
    return out


def extract_key_from_filename(path: Path) -> str | None:
    m = JIRA_KEY_RE.match(path.stem)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def sync_one_file(path: Path, auth: str, dry_run: bool = False) -> bool:
    key = extract_key_from_filename(path)
    if not key:
        print(f"  SKIP {path}: filename has no <PROJECT>-XXX key")
        return False

    text = path.read_text()
    sections = split_top_level_sections(text)

    notes_lede, notes_status, notes_next = parse_notes_section(sections.get("Notes", ""))
    checklist_items = parse_checklist_section(sections.get("Checklist", ""))
    web_links = parse_web_links_section(sections.get("Web Links", ""))
    issue_links = parse_linked_issues_section(sections.get("Linked Issues", ""))

    print(f"\n=== {key} ({path.name}) ===")
    print(f"  Notes:        lede={'yes' if notes_lede else 'no'}, status={'yes' if notes_status else 'no'}, next={'yes' if notes_next else 'no'}")
    print(f"  Checklist:    {len(checklist_items)} items")
    print(f"  Web Links:    {len(web_links)}")
    print(f"  Linked Issues:{len(issue_links)}")

    if dry_run:
        return True

    fields: dict = {}

    # Notes — only push if any of the three are present
    if any([notes_lede, notes_status, notes_next]):
        fields["customfield_10246"] = build_notes_doc(notes_lede, notes_status, notes_next)

    # Next Steps (board view) — mirror the Next line
    if notes_next:
        fields["customfield_10280"] = notes_next

    # Checklist — push only if section exists in file; empty section clears the field
    if "Checklist" in sections:
        if checklist_items:
            fields["customfield_10032"] = build_checklist_doc(checklist_items)
        else:
            fields["customfield_10032"] = empty_checklist_doc()

    if fields:
        print(f"  Updating fields: {', '.join(fields.keys())}")
        jira_put(key, fields, auth)

    # Web Links — reconcile (add missing, remove obsolete url-<sha1> entries)
    if "Web Links" in sections:
        reconcile_web_links(key, web_links, auth)

    # Linked Issues — create missing (we never delete; too risky)
    if issue_links:
        existing = fetch_existing_links(key, auth)
        for type_name, target, outward in issue_links:
            result = jira_upsert_issue_link(key, type_name, target, outward, auth, existing)
            print(f"  • {result}")

    print(f"  ✓ {key} synced")
    return True


def reconcile_web_links(key: str, desired: list[tuple[str, str]], auth: str) -> None:
    """Add missing links and delete any url-<sha1>-marked links no longer in markdown.

    Links written by other tools (no globalId, or non-url-<sha1> globalId) are
    left alone — we only manage links we put there ourselves.
    """
    existing = fetch_remote_links(key, auth)
    desired_global_ids = {"url-" + hashlib.sha1(url.encode()).hexdigest() for _label, url in desired}
    existing_global_ids = {link["globalId"] for link in existing if link.get("globalId")}

    to_add = [(label, url) for (label, url) in desired
              if ("url-" + hashlib.sha1(url.encode()).hexdigest()) not in existing_global_ids]
    to_delete = [link for link in existing
                 if link.get("globalId", "").startswith("url-")
                 and link["globalId"] not in desired_global_ids]

    if to_add or to_delete:
        print(f"  Web Links: +{len(to_add)} / -{len(to_delete)}")

    for label, url in to_add:
        jira_upsert_remote_link(key, label, url, auth)
        print(f"    + {label}  {url}")

    for link in to_delete:
        jira_delete_remote_link(key, link["id"], auth)
        print(f"    - {link.get('title', '')}  {link.get('url', '')}")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def file_for_key(key: str) -> Path | None:
    """Return the markdown file path for a given <PROJECT>-XXX key."""
    for folder in ISSUES_DIR.glob(f"{key}*"):
        if folder.is_dir():
            for f in folder.glob("*.md"):
                if extract_key_from_filename(f) == key:
                    return f
        elif folder.suffix == ".md" and extract_key_from_filename(folder) == key:
            return folder
    return None


def files_changed_since(ref: str) -> list[Path]:
    """Return issue files that changed (added or modified) since the given git ref."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=AM", f"{ref}..HEAD", "--", "issues/"],
            cwd=REPO_ROOT, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR git diff: {e}", file=sys.stderr)
        return []
    paths = []
    for name in out.splitlines():
        name = name.strip()
        if not name or not name.endswith(".md"):
            continue
        p = REPO_ROOT / name
        if p.exists() and extract_key_from_filename(p):
            paths.append(p)
    return paths


def all_issue_files() -> list[Path]:
    paths = []
    for folder in ISSUES_DIR.iterdir():
        if folder.is_dir():
            for f in folder.glob("*.md"):
                if extract_key_from_filename(f):
                    paths.append(f)
    return sorted(paths)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="Path to a single issue markdown file")
    g.add_argument("--key", help="<PROJECT>-XXX key (auto-locates the file)")
    g.add_argument("--changed-since", metavar="SHA",
                   help="Sync every issue file changed since this git ref")
    g.add_argument("--all", action="store_true", help="Sync every issue file under issues/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and report — don't push anything to Jira")
    args = parser.parse_args()

    if args.file:
        paths = [Path(args.file)]
    elif args.key:
        p = file_for_key(args.key.strip().upper())
        if not p:
            print(f"ERROR: no markdown file found for {args.key}", file=sys.stderr)
            sys.exit(2)
        paths = [p]
    elif args.changed_since:
        paths = files_changed_since(args.changed_since)
        if not paths:
            print(f"No issue files changed since {args.changed_since}")
            return
    else:
        paths = all_issue_files()

    auth = "" if args.dry_run else auth_header()
    print(f"Syncing {len(paths)} file(s)" + (" (dry run)" if args.dry_run else ""))
    ok = 0
    for p in paths:
        try:
            if sync_one_file(p, auth, dry_run=args.dry_run):
                ok += 1
        except Exception as e:
            print(f"  ERROR processing {p}: {e}", file=sys.stderr)
    print(f"\n=== Done: {ok}/{len(paths)} files synced ===")


if __name__ == "__main__":
    main()
