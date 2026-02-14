# Solar 部署指南

## 快速部署到新机器

### 方式一：完整同步（推荐）

**从 MacBook Pro 同步到 Mac Mini：**

```bash
# 在 MacBook Pro 上执行
cd ~/Solar
./deploy/sync-config.sh lisihao@192.168.50.194
```

这会自动：
- ✅ 同步所有配置文件（skills/rules/agents/hooks）
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

## 常见问题

**Q: 为什么 git clone 后缺少文件？**

A: `~/.claude/` 配置目录和 `~/.solar/` 数据目录不在 git 仓库里，需要：
- 使用 `sync-config.sh` 同步
- 或者手动复制/rsync

**Q: 数据库初始化失败？**

A: 检查：
- 是否所有 `schema.sql` 文件都在 `core/` 目录下
- SQLite3 是否已安装
- 目录权限是否正确

**Q: Skills 数量不一致？**

A: 检查是否完整同步了 `~/.claude/skills/` 目录：
```bash
ls ~/.claude/skills/ | wc -l  # 应该是 76 个
```
