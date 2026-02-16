#!/bin/bash
# ============================================================
# 小爱洞察分析调度器 v2.0
# 七阶段深度分析 - Cortex 驱动
# 五专家协作 + 互评 + 综合
# ============================================================

set -e

# 加载环境变量
if [ -f "$HOME/.solar/.env" ]; then
    export $(grep -v '^#' "$HOME/.solar/.env" | xargs)
fi

# 配置
INSIGHT_DIR="$HOME/.claude/core/xiaoai-insight"
LOG_FILE="/tmp/xiaoai-insight.log"
ARTIFACTS_DIR="$HOME/.solar/cortex/artifacts"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

show_usage() {
    echo "小爱洞察分析 v2.0 - 七阶段深度分析"
    echo ""
    echo "用法: $0 <分析主题> [请求人]"
    echo ""
    echo "示例:"
    echo "  $0 \"对比 React 和 Vue 的优缺点\""
    echo "  $0 \"分析 LLM Agent 记忆系统最新进展\" \"昊哥\""
    echo ""
    echo "七阶段流程:"
    echo "  P1: 生成大纲提示词"
    echo "  P2: 五专家各自生成大纲"
    echo "  P3: 五专家互评大纲"
    echo "  P4: 综合大纲 + 拆解章节"
    echo "  P5: 逐章写作 + 互评 + 综合"
    echo "  P6: 合并初稿"
    echo "  P7: 生成结构化输出"
    echo ""
    echo "专家团队:"
    echo "  稳健派 (Gemini 2.5 Pro) - 严谨务实、质量把关"
    echo "  探索派 (Gemini 3 Pro)   - 前沿探索、创新方案"
    echo "  审判官 (DeepSeek R1)    - 深度推理、红队验证"
    echo "  创想家 (DeepSeek V3)    - 创意编码、突破常规"
    echo "  智囊 (GLM-5)            - 战略分析、决策支持"
}

# 检查参数
if [ -z "$1" ]; then
    show_usage
    exit 1
fi

TOPIC="$1"
REQUESTER="${2:-unknown}"

echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│  🔬 小爱洞察分析 v2.0                                   │"
echo "├─────────────────────────────────────────────────────────┤"
echo "│  主题: $(echo "$TOPIC" | head -c 45)...                 │"
echo "│  请求人: $REQUESTER                                     │"
echo "│  时间: $(date '+%Y-%m-%d %H:%M:%S')                     │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""

log "开始七阶段洞察分析: $TOPIC"

# 调用 insight-v2.ts
cd "$INSIGHT_DIR"
TASK_ID=$(bun run insight-v2.ts "$TOPIC" "$REQUESTER" 2>&1 | tee -a "$LOG_FILE")

# 检查是否成功
if [ -z "$TASK_ID" ]; then
    log "错误: 任务执行失败"
    exit 1
fi

# 提取任务ID (最后一行)
TASK_ID=$(echo "$TASK_ID" | tail -1)

log "任务完成: $TASK_ID"

# 输出结果位置
echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│  ✅ 分析完成                                            │"
echo "├─────────────────────────────────────────────────────────┤"
echo "│  任务ID: $TASK_ID                                       │"
echo "│                                                         │"
echo "│  📁 文档位置:                                           │"
echo "│  $ARTIFACTS_DIR/$TASK_ID/                               │"
echo "│                                                         │"
echo "│  📊 查看任务详情:                                       │"
echo "│  bun ~/.claude/core/cortex/index.ts task $TASK_ID       │"
echo "│                                                         │"
echo "│  🏆 专家考评:                                           │"
echo "│  bun ~/.claude/core/xiaoai-insight/ceo-evaluator.ts eval│"
echo "└─────────────────────────────────────────────────────────┘"
