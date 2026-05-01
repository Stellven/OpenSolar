#!/bin/bash
# Solar L1 安装 fresh-install smoke test
#
# 用法: ./scripts/smoke-install.sh
#
# 行为:
#   1. 创建临时沙盒 (/tmp/solar-smoke-<时间戳>)
#   2. 把当前仓库 cp 到沙盒里
#   3. 在沙盒里跑 ./install.sh, 沙盒的 HOME=沙盒目录 (不污染真实 ~/.claude/)
#   4. 验证沙盒里 .claude/ 和 .solar/ 都建好了
#   5. 输出 PASS/FAIL + 清理选项
#
# 通过条件: install.sh 退出码 0 + 6 项自检全 ✅ + 二次验收 ls 全成功

set -e

SOLAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="/tmp/solar-smoke-$(date +%Y%m%d-%H%M%S)"

echo "🧪 Solar L1 Fresh Install Smoke Test"
echo "===================================="
echo ""
echo "源仓库: $SOLAR_DIR"
echo "沙盒:   $SANDBOX"
echo ""

# Step 1: 准备沙盒 (rsync 拷工作区 — 包括未 commit 的改动)
echo "[1/5] 创建沙盒..."
mkdir -p "$SANDBOX/Solar"
# exclude: 断链 (secretary/openclaw 子链), 大目录, 用户私有数据
rsync -a \
    --exclude='secretary/openclaw' \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='Lollisland' \
    --exclude='Skin-check' \
    --exclude='data' \
    --exclude='*.log' \
    "$SOLAR_DIR/" "$SANDBOX/Solar/" 2>&1 | tail -3
test -f "$SANDBOX/Solar/install.sh" || { echo "❌ 复制失败,install.sh 不在沙盒"; exit 1; }
echo "      ✅ $SANDBOX/Solar 已建 ($(du -sh $SANDBOX/Solar | cut -f1))"

# Step 2: 在沙盒里跑 install.sh, 用沙盒做 HOME
echo ""
echo "[2/5] 跑 install.sh (HOME=$SANDBOX)..."
cd "$SANDBOX/Solar"
INSTALL_OUTPUT=$(HOME="$SANDBOX" ./install.sh 2>&1)
INSTALL_EXIT=$?

echo "$INSTALL_OUTPUT" | tail -20
echo ""

if [ "$INSTALL_EXIT" -ne 0 ]; then
    echo "❌ install.sh 退出码 $INSTALL_EXIT"
    echo ""
    echo "完整输出:"
    echo "$INSTALL_OUTPUT"
    exit 1
fi
echo "      ✅ install.sh 退出码 0"

# Step 3: 检查 6 项自检
echo ""
echo "[3/5] 检查 install.sh 自检结果..."
PASS_COUNT=$(echo "$INSTALL_OUTPUT" | grep -c "  ✅" || true)
FAIL_COUNT=$(echo "$INSTALL_OUTPUT" | grep -c "  ❌" || true)
echo "      ✅ PASS: $PASS_COUNT"
echo "      ❌ FAIL: $FAIL_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "      自检失败,smoke FAIL"
    exit 1
fi
if [ "$PASS_COUNT" -lt 6 ]; then
    echo "      自检 PASS 不足 6 项 ($PASS_COUNT), smoke FAIL"
    exit 1
fi

# Step 4: 二次验收 (独立验证)
echo ""
echo "[4/5] 二次验收 (沙盒文件实际存在性)..."
SANDBOX_HOME="$SANDBOX"
TARGETS=(
    "$SANDBOX_HOME/.claude/CLAUDE.md"
    "$SANDBOX_HOME/.claude/rules"
    "$SANDBOX_HOME/.claude/skills"
    "$SANDBOX_HOME/.claude/agents"
    "$SANDBOX_HOME/.solar"
)
ALL_PASS=true
for t in "${TARGETS[@]}"; do
    if [ -e "$t" ]; then
        echo "      ✅ $t"
    else
        echo "      ❌ $t (不存在)"
        ALL_PASS=false
    fi
done

if [ "$ALL_PASS" = false ]; then
    echo "      smoke FAIL: 二次验收发现缺失"
    exit 1
fi

# Step 5: 内容质量
echo ""
echo "[5/5] 内容质量..."
CLAUDE_SIZE=$(wc -c < "$SANDBOX_HOME/.claude/CLAUDE.md")
RULES_COUNT=$(ls "$SANDBOX_HOME/.claude/rules" 2>/dev/null | wc -l | tr -d ' ')
SKILLS_COUNT=$(ls "$SANDBOX_HOME/.claude/skills" 2>/dev/null | wc -l | tr -d ' ')
AGENTS_COUNT=$(ls "$SANDBOX_HOME/.claude/agents" 2>/dev/null | wc -l | tr -d ' ')

echo "      CLAUDE.md: $CLAUDE_SIZE bytes"
echo "      rules:     $RULES_COUNT 项"
echo "      skills:    $SKILLS_COUNT 项"
echo "      agents:    $AGENTS_COUNT 项"

if [ "$CLAUDE_SIZE" -lt 100 ]; then
    echo "      ❌ CLAUDE.md 太小 ($CLAUDE_SIZE bytes)"
    exit 1
fi

# 全部通过
echo ""
echo "===================================="
echo "✅ Solar L1 Smoke Test PASSED"
echo "===================================="
echo ""
echo "沙盒: $SANDBOX"
echo "  - 跑 \"rm -rf $SANDBOX\" 清理"
echo "  - 或 \"ls $SANDBOX/.claude\" 看安装产物"
echo ""
exit 0
