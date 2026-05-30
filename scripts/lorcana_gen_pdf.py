#!/usr/bin/env python3
"""
lorcana_gen_pdf.py — Generate a pixel-perfect printable PDF card checklist
                     matching the Disney Lorcana TCG card tracker layout.

Measurements derived from the reference PDF (Winterspell set):
  - Page: 8.5" x 11" (612pt x 792pt)
  - Left content edge: 70.38pt (0.977")
  - Card name column: 164.40pt (2.283")
  - Rarity column: 291.09pt (4.043")
  - Row spacing: 10.56pt
  - Page 2+ top margin: 204.39pt (2.839")
  - Bottom margin: ~71pt (0.984")

Usage:
    python3 scripts/lorcana_gen_pdf.py --cards /tmp/cards.json \\
            --set-name "Wilds Unknown" --out assets/lorcana/wilds-unknown.pdf
"""

import argparse
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

# ── Page geometry (matched to reference PDF) ─────────────────────────────────
PAGE_W, PAGE_H = letter          # 612 x 792 pt
LEFT_EDGE   = 70.38              # x where card # starts
NAME_X      = 164.40             # x where name starts
RARITY_X    = 291.09             # x where rarity starts
INK_X       = 390.0              # x where ink starts (we add this column)
RIGHT_EDGE  = 490.0              # right edge of content
ROW_H       = 10.56              # row height (pt)
TOP_MARGIN  = 204.39             # top margin on pages 2+ (pt from top)
BOT_MARGIN  = 71.0               # bottom margin (pt from bottom)

# Content area height on non-first pages
CONTENT_H_P2 = PAGE_H - TOP_MARGIN - BOT_MARGIN  # ~516pt ≈ 49 rows

# ── Colors ───────────────────────────────────────────────────────────────────
RARITY_COLORS = {
    "Common":     colors.HexColor("#9CA3AF"),
    "Uncommon":   colors.HexColor("#34D399"),
    "Rare":       colors.HexColor("#60A5FA"),
    "Super Rare": colors.HexColor("#A78BFA"),
    "Legendary":  colors.HexColor("#FBBF24"),
    "Enchanted":  colors.HexColor("#F472B6"),
    "Epic":       colors.HexColor("#FB923C"),
    "Iconic":     colors.HexColor("#C084FC"),
}

INK_COLORS = {
    "amber":    colors.HexColor("#F59E0B"),
    "amethyst": colors.HexColor("#8B5CF6"),
    "emerald":  colors.HexColor("#10B981"),
    "ruby":     colors.HexColor("#EF4444"),
    "sapphire": colors.HexColor("#3B82F6"),
    "steel":    colors.HexColor("#6B7280"),
}

GRAY_TEXT  = colors.HexColor("#6B7280")
LIGHT_GRAY = colors.HexColor("#F9FAFB")
BLACK      = colors.black
DIVIDER    = colors.HexColor("#E5E7EB")


def draw_dot(c: rl_canvas.Canvas, x: float, y: float, color, r: float = 3.5):
    """Draw a filled circle centered at (x, y) in PDF coords."""
    c.setFillColor(color)
    c.circle(x, y, r, stroke=0, fill=1)
    c.setFillColor(BLACK)


def draw_rarity_row(c, x, y, rarity: str):
    """Draw colored dot + rarity label at (x, y)."""
    color = RARITY_COLORS.get(rarity, GRAY_TEXT)
    dot_y = y + ROW_H * 0.35
    draw_dot(c, x + 4, dot_y, color)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawString(x + 10, y + 1, rarity)
    c.setFillColor(BLACK)


def draw_ink_row(c, x, y, ink: str):
    """Draw colored dot + ink label at (x, y)."""
    if not ink:
        return
    color = INK_COLORS.get(ink.lower(), GRAY_TEXT)
    dot_y = y + ROW_H * 0.35
    draw_dot(c, x + 4, dot_y, color)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawString(x + 10, y + 1, ink.title())
    c.setFillColor(BLACK)


def draw_column_headers(c, y):
    """Draw # | Card Name | Rarity | Ink column headers."""
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(GRAY_TEXT)
    c.drawString(LEFT_EDGE, y, "#")
    c.drawString(NAME_X + 14, y, "Card Name")
    c.drawString(RARITY_X, y, "Rarity")
    c.drawString(INK_X, y, "Ink")
    # Divider line below headers
    c.setStrokeColor(DIVIDER)
    c.setLineWidth(0.75)
    c.line(LEFT_EDGE, y - 2, RIGHT_EDGE, y - 2)
    c.setFillColor(BLACK)


def draw_card_row(c, card: dict, y: float, striped: bool):
    """Draw one card row at the given y (bottom of row in PDF coords)."""
    if striped:
        c.setFillColor(LIGHT_GRAY)
        c.rect(LEFT_EDGE - 2, y - 1, RIGHT_EDGE - LEFT_EDGE + 4, ROW_H + 1,
               stroke=0, fill=1)
        c.setFillColor(BLACK)

    num    = str(card.get("number", card.get("#", "")))
    name   = card.get("name", "")
    rarity = card.get("rarity", "")
    ink    = card.get("ink", "")

    text_y = y + 2   # baseline

    # Card number
    c.setFont("Helvetica", 7)
    c.setFillColor(GRAY_TEXT)
    c.drawRightString(LEFT_EDGE + 22, text_y, num)
    c.setFillColor(BLACK)

    # Checkbox square
    box_x = LEFT_EDGE + 26
    box_y = y + 1.5
    c.setStrokeColor(colors.HexColor("#9CA3AF"))
    c.setLineWidth(0.5)
    c.rect(box_x, box_y, 7, 7, stroke=1, fill=0)
    c.setStrokeColor(BLACK)

    # Card name (clip to rarity column)
    c.setFont("Helvetica", 7)
    c.setFillColor(BLACK)
    # Truncate name if too long
    max_name_w = RARITY_X - NAME_X - 8
    while c.stringWidth(name, "Helvetica", 7) > max_name_w and len(name) > 4:
        name = name[:-2] + "…"
    c.drawString(NAME_X + 14, text_y, name)

    # Rarity dot + label
    draw_rarity_row(c, RARITY_X, y, rarity)

    # Ink dot + label
    draw_ink_row(c, INK_X, y, ink)


def draw_legend(c, x: float, y: float):
    """Draw rarity + ink legend. Returns new y after legend."""
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(BLACK)
    c.drawString(x, y, "Rarity Legend")

    col = x
    row_y = y - 11
    for i, (name, color) in enumerate(RARITY_COLORS.items()):
        if name not in ("Common","Uncommon","Rare","Super Rare","Legendary","Enchanted"):
            continue
        draw_dot(c, col + 4, row_y + 3, color, r=3.5)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.HexColor("#374151"))
        label_w = c.stringWidth(name, "Helvetica", 6.5)
        c.drawString(col + 10, row_y, name)
        col += label_w + 22
        if col > x + 200:
            col = x
            row_y -= 11

    ink_x = x + 230
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(BLACK)
    c.drawString(ink_x, y, "Ink Legend")

    col2 = ink_x
    ink_y = y - 11
    for name, color in INK_COLORS.items():
        draw_dot(c, col2 + 4, ink_y + 3, color, r=3.5)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.HexColor("#374151"))
        label = name.title()
        label_w = c.stringWidth(label, "Helvetica", 6.5)
        c.drawString(col2 + 10, ink_y, label)
        col2 += label_w + 18
        if col2 > ink_x + 180:
            col2 = ink_x
            ink_y -= 11

    return min(row_y, ink_y) - 6


def draw_page_number(c, page_num: int, total: int):
    c.setFont("Helvetica", 6)
    c.setFillColor(GRAY_TEXT)
    c.drawRightString(RIGHT_EDGE, BOT_MARGIN - 12, f"Page {page_num} of {total}")
    c.setFillColor(BLACK)


def generate_pdf(set_name: str, cards: list[dict], out_path: str):
    c = rl_canvas.Canvas(out_path, pagesize=letter)
    c.setTitle(f"Disney Lorcana TCG: {set_name}")

    # ── Paginate cards ────────────────────────────────────────────────────────
    # Page 1: header takes space, fewer cards fit
    # Pages 2+: full content height

    # First pass — figure out how many cards fit per page
    HEADER_H = 80          # approximate height of title + legend on page 1
    HDR_ROW_H = ROW_H + 1  # row height with 1pt gap

    def cards_for_page(is_first: bool) -> int:
        avail = PAGE_H - TOP_MARGIN - BOT_MARGIN
        if is_first:
            avail -= HEADER_H + 20   # subtract header
        return int(avail / HDR_ROW_H)

    pages: list[list[dict]] = []
    remaining = list(cards)
    while remaining:
        per = cards_for_page(len(pages) == 0)
        pages.append(remaining[:per])
        remaining = remaining[per:]

    total_pages = len(pages)

    for page_idx, page_cards in enumerate(pages):
        is_first = page_idx == 0

        # ── Y cursor (PDF coords: 0 = bottom, PAGE_H = top) ─────────────────
        y = PAGE_H - TOP_MARGIN   # top of content area

        if is_first:
            # Title
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(BLACK)
            c.drawString(LEFT_EDGE, y, f"Disney Lorcana TCG: {set_name}")
            y -= 14

            c.setFont("Helvetica", 7)
            c.setFillColor(GRAY_TEXT)
            c.drawString(LEFT_EDGE, y, "Use the check boxes below to keep track of your Lorcana TCG cards!")
            y -= 16

            # Legend
            y = draw_legend(c, LEFT_EDGE, y)
            y -= 10

        # Column headers
        draw_column_headers(c, y)
        y -= ROW_H + 3

        # Card rows
        for i, card in enumerate(page_cards):
            draw_card_row(c, card, y, striped=(i % 2 == 1))
            y -= HDR_ROW_H

        draw_page_number(c, page_idx + 1, total_pages)
        c.showPage()

    c.save()
    print(f"✓ Generated {out_path} ({len(cards)} cards, {total_pages} pages)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, help="JSON card list file")
    parser.add_argument("--set-name", required=True, help="Set display name")
    parser.add_argument("--out", required=True, help="Output PDF path")
    args = parser.parse_args()

    with open(args.cards) as f:
        cards = json.load(f)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    generate_pdf(args.set_name, cards, args.out)


if __name__ == "__main__":
    main()
