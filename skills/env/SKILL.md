# /env - 环境管理

## 触发
- `/env` - 显示当前环境
- `/env list` - 列出所有环境
- `/env switch <环境>` - 切换环境
- `/env diff <env1> <env2>` - 比较环境
- `/env check` - 检查环境变量完整性
- `/env export` - 导出当前环境

## 执行

### 显示当前环境

```bash
echo "=== 当前环境 ==="
echo "NODE_ENV: ${NODE_ENV:-development}"
echo "Shell: $SHELL"
echo "PWD: $PWD"

# 检查关键变量
echo ""
echo "=== 关键变量 ==="
[ -n "$API_BASE" ] && echo "✓ API_BASE" || echo "✗ API_BASE 未设置"
[ -n "$DATABASE_URL" ] && echo "✓ DATABASE_URL" || echo "✗ DATABASE_URL 未设置"
[ -n "$OPENAI_API_KEY" ] && echo "✓ OPENAI_API_KEY" || echo "✗ OPENAI_API_KEY 未设置"
```

### 环境切换

```bash
# 使用 .env 文件
# .env.development, .env.staging, .env.production

switch_env() {
  ENV=$1
  ENV_FILE=".env.$ENV"

  if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" .env
    echo "✓ 已切换到 $ENV 环境"
    # 重新加载
    source .env 2>/dev/null || export $(cat .env | xargs)
  else
    echo "✗ 环境文件不存在: $ENV_FILE"
  fi
}

# 切换到 staging
switch_env staging
```

### 环境比较

```bash
diff_env() {
  ENV1=$1
  ENV2=$2

  echo "=== $ENV1 vs $ENV2 ==="
  diff <(sort ".env.$ENV1" 2>/dev/null) <(sort ".env.$ENV2" 2>/dev/null) | \
    grep "^[<>]" | \
    sed 's/^</[只在 '$ENV1']/' | \
    sed 's/^>/[只在 '$ENV2']/'
}

diff_env development production
```

### 环境检查

```bash
# 检查 .env.example 中定义的变量是否都设置了
check_env() {
  MISSING=0
  if [ -f ".env.example" ]; then
    while IFS= read -r line; do
      # 跳过注释和空行
      [[ "$line" =~ ^# ]] && continue
      [[ -z "$line" ]] && continue

      KEY=$(echo "$line" | cut -d= -f1)
      if [ -z "${!KEY}" ] && ! grep -q "^$KEY=" .env 2>/dev/null; then
        echo "✗ 缺少: $KEY"
        MISSING=$((MISSING + 1))
      fi
    done < ".env.example"

    if [ $MISSING -eq 0 ]; then
      echo "✓ 所有环境变量已设置"
    else
      echo "⚠️ 缺少 $MISSING 个环境变量"
    fi
  else
    echo "未找到 .env.example"
  fi
}
```

### dotenv 管理

```bash
# 使用 direnv (推荐)
brew install direnv

# 在 ~/.zshrc 添加
eval "$(direnv hook zsh)"

# 项目中创建 .envrc
echo "dotenv" > .envrc
direnv allow

# 自动加载 .env 当进入目录
```

### 多环境配置结构

```
project/
├── .env                    # 当前激活 (gitignore)
├── .env.example            # 模板 (提交)
├── .env.development        # 开发环境
├── .env.staging            # 测试环境
├── .env.production         # 生产环境 (敏感,不提交)
└── .env.local              # 本地覆盖 (gitignore)
```

## 输出格式

```
┌─ 🔧 Environment ────────────────────────────────────────────────┐
│                                                                  │
│  当前环境: development                                           │
│  配置文件: .env.development                                      │
│                                                                  │
├─ 变量状态 ───────────────────────────────────────────────────────┤
│                                                                  │
│  ✓ NODE_ENV         development                                  │
│  ✓ API_BASE         http://localhost:3000                        │
│  ✓ DATABASE_URL     postgresql://...                             │
│  ✗ REDIS_URL        未设置                                       │
│  ✓ OPENAI_API_KEY   sk-...****                                   │
│                                                                  │
├─ 可用环境 ───────────────────────────────────────────────────────┤
│                                                                  │
│  • development (当前)                                            │
│  • staging                                                       │
│  • production                                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 安全提醒

- **永远不要**提交生产环境密钥
- 使用 `.gitignore` 排除敏感文件
- 敏感信息用 `****` 遮蔽显示
- 考虑使用 Vault/AWS Secrets Manager
