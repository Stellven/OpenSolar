#!/bin/bash
# Solar Core 安装脚本
# 安装 Solar v3.0 核心组件

set -e

SOLAR_HOME="${HOME}/.solar"
CLAUDE_HOME="${HOME}/.claude"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}"
echo "  ╭──────────────────────────────────────────────────────────────╮"
echo "  │                                                              │"
echo "  │    ☀️  S O L A R  v3.0    ·    Core Installation             │"
echo "  │                                                              │"
echo "  ╰──────────────────────────────────────────────────────────────╯"
echo -e "${NC}"

# 检查 Bun
if ! command -v bun &> /dev/null; then
    echo -e "${RED}Error: Bun is required but not installed.${NC}"
    echo "Install Bun: curl -fsSL https://bun.sh/install | bash"
    exit 1
fi

echo -e "${BLUE}[1/5]${NC} Creating directories..."
mkdir -p "${SOLAR_HOME}"
mkdir -p "${SOLAR_HOME}/cache"
mkdir -p "${SOLAR_HOME}/plugins/skills"
mkdir -p "${SOLAR_HOME}/plugins/hooks"
mkdir -p "${SOLAR_HOME}/plugins/agents"
mkdir -p "${SOLAR_HOME}/plugins/models"
mkdir -p "${SOLAR_HOME}/plugins/custom"
mkdir -p "${CLAUDE_HOME}/solar"

echo -e "${BLUE}[2/5]${NC} Installing core modules..."
cp -r "${SCRIPT_DIR}/core" "${CLAUDE_HOME}/solar/"
echo -e "${GREEN}  ✓${NC} core/nerve (SQLite + StateManager)"
echo -e "${GREEN}  ✓${NC} core/daemon (Heart)"
echo -e "${GREEN}  ✓${NC} core/plugin (Plugin Host)"

echo -e "${BLUE}[3/5]${NC} Installing CLI tools..."
cp -r "${SCRIPT_DIR}/bin" "${CLAUDE_HOME}/solar/"
chmod +x "${CLAUDE_HOME}/solar/bin/"*
echo -e "${GREEN}  ✓${NC} solar (main CLI)"
echo -e "${GREEN}  ✓${NC} solar-daemon (daemon manager)"

echo -e "${BLUE}[4/5]${NC} Installing templates..."
cp -r "${SCRIPT_DIR}/templates" "${CLAUDE_HOME}/solar/"

# 创建配置文件
if [ ! -f "${SOLAR_HOME}/.env" ]; then
    cp "${SCRIPT_DIR}/templates/env.template" "${SOLAR_HOME}/.env"
    echo -e "${GREEN}  ✓${NC} Created ${SOLAR_HOME}/.env"
else
    echo -e "${YELLOW}  ⚠${NC} Config already exists: ${SOLAR_HOME}/.env"
fi

echo -e "${BLUE}[5/5]${NC} Adding to PATH..."
# 检查是否已添加
EXPORT_LINE='export PATH="$HOME/.claude/solar/bin:$PATH"'

add_to_shell_rc() {
    local rc_file="$1"
    if [ -f "$rc_file" ]; then
        if ! grep -q "/.claude/solar/bin" "$rc_file"; then
            echo "" >> "$rc_file"
            echo "# Solar CLI" >> "$rc_file"
            echo "$EXPORT_LINE" >> "$rc_file"
            echo -e "${GREEN}  ✓${NC} Added to $rc_file"
        else
            echo -e "${YELLOW}  ⚠${NC} Already in $rc_file"
        fi
    fi
}

add_to_shell_rc "${HOME}/.zshrc"
add_to_shell_rc "${HOME}/.bashrc"

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Reload your shell:"
echo "     source ~/.zshrc  # or ~/.bashrc"
echo ""
echo "  2. Configure API keys:"
echo "     nano ${SOLAR_HOME}/.env"
echo ""
echo "  3. Start the daemon:"
echo "     solar daemon start"
echo ""
echo "  4. Check status:"
echo "     solar status"
echo ""
