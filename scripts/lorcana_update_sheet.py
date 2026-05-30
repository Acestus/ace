#!/usr/bin/env python3
"""
lorcana_update_sheet.py — Update a Google Sheet tab with Lorcana card data.

Auth: OAuth 2.0 desktop app flow. First run opens a browser; token is cached
at ~/.config/ace/google_token.json for subsequent runs.

Usage:
    python3 scripts/lorcana_update_sheet.py \
        --sheet-id 16ykFi413edBFxDRG__0rrBqfHOXYGFgt3p3PD0hq704 \
        --tab "Wilds Unknown" \
        --cards /tmp/cards.json

    # Or pipe cards from the scraper:
    python3 scripts/lorcana_scrape.py --set wilds-unknown | \
        python3 scripts/lorcana_update_sheet.py --tab "Wilds Unknown"
"""

import argparse
import json
import sys
from pathlib import Path

import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN_PATH = Path.home() / ".config" / "ace" / "google_token.json"
CLIENT_SECRET_PATH = Path(__file__).parent.parent / ".secrets" / "google-oauth-client.json"

DEFAULT_SHEET_ID = "16ykFi413edBFxDRG__0rrBqfHOXYGFgt3p3PD0hq704"
DEFAULT_TAB_GID   = 1602086961

HEADERS = ["#", "Name", "Type", "Ink", "Rarity"]


def get_credentials() -> Credentials:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                print(
                    f"ERROR: OAuth client secret not found at {CLIENT_SECRET_PATH}",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0, open_browser=False)

        TOKEN_PATH.write_text(creds.to_json())
        print(f"  ✓ Token saved to {TOKEN_PATH}", file=sys.stderr)

    return creds


def load_cards(cards_file: str | None) -> list[dict]:
    if cards_file:
        with open(cards_file) as f:
            return json.load(f)
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    print("ERROR: provide --cards or pipe JSON from lorcana_scrape.py", file=sys.stderr)
    sys.exit(1)


def find_worksheet(spreadsheet, tab_name: str | None, tab_gid: int | None):
    """Find worksheet by GID first (most reliable), fall back to name."""
    if tab_gid is not None:
        for ws in spreadsheet.worksheets():
            if ws.id == tab_gid:
                print(f"  Found tab by GID {tab_gid}: '{ws.title}'", file=sys.stderr)
                return ws

    if tab_name:
        try:
            ws = spreadsheet.worksheet(tab_name)
            print(f"  Found tab by name: '{tab_name}'", file=sys.stderr)
            return ws
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=tab_name, rows=300, cols=10)
            print(f"  Created new tab: '{tab_name}'", file=sys.stderr)
            return ws

    print("ERROR: tab not found", file=sys.stderr)
    sys.exit(1)


def update_sheet(sheet_id: str, tab_name: str | None, tab_gid: int | None, cards: list[dict]) -> None:
    creds = get_credentials()
    gc = gspread.authorize(creds)

    print(f"  Opening sheet {sheet_id}...", file=sys.stderr)
    spreadsheet = gc.open_by_key(sheet_id)
    ws = find_worksheet(spreadsheet, tab_name, tab_gid)

    rows = [HEADERS]
    for card in sorted(cards, key=lambda c: c["number"]):
        rows.append([
            card["number"],
            card["name"],
            card["type"],
            card["ink"],
            card["rarity"],
        ])

    ws.clear()
    ws.update("A1", rows)
    ws.format("A1:E1", {"textFormat": {"bold": True}})

    spreadsheet.batch_update({
        "requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        }]
    })

    print(f"  ✓ Wrote {len(cards)} cards to '{ws.title}'", file=sys.stderr)
    print(f"  URL: https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={ws.id}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-id", default=DEFAULT_SHEET_ID)
    parser.add_argument("--tab", help="Tab name (optional if --gid provided)")
    parser.add_argument("--gid", type=int, default=DEFAULT_TAB_GID, help="Tab GID")
    parser.add_argument("--cards", help="Path to cards JSON file")
    args = parser.parse_args()

    cards = load_cards(args.cards)
    print(f"  Loaded {len(cards)} cards", file=sys.stderr)
    update_sheet(args.sheet_id, args.tab, args.gid, cards)


if __name__ == "__main__":
    main()
