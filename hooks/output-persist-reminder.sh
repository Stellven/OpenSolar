#!/bin/bash
# output-persist-reminder.sh
# UserPromptSubmit Hook - 提醒 Solar 每次输出后存储

# 检测用户输入中是否包含需要分析的触发词
TRIGGER_WORDS="分析|总结|设计|评审|调研|对比|方案|报告|评估"

if echo "$1" | grep -qiE "$TRIGGER_WORDS"; then
    echo ""
    echo "💡 [Hook 提醒] 本次输出涉及分析/设计，完成后请存储到知识库"
    echo "   格式: INSERT INTO sys_favorites (title, question, answer, tags, importance)"
    echo "   声明: 📝 已固化: sys_favorites #xxx"
fi
