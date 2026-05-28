#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="${HOME}"
HARNESS_DIR="${HARNESS_DIR:-$HOME_DIR/.solar/harness}"
SPRINT_ID="${SPRINT_ID:-sprint-20260527-understand-anything-background-knowledge-graph}"
TARGET_REPO="${1:-/Users/lisihao/Solar}"
OUTPUT_DIR="$TARGET_REPO/.understand-anything"
RUN_ROOT="$HARNESS_DIR/run/understand-anything-background/$SPRINT_ID"
STATUS_JSON="$RUN_ROOT/status.json"
OUTPUT_LOG="$RUN_ROOT/output.log"
PREFLIGHT_JSON="$RUN_ROOT/preflight.json"
VERIFY_JSON="$RUN_ROOT/verify.json"
HANDOFF_MD="$HARNESS_DIR/sprints/$SPRINT_ID.handoff.md"
TASK_GRAPH="$HARNESS_DIR/sprints/$SPRINT_ID.task_graph.json"
SPRINT_STATUS="$HARNESS_DIR/sprints/$SPRINT_ID.status.json"
PLUGIN_ROOT="$HOME_DIR/.claude/plugins/cache/understand-anything/understand-anything/2.7.5"

export SPRINT_ID

mkdir -p "$RUN_ROOT"

write_status() {
  local phase="$1"
  local state="$2"
  local message="$3"
  STATUS_JSON="$STATUS_JSON" phase="$phase" state="$state" message="$message" target_repo="$TARGET_REPO" output_dir="$OUTPUT_DIR" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

path = Path(os.environ["STATUS_JSON"])
payload = {
    "schema_version": "solar.understand_anything_background.status.v1",
    "sprint_id": os.environ.get("SPRINT_ID", "unknown"),
    "phase": os.environ["phase"],
    "status": os.environ["state"],
    "message": os.environ["message"],
    "target_repo": os.environ["target_repo"],
    "output_dir": os.environ["output_dir"],
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

update_sprint_status() {
  local phase="$1"
  local state="$2"
  local blocker="$3"
  SPRINT_STATUS="$SPRINT_STATUS" phase="$phase" state="$state" blocker="$blocker" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

path = Path(os.environ["SPRINT_STATUS"])
payload = {}
if path.exists():
    payload = json.loads(path.read_text(encoding="utf-8"))
payload.update({
    "sprint_id": payload.get("sprint_id", "sprint-20260527-understand-anything-background-knowledge-graph"),
    "id": payload.get("id", "sprint-20260527-understand-anything-background-knowledge-graph"),
    "title": payload.get("title", "Understand Anything 全仓知识图后台生成（分阶段、非阻塞）"),
    "status": os.environ["state"],
    "phase": os.environ["phase"],
    "current_node": payload.get("current_node", "U1_preflight_runtime"),
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "blocker": os.environ["blocker"],
})
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_handoff() {
  local result="$1"
  cat > "$HANDOFF_MD" <<EOF
# Handoff — $SPRINT_ID

- target_repo: \`$TARGET_REPO\`
- output_dir: \`$OUTPUT_DIR\`
- result: \`$result\`
- status_json: \`$STATUS_JSON\`
- output_log: \`$OUTPUT_LOG\`
- preflight_json: \`$PREFLIGHT_JSON\`
- verify_json: \`$VERIFY_JSON\`

## Notes
- This run is isolated in a dedicated background tmux session to avoid blocking the main Solar Harness panes.
- Check \`$STATUS_JSON\` for the latest phase and \`$OUTPUT_LOG\` for raw command output.
EOF
}

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] understand-anything background task start" > "$OUTPUT_LOG"
echo "sprint=$SPRINT_ID target=$TARGET_REPO" >> "$OUTPUT_LOG"

write_status "U1_preflight_runtime" "running" "Checking Claude auth, plugin cache, Node and pnpm prerequisites."
update_sprint_status "background_preflight" "active" ""

CLAUDE_AUTH_JSON="$(claude auth status)"
NODE_VERSION="$(node -v)"
PNPM_VERSION="$(pnpm -v)"

python3 - <<PY > "$PREFLIGHT_JSON"
import json
from pathlib import Path
payload = {
  "claude_auth": json.loads('''$CLAUDE_AUTH_JSON'''),
  "node_version": "$NODE_VERSION",
  "pnpm_version": "$PNPM_VERSION",
  "plugin_root_exists": Path("$PLUGIN_ROOT").exists(),
  "target_repo": "$TARGET_REPO",
  "output_dir_exists": Path("$OUTPUT_DIR").exists(),
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY

write_status "U2_run_understand_zh_background" "running" "Launching /understand --language zh in the dedicated background runner."
update_sprint_status "background_understand_running" "active" ""

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] phase=U2_run_understand_zh_background"
  nice -n 10 claude -p --dangerously-skip-permissions --output-format text "/understand --language zh $TARGET_REPO"
} >> "$OUTPUT_LOG" 2>&1

write_status "U3_verify_graph_artifacts" "running" "Verifying knowledge graph artifacts and metadata."

python3 - <<PY > "$VERIFY_JSON"
import json
from pathlib import Path
root = Path("$OUTPUT_DIR")
graph = root / "knowledge-graph.json"
meta = root / "meta.json"
config = root / "config.json"
payload = {
  "output_dir_exists": root.exists(),
  "config_exists": config.exists(),
  "knowledge_graph_exists": graph.exists(),
  "knowledge_graph_size": graph.stat().st_size if graph.exists() else 0,
  "meta_exists": meta.exists(),
}
if graph.exists():
  try:
    json.loads(graph.read_text(encoding="utf-8"))
    payload["knowledge_graph_json_valid"] = True
  except Exception as exc:
    payload["knowledge_graph_json_valid"] = False
    payload["knowledge_graph_error"] = str(exc)
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY

if python3 - <<PY
import json
from pathlib import Path
payload = json.loads(Path("$VERIFY_JSON").read_text(encoding="utf-8"))
assert payload.get("knowledge_graph_exists")
assert payload.get("knowledge_graph_json_valid")
PY
then
  write_status "U4_handoff_resume_contract" "running" "Knowledge graph verified; writing handoff."
  write_handoff "success"
  write_status "U4_handoff_resume_contract" "completed" "Background understand-anything run completed successfully."
  update_sprint_status "background_completed" "reviewing" ""
else
  write_handoff "partial_or_failed"
  write_status "U3_verify_graph_artifacts" "failed" "Background run finished without a valid knowledge-graph.json."
  update_sprint_status "background_verification_failed" "active" "knowledge-graph.json missing or invalid after background run"
  exit 1
fi
