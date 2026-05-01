#!/bin/bash
# Solar 一键部署脚本 — L1 基础安装 (cp 模式)
#
# 行为:
#   1. 备份 ~/.claude/ 现有内容 (如有)
#   2. 把仓库内 CLAUDE.md/rules/skills/agents/hooks/core 复制到 ~/.claude/
#   3. 创建 ~/.solar/ 目录 + 初始化 solar.db (如有 schema)
#   4. 自检 verify
#
# 不做的事 (诚实):
#   - 不 git clone 别的仓库
#   - 不安装 ~/.solar/bin/solar-harness (该工具属于 L2 高级模式, 当前未打包)
#   - 不写入 API keys (用户自己编辑 .env)

set -e

SOLAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SOLAR_HOME="$HOME/.solar"

echo "🚀 Solar 一键部署 (L1 基础安装)"
echo "================================"
echo ""

# Step 1: 创建 ~/.claude/ (如不存在)
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "📁 创建 $CLAUDE_DIR ..."
    mkdir -p "$CLAUDE_DIR"
fi

# Step 2: 备份现有配置 (如存在)
if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    BACKUP_DIR="$CLAUDE_DIR/backup-$(date +%Y%m%d_%H%M%S)"
    echo "💾 备份现有配置到 $BACKUP_DIR ..."
    mkdir -p "$BACKUP_DIR"
    [ -f "$CLAUDE_DIR/CLAUDE.md" ] && cp "$CLAUDE_DIR/CLAUDE.md" "$BACKUP_DIR/"
    for sub in rules skills agents hooks core; do
        [ -d "$CLAUDE_DIR/$sub" ] && cp -r "$CLAUDE_DIR/$sub" "$BACKUP_DIR/" 2>/dev/null || true
    done
fi

# Step 3: 复制各部分
copy_dir() {
    local name="$1" src="$SOLAR_DIR/$1"
    if [ -d "$src" ]; then
        echo "📋 复制 $name ..."
        mkdir -p "$CLAUDE_DIR/$name"
        cp -r "$src/"* "$CLAUDE_DIR/$name/" 2>/dev/null || true
        return 0
    fi
    echo "⚠️  $name 在仓库里不存在,跳过"
    return 1
}

echo "📋 复制 CLAUDE.md ..."
cp "$SOLAR_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"

copy_dir "rules"
copy_dir "skills"
copy_dir "agents"
copy_dir "hooks"
copy_dir "core"

# 给 hooks 加可执行权限
chmod +x "$CLAUDE_DIR/hooks/"*.sh 2>/dev/null || true

# Step 4: 创建 .solar/ + 初始化 db
echo ""
echo "📂 创建 $SOLAR_HOME ..."
mkdir -p "$SOLAR_HOME"

if [ ! -f "$SOLAR_HOME/solar.db" ]; then
    if [ -f "$SOLAR_DIR/core/schema.sql" ]; then
        echo "🗄️  初始化数据库..."
        sqlite3 "$SOLAR_HOME/solar.db" < "$SOLAR_DIR/core/schema.sql"
    else
        echo "ℹ️  无 schema.sql, 跳过 db 初始化 (Solar 启动时会自建)"
    fi
fi

# Step 5: 真实 verify 自检 (不假装 solar-harness 存在)
echo ""
echo "🔍 安装自检"
echo "==========="
PASS=0
FAIL=0

check() {
    local name="$1" cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  ✅ $name"
        PASS=$((PASS+1))
    else
        echo "  ❌ $name"
        FAIL=$((FAIL+1))
    fi
}

check "CLAUDE.md 已就位"         "test -f $CLAUDE_DIR/CLAUDE.md"
check "CLAUDE.md 含 Solar 标识"  "grep -qE 'Solar' $CLAUDE_DIR/CLAUDE.md"
check "~/.claude/rules/ 已就位"  "test -d $CLAUDE_DIR/rules && [ \$(ls $CLAUDE_DIR/rules 2>/dev/null | wc -l) -gt 0 ]"
check "~/.claude/skills/ 已就位" "test -d $CLAUDE_DIR/skills"
check "~/.claude/agents/ 已就位" "test -d $CLAUDE_DIR/agents"
check "~/.solar/ 目录已建"        "test -d $SOLAR_HOME"

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "✅ L1 基础安装完成 ($PASS/6 通过)"
    echo ""
    echo "📝 下一步:"
    echo "   1. (可选) 配置 API keys: cp $SOLAR_DIR/.env.template $SOLAR_DIR/.env"
    echo "      然后编辑填入: ANTHROPIC_API_KEY / ZHIPU_API_KEY / DEEPSEEK_API_KEY"
    echo "   2. 启动 Claude Code"
    echo "   3. 输入 'solar' 看 Solar 启动宣告"
    echo ""
    echo "📚 完整文档: https://github.com/lisihao/Solar"
    echo "📖 用户指南: $SOLAR_DIR/USER-GUIDE.md"
    echo ""
    echo "ℹ️  L2 高级模式 (协调器/Sprint/牛马链路) 当前未打包到本仓库"
    echo "   见 USER-GUIDE.md 第 9 节 \"远程模式 + Codex Pro\""
    exit 0
else
    echo "❌ 安装自检失败 ($FAIL/6 项, $PASS/6 通过)"
    echo ""
    echo "🆘 故障排查:"
    echo "   - 检查仓库完整性: ls $SOLAR_DIR/CLAUDE.md $SOLAR_DIR/rules/ $SOLAR_DIR/skills/"
    echo "   - 检查权限: ls -la $CLAUDE_DIR/"
    echo "   - 重跑前清理: rm -rf $CLAUDE_DIR/CLAUDE.md $CLAUDE_DIR/rules"
    echo "   - 提交 issue: https://github.com/lisihao/Solar/issues"
    exit 1
fi
