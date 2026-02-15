#!/bin/bash
# Solar Trajectory Recorder
# 记录所有工具调用和操作轨迹

TRAJECTORY_DIR="$HOME/.solar/trajectories/raw"
TODAY=$(date +%Y-%m-%d)
SESSION_FILE="$TRAJECTORY_DIR/${TODAY}_session.jsonl"

# 读取工具输入
INPUT=$(cat)

# 解析关键字段
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
TOOL_OUTPUT=$(echo "$INPUT" | jq -c '.tool_output // {}' | head -c 10000)  # 限制大小
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 获取环境信息
GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "")
CWD=$(pwd)

# 构建轨迹记录 (紧凑格式 JSONL)
RECORD=$(jq -c -n \
  --arg ts "$TIMESTAMP" \
  --arg sid "$SESSION_ID" \
  --arg tool "$TOOL_NAME" \
  --argjson input "$TOOL_INPUT" \
  --arg output "$TOOL_OUTPUT" \
  --arg cwd "$CWD" \
  --arg branch "$GIT_BRANCH" \
  --arg commit "$GIT_COMMIT" \
  '{
    timestamp: $ts,
    session_id: $sid,
    event_type: "tool_call",
    tool: {
      name: $tool,
      input: $input,
      output_preview: ($output | if length > 500 then .[0:500] + "..." else . end)
    },
    environment: {
      cwd: $cwd,
      git_branch: $branch,
      git_commit: $commit
    }
  }'
)

# 追加到会话文件
echo "$RECORD" >> "$SESSION_FILE"

# 输出 (不影响工具执行)
echo '{"continue": true}'
