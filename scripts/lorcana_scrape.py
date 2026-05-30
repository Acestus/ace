#!/usr/bin/env python3
"""
lorcana_scrape.py — Scrape the full card list from lorcanaplayer.com.

Uses the site's two-stage AJAX loading to get all cards (not just the
first 30 rendered in the initial HTML).

Usage:
    python3 scripts/lorcana_scrape.py --set wilds-unknown
    python3 scripts/lorcana_scrape.py --url https://lorcanaplayer.com/wilds-unknown-card-list-lorcana-set-12/
    python3 scripts/lorcana_scrape.py --set wilds-unknown --out /tmp/cards.json
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

SET_URLS = {
    "wilds-unknown": "https://lorcanaplayer.com/wilds-unknown-card-list-lorcana-set-12/",
    "winterspell":   "https://lorcanaplayer.com/winterspell-card-list-lorcana-set-11/",
    "archazia":      "https://lorcanaplayer.com/archazia-card-list-lorcana-set-10/",
}

AJAX_URL = "https://lorcanaplayer.com/wp-admin/admin-ajax.php"

RARITY_MAP = {
    "C":  "Common",
    "UC": "Uncommon",
    "R":  "Rare",
    "SR": "Super Rare",
    "L":  "Legendary",
    "E":  "Enchanted",
    "EP": "Epic",
    "IC": "Iconic",
}

INK_COLORS = ["amber", "amethyst", "emerald", "ruby", "sapphire", "steel"]


def fetch(url: str, data: bytes = None, referer: str = None) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
        headers["Origin"] = "https://lorcanaplayer.com"
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse_ink(img_tag) -> str:
    if not img_tag:
        return ""
    text = ((img_tag.get("alt") or "") + (img_tag.get("src") or "")).lower()
    for color in INK_COLORS:
        if color in text:
            return color.capitalize()
    return ""


def parse_rows(soup) -> list[dict]:
    cards = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        num_text = cells[1].get_text(strip=True)
        if not re.match(r"^\d+", num_text):
            continue
        card_num = int(num_text.split("/")[0])
        name = cells[2].get_text(strip=True)
        card_type = cells[3].get_text(strip=True)
        ink = parse_ink(cells[4].find("img"))
        rarity_short = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        rarity = RARITY_MAP.get(rarity_short, rarity_short)
        cards.append({
            "number": card_num,
            "name":   name,
            "type":   card_type,
            "ink":    ink,
            "rarity": rarity,
        })
    return cards


def scrape(url: str) -> list[dict]:
    print(f"  Fetching page: {url}", file=sys.stderr)
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    block = soup.find(attrs={"data-nonce": True})
    if not block:
        print("ERROR: card list block not found on page", file=sys.stderr)
        sys.exit(1)

    nonce = block["data-nonce"]
    atts  = json.loads(block["data-atts"])
    set_name = atts["set"]
    estimated = atts.get("total_cards_estimated", "?")
    print(f"  Set: {set_name} | Estimated: {estimated} cards", file=sys.stderr)

    table = soup.find("table")
    cards = parse_rows(table)
    print(f"  First chunk: {len(cards)} cards", file=sys.stderr)

    post_data = urllib.parse.urlencode({
        "action":          "cardadmin_load_remaining",
        "set":             set_name,
        "sort_field":      "card_number",
        "sort_direction":  "asc",
        "display_options": json.dumps(atts.get("display_options", {})),
        "nonce":           nonce,
    }).encode()

    print(f"  Fetching remaining cards via AJAX...", file=sys.stderr)
    resp = json.loads(fetch(AJAX_URL, data=post_data, referer=url))
    if not resp.get("success"):
        print(f"ERROR: AJAX failed: {resp}", file=sys.stderr)
        sys.exit(1)

    remaining_html = resp["data"]["html"]
    remaining_soup = BeautifulSoup(
        f"<table><tbody>{remaining_html}</tbody></table>", "html.parser"
    )
    remaining = parse_rows(remaining_soup)
    print(f"  Remaining chunk: {len(remaining)} cards", file=sys.stderr)

    all_cards = sorted(cards + remaining, key=lambda c: c["number"])
    print(f"  Total: {len(all_cards)} cards scraped", file=sys.stderr)
    return all_cards


def format_txt(cards: list) -> str:
    """
    Three sections separated by blank lines, one value per line.
    Paste each section into a spreadsheet column.

    Section 1 — Card Names
    Section 2 — Rarities
    Section 3 — Ink Colors
    """
    names    = [c["name"]   for c in cards]
    rarities = [RARITY_MAP.get(c["rarity"], c["rarity"]) for c in cards]
    inks     = [c["ink"]    for c in cards]

    lines = []
    lines.append("=== NAMES ===")
    lines.extend(names)
    lines.append("")
    lines.append("=== RARITY ===")
    lines.extend(rarities)
    lines.append("")
    lines.append("=== INK COLOR ===")
    lines.extend(inks)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Scrape Lorcana card list")
    parser.add_argument("--set", default="wilds-unknown", choices=list(SET_URLS.keys()))
    parser.add_argument("--url", help="Override URL directly")
    parser.add_argument("--out", help="Write output to file (default: stdout)")
    parser.add_argument("--txt", action="store_true",
                        help="Output plain text sections for copy-paste instead of JSON")
    args = parser.parse_args()

    url = args.url or SET_URLS[args.set]
    cards = scrape(url)

    output = format_txt(cards) if args.txt else json.dumps(cards, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w") as f:
            f.write(output)
        print(f"  Wrote {len(cards)} cards to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
