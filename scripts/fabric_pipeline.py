#!/usr/bin/env python3
"""
fabric_pipeline.py — Microsoft Fabric pipeline and schedule management.

Usage:
    python3 scripts/fabric_pipeline.py --workspace-id ID --list
    python3 scripts/fabric_pipeline.py --workspace-id ID --get-schedule PIPELINE_ID
    python3 scripts/fabric_pipeline.py --workspace-id ID --set-schedule PIPELINE_ID --schedule-file FILE
    python3 scripts/fabric_pipeline.py --workspace-id ID --trigger PIPELINE_ID
    python3 scripts/fabric_pipeline.py --workspace-id ID --run-status PIPELINE_ID --run-id RUN_ID
    python3 scripts/fabric_pipeline.py --workspace-id ID --list-runs PIPELINE_ID
    python3 scripts/fabric_pipeline.py --workspace-id ID --save-schedule PIPELINE_ID --output FILE
    python3 scripts/fabric_pipeline.py --list-workspaces

Environment:
    FABRIC_WORKSPACE_ID  — default workspace ID (overridden by --workspace-id)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, warn, require_tool, http_fail, FABRIC_COMMON_CAUSES


FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value




def success(message: str):
    print(f"✓ {message}")


def get_fabric_token():
    result = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", "https://api.fabric.microsoft.com",
            "--query", "accessToken", "-o", "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    result = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", "https://analysis.windows.net/powerbi/api",
            "--query", "accessToken", "-o", "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    fail(
        "Could not get Fabric access token",
        causes=["Not logged in to Azure CLI",
                "az CLI is not installed"],
        try_=["az login",
              "az account show  # confirm active session",
              "which az || brew install azure-cli"],
    )


def print_table(headers: list[str], rows: list[list[str]]):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    header_line = " | ".join(headers[index].ljust(widths[index]) for index in range(len(headers)))
    divider = "-+-".join("-" * widths[index] for index in range(len(headers)))
    print(header_line)
    print(divider)
    for row in rows:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def parse_json_bytes(payload: bytes):
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def api_request(method: str, path: str, token: str, body=None, resource: str = "resource"):
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{FABRIC_API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers), parse_json_bytes(response.read())
    except urllib.error.HTTPError as exc:
        http_fail(exc, api_name="Fabric", operation=f"{method} {path}",
                  common_causes=FABRIC_COMMON_CAUSES)
    except Exception as exc:
        fail(f"Fabric API request failed: {exc}",
             causes=FABRIC_COMMON_CAUSES.get(0, {}).get("causes", [
                 "Network error or DNS failure",
                 "FABRIC_API_BASE URL is wrong"]),
             try_=["az account show  # confirm az login is active",
                   f"curl -s '{FABRIC_API_BASE}{path}'"])


def workspace_required(args):
    workspace_id = args.workspace_id or os.environ.get("FABRIC_WORKSPACE_ID", "")
    if workspace_id:
        return workspace_id
    fail("--workspace-id required or set FABRIC_WORKSPACE_ID in .env",
         causes=["FABRIC_WORKSPACE_ID not in environment"],
         try_=["export FABRIC_WORKSPACE_ID=<guid>",
               "grep FABRIC_WORKSPACE_ID .env"])


def list_pipelines(workspace_id: str, token: str):
    _, _, data = api_request("GET", f"/workspaces/{workspace_id}/dataPipelines", token, resource="dataPipelines")
    rows = []
    for item in data.get("value", []):
        rows.append([
            str(item.get("id", "—")),
            str(item.get("displayName", item.get("name", "—"))),
            str(item.get("description", "")),
        ])
    if not rows:
        warn("No pipelines found")
        return 0
    print_table(["PIPELINE_ID", "NAME", "DESCRIPTION"], rows)
    return 0


def extract_schedule_from_pipeline(data: dict):
    if not isinstance(data, dict):
        return None
    if data.get("schedule"):
        return data["schedule"]
    properties = data.get("properties", {})
    if isinstance(properties, dict) and properties.get("schedule"):
        return properties["schedule"]
    activities = properties.get("activities", [])
    for activity in activities:
        if isinstance(activity, dict) and activity.get("schedule"):
            return activity["schedule"]
        activity_properties = activity.get("properties", {}) if isinstance(activity, dict) else {}
        if isinstance(activity_properties, dict) and activity_properties.get("schedule"):
            return activity_properties["schedule"]
    return None


def get_schedule_resource(workspace_id: str, pipeline_id: str, token: str, allow_missing: bool = False):
    path = f"/workspaces/{workspace_id}/items/{pipeline_id}/schedules"
    request = urllib.request.Request(
        f"{FABRIC_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers), parse_json_bytes(response.read())
    except urllib.error.HTTPError as exc:
        if allow_missing and exc.code == 404:
            return 404, {}, {}
        http_fail(exc, api_name="Fabric", operation=f"GET {path}",
                  common_causes=FABRIC_COMMON_CAUSES)
    except Exception as exc:
        fail(f"Fabric API request failed: {exc}",
             causes=["Network error or DNS failure"],
             try_=["az account show  # confirm az login is active"])


def resolve_schedule(workspace_id: str, pipeline_id: str, token: str):
    _, _, pipeline = api_request(
        "GET",
        f"/workspaces/{workspace_id}/dataPipelines/{pipeline_id}",
        token,
        resource=f"pipeline {pipeline_id}",
    )
    direct_schedule = extract_schedule_from_pipeline(pipeline)
    if direct_schedule:
        return direct_schedule
    status, _, schedules = get_schedule_resource(workspace_id, pipeline_id, token, allow_missing=True)
    if status != 404 and schedules:
        return schedules
    return None


def get_schedule(workspace_id: str, pipeline_id: str, token: str):
    schedule = resolve_schedule(workspace_id, pipeline_id, token)
    if schedule is None:
        warn("No schedule configured on this pipeline")
        return 0
    print(json.dumps(schedule, indent=2))
    return 0


def save_schedule(workspace_id: str, pipeline_id: str, output_file: str, token: str):
    schedule = resolve_schedule(workspace_id, pipeline_id, token)
    if schedule is None:
        warn("No schedule configured on this pipeline")
        return 0
    output_path = Path(output_file)
    output_path.write_text(json.dumps(schedule, indent=2) + "\n")
    success(f"Schedule saved to {output_path}")
    return 0


def normalize_schedule_payload(payload):
    if isinstance(payload, dict) and isinstance(payload.get("value"), list):
        values = payload["value"]
        if len(values) == 1:
            return values[0]
    return payload


def set_schedule(workspace_id: str, pipeline_id: str, schedule_file: str, token: str):
    schedule_path = Path(schedule_file)
    payload = normalize_schedule_payload(json.loads(schedule_path.read_text()))
    status, _, existing = get_schedule_resource(workspace_id, pipeline_id, token, allow_missing=True)
    schedules = []
    if status != 404:
        if isinstance(existing, dict) and isinstance(existing.get("value"), list):
            schedules = existing["value"]
        elif isinstance(existing, list):
            schedules = existing
    if schedules and isinstance(schedules[0], dict) and schedules[0].get("id"):
        schedule_id = schedules[0]["id"]
        api_request(
            "PATCH",
            f"/workspaces/{workspace_id}/items/{pipeline_id}/schedules/{schedule_id}",
            token,
            body=payload,
            resource=f"schedule {schedule_id}",
        )
    else:
        api_request(
            "POST",
            f"/workspaces/{workspace_id}/items/{pipeline_id}/schedules",
            token,
            body=payload,
            resource=f"pipeline {pipeline_id} schedules",
        )
    success("Schedule applied")
    return 0


def trigger_pipeline(workspace_id: str, pipeline_id: str, token: str):
    status, headers, data = api_request(
        "POST",
        f"/workspaces/{workspace_id}/dataPipelines/{pipeline_id}/jobs/instances?jobType=Pipeline",
        token,
        body={},
        resource=f"pipeline {pipeline_id} trigger",
    )
    location = headers.get("Location", "") or headers.get("location", "")
    run_id = str(data.get("id", "")) if isinstance(data, dict) else ""
    if not run_id and location:
        match = re.search(r"/jobs/instances/([^/?]+)", location)
        if match:
            run_id = match.group(1)
    if status == 202 and run_id:
        success(f"Pipeline triggered — run ID: {run_id}")
        return 0
    if run_id:
        success(f"Pipeline triggered — run ID: {run_id}")
        return 0
    warn("Pipeline triggered but run ID was not returned")
    return 0


def first_value(data: dict, paths: list[tuple[str, ...]]):
    for path in paths:
        current = data
        found = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current[key]
        if found and current not in (None, ""):
            return current
    return "—"


def run_status(workspace_id: str, pipeline_id: str, run_id: str, token: str):
    _, _, data = api_request(
        "GET",
        f"/workspaces/{workspace_id}/dataPipelines/{pipeline_id}/jobs/instances/{run_id}",
        token,
        resource=f"run {run_id}",
    )
    status_value = first_value(data, [("status",), ("properties", "status")])
    start_time = first_value(data, [("startTimeUtc",), ("startTime",), ("properties", "startTime")])
    end_time = first_value(data, [("endTimeUtc",), ("endTime",), ("properties", "endTime")])
    duration = first_value(data, [("duration",), ("durationInMs",), ("properties", "duration")])
    error_message = first_value(
        data,
        [
            ("error", "message"),
            ("properties", "error", "message"),
            ("failureReason",),
        ],
    )
    print(f"RUN ID: {run_id}")
    print(f"STATUS: {status_value}")
    print(f"START: {start_time}")
    print(f"END: {end_time}")
    print(f"DURATION: {duration}")
    if str(status_value).lower() == "failed" or error_message != "—":
        print(f"ERROR: {error_message}")
    return 0


def list_runs(workspace_id: str, pipeline_id: str, token: str):
    _, _, data = api_request(
        "GET",
        f"/workspaces/{workspace_id}/dataPipelines/{pipeline_id}/jobs/instances?jobType=Pipeline",
        token,
        resource=f"pipeline {pipeline_id} runs",
    )
    rows = []
    for item in data.get("value", [])[:10]:
        rows.append([
            str(first_value(item, [("id",)])),
            str(first_value(item, [("status",), ("properties", "status")])),
            str(first_value(item, [("startTimeUtc",), ("startTime",), ("properties", "startTime")])),
            str(first_value(item, [("duration",), ("durationInMs",), ("properties", "duration")])),
        ])
    if not rows:
        warn("No runs found")
        return 0
    print_table(["RUN_ID", "STATUS", "START", "DURATION"], rows)
    return 0


def list_workspaces(token: str):
    _, _, data = api_request("GET", "/workspaces", token, resource="workspaces")
    rows = []
    for item in data.get("value", []):
        rows.append([
            str(item.get("id", "—")),
            str(item.get("displayName", item.get("name", "—"))),
            str(item.get("type", "—")),
            str(item.get("capacityId", "—")),
        ])
    if not rows:
        warn("No workspaces found")
        return 0
    print_table(["WORKSPACE_ID", "NAME", "TYPE", "CAPACITY_ID"], rows)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Microsoft Fabric pipeline helper")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--list", action="store_true", help="List pipelines in a workspace")
    actions.add_argument("--get-schedule", metavar="PIPELINE_ID", help="Get pipeline schedule")
    actions.add_argument("--set-schedule", metavar="PIPELINE_ID", help="Set pipeline schedule")
    actions.add_argument("--trigger", metavar="PIPELINE_ID", help="Trigger a pipeline run")
    actions.add_argument("--run-status", metavar="PIPELINE_ID", help="Get run status for a pipeline")
    actions.add_argument("--list-runs", metavar="PIPELINE_ID", help="List recent pipeline runs")
    actions.add_argument("--save-schedule", metavar="PIPELINE_ID", help="Save pipeline schedule to a file")
    actions.add_argument("--list-workspaces", action="store_true", help="List Fabric workspaces")
    parser.add_argument("--workspace-id", default=os.environ.get("FABRIC_WORKSPACE_ID", ""), help="Fabric workspace ID")
    parser.add_argument("--schedule-file", help="Schedule JSON file")
    parser.add_argument("--run-id", help="Pipeline run ID")
    parser.add_argument("--output", help="Output file for saved schedule")
    return parser


def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()

    if args.list_workspaces:
        token = get_fabric_token()
        return list_workspaces(token)

    workspace_id = workspace_required(args)
    token = get_fabric_token()

    if args.list:
        return list_pipelines(workspace_id, token)
    if args.get_schedule:
        return get_schedule(workspace_id, args.get_schedule, token)
    if args.save_schedule:
        if not args.output:
            fail("--save-schedule requires --output FILE")
        return save_schedule(workspace_id, args.save_schedule, args.output, token)
    if args.set_schedule:
        if not args.schedule_file:
            fail("--set-schedule requires --schedule-file FILE")
        return set_schedule(workspace_id, args.set_schedule, args.schedule_file, token)
    if args.trigger:
        return trigger_pipeline(workspace_id, args.trigger, token)
    if args.run_status:
        if not args.run_id:
            fail("--run-status requires --run-id RUN_ID")
        return run_status(workspace_id, args.run_status, args.run_id, token)
    if args.list_runs:
        return list_runs(workspace_id, args.list_runs, token)
    fail("No action selected")


if __name__ == "__main__":
    sys.exit(main())
