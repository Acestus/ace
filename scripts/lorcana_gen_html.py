#!/usr/bin/env python3
"""
lorcana_gen_html.py — Generate a pixel-perfect printable HTML card checklist
                       from scraped Lorcana card data.

Usage:
    python3 scripts/lorcana_gen_html.py --set wilds-unknown --out /tmp/wilds-unknown.html
    python3 scripts/lorcana_gen_html.py --cards /tmp/cards.json --set-name "Wilds Unknown" --out out.html
"""

import argparse
import json
import sys
from pathlib import Path

RARITY_COLORS = {
    "Common":    "#9CA3AF",  # gray
    "Uncommon":  "#34D399",  # green
    "Rare":      "#60A5FA",  # blue
    "Super Rare":"#A78BFA",  # purple
    "Legendary": "#FBBF24",  # gold
    "Enchanted": "#F472B6",  # pink/rainbow
    "Epic":      "#FB923C",  # orange
    "Iconic":    "#C084FC",  # light purple
}

INK_COLORS = {
    "amber":    "#F59E0B",
    "amethyst": "#8B5CF6",
    "emerald":  "#10B981",
    "ruby":     "#EF4444",
    "sapphire": "#3B82F6",
    "steel":    "#6B7280",
}

INK_DISPLAY = {
    "amber":    "Amber",
    "amethyst": "Amethyst",
    "emerald":  "Emerald",
    "ruby":     "Ruby",
    "sapphire": "Sapphire",
    "steel":    "Steel",
}

CARDS_PER_PAGE = 42


def color_dot(color: str, size: int = 10) -> str:
    return (
        f'<span style="display:inline-block;width:{size}px;height:{size}px;'
        f'border-radius:50%;background:{color};'
        f'border:1px solid rgba(0,0,0,0.2);flex-shrink:0;"></span>'
    )


def rarity_badge(rarity: str) -> str:
    color = RARITY_COLORS.get(rarity, "#9CA3AF")
    abbrev = {"Common": "C", "Uncommon": "UC", "Rare": "R",
              "Super Rare": "SR", "Legendary": "L", "Enchanted": "E",
              "Epic": "EP", "Iconic": "IC"}.get(rarity, rarity[:2])
    return (
        f'<span style="display:inline-flex;align-items:center;gap:3px;">'
        f'{color_dot(color, 9)}'
        f'<span style="font-size:7.5pt;color:#374151;">{rarity}</span>'
        f'</span>'
    )


def ink_badge(ink: str) -> str:
    if not ink:
        return ""
    color = INK_COLORS.get(ink.lower(), "#9CA3AF")
    label = INK_DISPLAY.get(ink.lower(), ink.title())
    return (
        f'<span style="display:inline-flex;align-items:center;gap:3px;">'
        f'{color_dot(color, 9)}'
        f'<span style="font-size:7.5pt;color:#374151;">{label}</span>'
        f'</span>'
    )


def render_legend() -> str:
    rarity_items = "".join(
        f'<div style="display:flex;align-items:center;gap:4px;margin:2px 6px 2px 0;">'
        f'{color_dot(color, 10)}'
        f'<span style="font-size:7.5pt;">{name}</span>'
        f'</div>'
        for name, color in RARITY_COLORS.items()
        if name in ("Common", "Uncommon", "Rare", "Super Rare", "Legendary", "Enchanted")
    )
    ink_items = "".join(
        f'<div style="display:flex;align-items:center;gap:4px;margin:2px 6px 2px 0;">'
        f'{color_dot(color, 10)}'
        f'<span style="font-size:7.5pt;">{INK_DISPLAY[name]}</span>'
        f'</div>'
        for name, color in INK_COLORS.items()
    )
    return f"""
    <div style="display:flex;gap:24px;margin:6px 0 10px 0;">
      <div>
        <div style="font-size:7.5pt;font-weight:bold;color:#111;margin-bottom:3px;">Rarity Legend</div>
        <div style="display:flex;flex-wrap:wrap;">{rarity_items}</div>
      </div>
      <div>
        <div style="font-size:7.5pt;font-weight:bold;color:#111;margin-bottom:3px;">Ink Legend</div>
        <div style="display:flex;flex-wrap:wrap;">{ink_items}</div>
      </div>
    </div>"""


def render_header(set_name: str, is_first_page: bool) -> str:
    if is_first_page:
        return f"""
    <div style="margin-bottom:8px;">
      <div style="font-size:16pt;font-weight:bold;color:#111;font-family:Georgia,serif;">
        Disney Lorcana TCG: {set_name}
      </div>
      <div style="font-size:8pt;color:#6B7280;margin-top:2px;">
        Use the check boxes below to keep track of your Lorcana TCG cards!
      </div>
      {render_legend()}
    </div>"""
    else:
        return f"""
    <div style="margin-bottom:8px;">
      <div style="font-size:11pt;font-weight:bold;color:#111;font-family:Georgia,serif;">
        Disney Lorcana TCG: {set_name} <span style="font-weight:normal;font-size:8pt;color:#9CA3AF;">(continued)</span>
      </div>
    </div>"""


def render_card_table(cards: list[dict]) -> str:
    rows = []
    for card in cards:
        num = card.get("number", card.get("#", ""))
        name = card.get("name", "")
        rarity = card.get("rarity", "")
        ink = card.get("ink", "")

        row = (
            f'<tr>'
            f'<td style="width:32px;padding:1.5px 4px;color:#9CA3AF;font-size:7.5pt;white-space:nowrap;">{num}</td>'
            f'<td style="padding:1.5px 6px;font-size:7.5pt;color:#111;">'
            f'<span style="display:inline-flex;align-items:center;gap:5px;">'
            f'<span style="display:inline-block;width:10px;height:10px;border:1px solid #9CA3AF;border-radius:2px;flex-shrink:0;"></span>'
            f'{name}</span></td>'
            f'<td style="padding:1.5px 6px;white-space:nowrap;">{rarity_badge(rarity)}</td>'
            f'<td style="padding:1.5px 4px;white-space:nowrap;">{ink_badge(ink)}</td>'
            f'</tr>'
        )
        rows.append(row)

    return f"""
    <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
      <colgroup>
        <col style="width:36px;">
        <col style="width:auto;">
        <col style="width:95px;">
        <col style="width:80px;">
      </colgroup>
      <thead>
        <tr style="border-bottom:1.5px solid #E5E7EB;">
          <th style="text-align:left;font-size:7pt;color:#9CA3AF;padding:2px 4px;font-weight:600;">#</th>
          <th style="text-align:left;font-size:7pt;color:#9CA3AF;padding:2px 6px;font-weight:600;">Card Name</th>
          <th style="text-align:left;font-size:7pt;color:#9CA3AF;padding:2px 6px;font-weight:600;">Rarity</th>
          <th style="text-align:left;font-size:7pt;color:#9CA3AF;padding:2px 4px;font-weight:600;">Ink</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows)}
      </tbody>
    </table>"""


def render_page(set_name: str, cards: list[dict], page_num: int, total_pages: int) -> str:
    header = render_header(set_name, page_num == 1)
    table = render_card_table(cards)
    footer = (
        f'<div style="margin-top:12px;text-align:right;'
        f'font-size:7pt;color:#9CA3AF;">Page {page_num} of {total_pages}</div>'
    )
    return f"""
  <div class="page">
    {header}
    {table}
    {footer}
  </div>"""


def generate_html(set_name: str, cards: list[dict]) -> str:
    chunks = [cards[i:i+CARDS_PER_PAGE] for i in range(0, len(cards), CARDS_PER_PAGE)]
    total_pages = len(chunks)

    pages_html = "\n".join(
        render_page(set_name, chunk, i + 1, total_pages)
        for i, chunk in enumerate(chunks)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Disney Lorcana TCG: {set_name}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: Arial, Helvetica, sans-serif;
      background: #f0f0f0;
      color: #111;
    }}

    /* Screen preview: simulate printed page with exact margins */
    .page {{
      width: 8.5in;
      min-height: 11in;
      margin: 0.25in auto;
      padding: 0.75in 2.2in 0.75in 0.7in;
      background: #fff;
      box-shadow: 0 2px 12px rgba(0,0,0,0.15);
      page-break-after: always;
      position: relative;
    }}

    .page:last-child {{
      page-break-after: avoid;
    }}

    /* Zebra stripe */
    tbody tr:nth-child(even) td {{
      background: #F9FAFB;
    }}

    @media print {{
      body {{ margin: 0; background: #fff; }}

      .page {{
        width: 100%;
        min-height: auto;
        margin: 0;
        padding: 0;          /* @page handles margins */
        box-shadow: none;
        page-break-after: always;
      }}

      .page:last-child {{
        page-break-after: avoid;
      }}

      tbody tr:nth-child(even) td {{
        background: #F9FAFB !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}

      span[style*="border-radius:50%"] {{
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}
    }}

    @page {{
      size: letter portrait;
      /* Left 0.7" | Right 2.2" | Top 0.75" | Bottom 0.75" */
      margin: 0.75in 2.2in 0.75in 0.7in;
    }}
  </style>
</head>
<body>
{pages_html}
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate printable Lorcana card list HTML")
    parser.add_argument("--cards", help="Path to JSON card list file")
    parser.add_argument("--set-name", help="Display name for the set (e.g. 'Wilds Unknown')")
    parser.add_argument("--out", required=True, help="Output HTML file path")
    args = parser.parse_args()

    if not args.cards:
        print("ERROR: --cards is required", file=sys.stderr)
        sys.exit(1)

    with open(args.cards) as f:
        cards = json.load(f)

    # Derive set name from filename if not provided
    set_name = args.set_name or Path(args.cards).stem.replace("-", " ").title()

    html = generate_html(set_name, cards)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    print(f"✓ Generated {out} ({len(cards)} cards, {-(-len(cards)//CARDS_PER_PAGE)} pages)")
    print(f"  Open in browser and use Ctrl+P to print")


if __name__ == "__main__":
    main()
