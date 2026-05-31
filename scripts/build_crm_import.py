#!/usr/bin/env python3
"""
build_crm_import.py — Parse Build attendee list and bulk-import into Notion People DB.

Usage:
    python3 scripts/build_crm_import.py --dry-run          # preview, no writes
    python3 scripts/build_crm_import.py --db-id <ID>       # run import
    python3 scripts/build_crm_import.py --db-id <ID> --tier 1   # only Tier 1

Tiers:
    1 — Founders/CEOs, C-suite, VPs, Directors, Distinguished/Fellows, GMs
    2 — Principals, Architects, Senior Engineers, PMs, Staff, Leads, DAs
    3 — Everyone else (use --tier 3 to include all)

Microsoft employees are included at all tiers (not filtered out).
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notion_lib import notion_request, load_env_file

ATTENDEE_FILE = Path(__file__).parent.parent / "issues/ACE-6/attendee-list.md"

TIER1_KEYWORDS = {
    "founder", "co-founder", "ceo", "cto", "coo", "ciso", "cpo", "chief",
    "president", "vp ", "vice president", "svp", "evp", "gm ", "general manager",
    "managing director", "partner", "distinguished", "fellow",
    "director", "head of",
}

TIER2_KEYWORDS = {
    "principal", "architect", "staff ", "lead ", "senior", "sr.", "sr ",
    "product manager", "pm ", "developer advocate", "dev advocate",
    "evangelist", "strategist", "solutions engineer", "solutions architect",
}

BOILERPLATE = {
    "Save to favorites", "Bio", "Search attendees", "Refine results",
    "Show Results", "Favorites", "Recommended for you", "Topics of Interest",
    "Order by", "Relevance", "Microsoft", "Discover", "All Microsoft",
    "View your profile", "My event", "Attendee Directory", "",
}


def get_tier(title: str, company: str) -> int:
    t = title.lower()
    for kw in TIER1_KEYWORDS:
        if kw in t:
            return 1
    for kw in TIER2_KEYWORDS:
        if kw in t:
            return 2
    return 3


def parse_attendees(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    entries = []
    seen_names = set()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip boilerplate and navigation lines
        if (line in BOILERPLATE
                or line.startswith("Profile image of ")
                or line.startswith("Hi ")
                or line.startswith("Client:")
                or "Sitemap Contact Microsoft" in line
                or "attendees (" in line
                or re.match(r"^[A-Z]{2}$", line)       # initials placeholder
                or re.match(r"^Show \d+", line)):
            i += 1
            continue

        # Expect: name (has space, reasonable length)
        if not line or " " not in line or len(line) > 70:
            i += 1
            continue

        # Peek at next lines for title + company
        title = lines[i + 1].strip() if i + 1 < len(lines) else ""
        blank = lines[i + 2].strip() if i + 2 < len(lines) else ""
        company = lines[i + 3].strip() if i + 3 < len(lines) else ""

        # Validate the pattern
        if (title
                and blank == ""
                and company
                and company not in BOILERPLATE
                and len(title) < 120
                and len(company) < 100
                and not title.startswith("Profile image")
                and not company.startswith("Profile image")):

            name = line
            # De-dupe doubled names like "Arjun Jobanputra Jobanputra"
            parts = name.split()
            if len(parts) >= 2 and parts[-1] == parts[-2]:
                name = " ".join(parts[:-1])

            if name not in seen_names:
                seen_names.add(name)
                tier = get_tier(title, company)
                entries.append({
                    "name": name,
                    "title": title,
                    "company": company,
                    "tier": tier,
                })
            i += 5
            continue

        i += 1

    return entries


def create_notion_entry(db_id: str, person: dict) -> str:
    """Create one page in the People database. Returns the new page ID."""
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Name": {
                "title": [{"text": {"content": person["name"]}}]
            },
            "Company": {
                "rich_text": [{"text": {"content": person["company"]}}]
            },
            "Role": {
                "rich_text": [{"text": {"content": person["title"]}}]
            },
            "How We Met": {
                "rich_text": [{"text": {"content": "Microsoft Build 2026"}}]
            },
        },
    }
    result = notion_request("POST", "pages", payload)
    return result.get("id", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-id", help="Notion People database ID (find in DB URL)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and show counts only — no Notion writes")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=2,
                        help="Max tier to import (1=executives only, 2=+senior ICs, 3=all)")
    args = parser.parse_args()

    if not args.dry_run and not args.db_id:
        parser.error("--db-id required unless using --dry-run")

    load_env_file()

    print("Parsing attendee list...")
    attendees = parse_attendees(ATTENDEE_FILE)
    filtered = [a for a in attendees if a["tier"] <= args.tier]

    tier_counts = {1: 0, 2: 0, 3: 0}
    for a in attendees:
        tier_counts[a["tier"]] += 1

    print(f"\n✓ Parsed {len(attendees)} unique attendees")
    print(f"  Tier 1 (exec/founder/VP/director): {tier_counts[1]}")
    print(f"  Tier 2 (principal/architect/senior): {tier_counts[2]}")
    print(f"  Tier 3 (all others):                {tier_counts[3]}")
    print(f"\nImporting Tier 1–{args.tier}: {len(filtered)} contacts")

    if args.dry_run:
        print("\n--- DRY RUN: first 20 ---")
        for a in filtered[:20]:
            print(f"  T{a['tier']} | {a['name']:<35} | {a['title']:<45} | {a['company']}")
        print(f"\n  ... and {max(0, len(filtered)-20)} more")
        return

    print(f"\nWriting to Notion DB: {args.db_id}")
    ok, err = 0, 0
    for i, person in enumerate(filtered):
        try:
            create_notion_entry(args.db_id, person)
            ok += 1
            if ok % 10 == 0:
                print(f"  {ok}/{len(filtered)} imported...")
            time.sleep(0.34)   # Notion rate limit: 3 req/s
        except Exception as e:
            print(f"  ❌ {person['name']}: {e}")
            err += 1

    print(f"\n✅ Done — {ok} created, {err} errors")


if __name__ == "__main__":
    main()
