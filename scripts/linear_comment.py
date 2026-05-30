#!/usr/bin/env python3
"""
linear_comment.py — Add a comment to a Linear issue.

Usage:
    python3 scripts/linear_comment.py --key ENG-123 --body "Investigated root cause..."
    python3 scripts/linear_comment.py --key ENG-123 --file /tmp/comment.md

Environment (reads from .env):
    LINEAR_API_KEY
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file

ISSUE_ID_QUERY = """
query GetIssueId($identifier: String!) {
  issues(filter: { identifier: { eq: $identifier } }) {
    nodes { id identifier }
  }
}
"""

COMMENT_MUTATION = """
mutation AddComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
    comment { id createdAt }
  }
}
"""


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Add a comment to a Linear issue")
    parser.add_argument("--key", required=True, help="Issue identifier, e.g. ENG-123")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--body", help="Comment body text (markdown)")
    group.add_argument("--file", help="Path to file containing comment body")
    args = parser.parse_args()

    body = args.body
    if args.file:
        body = Path(args.file).read_text()

    data = graphql(ISSUE_ID_QUERY, {"identifier": args.key.upper()})
    nodes = data.get("issues", {}).get("nodes", [])
    if not nodes:
        sys.exit(f"Issue {args.key} not found.")

    issue_id = nodes[0]["id"]
    result = graphql(COMMENT_MUTATION, {"issueId": issue_id, "body": body})
    cr = result.get("commentCreate", {})
    if cr.get("success"):
        print(f"✓ Comment added to {args.key}")
    else:
        sys.exit(f"Failed to add comment to {args.key}")


if __name__ == "__main__":
    main()
