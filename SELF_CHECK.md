# Solar 自检清单 (Self-Check Checklist)

> **用途**: 每次从 GitHub 拉取、同步到新机器、新安装后执行
> **目的**: 确保系统安全、可靠、稳定，功能完整无断头
> **更新**: 2026-02-18

---

## 一、核心文件检查

### 1.1 必备文件

```bash
# 检查核心配置文件
check_files() {
  echo "=== 核心文件检查 ==="

  files=(
    "$HOME/.claude/CLAUDE.md"
    "$HOME/.claude/settings.json"
    "$HOME/.claude/STATE.md"
    "$HOME/.claude/solar.db"
    "$HOME/.solar/solar.db"
    "$HOME/.claude/solar/bin/solar-search"
  )

  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      echo "✓ $f"
    else
      echo "✗ $f (缺失)"
    fi
  done
}

check_files
```

**验收标准**:
- [ ] CLAUDE.md 存在且大小 > 5KB
- [ ] settings.json 存在
- [ ] STATE.md 存在
- [ ] solar.db 存在（两个位置都要检查）

---

## 二、数据库完整性

### 2.1 主数据库检查

```bash
# 数据库完整性检查
check_database() {
  echo "=== 数据库检查 ==="

  DB="$HOME/.solar/solar.db"

  # 1. 完整性
  result=$(sqlite3 "$DB" "PRAGMA integrity_check" 2>&1)
  echo "完整性: $result"

  # 2. 关键表
  tables=$(sqlite3 "$DB" "SELECT name FROM sqlite_master WHERE type='table'" 2>&1)
  echo "表数量: $(echo "$tables" | wc -l)"

  # 3. 核心表数据量
  echo ""
  echo "=== 核心表数据量 ==="
  sqlite3 "$DB" "SELECT 'sys_favorites' as tbl, COUNT(*) as cnt FROM sys_favorites
    UNION ALL SELECT 'sys_skills', COUNT(*) FROM sys_skills
    UNION ALL SELECT 'sys_resources', COUNT(*) FROM sys_resources WHERE status='active'
    UNION ALL SELECT 'sys_agents', COUNT(*) FROM sys_agents
    UNION ALL SELECT 'cortex_sources', COUNT(*) FROM cortex_sources"
}

check_database
```

**验收标准**:
- [ ] integrity_check = "ok"
- [ ] sys_favorites > 50 条
- [ ] sys_skills > 60 个
- [ ] sys_resources > 100 个
- [ ] sys_agents > 10 个

---

## 三、Tantivy 搜索引擎

### 3.1 二进制检查

```bash
# 搜索引擎检查
check_search() {
  echo "=== Tantivy 搜索检查 ==="

  SEARCH_BIN="$HOME/.claude/solar/bin/solar-search"

  # 1. 二进制存在
  if [ -f "$SEARCH_BIN" ]; then
    echo "✓ solar-search 存在"
    $SEARCH_BIN --version
  else
    echo "✗ solar-search 不存在，需要编译"
    echo "  编译命令: cd ~/.claude/solar/core/search && cargo build --release"
    return 1
  fi

  # 2. 索引存在
  if [ -d "$HOME/.solar/search-index" ]; then
    echo "✓ 搜索索引存在"
    du -sh "$HOME/.solar/search-index"
  else
    echo "✗ 搜索索引不存在，需要重建"
  fi

  # 3. 功能测试
  echo ""
  echo "=== 搜索功能测试 ==="
  $SEARCH_BIN stats 2>&1 | head -10
}

check_search
```

**验收标准**:
- [ ] solar-search 可执行
- [ ] 索引目录存在
- [ ] 文档数 > 10000
- [ ] 搜索测试通过

---

## 四、Skills / Agents / Hooks

### 4.1 组件统计

```bash
# 组件检查
check_components() {
  echo "=== 组件统计 ==="

  echo "Rules (活跃): $(ls ~/.claude/rules/*.md 2>/dev/null | wc -l) 条"
  echo "Rules (归档): $(ls ~/.claude/rules/archive/*.md 2>/dev/null | wc -l) 条"
  echo "Skills: $(ls ~/.claude/skills 2>/dev/null | wc -l) 个"
  echo "Agents: $(ls ~/.claude/agents 2>/dev/null | wc -l) 个"
  echo "Hooks: $(ls ~/.claude/hooks 2>/dev/null | wc -l) 个"
  echo "Core: $(ls ~/.claude/core 2>/dev/null | wc -l) 个模块"

  echo ""
  echo "=== 与标准对比 ==="
  echo "           当前    标准    状态"
  echo "Rules       $(ls ~/.claude/rules/*.md 2>/dev/null | wc -l)       10      $( [ $(ls ~/.claude/rules/*.md 2>/dev/null | wc -l) -ge 10 ] && echo '✓' || echo '✗' )"
  echo "Skills      $(ls ~/.claude/skills 2>/dev/null | wc -l)       90      $( [ $(ls ~/.claude/skills 2>/dev/null | wc -l) -ge 90 ] && echo '✓' || echo '✗' )"
  echo "Agents      $(ls ~/.claude/agents 2>/dev/null | wc -l)       15      $( [ $(ls ~/.claude/agents 2>/dev/null | wc -l) -ge 15 ] && echo '✓' || echo '✗' )"
  echo "Hooks       $(ls ~/.claude/hooks 2>/dev/null | wc -l)       70      $( [ $(ls ~/.claude/hooks 2>/dev/null | wc -l) -ge 70 ] && echo '✓' || echo '✗' )"
}

check_components
```

**验收标准**:
- [ ] Rules 活跃 ≥ 10 条
- [ ] Skills ≥ 90 个
- [ ] Agents ≥ 15 个
- [ ] Hooks ≥ 70 个
- [ ] Core 模块 ≥ 50 个

---

## 五、配置文件同步

### 5.1 配置完整性

```bash
# 配置检查
check_config() {
  echo "=== 配置文件检查 ==="

  configs=(
    "$HOME/.claude/CLAUDE.md"
    "$HOME/.claude/settings.json"
    "$HOME/.claude/settings.local.json"
    "$HOME/.claude/modes.md"
    "$HOME/.claude/niumao-anchors.json"
    "$HOME/.claude/personality-anchor.txt"
    "$HOME/.mcp.json"
    "$HOME/.claude.json"
    "$HOME/.zshrc"
    "$HOME/.gitconfig"
    "$HOME/.ssh/id_ed25519"
  )

  for f in "${configs[@]}"; do
    if [ -f "$f" ]; then
      size=$(wc -c < "$f")
      echo "✓ $f ($size bytes)"
    else
      echo "✗ $f (缺失)"
    fi
  done
}

check_config
```

**验收标准**:
- [ ] CLAUDE.md > 5KB
- [ ] settings.json 存在
- [ ] niumao-anchors.json 存在
- [ ] .mcp.json 存在
- [ ] SSH 密钥存在

---

## 六、依赖环境

### 6.1 运行时检查

```bash
# 环境检查
check_environment() {
  echo "=== 运行时环境 ==="

  # Bun
  if command -v bun &> /dev/null; then
    echo "✓ Bun: $(bun --version)"
  else
    echo "✗ Bun 未安装"
  fi

  # Node
  if command -v node &> /dev/null; then
    echo "✓ Node: $(node --version)"
  else
    echo "✗ Node 未安装"
  fi

  # Rust/Cargo
  if command -v cargo &> /dev/null; then
    echo "✓ Cargo: $(cargo --version)"
  else
    echo "✗ Cargo 未安装"
  fi

  # SQLite
  if command -v sqlite3 &> /dev/null; then
    echo "✓ SQLite: $(sqlite3 --version | awk '{print $1}')"
  else
    echo "✗ SQLite 未安装"
  fi

  # Git
  if command -v git &> /dev/null; then
    echo "✓ Git: $(git --version | awk '{print $3}')"
  else
    echo "✗ Git 未安装"
  fi
}

check_environment
```

**验收标准**:
- [ ] Bun ≥ 1.0
- [ ] Node ≥ 18
- [ ] Cargo/Rust ≥ 1.70
- [ ] SQLite ≥ 3.40
- [ ] Git ≥ 2.40

---

## 七、密钥与认证检查

### 7.1 SSH 密钥

```bash
# SSH 密钥检查
check_ssh_keys() {
  echo "=== SSH 密钥检查 ==="

  # 检查 ed25519 密钥
  if [ -f "$HOME/.ssh/id_ed25519" ]; then
    echo "✓ id_ed25519 存在"
    # 检查权限
    perms=$(stat -f "%OLp" "$HOME/.ssh/id_ed25519" 2>/dev/null || stat -c "%a" "$HOME/.ssh/id_ed25519" 2>/dev/null)
    if [ "$perms" = "600" ]; then
      echo "  ✓ 权限正确 (600)"
    else
      echo "  ✗ 权限错误 ($perms)，应为 600"
    fi
    # 测试 GitHub 连接
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
      echo "  ✓ GitHub 认证成功"
    else
      echo "  ⚠ GitHub 认证失败或未配置"
    fi
  else
    echo "✗ id_ed25519 不存在"
  fi

  # 检查 known_hosts
  if [ -f "$HOME/.ssh/known_hosts" ]; then
    host_count=$(wc -l < "$HOME/.ssh/known_hosts")
    echo "✓ known_hosts ($host_count 条记录)"
  else
    echo "⚠ known_hosts 不存在"
  fi
}

check_ssh_keys
```

**验收标准**:
- [ ] id_ed25519 存在且权限 600
- [ ] GitHub SSH 认证成功
- [ ] known_hosts 有记录

### 7.2 API 密钥检查

```bash
# API 密钥检查（不显示密钥值）
check_api_keys() {
  echo "=== API 密钥检查 ==="

  # 检查环境变量中的密钥
  keys_to_check=(
    "ANTHROPIC_API_KEY"
    "OPENAI_API_KEY"
    "GOOGLE_API_KEY"
    "GEMINI_API_KEY"
    "DEEPSEEK_API_KEY"
    "ZHIPU_API_KEY"
  )

  for key in "${keys_to_check[@]}"; do
    if [ -n "${!key}" ]; then
      # 只显示前8位和后4位
      value="${!key}"
      len=${#value}
      masked="${value:0:8}...${value: -4}"
      echo "✓ $key ($len chars): $masked"
    else
      echo "✗ $key (未设置)"
    fi
  done

  # 检查 .env 文件
  echo ""
  if [ -f "$HOME/.env" ]; then
    env_count=$(grep -c "API_KEY\|TOKEN\|SECRET" "$HOME/.env" 2>/dev/null || echo 0)
    echo "✓ ~/.env 存在 ($env_count 个密钥配置)"
  else
    echo "⚠ ~/.env 不存在"
  fi
}

check_api_keys
```

**验收标准**:
- [ ] ANTHROPIC_API_KEY 已设置
- [ ] 至少 3 个其他 API 密钥已设置
- [ ] ~/.env 文件存在

---

## 八、MCP 服务与模型配置检查

### 8.1 MCP 配置

```bash
# MCP 检查
check_mcp() {
  echo "=== MCP 服务检查 ==="

  # 检查 MCP 配置
  if [ -f "$HOME/.mcp.json" ]; then
    mcp_count=$(cat "$HOME/.mcp.json" | grep -c '"command"' 2>/dev/null || echo 0)
    echo "MCP 服务数: $mcp_count"
    cat "$HOME/.mcp.json" | grep -E '"[^"]+":' | head -10
  else
    echo "✗ .mcp.json 不存在"
  fi

  # 检查关键 MCP
  echo ""
  echo "=== 关键 MCP 状态 ==="

  # Brain Router
  if pgrep -f "brain-router" > /dev/null 2>&1; then
    echo "✓ Brain Router 运行中"
  else
    echo "⚠ Brain Router 未运行"
  fi
}

check_mcp
```

### 8.2 模型配置检查

```bash
# 模型配置检查
check_model_config() {
  echo "=== 模型配置检查 ==="

  DB="$HOME/.solar/solar.db"

  # 1. 检查 collab_model_profiles 表
  echo "1. 已注册模型:"
  if sqlite3 "$DB" ".tables" | grep -q "collab_model_profiles"; then
    sqlite3 "$DB" "SELECT model_id, nickname, farm_role, context_window, cost_per_1k_input
                   FROM collab_model_profiles
                   ORDER BY cost_per_1k_input" 2>/dev/null | head -15
  else
    echo "  ✗ collab_model_profiles 表不存在"
  fi

  # 2. 检查路由模式
  echo ""
  echo "2. 路由模式配置:"
  if sqlite3 "$DB" ".tables" | grep -q "sroe_routing_modes"; then
    sqlite3 "$DB" "SELECT mode_id, description, is_active
                   FROM sroe_routing_modes" 2>/dev/null
  else
    echo "  ✗ sroe_routing_modes 表不存在"
  fi

  # 3. 当前激活模式
  echo ""
  echo "3. 当前模式:"
  current_mode=$(sqlite3 "$DB" "SELECT preference_value FROM sys_preferences
                                 WHERE preference_key = 'current_routing_mode'" 2>/dev/null)
  if [ -n "$current_mode" ]; then
    echo "  激活模式: $current_mode"
  else
    echo "  ⚠ 未设置路由模式"
  fi

  # 4. Brain Router 模型配置
  echo ""
  echo "4. Brain Router 配置:"
  if [ -f "$HOME/.solar/brain-router/config.json" ]; then
    echo "  ✓ Brain Router 配置存在"
    cat "$HOME/.solar/brain-router/config.json" | grep -E '"model"|"default_model"' | head -5
  else
    echo "  ⚠ Brain Router 配置不存在"
  fi
}

check_model_config
```

**验收标准**:
- [ ] .mcp.json 存在
- [ ] MCP 服务数 ≥ 5
- [ ] Brain Router 可用
- [ ] collab_model_profiles 有 ≥ 5 个模型
- [ ] 路由模式已配置
- [ ] 当前模式已激活

---

## 九、.claude 配置完整性检查

### 9.1 核心目录结构

```bash
# .claude 配置完整性检查
check_claude_config() {
  echo "=== .claude 配置完整性检查 ==="

  # 1. 核心目录
  echo "1. 核心目录:"
  dirs=(
    ".claude"
    ".claude/rules"
    ".claude/rules/archive"
    ".claude/skills"
    ".claude/agents"
    ".claude/hooks"
    ".claude/core"
    ".claude/modes"
    ".claude/solar"
    ".claude/solar/bin"
    ".solar"
    ".solar/search-index"
    ".solar/brain-router"
    ".solar/cortex"
  )

  for d in "${dirs[@]}"; do
    if [ -d "$HOME/$d" ]; then
      count=$(ls "$HOME/$d" 2>/dev/null | wc -l | tr -d ' ')
      echo "  ✓ $d ($count 项)"
    else
      echo "  ✗ $d (缺失)"
    fi
  done

  # 2. 核心文件
  echo ""
  echo "2. 核心文件:"
  files=(
    ".claude/CLAUDE.md"
    ".claude/settings.json"
    ".claude/settings.local.json"
    ".claude/STATE.md"
    ".claude/modes.md"
    ".claude/niumao-anchors.json"
    ".claude/personality-anchor.txt"
    ".claude.json"
    ".mcp.json"
    ".solar/solar.db"
    ".claude/solar/bin/solar-search"
  )

  for f in "${files[@]}"; do
    if [ -f "$HOME/$f" ]; then
      size=$(wc -c < "$HOME/$f" 2>/dev/null | tr -d ' ')
      echo "  ✓ $f ($size bytes)"
    else
      echo "  ✗ $f (缺失)"
    fi
  done

  # 3. Rules 活跃文件列表
  echo ""
  echo "3. 活跃 Rules (前10):"
  ls ~/.claude/rules/*.md 2>/dev/null | head -10 | xargs -n1 basename

  # 4. 检查关键规则
  echo ""
  echo "4. 关键规则检查:"
  critical_rules=(
    "00-core-laws.md"
    "01-three-core-laws.md"
    "solar-farm.md"
    "state-persistence.md"
    "cortex-first.md"
  )

  for r in "${critical_rules[@]}"; do
    if [ -f "$HOME/.claude/rules/$r" ]; then
      echo "  ✓ $r"
    else
      echo "  ✗ $r (缺失)"
    fi
  done
}

check_claude_config
```

### 9.2 配置文件对比标准

```bash
# 与 Mac Mini 标准对比
check_against_standard() {
  echo "=== 与 Mac Mini 标准对比 ==="

  echo "           当前值    标准值    状态"
  echo "─────────────────────────────────────"

  # Rules
  current=$(ls ~/.claude/rules/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 10 ]; then
    echo "Rules       $current        10       ✓"
  else
    echo "Rules       $current        10       ✗"
  fi

  # Rules Archive
  current=$(ls ~/.claude/rules/archive/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 50 ]; then
    echo "Rules归档   $current        56       ✓"
  else
    echo "Rules归档   $current        56       ✗"
  fi

  # Skills
  current=$(ls ~/.claude/skills 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 90 ]; then
    echo "Skills      $current        93       ✓"
  else
    echo "Skills      $current        93       ✗"
  fi

  # Agents
  current=$(ls ~/.claude/agents 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 15 ]; then
    echo "Agents      $current        16       ✓"
  else
    echo "Agents      $current        16       ✗"
  fi

  # Hooks
  current=$(ls ~/.claude/hooks 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 70 ]; then
    echo "Hooks       $current        77       ✓"
  else
    echo "Hooks       $current        77       ✗"
  fi

  # Core
  current=$(ls ~/.claude/core 2>/dev/null | wc -l | tr -d ' ')
  if [ "$current" -ge 50 ]; then
    echo "Core        $current        51       ✓"
  else
    echo "Core        $current        51       ✗"
  fi

  # Favorites
  current=$(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_favorites" 2>/dev/null)
  if [ "$current" -ge 80 ]; then
    echo "Favorites   $current        90       ✓"
  else
    echo "Favorites   $current        90       ✗"
  fi

  # 数据库大小
  db_size=$(du -m ~/.solar/solar.db 2>/dev/null | cut -f1)
  echo "数据库      ${db_size}MB     450MB    -"
}

check_against_standard
```

**验收标准**:
- [ ] 所有核心目录存在
- [ ] 所有核心文件存在
- [ ] 5 个关键规则文件存在
- [ ] 各组件数量 ≥ 标准值

---

## 十、功能验证测试

### 10.1 核心功能测试

```bash
# 功能测试
test_functions() {
  echo "=== 功能验证测试 ==="

  # 1. 搜索测试
  echo "1. 搜索测试..."
  if ~/.claude/solar/bin/solar-search query "test" 2>&1 | grep -q "results"; then
    echo "   ✓ 搜索功能正常"
  else
    echo "   ✗ 搜索功能异常"
  fi

  # 2. 数据库读取测试
  echo "2. 数据库读取测试..."
  if sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_favorites" &>/dev/null; then
    echo "   ✓ 数据库读取正常"
  else
    echo "   ✗ 数据库读取异常"
  fi

  # 3. Skills 加载测试
  echo "3. Skills 加载测试..."
  skill_count=$(ls ~/.claude/skills/*/SKILL.md 2>/dev/null | wc -l)
  if [ "$skill_count" -gt 50 ]; then
    echo "   ✓ Skills 加载正常 ($skill_count 个)"
  else
    echo "   ✗ Skills 加载异常"
  fi

  # 4. Rules 加载测试
  echo "4. Rules 加载测试..."
  rule_count=$(ls ~/.claude/rules/*.md 2>/dev/null | wc -l)
  if [ "$rule_count" -ge 10 ]; then
    echo "   ✓ Rules 加载正常 ($rule_count 条)"
  else
    echo "   ✗ Rules 加载异常"
  fi
}

test_functions
```

**验收标准**:
- [ ] 搜索返回结果
- [ ] 数据库可读取
- [ ] Skills 可加载
- [ ] Rules 可加载

---

## 十一、自检报告生成

### 11.1 一键自检脚本

```bash
#!/bin/bash
# solar-self-check.sh - Solar 一键自检

echo "╭─────────────────────────────────────────────────────────────────╮"
echo "│                    🔍 Solar 系统自检报告                        │"
echo "│                    $(date '+%Y-%m-%d %H:%M:%S')                            │"
echo "├─────────────────────────────────────────────────────────────────┤"
echo ""

# 执行所有检查
check_files
echo ""
check_database
echo ""
check_search
echo ""
check_components
echo ""
check_config
echo ""
check_environment
echo ""
check_ssh_keys
echo ""
check_api_keys
echo ""
check_mcp
echo ""
check_model_config
echo ""
check_claude_config
echo ""
check_against_standard
echo ""
test_functions

echo ""
echo "├─────────────────────────────────────────────────────────────────┤"
echo "│  自检完成！请检查上方 ✗ 项并修复                                │"
echo "╰─────────────────────────────────────────────────────────────────╯"
```

---

## 十二、常见问题修复

### 12.1 问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| solar-search 不存在 | 未编译 | `cd ~/.claude/solar/core/search && cargo build --release` |
| 搜索索引为空 | 未建立索引 | `~/.claude/solar/bin/solar-search index all` |
| 数据库损坏 | 传输中断 | 从备份恢复或重新同步 |
| Skills 数量不足 | 未同步完整 | `rsync -avz source:.claude/skills/ ~/.claude/skills/` |
| Rules 缺失 | 未同步 | 同步 Mac Mini 或 GitHub 版本 |
| MCP 无法连接 | 服务未启动 | 检查 MCP 配置并重启服务 |
| SSH 认证失败 | 密钥未添加到 GitHub | `gh auth login` 或添加 SSH key 到 GitHub |
| API 密钥缺失 | 未配置环境变量 | 编辑 ~/.zshrc 或 ~/.env 添加密钥 |
| 模型配置缺失 | 数据库未同步 | 从 Mac Mini 同步 solar.db |
| 权限错误 (600) | 文件权限不对 | `chmod 600 ~/.ssh/id_ed25519` |

### 12.2 修复命令速查

```bash
# 编译搜索
cd ~/.claude/solar/core/search && cargo build --release

# 重建索引
~/.claude/solar/bin/solar-search index all

# 数据库完整性修复
sqlite3 ~/.solar/solar.db "PRAGMA integrity_check"
sqlite3 ~/.solar/solar.db "VACUUM"

# 同步最新配置
rsync -avz --delete lisihao@192.168.50.194:/Users/lisihao/.claude/ ~/.claude/

# 安装依赖
cd ~/.claude/solar && bun install
```

---

## 附录：标准数据参考

### A. 核心资产标准值

| 资产类型 | 标准值 | 来源 |
|----------|--------|------|
| Rules (活跃) | 10 条 | Mac Mini 2026-02-18 |
| Rules (归档) | 56 条 | Mac Mini 2026-02-18 |
| Skills | 93 个 | Mac Mini 2026-02-18 |
| Agents | 16 个 | Mac Mini 2026-02-18 |
| Hooks | 77 个 | Mac Mini 2026-02-18 |
| Core 模块 | 51 个 | Mac Mini 2026-02-18 |
| Favorites | 90 条 | Mac Mini 2026-02-18 |
| 搜索文档 | 450,000+ | 索引统计 |

### B. 文件大小参考

| 文件 | 标准大小 |
|------|----------|
| CLAUDE.md | 5,725 bytes |
| settings.json | 3,966 bytes |
| solar.db | ~450 MB |
| search-index/ | ~1 GB |
| solar-search | ~11 MB |

### C. 必需 API 密钥

| 密钥名称 | 用途 | 获取方式 |
|----------|------|----------|
| ANTHROPIC_API_KEY | Claude API | console.anthropic.com |
| GOOGLE_API_KEY | Gemini API | aistudio.google.com |
| DEEPSEEK_API_KEY | DeepSeek API | platform.deepseek.com |
| ZHIPU_API_KEY | GLM API | open.bigmodel.cn |
| OPENAI_API_KEY | GPT API | platform.openai.com |
| GITHUB_TOKEN | GitHub API | github.com/settings/tokens |

### D. MCP 服务标准配置

| MCP 服务 | 功能 | 状态 |
|----------|------|------|
| brain-router | 智能路由 | 必需 |
| playwright | 浏览器自动化 | 推荐 |
| filesystem | 文件系统 | 推荐 |
| web-reader | 网页读取 | 推荐 |
| are | 智能编排 | 推荐 |

### E. 模型配置标准

| 模型 ID | 昵称 | 角色 | 上下文 |
|---------|------|------|--------|
| glm-5 | 老实人 | 日常编码 | 128K |
| glm-4-flash | 小快手 | 简单任务 | 128K |
| gemini-2.5-pro | 技术宅 | 架构审查 | 1M |
| gemini-3-pro | 千里马 | 前沿探索 | 1M |
| deepseek-v3 | 鬼才码农 | 创意编码 | 64K |
| deepseek-r1 | 思考驼 | 深度推理 | 64K |

---

*Self-Check Checklist v2.0*
*创建于: 2026-02-18*
*更新于: 2026-02-18 (新增密钥/模型配置/完整性检查)*
*维护者: Solar*
