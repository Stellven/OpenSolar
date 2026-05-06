#!/bin/bash
# ================================================================
# Solar Harness — Pane 启动器 (无交互阻塞, 统一配置)
#
# D1: 配置统一到 lib/persona-config.sh (sprint-20260502-191700)
# D2: 无 read -r 阻塞, 直接启动
# D4: 无明文 token
#
# @module solar-farm/harness/pane-launcher
# ================================================================
set -eu

PERSONA="${1:?Usage: $0 <planner|builder|evaluator> [workdir]}"
WORK_DIR="${2:-.}"
HARNESS_DIR="$HOME/.solar/harness"

# sprint-20260502-191700 follow-up: --print-config 必须**前置** (同 start-incarnation.sh)
if [[ "$PERSONA" == "--print-config" ]]; then
  bash "$HARNESS_DIR/lib/persona-config.sh" --print-config "${2:?missing persona arg}"
  exit $?
fi

PERSONA_FILE="$HOME/.solar/harness/personas/${PERSONA}.md"
[[ -f "$PERSONA_FILE" ]] || { echo "ERROR: Persona not found: $PERSONA_FILE"; exit 1; }
[[ -d "$WORK_DIR" ]] || { echo "ERROR: Dir not found: $WORK_DIR"; exit 1; }

# 加载共享配置
source "$HARNESS_DIR/lib/persona-config.sh"

# 解析配置
CONFIG=$(get_persona_config "$PERSONA")
eval "$CONFIG"  # 设置 CN, MODEL_FLAG, TOOL_FLAG, DISPLAY_MODEL, STARTUP_TOKEN, PROXY_CHECK

# 设置环境变量
apply_persona_env "$PERSONA"

G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; N='\033[0m'

clear
echo -e "${C}══════════════════════════════════════${N}"
echo -e "${B}  Solar Harness — ${CN}化身${N}"
echo -e "  Persona: ${PERSONA}"
echo -e "  模型: ${Y}${DISPLAY_MODEL}${N}"
echo -e "  工作目录: ${WORK_DIR}"
echo -e "${C}══════════════════════════════════════${N}"
echo ""

# Git worktree 隔离: builder
WORKTREE_DIR=""
if [[ "$PERSONA" == "builder" ]]; then
  source "$HARNESS_DIR/lib/worktree.sh"
  WORKTREE_DIR=$(setup_builder_worktree "$WORK_DIR")
  if [[ -n "$WORKTREE_DIR" ]]; then
    echo -e "  ${G}Git worktree:${N} $WORKTREE_DIR"
    WORK_DIR="$WORKTREE_DIR"
  fi
fi

cd "$WORK_DIR"

# D2: poll 就绪提示符后发送启动 token
TMUX_PANE="${TMUX_PANE:-}"
send_ready_token() {
  local pane="$1" token="$2"
  [[ -z "$pane" ]] && return
  local max_attempts=60 attempt=0
  while (( attempt < max_attempts )); do
    local content
    content=$(tmux capture-pane -t "$pane" -p 2>/dev/null | tail -8)
    if echo "$content" | grep -qE '(╭──|trust.*folder|Allow.*permission|bypass permissions)'; then
      sleep 1
      if [[ -n "$token" ]]; then
        tmux send-keys -t "$pane" "$token" Enter
      else
        tmux send-keys -t "$pane" Enter
      fi
      return 0
    fi
    sleep 1
    ((attempt++))
  done
}
if [[ -n "$TMUX_PANE" ]]; then
  send_ready_token "$TMUX_PANE" "$STARTUP_TOKEN" &>/dev/null &
  AUTO_PID=$!
fi

# 构建启动命令
CLAUDE_CMD="claude --dangerously-skip-permissions"
[[ -n "$MODEL_FLAG" ]] && CLAUDE_CMD="$CLAUDE_CMD $MODEL_FLAG"
[[ -n "$TOOL_FLAG" ]] && CLAUDE_CMD="$CLAUDE_CMD $TOOL_FLAG"

# 退出信号捕获 → pane-exit.jsonl
EXIT_LOG="$HARNESS_DIR/logs/pane-exit.jsonl"
mkdir -p "$(dirname "$EXIT_LOG")" 2>/dev/null || true

set +e
_whisper=$(inject_whisper "$PERSONA")
$CLAUDE_CMD --append-system-prompt "$(cat "$PERSONA_FILE")$_whisper"
CLAUDE_EXIT=$?
set -e

# 写退出记录
{
  LAST_LINES=""
  if [[ -n "$TMUX_PANE" ]]; then
    LAST_LINES=$(tmux capture-pane -t "$TMUX_PANE" -p -S -30 2>/dev/null | tail -30 | python3 -c "import sys; print(sys.stdin.read().replace('\n','\\n')[:2000])" 2>/dev/null || true)
  fi
  python3 -c "
import json, datetime
record = {
    'ts': datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'pane': '${TMUX_PANE:-}',
    'persona': '${PERSONA}',
    'exit_code': ${CLAUDE_EXIT},
    'signal': 'normal' if ${CLAUDE_EXIT} < 128 else 'signal_' + str(${CLAUDE_EXIT} - 128),
    'last_30_lines': '''${LAST_LINES}'''
}
print(json.dumps(record, ensure_ascii=False))
" 2>/dev/null
} >> "$EXIT_LOG" 2>/dev/null || true

[[ -n "${AUTO_PID:-}" ]] && kill "$AUTO_PID" 2>/dev/null || true

# 清理 worktree
if [[ -n "$WORKTREE_DIR" ]]; then
  source "$HARNESS_DIR/lib/worktree.sh"
  cleanup_builder_worktree "$WORKTREE_DIR" "$(cd .. && pwd)"
fi

exec "${SHELL:-/bin/zsh}"
