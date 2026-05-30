#!/usr/bin/env python3
"""
upload_to_sharepoint.py — Upload an HTML file to the <ORG_NAME> Infrastructure SharePoint docs folder.

Usage:
    python3 scripts/upload_to_sharepoint.py sharepoint/my-guide.html
    python3 scripts/upload_to_sharepoint.py sharepoint/my-guide.html --folder docs/subdirectory
    python3 scripts/upload_to_sharepoint.py sharepoint/my-guide.html --dry-run

Target by default:
    https://<org_short>fg.sharepoint.com/sites/Infrastructure/Files/docs/

Auth:
    Uses az CLI session token (az account get-access-token --resource https://graph.microsoft.com).
    Run `az login` if the token request fails.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_tool, http_fail, GRAPH_COMMON_CAUSES


SITE_HOSTNAME = "<org_short>fg.sharepoint.com"
SITE_PATH = "/sites/Infrastructure"
DRIVE_NAME = "FS - Infrastructure"
DEFAULT_FOLDER = "docs"
SHAREPOINT_BASE = f"https://{SITE_HOSTNAME}{SITE_PATH}"


def ok(msg):  print(f"  ✓ {msg}")
def err(msg): print(f"  ❌ {msg}", file=sys.stderr)
def info(msg):print(f"  → {msg}")


def get_graph_token() -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token",
         "--resource", "https://graph.microsoft.com",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    fail(
        "Could not get Microsoft Graph token via az CLI",
        causes=["az CLI session expired or not authenticated",
                "The active az account lacks the required scope"],
        try_=["az login", "az account show  # confirm you're in the right tenant"],
    )


def http_call(method: str, url: str, token: str, data: bytes = None, accept: str = "application/json", content_type: str = None) -> dict:
    import urllib.request, urllib.error
    headers = {"Authorization": f"Bearer {token}", "Accept": accept}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            body_str = body.decode()
        except Exception:
            body_str = repr(body)
        if e.code == 401 and "invalid_request" in body_str:
            fail(
                "SharePoint returned 401 invalid_request — Conditional Access policy blocked the request",
                causes=["Your IP address is outside the tenant's allowed network range",
                        "The token was acquired from a cloud agent rather than a trusted location"],
                try_=["Run this script from your local machine (WSL or Windows terminal), not from a cloud agent",
                      "Connect to the corporate VPN if required by the CA policy"],
            )
        http_fail(e, api_name="Microsoft Graph / SharePoint", key=url,
                  operation=f"{method} {url}", common_causes=GRAPH_COMMON_CAUSES)


def graph_get(token: str, url: str) -> dict:
    return http_call("GET", token=token, url=url)


def graph_put(token: str, url: str, data: bytes, content_type: str = "text/html") -> dict:
    return http_call("PUT", token=token, url=url, data=data, content_type=content_type)


def get_site_id(token: str) -> str:
    url = f"https://graph.microsoft.com/v1.0/sites/{SITE_HOSTNAME}:{SITE_PATH}"
    info(f"Fetching site ID from {url}")
    data = graph_get(token, url)
    site_id = data["id"]
    ok(f"Site: {data.get('displayName', 'Infrastructure')} ({site_id})")
    return site_id


def get_drive_id(token: str, site_id: str) -> str:
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    info(f"Listing drives to find '{DRIVE_NAME}' library")
    data = graph_get(token, url)
    for drive in data.get("value", []):
        if drive.get("name") == DRIVE_NAME:
            ok(f"Drive: {drive['name']} ({drive['id']})")
            return drive["id"]
    # Fallback: print available drives and fail clearly
    names = [d.get("name") for d in data.get("value", [])]
    fail(
        f"Drive '{DRIVE_NAME}' not found in site {site_id}",
        causes=["The SharePoint document library name changed",
                "The authenticated user does not have access to this library"],
        try_=[f"Available drives: {names}",
              "Verify DRIVE_NAME in upload_to_sharepoint.py matches the SharePoint library name"],
    )


def upload_file(token: str, drive_id: str, folder: str, filename: str, content: bytes) -> str:
    encoded_path = quote(f"{folder}/{filename}", safe="/")
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/content"
    info(f"Uploading to /{folder}/{filename}")
    result = graph_put(token, url, content, content_type="text/html")
    web_url = result.get("webUrl", "")
    ok(f"Uploaded: {web_url}")
    return web_url


def main():
    parser = argparse.ArgumentParser(description="Upload an HTML file to SharePoint Infrastructure/Files/docs")
    parser.add_argument("file", help="Path to the HTML file to upload")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help=f"Target folder inside the Files library (default: {DEFAULT_FOLDER})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without uploading")
    args = parser.parse_args()

    html_path = Path(args.file)
    if not html_path.exists():
        fail(
            f"HTML file not found: {html_path}",
            causes=["Path was mistyped or the file was moved"],
            try_=[f"ls sharepoint/  # list available files"],
        )

    filename = html_path.name
    content = html_path.read_bytes()

    print(f"📄 {filename}  ({len(content):,} bytes)")
    print(f"📁 Target: {SHAREPOINT_BASE}/Files/{args.folder}/{filename}")
    print()

    if args.dry_run:
        print("🔍 Dry run — no upload performed.")
        return

    token = get_graph_token()
    site_id = get_site_id(token)
    drive_id = get_drive_id(token, site_id)
    web_url = upload_file(token, drive_id, args.folder, filename, content)

    print()
    print(f"✅ Published to SharePoint")
    print(f"   {web_url}")
    print()
    print(f"📂 Browse folder:")
    print(f"   https://<org_short>fg.sharepoint.com/sites/Infrastructure/Files/Forms/AllItems.aspx?id=%2Fsites%2FInfrastructure%2FFiles%2Fdocs&viewid=<RESOURCE_GUID>")


if __name__ == "__main__":
    main()
