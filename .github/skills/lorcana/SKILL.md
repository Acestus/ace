---
name: lorcana
description: 'Scrape a Lorcana card list from lorcanaplayer.com and produce a plain-text copy-paste file (names, rarity, ink color) in assets/lorcana/. Use when the user says "scrape lorcana", "generate lorcana list", or gives you a lorcanaplayer.com URL for a new set.'
argument-hint: 'Set name (e.g. wilds-unknown) or full lorcanaplayer.com URL'
---

# Lorcana Skill

Scrape a Lorcana set from lorcanaplayer.com and produce a plain-text file with three copy-paste sections: card names, rarities, and ink colors.

## When to Use

- User says "scrape lorcana", "generate lorcana list", "get set 13"
- User pastes a lorcanaplayer.com URL for a new or unknown set
- User wants a copy-paste-ready text file to paste into Google Sheets

## Workflow

### Step 1 — Resolve the set

**Known sets** (already in `scripts/lorcana_scrape.py`):
```
wilds-unknown   → set 12
winterspell     → set 11
archazia        → set 10
```

If the user gives a URL, pass it with `--url`. If it's a known slug, pass it with `--set`.

**New set (URL provided):**
```bash
python3 scripts/lorcana_scrape.py \
    --url "https://lorcanaplayer.com/<new-set-slug>/" \
    --txt \
    --out "assets/lorcana/<set-slug>-copypaste.txt"
```

**Known set by name:**
```bash
python3 scripts/lorcana_scrape.py \
    --set wilds-unknown \
    --txt \
    --out "assets/lorcana/wilds-unknown-copypaste.txt"
```

### Step 2 — Verify output

```bash
wc -l assets/lorcana/<set-slug>-copypaste.txt
grep "=== " assets/lorcana/<set-slug>-copypaste.txt
```

Expect 3 section headers and 3× the card count in lines (plus 2 blank separators).

### Step 3 — Add new set URL to the scraper (if new)

If the user gave a URL not in `SET_URLS`, add it so it works by name next time:

```python
# in scripts/lorcana_scrape.py — SET_URLS dict
"<set-slug>": "https://lorcanaplayer.com/<full-url>/",
```

### Step 4 — Commit and push

```bash
git add assets/lorcana/<set-slug>-copypaste.txt scripts/lorcana_scrape.py
git commit -m "feat(lorcana): add <Set Name> copy-paste list"
git push ace main
```

## Output Format

The text file has three sections separated by blank lines. Each value is one per line — paste the block directly into a spreadsheet column.

```
=== NAMES ===
Gosalyn Mallard – The Quiverwing Quack
Monterey Jack – Watchful Ranger
...

=== RARITY ===
Common
Common
...

=== INK COLOR ===
Amber
Amber
...
```

## Adding a New Set

When set 13 (or any future set) is released:

1. Find the lorcanaplayer.com card list page URL
2. Run: `python3 scripts/lorcana_scrape.py --url <url> --txt --out assets/lorcana/<slug>-copypaste.txt`
3. Add the slug → URL mapping to `SET_URLS` in `scripts/lorcana_scrape.py`
4. Commit and push

## Files

| File | Purpose |
|------|---------|
| `scripts/lorcana_scrape.py` | Scraper + text formatter. `--txt` flag produces copy-paste output |
| `assets/lorcana/*-copypaste.txt` | Output files, one per set |
| `assets/lorcana/*.pdf` | Print-ready checklists (separate workflow) |

## Notes

- The site uses two-stage AJAX loading — the scraper handles this automatically
- Ink color is parsed from image alt/src tags; text values are `Amber`, `Amethyst`, `Emerald`, `Ruby`, `Sapphire`, `Steel`
- The scraper needs network access (won't work from sandboxed CI)
