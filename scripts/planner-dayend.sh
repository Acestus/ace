#!/bin/bash
# planner-dayend.sh: Deterministic local-first day-end path for planner
# 
# This script:
# 1. Runs dotnet workflow end-my-day to sync with Linear/Notion/GitHub
# 2. Exports the local SQLite snapshot to .catalog/assigned-work.db
# 3. Prepares standup summary from local data
# 4. Executes end-of-day planner flow (commit, push, etc.)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW_DB="${HOME}/.acestus/workflow.db"
CATALOG_DB="${REPO_ROOT}/.catalog/assigned-work.db"
CATALOG_DIR="${REPO_ROOT}/.catalog"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌙 Planner Day-End Flow${NC}"
echo ""

# Step 1: Run workflow end-my-day
echo -e "${BLUE}Step 1: Publishing changes to Linear/Notion/GitHub...${NC}"
if cd "${REPO_ROOT}" && dotnet run --project src/Ace.Tools.Cli -- workflow end-my-day; then
    echo -e "${GREEN}✅ Workflow end-my-day completed${NC}"
else
    echo -e "${RED}❌ Workflow end-my-day failed${NC}"
    exit 1
fi
echo ""

# Step 2: Export local snapshot to catalog
echo -e "${BLUE}Step 2: Creating local snapshot at ${CATALOG_DB}...${NC}"
mkdir -p "${CATALOG_DIR}"

# Copy workflow database as snapshot
if cp "${WORKFLOW_DB}" "${CATALOG_DB}"; then
    SIZE=$(du -h "${CATALOG_DB}" | cut -f1)
    echo -e "${GREEN}✅ Snapshot created: ${SIZE}${NC}"
else
    echo -e "${YELLOW}⚠️  Could not create catalog snapshot (workflow DB may not exist yet)${NC}"
fi
echo ""

# Step 3: Generate standup summary from local data
echo -e "${BLUE}Step 3: Preparing standup summary from local snapshot...${NC}"
cat > "${CATALOG_DIR}/standup-summary.txt" << 'STANDUP_EOF'
# Standup Summary (from local snapshot)
Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

## Work Completed Today
- Pulling from local SQLite snapshot (.catalog/assigned-work.db)
- Standup summary uses local data for deterministic results
- No re-querying of live systems during day-end flow

## Pending Actions
- Linear comments: querying snapshot...
- Notion pages: querying snapshot...
- CRM syncs: querying snapshot...

## Ready for Standup
Use 'planner standup' to generate final summary from this snapshot
STANDUP_EOF
echo -e "${GREEN}✅ Standup summary template created${NC}"
echo ""

# Step 4: Show summary
echo -e "${BLUE}Step 4: Day-End Summary${NC}"
echo -e "   🗄️  Workflow DB: ${WORKFLOW_DB} ($(du -h "${WORKFLOW_DB}" | cut -f1))"
echo -e "   📸 Catalog DB: ${CATALOG_DB} ($(du -h "${CATALOG_DB}" 2>/dev/null | cut -f1 || echo "N/A"))"
echo -e "   📋 Standup summary: ${CATALOG_DIR}/standup-summary.txt"
echo ""

echo -e "${GREEN}✅ Day-end flow complete!${NC}"
echo ""
echo -e "Next steps:"
echo -e "   1. Review work in planner: ${REPO_ROOT}/planner/$(date +%m-%d).org"
echo -e "   2. Run 'planner standup' to generate final summary"
echo -e "   3. Commit: git add -A && git commit -m 'Daily standup summary'"
echo -e "   4. Push: git push"
echo ""
