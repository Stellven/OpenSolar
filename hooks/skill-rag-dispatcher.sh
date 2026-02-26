#!/bin/bash
# Skill-RAG Auto-Dispatcher Hook
# 位置: UserPromptSubmit
# 目的: 每次用户输入时自动匹配 Playbook，注入上下文提示
# 修复断头1: 主脑不会自动调 matchPlaybooks()
# v1.0 2026-02-24

set -euo pipefail

# 从 stdin 读取 JSON 格式输入
INPUT=$(cat)
USER_INPUT=$(echo "$INPUT" | jq -r '.user_prompt // ""' 2>/dev/null)

# 空输入或极短输入(≤2字) → 跳过
[ -z "$USER_INPUT" ] && exit 0
[ ${#USER_INPUT} -le 2 ] && exit 0

# 排除系统命令和 slash commands
case "$USER_INPUT" in
  /*)  exit 0 ;;   # slash commands
  @*)  exit 0 ;;   # agent triggers
  solar*|Solar*) exit 0 ;; # 启动词
esac

# 调用 auto-dispatcher hook 模式 (静默失败)
RESULT=$(cd ~/.claude/core/solar-farm && bun auto-dispatcher.ts hook "$USER_INPUT" 2>/dev/null || echo "")

# 有匹配结果才输出
if [ -n "$RESULT" ] && echo "$RESULT" | grep -q "skill-rag-hint"; then
  echo "$RESULT"
fi

exit 0
