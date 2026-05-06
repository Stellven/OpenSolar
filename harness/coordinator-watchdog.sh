#!/usr/bin/env bash
# ================================================================
# Solar Harness — Coordinator Watchdog
#
# 每 30 秒检查 coordinator PID 是否存活
# 死了自动 wake → 连续 3 次失败则熔断报警
#
# 用法:
#   coordinator-watchdog.sh start    启动守护 (后台)
#   coordinator-watchdog.sh stop     停止守护
#   coordinator-watchdog.sh status   查看状态
#   coordinator-watchdog.sh check    单次检查 (手动)
#
# @module solar-farm/harness/watchdog
# ================================================================
set -eu

# Bash 4+ 版本守卫
if [[ "${BASH_VERSINFO[0]:-0}" -lt 4 ]]; then
  echo "ERROR: watchdog 需要 bash 4+ (当前: ${BASH_VERSION:-unknown})" >&2
  echo "修复: brew install bash" >&2
  exit 1
fi

HARNESS_DIR="$HOME/.solar/harness"
SPRINTS_DIR="$HARNESS_DIR/sprints"
SESSION_NAME="solar-harness"
WATCHDOG_PID_FILE="$HARNESS_DIR/.watchdog.pid"
WATCHDOG_STATE="$HARNESS_DIR/.watchdog-state"
COORD_PID_FILE="$HARNESS_DIR/.coordinator.pid"

# 熔断阈值
MAX_CONSECUTIVE_FAILURES=3
CHECK_INTERVAL=30

# D5: 死 pane 自愈配置
PANE_CHECK_INTERVAL=10
PANE_DEAD_THRESHOLD=30
# sprint-20260502-172945 D4: 熔断窗口 60s→300s, 阈值 2→3 (合约要求 5min/3 次)
PANE_RESTART_COOLDOWN=300
PANE_MAX_RESTARTS=3
PANE_RESTART_STATE="$HARNESS_DIR/.pane-restart-state"
# sprint-20260503-100705 D5: 熔断自动恢复秒数 (默认 600, 可环境变量覆盖)
AUTO_RECOVER_SECS="${AUTO_RECOVER_SECS:-600}"
# sprint-20260503-100705 D4: 熔断通知限频 (同一 pane 5 分钟窗口最多 1 条)
_last_cb_notify_ts=0

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'
log()  { echo -e "${C}[Watchdog]${N} $(date '+%H:%M:%S') $*"; }
ok()   { echo -e "${G}[Watchdog]${N} $*"; }
warn() { echo -e "${Y}[Watchdog]${N} $*"; }
err()  { echo -e "${R}[Watchdog]${N} $*"; }

# --- D4: 终态 sprint 过滤 (Sprint 20260422-211820) ---
is_actionable_state() {
  case "$1" in
    drafting|active|reviewing|approved) return 0 ;;
    *) return 1 ;;
  esac
}

# --- 读取连续失败计数 ---
get_failure_count() {
  if [[ -f "$WATCHDOG_STATE" ]]; then
    cat "$WATCHDOG_STATE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('consecutive_failures',0))" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

# --- 写入状态 ---
save_state() {
  local failures="$1"
  local last_check
  last_check=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "{\"consecutive_failures\":${failures},\"last_check\":\"${last_check}\"}" > "$WATCHDOG_STATE"
}

# --- 单次检查 ---
do_check() {
  local coord_alive=false

  if [[ -f "$COORD_PID_FILE" ]]; then
    local pid
    pid=$(cat "$COORD_PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
      coord_alive=true
    fi
  fi

  local failures
  failures=$(get_failure_count)

  if $coord_alive; then
    # Coordinator 存活 → 重置失败计数
    if [[ "$failures" -gt 0 ]]; then
      log "Coordinator 恢复正常 (PID: $(cat "$COORD_PID_FILE"))"
    fi
    save_state 0
    return 0
  fi

  # Coordinator 死了
  failures=$((failures + 1))
  save_state "$failures"

  if [[ "$failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]]; then
    err "熔断! Coordinator 连续 ${failures} 次启动失败，停止重启"
    err "手动恢复: bash $HARNESS_DIR/solar-harness.sh wake <sid>"
    # 写事件到活跃 sprint
    local sf
    sf=$(ls -t "$SPRINTS_DIR"/*.status.json 2>/dev/null | head -1)
    if [[ -n "$sf" ]]; then
      local sid
      sid=$(python3 -c "import json; print(json.load(open('$sf')).get('id',''))" 2>/dev/null)
      if [[ -n "$sid" ]]; then
        bash "$HARNESS_DIR/session.sh" append "$sid" "{\"event\":\"watchdog_circuit_break\",\"by\":\"watchdog\",\"data\":{\"failures\":${failures}}}" 2>/dev/null || true
      fi
    fi
    return 1
  fi

  warn "Coordinator 已死! (失败 ${failures}/${MAX_CONSECUTIVE_FAILURES})，尝试重启..."

  # 找活跃 sprint 并 wake (D3: 只 wake 非终态 sprint)
  local active_sid=""
  for f in "$SPRINTS_DIR"/*.status.json; do
    [[ -f "$f" ]] || continue
    local st
    st=$(python3 -c "import json; print(json.load(open('$f')).get('status',''))" 2>/dev/null)
    if is_actionable_state "$st"; then
      active_sid=$(python3 -c "import json; print(json.load(open('$f')).get('id',''))" 2>/dev/null)
      break
    fi
  done

  if [[ -n "$active_sid" ]]; then
    log "Wake Sprint: ${active_sid}"
    bash "$HARNESS_DIR/solar-harness.sh" wake "$active_sid" 2>&1 || true
  else
    log "无非终态 sprint, 跳过 wake"
    bash "$HARNESS_DIR/coordinator.sh" >> "$HARNESS_DIR/.coordinator.log" 2>&1 &
    echo $! > "$COORD_PID_FILE"
    log "Coordinator 重启完成 (PID: $!)"
  fi

  # 记录 watchdog 事件
  if [[ -n "$active_sid" ]]; then
    bash "$HARNESS_DIR/session.sh" append "$active_sid" "{\"event\":\"watchdog_restart\",\"by\":\"watchdog\",\"data\":{\"failure_count\":${failures}}}" 2>/dev/null || true
  fi

  return 0
}

# --- D1: claude 活性检测 (递归 BFS 进程子树) ---
# sprint-20260503-100705: 重写为完整递归，不再限于两级
# 用 pgrep -P BFS 遍历 pane_pid 的整个子进程树，匹配 ^claude
is_claude_alive_in_pane() {
  local pane_pid="$1"
  local queue="$pane_pid" visited=""

  while [[ -n "$queue" ]]; do
    local next_queue=""
    for pid in $queue; do
      case " $visited " in *" $pid "*) continue ;; esac
      visited="$visited $pid"
      # 用 comm= 精确匹配 (comm 是进程名，不含路径和参数)
      local ccmd
      ccmd=$(ps -p "$pid" -o comm= 2>/dev/null) || continue
      case "$ccmd" in
        claude) return 0 ;;
      esac
      # 也检查 args= 前缀 (处理 claude CLI 入口 node .../claude)
      local cargs
      cargs=$(ps -p "$pid" -o args= 2>/dev/null) || continue
      case "$cargs" in
        claude[[:space:]]*|claude) return 0 ;;
      esac
      # BFS: 收集子进程
      local children
      children=$(pgrep -P "$pid" 2>/dev/null) || true
      [[ -n "$children" ]] && next_queue="$next_queue $children"
    done
    queue="$next_queue"
  done

  return 1
}

# --- D5: 死 pane 检测 + 自动重启 ---
# pane 索引 → persona 映射 (只对这些 pane 做自愈)
# Window 0 "Product Delivery"
declare -A PERSONA_PANES=( [0]="pm" [1]="planner" [2]="builder" [3]="evaluator" )
# Window 1 "Strategy Lab" — loaded from farm-layout.json if available
_load_strategy_lab_panes() {
  local layout="$HOME/.solar/harness/farm-layout.json"
  [[ -f "$layout" ]] || return 0
  local n_panes
  n_panes=$(python3 -c "import json; d=json.load(open('$layout')); w1=[w for w in d.get('windows',[]) if w.get('name')=='Strategy Lab']; print(len(w1[0]['panes']) if w1 else 0)" 2>/dev/null) || return 0
  local idx=0
  while [[ "$idx" -lt "$n_panes" ]]; do
    local role
    role=$(python3 -c "import json; d=json.load(open('$layout')); w1=[w for w in d.get('windows',[]) if w.get('name')=='Strategy Lab']; p=w1[0]['panes'][$idx] if w1 else {}; print(p.get('persona',''))" 2>/dev/null) || break
    [[ -n "$role" ]] && PERSONA_PANES["$((idx + 4))"]="$role"
    idx=$((idx + 1))
  done
}
_load_strategy_lab_panes

check_panes() {
  # 检查 tmux session 存在
  tmux has-session -t "$SESSION_NAME" &>/dev/null || return 0

  local now
  now=$(date +%s)

  # 读取 rate-limit 状态: pane_index:last_ts:count (取最后匹配行)
  declare -A pane_state
  if [[ -f "$PANE_RESTART_STATE" ]]; then
    while IFS=':' read -r pidx pts pcount; do
      pane_state["$pidx"]="${pts}:${pcount}"
    done < <(tail -r "$PANE_RESTART_STATE" 2>/dev/null | awk -F: '!seen[$1]++')
  fi

  local pane_output
  pane_output=$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_index} #{pane_current_command} #{pane_dead}' 2>/dev/null) || return 0

  while read -r line; do
    [[ -z "$line" ]] && continue
    local pidx pcmd pdead
    read -r pidx pcmd pdead <<< "$line"

    # remain-on-exit 死 pane 不重启 (用户可手动处理)
    [[ "$pdead" == "1" ]] && continue
    # D1: 只有 claude/node 在白名单 (合约: 非 claude/node → 走活性检测)
    case "$pcmd" in
      claude|node) continue ;;
    esac
    # 未知 pane 索引跳过 (只扫 persona pane 0/1/2)
    [[ -z "${PERSONA_PANES[$pidx]:-}" ]] && continue

    # D1: cmd 不是 claude/node → 递归 BFS 检查 claude 是否在子进程树中
    local pane_pid
    pane_pid=$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_index} #{pane_pid}' 2>/dev/null | awk -v pi="$pidx" '$1==pi{print $2}') || true
    if [[ -n "$pane_pid" ]] && is_claude_alive_in_pane "$pane_pid"; then
      continue
    fi

    local persona="${PERSONA_PANES[$pidx]}"

    # rate-limit 检查
    local last_ts=0 count=0
    if [[ -n "${pane_state[$pidx]:-}" ]]; then
      local parts
      IFS=':' read -r last_ts count <<< "${pane_state[$pidx]}"
    fi

    local elapsed=$(( now - last_ts ))
    # sprint-20260503-100705 D5: 熔断自动恢复 — 超过 AUTO_RECOVER_SECS 清零 count
    if (( elapsed >= AUTO_RECOVER_SECS )); then
      count=0
      echo "${pidx}:${now}:0" >> "$PANE_RESTART_STATE"
    fi
    if (( elapsed < PANE_RESTART_COOLDOWN && count >= PANE_MAX_RESTARTS )); then
      # 超限 → 写警告转人工
      local active_sid=""
      for f in "$SPRINTS_DIR"/*.status.json; do
        [[ -f "$f" ]] || continue
        local fst
        fst=$(python3 -c "import json; print(json.load(open('$f')).get('status',''))" 2>/dev/null)
        case "$fst" in passed|done|failed|eval_pass|cancelled) continue ;; esac
        active_sid=$(python3 -c "import json; print(json.load(open('$f')).get('id',''))" 2>/dev/null)
        break
      done
      if [[ -n "$active_sid" ]]; then
        bash "$HARNESS_DIR/session.sh" append "$active_sid" \
          "{\"event\":\"pane_restart_rate_limited\",\"by\":\"watchdog\",\"data\":{\"pane\":\"$pidx\",\"persona\":\"$persona\",\"count\":$count}}" 2>/dev/null || true
      fi
      warn "Pane $pidx ($persona) rate-limited (${count}/${PANE_MAX_RESTARTS} in ${PANE_RESTART_COOLDOWN}s)"
      # sprint-20260503-100705 D4: 熔断通知限频 — 同一 pane 5 分钟窗口最多 1 条
      local cb_ts
      cb_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
      local cb_now
      cb_now=$(date +%s)
      if (( cb_now - _last_cb_notify_ts >= 300 )); then
        printf '%s\n' "- [ ] [${cb_ts}] [WATCHDOG-CIRCUIT-BREAKER] Pane ${pidx} (${persona}) ${PANE_RESTART_COOLDOWN}s 内 restart ${count}/${PANE_MAX_RESTARTS} 次,已熔断,停止重启,需人工介入" \
          >> "$HARNESS_DIR/PLANNER-INBOX.md"
        printf '%s\tcircuit_breaker\t\twatchdog 熔断 pane=%s persona=%s count=%s window=%ss\n' \
          "$cb_ts" "$pidx" "$persona" "$count" "$PANE_RESTART_COOLDOWN" \
          > "$HARNESS_DIR/.planner-last-notice"
        _last_cb_notify_ts=$cb_now
      fi
      continue
    fi

    # 重启 pane
    log "Pane $pidx ($persona) 异常 (cmd=$pcmd)，重启..."
    tmux send-keys -t "$SESSION_NAME:0.$pidx" C-c 2>/dev/null || true
    sleep 0.5
    # D3/D5 sprint-20260502-191700: 传 work_dir + 路径转义
    local _respawn_workdir="$HOME"
    if [[ "$persona" == "builder" ]] && [[ -d "$HOME/.solar/harness" ]]; then
      _respawn_workdir="$HOME"
    fi
    local _esc_h _esc_w
    _esc_h=$(printf '%q' "$HARNESS_DIR")
    _esc_w=$(printf '%q' "$_respawn_workdir")
    # sprint-20260502-200424 D2: 用绝对路径 bash + 注入完整 PATH
    # 根因: tmux respawn-pane 不继承用户 shell profile, ~/n/bin/claude 找不到 → exit 127
    local _restart_bash="/opt/homebrew/bin/bash"
    [[ -x "$_restart_bash" ]] || _restart_bash="/bin/bash"
    local _user_path="${PATH}"
    for _p in /opt/homebrew/bin /usr/local/bin "$HOME/n/bin" "$HOME/.local/bin" "$HOME/.npm-global/bin" "$HOME/.bun/bin"; do
      [[ -d "$_p" ]] && case ":${_user_path}:" in *":$_p:"*) ;; *) _user_path="$_p:${_user_path}" ;; esac
    done
    tmux respawn-pane -k -t "$SESSION_NAME:0.$pidx" \
      "env HOME='${HOME}' PATH='${_user_path}' ${_restart_bash} ${_esc_h}/start-incarnation.sh $persona ${_esc_w}" 2>/dev/null || {
      warn "respawn-pane 失败, 尝试 send-keys..."
      tmux send-keys -t "$SESSION_NAME:0.$pidx" \
        "env PATH='${_user_path}' ${_restart_bash} ${_esc_h}/start-incarnation.sh $persona ${_esc_w}" Enter
    }
    # sprint-20260502-200424 D2: respawn 后 5 秒验证 pane 活性 (诊断, 不是重试)
    sleep 5
    local _post_respawn_dead
    _post_respawn_dead=$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_index} #{pane_dead}' 2>/dev/null | awk -v pi="$pidx" '$1==pi{print $2}')
    if [[ "${_post_respawn_dead:-0}" == "1" ]]; then
      err "Pane $pidx ($persona) respawn 后立即死亡! (status 127 或其他)"
      echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"respawn_immediate_death\",\"pane\":\"$pidx\",\"persona\":\"$persona\",\"path\":\"${_user_path}\"}" \
        >> "$HARNESS_DIR/logs/pane-exit.jsonl"
    fi

    # 更新 rate-limit
    local new_count=1
    if (( elapsed < PANE_RESTART_COOLDOWN )); then
      new_count=$(( count + 1 ))
    fi
    echo "${pidx}:${now}:${new_count}" >> "$PANE_RESTART_STATE"

    # 写事件
    local active_sid=""
    for f in "$SPRINTS_DIR"/*.status.json; do
      [[ -f "$f" ]] || continue
      local fst
      fst=$(python3 -c "import json; print(json.load(open('$f')).get('status',''))" 2>/dev/null)
      case "$fst" in passed|done|failed|eval_pass|cancelled) continue ;; esac
      active_sid=$(python3 -c "import json; print(json.load(open('$f')).get('id',''))" 2>/dev/null)
      break
    done
    if [[ -n "$active_sid" ]]; then
      bash "$HARNESS_DIR/session.sh" append "$active_sid" \
        "{\"event\":\"pane_auto_restarted\",\"by\":\"watchdog\",\"data\":{\"pane\":\"$pidx\",\"persona\":\"$persona\",\"restart_count\":$new_count}}" 2>/dev/null || true
    fi

    log "Pane $pidx ($persona) 已重启 (restart #${new_count})"
  done <<< "$pane_output"
}

# 清理 pane restart state (启动时)
clean_pane_restart_state() {
  if [[ -f "$PANE_RESTART_STATE" ]]; then
    local now
    now=$(date +%s)
    # 只保留最近 5 分钟的记录
    local tmpf
    tmpf=$(mktemp)
    while IFS=':' read -r pidx ts count; do
      local elapsed=$(( now - ts ))
      (( elapsed < 300 )) && echo "${pidx}:${ts}:${count}" >> "$tmpf"
    done < "$PANE_RESTART_STATE"
    mv "$tmpf" "$PANE_RESTART_STATE"
  fi
}

# --- 后台守护循环 ---
run_watchdog() {
  log "Watchdog 启动 (每 ${CHECK_INTERVAL}s 检查 coordinator, ${PANE_CHECK_INTERVAL}s 检查 panes)"
  save_state 0
  clean_pane_restart_state

  local coord_ticks=0
  local pane_ticks=0

  while true; do
    # Coordinator 检查 (每 CHECK_INTERVAL)
    if (( coord_ticks >= CHECK_INTERVAL )); then
      do_check || {
        err "Watchdog 因熔断退出"
        break
      }
      coord_ticks=0
    fi

    # D5: Pane 检查 (每 PANE_CHECK_INTERVAL)
    if (( pane_ticks >= PANE_CHECK_INTERVAL )); then
      check_panes
      pane_ticks=0
    fi

    sleep 1
    coord_ticks=$((coord_ticks + 1))
    pane_ticks=$((pane_ticks + 1))
  done
}

# --- 命令入口 ---
case "${1:-help}" in
  start)
    # D3: pidfile 自治 — 防多实例 (Sprint 20260422-222017)
    if [[ -f "$WATCHDOG_PID_FILE" ]]; then
      # [HOTFIX 1] removed `local wpid` (case branch, not function)
      wpid=$(cat "$WATCHDOG_PID_FILE" 2>/dev/null)
      if [[ -n "$wpid" ]] && kill -0 "$wpid" 2>/dev/null; then
        ok "Watchdog 已在运行 (PID: ${wpid})"
        exit 0
      fi
      rm -f "$WATCHDOG_PID_FILE"
    fi
    log "启动 Watchdog..."
    run_watchdog >> "$HARNESS_DIR/.watchdog.log" 2>&1 &
    echo $! > "$WATCHDOG_PID_FILE"
    ok "Watchdog 启动完成 (PID: $!)"
    ;;
  stop)
    if [[ -f "$WATCHDOG_PID_FILE" ]]; then
      kill "$(cat "$WATCHDOG_PID_FILE")" 2>/dev/null || true
      rm -f "$WATCHDOG_PID_FILE"
      ok "Watchdog 已停止"
    else
      warn "Watchdog 未运行"
    fi
    ;;
  status)
    echo ""
    if [[ -f "$WATCHDOG_PID_FILE" ]] && kill -0 "$(cat "$WATCHDOG_PID_FILE")" 2>/dev/null; then
      ok "✅ 运行中 PID=$(cat "$WATCHDOG_PID_FILE")"
      # 检测运行模式
      if launchctl list 2>/dev/null | grep -q "com.solar.watchdog"; then
        log "模式: launchd 常驻"
      else
        log "模式: 后台进程"
      fi
    else
      # 检查 launchd 是否在管理
      if launchctl list 2>/dev/null | grep -q "com.solar.watchdog"; then
        warn "Watchdog launchd 已注册但进程未检测到"
      else
        warn "Watchdog 未运行"
      fi
    fi
    if [[ -f "$COORD_PID_FILE" ]]; then
      pid=$(cat "$COORD_PID_FILE")
      if kill -0 "$pid" 2>/dev/null; then
        ok "Coordinator 存活 (PID: ${pid})"
      else
        err "Coordinator 已死 (PID: ${pid} 不存在)"
      fi
    else
      warn "无 Coordinator PID 文件"
    fi
    failures=$(get_failure_count)
    echo "  连续失败: ${failures}/${MAX_CONSECUTIVE_FAILURES}"
    if [[ "$failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]]; then
      err "  状态: 熔断 (需手动恢复)"
    else
      ok "  状态: 正常"
    fi
    echo ""
    ;;
  check)
    do_check
    ;;
  install-launchd)
    # 互斥检查：如果已经在用后台 start 模式，先停掉
    if [[ -f "$WATCHDOG_PID_FILE" ]] && kill -0 "$(cat "$WATCHDOG_PID_FILE")" 2>/dev/null; then
      warn "Watchdog 后台模式运行中 (PID: $(cat "$WATCHDOG_PID_FILE"))，先停止..."
      kill "$(cat "$WATCHDOG_PID_FILE")" 2>/dev/null || true
      rm -f "$WATCHDOG_PID_FILE"
    fi

    local plist_label="com.solar.watchdog"
    local plist_path="$HOME/Library/LaunchAgents/${plist_label}.plist"
    local script_path="$HARNESS_DIR/coordinator-watchdog.sh"

    if [[ -f "$plist_path" ]]; then
      launchctl unload "$plist_path" 2>/dev/null || true
    fi

    mkdir -p "$(dirname "$plist_path")"

    cat > "$plist_path" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${plist_label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${script_path}</string>
        <string>run-daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StartInterval</key>
    <integer>${CHECK_INTERVAL}</integer>
    <key>StandardOutPath</key>
    <string>${HARNESS_DIR}/.watchdog-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>${HARNESS_DIR}/.watchdog-launchd.log</string>
    <key>WorkingDirectory</key>
    <string>${HARNESS_DIR}</string>
</dict>
</plist>
PLIST_EOF

    launchctl load "$plist_path" 2>/dev/null
    # 写 PID 文件（launchd 管理的进程 PID 需要等一下）
    sleep 1
    # 尝试获取 launchd 管理的 watchdog PID
    local daemon_pid
    daemon_pid=$(pgrep -f "coordinator-watchdog.sh run-daemon" 2>/dev/null | head -1 || true)
    if [[ -n "$daemon_pid" ]]; then
      echo "$daemon_pid" > "$WATCHDOG_PID_FILE"
      ok "Watchdog 已通过 launchd 常驻 (PID: ${daemon_pid})"
    else
      ok "Watchdog launchd plist 已加载 (PID 将在首次 check 时写入)"
    fi
    log "plist: ${plist_path}"
    log "日志: ${HARNESS_DIR}/.watchdog-launchd.log"
    log "卸载: $0 uninstall-launchd"
    ;;
  uninstall-launchd)
    local plist_label="com.solar.watchdog"
    local plist_path="$HOME/Library/LaunchAgents/${plist_label}.plist"

    if [[ -f "$plist_path" ]]; then
      launchctl unload "$plist_path" 2>/dev/null || true
      rm -f "$plist_path"
      rm -f "$WATCHDOG_PID_FILE"
      ok "Watchdog launchd 已卸载，plist 已删除"
    else
      warn "无 launchd plist (${plist_path})"
    fi
    ;;
  run-daemon)
    # D3: pidfile 自治 + trap 清理 (Sprint 20260422-222017)
    cleanup_watchdog_pid() {
      if [[ "$(cat "$WATCHDOG_PID_FILE" 2>/dev/null)" == "$$" ]]; then
        rm -f "$WATCHDOG_PID_FILE"
      fi
    }
    trap 'cleanup_watchdog_pid' EXIT TERM
    echo "$$" > "$WATCHDOG_PID_FILE"
    log "Watchdog daemon 启动 (PID: $$, coord 每 ${CHECK_INTERVAL}s, panes 每 ${PANE_CHECK_INTERVAL}s)"
    save_state 0
    clean_pane_restart_state

    # Sprint 20260423-062851 D2: 启动时记录自身 md5 用于热加载自检
    local INIT_MD5
    INIT_MD5=$(md5 -q "$0" 2>/dev/null || md5sum "$0" 2>/dev/null | cut -d' ' -f1 || echo 'unknown')
    log "watchdog md5=${INIT_MD5}"

    local coord_ticks=0
    local pane_ticks=0
    local daemon_loop_count=0

    while true; do
      if (( coord_ticks >= CHECK_INTERVAL )); then
        do_check || {
          err "Watchdog daemon 因熔断退出"
          rm -f "$WATCHDOG_PID_FILE"
          exit 1
        }
        coord_ticks=0
      fi
      if (( pane_ticks >= PANE_CHECK_INTERVAL )); then
        check_panes
        pane_ticks=0
      fi
      sleep 1
      coord_ticks=$((coord_ticks + 1))
      pane_ticks=$((pane_ticks + 1))
      daemon_loop_count=$((daemon_loop_count + 1))

      # Sprint 20260423-062851 D2: md5 自检热加载 (每 60 轮 ≈ 60 秒)
      local hot_reload_tick=${HOT_RELOAD_TICK_OVERRIDE:-60}
      if (( daemon_loop_count % hot_reload_tick == 0 )); then
        local current_md5
        current_md5=$(md5 -q "$0" 2>/dev/null || md5sum "$0" 2>/dev/null | cut -d' ' -f1 || echo 'unknown')
        if [[ "$current_md5" != "$INIT_MD5" ]]; then
          log "[hot-reload] watchdog md5 changed: ${INIT_MD5} → ${current_md5}, exec restart"
          cleanup_watchdog_pid
          exec /opt/homebrew/bin/bash "$0" run-daemon
        fi
      fi
    done
    ;;
  help|--help|-h|"")
    echo "Solar Harness — Coordinator Watchdog"
    echo ""
    echo "用法:"
    echo "  $0 start             启动守护 (后台, 每 ${CHECK_INTERVAL}s 检查)"
    echo "  $0 stop              停止守护"
    echo "  $0 status            查看状态"
    echo "  $0 check             单次手动检查"
    echo "  $0 install-launchd   macOS launchd 常驻 (开机自启)"
    echo "  $0 uninstall-launchd 卸载 launchd 常驻"
    echo "  $0 run-daemon        前台守护模式 (由 launchd 管理)"
    echo ""
    echo "熔断: 连续 ${MAX_CONSECUTIVE_FAILURES} 次失败后停止重启"
    ;;
  *)
    err "未知命令: $1"
    exit 1
    ;;
esac
