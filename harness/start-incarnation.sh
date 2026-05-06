#!/bin/bash
# ================================================================
# Solar Harness — Incarnation 自动启动器 (无交互, watchdog 用)
#
# D1: 配置统一到 lib/persona-config.sh (sprint-20260502-191700)
# D3: builder worktree 支持
#
# @module solar-farm/harness/start-incarnation
# ================================================================
set -eu

# sprint-20260502-200424 D2: PATH 保底 — watchdog respawn 后 tmux env 不含用户 profile 路径
# claude 在 ~/n/bin, node 在 ~/n/bin 或 /opt/homebrew/bin, git 在 /opt/homebrew/bin 或 /usr/bin
for _p in /opt/homebrew/bin /usr/local/bin "$HOME/n/bin" "$HOME/.local/bin" "$HOME/.npm-global/bin" "$HOME/.bun/bin"; do
  [[ -d "$_p" ]] && case ":${PATH}:" in *":$_p:"*) ;; *) export PATH="$_p:${PATH}" ;; esac
done

PERSONA="${1:?Usage: $0 <planner|builder|evaluator> [workdir]}"
WORK_DIR="${2:-.}"
HARNESS_DIR="$HOME/.solar/harness"

# sprint-20260502-191700 follow-up: --print-config 必须**前置**
# 旧 bug: 先 [[ -f PERSONA_FILE ]] || exit 1 → "--print-config" 当 PERSONA 找文件失败 → 永远进不到 --print-config 分支
# 修复: 把 CLI 接口拦截放最前面
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
eval "$CONFIG"

# 设置环境变量
apply_persona_env "$PERSONA"

# Git worktree 隔离: builder
WORKTREE_DIR=""
ORIGINAL_WORK_DIR="$WORK_DIR"
if [[ "$PERSONA" == "builder" ]]; then
  source "$HARNESS_DIR/lib/worktree.sh"
  WORKTREE_DIR=$(setup_builder_worktree "$WORK_DIR")
  if [[ -n "$WORKTREE_DIR" ]]; then
    WORK_DIR="$WORKTREE_DIR"
  fi
fi

cd "$WORK_DIR"

clear
echo "══════════════════════════════════════"
echo "  Solar Harness — ${CN}化身"
echo "  Persona: ${PERSONA}"
echo "  工作目录: ${WORK_DIR}"
echo "══════════════════════════════════════"
echo ""

# Poll 就绪提示符后发送启动 token
TMUX_PANE="${TMUX_PANE:-}"
send_ready_token() {
  local pane="$1" token="$2"
  [[ -z "$pane" ]] && return
  local max_attempts=60 attempt=0
  while (( attempt < max_attempts )); do
    local content
    content=$(tmux capture-pane -t "$pane" -p 2>/dev/null | tail -8)
    if echo "$content" | grep -qE '(╭──|trust.*folder|Allow.*permission)'; then
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
  cleanup_builder_worktree "$WORKTREE_DIR" "$ORIGINAL_WORK_DIR"
fi

exec "${SHELL:-/bin/zsh}"
