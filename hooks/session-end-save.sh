#!/bin/bash
# Solar Session End Hook
# 会话结束前强制保存

set -e

SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
PROJECT_DIR="${PWD}"

echo "[SessionEnd] 会话即将结束，保存状态..."

# 1. 保存当前会话状态
if [ -f "$HOME/Solar/core/memory/save-session.ts" ]; then
  bun "$HOME/Solar/core/memory/save-session.ts" session-end 2>/dev/null || true
fi

# 2. 检查是否有未文档化的重要讨论
# 通过检测关键词来判断
if [ -f "$HOME/.solar/solar.db" ]; then
  sqlite3 "$HOME/.solar/solar.db" <<EOF
-- 记录会话结束事件
INSERT INTO evo_memory_semantic (
  memory_id,
  namespace,
  key,
  value,
  source_type,
  confidence
) VALUES (
  'session_end_${SESSION_ID}',
  'system/sessions',
  'session_end_${SESSION_ID}',
  json_object(
    'session_id', '${SESSION_ID}',
    'project_dir', '${PROJECT_DIR}',
    'timestamp', datetime('now'),
    'saved', 1
  ),
  'system',
  1.0
);
EOF
fi

# 3. 自动 git checkpoint (WIP commit)
auto_git_checkpoint() {
  # 检查是否在 git 仓库中
  if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    return
  fi

  # 检查是否有未提交的变更
  if git status --short | grep -q '^'; then
    local timestamp=$(date +"%Y-%m-%d %H:%M")
    local branch=$(git branch --show-current 2>/dev/null || echo "unknown")

    # Stage all changes
    git add -A

    # Commit with WIP message
    git commit -m "WIP: checkpoint @ $timestamp [$branch]

Auto-checkpoint by Solar SessionEnd hook.
Session: ${SESSION_ID}" --no-verify 2>/dev/null || true

    echo "[SessionEnd] ✅ Git checkpoint 已创建"
  else
    echo "[SessionEnd] Git 无需 checkpoint (无变更)"
  fi
}

# 执行自动 checkpoint
auto_git_checkpoint

echo "[SessionEnd] ✓ 会话状态已保存"
