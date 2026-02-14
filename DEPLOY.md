# Solar 部署指南

## 快速开始

### 一键部署

```bash
git clone https://github.com/anthropics/solar.git
cd solar
./install.sh
```

这将自动：
- 复制配置到 `~/.claude/`
- 安装所有 skills、agents、rules、hooks
- 初始化数据库
- 备份现有配置（如果存在）

### 手动部署

如果需要自定义部署：

```bash
# 1. 复制配置文件
cp CLAUDE.md ~/.claude/

# 2. 复制规则
cp -r rules/* ~/.claude/rules/

# 3. 复制技能
cp -r skills/* ~/.claude/skills/

# 4. 复制 Agents
cp -r agents/* ~/.claude/agents/

# 5. 复制 Hooks
cp -r hooks/* ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh

# 6. 复制核心模块
cp -r core/* ~/.claude/core/

# 7. 初始化数据库
mkdir -p ~/.solar
sqlite3 ~/.solar/solar.db < core/schema.sql
```

## 配置密钥（可选）

如果需要使用外部服务（邮件、Notion、Trello 等）：

```bash
mkdir -p ~/.claude/secrets
# 在 secrets/ 目录下添加密钥文件
```

**注意**: `secrets/` 目录已在 `.gitignore` 中，不会被推送。

## OpenClaw/小爱集成

小爱（XiaoAi）是 Solar 的 AI 秘书系统，用于处理日常办公任务。

### 安装 OpenClaw

```bash
cd secretary/openclaw
npm install
# 或
bun install
```

### 配置

配置文件已包含在：
- `~/.claude/CLAUDE.md` - 小爱使用说明
- `~/.claude/rules/delegate-to-xiaoai.md` - 委派规则
- `~/.claude/rules/delegate-insight-to-xiaoai.md` - 洞察分析委派

### 使用

```bash
# 调用小爱处理任务
openclaw agent --local --agent main --message "帮我查一下今天的邮件"
```

或在 Solar 中直接说："让小爱查邮件"

## 启动 Solar

```bash
# 启动 Claude Code
claude

# 在对话中输入
solar
```

## 验证安装

```bash
# 检查技能数量
ls ~/.claude/skills | wc -l

# 检查规则文件
ls ~/.claude/rules | wc -l

# 检查数据库
sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_skills"
```

## 更新

```bash
cd ~/solar
git pull
./install.sh
```

安装脚本会自动备份现有配置。

## 目录结构

```
~/.claude/
├── CLAUDE.md           # 主配置文件
├── rules/              # 铁律规则（小爱委派等）
├── skills/             # 技能（38个）
├── agents/             # Agent 定义
├── hooks/              # 事件钩子
└── core/               # 核心模块

~/.solar/
├── solar.db            # 系统数据库
├── STATE.md            # 当前状态（不推送）
└── DECISIONS.md        # 决策日志（不推送）
```

## 隐私与安全

### 不会推送的内容

- 密钥文件 (`secrets/`, `*.key`, `*.env`)
- 数据库文件 (`*.db`)
- 个人状态文件 (`.solar/STATE.md`, `.solar/DECISIONS.md`)
- 日志文件 (`*.log`, `.solar/LOG/`)

### 会推送的内容

- 配置文件和规则
- 技能和 Agents
- 核心代码和脚本
- 文档和示例

## 故障排查

### 技能未加载

```bash
# 检查技能目录
ls ~/.claude/skills

# 重新安装
./install.sh
```

### 数据库初始化失败

```bash
# 手动初始化
rm ~/.solar/solar.db
sqlite3 ~/.solar/solar.db < core/schema.sql
```

### Hook 不执行

```bash
# 设置执行权限
chmod +x ~/.claude/hooks/*.sh
```

## 支持

- GitHub: https://github.com/anthropics/solar
- Issues: https://github.com/anthropics/solar/issues
- Docs: 查看 `docs/` 目录

---

**Solar v2.0** - AI Native Operating System
