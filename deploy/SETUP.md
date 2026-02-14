# Solar 从零开始设置指南

## 新机器完整部署流程

### 前置条件

- macOS 系统
- 已安装 Claude Code
- 网络连接正常

### Step 1: 克隆仓库

```bash
cd ~
git clone git@github.com:YOUR_USERNAME/Solar.git
# 或使用 HTTPS: git clone https://github.com/YOUR_USERNAME/Solar.git
cd Solar
```

### Step 2: 安装依赖

```bash
./deploy/install-deps.sh
```

这个脚本会自动安装：
- ✅ Homebrew (如果未安装)
- ✅ Bun runtime
- ✅ Things CLI (things.sh)
- ✅ Remindctl (Apple Reminders CLI)
- ✅ Himalaya (邮件 CLI)
- ✅ OpenClaw (小爱) - 需要手动安装

### Step 3: 配置同步 (如果有源机器)

如果你有另一台已配置好的机器 (如 MacBook)：

```bash
# 在源机器上执行
cd ~/Solar
./deploy/sync-config.sh user@target-machine

# 这会同步：
# - ~/.claude/skills/
# - ~/.claude/rules/
# - ~/.claude/agents/
# - ~/.claude/hooks/
# - ~/.claude/CLAUDE.md
# - ~/.claude/personality-anchor.txt
# - ~/Solar/ 代码
```

### Step 4: 初始化数据库

```bash
./deploy/init-database.sh
```

这会自动：
- ✅ 收集所有 schema.sql 文件
- ✅ 创建 ~/.solar/solar.db
- ✅ 初始化系统表
- ✅ 插入种子数据

### Step 5: MCP 配置 (重要!)

Brain Router 需要 MCP 配置文件：

**位置**: `~/.gemini/antigravity/mcp_config.json`

如果有源机器：
```bash
scp source-user@source-host:~/.gemini/antigravity/mcp_config.json ~/.gemini/antigravity/
```

如果从零开始，创建配置文件：
```bash
mkdir -p ~/.gemini/antigravity
cat > ~/.gemini/antigravity/mcp_config.json << 'EOF'
{
  "brain-router": {
    "command": "bun",
    "args": ["run", "/Users/USERNAME/.claude/core/solar-farm/brain-router-server.ts"],
    "env": {
      "GEMINI_API_KEY": "your-gemini-api-key",
      "DEEPSEEK_API_KEY": "your-deepseek-api-key",
      "GLM_API_KEY": "your-glm-api-key"
    }
  }
}
EOF
```

**替换占位符**:
- `USERNAME` → 你的用户名
- `your-*-api-key` → 对应的 API Key

### Step 6: 验证安装

```bash
# 检查 CLI 工具
which things remindctl himalaya openclaw bun

# 检查数据库
sqlite3 ~/.solar/solar.db ".tables" | head -5

# 检查配置文件
ls -la ~/.claude/skills/ | head -5
ls -la ~/.claude/rules/ | head -5
cat ~/.claude/CLAUDE.md | head -10
```

### Step 7: 启动 Solar

1. 打开 Claude Code
2. 切换到 Solar 项目目录
3. 执行: `/solar`

应该看到启动横幅和态势报告。

## 常见问题

### Q: Homebrew 安装太慢

使用中国镜像：
```bash
export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git"
export HOMEBREW_CORE_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git"
```

### Q: OpenClaw 安装失败

手动安装：
```bash
npm install -g @openclaw/cli
# 或从源码: git clone https://github.com/openclaw/openclaw && cd openclaw && npm install
```

### Q: Git 无法 push/pull

配置 SSH Key：
```bash
ssh-keygen -t ed25519 -C "your-email@example.com"
cat ~/.ssh/id_ed25519.pub  # 复制后添加到 GitHub
```

### Q: Things CLI 找不到

检查 Homebrew 安装路径：
```bash
brew --prefix
ls $(brew --prefix)/bin/things
```

如果在 `/opt/homebrew/bin/`，添加到 PATH：
```bash
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## 最小化安装 (只用核心功能)

如果只想用 Solar 的代码功能，不需要办公自动化：

```bash
# 只安装 Bun
curl -fsSL https://bun.sh/install | bash

# 只初始化数据库
./deploy/init-database.sh

# 只同步核心规则 (从源机器)
rsync -av source:~/.claude/rules/ ~/.claude/rules/
rsync -av source:~/.claude/CLAUDE.md ~/.claude/
```

## 文件结构说明

```
~/Solar/              # Git 仓库 (代码)
  ├── core/           # 核心代码
  ├── deploy/         # 部署脚本
  └── .solar/         # 项目状态 (不在 git)

~/.claude/            # 用户配置 (不在 git)
  ├── skills/         # 76+ 技能
  ├── rules/          # 规则文件
  ├── agents/         # Agent 定义
  ├── hooks/          # 钩子脚本
  └── CLAUDE.md       # 主配置

~/.solar/             # 运行时数据 (不在 git)
  ├── solar.db        # SQLite 数据库
  └── STATE.md        # 会话状态

~/.gemini/antigravity/
  └── mcp_config.json # Brain Router MCP 配置
```

## API Keys 配置

Solar 使用多个 AI 模型，需要配置 API Keys：

| 服务 | 环境变量 | 获取地址 |
|------|---------|---------|
| Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| DeepSeek | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys |
| GLM (智谱) | `GLM_API_KEY` | https://open.bigmodel.cn/usercenter/apikeys |

添加到 `~/.zshrc` 或 `~/.bashrc`：
```bash
export GEMINI_API_KEY="your-key-here"
export DEEPSEEK_API_KEY="your-key-here"
export GLM_API_KEY="your-key-here"
```

## 下一步

完成设置后，建议阅读：
- `~/Solar/README.md` - 项目总览
- `~/.claude/rules/00-core-laws.md` - 核心铁律
- `~/Solar/.solar/STATE.md` - 当前任务态势

开始使用：
```bash
cd ~/Solar
# 在 Claude Code 中执行
/solar
```
