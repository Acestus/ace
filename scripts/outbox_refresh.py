#!/usr/bin/env python3
"""
outbox_refresh.py — Rebuild per-stakeholder outbox files from flow:waiting tickets.

Reads every `flow:waiting` issue file under issues/ and renders rich "newspaper-card"
markdown into planner/outbox/{stakeholder-slug}.md. Each card is reconstructed from
the ticket's `## Notes` Lede / Status / Next subsections plus Web Links and
Linked Issues — the same shape <ORG_NAME> Clerk uses for kanban cards.

Routing rules (each waiting ticket lands in one or more outbox files):
  1. Always: michael-seaman.md  (manager catch-all — needed for the weekly backlog meeting)
  2. Any names found in `## Follow-up` line `Waiting on: Name One, Name Two`
  3. Any names parsed from `### Status` line ("waiting on X", "blocked by X")
  4. Fallback bucket files for non-person waits:
       _code-review.md       — "code review" or "pr review"
       _vendor.md            — "vendor", "support ticket", "microsoft support", "atlassian"
       _external-ticket.md   — "blocked by <PROJECT>-..." or "waiting on ticket"
       _no-stakeholder.md    — anything else with no extractable owner

The `## Draft Messages` block at the bottom of each outbox file is preserved across runs.

Usage:
  python3 scripts/outbox_refresh.py
  python3 scripts/outbox_refresh.py --no-catchall    # skip <APPROVER_NAME> manager catch-all
  python3 scripts/outbox_refresh.py --manager "Some Other Manager"
  python3 scripts/outbox_refresh.py --dry-run
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail

ISSUES_DIR = Path("issues")
DEFAULT_OUTBOX_DIR = Path("planner/outbox")
DEFAULT_MANAGER = "<APPROVER_NAME>"
TODAY = date.today().isoformat()

# --- regex helpers -----------------------------------------------------------

SECTION_RE = lambda name: re.compile(
    rf"^## {re.escape(name)}\s*$(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE
)
SUBSECTION_RE = lambda name: re.compile(
    rf"^### {re.escape(name)}\s*$(.*?)(?=^### |^## |\Z)", re.DOTALL | re.MULTILINE
)

# "waiting on X", "blocked by X", "pending X" — pull names/labels
# Captures the trailing phrase after these triggers.
WAITING_PHRASE_RE = re.compile(
    r"(?:waiting on|blocked by|pending|awaiting)\s+([A-Z][A-Za-z0-9 .'\-/]{2,60})",
    re.IGNORECASE,
)

# Person-name heuristic — two capitalized tokens (e.g., "<APPROVER_NAME>")
PERSON_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")

NON_PERSON_LABELS = {
    "code review": "_code-review",
    "pr review": "_code-review",
    "vendor": "_vendor",
    "support ticket": "_vendor",
    "microsoft support": "_vendor",
    "atlassian": "_vendor",
    "atlassian support": "_vendor",
    "tenable": "_vendor",
    "fortinet": "_vendor",
    "network team": "_vendor",
    "procurement": "_vendor",
    "csp": "_vendor",
    "external ticket": "_external-ticket",
    "ticket": "_external-ticket",
    "infra-": "_external-ticket",
    "sdp-": "_external-ticket",
    "global admin": "_global-admin",
    "leadership": "_leadership",
    "compliance": "_compliance",
}

KEY_RE = re.compile(r"\b(INFRA-\d+|SDP-\d+)\b")


def slugify(name: str) -> str:
    """'Greg Carlton' → 'greg-carlton';  '_vendor' stays as '_vendor'."""
    if name.startswith("_"):
        return name
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


# --- ticket parsing ----------------------------------------------------------

def parse_section(md: str, name: str) -> str:
    m = SECTION_RE(name).search(md)
    return m.group(1).strip() if m else ""


def parse_subsection(section_text: str, name: str) -> str:
    m = SUBSECTION_RE(name).search(section_text)
    return m.group(1).strip() if m else ""


def clean_placeholder(text: str) -> str:
    """Treat _(italic placeholder)_ lines as empty."""
    if not text:
        return ""
    lines = [l for l in text.splitlines() if not re.match(r"^\s*_\(.*\)_\s*$", l)]
    return "\n".join(lines).strip()


def extract_ticket_key(file_path: Path, md: str) -> str:
    m = KEY_RE.search(file_path.name)
    if m:
        return m.group(1)
    m = re.search(r"<!--\s*jira:\s*(INFRA-\d+|SDP-\d+)\s*-->", md)
    if m:
        return m.group(1)
    return ""


def extract_title(md: str, fallback: str) -> str:
    m = re.match(r"^# (.+)", md)
    if m:
        return m.group(1).strip()
    return fallback


def extract_jira_url(md: str, key: str) -> str:
    m = re.search(r"https://<org_short>fg\.atlassian\.net/browse/(INFRA-\d+|SDP-\d+)", md)
    if m:
        return m.group(0)
    if key.startswith("INFRA-") or key.startswith("SDP-"):
        return f"https://<YOUR_ATLASSIAN>.atlassian.net/browse/{key}"
    return ""


def extract_waiting_since(md: str) -> tuple[str, str]:
    """Return (date_str, stale_days_str). Uses last ### YYYY-MM-DD action header."""
    dates = re.findall(r"^### (\d{4}-\d{2}-\d{2})\s*$", md, re.MULTILINE)
    if not dates:
        return "", ""
    last = sorted(dates)[-1]
    try:
        delta = date.today() - datetime.strptime(last, "%Y-%m-%d").date()
        return last, f"{delta.days}d"
    except ValueError:
        return last, ""


def extract_followup_waiting_on(md: str) -> tuple[list[str], list[str]]:
    """Parse `Waiting on:` from Follow-up. Returns (people, fallback_buckets)."""
    section = parse_section(md, "Follow-up")
    if not section:
        return [], []
    m = re.search(r"Waiting on:\s*(.+)", section)
    if not m:
        return [], []
    raw = m.group(1)
    people: list[str] = []
    buckets: list[str] = []
    for chunk in re.split(r",\s*", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Strip after em-dash, en-dash, or " - " — keep only the entity name
        chunk = re.split(r"\s+[—–-]\s+", chunk, maxsplit=1)[0].strip()
        # Strip parentheticals: "Greg Carlton (network team)" → "Greg Carlton"
        chunk = re.sub(r"\s*\(.*?\)", "", chunk).strip()
        if not chunk:
            continue
        lowered = chunk.lower()
        matched_bucket = False
        for label, bucket in NON_PERSON_LABELS.items():
            if label in lowered:
                if bucket not in buckets:
                    buckets.append(bucket)
                matched_bucket = True
                break
        if matched_bucket:
            continue
        # Treat as a person name if it's 2-3 capitalized tokens
        pm = PERSON_RE.match(chunk)
        if pm and len(chunk.split()) <= 4:
            if pm.group(1) not in people:
                people.append(pm.group(1))
        else:
            if "_no-stakeholder" not in buckets:
                buckets.append("_no-stakeholder")
    return people, buckets


def extract_status_stakeholders(status_line: str) -> tuple[list[str], list[str]]:
    """Parse `### Status` line for stakeholders. Returns (people, fallback_bucket_keys)."""
    if not status_line:
        return [], []
    people: list[str] = []
    buckets: list[str] = []
    lowered = status_line.lower()

    # Non-person buckets — match by label keyword
    for label, bucket in NON_PERSON_LABELS.items():
        if label in lowered:
            if bucket not in buckets:
                buckets.append(bucket)

    # External-ticket bucket — <PROJECT>-### or SDP-### in the status line
    if re.search(r"\b(INFRA-\d+|SDP-\d+)\b", status_line):
        if "_external-ticket" not in buckets:
            buckets.append("_external-ticket")

    # Person extraction: phrases like "waiting on Greg Carlton"
    for m in WAITING_PHRASE_RE.finditer(status_line):
        target = m.group(1).strip()
        # If it looks like a person (two+ capitalized tokens), keep it
        pm = PERSON_RE.match(target)
        if pm:
            people.append(pm.group(1))

    return people, buckets


def parse_links_block(md: str, name: str) -> list[str]:
    """Return raw markdown list items from a section."""
    section = parse_section(md, name)
    if not section:
        return []
    items = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            # Strip leading "- " or "* "
            items.append(line[2:].strip())
    return items


# --- card rendering ----------------------------------------------------------

def render_card(t: dict) -> str:
    """Render a single ticket card — newspaper-lede style, like a <ORG_NAME> Clerk kanban card."""
    lines = []
    title = t["title"]
    key = t["key"]
    jira = t["jira_url"]

    # Header: ### KEY — title (jira link)
    if jira:
        lines.append(f"### [{key}]({jira}) — {title}")
    else:
        lines.append(f"### {key} — {title}")

    # Waiting-since badge
    if t["waiting_since"]:
        stale = f" · {t['stale_days']} ago" if t["stale_days"] else ""
        lines.append(f"_Waiting since {t['waiting_since']}{stale}_")

    # Direct path into the Jira ticket — primary entry point for meeting direction
    if jira:
        lines.append(f"📎 **[Open in Jira →]({jira})**  ·  `python3 scripts/jira_comment.py --key {key} --comment \"...\"`")
    lines.append("")

    # The newspaper lede
    if t["lede"]:
        lines.append(t["lede"])
        lines.append("")

    # Status + Next
    if t["status"]:
        lines.append(f"**Status.** {t['status']}")
    if t["next_action"]:
        lines.append(f"**Next.** {t['next_action']}")
    if t["status"] or t["next_action"]:
        lines.append("")

    # Web Links
    if t["web_links"]:
        lines.append("**Links:**")
        for item in t["web_links"]:
            lines.append(f"- {item}")
        lines.append("")

    # Linked Issues
    if t["linked_issues"]:
        lines.append("**Linked issues:**")
        for item in t["linked_issues"]:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def render_outbox_file(stakeholder: str, tickets: list[dict], display_name: str) -> str:
    header = [
        f"# {display_name} — Follow-up Outbox",
        "",
        f"_Auto-generated by `scripts/outbox_refresh.py` from `flow:waiting` issue and case files. Last updated: {TODAY}_",
        f"_{len(tickets)} card{'s' if len(tickets) != 1 else ''}. Edit only the Draft Messages section at the bottom — everything above it is overwritten on each refresh._",
        "",
        "---",
        "",
        "## Pending",
        "",
    ]
    # Stale tickets first (longest waiting at the top)
    def sort_key(t):
        days = 0
        if t["stale_days"]:
            try:
                days = int(t["stale_days"].rstrip("d"))
            except ValueError:
                pass
        return -days

    tickets_sorted = sorted(tickets, key=sort_key)

    cards = [render_card(t) for t in tickets_sorted]
    body = header + ["\n".join(cards)] if cards else header + ["_No waiting tickets routed here._", ""]
    return "\n".join(body) + "\n"


def display_for(slug: str) -> str:
    """Render the human-readable header from a slug or person name."""
    mapping = {
        "_code-review": "Code Review Queue",
        "_vendor": "Vendor & External Support",
        "_external-ticket": "Blocked by External Tickets",
        "_no-stakeholder": "Waiting — No Stakeholder Identified",
        "_global-admin": "Global Admin Queue",
        "_leadership": "Leadership Decision Queue",
        "_compliance": "Compliance Review Queue",
    }
    return mapping.get(slug, slug)


def preserve_draft_block(outbox_path: Path) -> str:
    """Preserve the operator's draft block. We anchor to a `## Draft Messages`
    line that starts at the beginning of a line AND is not embedded inside an
    italic header line (which contains a backtick before the section name).
    To be safe against legacy corrupted files, we take the LAST occurrence."""
    if not outbox_path.exists():
        return ""
    content = outbox_path.read_text(encoding="utf-8")
    # Find every plausible section header — start-of-line, optional spaces, then
    # `## Draft Messages` not preceded by a backtick.
    matches = list(re.finditer(
        r"^## Draft Messages\b(?!`)", content, re.MULTILINE
    ))
    if not matches:
        return ""
    # Take the last one — older corrupted runs may have duplicates.
    start = matches[-1].start()
    return content[start:].rstrip()


# --- main flow ---------------------------------------------------------------

CASES_DIR = Path("cases")

BOLD_HEADER_RE = re.compile(r"^\*{2}([A-Za-z_ ]+?):\*{2}\s*(.*)$")


def scan_cases(cases_dir: Path, jira_keys_seen: set[str] | None = None) -> list[dict]:
    """Scan cases/ for flow:waiting SDP tickets and return them in the same
    dict shape as scan_issues() so they can be unioned into the same outbox routing.

    If jira_keys_seen is provided, skip SDP cases whose linked Jira ticket is
    already in that set (avoids duplicate cards in the outbox).
    """
    results: list[dict] = []
    if not cases_dir.exists():
        return results

    for case_dir in sorted(cases_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        md_files = list(case_dir.glob("*.md"))
        if not md_files:
            continue
        md_file = md_files[0]
        try:
            md = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "flow:waiting" not in md:
            continue

        # Parse bold headers
        header: dict[str, str] = {}
        for line in md.splitlines()[:30]:
            m = BOLD_HEADER_RE.match(line)
            if m:
                header[m.group(1).strip().lower()] = m.group(2).strip()
            elif line.startswith("# "):
                header["_title"] = line[2:].strip()

        owner = header.get("owner", "sdp")
        if owner.lower() != "sdp":
            continue

        # Dedup: if this case has a linked Jira ticket that's already in the
        # outbox from issues/, skip it (Jira is the primary card)
        jira_refs = re.findall(r"(INFRA-\d+)", md)
        if jira_keys_seen and jira_refs:
            if any(k in jira_keys_seen for k in jira_refs):
                continue

        display_id = case_dir.name
        title = header.get("_title", display_id)
        requester = header.get("requester", "")

        # Build SDP URL
        long_id = header.get("long id", "")
        sdp_url = (f"https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/{long_id}/details"
                   if long_id else "")

        # Parse clerk card blockquote for lede/status/next
        lede = ""
        status = ""
        next_action = ""
        in_clerk = False
        for line in md.splitlines():
            if "## 📰 Clerk Card" in line:
                in_clerk = True
                continue
            if in_clerk and line.startswith("## "):
                break
            if in_clerk and line.startswith("> **Lede.**"):
                lede = line.split("**Lede.**", 1)[1].strip()
            elif in_clerk and line.startswith("> **Status.**"):
                status = line.split("**Status.**", 1)[1].strip()
            elif in_clerk and line.startswith("> **Next.**"):
                next_action = line.split("**Next.**", 1)[1].strip()

        # Waiting since — last ### YYYY-MM-DD action header
        waiting_since, stale_days = extract_waiting_since(md)

        # Stakeholder routing from Follow-up section
        explicit_people, explicit_buckets = extract_followup_waiting_on(md)
        status_people, status_buckets = extract_status_stakeholders(status)

        people = []
        for p in explicit_people + status_people:
            if p not in people:
                people.append(p)
        buckets = []
        for b in explicit_buckets + status_buckets:
            if b not in buckets:
                buckets.append(b)

        # Also route to requester if it looks like a person name
        if requester and not people:
            req_name = re.match(r"([A-Z][a-z]+ [A-Z][a-z]+)", requester)
            if req_name:
                people.append(req_name.group(1))

        results.append({
            "key": f"SDP #{display_id}",
            "title": title.split(" - ", 1)[-1] if " - " in title else title,
            "jira_url": sdp_url,
            "lede": lede,
            "status": status,
            "next_action": next_action,
            "waiting_since": waiting_since,
            "stale_days": stale_days,
            "web_links": [],
            "linked_issues": [],
            "people": people,
            "fallback_buckets": buckets,
            "source_file": str(md_file),
        })

    return results


def scan_issues(issues_dir: Path) -> list[dict]:
    """Return list of waiting-ticket dicts ready for routing. Dedupes by ticket key
    (keeping the longest source path — typically the canonical long-name folder)."""
    raw: list[dict] = []
    for md_file in sorted(issues_dir.rglob("*.md")):
        if "archive" in md_file.parts:
            continue
        try:
            md = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "flow:waiting" not in md:
            continue

        key = extract_ticket_key(md_file, md)
        title = extract_title(md, md_file.stem)
        jira_url = extract_jira_url(md, key)

        notes_section = parse_section(md, "Notes")
        lede = clean_placeholder(parse_subsection(notes_section, "Lede"))
        status = clean_placeholder(parse_subsection(notes_section, "Status"))
        next_action = clean_placeholder(parse_subsection(notes_section, "Next"))

        # Fallback: pull "Their next action:" from Follow-up if Notes/Next is empty
        if not next_action:
            fu = parse_section(md, "Follow-up")
            m = re.search(r"Their next action:\s*(.+)", fu)
            if m:
                next_action = m.group(1).strip()

        waiting_since, stale_days = extract_waiting_since(md)
        web_links = parse_links_block(md, "Web Links")
        linked_issues = parse_links_block(md, "Linked Issues")

        explicit_people, explicit_buckets = extract_followup_waiting_on(md)
        status_people, status_buckets = extract_status_stakeholders(status)

        people = []
        for p in explicit_people + status_people:
            if p not in people:
                people.append(p)
        buckets = []
        for b in explicit_buckets + status_buckets:
            if b not in buckets:
                buckets.append(b)

        raw.append({
            "key": key,
            "title": title,
            "jira_url": jira_url,
            "lede": lede,
            "status": status,
            "next_action": next_action,
            "waiting_since": waiting_since,
            "stale_days": stale_days,
            "web_links": web_links,
            "linked_issues": linked_issues,
            "people": people,
            "fallback_buckets": buckets,
            "source_file": str(md_file),
        })

    # Dedup by key — when multiple files share a key (old short-folder + canonical
    # long-folder), keep the one with the richest content (longest source path
    # tends to be the canonical one, and break ties by longest lede).
    by_key: dict[str, dict] = {}
    for t in raw:
        k = t["key"] or t["source_file"]  # fall back to path for keyless files
        existing = by_key.get(k)
        if not existing:
            by_key[k] = t
            continue
        # Prefer the entry with a longer source path, then with a longer lede.
        if (len(t["source_file"]), len(t["lede"])) > (len(existing["source_file"]), len(existing["lede"])):
            by_key[k] = t

    return list(by_key.values())


def route_to_outboxes(
    tickets: list[dict],
    manager: str | None,
    no_catchall: bool,
) -> dict[str, list[dict]]:
    """Group tickets by outbox-slug. A single ticket can appear in multiple outboxes."""
    by_slug: dict[str, list[dict]] = defaultdict(list)

    manager_slug = slugify(manager) if manager else None

    for t in tickets:
        targets: list[str] = []

        for person in t["people"]:
            targets.append(slugify(person))
        for bucket in t["fallback_buckets"]:
            if bucket not in targets:
                targets.append(bucket)

        # Catch-all: manager outbox always gets every waiting ticket
        if manager_slug and not no_catchall and manager_slug not in targets:
            targets.append(manager_slug)

        # If after all that we still have nothing, route to _no-stakeholder
        if not targets:
            targets.append("_no-stakeholder")

        for slug in targets:
            by_slug[slug].append(t)

    return by_slug


def write_outboxes(
    by_slug: dict[str, list[dict]],
    outbox_dir: Path,
    dry_run: bool,
    manager: str | None,
) -> None:
    outbox_dir.mkdir(parents=True, exist_ok=True)

    manager_slug = slugify(manager) if manager else None
    written = []
    for slug, tickets in sorted(by_slug.items()):
        out_path = outbox_dir / f"{slug}.md"
        if slug == manager_slug:
            display = manager
        elif slug.startswith("_"):
            display = display_for(slug)
        else:
            # Person slug → title-case the name back
            display = slug.replace("-", " ").title()

        body = render_outbox_file(slug, tickets, display)
        draft_block = preserve_draft_block(out_path)
        if draft_block:
            full = body + "\n" + draft_block + "\n"
        else:
            full = body + "\n## Draft Messages\n\n<!-- Paste Teams / email drafts here. Everything below this line is preserved across refreshes. -->\n"

        if dry_run:
            written.append(f"  DRY-RUN  {out_path}  ({len(tickets)} cards)")
            continue
        out_path.write_text(full, encoding="utf-8")
        written.append(f"  ✓ {slug:<30s}  {len(tickets):>3d} cards  →  {out_path}")

    # Prune outbox files for slugs that no longer have any routed tickets
    if not dry_run:
        current_slugs = set(by_slug.keys())
        for stale_path in outbox_dir.glob("*.md"):
            slug = stale_path.stem
            if slug not in current_slugs:
                # Preserve files that contain a non-empty draft block the user wrote
                # (delete only fully auto-generated empty ones to be safe)
                stale_path.unlink()
                print(f"  🗑  Removed stale outbox: {stale_path.name}")

    print(f"\n  ✓ Outbox refresh complete — {len(written)} stakeholder file(s)")
    for line in written:
        print(line)


def main():
    parser = argparse.ArgumentParser(description="Rebuild stakeholder outbox files from flow:waiting issue files")
    parser.add_argument("--outbox-dir", default=str(DEFAULT_OUTBOX_DIR))
    parser.add_argument("--issues-dir", default=str(ISSUES_DIR))
    parser.add_argument("--manager", default=DEFAULT_MANAGER,
                        help=f"Manager who gets the catch-all outbox (default: {DEFAULT_MANAGER})")
    parser.add_argument("--no-catchall", action="store_true",
                        help="Disable manager catch-all outbox")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    issues_dir = Path(args.issues_dir)
    outbox_dir = Path(args.outbox_dir)
    if not issues_dir.exists():
        fail(
            f"Issues directory not found: {issues_dir}",
            causes=["Not running from the repo root",
                    "--issues-dir path is wrong"],
            try_=["cd /home/wweeks/git/projects && python3 scripts/outbox_refresh.py",
                  "ls issues/"],
        )

    tickets = scan_issues(issues_dir)
    # Collect Jira keys already in the outbox to avoid duplicate SDP cards
    jira_keys_seen = {t["key"] for t in tickets if t["key"].startswith("INFRA-")}
    sdp_tickets = scan_cases(CASES_DIR, jira_keys_seen=jira_keys_seen)
    all_tickets = tickets + sdp_tickets
    print(f"  📥 Scanned {len(list(issues_dir.rglob('*.md')))} issue files — {len(tickets)} are flow:waiting")
    if sdp_tickets:
        print(f"  📥 Scanned cases/ — {len(sdp_tickets)} SDP cases are flow:waiting (deduplicated)")
    by_slug = route_to_outboxes(all_tickets, args.manager, args.no_catchall)
    write_outboxes(by_slug, outbox_dir, args.dry_run, args.manager)


if __name__ == "__main__":
    main()
