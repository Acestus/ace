#!/usr/bin/env bash
# Run the Ace CRM fully locally:
#   - Azurite (emulates the Functions runtime's own AzureWebJobsStorage)
#   - Azure Functions host (Ace.Crm.Api), talking to the REAL Azure Table
#     Storage account (stcrmdevscus001) over your own az login / AAD identity
#     — no keys on disk, no public endpoint, data never touches a Static
#     Web App or public internet.
#   - A plain static file server for web/wwwroot (vanilla HTML/JS, no build)
#
# Requires: az login (with Storage Table Data Contributor on stcrmdevscus001),
# azurite (npm i -g azurite), Azure Functions Core Tools (func), .NET 10 SDK.
#
# Usage: ./scripts/crm-local.sh [stop]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/src/Ace.Crm.Api"
WEB_DIR="$REPO_ROOT/web/wwwroot"
AZURITE_DATA="/tmp/ace-crm-azurite"
PIDFILE="/tmp/ace-crm-local.pids"

FUNC_PORT="${FUNC_PORT:-7071}"
WEB_PORT="${WEB_PORT:-8080}"

if [[ "${1:-}" == "stop" ]]; then
  if [[ -f "$PIDFILE" ]]; then
    while read -r pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PIDFILE"
    rm -f "$PIDFILE"
  fi
  echo "Stopped."
  exit 0
fi

if [[ -f "$PIDFILE" ]]; then
  echo "Already running (or stale pidfile). Run '$0 stop' first." >&2
  exit 1
fi

command -v azurite >/dev/null || { echo "azurite not found. Run: npm install -g azurite" >&2; exit 1; }
command -v func >/dev/null || { echo "func (Azure Functions Core Tools) not found." >&2; exit 1; }
az account show >/dev/null 2>&1 || { echo "Not logged in. Run: az login" >&2; exit 1; }

mkdir -p "$AZURITE_DATA"
: > "$PIDFILE"

echo "Starting Azurite (local runtime storage only)..."
azurite --silent --location "$AZURITE_DATA" &
echo $! >> "$PIDFILE"
sleep 2

echo "Starting Functions host on :$FUNC_PORT (real Table Storage via az login)..."
(cd "$API_DIR" && func start --port "$FUNC_PORT") &
echo $! >> "$PIDFILE"
sleep 5

echo "Starting static file server on :$WEB_PORT for web/wwwroot..."
(cd "$WEB_DIR" && python3 -m http.server "$WEB_PORT") &
echo $! >> "$PIDFILE"

cat <<EOF

Ace CRM running locally:
  UI:  http://localhost:$WEB_PORT/crm.html
  API: http://localhost:$FUNC_PORT/api

Stop with: $0 stop
EOF
