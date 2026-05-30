#!/usr/bin/env python3
"""
linear_create_project.py — Create or reuse a Linear project.

Usage:
    python3 scripts/linear_create_project.py --team ACE --name "Make $50"
    python3 scripts/linear_create_project.py --team ACE --name "Make $50" \
        --description "Track the goal to earn $50."

Environment (reads from .env):
    LINEAR_API_KEY
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file

TEAM_QUERY = """
query GetTeam($key: String!) {
  teams(filter: { key: { eq: $key } }) {
    nodes {
      id
      key
      name
    }
  }
}
"""

PROJECTS_QUERY = """
query GetProjects($name: String!) {
  projects(filter: { name: { eq: $name } }) {
    nodes {
      id
      name
      url
      description
      teams { nodes { key name } }
    }
  }
}
"""

CREATE_MUTATION = """
mutation CreateProject($input: ProjectCreateInput!) {
  projectCreate(input: $input) {
    success
    project {
      id
      name
      url
      description
      teams { nodes { key name } }
    }
  }
}
"""


def find_project(projects: list[dict], team_key: str) -> dict | None:
    team_key = team_key.upper()
    for project in projects:
        teams = (project.get("teams") or {}).get("nodes", [])
        if any((team.get("key") or "").upper() == team_key for team in teams):
            return project
    return None


def main() -> None:
    load_env_file()
    parser = argparse.ArgumentParser(description="Create or reuse a Linear project")
    parser.add_argument("--team", required=True, help="Team key, e.g. ACE")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--description", default="", help="Project description")
    parser.add_argument("--icon", default="", help="Optional project icon")
    parser.add_argument("--color", default="", help="Optional project color")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    team_data = graphql(TEAM_QUERY, {"key": args.team.upper()})
    teams = team_data.get("teams", {}).get("nodes", [])
    if not teams:
        sys.exit(f"Team '{args.team}' not found.")
    team = teams[0]

    projects_data = graphql(PROJECTS_QUERY, {"name": args.name})
    project = find_project(projects_data.get("projects", {}).get("nodes", []), team["key"])
    if project:
        if args.json:
            print(json.dumps({"created": False, "project": project}, indent=2))
        else:
            print(f"✓ Project exists: {project['name']}")
            print(f"  URL: {project.get('url', 'N/A')}")
        return

    input_data = {
        "teamIds": [team["id"]],
        "name": args.name,
    }
    if args.description:
        input_data["description"] = args.description
    if args.icon:
        input_data["icon"] = args.icon
    if args.color:
        input_data["color"] = args.color

    result = graphql(CREATE_MUTATION, {"input": input_data})
    payload = result.get("projectCreate", {})
    if not payload.get("success"):
        sys.exit("Failed to create project.")

    project = payload["project"]
    if args.json:
        print(json.dumps({"created": True, "project": project}, indent=2))
        return

    print(f"✓ Created project: {project['name']}")
    print(f"  URL: {project.get('url', 'N/A')}")


if __name__ == "__main__":
    main()
