#!/bin/bash
# ================================================================
# Solar Harness — 一键启动多化身协同环境
#
# 用法:
#   solar-harness.sh [工作目录]          启动3化身 (默认)
#   solar-harness.sh 2 [工作目录]        启动2化身
#   solar-harness.sh status              查看状态
#   solar-harness.sh kill                关闭
#   solar-harness.sh sprint "需求"       创建 Sprint
#
# @module solar-farm/harness
# ================================================================
set -eu

HARNESS_DIR="$HOME/.solar/harness"
SESSION_NAME="solar-harness"
SPRINTS_DIR="$HARNESS_DIR/sprints"

# sprint-20260503-094659 D2: 统一 state helper
. "$HARNESS_DIR/lib/run-state.sh"

# sprint-20260503-163542 D3: bridge ledger
[[ -f "$HARNESS_DIR/lib/bridge-ledger.sh" ]] && . "$HARNESS_DIR/lib/bridge-ledger.sh"

# ---- Colors ----
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; B='\033[0;34m'; N='\033[0m'
log()  { echo -e "${C}[Harness]${N} $*"; }
ok()   { echo -e "${G}[Harness]${N} $*"; }
warn() { echo -e "${Y}[Harness]${N} $*"; }
err()  { echo -e "${R}[Harness]${N} $*"; }

ensure_dirs() { mkdir -p "$SPRINTS_DIR" "$HARNESS_DIR/personas" "$HARNESS_DIR/templates"; }

# ---- Bash 4+ 检测 ----

resolve_bash4() {
  local candidates=(
    /opt/homebrew/bin/bash
    /usr/local/bin/bash
    "$(command -v bash 2>/dev/null)"
  )
  for b in "${candidates[@]}"; do
    [[ -z "$b" || ! -x "$b" ]] && continue
    local major
    major=$("$b" -c 'echo ${BASH_VERSINFO[0]}' 2>/dev/null || echo 0)
    if [[ "$major" -ge 4 ]]; then
      echo "$b"
      return 0
    fi
  done
  return 1
}

# 缓存 bash4 路径 (启动时解析一次)
BASH4=""
_ensure_bash4() {
  [[ -n "$BASH4" ]] && return 0
  BASH4=$(resolve_bash4) || return 1
}

# ---- Doctor 自检 ----

do_doctor() {
  local failed=0

  # (a) bash 4+ 可用
  local bash4=""
  bash4=$(resolve_bash4) || {
    echo "❌ bash 4+ 不可用 (当前 /bin/bash: ${BASH_VERSINFO[0]})"
    echo "   修复: brew install bash"
    ((failed++))
  }

  # (b) tmux/claude/python3/jq 在 PATH
  for cmd in tmux claude python3 jq; do
    command -v "$cmd" &>/dev/null || {
      echo "❌ $cmd 不在 PATH"
      echo "   修复: brew install $cmd"
      ((failed++))
    }
  done

  # (c) coordinator.sh bash -n 通过
  if [[ -n "$bash4" ]]; then
    "$bash4" -n "$HARNESS_DIR/coordinator.sh" 2>/dev/null || {
      echo "❌ coordinator.sh 语法错误 (bash -n 失败)"
      echo "   修复: $bash4 -n $HARNESS_DIR/coordinator.sh 查看详情"
      ((failed++))
    }
  fi

  # (d) 关键目录可写
  [[ -w "$HARNESS_DIR" ]] || {
    echo "❌ $HARNESS_DIR 不可写"
    ((failed++))
  }

  # (e) coordinator pidfile 进程活
  if [[ -f "$HARNESS_DIR/.coordinator.pid" ]]; then
    local cpid
    cpid=$(cat "$HARNESS_DIR/.coordinator.pid" 2>/dev/null)
    if [[ -n "$cpid" ]] && ! kill -0 "$cpid" 2>/dev/null; then
      echo "⚠ coordinator pidfile 指向死进程 (PID=$cpid, 启动时会自愈)"
    fi
  fi

  # (f) coordinator.sh 未转义双引号平衡
  if [[ -f "$HARNESS_DIR/coordinator.sh" ]]; then
    local qcount
    qcount=$(awk '
      { for(i=1;i<=length;i++) if(substr($0,i,1)=="\"" && (i==1 || substr($0,i-1,1)!="\\")) n++ }
      END { print n+0 }' "$HARNESS_DIR/coordinator.sh")
    if (( qcount % 2 != 0 )); then
      echo "❌ coordinator.sh 未转义引号不平衡 (count=$qcount)"
      echo "   修复: 检查多行字符串中的双引号闭合"
      ((failed++))
    fi
  fi

  # (g) 所有 sprint 状态机合法
  for f in "$SPRINTS_DIR"/*.status.json; do
    [[ -f "$f" ]] || continue
    local st
    st=$(python3 -c "import json; print(json.load(open('$f')).get('status',''))" 2>/dev/null)
    case "$st" in
      drafting|active|planning|approved|reviewing|ready_for_review|failed_review|passed|done|failed|eval_pass|cancelled|interrupted|superseded|needs_human_review) ;;
      *)
        echo "⚠ $(basename "$f") 非法状态: $st"
        ;;
    esac
  done

  if (( failed == 0 )); then
    echo "✅ Solar Harness doctor: 全部通过"
    return 0
  else
    echo "❌ ${failed} 项检查失败"
    return 1
  fi
}

# ---- 同步启动 Coordinator ----

start_coordinator_sync() {
  _ensure_bash4 || { err "bash 4+ 不可用，无法启动 coordinator"; return 1; }

  local pidfile="$HARNESS_DIR/.coordinator.pid"

  # 已有活进程 → 跳过
  if [[ -f "$pidfile" ]]; then
    local existing_pid
    existing_pid=$(cat "$pidfile" 2>/dev/null)
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      ok "Coordinator 已在运行 (PID: $existing_pid)"
      # D7: doctor summary
      bash "$HARNESS_DIR/doctor.sh" --summary 2>/dev/null || true
      return 0
    fi
    # 死进程 → 清锁
    rm -f "$pidfile"
  fi

  # 启动 (nohup 隔离 SIGHUP)
  nohup "$BASH4" "$HARNESS_DIR/coordinator.sh" >> "$HARNESS_DIR/.coordinator.log" 2>&1 &
  disown 2>/dev/null || true

  # 等待 pidfile 出现 (最多 3 秒)
  local waited=0
  while (( waited < 30 )); do
    if [[ -f "$pidfile" ]]; then
      local pid
      pid=$(cat "$pidfile" 2>/dev/null)
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        ok "Coordinator 启动成功 (PID: $pid)"
        # D7: doctor summary
        bash "$HARNESS_DIR/doctor.sh" --summary 2>/dev/null || true
        return 0
      fi
    fi
    sleep 0.1
    ((waited++))
  done

  err "Coordinator 启动失败: 3 秒内 pidfile 未出现"
  err "查看日志: cat $HARNESS_DIR/.coordinator.log"
  return 1
}

# ---- 同步启动 Watchdog ----

start_watchdog_sync() {
  _ensure_bash4 || { warn "bash 4+ 不可用，跳过 watchdog"; return 0; }

  local pidfile="$HARNESS_DIR/.watchdog.pid"

  if [[ -f "$pidfile" ]]; then
    local existing_pid
    existing_pid=$(cat "$pidfile" 2>/dev/null)
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      ok "Watchdog 已在运行 (PID: $existing_pid)"
      return 0
    fi
    rm -f "$pidfile"
  fi

  nohup "$BASH4" "$HARNESS_DIR/coordinator-watchdog.sh" start >> "$HARNESS_DIR/.watchdog.log" 2>&1 &
  disown 2>/dev/null || true

  sleep 0.5
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    ok "Watchdog 启动成功 (PID: $(cat "$pidfile"))"
  else
    warn "Watchdog 启动未确认 (可能需要手动检查)"
  fi
  return 0
}

# ---- Start Harness ----

start_harness() {
  local mode="${1:-3}"
  local work_dir="${2:-$(pwd)}"
  local skip_doctor="${3:-}"

  # 启动前自检 (除非 --skip-doctor)
  if [[ "$skip_doctor" != "--skip-doctor" ]]; then
    log "运行启动自检..."
    do_doctor || { err "启动前自检失败，修复后再试 (或用 --skip-doctor 跳过)"; exit 1; }
  fi

  command -v tmux &>/dev/null || { err "tmux 未安装: brew install tmux"; exit 1; }
  command -v claude &>/dev/null || { err "claude 未安装"; exit 1; }

  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    # 检查是否还有 claude 在运行
    local claude_count
    claude_count=$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_current_command}' 2>/dev/null | grep -c '^claude$' || true)
    if [[ "$claude_count" -gt 0 ]]; then
      ok "Solar Harness 运行中 (${claude_count} 个 Claude 活跃)"
      tmux attach -t "$SESSION_NAME"
      return
    fi
    # 没有 claude 了 → 死 session，自动重建
    warn "旧 session 存在但 Claude 已退出，自动重建..."
    tmux kill-session -t "$SESSION_NAME"
  fi

  ensure_dirs

  log "启动 Solar Harness (${mode} 化身 + 监控)..."
  log "工作目录: ${work_dir}"

  # ================================================================
  # 四分屏布局 — Product Delivery (Window 0)
  #
  # ┌──────────────┬──────────────┐
  # │   产品经理    │   规划者      │
  # │   pm         │   planner    │
  # ├──────────────┼──────────────┤
  # │   建设者      │   审判官      │
  # │   builder    │   evaluator  │
  # └──────────────┴──────────────┘
  # ================================================================

  tmux new-session -d -s "$SESSION_NAME" -c "$work_dir"

  # D3: pane 保留现场 — 进程退出后 pane 不消失 (remain-on-exit)
  tmux set-option -t "$SESSION_NAME" remain-on-exit on

  # 创建4个 pane (tmux 会重编号！)
  # Step 1: 上下分 → 0(上) + 1(下)
  tmux split-window -v -t "$SESSION_NAME" -c "$work_dir"
  # Step 2: 上半左右分 → 0(左上) + 1(右上), 原1(下)变2
  tmux split-window -h -t "$SESSION_NAME:0.0" -c "$work_dir"
  # Step 3: 下半左右分 → 2(左下) + 3(右下)
  tmux split-window -h -t "$SESSION_NAME:0.2" -c "$work_dir"

  # Rename window 0
  tmux rename-window -t "$SESSION_NAME:0" "Product Delivery"

  # 最终编号: 0=左上 1=右上 2=左下 3=右下
  # 启动 pane-launcher (统一配置, 无交互阻塞)
  # D5 sprint-20260502-191700: printf '%q' 路径转义
  local _esc_harness _esc_work
  _esc_harness=$(printf '%q' "$HARNESS_DIR")
  _esc_work=$(printf '%q' "$work_dir")
  sleep 1
  tmux send-keys -t "$SESSION_NAME:Product Delivery.0" "bash ${_esc_harness}/pane-launcher.sh pm ${_esc_work}" Enter
  sleep 1
  tmux send-keys -t "$SESSION_NAME:Product Delivery.1" "bash ${_esc_harness}/pane-launcher.sh planner ${_esc_work}" Enter
  if [[ "$mode" == "3" ]]; then
    sleep 1
    tmux send-keys -t "$SESSION_NAME:Product Delivery.2" "bash ${_esc_harness}/pane-launcher.sh builder ${_esc_work}" Enter
    sleep 1
    tmux send-keys -t "$SESSION_NAME:Product Delivery.3" "bash ${_esc_harness}/pane-launcher.sh evaluator ${_esc_work}" Enter
  else
    sleep 1
    tmux send-keys -t "$SESSION_NAME:Product Delivery.2" "bash ${_esc_harness}/pane-launcher.sh builder ${_esc_work}" Enter
  fi

  # 设置活跃 pane 为 PM (非监控)
  tmux select-pane -t "$SESSION_NAME:Product Delivery.0"

  # 开启鼠标支持 (点击切换 pane)
  tmux set-option -t "$SESSION_NAME" mouse on

  # tmux 样式
  tmux set-option -t "$SESSION_NAME" status-style "bg=#1a1a2e,fg=#cdd6f4"
  tmux set-option -t "$SESSION_NAME" pane-border-style "fg=#45475a"
  tmux set-option -t "$SESSION_NAME" pane-active-border-style "fg=#89b4fa"
  tmux set-option -t "$SESSION_NAME" status-right-length 60
  tmux set-option -t "$SESSION_NAME" status-right "#[fg=#89b4fa]Solar Harness #[fg=#a6e3a1]${mode}化身+并行 #[default]%H:%M"

  # 打印帮助 (attach 前输出到 stdout)
  echo ""
  ok "══════════════════════════════════════════════════"
  ok "  Solar Harness 启动完成!"
  echo ""
  if [[ "$mode" == "3" ]]; then
    echo "  布局 (四分屏同时可见):"
    echo ""
    echo "  ┌──────────────┬──────────────┐"
    echo "  │   产品经理    │   规划者      │"
    echo "  │   pm         │   planner    │"
    echo "  ├──────────────┼──────────────┤"
    echo "  │   建设者      │   审判官      │"
    echo "  │   builder    │   evaluator  │"
    echo "  └──────────────┴──────────────┘"
  else
    echo "  布局 (三分屏):"
    echo ""
    echo "  ┌──────────────┬──────────────┐"
    echo "  │   产品经理    │   规划者      │"
    echo "  │   pm         │   planner    │"
    echo "  ├──────────────┴──────────────┤"
    echo "  │         建设者 builder       │"
    echo "  └─────────────────────────────┘"
  fi
  echo ""
  log "tmux 快捷键:"
  echo "  切 pane:   Ctrl+B → 方向键"
  echo "  全屏当前:  Ctrl+B → z (再按一次恢复)"
  echo "  后台运行:  Ctrl+B → d"
  echo "  重新接入:  tmux attach -t $SESSION_NAME"
  echo ""
  log "使用方法:"
  echo "  1. 切到化身 pane (Ctrl+B → 方向键 / 鼠标点击)"
  echo "  2. 按 Enter 启动该化身的 Claude"
  echo "  3. 处理 Claude 的确认提示 (信任文件夹等)"
  echo ""

  # ── 同步拉 Coordinator + Watchdog (SIGHUP 隔离) ──
  start_coordinator_sync || { err "Coordinator 启动失败，中止"; exit 1; }
  start_watchdog_sync

  tmux attach -t "$SESSION_NAME"
}

# ---- Status ----

show_status() {
  echo ""
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    ok "Solar Harness 运行中"
    echo ""
    tmux list-windows -t "$SESSION_NAME" 2>/dev/null | sed 's/^/  /'
    echo ""
    local cnt
    cnt=$(ls "$SPRINTS_DIR"/*.status.json 2>/dev/null | wc -l | tr -d ' ')
    log "Sprints: ${cnt}"
    for f in "$SPRINTS_DIR"/*.status.json; do
      [[ -f "$f" ]] || continue
      local sid st stitle
      sid=$(python3 -c "import json; print(json.load(open('$f')).get('id','?'))" 2>/dev/null)
      st=$(python3 -c  "import json; print(json.load(open('$f')).get('status','?'))" 2>/dev/null)
      stitle=$(python3 -c "import json; print(json.load(open('$f')).get('title',''))" 2>/dev/null)
      if [[ -n "$stitle" ]]; then
        echo -e "  ${G}${stitle}${N} — ${st} (${sid})"
      else
        echo -e "  ${G}${sid}${N} — ${st}"
      fi
    done
  else
    warn "Solar Harness 未运行"
    log "启动: $0 [工作目录]"
  fi
  echo ""
}

# ---- Kill ----

kill_harness() {
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log "关闭..."
    # Mark active sprints as interrupted
    for f in "$SPRINTS_DIR"/*.status.json; do
      [[ -f "$f" ]] || continue
      python3 -c "
import json
with open('$f') as fh: d = json.load(fh)
if d.get('status') in ('active','reviewing'):
    d['status'] = 'interrupted'
    with open('$f','w') as fh: json.dump(d, fh, indent=2)
" 2>/dev/null
    done
    tmux kill-session -t "$SESSION_NAME"
    ok "已关闭"
  else
    warn "未运行"
  fi
}

# ---- Extend: 启动第二个四分屏 (Strategy Lab) ----

start_extension() {
  if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    err "Harness 未运行，先启动: solar-harness"
    exit 1
  fi

  # Check if Strategy Lab window already exists
  if tmux list-windows -t "$SESSION_NAME" -F '#{window_name}' 2>/dev/null | grep -q "Strategy Lab"; then
    ok "Window 1 (Strategy Lab) 已存在"
    tmux select-window -t "$SESSION_NAME:Strategy Lab"
    tmux attach -t "$SESSION_NAME"
    return
  fi

  local work_dir="${1:-$(pwd)}"

  # Create window 1
  tmux new-window -t "$SESSION_NAME" -n "Strategy Lab" -c "$work_dir"

  # Split into 4 panes (same layout as window 0)
  tmux split-window -v -t "$SESSION_NAME:Strategy Lab" -c "$work_dir"
  tmux split-window -h -t "$SESSION_NAME:Strategy Lab.0" -c "$work_dir"
  tmux split-window -h -t "$SESSION_NAME:Strategy Lab.2" -c "$work_dir"

  # Launch personas
  local _esc_harness _esc_work
  _esc_harness=$(printf '%q' "$HARNESS_DIR")
  _esc_work=$(printf '%q' "$work_dir")
  sleep 1
  tmux send-keys -t "$SESSION_NAME:Strategy Lab.0" "bash ${_esc_harness}/pane-launcher.sh architect ${_esc_work}" Enter
  sleep 1
  tmux send-keys -t "$SESSION_NAME:Strategy Lab.1" "bash ${_esc_harness}/pane-launcher.sh lab-builder ${_esc_work}" Enter
  sleep 1
  tmux send-keys -t "$SESSION_NAME:Strategy Lab.2" "bash ${_esc_harness}/pane-launcher.sh lab-evaluator ${_esc_work}" Enter
  sleep 1
  tmux send-keys -t "$SESSION_NAME:Strategy Lab.3" "bash ${_esc_harness}/pane-launcher.sh observer ${_esc_work}" Enter

  ok "Strategy Lab 四分屏已启动"
  echo ""
  echo "  ┌──────────────┬──────────────┐"
  echo "  │   架构师      │  实验建设者   │"
  echo "  │   architect   │  lab-builder │"
  echo "  ├──────────────┼──────────────┤"
  echo "  │  实验审判官   │   观察者      │"
  echo "  │ lab-evaluator │   observer   │"
  echo "  └──────────────┴──────────────┘"
  echo ""
  tmux attach -t "$SESSION_NAME"
}

# ---- New Sprint ----

new_sprint() {
  local req="$1"
  local sid
  sid=$(date +"sprint-%Y%m%d-%H%M%S")
  ensure_dirs

  local template="$HARNESS_DIR/templates/contract-template-v2.md"
  local title
  title=$(echo "$req" | head -1 | cut -c1-60)
  local created_at
  created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Prefer v2 template if it exists, otherwise fall back to inline
  if [[ -f "$template" ]]; then
    sed \
      -e "s|{{sprint_id}}|${sid}|g" \
      -e "s|{{created_at}}|${created_at}|g" \
      -e "s|{{project_dir}}|$(pwd)|g" \
      -e "s|{{name}}|${title}|g" \
      -e "s|{{description}}|${req}|g" \
      -e "s|{{triggers}}|auto|g" \
      -e "s|{{requirements}}|${req}|g" \
      "$template" > "${SPRINTS_DIR}/${sid}.contract.md"
  else
    # Fallback: inline template (backward compat)
    cat > "${SPRINTS_DIR}/${sid}.contract.md" << EOF
# Sprint Contract — ${sid}
Created: ${created_at}
Status: drafting
Project: $(pwd)

## Requirements

${req}

## Definition of Done

> Planner fills in

- [ ] (criterion 1)
- [ ] (criterion 2)
- [ ] (criterion 3)

## Scope

- In: (planner fills)
- Out: (planner fills)

## Constraints

> Planner fills in

## Implementation Files

> Builder fills in after completion

## Evaluation Dimensions

1. Functional completeness: Done criteria checked
2. Code quality: Error handling, edge cases, security
3. Contract compliance: Within scope
4. Maintainability: Naming, structure
EOF
  fi

  cat > "${SPRINTS_DIR}/${sid}.status.json" << EOF2
{
  "id": "${sid}",
  "title": "${title}",
  "status": "drafting",
  "phase": "spec",
  "created_at": "${created_at}",
  "round": 0,
  "history": [{"ts": "${created_at}", "event": "contract_created", "by": "user"}]
}
EOF2

  # Log phase_init event
  printf '{"ts":"%s","event":"phase_transition","by":"solar-harness","sid":"%s","data":{"from":"none","to":"spec"}}\n' \
    "$created_at" "$sid" >> "${SPRINTS_DIR}/${sid}.events.jsonl" 2>/dev/null || true

  ok "Sprint created: ${sid}"
  log "Contract: ${SPRINTS_DIR}/${sid}.contract.md"
  log "Phase: spec"
  log "Next: Planner expands Done criteria"
}

# ---- Wake: 从崩溃恢复 Sprint ----

wake_sprint() {
  local sid="${2:-}"

  # wake --help / wake -h: 打印 usage
  if [[ "$sid" == "--help" || "$sid" == "-h" ]]; then
    echo "Solar Harness — wake: 从崩溃恢复 Sprint"
    echo ""
    echo "用法:"
    echo "  $0 wake              列出所有未完成 Sprint 供选择"
    echo "  $0 wake <sprint-id>  恢复指定 Sprint"
    echo "  $0 wake --help       显示帮助"
    echo ""
    echo "恢复流程:"
    echo "  1. 确保 tmux session 存在 (不存在则重建)"
    echo "  2. 从 events.jsonl 检查幂等性 (防止重复 wake)"
    echo "  3. 从 sprint 状态推导派发目标 (planner/builder/evaluator)"
    echo "  4. 生成 dispatch.md 并派发到对应 pane"
    echo "  5. 记录 wake 事件"
    echo "  6. 确保 coordinator 运行"
    echo ""
    echo "覆盖状态: drafting/active/planning/approved/reviewing/failed_review/interrupted"
    return 0
  fi

  if [[ -z "$sid" ]]; then
    # 无参数时列出所有未完成 sprint
    echo ""
    ok "未完成 Sprint 列表:"
    echo ""
    local found=0
    for f in "$SPRINTS_DIR"/*.status.json; do
      [[ -f "$f" ]] || continue
      local fst fstitle fstid
      fst=$(python3 -c "import json; print(json.load(open('$f')).get('status',''))" 2>/dev/null)
      case "$fst" in
        passed|done|failed|eval_pass) continue ;;
      esac
      fstid=$(python3 -c "import json; print(json.load(open('$f')).get('id',''))" 2>/dev/null)
      fstitle=$(python3 -c "import json; t=json.load(open('$f')).get('title',''); print(t[:50])" 2>/dev/null)
      echo -e "  ${G}${fstid}${N}  ${fst}  ${fstitle}"
      found=$((found + 1))
    done
    echo ""
    if [[ "$found" -eq 0 ]]; then
      warn "无活跃 Sprint"
    else
      log "用法: $0 wake <sprint-id>"
    fi
    return 0
  fi

  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || { err "Sprint 不存在: $sid"; exit 1; }

  local st
  st=$(python3 -c "import json; print(json.load(open('$sf')).get('status',''))" 2>/dev/null)
  case "$st" in
    passed|done|failed|eval_pass)
      ok "Sprint ${sid} 已完成 (${st})，无需恢复"
      return 0
      ;;
  esac

  log "恢复 Sprint: ${sid} (当前状态: ${st})"

  # Step 1: 确保 tmux session 存在
  if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    warn "tmux session 不存在，重建..."
    # 用当前目录启动 (不 attach)
    local work_dir
    work_dir=$(grep '^Project:' "$SPRINTS_DIR/${sid}.contract.md" 2>/dev/null | sed 's/^Project:[[:space:]]*//' || echo "$HOME")
    [[ -z "$work_dir" ]] && work_dir="$HOME"

    # 重建 4-pane 布局 (后台)
    tmux new-session -d -s "$SESSION_NAME" -c "$work_dir"
    tmux split-window -v -t "$SESSION_NAME" -c "$work_dir"
    tmux split-window -h -t "$SESSION_NAME:0.0" -c "$work_dir"
    tmux split-window -h -t "$SESSION_NAME:0.2" -c "$work_dir"
    tmux set-option -t "$SESSION_NAME" mouse on
    sleep 1

    # 启动各 pane (D5 sprint-20260502-191700: 路径转义)
    local _esc_h _esc_w
    _esc_h=$(printf '%q' "$HARNESS_DIR")
    _esc_w=$(printf '%q' "$work_dir")
    tmux send-keys -t "$SESSION_NAME:0.0" "bash ${_esc_h}/pane-launcher.sh planner ${_esc_w}" Enter
    sleep 1
    tmux send-keys -t "$SESSION_NAME:0.1" "bash ${_esc_h}/pane-launcher.sh builder ${_esc_w}" Enter
    sleep 1
    tmux send-keys -t "$SESSION_NAME:0.2" "bash ${_esc_h}/pane-launcher.sh evaluator ${_esc_w}" Enter
    sleep 1
    tmux send-keys -t "$SESSION_NAME:0.3" "bash ${_esc_h}/pane-launcher.sh second-builder ${_esc_w}" Enter
    sleep 1

    ok "tmux session 已重建"
  fi

  # Step 2: 幂等检查 — 从 events.jsonl 看是否已经 wake 过且无新活动
  local events_file="$SPRINTS_DIR/${sid}.events.jsonl"
  if [[ -f "$events_file" ]]; then
    local last_event
    last_event=$(tail -1 "$events_file" 2>/dev/null | python3 -c "
import json, sys
line = sys.stdin.read().strip()
if line:
    try:
        d = json.loads(line)
        if d.get('event') == 'waked':
            print('already_waked')
        else:
            print('ok')
    except:
        print('ok')
else:
    print('no_events')
" 2>/dev/null)
    if [[ "$last_event" == "already_waked" ]]; then
      # 检查 events.jsonl 最后修改时间 vs status.json
      local ev_mtime sf_mtime
      ev_mtime=$(stat -f %m "$events_file" 2>/dev/null || echo 0)
      sf_mtime=$(stat -f %m "$sf" 2>/dev/null || echo 0)
      if [[ "$sf_mtime" -le "$ev_mtime" ]]; then
        ok "Sprint ${sid} 已 wake 且无新活动，跳过 (幂等)"
        return 0
      fi
    fi
  fi

  # Step 3: 从最后状态推导派发目标
  local PANE_PLANNER="$SESSION_NAME:0.0"
  local PANE_BUILDER="$SESSION_NAME:0.1"
  local PANE_EVALUATOR="$SESSION_NAME:0.2"
  local target_pane="" target_task=""

  case "$st" in
    drafting)
      target_pane="$PANE_PLANNER"
      target_task="Sprint ${sid} 恢复：请在规划者窗口继续完成 Done 定义。"
      ;;
    active)
      target_pane="$PANE_BUILDER"
      target_task="Sprint ${sid} 恢复：请读取合约并继续实现。cat ~/.solar/harness/sprints/${sid}.contract.md"
      ;;
    planning)
      target_pane="$PANE_EVALUATOR"
      target_task="Sprint ${sid} 恢复：建设者已提交计划，请审批。cat ~/.solar/harness/sprints/${sid}.plan.md"
      ;;
    approved)
      target_pane="$PANE_BUILDER"
      target_task="Sprint ${sid} 恢复：计划已批准，请继续实现。cat ~/.solar/harness/sprints/${sid}.plan.md"
      ;;
    reviewing|ready_for_review)
      target_pane="$PANE_EVALUATOR"
      target_task="Sprint ${sid} 恢复：建设者已提交，请评审。cat ~/.solar/harness/sprints/${sid}.handoff.md"
      ;;
    failed_review)
      target_pane="$PANE_BUILDER"
      target_task="Sprint ${sid} 恢复：评审未通过，请修复。cat ~/.solar/harness/sprints/${sid}.eval.md"
      ;;
    interrupted)
      # 被 kill_harness 打断，改回 reviewing 让 coordinator 重新派发
      python3 -c "
import json, datetime
d = json.load(open('$sf'))
d['status'] = 'reviewing'
d['updated_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
json.dump(d, open('$sf', 'w'), indent = 2)
" 2>/dev/null
      target_pane="$PANE_EVALUATOR"
      target_task="Sprint ${sid} 恢复 (从 interrupted)：请评审。cat ~/.solar/harness/sprints/${sid}.handoff.md"
      ;;
    *)
      warn "未知状态: ${st}，派发给建设者"
      target_pane="$PANE_BUILDER"
      target_task="Sprint ${sid} 恢复：当前状态 ${st}，请检查并继续。"
      ;;
  esac

  # Step 4: 重新生成 dispatch.md 并派发
  cat > "$SPRINTS_DIR/${sid}.dispatch.md" << DISPATCH_EOF
# 协调器恢复指令 (Wake)

${target_task}
DISPATCH_EOF

  local short_cmd="读取并执行指令文件 $SPRINTS_DIR/${sid}.dispatch.md 中的所有步骤"
  tmux send-keys -t "$target_pane" "$short_cmd" Enter 2>/dev/null

  # Step 5: 记录 wake 事件
  bash "$HARNESS_DIR/session.sh" append "$sid" "{\"event\":\"waked\",\"by\":\"wake\",\"data\":{\"from_status\":\"${st}\",\"target_pane\":\"${target_pane}\"}}" 2>/dev/null || true

  ok "Sprint ${sid} 已恢复 → ${target_pane} (从 ${st})"

  # Step 6: 确保 coordinator 在运行
  _ensure_bash4 2>/dev/null || true
  local coord_bash="${BASH4:-bash}"
  if [[ -f "$HARNESS_DIR/.coordinator.pid" ]]; then
    local pid
    pid=$(cat "$HARNESS_DIR/.coordinator.pid")
    if ! kill -0 "$pid" 2>/dev/null; then
      warn "Coordinator PID ${pid} 已死，重启..."
      rm -f "$HARNESS_DIR/.coordinator.pid"
      nohup "$coord_bash" "$HARNESS_DIR/coordinator.sh" >> "$HARNESS_DIR/.coordinator.log" 2>&1 &
      disown 2>/dev/null || true
      ok "Coordinator 重启中..."
    else
      ok "Coordinator 运行中 (PID: ${pid})"
    fi
  else
    warn "无 coordinator PID 文件，启动新的..."
    nohup "$coord_bash" "$HARNESS_DIR/coordinator.sh" >> "$HARNESS_DIR/.coordinator.log" 2>&1 &
    ok "Coordinator 启动中..."
  fi
}

# ---- Atomic Commands (Sprint 20260420-113026) ----

do_handoff_submit() {
  local sid="$1"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  local hf="$SPRINTS_DIR/${sid}.handoff.md"
  rs_exists "$sid" || { err "Sprint not found: $sid"; exit 1; }
  [[ -f "$hf" ]] || { err "handoff.md not found for $sid — 先写 handoff 再提交"; exit 1; }

  local handoff_mtime
  handoff_mtime=$(stat -f %m "$hf" 2>/dev/null || echo 0)

  # Idempotent: same handoff mtime = already submitted
  python3 -c "
import json
d=json.load(open('$sf'))
if d.get('last_handoff_mtime') == float('${handoff_mtime}'):
    exit(0)
exit(1)
" 2>/dev/null && { ok "handoff-submit: $sid already submitted (handoff unchanged)"; return 0; } || true

  rs_transition_with_round_bump "$sid" "reviewing" "implementation_completed" "builder" \
    || { err "handoff-submit 写入失败"; exit 1; }

  # Write last_handoff_mtime as top-level field
  python3 -c "
import json, os, tempfile
sf=os.path.expanduser('$sf')
d=json.load(open(sf))
d['last_handoff_mtime']=float('${handoff_mtime}')
fd,tmp=tempfile.mkstemp(dir=os.path.dirname(sf))
with os.fdopen(fd,'w') as f: json.dump(d,f,indent=2)
os.rename(tmp,sf)
" || true

  bash "$HARNESS_DIR/session.sh" append "$sid" "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"handoff_submitted\",\"by\":\"builder\",\"sid\":\"$sid\"}" 2>/dev/null || true
  type ledger_emit &>/dev/null && ledger_emit "produced" "$sid.handoff.md" "{\"by\":\"builder\"}" 2>/dev/null || true
  ok "handoff-submit: $sid → reviewing"
}

do_plan_verdict() {
  local sid="$1" verdict="$2" reason="${3:-}"
  rs_exists "$sid" || { err "Sprint not found: $sid"; exit 1; }

  local new_status verdict_upper
  case "$verdict" in
    approve|approved) new_status="approved"; verdict_upper="APPROVE" ;;
    reject|rejected)  new_status="active";   verdict_upper="REJECT" ;;
    *) err "verdict 必须是 approve 或 reject"; exit 1 ;;
  esac

  local extra_json
  if [[ -n "$reason" ]]; then
    extra_json=$(python3 -c "import json; print(json.dumps({'verdict':'$verdict_upper','reason':'$reason'}))")
  else
    extra_json="{\"verdict\":\"$verdict_upper\"}"
  fi

  rs_transition "$sid" "$new_status" "plan_reviewed" "evaluator" "$extra_json" \
    || { err "plan-verdict 写入失败"; exit 1; }

  bash "$HARNESS_DIR/session.sh" append "$sid" "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"plan_verdict\",\"by\":\"evaluator\",\"verdict\":\"${verdict}\",\"sid\":\"$sid\"}" 2>/dev/null || true
  ok "plan-verdict: $sid → $new_status"
}

do_eval_verdict() {
  local sid="$1" verdict="$2" reason="${3:-}"
  rs_exists "$sid" || { err "Sprint not found: $sid"; exit 1; }

  local new_status event_name verdict_upper
  case "$verdict" in
    pass|passed)
      new_status="passed"; event_name="eval_passed"; verdict_upper="PASS" ;;
    fail|failed)
      new_status="failed_review"; event_name="eval_failed"; verdict_upper="FAIL" ;;
    *) err "verdict 必须是 pass 或 fail"; exit 1 ;;
  esac

  local extra_json
  if [[ -n "$reason" ]]; then
    extra_json=$(python3 -c "import json; print(json.dumps({'verdict':'$verdict_upper','reason':'$reason'}))")
  else
    extra_json="{\"verdict\":\"$verdict_upper\"}"
  fi

  if [[ "$new_status" == "failed_review" ]]; then
    rs_transition_with_round_bump "$sid" "$new_status" "eval_completed" "evaluator" "$extra_json" \
      || { err "eval-verdict 写入失败"; exit 1; }
  else
    rs_transition "$sid" "$new_status" "eval_completed" "evaluator" "$extra_json" \
      || { err "eval-verdict 写入失败"; exit 1; }
  fi

  bash "$HARNESS_DIR/session.sh" append "$sid" "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"${event_name}\",\"by\":\"evaluator\",\"verdict\":\"${verdict}\",\"sid\":\"$sid\"}" 2>/dev/null || true
  local ledger_event
  if [[ "$new_status" == "passed" ]]; then
    ledger_event="accepted"
  else
    ledger_event="rejected"
  fi
  type ledger_emit &>/dev/null && ledger_emit "$ledger_event" "$sid.handoff.md" "{\"verdict\":\"$verdict_upper\",\"by\":\"evaluator\"}" 2>/dev/null || true
  ok "eval-verdict: $sid → $new_status"
}

do_verify_events() {
  local sid="$1"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  local events_file="$SPRINTS_DIR/${sid}.events.jsonl"
  [[ ! -f "$sf" ]] && { err "Sprint not found: $sid"; exit 1; }

  local issues=0 fixed=0

  # 1. Check history events vs events.jsonl
  local history_events
  history_events=$(python3 -c "
import json
d = json.load(open('$sf'))
for h in d.get('history', []):
    print(h.get('event',''))
" 2>/dev/null)

  if [[ -f "$events_file" ]]; then
    local events_recorded
    events_recorded=$(grep -c '.' "$events_file" 2>/dev/null || echo 0)

    for evt in $history_events; do
      if ! grep -q "\"$evt\"" "$events_file" 2>/dev/null; then
        log "[verify] history has '$evt' but events.jsonl missing it"
        ((issues++))
        bash "$HARNESS_DIR/session.sh" append "$sid" "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"${evt}\",\"by\":\"verify-repair\",\"sid\":\"$sid\",\"source\":\"history_backfill\"}" 2>/dev/null || true
        ((fixed++))
      fi
    done
  else
    log "[verify] no events.jsonl for $sid"
    ((issues++))
  fi

  # 2. Check status consistency
  local st
  st=$(python3 -c "import json; print(json.load(open('$sf')).get('status',''))" 2>/dev/null)
  if [[ "$st" == "passed" ]] && [[ ! -f "$SPRINTS_DIR/${sid}.finalized" ]]; then
    log "[verify] status=passed but no .finalized"
    ((issues++))
  fi

  # 3. Per-round completeness check (Sprint 20260420-191039)
  python3 -c "
import json
d = json.load(open('$sf'))
history = d.get('history', [])
max_round = d.get('round', 0)
for r in range(1, max_round + 1):
    has_impl = any(h.get('event') == 'implementation_completed' and h.get('round') == r for h in history)
    # eval_completed may have round=N (FAIL) or no round key (final PASS)
    has_eval = any(h.get('event') == 'eval_completed' and (h.get('round') == r or (r == max_round and 'round' not in h)) for h in history)
    if not has_impl:
        print(f'WARN: round {r} missing implementation_completed — 补齐: python3 -c ... append history')
    if not has_eval:
        print(f'WARN: round {r} missing eval_completed — 补齐: bash solar-harness.sh eval-verdict $sid pass/fail')
" 2>/dev/null | while IFS= read -r line; do
    log "[verify] $line"
    ((issues++))
  done

  if (( issues == 0 )); then
    ok "verify-events: $sid — 一致 (0 issues)"
  else
    log "verify-events: $sid — ${issues} issues, ${fixed} fixed"
  fi
}

# ---- Main ----

# ---- Capsule / Ledger (sprint-20260503-163542 D5) ----

CAPSULE_FIELDS=("goal" "facts_established" "changes_made" "risks" "open_questions" "required_next_action" "recursion_round" "topology")

do_capsule_show() {
  local sid="$1"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  rs_exists "$sid" || { err "Sprint not found: $sid"; exit 1; }

  local topology round mode
  topology=$(rs_read_field "$sid" "topology")
  [[ -z "$topology" ]] && topology="standard"
  round=$(rs_read_field "$sid" "round")
  [[ -z "$round" ]] && round="0"
  mode=$(rs_read_field "$sid" "mode")
  [[ -z "$mode" ]] && mode="balanced"

  echo "=== Capsule: $sid ==="
  echo "topology: $topology"
  echo "recursion_round: $round"
  echo "mode: $mode"

  # Extract 8 fields from plan/handoff/eval files
  for doc in plan handoff eval; do
    local f="$SPRINTS_DIR/${sid}.${doc}.md"
    [[ -f "$f" ]] || continue
    echo ""
    echo "--- from ${doc}.md ---"
    for field in "${CAPSULE_FIELDS[@]}"; do
      local field_title
      field_title=$(echo "$field" | sed 's/_/ /g')
      # Try ## Section header format (case-insensitive via awk)
      local val
      val=$(awk -v pat="$field_title" 'BEGIN{IGNORECASE=1} tolower($0) ~ "^##+ *"tolower(pat)" *$"{found=1; next} found && /^##+/{exit} found && NF{print}' "$f" | head -3)
      if [[ -z "$val" ]]; then
        # Try yaml frontmatter
        val=$(grep -i "^${field}:" "$f" 2>/dev/null | head -1 | sed "s/^[^:]*:[[:space:]]*//")
      fi
      [[ -n "$val" ]] && echo "  $field: $val"
    done
  done
  echo ""
}

do_ledger_show() {
  local sid="$1"
  type ledger_events_for_sid &>/dev/null || { err "bridge-ledger.sh not loaded"; exit 1; }
  echo "=== Ledger: $sid ==="
  local events
  events=$(ledger_events_for_sid "$sid")
  if [[ -z "$events" ]]; then
    echo "(no events)"
  else
    echo "$events" | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        print(f\"  {d.get('ts','')} [{d.get('event','')}] {d.get('artifact','')}\" + (' → ' + d.get('verdict','') if 'verdict' in d else ''))
    except: pass
"
  fi
}

# ---- Update Contract (Sprint 20260420-082442, D4: 从 case 分支提取为函数) ----

do_update_contract() {
  local usid="${2:-}" section="${3:-}" content="${4:-}"
  if [[ -z "$usid" ]] || [[ -z "$section" ]] || [[ -z "$content" ]]; then
    usid=$(ls "$SPRINTS_DIR"/*.status.json 2>/dev/null | sort | tail -1 | xargs -I{} python3 -c "import json; print(json.load(open('{}'))['id'])" 2>/dev/null)
    [[ -z "$usid" ]] && { err "无活跃 Sprint"; exit 1; }
    err "用法: $0 update-contract <sprint-id> done \"- [ ] 条件1\n- [ ] 条件2\""
    log "当前 Sprint: $usid"
    exit 1
  fi
  local cfile="$SPRINTS_DIR/${usid}.contract.md"
  [[ -f "$cfile" ]] || { err "合约不存在: $cfile"; exit 1; }

  case "$section" in
    done)
      # D7: 用 base64 编码避免 HEREDOC 特殊字符吞参数 (Sprint 20260423-062851)
      local encoded
      encoded=$(printf '%s' "$content" | base64)
      python3 -c "
import re, base64, sys
content = open('$cfile').read()
new_done = base64.b64decode('$encoded').decode('utf-8')
pattern = r'(## (?:Done 定义|Definition of Done)\n\n(?:>.*?\n\n)?)(.*?)(\n## )'
def replacer(m):
    return m.group(1) + new_done + '\n\n' + m.group(3)
result = re.sub(pattern, replacer, content, flags=re.DOTALL)
if result == content:
    print('Warning: update-contract regex did not match, contract unchanged', file=sys.stderr)
    sys.exit(1)
open('$cfile', 'w').write(result)
print('Done 定义已更新')
" 2>/dev/null
      ok "合约更新: $cfile"
      ;;
    scope)
      local encoded
      encoded=$(printf '%s' "$content" | base64)
      python3 -c "
import re, base64
content = open('$cfile').read()
new_scope = base64.b64decode('$encoded').decode('utf-8')
pattern = r'(## 范围\n\n)(.*?)(\n## )'
def replacer(m):
    return m.group(1) + new_scope + '\n\n' + m.group(3)
result = re.sub(pattern, replacer, content, flags=re.DOTALL)
open('$cfile', 'w').write(result)
" 2>/dev/null
      ok "范围已更新"
      ;;
    constraints)
      local encoded
      encoded=$(printf '%s' "$content" | base64)
      python3 -c "
import re, base64
content = open('$cfile').read()
new_c = base64.b64decode('$encoded').decode('utf-8')
pattern = r'(## 约束\n\n>.*?\n\n)(.*?)(\n## )'
def replacer(m):
    return m.group(1) + new_c + '\n\n' + m.group(3)
result = re.sub(pattern, replacer, content, flags=re.DOTALL)
open('$cfile', 'w').write(result)
" 2>/dev/null
      ok "约束已更新"
      ;;
    *)
      err "未知 section: $section (支持: done, scope, constraints)"
      ;;
  esac
}

# Sprint 20260420-090726 D2: 僵尸 cancelled 文件清理
do_clean_corrupted() {
  local apply="${1:-}"
  local qdir="$SPRINTS_DIR/.quarantine/$(date +%Y-%m-%d)"
  local count=0

  echo "扫描僵尸文件..."
  for f in "$SPRINTS_DIR"/sprint-*.status.json; do
    [[ -f "$f" ]] || continue
    local fid
    fid=$(python3 -c "import json; print(json.load(open('$f')).get('id',''))" 2>/dev/null)
    if [[ -z "$fid" ]]; then
      ((count++))
      echo "  僵尸: $(basename "$f")"
      if [[ "$apply" == "--apply" ]]; then
        mkdir -p "$qdir"
        mv "$f" "$qdir/"
        mkdir -p "$SPRINTS_DIR/.quarantine"
        echo "- $(basename "$f") | id为空 | $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SPRINTS_DIR/.quarantine/MANIFEST.md"
      fi
    fi
  done

  if [[ "$apply" != "--apply" ]]; then
    echo "共 ${count} 个僵尸文件 (dry-run, 用 --apply 执行)"
  else
    echo "已隔离 ${count} 个僵尸文件到 .quarantine/"
  fi
}

# sprint-20260503-195627 D3: telemetry stats
TELEMETRY_FILE="${HARNESS_DIR}/telemetry/runs.jsonl"

do_stats_overview() {
  [[ -f "$TELEMETRY_FILE" ]] || { echo "无 telemetry 数据"; return 0; }
  python3 - "$TELEMETRY_FILE" <<'PY'
import json, sys
from collections import Counter
tf = sys.argv[1]
runs = []
with open(tf) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: runs.append(json.loads(line))
        except: pass
if not runs:
    print("无 telemetry 数据"); sys.exit(0)
total = len(runs)
passed = sum(1 for r in runs if r.get("verdict") == "passed")
failed = total - passed
avg_rounds = sum(r.get("rounds", 0) for r in runs) / total
durations = [r.get("duration_sec", 0) for r in runs if r.get("duration_sec", 0) > 0]
avg_dur = sum(durations) / len(durations) if durations else 0
print(f"总览 (最近 {total} 个 sprint 终态)")
print(f"  总数: {total}  |  通过: {passed}  |  失败: {failed}  |  通过率: {passed/total*100:.1f}%")
print(f"  平均轮次: {avg_rounds:.1f}  |  平均耗时: {avg_dur:.0f}s")
print()
topos = {}
for r in runs:
    t = r.get("topology", "standard")
    if t not in topos:
        topos[t] = {"total": 0, "passed": 0, "rounds": [], "dur": []}
    topos[t]["total"] += 1
    if r.get("verdict") == "passed":
        topos[t]["passed"] += 1
    topos[t]["rounds"].append(r.get("rounds", 0))
    d = r.get("duration_sec", 0)
    if d > 0: topos[t]["dur"].append(d)
print("各拓扑通过率:")
for t in sorted(topos.keys()):
    v = topos[t]
    rate = v["passed"] / v["total"] * 100 if v["total"] else 0
    ar = sum(v["rounds"]) / len(v["rounds"]) if v["rounds"] else 0
    ad = sum(v["dur"]) / len(v["dur"]) if v["dur"] else 0
    print(f"  {t:15s}  {v['passed']}/{v['total']}  ({rate:5.1f}%)  avg {ar:.1f}轮  {ad:.0f}s")
fail_counter = Counter()
for r in runs:
    for d in r.get("fail_dones", []):
        fail_counter[d] += 1
if fail_counter:
    print()
    print("Top 5 最常 FAIL 的 Done:")
    for done, cnt in fail_counter.most_common(5):
        print(f"  {done}: {cnt} 次")
PY
}

do_stats_topology() {
  local name="$1"
  [[ -z "$name" ]] && { err "用法: solar-harness stats topology <name>"; exit 1; }
  [[ -f "$TELEMETRY_FILE" ]] || { echo "无 telemetry 数据"; return 0; }
  python3 - "$TELEMETRY_FILE" "$name" <<'PY'
import json, sys
tf, name = sys.argv[1:]
runs = []
with open(tf) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: runs.append(json.loads(line))
        except: pass
filtered = [r for r in runs if r.get("topology") == name]
if not filtered:
    print(f"无 topology={name} 的数据"); sys.exit(0)
total = len(filtered)
passed = sum(1 for r in filtered if r.get("verdict") == "passed")
avg_r = sum(r.get("rounds", 0) for r in filtered) / total
durs = [r.get("duration_sec", 0) for r in filtered if r.get("duration_sec", 0) > 0]
avg_d = sum(durs) / len(durs) if durs else 0
print(f"拓扑: {name}")
print(f"  总数: {total}  |  通过: {passed}  |  通过率: {passed/total*100:.1f}%")
print(f"  平均轮次: {avg_r:.1f}  |  平均耗时: {avg_d:.0f}s")
print()
print("最近 runs:")
for r in filtered[-10:]:
    v = r.get("verdict", "?")
    s = r.get("sid", "?")[:20]
    print(f"  {s}  round={r.get('rounds',0)}  {v}  {r.get('duration_sec',0):.0f}s")
PY
}

do_stats_sprint() {
  local sid="$1"
  [[ -z "$sid" ]] && { err "用法: solar-harness stats sprint <sid>"; exit 1; }
  [[ -f "$TELEMETRY_FILE" ]] || { echo "无 telemetry 数据"; return 0; }
  python3 - "$TELEMETRY_FILE" "$sid" <<'PY'
import json, sys
tf, sid = sys.argv[1:]
with open(tf) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            r = json.loads(line)
            if r.get("sid") == sid:
                for k, v in r.items():
                    print(f"  {k}: {v}")
                sys.exit(0)
        except: pass
print(f"未找到 sid={sid} 的 telemetry 记录")
PY
}

# ---- Main ----

case "${1:-start}" in
  start|"")  start_harness 3 "${2:-$(pwd)}" "${3:-}" ;;
  2)         start_harness 2 "${2:-$(pwd)}" "${3:-}" ;;
  3)         start_harness 3 "${2:-$(pwd)}" "${3:-}" ;;
  status)    show_status ;;
  doctor)    bash "$HARNESS_DIR/doctor.sh" "${2:-}" ;;
  --skip-doctor) start_harness 3 "${2:-$(pwd)}" "--skip-doctor" ;;
  coord-status)
    # Sprint 20260420-082442 D2: 协调器状态诊断
    local pidfile="$HARNESS_DIR/.coordinator.pid"
    local running=false stale_lock=false pid=0 uptime_s=0
    if [[ -f "$pidfile" ]]; then
      pid=$(cat "$pidfile" 2>/dev/null)
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        running=true
        # 计算运行时间
        local start_ts
        start_ts=$(ps -p "$pid" -o lstart= 2>/dev/null)
        if [[ -n "$start_ts" ]]; then
          uptime_s=$(( $(date +%s) - $(date -j -f "%a %b %d %H:%M:%S %Y" "$start_ts" +%s 2>/dev/null || echo $(date +%s)) ))
        fi
      else
        stale_lock=true
      fi
    fi
    python3 -c "
import json
print(json.dumps({
    'running': '$running' == 'true',
    'pid': $pid,
    'uptime_s': $uptime_s,
    'stale_lock': '$stale_lock' == 'true'
}, indent=2))
" 2>/dev/null
    ;;
  # Sprint 20260420-090726 D2: 僵尸文件清理
  clean-corrupted)
    do_clean_corrupted "${2:-}"
    ;;
  kill|stop) kill_harness ;;
  扩展|extend) start_extension "${2:-$(pwd)}" ;;
  sprint)
    [[ -z "${2:-}" ]] && { err "用法: $0 sprint \"需求描述\""; exit 1; }
    new_sprint "$2"
    ;;
  attach)
    tmux attach -t "$SESSION_NAME" 2>/dev/null || err "未运行"
    ;;
  monitor)
    if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
      err "Harness 未运行，先启动: $0"
      exit 1
    fi
    tmux new-window -t "$SESSION_NAME" -n "monitor" -c "$HOME"
    tmux send-keys -t "$SESSION_NAME:monitor" "bash $HARNESS_DIR/monitor.sh" Enter
    ok "monitor 已在独立窗口打开"
    log "Ctrl-b n 切到下一个窗口, Ctrl-b p 切回上一个"
    ;;
  wake)
    wake_sprint "$@"
    ;;
  webhook)
    case "${2:-start}" in
      start)
        if [[ -f "$HARNESS_DIR/.webhook.pid" ]] && kill -0 "$(cat "$HARNESS_DIR/.webhook.pid")" 2>/dev/null; then
          ok "Webhook server 已在运行 (PID: $(cat "$HARNESS_DIR/.webhook.pid"))"
        else
          bun "$HARNESS_DIR/webhook-server.ts" >> "$HARNESS_DIR/.webhook.log" 2>&1 &
          echo $! > "$HARNESS_DIR/.webhook.pid"
          ok "Webhook server 启动 (PID: $!, port: ${HARNESS_PORT:-9876})"
          log "日志: $HARNESS_DIR/.webhook.log"
          log "测试: curl -X POST localhost:${HARNESS_PORT:-9876}/sprint -H 'Content-Type: application/json' -d '{\"title\":\"测试\"}'"
        fi
        ;;
      stop)
        if [[ -f "$HARNESS_DIR/.webhook.pid" ]]; then
          kill "$(cat "$HARNESS_DIR/.webhook.pid")" 2>/dev/null
          rm -f "$HARNESS_DIR/.webhook.pid"
          ok "Webhook server 已停止"
        else
          warn "Webhook server 未运行"
        fi
        ;;
      status)
        if [[ -f "$HARNESS_DIR/.webhook.pid" ]] && kill -0 "$(cat "$HARNESS_DIR/.webhook.pid")" 2>/dev/null; then
          ok "运行中 (PID: $(cat "$HARNESS_DIR/.webhook.pid"))"
          curl -s "http://localhost:${HARNESS_PORT:-9876}/health" 2>/dev/null | python3 -m json.tool 2>/dev/null || true
        else
          warn "未运行"
        fi
        ;;
      *) err "用法: $0 webhook [start|stop|status]" ;;
    esac
    ;;
  plan-verdict)
    [[ -z "${2:-}" ]] && { err "用法: solar-harness plan-verdict <sid> approve|reject [reason]"; exit 1; }
    do_plan_verdict "$2" "${3:-}" "${4:-}"
    ;;
  handoff-submit)
    [[ -z "${2:-}" ]] && { err "用法: solar-harness handoff-submit <sid>"; exit 1; }
    do_handoff_submit "$2"
    ;;
  eval-verdict)
    [[ -z "${2:-}" ]] && { err "用法: solar-harness eval-verdict <sid> pass|fail [reason]"; exit 1; }
    do_eval_verdict "$2" "${3:-}" "${4:-}"
    ;;
  capsule)
    shift
    case "${1:-}" in
      show)
        [[ -z "${2:-}" ]] && { err "用法: solar-harness capsule show <sid>"; exit 1; }
        do_capsule_show "$2"
        ;;
      *)
        echo "Solar Harness Capsule — State Capsule 查看"
        echo "用法: solar-harness capsule show <sid>"
        ;;
    esac
    ;;
  ledger)
    shift
    case "${1:-}" in
      show)
        [[ -z "${2:-}" ]] && { err "用法: solar-harness ledger show <sid>"; exit 1; }
        do_ledger_show "$2"
        ;;
      *)
        echo "Solar Harness Ledger — Bridge Ledger 查看"
        echo "用法: solar-harness ledger show <sid>"
        ;;
    esac
    ;;
  verify-events)
    [[ -z "${2:-}" ]] && { err "用法: solar-harness verify-events <sid>"; exit 1; }
    do_verify_events "$2"
    ;;
  stats)
    shift
    case "${1:-}" in
      "")        do_stats_overview ;;
      topology)  do_stats_topology "${2:-}" ;;
      sprint)    do_stats_sprint "${2:-}" ;;
      *)         echo "用法: solar-harness stats [topology <name>|sprint <sid>]" ;;
    esac
    ;;
  migrate)
    # Sprint 20260422-162434: 一键跨机迁移 + Sprint 20260423-151839 D8
    migrate_subcmd="${2:-help}"
    migrate_script="$HARNESS_DIR/migrate/${migrate_subcmd}.sh"
    if [[ -f "$migrate_script" ]]; then
      bash "$migrate_script" "${@:3}"
    else
      echo "Solar Migrate — 跨机迁移工具"
      echo ""
      echo "用法:"
      echo "  $0 migrate export [--out <path>] [--include-secrets] [--password <pw>] [--push <host:path>] [--cleanup-local]"
      echo "  $0 migrate import <bundle|ssh://host/path> [--password <pw>] [--dry-run] [--install-deps]"
      echo "                   [--skip-diff-backup] [--skip-full-backup] [--keep-local]"
      echo "  $0 migrate verify <bundle> [--password <pw>]"
      echo "  $0 migrate rollback [--diff|--full] [--confirm] [--backup-dir <path>] [--remote <user@host>]"
      echo "  $0 migrate deploy <user@host> [--force]"
      echo "  $0 migrate bootstrap <user@host>"
      echo ""
      echo "子命令: export, import, verify, rollback, deploy, bootstrap"
      exit 1
    fi
    ;;
  deploy)
    # Sprint 20260423-151839 D8: 一键部署
    DEPLOY_TARGET="${2:-}"
    DEPLOY_FORCE="${3:-}"
    [[ -z "$DEPLOY_TARGET" ]] && { err "用法: $0 deploy <user@host> [--force]"; exit 1; }

    SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=accept-new"
    BUNDLE_OUT="/tmp/solar-deploy-$$"
    LATEST_REMOTE="\$HOME/solar-bundles/latest.tar"

    echo ""
    echo "══════════════════════════════════════════════════"
    echo "  Solar Deploy — 一键部署"
    echo "══════════════════════════════════════════════════"
    echo ""

    # Step 1: Check remote doesn't already have ~/.solar (unless --force)
    HAS_SOLAR=$(ssh $SSH_OPTS "$DEPLOY_TARGET" "test -d ~/.solar && echo yes || echo no" 2>/dev/null || echo "error")
    if [[ "$HAS_SOLAR" == "yes" && "$DEPLOY_FORCE" != "--force" ]]; then
      err "目标机已有 ~/.solar, 使用 --force 覆盖"
      exit 1
    fi

    # Step 2: Export + push
    ok "Step 1/4: Export + Push..."
    mkdir -p "$BUNDLE_OUT"
    bash "$HARNESS_DIR/migrate/export.sh" --out "$BUNDLE_OUT" "${@:4}" 2>&1
    DEPLOY_TAR=$(ls -t "$BUNDLE_OUT"/solar-bundle-*.tar 2>/dev/null | head -1)
    if [[ -z "$DEPLOY_TAR" ]]; then
      err "Export 失败: 未找到 bundle"
      rm -rf "$BUNDLE_OUT"
      exit 1
    fi

    # Push to remote
    ok "Step 2/4: Push bundle..."
    ssh $SSH_OPTS "$DEPLOY_TARGET" "mkdir -p ~/solar-bundles" 2>/dev/null
    if command -v rsync &>/dev/null; then
      rsync --partial --append --progress "$DEPLOY_TAR" "${DEPLOY_TARGET}:${LATEST_REMOTE}" 2>&1
      rsync --partial --append --progress "${DEPLOY_TAR}.sha256" "${DEPLOY_TARGET}:${LATEST_REMOTE}.sha256" 2>&1
    else
      scp $SSH_OPTS "$DEPLOY_TAR" "${DEPLOY_TARGET}:${LATEST_REMOTE}" 2>/dev/null
      scp $SSH_OPTS "${DEPLOY_TAR}.sha256" "${DEPLOY_TARGET}:${LATEST_REMOTE}.sha256" 2>/dev/null
    fi
    rm -rf "$BUNDLE_OUT"

    # Step 3: Remote import
    ok "Step 3/4: Remote import..."
    ssh $SSH_OPTS "$DEPLOY_TARGET" "bash -lc 'solar-harness migrate import ~/solar-bundles/latest.tar'" 2>&1
    IMPORT_EXIT=$?

    if [[ $IMPORT_EXIT -ne 0 ]]; then
      err "远程 import 失败 (exit=$IMPORT_EXIT)"
      exit 1
    fi

    # Step 4: Remote doctor
    ok "Step 4/4: Remote doctor..."
    ssh $SSH_OPTS "$DEPLOY_TARGET" "bash -lc 'solar-harness doctor'" 2>&1
    DOCTOR_EXIT=$?

    if [[ $DOCTOR_EXIT -ne 0 ]]; then
      warn "远程 doctor 检查失败, 自动 rollback --diff..."
      ssh $SSH_OPTS "$DEPLOY_TARGET" "bash -lc 'solar-harness migrate rollback --diff --confirm'" 2>&1 || true
      err "部署失败: doctor 检查未通过, 已自动回滚"
      exit 1
    fi

    echo ""
    echo "──────────────────────────────────────────────────"
    ok "一键部署完成: $DEPLOY_TARGET"
    echo "──────────────────────────────────────────────────"
    echo ""
    ;;
  reload)
    # Sprint 20260423-062851 D3: 热加载 coordinator (kill + watchdog 拉新)
    if ! tmux has-session -t solar-harness 2>/dev/null; then
      err "tmux session solar-harness 不存在, 无法 reload"
      exit 1
    fi
    local coord_pidfile="$HARNESS_DIR/.coordinator.pid"
    local old_pid=""
    [[ -f "$coord_pidfile" ]] && old_pid=$(cat "$coord_pidfile" 2>/dev/null)
    if [[ -z "$old_pid" ]] || ! kill -0 "$old_pid" 2>/dev/null; then
      err "Coordinator 未运行 (PID=${old_pid:-empty})"
      exit 1
    fi
    local old_md5
    old_md5=$(md5 -q "$HARNESS_DIR/coordinator.sh" 2>/dev/null || echo 'unknown')
    ok "旧 Coordinator: PID=${old_pid}, md5=${old_md5}"
    kill -TERM "$old_pid" 2>/dev/null || true
    ok "已发送 SIGTERM, 等待 watchdog 拉起新实例..."
    local waited=0 new_pid=""
    while (( waited < 40 )); do
      sleep 1
      waited=$((waited + 1))
      [[ -f "$coord_pidfile" ]] && new_pid=$(cat "$coord_pidfile" 2>/dev/null)
      if [[ -n "$new_pid" ]] && kill -0 "$new_pid" 2>/dev/null && [[ "$new_pid" != "$old_pid" ]]; then
        break
      fi
      # exec 热加载 PID 不变, 但进程是新的 — 检查 md5 log
      if [[ "$new_pid" == "$old_pid" ]] && [[ -f "$HARNESS_DIR/.coordinator.log" ]]; then
        if tail -20 "$HARNESS_DIR/.coordinator.log" 2>/dev/null | grep -q "hot-reload\|coordinator.sh md5="; then
          break
        fi
      fi
    done
    if [[ -z "$new_pid" ]] || ! kill -0 "$new_pid" 2>/dev/null; then
      err "Watchdog 未能拉起新 coordinator (${waited}s), 请手动: bash $HARNESS_DIR/coordinator-watchdog.sh start"
      exit 1
    fi
    local new_md5
    new_md5=$(md5 -q "$HARNESS_DIR/coordinator.sh" 2>/dev/null || echo 'unknown')
    ok "新 Coordinator: PID=${new_pid}, md5=${new_md5}"
    ;;
  update-contract)
    do_update_contract "$@"
    ;;
  help|--help|-h)
    echo "Solar Harness — 多化身协同环境"
    echo ""
    echo "用法:"
    echo "  $0 [start] [工作目录] [--skip-doctor]  启动3化身"
    echo "  $0 2 [工作目录]        启动2化身"
    echo "  $0 status              查看状态"
    echo "  $0 doctor              环境自检"
    echo "  $0 kill                关闭"
    echo "  $0 扩展 | extend       启动第二个四分屏 (Strategy Lab)"
    echo "  $0 sprint \"需求\"       创建 Sprint"
    echo "  $0 wake [sprint-id]  列出未完成 Sprint 或恢复指定 Sprint"
    echo "  $0 wake --help       显示 wake 帮助"
    echo "  $0 reload              热加载 coordinator (kill + watchdog 拉新)"
    echo "  $0 update-contract <id> <section> <content>  更新合约"
    echo "  $0 migrate <export|import|verify|rollback|deploy|bootstrap>  跨机迁移"
    echo "  $0 deploy <user@host> [--force]  一键部署"
    echo "  $0 plan-verdict <sid> approve|reject [reason]  原子审批计划"
    echo "  $0 eval-verdict <sid> pass|fail [reason]  原子评审判定"
    echo "  $0 verify-events <sid>  事件一致性校验"
    echo "  $0 capsule show <sid>   查看 State Capsule 摘要"
    echo "  $0 ledger show <sid>    查看 Bridge Ledger 事件流"
    echo "  $0 attach              重新接入 tmux"
    echo "  $0 monitor             在独立窗口打开 monitor (回退)"
    echo "  $0 webhook [start|stop|status]  管理 Webhook server"
    ;;
  *)
    # If arg looks like a directory, use it as work dir
    if [[ -d "$1" ]]; then
      start_harness 3 "$1"
    else
      err "未知命令: $1"; log "运行 '$0 help'"; exit 1
    fi
    ;;
esac
