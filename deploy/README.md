# Solar 部署指南

## 🆕 从零开始 (新用户)

**如果你是第一次使用 Solar，完全从零开始：**

详见 **[SETUP.md](./SETUP.md)** - 完整的从零到一设置指南

**快速步骤：**

```bash
# 1. Clone 仓库
git clone git@github.com:YOUR_USERNAME/Solar.git ~/Solar
cd ~/Solar

# 2. 安装依赖 (Homebrew/Bun/CLI工具)
./deploy/install-deps.sh

# 3. 初始化数据库
./deploy/init-database.sh

# 4. 配置 MCP (重要!)
# 创建 ~/.gemini/antigravity/mcp_config.json
# 参考 SETUP.md 的 MCP 配置章节

# 5. 启动 Claude Code，执行 /solar
```

---

## 📋 已有配置机器之间同步

### 方式一：完整同步（推荐）

**从 MacBook Pro 同步到 Mac Mini：**

```bash
# 在 MacBook Pro 上执行
cd ~/Solar
./deploy/sync-config.sh lisihao@192.168.50.194
```

这会自动：
- ✅ 同步所有配置文件（skills/rules/agents/hooks/CLAUDE.md）
- ✅ 同步 Solar 代码
- ✅ 初始化数据库

### 方式二：手动部署

**1. Clone 代码**

```bash
git clone <solar-repo-url> ~/Solar
cd ~/Solar
```

**2. 初始化数据库**

```bash
./deploy/init-database.sh
```

**3. 复制配置文件**

```bash
# 从另一台机器同步（需要先在源机器上配置好）
rsync -av source-machine:~/.claude/ ~/.claude/
```

## 目录结构

```
~/Solar/              # Git 仓库（代码）
├── core/            # 核心功能
├── deploy/          # 部署脚本
└── ...

~/.claude/           # 用户配置（不在 git 里）
├── skills/         # 技能定义
├── rules/          # 规则文件
├── agents/         # Agent 定义
└── hooks/          # Git hooks

~/.solar/            # 运行时数据（不在 git 里）
├── solar.db        # 数据库
├── STATE.md        # 当前任务状态
└── DECISIONS.md    # 决策日志
```

## 数据库说明

- **不推送到 git**：数据库文件包含用户数据，不应该推送
- **初始化脚本**：使用 `init-database.sh` 在新机器上创建
- **Schema 文件**：各模块的 `schema.sql` 会被自动收集执行

## 配置文件说明

- **不推送到 git**：`~/.claude/` 是用户级配置，可能包含私密信息
- **同步方式**：使用 `sync-config.sh` 或手动 rsync

## 部署脚本说明

| 脚本 | 用途 | 使用场景 |
|------|------|----------|
| `install-deps.sh` | 安装系统依赖 | **新机器首次安装** |
| `init-database.sh` | 初始化数据库 | 新机器或数据库损坏 |
| `sync-config.sh` | 同步配置文件 | 已有机器间同步 |

## 必需依赖清单

| 依赖 | 必需? | 用途 | 安装方式 |
|------|------|------|----------|
| Bun | ✅ 必需 | 运行 TypeScript 脚本 | `curl -fsSL https://bun.sh/install \| bash` |
| things.sh | ⚠️ 办公功能 | Things 3 任务管理 | `brew install things.sh` |
| remindctl | ⚠️ 办公功能 | Apple Reminders | `brew install keith/formulae/remindctl` |
| himalaya | ⚠️ 办公功能 | 邮件 CLI | `brew install himalaya` |
| openclaw | ⚠️ 小爱功能 | AI 助手 | `npm install -g @openclaw/cli` |
| MCP配置 | ✅ 必需 | Brain Router | 参考 SETUP.md |

**最小化安装**: 只安装 Bun + MCP 配置即可使用核心功能

## 常见问题

**Q: 为什么 git clone 后缺少文件？**

A: `~/.claude/` 配置目录和 `~/.solar/` 数据目录不在 git 仓库里，需要：
- 使用 `sync-config.sh` 同步（从已有机器）
- 或者从零开始安装（参考 SETUP.md）

**Q: 数据库初始化失败？**

A: 检查：
- 是否所有 `schema.sql` 文件都在 `core/` 目录下
- SQLite3 是否已安装
- 目录权限是否正确

**Q: Skills 数量不一致？**

A: 检查是否完整同步了 `~/.claude/skills/` 目录：
```bash
ls ~/.claude/skills/ | wc -l  # 应该是 76+ 个
```

**Q: MCP 配置在哪里？**

A: Brain Router 的 MCP 配置文件位置：
```
~/.gemini/antigravity/mcp_config.json
```

详细配置方法参考 `SETUP.md`

**Q: 从零开始需要多久？**

A:
- 安装依赖: ~10 分钟 (首次安装 Homebrew 较慢)
- 配置 API Keys: ~5 分钟
- 同步配置: ~2 分钟
- 总计: **15-20 分钟**
