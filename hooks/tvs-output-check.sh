#!/bin/bash
# TVS 输出检查 Hook
# 检测 Box/Card 输出是否包含 Footer

# 从 stdin 读取工具输出
INPUT=$(cat)

# 检查是否有 Box 字符 (TVS 输出特征)
if echo "$INPUT" | grep -q '┌\|╭\|╔\|┐\|╮\|╗'; then
    # 检查是否有 Footer
    if ! echo "$INPUT" | grep -q 'Powered by TVS'; then
        cat << 'EOF'
{
  "decision": "approve",
  "systemMessage": "⚠️ 【TVS Footer 缺失】检测到 Box/Card 输出但没有 Footer。\n\n请在输出末尾添加:\n────────────────────────────────────────────────────────────────────\nPowered by TVS v0.4.0 · Style: zenwhite.terminal\n可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...\n切换风格: /theme <style> | 查看所有: /theme list"
}
EOF
        exit 0
    fi
fi

echo '{"decision": "approve"}'
