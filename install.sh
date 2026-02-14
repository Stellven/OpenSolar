#!/bin/bash
# Solar 一键部署脚本

set -e

SOLAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "🚀 Solar 一键部署"
echo "=================="
echo ""

# 创建 .claude 目录（如果不存在）
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "📁 创建 $CLAUDE_DIR 目录..."
    mkdir -p "$CLAUDE_DIR"
fi

# 备份现有配置（如果存在）
if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    echo "💾 备份现有配置..."
    BACKUP_DIR="$CLAUDE_DIR/backup-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    [ -f "$CLAUDE_DIR/CLAUDE.md" ] && cp "$CLAUDE_DIR/CLAUDE.md" "$BACKUP_DIR/"
    [ -d "$CLAUDE_DIR/rules" ] && cp -r "$CLAUDE_DIR/rules" "$BACKUP_DIR/" 2>/dev/null || true
    [ -d "$CLAUDE_DIR/skills" ] && cp -r "$CLAUDE_DIR/skills" "$BACKUP_DIR/" 2>/dev/null || true
    [ -d "$CLAUDE_DIR/agents" ] && cp -r "$CLAUDE_DIR/agents" "$BACKUP_DIR/" 2>/dev/null || true
    [ -d "$CLAUDE_DIR/hooks" ] && cp -r "$CLAUDE_DIR/hooks" "$BACKUP_DIR/" 2>/dev/null || true
    echo "   备份位置: $BACKUP_DIR"
fi

# 复制配置文件
echo "📋 复制配置文件..."
cp "$SOLAR_DIR/CLAUDE.md" "$CLAUDE_DIR/"

# 复制规则
echo "📖 复制规则文件..."
mkdir -p "$CLAUDE_DIR/rules"
cp -r "$SOLAR_DIR/rules/"* "$CLAUDE_DIR/rules/" 2>/dev/null || true

# 复制技能
echo "🛠️  复制技能..."
mkdir -p "$CLAUDE_DIR/skills"
cp -r "$SOLAR_DIR/skills/"* "$CLAUDE_DIR/skills/" 2>/dev/null || true

# 复制 Agents
echo "🤖 复制 Agents..."
mkdir -p "$CLAUDE_DIR/agents"
cp -r "$SOLAR_DIR/agents/"* "$CLAUDE_DIR/agents/" 2>/dev/null || true

# 复制 Hooks
echo "🪝 复制 Hooks..."
mkdir -p "$CLAUDE_DIR/hooks"
cp -r "$SOLAR_DIR/hooks/"* "$CLAUDE_DIR/hooks/" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/hooks/"*.sh 2>/dev/null || true

# 复制核心模块
echo "⚙️  复制核心模块..."
mkdir -p "$CLAUDE_DIR/core"
cp -r "$SOLAR_DIR/core/"* "$CLAUDE_DIR/core/" 2>/dev/null || true

# 创建 .solar 目录
echo "📂 创建 .solar 目录..."
mkdir -p "$HOME/.solar"

# 初始化数据库（如果不存在）
if [ ! -f "$HOME/.solar/solar.db" ]; then
    echo "🗄️  初始化数据库..."
    if [ -f "$SOLAR_DIR/core/schema.sql" ]; then
        sqlite3 "$HOME/.solar/solar.db" < "$SOLAR_DIR/core/schema.sql"
    fi
fi

echo ""
echo "✅ 部署完成！"
echo ""
echo "📝 下一步："
echo "   1. 配置密钥: 编辑 ~/.claude/secrets/ (如果需要)"
echo "   2. 启动 Claude Code"
echo "   3. 输入 'solar' 开始使用"
echo ""
echo "📚 文档: https://github.com/anthropics/solar"
