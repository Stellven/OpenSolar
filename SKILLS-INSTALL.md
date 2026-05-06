# SKILLS-INSTALL — 给 AI Agent 看的 Skills 安装剧本

> 如果你是用户的 AI agent (Claude / Codex / Cursor / Copilot 等), 用户把这个文档贴给你, 你的任务是按下面剧本帮用户在他机器上**自动**安装 Solar 系统所需的 Skills。

---

## 协议

- **Solar 仓库自身只打包 12 个 Solar 自有 skill** (`~/Solar/skills/`), `install.sh` 已经把它们装到 `~/.claude/skills/`
- **真正完整体验需要 1500+ skills**, 来自 Anthropic 官方 + 第三方 + Karpathy 编程技能等
- **本剧本目的**: 让 AI agent 自动 clone 这些 skill 仓库, 不需要用户手动 git
- **执行边界**: 全程不需要 root/sudo, 只在 `~/.claude/skills/` 下操作

---

## 安装前检查

执行前先确认:

```bash
# Solar L1 + L2 已装
test -f ~/.claude/CLAUDE.md && echo "✅ Solar 已装" || echo "❌ 先跑 ~/Solar/install.sh"

# git 可用
which git && git --version | head -1
```

如果 Solar 没装, 先停下让用户跑 `cd ~/Solar && ./install.sh`。

---

## Step 1: Karpathy 编程技能集 (~210 个 skill, 强烈推荐)

**来源**: `forrestchang/andrej-karpathy-skills` — Karpathy 编码哲学 + 工具技能合集
**为什么需要**: Solar `CLAUDE.md` 里的 "Karpathy 编码四原则" 引用这些技能

```bash
# 检查是否已装
if [ -d ~/.claude/skills/python-pro ] || [ -d ~/.claude/skills/code-reviewer ]; then
    echo "✅ Karpathy skills 似乎已装"
else
    cd ~/.claude/skills
    # 临时 clone 到子目录, 然后展开
    git clone --depth=1 https://github.com/forrestchang/andrej-karpathy-skills.git .karpathy-tmp
    cp -r .karpathy-tmp/skills/* ~/.claude/skills/ 2>/dev/null || cp -r .karpathy-tmp/* ~/.claude/skills/
    rm -rf .karpathy-tmp
    echo "✅ Karpathy skills 装好"
fi
```

**预期结果**: `~/.claude/skills/` 增加 ~200 个 skill 目录 (python-pro / code-reviewer / debugger / 等)

**失败处理**:
- `git clone` 失败 → 配代理或换 SSH (`git@github.com:forrestchang/andrej-karpathy-skills.git`)
- 用户在中国大陆 → 试 `https://gitclone.com/github.com/forrestchang/andrej-karpathy-skills.git` 镜像

**通过条件**: `ls ~/.claude/skills/ | wc -l` 输出 ≥ 50 → 进入 Step 2

---

## Step 2: Anthropic 官方 Claude Code Skills (~50 个)

**来源**: Anthropic Claude Code 自带 — 通常用户装 Claude Code 时已经在 `~/.claude/skills/` 或 `/Applications/Claude.app/Contents/Resources/skills/` 里
**为什么需要**: `gstack/Superpowers` 触发词链路依赖

```bash
# 检查 Claude Code 是否已装
which claude || open -a "Claude" 2>/dev/null

# 看 Claude Code 自带 skills 位置
for path in /Applications/Claude.app/Contents/Resources/skills \
            ~/Library/Application\ Support/Claude/skills \
            ~/.config/claude/skills; do
    if [ -d "$path" ]; then
        echo "找到 Claude Code 自带 skills: $path"
        # 软链或复制 (建议软链, 跟 Claude Code 升级同步)
        ln -sf "$path"/* ~/.claude/skills/ 2>/dev/null || cp -r "$path"/* ~/.claude/skills/
    fi
done
```

**通过条件**: `ls ~/.claude/skills/ | grep -E "^(brainstorming|writing-plans|systematic-debugging)$"` 至少命中 1 个

---

## Step 3: gstack 工具集 (网页浏览/QA/部署 等)

**来源**: gstack 是 Solar 自有的扩展, 通过 `~/.claude/skills/gstack/setup` 安装
**为什么需要**: Solar `CLAUDE.md` 的"gstack (核心模块)"章节, 触发词 `/browse` `/review` `/ship` 等都依赖它

```bash
# Solar L1 安装时 gstack 子目录已经在 ~/.claude/skills/gstack/, 只需跑 setup
if [ -f ~/.claude/skills/gstack/setup ]; then
    cd ~/.claude/skills/gstack && ./setup
    echo "✅ gstack 已 setup"
else
    echo "⚠️  ~/.claude/skills/gstack/ 不存在, 先跑 ~/Solar/install.sh"
fi
```

**通过条件**: `~/.claude/skills/gstack/bin/$B` 或 `~/.solar/bin/$B` 可执行

---

## Step 4: Skill Retriever MCP (按场景动态加载 Skill)

**来源**: Solar `core/mcp-servers/skill-retriever/` (已随 install.sh 装到 `~/.claude/core/`)
**为什么需要**: Solar `CLAUDE.md` 的"技能分层检索 (MCP v2.0)"章节, 让 Claude 按用户意图动态拉 skill

```bash
# 注册到 Claude Code MCP
SKILL_MCP=$(find ~/.claude/core ~/.claude/mcp-servers -name "*skill-retriever*" -type d 2>/dev/null | head -1)
if [ -n "$SKILL_MCP" ]; then
    cd "$SKILL_MCP"
    [ -f package.json ] && npm install --silent
    [ -f main.ts ] && claude mcp add skill-retriever -- node $SKILL_MCP/main.js
    echo "✅ skill-retriever MCP 已注册"
fi
```

**通过条件**: `claude mcp list | grep skill-retriever | grep -v Failed` 命中

---

## Step 5: 第三方 Skills (按需选装)

下面是用户**可能**想要的额外 skill 仓库, **AI 应该问用户哪些要装** 不要全装:

| 仓库 | 内容 | 何时装 |
|------|------|-------|
| `anthropics/claude-cookbooks` | API 用法示例 | 用户开发 Claude API 时 |
| `langchain-ai/langgraph-skills` | LangGraph 工作流 skill | 用户做 agent 编排时 |
| `mlflow/mlflow-skills` | ML 实验跟踪 | 用户搞 ML 时 |

```bash
# 询问用户后再装
read -p "要装 LangGraph skills 吗? [y/N] " yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
    git clone --depth=1 https://github.com/langchain-ai/langgraph-skills.git ~/.claude/skills/langgraph 2>&1
fi
```

---

## Step 6: 验收

```bash
echo "=== Solar Skills 安装结果 ==="
TOTAL=$(ls ~/.claude/skills/ 2>/dev/null | wc -l | tr -d ' ')
echo "总 skill 目录: $TOTAL"

# 关键 skill 抽检
for s in python-pro code-reviewer brainstorming writing-plans gstack; do
    [ -d ~/.claude/skills/$s ] && echo "  ✅ $s" || echo "  ❌ $s 缺失"
done

echo ""
if [ "$TOTAL" -ge 50 ]; then
    echo "✅ Skills 安装完成 (≥ 50 个)"
    echo "下一步: 启动 Claude Code, 输入 'solar' 看 Solar 启动宣告"
else
    echo "⚠️ 数量偏少 ($TOTAL < 50), 至少 Step 1 (Karpathy) 应该装"
fi
```

---

## 给 AI agent 的元规则

执行本剧本时:

1. **不擅自装第 5 步可选 skills** — 必须先问用户
2. **不假装成功** — 每步检查 exit code, 失败明确报告
3. **不删用户已有 skill** — 用 `cp -n` 不覆盖, 或软链
4. **遇到 git 网络问题** — 提示用户配代理或换镜像, 不卡死
5. **遇到 Claude Code 未装** — 停下提示用户先装 Claude Code: https://claude.ai/code

---

## 可选高级:让用户的 AI 自动维护 skills

监护人级用户 (有 GitHub PAT) 可以让 AI agent 跑后台脚本周期性 `git pull` 更新 skills:

```bash
# crontab 每周日凌晨 3 点更新 Karpathy skills
(crontab -l 2>/dev/null; echo "0 3 * * 0 cd ~/.claude/skills/.karpathy-tmp && git pull --quiet") | crontab -
```

**默认不设**, 用户主动要才配置。

---

**底线**: 本剧本帮 AI 装的 skills 是**增强**Solar 体验, 不是必需。即使全部 skip 失败, Solar L1 + L2 (CLAUDE.md + harness + mempalace) 已经能跑大部分核心功能。
