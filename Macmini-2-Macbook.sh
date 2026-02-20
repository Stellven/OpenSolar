#!/bin/bash
#
# Solar 同步脚本: Mac mini → MacBook
# 用法: ./Macmini-2-Macbook.sh [--dry-run] [--sync]
#
# 作者: Solar
# 创建: 2026-02-20
#

set -e

# ========== 配置 ==========
REMOTE_USER="lisihao"
REMOTE_HOST="192.168.50.194"
REMOTE_TAILSCALE="100.122.223.55"  # 备用 Tailscale 地址

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========== 参数解析 ==========
DRY_RUN=false
SYNC_MODE=false

for arg in "$@"; do
    case $arg in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --sync|-s)
            SYNC_MODE=true
            shift
            ;;
        --help|-h)
            echo "用法: $0 [--dry-run] [--sync]"
            echo ""
            echo "选项:"
            echo "  --dry-run, -n   只显示差异，不实际同步"
            echo "  --sync, -s      执行实际同步"
            echo "  --help, -h      显示帮助"
            exit 0
            ;;
    esac
done

# 如果没有任何参数，默认 dry-run
if [ "$DRY_RUN" = false ] && [ "$SYNC_MODE" = false ]; then
    DRY_RUN=true
fi

# ========== 函数 ==========
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测远程主机连接
detect_remote() {
    log_info "检测远程主机连接..."

    # 先试局域网
    if ssh -o ConnectTimeout=3 -o BatchMode=yes ${REMOTE_USER}@${REMOTE_HOST} "echo ok" &>/dev/null; then
        REMOTE="${REMOTE_USER}@${REMOTE_HOST}"
        log_success "使用局域网地址: ${REMOTE_HOST}"
        return 0
    fi

    # 再试 Tailscale
    if ssh -o ConnectTimeout=3 -o BatchMode=yes ${REMOTE_USER}@${REMOTE_TAILSCALE} "echo ok" &>/dev/null; then
        REMOTE="${REMOTE_USER}@${REMOTE_TAILSCALE}"
        log_success "使用 Tailscale 地址: ${REMOTE_TAILSCALE}"
        return 0
    fi

    log_error "无法连接到 Mac mini (局域网: ${REMOTE_HOST}, Tailscale: ${REMOTE_TAILSCALE})"
    return 1
}

# 显示差异
show_diff() {
    local name="$1"
    local src="$2"
    local dest="$3"
    local extra_opts="$4"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}📦 ${name}${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 统计
    local count=$(rsync -avn $extra_opts "$src" "$dest" 2>/dev/null | grep -c "^" || echo "0")
    echo "源: $src"
    echo "目标: $dest"
    echo ""

    if [ "$count" -gt 2 ]; then
        echo "需同步的文件 (前 30 个):"
        rsync -avn $extra_opts "$src" "$dest" 2>/dev/null | grep -v "^deleting" | grep -v "^sent" | grep -v "^total" | grep -v "^Transfer" | grep -v "^$" | head -30
        local total=$(rsync -avn $extra_opts "$src" "$dest" 2>/dev/null | grep -v "^deleting" | grep -v "^sent" | grep -v "^total" | grep -v "^Transfer" | grep -v "^$" | wc -l | tr -d ' ')
        if [ "$total" -gt 30 ]; then
            echo "... 还有 $((total - 30)) 个文件"
        fi
    else
        log_success "无差异"
    fi
}

# 执行同步
do_sync() {
    local name="$1"
    local src="$2"
    local dest="$3"
    local extra_opts="$4"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}🔄 同步 ${name}${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 确保目标目录存在
    mkdir -p "$dest"

    if rsync -av $extra_opts "$src" "$dest"; then
        log_success "${name} 同步完成"
    else
        log_error "${name} 同步失败"
        return 1
    fi
}

# ========== 主流程 ==========
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         Solar 同步工具: Mac mini → MacBook                      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# 检测连接
detect_remote || exit 1

# ========== 同步项目定义 ==========
# 格式: "名称|源路径(远程)|目标路径(本地)|额外选项"

SYNC_ITEMS=(
    # ══════════════════════════════════════════════════════════
    # 主仓库
    # ══════════════════════════════════════════════════════════
    "Solar|${REMOTE}:~/Solar/|~/Solar/|--exclude='.git/worktrees'"

    # ══════════════════════════════════════════════════════════
    # Claude Code 完整配置
    # ══════════════════════════════════════════════════════════
    # 核心配置
    ".claude/CLAUDE.md|${REMOTE}:~/.claude/CLAUDE.md|~/.claude/CLAUDE.md|"
    ".claude/STATE.md|${REMOTE}:~/.claude/STATE.md|~/.claude/STATE.md|"
    ".claude/rules/|${REMOTE}:~/.claude/rules/|~/.claude/rules/|"
    ".claude/core/|${REMOTE}:~/.claude/core/|~/.claude/core/|"
    ".claude/agents/|${REMOTE}:~/.claude/agents/|~/.claude/agents/|"
    ".claude/skills/|${REMOTE}:~/.claude/skills/|~/.claude/skills/|"
    ".claude/docs/|${REMOTE}:~/.claude/docs/|~/.claude/docs/|"

    # MCP 配置 (重要!)
    ".claude/settings.json|${REMOTE}:~/.claude/settings.json|~/.claude/settings.json|"
    ".claude/settings.local.json|${REMOTE}:~/.claude/settings.local.json|~/.claude/settings.local.json|"

    # 其他配置文件
    ".claude/niumao-anchors.json|${REMOTE}:~/.claude/niumao-anchors.json|~/.claude/niumao-anchors.json|"
    ".claude/stats-cache.json|${REMOTE}:~/.claude/stats-cache.json|~/.claude/stats-cache.json|"
    ".claude/modes.md|${REMOTE}:~/.claude/modes.md|~/.claude/modes.md|"
    ".claude/personality-anchor.txt|${REMOTE}:~/.claude/personality-anchor.txt|~/.claude/personality-anchor.txt|"
    ".claude/skills-index.md|${REMOTE}:~/.claude/skills-index.md|~/.claude/skills-index.md|"

    # hooks 目录 (重要!)
    ".claude/hooks/|${REMOTE}:~/.claude/hooks/|~/.claude/hooks/|"

    # modes 目录
    ".claude/modes/|${REMOTE}:~/.claude/modes/|~/.claude/modes/|"

    # 其他子目录
    ".claude/cache/|${REMOTE}:~/.claude/cache/|~/.claude/cache/|"
    ".claude/data/|${REMOTE}:~/.claude/data/|~/.claude/data/|"
    ".claude/paste-cache/|${REMOTE}:~/.claude/paste-cache/|~/.claude/paste-cache/|"
    ".claude/plugins/|${REMOTE}:~/.claude/plugins/|~/.claude/plugins/|"
    ".claude/insight-reports/|${REMOTE}:~/.claude/insight-reports/|~/.claude/insight-reports/|"

    # ══════════════════════════════════════════════════════════
    # 遗漏的目录 (第3轮检查发现)
    # ══════════════════════════════════════════════════════════
    # 研究文件
    ".claude/research/|${REMOTE}:~/.claude/research/|~/.claude/research/|"

    # 脚本
    ".claude/scripts/|${REMOTE}:~/.claude/scripts/|~/.claude/scripts/|"

    # 技能模板 (重要!)
    ".claude/skill-templates/|${REMOTE}:~/.claude/skill-templates/|~/.claude/skill-templates/|"

    # Solar 子目录 (有 bin, core, templates)
    ".claude/solar/|${REMOTE}:~/.claude/solar/|~/.claude/solar/|"

    # Web 相关
    ".claude/web/|${REMOTE}:~/.claude/web/|~/.claude/web/|"

    # 任务目录
    ".claude/tasks/|${REMOTE}:~/.claude/tasks/|~/.claude/tasks/|"

    # 模板
    ".claude/templates/|${REMOTE}:~/.claude/templates/|~/.claude/templates/|"

    # 智慧库
    ".claude/wisdom/|${REMOTE}:~/.claude/wisdom/|~/.claude/wisdom/|"

    # 待办
    ".claude/todos/|${REMOTE}:~/.claude/todos/|~/.claude/todos/|"

    # Shell 快照
    ".claude/shell-snapshots/|${REMOTE}:~/.claude/shell-snapshots/|~/.claude/shell-snapshots/|"

    # 会话环境
    ".claude/session-env/|${REMOTE}:~/.claude/session-env/|~/.claude/session-env/|"

    # 遥测
    ".claude/telemetry/|${REMOTE}:~/.claude/telemetry/|~/.claude/telemetry/|"

    # 遗漏的文件
    ".claude/SELF_CHECK.md|${REMOTE}:~/.claude/SELF_CHECK.md|~/.claude/SELF_CHECK.md|"
    ".claude/XIAOAI_CHECK.md|${REMOTE}:~/.claude/XIAOAI_CHECK.md|~/.claude/XIAOAI_CHECK.md|"
    ".claude/solar.db|${REMOTE}:~/.claude/solar.db|~/.claude/solar.db|"

    # .claude 内的 .solar 状态目录
    ".claude/.solar/|${REMOTE}:~/.claude/.solar/|~/.claude/.solar/|"

    # 会话数据
    ".claude/history|${REMOTE}:~/.claude/history.jsonl|~/.claude/history.jsonl|"
    ".claude/json|${REMOTE}:~/.claude/.claude.json|~/.claude/.claude.json|"
    ".claude/projects|${REMOTE}:~/.claude/projects/|~/.claude/projects/|"
    ".claude/debug/|${REMOTE}:~/.claude/debug/|~/.claude/debug/|"
    ".claude/file-history/|${REMOTE}:~/.claude/file-history/|~/.claude/file-history/|"
    ".claude/plans/|${REMOTE}:~/.claude/plans/|~/.claude/plans/|"

    # ══════════════════════════════════════════════════════════
    # Solar 数据目录 (数据库、索引、日志)
    # ══════════════════════════════════════════════════════════
    ".solar/|${REMOTE}:~/.solar/|~/.solar/|"

    # ══════════════════════════════════════════════════════════
    # Claude 配置文件 (主目录)
    # ══════════════════════════════════════════════════════════
    ".claude.json|${REMOTE}:~/.claude.json|~/.claude.json|"

    # ══════════════════════════════════════════════════════════
    # OpenClaw 配置 (小爱依赖)
    # ══════════════════════════════════════════════════════════
    ".openclaw/|${REMOTE}:~/.openclaw/|~/.openclaw/|"

    # ══════════════════════════════════════════════════════════
    # Claude Squad (可选)
    # ══════════════════════════════════════════════════════════
    ".claude-squad/|${REMOTE}:~/.claude-squad/|~/.claude-squad/|"

    # ══════════════════════════════════════════════════════════
    # 环境变量 (API Keys 等)
    # ══════════════════════════════════════════════════════════
    ".zshrc|${REMOTE}:~/.zshrc|~/.zshrc|"

    # ══════════════════════════════════════════════════════════
    # MCP 全局配置 (注意路径需要手动修正!)
    # ══════════════════════════════════════════════════════════
    ".mcp.json|${REMOTE}:~/.mcp.json|~/.mcp.json|"

    # ══════════════════════════════════════════════════════════
    # Claude Desktop 配置
    # ══════════════════════════════════════════════════════════
    "Claude Desktop|${REMOTE}:~/Library/Application\ Support/Claude/|~/Library/Application\ Support/Claude/|"

    # ══════════════════════════════════════════════════════════
    # LaunchAgents (后台服务)
    # ══════════════════════════════════════════════════════════
    "LaunchAgents|${REMOTE}:~/Library/LaunchAgents/|~/Library/LaunchAgents/|--include='com.solar.*' --include='ai.openclaw.*' --exclude='*'"
)

# ═════════════════════════════════════════════════════════════
# 可选同步项目 (手动启用)
# ═════════════════════════════════════════════════════════════
# 如需同步 SSH 密钥，取消注释:
# "SSH keys|${REMOTE}:~/.ssh/|~/.ssh/|--include='id_*' --include='known_hosts*' --exclude='*'"
#
# 如需同步 Git 配置，取消注释:
# "Git config|${REMOTE}:~/.gitconfig|~/.gitconfig|"

# ========== 执行 ==========
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${YELLOW}🔍 DRY-RUN 模式 - 只显示差异${NC}"
    echo ""

    for item in "${SYNC_ITEMS[@]}"; do
        IFS='|' read -r name src dest opts <<< "$item"
        show_diff "$name" "$src" "$dest" "$opts"
    done

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}提示: 运行 $0 --sync 执行实际同步${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

elif [ "$SYNC_MODE" = true ]; then
    echo ""
    echo -e "${GREEN}🚀 同步模式 - 开始同步${NC}"
    echo ""

    FAILED=0
    for item in "${SYNC_ITEMS[@]}"; do
        IFS='|' read -r name src dest opts <<< "$item"
        do_sync "$name" "$src" "$dest" "$opts" || FAILED=$((FAILED + 1))
    done

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✅ 全部同步完成！${NC}"
    else
        echo -e "${RED}❌ 有 $FAILED 个项目同步失败${NC}"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

# ========== 同步后提醒 ==========
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                📋 同步内容清单 (第3轮完整版)                     ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║                                                                  ║"
echo "║  📁 ~/Solar/              主代码仓库                            ║"
echo "║                                                                  ║"
echo "║  📁 ~/.claude/            Claude Code 完整配置                  ║"
echo "║     ├── 核心文件                                             ║"
echo "║     │   CLAUDE.md, STATE.md, SELF_CHECK.md, XIAOAI_CHECK.md   ║"
echo "║     │   niumao-anchors.json, personality-anchor.txt            ║"
echo "║     │   modes.md, skills-index.md, solar.db                    ║"
echo "║     ├── 配置目录                                             ║"
echo "║     │   rules/, core/, skills/, agents/, docs/                ║"
echo "║     │   hooks/, modes/, settings.json, settings.local.json    ║"
echo "║     ├── 新增目录 (第3轮)                                     ║"
echo "║     │   research/, scripts/, skill-templates/, solar/         ║"
echo "║     │   web/, tasks/, templates/, wisdom/                     ║"
echo "║     │   todos/, shell-snapshots/, session-env/, telemetry/    ║"
echo "║     └── 会话数据                                             ║"
echo "║         history.jsonl, projects/, debug/, file-history/       ║"
echo "║         plans/, cache/, data/, paste-cache/, plugins/         ║"
echo "║                                                                  ║"
echo "║  📁 ~/.solar/             数据库、索引、日志                    ║"
echo "║     ├── solar.db, memory.db, brain_router.db                  ║"
echo "║     ├── search-index/ (Tantivy)                                ║"
echo "║     ├── cortex/, logs/, insight-reports/                       ║"
echo "║                                                                  ║"
echo "║  📄 ~/.claude.json        Claude 主配置                         ║"
echo "║  📁 ~/.openclaw/          OpenClaw 配置 (小爱依赖)              ║"
echo "║  📁 ~/.claude-squad/      Squad 配置                            ║"
echo "║  📄 ~/.mcp.json           MCP 全局配置 (需修正路径!)            ║"
echo "║  📄 ~/.zshrc              环境变量 (API Keys)                   ║"
echo "║     ├── DEEPSEEK_API_KEY                                      ║"
echo "║     ├── ZHIPU_API_KEY                                         ║"
echo "║     └── GOOGLE_API_KEY                                        ║"
echo "║  📁 ~/Library/Application Support/Claude/  Desktop 配置         ║"
echo "║  📁 ~/Library/LaunchAgents/  后台服务 (18+ 个)                  ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚠️  同步后操作:"
echo "   1. 重新加载环境变量: source ~/.zshrc"
echo "   2. 加载 LaunchAgents: launchctl load ~/Library/LaunchAgents/com.solar.*.plist"
echo "   3. 重启 Claude Code (如果 MCP 配置有变化)"
echo "   4. ⚠️  修正 .mcp.json 中的路径:"
echo "      sed -i '' 's|/Users/lisihao|/Users/sihaoli|g' ~/.mcp.json"
echo ""
