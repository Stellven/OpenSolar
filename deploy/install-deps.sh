#!/bin/bash
# Solar 依赖安装脚本 - 从零开始
# 用途: 在新机器上安装所有必需的依赖

set -e

echo "🚀 Solar 依赖安装"
echo ""

# 检查操作系统
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ 此脚本仅支持 macOS"
    exit 1
fi

# 检查 Homebrew
echo "1️⃣  检查 Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "   ⚠️  未找到 Homebrew，正在安装..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "   ✅ Homebrew 已安装"
fi

# 安装 Bun (如果未安装)
echo ""
echo "2️⃣  检查 Bun..."
if ! command -v bun &> /dev/null; then
    echo "   ⚠️  未找到 Bun，正在安装..."
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
else
    echo "   ✅ Bun 已安装: $(bun --version)"
fi

# 安装 CLI 工具
echo ""
echo "3️⃣  安装 CLI 工具..."

# Things 3
if ! command -v things &> /dev/null; then
    echo "   ⚠️  安装 Things CLI..."
    brew install things.sh
else
    echo "   ✅ Things CLI 已安装"
fi

# Remindctl
if ! command -v remindctl &> /dev/null; then
    echo "   ⚠️  安装 Remindctl..."
    brew install keith/formulae/remindctl
else
    echo "   ✅ Remindctl 已安装"
fi

# Himalaya
if ! command -v himalaya &> /dev/null; then
    echo "   ⚠️  安装 Himalaya (邮件 CLI)..."
    brew install himalaya
else
    echo "   ✅ Himalaya 已安装"
fi

# OpenClaw (小爱)
echo ""
echo "4️⃣  检查 OpenClaw..."
if ! command -v openclaw &> /dev/null; then
    echo "   ⚠️  未找到 OpenClaw"
    echo "   📋 请手动安装: https://github.com/openclaw/openclaw"
    echo "   或运行: npm install -g @openclaw/cli"
else
    echo "   ✅ OpenClaw 已安装: $(openclaw --version 2>&1 | head -1)"
fi

# 创建必要目录
echo ""
echo "5️⃣  创建目录结构..."
mkdir -p ~/.claude/skills
mkdir -p ~/.claude/rules
mkdir -p ~/.claude/agents
mkdir -p ~/.claude/hooks
mkdir -p ~/.solar
mkdir -p ~/.gemini/antigravity
echo "   ✅ 目录已创建"

# MCP 配置
echo ""
echo "6️⃣  MCP 配置..."
MCP_CONFIG="$HOME/.gemini/antigravity/mcp_config.json"
if [[ ! -f "$MCP_CONFIG" ]]; then
    echo "   ⚠️  MCP 配置不存在，需要手动配置"
    echo "   📋 位置: $MCP_CONFIG"
    echo "   📋 从源机器复制或参考 deploy/README.md 配置"
else
    echo "   ✅ MCP 配置已存在"
fi

echo ""
echo "✅ 依赖安装完成！"
echo ""
echo "📋 下一步:"
echo "   1. 运行: ./deploy/sync-config.sh <source-host>"
echo "   2. 运行: ./deploy/init-database.sh"
echo "   3. 启动 Claude Code，执行 /solar"
