#!/bin/bash
# Solar 安装脚本

set -e

CLAUDE_DIR="$HOME/.claude"

echo "Installing Solar to $CLAUDE_DIR..."

# 创建目录
mkdir -p "$CLAUDE_DIR/agents"
mkdir -p "$CLAUDE_DIR/skills"
mkdir -p "$CLAUDE_DIR/hooks"

# 复制文件
cp -r agents/* "$CLAUDE_DIR/agents/"
cp -r skills/* "$CLAUDE_DIR/skills/" 2>/dev/null || true
cp -r hooks/* "$CLAUDE_DIR/hooks/" 2>/dev/null || true
cp CLAUDE.md "$CLAUDE_DIR/"

# 设置 hook 执行权限
chmod +x "$CLAUDE_DIR/hooks/"*.sh 2>/dev/null || true

echo "Done! Solar installed to $CLAUDE_DIR"
