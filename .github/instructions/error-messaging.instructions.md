---
applyTo: "scripts/**/*.py,scripts/**/*.ps1,.github/workflows/*.yaml,.github/workflows/*.yml"
---

# Actionable Error Messaging

## The Principle

Every script and workflow failure must answer three questions for the next
human or agent who reads the output:

1. **What failed?** — the specific operation, not just a stack trace
2. **Why does it most likely fail?** — 1–3 ranked common causes
3. **What should I try next?** — a concrete command, doc link, or config key

Treat error messages as documentation. An agent in a fresh context window
should be able to fix a transient failure without re-reading the source.

## The Format

### Python scripts

Use the shared helpers in `scripts/lib/errors.py`. Do not write ad-hoc
`print("ERROR ..."); sys.exit(1)`.

```python
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES

require_env(
    "CONFLUENCE_EMAIL",
    "WWEEKS_CONFLUENCE_API_TOKEN",
    hint="Load .env: export $(grep -v '^#' .env | xargs)",
)

try:
    resp = urlopen(req)
except urllib.error.HTTPError as e:
    http_fail(e, api_name="Linear", key=args.key, common_causes=JIRA_COMMON_CAUSES)
```

### Output format (rendered)

```
❌ <one-line summary of what failed>
   Likely causes:
     • <cause 1>
     • <cause 2>
   Try:
     • <command or check 1>
     • <command or check 2>
   Docs: <path or URL, if applicable>
```

Emoji prefix is mandatory (`❌` for fatal, `⚠️` for warn, `ℹ️` for info).
The block always ends with `Try:` — if you cannot name a next step, the
error is not actionable enough yet.

### PowerShell scripts

```powershell
try {
    Invoke-RestMethod -Uri $url -Headers $headers
} catch {
    Write-Host "❌ Fabric API rejected request ($($_.Exception.Response.StatusCode))" -ForegroundColor Red
    Write-Host "   Likely causes:" -ForegroundColor Yellow
    Write-Host "     • Managed identity lost the Fabric workspace role"
    Write-Host "     • Token cache stale — Functions host needs restart"
    Write-Host "   Try:"
    Write-Host "     • Verify role: az fabric workspace user list --workspace-id $wsId"
    Write-Host "     • Restart Function App"
    throw
}
```

### GitHub Actions workflows

Every workflow that calls scripts or `az`/`gh`/`terraform`/`bicep` must
include a final `if: failure()` step that prints troubleshooting hints:

```yaml
- name: 📋 Troubleshooting hints (on failure)
  if: failure()
  run: |
    echo "❌ Workflow failed. Common causes:"
    echo "   • OIDC federated credential mismatch — verify subject claim"
    echo "   • Stack does not exist in target subscription"
    echo "   • Required secret missing: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID"
    echo ""
    echo "Try:"
    echo "   • Re-run with debug: gh workflow run <file> --ref <branch> -f debug=true"
    echo "   • Check secret: gh secret list | grep AZURE"
    echo "   • Validate stack locally: ./scripts/deploy-bicep.ps1 -Env dev -Stack <name> -Action what-if"
```

## Required Causes & Fixes by API

When raising an HTTP/CLI failure, always pair it with the relevant
"common causes" dict from `scripts/lib/errors.py`:

| Tool / API | Common-causes constant |
|---|---|
| Linear REST | `JIRA_COMMON_CAUSES` |
| ServiceDesk Plus | `Linear_COMMON_CAUSES` |
| Azure CLI (`az`) | `AZURE_COMMON_CAUSES` |
| Notion REST | `CONFLUENCE_COMMON_CAUSES` |
| Microsoft Graph | `GRAPH_COMMON_CAUSES` |
| Fabric REST | `FABRIC_COMMON_CAUSES` |

If a new API is introduced, add a `*_COMMON_CAUSES` dict to `lib/errors.py`
in the same PR — do not ship a script that surfaces raw HTTP error bodies.

## Anti-Patterns

❌ `raise Exception("failed")` — no context
❌ `print(f"ERROR: {e}"); sys.exit(1)` — generic, no next step
❌ `except Exception: pass` — silent swallow
❌ Dumping a 4 KB API response body verbatim — overwhelming, not actionable
❌ Error message in a language only the author understands
   (e.g. `"flow stub broken"` — meaningless to an agent)

## Style Notes

- Lead with the **operation**, not the exception class
  - ✅ `❌ Linear label update rejected for <PROJECT>-519`
  - ❌ `❌ HTTPError: 403`
- Name **environment variables** explicitly, never "auth failed"
- Always include the **resource identifier** (issue key, vault name, sub id)
- Causes are **ranked** — most likely first
- Each `Try:` item should be **copy-pasteable** when possible

## Checklist for any new script

- [ ] Imports from `lib.errors` instead of ad-hoc `print/sys.exit`
- [ ] Required env vars validated up front via `require_env()`
- [ ] HTTP failures routed through `http_fail()` with a `*_COMMON_CAUSES` dict
- [ ] Required CLI tools validated via `require_tool()`
- [ ] At least one manual failure test confirms output is actionable
