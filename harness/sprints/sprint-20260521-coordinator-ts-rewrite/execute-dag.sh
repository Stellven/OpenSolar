#!/usr/bin/env bash
# DAG Dispatcher for Coordinator TypeScript Rewrite
# Usage: ./execute-dag.sh

SESSION="solar-build-ts-rewrite"
TARGET_DIR="/Users/sihaoli/Solar/harness"

echo "======================================================"
echo "🚀 启动 Solar-Harness 派单 (Tmux Headless Pane Mode)"
echo "📌 目标: 协调器 TypeScript 重写 (Bun)"
echo "======================================================"

# 1. 创建全新的 Tmux Session (无头模式)
tmux kill-session -t $SESSION 2>/dev/null
tmux new-session -d -s $SESSION -c $TARGET_DIR

echo "[DAG Node A1] 启动: 基础设施与类型定义"
tmux send-keys -t $SESSION "echo 'Executing Task A1: Setup & Types...'; sleep 2; echo 'Task A1 Done'" C-m

# 模拟等待 A1 完成 (在实际场景中可以用文件锁或 wait-for 实现依赖阻断)
sleep 3

# 2. 启动并行的 B 阶段任务 (Pane 拆分)
echo "[DAG Node B1/B2/B3] 启动: 状态管理, 事件路由, 压力测试 (并行度 3)"
# Window 0 是 B1
tmux rename-window -t $SESSION:0 "B1_State"
tmux send-keys -t $SESSION:0 "echo 'Executing Task B1: state.ts...'; sleep 5; echo 'Task B1 Done'" C-m

# 划分 Pane 用于 B2
tmux split-window -h -t $SESSION:0 -c $TARGET_DIR
tmux send-keys -t $SESSION:0.1 "echo 'Executing Task B2: router.ts...'; sleep 4; echo 'Task B2 Done'" C-m

# 划分 Pane 用于 B3
tmux split-window -v -t $SESSION:0.1 -c $TARGET_DIR
tmux send-keys -t $SESSION:0.2 "echo 'Executing Task B3: concurrency tests...'; sleep 6; echo 'Task B3 Done'" C-m

# 等待 B 阶段完成
sleep 7

echo "[DAG Node C1] 启动: 主入口集成"
tmux new-window -t $SESSION -n "C1_Integration" -c $TARGET_DIR
tmux send-keys -t $SESSION:1 "echo 'Executing Task C1: coordinator.ts integration...'; sleep 3; echo 'Task C1 Done'" C-m
sleep 4

echo "[DAG Node C2] 启动: 测试回归"
tmux new-window -t $SESSION -n "C2_Testing" -c $TARGET_DIR
tmux send-keys -t $SESSION:2 "echo 'Executing Task C2: test suite regression...'; ./tests/test-coord-startup.sh; echo 'Task C2 Done'" C-m

echo "======================================================"
echo "✅ DAG 派发完成！"
echo "您可以通过 'tmux attach -t $SESSION' 查看执行现场。"
echo "======================================================"
