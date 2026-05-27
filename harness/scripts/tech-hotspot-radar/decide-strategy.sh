#!/usr/bin/env bash
# scripts/tech-hotspot-radar/decide-strategy.sh - Run hard gates and strategy engine for one or more repos
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"

DB_PATH=""
REPO=""
DRY_RUN="false"
FORCE_DECISION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db) DB_PATH="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --dry-run) DRY_RUN="true"; shift ;;
        --force-decision) FORCE_DECISION="$2"; shift 2 ;;
        --config) shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$DB_PATH" ]]; then
    echo "Usage: decide-strategy.sh --db <path> [--repo <owner/name>] [--dry-run] [--force-decision <type>]" >&2
    exit 1
fi

mapfile -t REPOS < <(
    python3 - <<'PY' "$DB_PATH" "$REPO"
import sqlite3, sys
db_path, repo = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db_path)
if repo:
    print(repo)
else:
    for row in conn.execute("SELECT DISTINCT repo_full_name FROM repo_analysis_cards ORDER BY repo_full_name"):
        print(row[0])
conn.close()
PY
)

for full_name in "${REPOS[@]}"; do
    [[ -z "$full_name" ]] && continue
    args=(--db "$DB_PATH" --repo "$full_name")
    [[ -n "$FORCE_DECISION" ]] && args+=(--force-decision "$FORCE_DECISION")
    [[ "$DRY_RUN" == "true" ]] && args+=(--dry-run)
    bash "$LIB_DIR/strategy-engine.sh" "${args[@]}"
done
