#!/bin/bash
# executor-reminder.sh
# UserPromptSubmit hook: 追加提醒让 Claude 记得输出 <Executor> 标签
#
# Claude Code hook 机制:
# - stdout 输出的内容会追加到用户输入的上下文中
# - 用户看不到这个追加内容，但 Claude 能看到

# 输出提醒 (Claude 会在用户输入后看到这段)
cat << 'EOF'

【⚠️ 铁律提醒】
回复的第一行必须是以下格式之一：
- <Executor>self</Executor> (你自己做)
- <Executor>delegate:牛马名</Executor> (让牛马做)

没有这行就开始干活 = 违规！
EOF

exit 0
