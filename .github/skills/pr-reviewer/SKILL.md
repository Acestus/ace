---
name: pr-reviewer
description: 'Review GitHub pull requests with an automated checklist. Pulls diff, checks CI, scans for secrets, validates size, and generates findings. Use when the user says "review PR", "check my PRs", "is this PR ready", or wants to run a code review.'
argument-hint: 'Specify a PR number (e.g., 25) and optionally a repo (owner/repo) or Jira key for issue linkage'
---

# PR Reviewer

Use this when you need a fast read on whether a PR is clean enough to approve, comment on, or merge.

`scripts/pr_review.py` does the review. `scripts/gh_pr.py` does the action. Keep them separate.

## When to Use

- User says `review PR 25`
- User asks `is this PR ready`
- User wants a checklist before approving or merging
- User wants to see their open PRs across <GITHUB_ORG>
- User wants stale PR cleanup

## Quick Start

Review a PR in one command:

```bash
cd /home/wweeks/git/projects
python3 scripts/pr_review.py --pr 25
```

Different repo:

```bash
python3 scripts/pr_review.py --pr 25 --repo <GITHUB_ORG>/iac-infra
```

Checklist only:

```bash
python3 scripts/pr_review.py --pr 25 --checklist
```

## Full Workflow

### 1. Run the review

```bash
python3 scripts/pr_review.py --pr 25
```

This checks:

- CI state from `gh pr checks`
- changed files
- sensitive paths like `.env`, `scripts/`, `.github/workflows/`
- secret patterns in the diff
- PR size
- Jira key in the PR body
- README/docs coverage when code changed

### 2. Read the finding, then decide

If the output says the PR is clean, use `gh_pr.py` to act.

**Approve:**

```bash
python3 scripts/gh_pr.py --approve 25 --body "LGTM"
```

**Request changes:**

```bash
python3 scripts/gh_pr.py --request-changes 25 --body "Fix the workflow permissions and add the Jira key."
```

**Comment:**

```bash
python3 scripts/gh_pr.py --comment 25 --body "CI is still pending. I want one green run before merge."
```

**Merge:**

```bash
python3 scripts/gh_pr.py --merge 25 --squash
```

Standard: review first, then act. Don't approve blind.

## Integration with jira-worklog

If the PR maps to a Jira issue, write the findings straight into the issue file:

```bash
python3 scripts/pr_review.py --pr 25 --to-issue <PROJECT>-400
```

That appends a new `PR Review` entry under `## Actions` in the matching issue markdown file and adds a worklog line.

## Stale PR Monitoring

Weekly cleanup:

```bash
python3 scripts/pr_review.py --stale
```

This finds open PRs older than 7 days with no submitted reviews. That's the list to chase.

## Check My Open PRs

```bash
python3 scripts/pr_review.py --my-prs
```

Use this when you want the quick board view across <GITHUB_ORG> repos.

## CLI Reference

### `pr_review.py`

```bash
python3 scripts/pr_review.py --pr NUMBER [--repo OWNER/REPO]
python3 scripts/pr_review.py --pr NUMBER --checklist
python3 scripts/pr_review.py --pr NUMBER --to-issue <PROJECT>-KEY
python3 scripts/pr_review.py --my-prs
python3 scripts/pr_review.py --stale
```

### `gh_pr.py`

```bash
python3 scripts/gh_pr.py --list [--repo OWNER/REPO]
python3 scripts/gh_pr.py --view NUMBER [--repo OWNER/REPO]
python3 scripts/gh_pr.py --checks NUMBER [--repo OWNER/REPO]
python3 scripts/gh_pr.py --diff NUMBER [--repo OWNER/REPO]
python3 scripts/gh_pr.py --approve NUMBER [--body TEXT] [--repo OWNER/REPO]
python3 scripts/gh_pr.py --request-changes NUMBER --body TEXT [--repo OWNER/REPO]
python3 scripts/gh_pr.py --comment NUMBER --body TEXT [--repo OWNER/REPO]
python3 scripts/gh_pr.py --merge NUMBER [--squash] [--repo OWNER/REPO]
```

## Notes

- Repo defaults to `GH_REPO` or the current git remote
- Workflow changes are high-risk. Read them closely.
- Large PRs are review debt. Push back on them.
- If CI is red, don't merge it

---

## Stop the Line

**Hard stops — do NOT approve or merge if:**
- CI is red or has failing checks → "🛑 Stop the line: CI is failing. Fix before merge."
- Secrets detected in diff (API keys, tokens, connection strings) → "🛑 Stop the line: secret in diff. Rotate immediately."
- Workflow permission escalation without justification → "🛑 Stop the line: elevated permissions need explicit justification."

These are not suggestions. If any hard-stop condition is met, the PR is not mergeable regardless of code quality.

## Learning Feedback

After every review (approve or request-changes):
1. If the same issue type was flagged on 3+ recent PRs (e.g., missing Jira key, docs not updated), surface it:
   ```
   📝 Pattern: "Missing Jira link" flagged on 3 of last 5 PRs.
      → Suggest: add branch naming convention or PR template update?
   ```
2. If a PR introduces a pattern worth capturing (new reusable workflow, new auth pattern), flag it for the clerk:
   ```
   💡 New pattern detected: reusable OIDC workflow in _reusable-fabric-cicd-deploy.yaml
      → Worth adding to planner/patterns/cicd.md? (say "pattern" to capture)
   ```
