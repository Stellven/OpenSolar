# /analyze - 代码质量分析

## 触发
- `/analyze` - 分析当前项目
- `/analyze <文件/目录>` - 分析指定路径
- `/analyze complexity` - 复杂度分析
- `/analyze deps` - 依赖分析
- `/analyze security` - 安全检查
- `/analyze duplicates` - 重复代码检测

## 执行

### 项目概览分析

```bash
# 文件统计
echo "=== 文件统计 ==="
find . -type f -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.go" | wc -l
echo "TypeScript/JavaScript:"
find . -type f \( -name "*.ts" -o -name "*.js" \) | wc -l
echo "Python:"
find . -type f -name "*.py" | wc -l

# 代码行数
echo "=== 代码行数 ==="
find . -type f \( -name "*.ts" -o -name "*.js" \) -exec wc -l {} + | tail -1

# TODO/FIXME
echo "=== TODO/FIXME ==="
grep -r "TODO\|FIXME" --include="*.ts" --include="*.js" . | wc -l
```

### 复杂度分析

```bash
# 大文件检测 (>500行)
echo "=== 大文件 (>500行) ==="
find . -type f \( -name "*.ts" -o -name "*.js" \) -exec wc -l {} + | awk '$1 > 500 {print}'

# 长函数检测
echo "=== 长函数 (>50行) ==="
# 使用 grep 找 function 定义并计算行数

# 深层嵌套检测
echo "=== 深层嵌套 ==="
grep -rn "^        if\|^            if" --include="*.ts" . | head -10
```

### 依赖分析

```bash
# Node.js 项目
if [ -f package.json ]; then
    echo "=== 依赖统计 ==="
    jq '.dependencies | length' package.json
    jq '.devDependencies | length' package.json

    echo "=== 过时依赖检查 ==="
    npm outdated 2>/dev/null || echo "运行 npm outdated 检查"
fi

# Python 项目
if [ -f requirements.txt ]; then
    echo "=== Python 依赖 ==="
    wc -l requirements.txt
fi
```

### 安全检查

```bash
# 敏感信息检测
echo "=== 敏感信息检测 ==="
grep -rn "password\|secret\|api_key\|token" --include="*.ts" --include="*.js" --include="*.env" . 2>/dev/null | grep -v node_modules | head -10

# .env 文件检查
echo "=== .env 文件 ==="
find . -name ".env*" -type f

# 硬编码 URL/IP
echo "=== 硬编码地址 ==="
grep -rn "http://\|https://\|[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+" --include="*.ts" . | grep -v node_modules | head -10
```

### 重复代码检测

```bash
# 简单重复检测 - 找相似的代码块
echo "=== 可能的重复代码 ==="
# 找重复的 import 语句
grep -rh "^import" --include="*.ts" . | sort | uniq -c | sort -rn | head -10

# 找重复的函数签名
grep -rh "function\|const.*=.*=>" --include="*.ts" . | sort | uniq -c | sort -rn | head -10
```

## 输出格式

TVS 风格报告:
```
┌─ 📊 代码分析报告 ─────────────────────────────────────────────────┐
│                                                                   │
│  项目: [项目名]                                                   │
│  分析时间: [时间]                                                 │
│                                                                   │
├─ 统计 ────────────────────────────────────────────────────────────┤
│  文件数: XXX    代码行: XXX    TODO: XX                           │
│                                                                   │
├─ 问题 ────────────────────────────────────────────────────────────┤
│  ⚠ 大文件: X 个                                                   │
│  ⚠ 长函数: X 个                                                   │
│  ⚠ 敏感信息: X 处                                                 │
│                                                                   │
├─ 建议 ────────────────────────────────────────────────────────────┤
│  1. 拆分 xxx.ts (>500行)                                          │
│  2. 检查 xxx 中的硬编码                                           │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## 集成

- 可与 /review 配合使用
- 可在 /commit 前自动运行
- 结果可存入 ses_task_records
