#!/bin/bash
# Solar Chain Watcher v3 — 全文件扫描 + 通知 + flock 防多开
# sprint-20260503-111139: 扩展扫描到 review-/research-/其它 + PLANNER-INBOX 通知
# 1. 扫 ~/.solar/codex-bridge/from-codex/ 所有 .md (排除 template) → 按 prefix 分发
# 2. contract-/execution-contract- → 起自动 sprint
# 3. review-/research-/其它 → 写 PLANNER-INBOX 通知
# 4. 检测无 active sprint → 起队列下一个 drafting

# D4: mkdir 原子锁防多开 (chain-watcher.pid) — flock 在 macOS 不可用
PID_LOCK_DIR="$HOME/.solar/harness/.chain-watcher.lock"
mkdir "$PID_LOCK_DIR" 2>/dev/null || { echo "[chain-watcher] already running, exit"; exit 0; }
echo $$ > "$PID_LOCK_DIR/pid"
trap 'rm -rf "$PID_LOCK_DIR"' EXIT

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
CODEX_INBOX="$HOME/.solar/codex-bridge/from-codex"
CODEX_PROCESSED="$HOME/.solar/codex-bridge/from-codex/.processed"
PLANNER_INBOX="$HARNESS_DIR/PLANNER-INBOX.md"
SPRINTS_DIR="$HARNESS_DIR/sprints"
mkdir -p "$CODEX_PROCESSED"

# D3: bridge ledger
LEDGER_SH="$HOME/.solar/harness/lib/bridge-ledger.sh"
[[ -f "$LEDGER_SH" ]] && . "$LEDGER_SH"

# D2: 通知机制 — 追加 [CODEX-xxx] 行到 PLANNER-INBOX.md
notify_planner_codex_file() {
  local type="$1" base="$2"
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%MZ")
  mkdir -p "$(dirname "$PLANNER_INBOX")"
  printf '%s\n' "- [ ] [${ts}] [${type}] ${base} (~/.solar/codex-bridge/from-codex/)" >> "$PLANNER_INBOX"
}

# sprint-20260503-150911 — pane 0 (planner) 强制通知
# 解决问题: 规划者反复漏看 PLANNER-INBOX, Codex review 卡很久没人处理
# 机制: tmux send-keys 直接写到 solar-harness:0.0 (planner pane) input box + C-m 提交
PANE0_TARGET="solar-harness:0.0"
PANE0_THROTTLE_FILE="$HOME/.solar/harness/.chain-watcher-pane0-throttle"
PANE0_THROTTLE_WINDOW=60   # 同 type 60s 内最多 1 条 send-keys (PLANNER-INBOX 不限频)

notify_pane0_planner() {
  local type="$1" base="$2"
  local now type_key last_ts elapsed
  now=$(date +%s)
  type_key=$(echo "$type" | tr 'A-Z' 'a-z')

  # D2: 限频检查 — 同一 type 60s 内只发 1 条
  touch "$PANE0_THROTTLE_FILE"
  last_ts=$(grep -E "^${type_key}:" "$PANE0_THROTTLE_FILE" 2>/dev/null | tail -1 | cut -d: -f2)
  if [ -n "$last_ts" ]; then
    elapsed=$(( now - last_ts ))
    if [ "$elapsed" -lt "$PANE0_THROTTLE_WINDOW" ]; then
      echo "[$(date '+%H:%M:%S')] pane0-throttle: ${type_key} skipped (${elapsed}s < ${PANE0_THROTTLE_WINDOW}s) for ${base}"
      return 0
    fi
  fi

  # D3: pane 0 idle 检测 (busy 时仍发 send-keys, claude TUI 自带 queue, 不打断思考)
  local pane_tail busy=0
  pane_tail=$(tmux capture-pane -t "$PANE0_TARGET" -p 2>/dev/null | tail -3)
  if echo "$pane_tail" | grep -qE 'Cerebrating|Churning|Honking|Whatchamacalliting|Lollygagging|Skedaddling|Discombobulating|Embellishing|Razzmatazzing|Topsy-turvying|Infusing|Flowing'; then
    busy=1
  fi

  # 实际发送
  local msg="[CODEX-NOTIFY] 收到 ${type}: ${base}. 立刻读 ~/.solar/harness/PLANNER-INBOX.md 末尾处理 (不要等 watch)."
  if tmux send-keys -t "$PANE0_TARGET" "$msg" C-m 2>/dev/null; then
    if [ "$busy" = "1" ]; then
      echo "[$(date '+%H:%M:%S')] pane 0 busy when notifying, queued: ${type} ${base}"
    else
      echo "[$(date '+%H:%M:%S')] pane 0 notified (idle): ${type} ${base}"
    fi
    # 更新 throttle: 删旧行 + 写新 type:last_ts
    if [ -f "$PANE0_THROTTLE_FILE" ]; then
      grep -vE "^${type_key}:" "$PANE0_THROTTLE_FILE" > "${PANE0_THROTTLE_FILE}.tmp" 2>/dev/null || true
    else
      : > "${PANE0_THROTTLE_FILE}.tmp"
    fi
    echo "${type_key}:${now}" >> "${PANE0_THROTTLE_FILE}.tmp"
    mv "${PANE0_THROTTLE_FILE}.tmp" "$PANE0_THROTTLE_FILE"
  else
    echo "[$(date '+%H:%M:%S')] pane 0 send-keys FAILED for ${type} ${base} (target ${PANE0_TARGET} not reachable?)"
  fi
}

# 处理单个 contract 文件 (从 ingest_codex_all_files 调用)
# dedup + cp+rm 由调用方统一处理
ingest_single_contract() {
  local cf="$1"
  local base
  base=$(basename "$cf")

  local TITLE
  TITLE=$(grep -m1 '^title:' "$cf" | sed 's/^title:[[:space:]]*//')
  [ -z "$TITLE" ] && TITLE=$(basename "$cf" .md | sed 's/contract-//')
  echo "[$(date '+%H:%M:%S')] codex 合约接收: $base → 起 sprint"

  local RESULT SID
  RESULT=$(~/.solar/bin/solar-harness sprint "[Codex] $TITLE" 2>&1)
  SID=$(echo "$RESULT" | grep -oE 'sprint-[0-9-]+' | head -1)
  if [ -z "$SID" ]; then
    echo "  ❌ 创建失败"
    return 1
  fi

  cp "$cf" "$HOME/.solar/harness/sprints/$SID.contract.md"

  # Codex remote execution path: contracts with bypass_pm:true are already fully
  # specified. Route them directly to builder by materializing a minimal plan and
  # promoting status, instead of downgrading them into PM intake.
  if grep -Eq '^bypass_pm:[[:space:]]*true[[:space:]]*$' "$cf"; then
    python3 - "$SID" "$cf" "$HOME/.solar/harness/sprints/$SID.status.json" "$HOME/.solar/harness/sprints/$SID.plan.md" <<'PY_CHAIN_WATCHER_BYPASS'
import json, sys, datetime
from pathlib import Path

sid, contract, status, plan = sys.argv[1:]
now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
contract_p = Path(contract)
status_p = Path(status)
plan_p = Path(plan)

try:
    d = json.loads(status_p.read_text())
except Exception:
    d = {"id": sid, "history": []}

d["status"] = "active"
d["phase"] = "planning_complete"
d["handoff_to"] = "builder"
d["updated_at"] = now
d.setdefault("history", []).append({
    "ts": now,
    "event": "bypass_pm_contract_promoted_to_builder",
    "by": "chain-watcher",
    "contract": str(contract_p),
})
status_p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
plan_p.write_text(f"""# Plan — {sid}

## Intent

Execute the already bounded bypass_pm contract exactly as written.

## Write Scope

- Only files explicitly allowed by the contract.
- For this sprint, write handoff/evidence under `~/.solar/harness/sprints/`.

## Steps

1. Read `{contract_p}`.
2. Execute only the Required Work and Acceptance Criteria in the contract.
3. Write `~/.solar/harness/sprints/{sid}.handoff.md` unless the contract explicitly requires a different handoff path.
4. Run the contract verification commands.
5. Submit with `bash ~/.solar/harness/solar-harness.sh handoff-submit {sid}`.

## Stop Rules

- Stop on any action outside the contract boundary.
- Do not repair unrelated Solar/Codex/harness state.
""")
PY_CHAIN_WATCHER_BYPASS
    if [[ -f "$HARNESS_DIR/lib/events.sh" ]]; then
      # shellcheck source=/dev/null
      source "$HARNESS_DIR/lib/events.sh"
      events_emit "chain-watcher" "bypass_pm_promoted" "info" "$SID" "{\"to\":\"builder\",\"plan\":\"$HARNESS_DIR/sprints/$SID.plan.md\"}" 2>/dev/null || true
    fi
    echo "  ✅ → $SID (bypass_pm:true → active/planning_complete, builder route)"
  else
    echo "  ✅ → $SID (drafting,等 chain 起)"
  fi
  type ledger_emit &>/dev/null && ledger_emit "produced" "$SID.contract.md" "{\"source\":\"codex\"}" 2>/dev/null || true
  type ledger_emit &>/dev/null && ledger_emit "consumed" "$SID.contract.md" "{\"source\":\"chain-watcher\"}" 2>/dev/null || true
}

# D1: 全文件扫描 — find 所有 .md (排除 template 和 .processed/)，按 prefix 分发
# D3: 通知路径共用 .processed/ dedup (cp + rm)
# D5: find 排除 *.template.md
# D8: 每轮末尾 log 统计
ingest_codex_all_files() {
  local n_contracts=0 n_reviews=0 n_research=0 n_unknown=0 n_templates=0
  for cf in $(find "$CODEX_INBOX" -maxdepth 1 -name "*.md" ! -name "*.template.md" 2>/dev/null); do
    [ -f "$cf" ] || continue
    local base
    base=$(basename "$cf")
    # D3: dedup — 已处理跳过
    [ -f "$CODEX_PROCESSED/$base" ] && continue

    case "$base" in
      contract-*|execution-contract-*)
        if ingest_single_contract "$cf"; then
          cp "$cf" "$CODEX_PROCESSED/$base"
          rm "$cf"
          n_contracts=$((n_contracts + 1))
        fi
        ;;
      review-*)
        notify_planner_codex_file "CODEX-REVIEW" "$base"
        notify_pane0_planner "CODEX-REVIEW" "$base"
        type ledger_emit &>/dev/null && ledger_emit "consumed" "$base" "{\"source\":\"chain-watcher\"}" 2>/dev/null || true
        cp "$cf" "$CODEX_PROCESSED/$base"
        rm "$cf"
        n_reviews=$((n_reviews + 1))
        ;;
      research-*)
        notify_planner_codex_file "CODEX-RESEARCH" "$base"
        notify_pane0_planner "CODEX-RESEARCH" "$base"
        type ledger_emit &>/dev/null && ledger_emit "consumed" "$base" "{\"source\":\"chain-watcher\"}" 2>/dev/null || true
        cp "$cf" "$CODEX_PROCESSED/$base"
        rm "$cf"
        n_research=$((n_research + 1))
        ;;
      *)
        notify_planner_codex_file "CODEX-UNKNOWN" "$base"
        notify_pane0_planner "CODEX-UNKNOWN" "$base"
        cp "$cf" "$CODEX_PROCESSED/$base"
        rm "$cf"
        n_unknown=$((n_unknown + 1))
        ;;
    esac
  done
  echo "[$(date '+%H:%M:%S')] scan: contracts=$n_contracts reviews=$n_reviews research=$n_research unknown=$n_unknown templates_skipped=$n_templates"
}

QUEUE_NEXT() {
  for f in $(ls -t "$SPRINTS_DIR"/sprint-*.status.json 2>/dev/null); do
    ST=$(python3 -c "import json; print(json.load(open('$f')).get('status',''))" 2>/dev/null)
    [ "$ST" = "drafting" ] && python3 -c "import json; print(json.load(open('$f')).get('id',''))" && return
  done
}

drafting_has_plan() {
  local sid="$1"
  [ -f "$SPRINTS_DIR/$sid.plan.md" ]
}

# D10: 启动恢复 — flock 后先扫一轮清积压
ingest_codex_all_files

while true; do
  # 1. 扫 codex 全文件
  ingest_codex_all_files

  # 2. 检测 active
  ACTIVE=$(grep -l '"status": "active"\|"status": "planning"\|"status": "approved"\|"status": "reviewing"\|"status": "failed_review"\|"status": "architect_reviewing"\|"status": "building_parallel"' "$SPRINTS_DIR"/sprint-*.status.json 2>/dev/null | head -1)
  if [ -z "$ACTIVE" ]; then
    NEXT=$(QUEUE_NEXT)
    if [ -n "$NEXT" ]; then
      if ! drafting_has_plan "$NEXT"; then
        echo "[$(date '+%H:%M:%S')] auto-chain: skip $NEXT (drafting without plan.md; coordinator PM→planner flow owns it)"
        sleep 60
        continue
      fi

      echo "[$(date '+%H:%M:%S')] auto-chain: 起 $NEXT (plan.md ready)"
      python3 "$HARNESS_DIR/lib/runtime_status.py" "$SPRINTS_DIR/$NEXT.status.json" "active" "auto_chain" "chain-watcher" '{"status_fields":{"phase":"planning_complete","handoff_to":"builder_main","target_role":"builder_main"},"note":"plan.md exists; promoted drafting sprint to active"}' >/dev/null 2>&1 || true
      sleep 60
    fi
  fi
  sleep 30
done
