#!/usr/bin/env python3
"""
migrate_case_files.py — Migrate existing cases/<ID>/<ID> - <summary>.md files
to the new canonical template by inserting missing sections idempotently.

Idempotent: re-running on already-migrated files is a no-op.

New header lines (inserted after SDP_ID if missing):
    OWNER: sdp
    Tags: —
    Urgency: 3
    Importance: 3
    Agentic: 4
    Approvers: —
    Summary: <first line of subject>

New sections (inserted before ## Follow-up if missing):
    ## Tasks            (carries TODO items from Follow-up if present)
    ## Web Links
    ## Linked Requests
    ## Approval

Usage:
    python3 scripts/migrate_case_files.py --dry-run
    python3 scripts/migrate_case_files.py
    python3 scripts/migrate_case_files.py --file cases/33903/...md
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CASES_DIR = REPO_ROOT / "cases"

SEP = "------------------------------------------------"
HEADER_DEFAULTS = [
    ("OWNER", "sdp"),
    ("Tags", "—"),
    ("Urgency", "3"),
    ("Importance", "3"),
    ("Agentic", "4"),
    ("Approvers", "—"),
]

NEW_SECTIONS_BEFORE_FOLLOWUP = ["Tasks", "Web Links", "Linked Requests", "Approval"]


def has_header_key(text: str, key: str) -> bool:
    return bool(re.search(rf"^{re.escape(key)}:\s", text, re.MULTILINE))


def has_section(text: str, name: str) -> bool:
    return bool(re.search(rf"^##\s+{re.escape(name)}\s*$", text, re.MULTILINE))


def insert_header_lines(text: str) -> tuple[str, list[str]]:
    """Insert missing header lines after SDP_ID line."""
    lines = text.splitlines(keepends=True)
    added = []
    # find SDP_ID line index
    sdp_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("SDP_ID:"):
            sdp_idx = i
            break
    if sdp_idx is None:
        return text, added

    # walk past existing header block (consecutive KEY: lines)
    insert_at = sdp_idx + 1
    while insert_at < len(lines) and re.match(r"^[A-Z][A-Za-z_]+:\s", lines[insert_at]):
        insert_at += 1

    to_insert = []
    for key, default in HEADER_DEFAULTS:
        if not has_header_key(text, key):
            to_insert.append(f"{key}: {default}\n")
            added.append(key)

    # Summary defaults from H1
    if not has_header_key(text, "Summary"):
        h1_match = re.search(r"^#\s+\d+\s*-\s*(.+)$", text, re.MULTILINE)
        summary = (h1_match.group(1).strip() if h1_match else "")[:120]
        to_insert.append(f"Summary: {summary}\n")
        added.append("Summary")

    if not to_insert:
        return text, added

    new_lines = lines[:insert_at] + to_insert + lines[insert_at:]
    return "".join(new_lines), added


def insert_sections(text: str) -> tuple[str, list[str]]:
    """Insert missing sections before ## Follow-up (or at end if Follow-up absent)."""
    added = []
    sections_to_add = []
    for name in NEW_SECTIONS_BEFORE_FOLLOWUP:
        if not has_section(text, name):
            sections_to_add.append(name)
            added.append(name)
    if not sections_to_add:
        return text, added

    block = ""
    for name in sections_to_add:
        block += f"\n## {name}\n\n{SEP}\n\n"

    followup_match = re.search(r"^##\s+Follow-up\s*$", text, re.MULTILINE)
    if followup_match:
        idx = followup_match.start()
        return text[:idx] + block.strip("\n") + "\n\n" + text[idx:], added
    else:
        # append at end
        return text.rstrip() + "\n" + block, added


def migrate_text(text: str) -> tuple[str, dict]:
    summary = {"header_added": [], "sections_added": []}
    text, hdr_added = insert_header_lines(text)
    summary["header_added"] = hdr_added
    text, sec_added = insert_sections(text)
    summary["sections_added"] = sec_added
    return text, summary


def migrate_file(path: Path, dry_run: bool = False) -> dict:
    original = path.read_text()
    new_text, summary = migrate_text(original)
    summary["file"] = str(path.relative_to(REPO_ROOT))
    summary["changed"] = (new_text != original)
    if summary["changed"] and not dry_run:
        path.write_text(new_text)
    return summary


def main():
    p = argparse.ArgumentParser(description="Migrate SDP case markdown to new template")
    p.add_argument("--file", help="Migrate a single file")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(CASES_DIR.glob("*/*.md"))

    if not files:
        print("No case files found.")
        return

    changed = 0
    for f in files:
        summary = migrate_file(f, dry_run=args.dry_run)
        marker = "*" if summary["changed"] else " "
        added = (summary["header_added"] + summary["sections_added"]) or ["—"]
        print(f"  {marker} {summary['file']}  +[{', '.join(added)}]")
        if summary["changed"]:
            changed += 1

    print(f"\n{'Would change' if args.dry_run else 'Changed'} {changed}/{len(files)} files")


if __name__ == "__main__":
    main()
