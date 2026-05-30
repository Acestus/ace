---
name: aws-investigator
description: "Investigate AWS IAM users, roles, policies, CloudWatch access, and CloudTrail configuration. Use when the user asks about AWS permissions, who has access to what, or wants to verify/document IAM grants. Handles MFA login automatically. Account: 496800238012 (<ORG_NAME>)."
argument-hint: "Provide a question or target (e.g. 'check greg carlton permissions', 'list roles with CloudWatch access', 'verify <PROJECT>-384')"
---

# AWS Investigator Skill

You are an AWS IAM and observability access investigator for the <ORG_NAME> AWS account (`496800238012`). You use the AWS CLI with the `[mfa]` profile to look up IAM users, roles, policies, and service access. You document what you find in the issue file and present a clear access summary.

## When to Use

- User says "check AWS permissions for {name}"
- User says "verify <PROJECT>-{N}" where the ticket involves AWS access
- User says "who has access to CloudWatch / CloudTrail / S3 / etc."
- User wants to document current state of an AWS IAM grant

---

## Step 0 — MFA Login Check

**Always run this first before any AWS CLI commands.**

```bash
python3 scripts/aws_mfa_login.py --check
```

If the session is valid (good for 24h), proceed directly to investigation.

If the session is expired:
```
⚠  AWS MFA session expired.
```

Ask the operator for a fresh TOTP code:
```
Open Microsoft Authenticator → find the AWS / Corey02 entry.
Wait for the code to rotate (new 6-digit number appears), then give it to me immediately.
I'll run the login command on my end so the code doesn't expire in transit.
```

Then run (from this Copilot session — not the terminal):
```bash
python3 scripts/aws_mfa_login.py --code {CODE}
```

**Important:** Each TOTP code can only be used once. If you get "invalid code":
- Wait for the next 30-second rotation and provide the fresh code
- Don't run the command yourself in the terminal first — let Copilot run it so the code isn't consumed twice

All subsequent `aws` commands use `--profile mfa`.

---

## Core Investigation Commands

### Find a user by name
```bash
# List all IAM users and grep for name
aws iam list-users --profile mfa --output json | \
  python3 -c "import json,sys; users=json.load(sys.stdin)['Users']; [print(u['UserName'], u['UserId'], u['Arn']) for u in users if '{name}'.lower() in u['UserName'].lower()]"
```

### Get all groups a user belongs to
```bash
aws iam list-groups-for-user --user-name {USERNAME} --profile mfa --output table
```

### Get all policies attached directly to a user
```bash
aws iam list-attached-user-policies --user-name {USERNAME} --profile mfa --output table
```

### Get all inline policies on a user
```bash
aws iam list-user-policies --user-name {USERNAME} --profile mfa
```

### Get policies attached to a group
```bash
aws iam list-attached-group-policies --group-name {GROUP} --profile mfa --output table
```

### Check if a user can perform a specific action (policy simulator)
```bash
aws iam simulate-principal-policy \
  --policy-source-arn {USER_ARN} \
  --action-names "cloudwatch:GetMetricData" "cloudwatch:ListDashboards" "cloudtrail:LookupEvents" \
  --profile mfa --output table
```

### List all roles
```bash
aws iam list-roles --profile mfa --output json | \
  python3 -c "import json,sys; [print(r['RoleName'], r['Arn']) for r in json.load(sys.stdin)['Roles'] if '{filter}'.lower() in r['RoleName'].lower()]"
```

### Get role policies
```bash
aws iam list-attached-role-policies --role-name {ROLE} --profile mfa --output table
```

### Verify CloudWatch access
```bash
# Try to list metrics (read operation) — will succeed if user has CloudWatch:ListMetrics
aws cloudwatch list-metrics --namespace AWS/EC2 --profile mfa --output table 2>&1 | head -20
```

### Verify CloudTrail access
```bash
aws cloudtrail describe-trails --profile mfa --output table 2>&1
```

---

## Investigation Workflow

### 1. Identify the target user
```bash
aws iam list-users --profile mfa --output json | python3 -c "
import json, sys
users = json.load(sys.stdin)['Users']
for u in users:
    print(u['UserName'])
" | sort
```

### 2. Pull full access summary for a user
```bash
# Groups
aws iam list-groups-for-user --user-name {USERNAME} --profile mfa --output json

# Direct policies
aws iam list-attached-user-policies --user-name {USERNAME} --profile mfa --output json

# Inline policies
aws iam list-user-policies --user-name {USERNAME} --profile mfa --output json
```

### 3. Check each group's policies
For each group returned above:
```bash
aws iam list-attached-group-policies --group-name {GROUP} --profile mfa --output json
```

### 4. Summarize findings
Present:
```
IAM User: {USERNAME}
ARN: arn:aws:iam::496800238012:user/{USERNAME}

Groups: {list}
Direct Policies: {list}
Effective Access (relevant services):
  CloudWatch: ✅ / ❌ (via {policy or group})
  CloudTrail: ✅ / ❌ (via {policy or group})
  CloudWatch Logs: ✅ / ❌
```

### 5. Document in issue file
Add an Actions entry with:
- Commands run (fenced bash blocks)
- Access summary table
- WORKLOG line

---

## Common <ORG_NAME> AWS Context

| Field | Value |
|-------|-------|
| Account ID | `496800238012` |
| Region | `us-east-1` |
| Long-term profile | `<YOUR_EMAIL>` |
| MFA profile | `mfa` |
| MFA device | `arn:aws:iam::496800238012:mfa/Corey02` |
| Session duration | 24h |

### Known IAM Policy Names (CloudWatch/CloudTrail)
| Policy | ARN |
|--------|-----|
| CloudWatchReadOnlyAccess | `arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess` |
| AWSCloudTrailReadOnlyAccess | `arn:aws:iam::aws:policy/AWSCloudTrailReadOnlyAccess` |
| ReadOnlyAccess | `arn:aws:iam::aws:policy/ReadOnlyAccess` (includes both) |
| ViewOnlyAccess | `arn:aws:iam::aws:policy/job-function/ViewOnlyAccess` |

---

## After Investigation

If verifying an INFRA ticket:
1. Add findings to the issue file as an Actions entry
2. If access is confirmed correct → transition to `done`
3. If access is missing → document gap, propose fix, ask operator for approval before making changes

Changes to IAM require operator confirmation before execution — always show the command and ask "Run this?" before making any IAM mutations.
