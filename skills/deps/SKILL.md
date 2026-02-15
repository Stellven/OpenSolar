# /deps - 依赖管理

## 触发
- `/deps` - 检查当前项目依赖状态
- `/deps check` - 检查过时依赖
- `/deps security` - 安全漏洞扫描
- `/deps update` - 更新依赖
- `/deps update <包名>` - 更新指定依赖
- `/deps tree` - 依赖树可视化
- `/deps why <包名>` - 为什么需要这个依赖

## 执行

### Node.js 项目

```bash
# 检查过时依赖
npm outdated

# 安全漏洞扫描
npm audit

# 自动修复安全问题
npm audit fix

# 更新所有依赖到最新
npm update

# 更新到最新大版本 (需要 npm-check-updates)
npx npm-check-updates -u && npm install

# 依赖树
npm ls --depth=2

# 为什么需要某个依赖
npm why $PACKAGE
```

### Python 项目

```bash
# 检查过时 (需要 pip-review)
pip list --outdated

# 安全扫描 (需要 safety)
pip install safety
safety check

# 更新所有
pip install --upgrade -r requirements.txt

# 依赖树 (需要 pipdeptree)
pip install pipdeptree
pipdeptree
```

### Go 项目

```bash
# 检查依赖
go list -m -u all

# 更新依赖
go get -u ./...

# 整理依赖
go mod tidy

# 依赖图
go mod graph
```

### Rust 项目

```bash
# 检查过时
cargo outdated

# 安全扫描
cargo audit

# 更新
cargo update
```

## 综合检查脚本

```bash
echo "=== 依赖检查 ==="

# 检测项目类型并执行对应检查
if [ -f package.json ]; then
    echo "📦 Node.js 项目"
    echo "--- 过时依赖 ---"
    npm outdated 2>/dev/null || echo "全部最新"
    echo "--- 安全漏洞 ---"
    npm audit 2>/dev/null | head -20
fi

if [ -f requirements.txt ]; then
    echo "🐍 Python 项目"
    pip list --outdated 2>/dev/null | head -10
fi

if [ -f go.mod ]; then
    echo "🐹 Go 项目"
    go list -m -u all 2>/dev/null | grep "\[" | head -10
fi

if [ -f Cargo.toml ]; then
    echo "🦀 Rust 项目"
    cargo outdated 2>/dev/null | head -10
fi
```

## 输出格式

```
┌─ 📦 Dependencies ───────────────────────────────────────────────┐
│                                                                  │
│  项目: my-project (Node.js)                                      │
│  依赖: 45 个 (32 prod + 13 dev)                                  │
│                                                                  │
├─ 过时依赖 ───────────────────────────────────────────────────────┤
│  Package      Current   Wanted   Latest                          │
│  typescript   4.9.5     4.9.5    5.3.3    ⚠️ 大版本              │
│  eslint       8.45.0    8.56.0   8.56.0   ✓ 可更新              │
│  jest         29.5.0    29.7.0   29.7.0   ✓ 可更新              │
│                                                                  │
├─ 安全漏洞 ───────────────────────────────────────────────────────┤
│  ⚠️ 2 moderate, 0 high, 0 critical                               │
│  运行 `npm audit fix` 可自动修复                                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 最佳实践

1. **定期检查**: 每周运行 `/deps check`
2. **及时修复安全漏洞**: `npm audit fix`
3. **锁定版本**: 提交 lock 文件
4. **小步更新**: 避免一次更新太多
