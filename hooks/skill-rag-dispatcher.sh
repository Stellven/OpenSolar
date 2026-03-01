#!/bin/bash
# Skill-RAG Auto-Dispatcher Hook v2.0
# 位置: UserPromptSubmit
# 目的: 每次用户输入时自动检索相关技能，注入上下文提示
# v2.0 2026-03-01 - 升级到三层架构

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

# 检测技术关键词 (触发技能检索)
TECH_KEYWORDS="设计|实现|开发|优化|重构|调试|测试|Python|React|Kubernetes|Docker|安全|API|权衡|决策|分析|根因|k8s|frontend|backend|database"
if ! echo "$USER_INPUT" | grep -qE "$TECH_KEYWORDS"; then
  exit 0
fi

# 调用新的技能分层系统
RESULT=$(cd ~/.claude/core && bun skill-layer-system.ts retrieve "$USER_INPUT" 2>/dev/null || echo "")

# 有匹配结果才输出提示
if [ -n "$RESULT" ] && echo "$RESULT" | grep -q "领域层"; then
  # 提取 Domain 技能
  DOMAIN_SKILLS=$(echo "$RESULT" | grep -A 5 "=== 领域层 ===" | grep "^  " | head -3 | tr '\n' ',' | sed 's/,$//' | sed 's/  //g')

  if [ -n "$DOMAIN_SKILLS" ]; then
    cat << EOF
{
  "type": "skill-rag-hint",
  "message": "💡 检测到技术问题，建议调用技能检索:\n   mcp__skill_retriever__retrieve_layered({ query: \"$USER_INPUT\" })\n\n   相关技能: $DOMAIN_SKILLS"
}
EOF
  fi
fi

exit 0
