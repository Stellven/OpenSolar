#!/bin/bash
# 小爱远程调用 - 通过 SSH 调用 Mac mini 上的 OpenClaw
# 用法: xiaoai-remote.sh "任务描述"

MAC_MINI="lisihao@192.168.50.194"
OPENCLAW_DIR="/Users/lisihao/.openclaw"

if [ -z "$1" ]; then
    echo "用法: xiaoai-remote.sh \"任务描述\""
    echo "      xiaoai-remote.sh --status    # 检查连接状态"
    exit 1
fi

if [ "$1" == "--status" ]; then
    echo "检查 Mac mini 连接..."
    ping -c 1 -W 2 192.168.50.194 > /dev/null 2>&1 && echo "✅ Mac mini 可达" || echo "❌ Mac mini 不可达"
    ssh -o ConnectTimeout=3 $MAC_MINI "pgrep -f openclaw-gateway > /dev/null" 2>/dev/null && echo "✅ OpenClaw 运行中" || echo "❌ OpenClaw 未运行"
    exit 0
fi

# 远程调用小爱
ssh $MAC_MINI "cd $OPENCLAW_DIR && openclaw agent --local --agent main --message '$*'" 2>&1
