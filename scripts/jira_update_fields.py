#!/usr/bin/env python3
"""
jira_update_fields.py — Update Jira ticket fields directly.

The Notes field (customfield_10246) is the ticket's newspaper-lede snapshot:
a self-contained card you can read in 20 seconds at standup. It is built from
three structured inputs (lead / status / next) and rendered as ADF.

URLs are NOT written into the Notes field — Jira's wiki-markup renderer turns
ADF link marks into literal `[text|url]` text. Instead, every `--related` is
upserted as a Jira Remote Link (clickable in the ticket's 'Web links' panel).

Usage (new structured form):
    python3 scripts/jira_update_fields.py --key <PROJECT>-257 \
        --lead "Tenable's CIEM Enterprise module surfaces overprivileged \
identities across AWS/Azure/GCP — closing the SASE control-plane gap left \
by the standard CNAPP license. Without it, identity-risk findings remain \
advisory instead of enforceable." \
        --status "flow:waiting — <APPROVER_NAME> to approve Enterprise upgrade budget" \
        --next "Escalation message drafted; sending today after standup" \
        --related "Parent epic — <PROJECT>-188|https://<YOUR_ATLASSIAN>.atlassian.net/browse/<PROJECT>-188" \
        --related "Vendor — Tenable CIEM overview|https://www.tenable.com/products/tenable-cloud-security" \
        --related "Confluence — CNAPP Deployment Runbook|https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/12345" \
        --blocked-by <PROJECT>-263 \
        --next-steps "Approve Tenable CIEM Enterprise budget" \
        --due 2026-06-01 \
        --sdp-url "https://<YOUR_SDP>.sdpondemand.manageengine.com/..." \
        --ac "Criterion one" --ac "Criterion two"

Legacy form (still works — single plain paragraph):
    python3 scripts/jira_update_fields.py --key <PROJECT>-366 --notes "..."

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail

from jira_lib import (
    load_env_file, auth_header,
    adf_paragraph, adf_bullet_list,
    build_notes_doc, build_checklist_doc, empty_checklist_doc,
    parse_related,
    jira_put, jira_upsert_remote_link,
    parse_link_spec, fetch_existing_links, jira_upsert_issue_link,
)


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Update Jira ticket fields")
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-366")

    # Structured Notes inputs (new)
    parser.add_argument("--lead",
                        help="Notes: newspaper-lede paragraph — what it is + why it matters (1-3 sentences)")
    parser.add_argument("--status",
                        help="Notes: one line — flow state + current blocker (e.g. 'flow:waiting — <APPROVER_NAME> to approve')")
    parser.add_argument("--next", dest="next_in_notes",
                        help="Notes: one line — literal next action (mirrors --next-steps into the Notes card)")
    parser.add_argument("--related", action="append", dest="related", default=[], metavar="LABEL|URL",
                        help="Web link as 'Label|URL'. Repeatable. Upserted as a Jira Remote Link in the ticket's 'Web links' panel (clickable, with favicon). Does NOT write into the Notes field — link marks render as literal wiki text there. Deduped by SHA-1 of URL so re-runs update in place.")
    parser.add_argument("--checklist", action="append", dest="checklist_items", default=[], metavar="ITEM",
                        help="Checklist item (HeroCoders Issue Checklist on customfield_10032). Repeatable. "
                             "Use '[x] text' for done, plain text for todo, or '# Section' for a header. "
                             "Re-running --checklist overwrites the whole list.")
    parser.add_argument("--checklist-clear", action="store_true",
                        help="Empty the checklist (writes a blank doc to customfield_10032).")

    # Linked work items (Jira issue links)
    parser.add_argument("--blocks", action="append", dest="blocks", default=[], metavar="KEY",
                        help="This issue blocks KEY. Repeatable. Idempotent (skips if link already exists).")
    parser.add_argument("--blocked-by", action="append", dest="blocked_by", default=[], metavar="KEY",
                        help="This issue is blocked by KEY. Repeatable.")
    parser.add_argument("--relates", action="append", dest="relates", default=[], metavar="KEY",
                        help="This issue relates to KEY. Repeatable.")
    parser.add_argument("--duplicates", action="append", dest="duplicates", default=[], metavar="KEY",
                        help="This issue duplicates KEY. Repeatable.")
    parser.add_argument("--clones", action="append", dest="clones", default=[], metavar="KEY",
                        help="This issue clones KEY. Repeatable.")
    parser.add_argument("--link", action="append", dest="link_specs", default=[], metavar="VERB:KEY",
                        help="Generic linked work item: 'verb:KEY' (e.g. 'blocks:<PROJECT>-275', 'is-blocked-by:<PROJECT>-263', "
                             "'relates:<PROJECT>-100'). Repeatable. Escape hatch for less common link types.")

    # Legacy single-paragraph form
    parser.add_argument("--notes",
                        help="Notes (legacy): single plain paragraph. Use --lead/--status/--next/--related instead.")

    # Other fields
    parser.add_argument("--next-steps", dest="next_steps",
                        help="Next Steps field (customfield_10280) — one sentence")
    parser.add_argument("--due", help="Due date YYYY-MM-DD")
    parser.add_argument("--sdp-url", dest="sdp_url", help="SDP issue URL (customfield_10404)")
    parser.add_argument("--ac", action="append", dest="ac_items", metavar="CRITERION",
                        help="Acceptance criteria item (repeat for multiple)")
    args = parser.parse_args()

    # Assemble all linked-work-item specs
    link_specs: list[tuple[str, str, bool]] = []
    for k in args.blocks:        link_specs.append(("Blocks",    k.strip().upper(), True))
    for k in args.blocked_by:    link_specs.append(("Blocks",    k.strip().upper(), False))
    for k in args.relates:       link_specs.append(("Relates",   k.strip().upper(), True))
    for k in args.duplicates:    link_specs.append(("Duplicate", k.strip().upper(), True))
    for k in args.clones:        link_specs.append(("Cloners",   k.strip().upper(), True))
    for raw in args.link_specs:
        link_specs.append(parse_link_spec(raw))

    structured = any([args.lead, args.status, args.next_in_notes])
    if not any([args.notes, structured, args.next_steps, args.due, args.sdp_url,
                args.ac_items, args.checklist_items, args.checklist_clear,
                args.related, link_specs]):
        parser.print_help()
        sys.exit(1)

    if args.notes and structured:
        fail(
            "--notes is the legacy form; cannot combine with --lead/--status/--next",
            causes=["Both legacy and structured Notes arguments were passed"],
            try_=["Use --lead/--status/--next for structured Notes, or --notes alone for the legacy paragraph form"],
        )

    auth = auth_header()
    fields: dict = {}
    related_pairs = [parse_related(r) for r in args.related]

    if structured:
        fields["customfield_10246"] = build_notes_doc(
            lead=args.lead,
            status=args.status,
            next_line=args.next_in_notes,
        )
    elif args.notes:
        fields["customfield_10246"] = adf_paragraph(args.notes)

    if args.next_steps:
        fields["customfield_10280"] = args.next_steps

    if args.due:
        fields["duedate"] = args.due

    if args.sdp_url:
        fields["customfield_10404"] = args.sdp_url

    if args.ac_items:
        fields["customfield_10057"] = adf_bullet_list(args.ac_items)

    if args.checklist_items:
        fields["customfield_10032"] = build_checklist_doc(args.checklist_items)
    elif args.checklist_clear:
        fields["customfield_10032"] = empty_checklist_doc()

    if fields:
        print(f"Updating {args.key}: {', '.join(fields.keys())}")
        jira_put(args.key, fields, auth)

    if related_pairs:
        print(f"Upserting {len(related_pairs)} remote link(s) on {args.key}")
        for label, url in related_pairs:
            jira_upsert_remote_link(args.key, label, url, auth)

    if link_specs:
        print(f"Upserting {len(link_specs)} linked work item(s) on {args.key}")
        existing = fetch_existing_links(args.key, auth)
        for type_name, target, outward in link_specs:
            result = jira_upsert_issue_link(args.key, type_name, target, outward, auth, existing)
            print(f"  • {result}")

    print(f"✓ {args.key} updated")


if __name__ == "__main__":
    main()
