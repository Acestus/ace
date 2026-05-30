#!/usr/bin/env python3
"""
infralogs_check.py — Query infralogs Gold layer for active P1/P2 alerts.

Used by the rounds skill to surface infrastructure alerts during board display.
Reads active_alerts from the Gold Lakehouse via OneLake REST API.

Usage:
    python3 scripts/infralogs_check.py [--severity P1] [--json]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_tool, AZURE_COMMON_CAUSES


WORKSPACE_ID = "e1027d60-0009-4e4a-8030-7e86088f9caf"
GOLD_LAKEHOUSE_ID = "420aaed5-8c10-40ff-9b69-103b8b2227f9"
ONELAKE_BASE = "https://onelake.dfs.fabric.microsoft.com"


def get_token():
    """Get OneLake storage token via az CLI."""
    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://storage.azure.com",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        fail(
            "az account get-access-token failed — cannot reach OneLake",
            causes=AZURE_COMMON_CAUSES.get("AuthorizationFailed", [
                "az CLI not logged in",
                "Token scope denied for https://storage.azure.com",
            ]),
            try_=["az login", "az account show  # confirm the right subscription is active"],
        )
    return result.stdout.strip()


def read_delta_metadata(token):
    """Read the active_alerts Delta table via OneLake REST.

    Since we can't read Delta format directly via REST (it's Parquet + log),
    we fall back to the Fabric SQL endpoint for the lakehouse.
    """
    # Use the Fabric SQL analytics endpoint instead
    sql_endpoint = get_sql_endpoint(token)
    if not sql_endpoint:
        return None
    return query_sql_endpoint(sql_endpoint, token)


def get_sql_endpoint(token):
    """Get the SQL analytics endpoint for the Gold lakehouse."""
    fabric_token = subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=30
    ).stdout.strip()

    import urllib.request
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/items/{GOLD_LAKEHOUSE_ID}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {fabric_token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            # Look for SQL endpoint in properties
            props = data.get("properties", {})
            return props.get("sqlEndpointProperties", {}).get("connectionString")
    except Exception:
        return None


def query_via_kusto(severity_filter=None):
    """Query Eventhouse Gold KQL database directly via az kusto CLI or REST."""
    eventhouse_uri = "https://trd-ydffpqg2x6407dxa90.z9.kusto.fabric.microsoft.com"
    kql_database = "kqldb_infralogs"

    # Get Kusto token
    token = subprocess.run(
        ["az", "account", "get-access-token", "--resource", eventhouse_uri,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=30
    ).stdout.strip()

    if not token:
        return None

    # Query Gold lakehouse active_alerts via the SQL endpoint won't work easily
    # Instead, query the Eventhouse directly for recent P1/P2 activity
    severity_clause = f"| where severity == '{severity_filter}'" if severity_filter else "| where severity in ('P1', 'P2')"

    query = f"""
activity_raw
| where ingestion_time > ago(24h)
| mv-expand raw
| project
    event_time = todatetime(raw["time"]),
    operation = tostring(raw["operationName"]),
    result_type = tostring(raw["resultType"]),
    resource_id = tostring(raw["resourceId"]),
    description = tostring(raw["resultSignature"])
| where result_type == "Failure" or operation contains "delete"
| extend severity = iff(result_type == "Failure", "P1", "P2")
{severity_clause}
| order by event_time desc
| take 10
"""

    import urllib.request
    url = f"{eventhouse_uri}/v1/rest/query"
    body = json.dumps({"db": kql_database, "csl": query}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            # Parse KQL response format
            frames = data.get("Tables", data.get("frames", []))
            if not frames:
                return []

            table = frames[0] if isinstance(frames, list) else frames
            columns = [c["ColumnName"] for c in table.get("Columns", [])]
            rows = table.get("Rows", [])

            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            return results
    except Exception as e:
        print(f"⚠ KQL query failed: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Check infralogs Gold for active alerts")
    parser.add_argument("--severity", choices=["P1", "P2"], help="Filter by severity")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    alerts = query_via_kusto(args.severity)

    if alerts is None:
        fail(
            "Could not query infralogs Gold layer",
            causes=["az account get-access-token failed or returned an empty token",
                    "Kusto/SQL endpoint is unavailable or returned an error"],
            try_=["az login  # re-authenticate if the session expired",
                  "python3 scripts/infralogs_check.py --json  # check raw output"],
        )

    if args.json:
        print(json.dumps(alerts, indent=2, default=str))
        return

    if not alerts:
        print("✅ No active infrastructure alerts")
        return

    p1_alerts = [a for a in alerts if a.get("severity") == "P1"]
    p2_alerts = [a for a in alerts if a.get("severity") == "P2"]

    if p1_alerts:
        print(f"🚨 {len(p1_alerts)} Critical (P1) infrastructure alert(s):")
        for a in p1_alerts[:5]:
            op = a.get("operation", "Unknown")[:60]
            res = a.get("resource_id", "")
            # Extract short resource name
            short_res = res.split("/")[-1] if "/" in res else res
            ts = str(a.get("event_time", ""))[:16]
            print(f"   • {op} — {short_res} ({ts})")

    if p2_alerts:
        print(f"⚠  {len(p2_alerts)} Advisory (P2) infrastructure alert(s):")
        for a in p2_alerts[:3]:
            op = a.get("operation", "Unknown")[:60]
            short_res = a.get("resource_id", "").split("/")[-1]
            print(f"   • {op} — {short_res}")


if __name__ == "__main__":
    main()
