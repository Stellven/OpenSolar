#!/bin/bash
# Solar 配置同步脚本
# 用途: 从 MacBook Pro 同步配置到其他机器

set -e

TARGET="${1:-}"

if [ -z "$TARGET" ]; then
    echo "用法: $0 <target-host>"
    echo "示例: $0 lisihao@192.168.50.194"
    exit 1
fi

echo "🔄 同步 Solar 配置到 $TARGET"

# 同步关键目录
echo "1️⃣  同步 ~/.claude/ 配置..."
rsync -av --delete \
    --exclude=".DS_Store" \
    --exclude="*.log" \
    --exclude="session.md" \
    ~/.claude/skills/ \
    ~/.claude/rules/ \
    ~/.claude/agents/ \
    ~/.claude/hooks/ \
    $TARGET:~/.claude/

# 同步核心文件
echo "2️⃣  同步核心配置文件..."
scp ~/.claude/modes.md \
    ~/.claude/personality-anchor.txt \
    ~/.claude/skills-index.md \
    $TARGET:~/.claude/

# 同步 Solar 项目
echo "3️⃣  同步 Solar 代码..."
rsync -av --delete \
    --exclude=".git" \
    --exclude="node_modules" \
    --exclude=".solar/*.db" \
    ~/Solar/ \
    $TARGET:~/Solar/

# 远程初始化数据库
echo "4️⃣  初始化数据库..."
ssh $TARGET "bash ~/Solar/deploy/init-database.sh"

echo "✅ 同步完成！"
