#!/bin/bash
# Solar Storage Check Hook
# 会话结束时检查存储容量并提醒

LOCAL_DIR="$HOME/.solar/trajectories"
CLOUD_DIR="$HOME/Library/CloudStorage/GoogleDrive-haogege1977@gmail.com/我的云端硬盘/Solar/trajectories"
LOCAL_MAX_MB=500
CLOUD_WARN_GB=10

# 获取本地大小
local_mb=$(du -sm "$LOCAL_DIR" 2>/dev/null | cut -f1 || echo "0")

# 获取云盘可用空间
cloud_mount="$HOME/Library/CloudStorage/GoogleDrive-haogege1977@gmail.com"
cloud_free=$(df -g "$cloud_mount" 2>/dev/null | tail -1 | awk '{print $4}' || echo "?")

# 待同步文件数
pending=$(find "$LOCAL_DIR/raw" -name "*.jsonl" -mtime +7 2>/dev/null | wc -l | tr -d ' ')

# 构建消息
warnings=""

if [[ $local_mb -gt $LOCAL_MAX_MB ]]; then
    warnings+="⚠️ 本地轨迹存储超限: ${local_mb}MB/${LOCAL_MAX_MB}MB\\n"
fi

if [[ "$cloud_free" != "?" ]] && [[ $cloud_free -lt $CLOUD_WARN_GB ]]; then
    warnings+="⚠️ Google Drive 空间不足: 剩余 ${cloud_free}GB\\n"
    warnings+="   💡 建议: 扩容或清理数据\\n"
fi

if [[ $pending -gt 20 ]]; then
    warnings+="📦 有 $pending 个旧轨迹待同步\\n"
    warnings+="   运行: ~/.solar/bin/trajectory-archive sync\\n"
fi

# 输出结果
if [[ -n "$warnings" ]]; then
    cat << EOF
{
  "decision": "approve",
  "systemMessage": "【存储容量提醒】\\n${warnings}\\n详情: ~/.solar/bin/trajectory-archive status"
}
EOF
else
    # 静默通过
    echo '{"decision": "approve"}'
fi
