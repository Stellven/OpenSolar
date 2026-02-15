#!/bin/bash
# Pre-edit hook: 检查文件是否受保护

# 读取工具输入
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# 受保护文件模式
PROTECTED_PATTERNS=(
    ".env"
    ".env.*"
    "*.pem"
    "*.key"
    "*secret*"
    "*credential*"
    "*password*"
)

# 检查是否匹配保护模式
for pattern in "${PROTECTED_PATTERNS[@]}"; do
    if [[ "$(basename "$FILE_PATH")" == $pattern ]]; then
        echo "错误: 文件 $FILE_PATH 受保护，禁止修改" >&2
        exit 2
    fi
done

# 性能敏感文件检查 (2026-02-02 学到的教训)
PERF_SENSITIVE_PATTERNS=(
    "*optimizer*"
    "*operators_v*"
    "*applicability*"
    "*benchmark*"
)

for pattern in "${PERF_SENSITIVE_PATTERNS[@]}"; do
    if [[ "$(basename "$FILE_PATH")" == $pattern ]]; then
        cat << EOF
{
  "decision": "approve",
  "systemMessage": "⚠️ 【性能敏感文件】正在修改 $FILE_PATH\n\n铁律提醒 (来自 2026-02-02 教训):\n1. 修改后必须运行 /benchmark tpch\n2. Applicability Check 禁止用估计值\n3. 对比 baseline，回归 >5% 必须修复"
}
EOF
        exit 0
    fi
done

exit 0
