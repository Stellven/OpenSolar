# /diff - 智能差异分析

## 触发
- `/diff` - 当前未提交变更摘要
- `/diff <file1> <file2>` - 比较两个文件
- `/diff <branch>` - 与分支比较
- `/diff <commit1> <commit2>` - 比较两个提交
- `/diff --summary` - 只显示摘要统计

## 执行

### Git 差异

```bash
# 未提交的变更 (工作区 vs 暂存区)
git diff

# 暂存的变更 (暂存区 vs HEAD)
git diff --cached

# 所有变更 (工作区 vs HEAD)
git diff HEAD

# 与某分支比较
git diff main

# 两个提交之间
git diff $COMMIT1 $COMMIT2

# 只看统计
git diff --stat

# 只看文件名
git diff --name-only
```

### 智能摘要

```bash
# 变更统计
echo "=== 变更统计 ==="
git diff --stat HEAD | tail -1

# 变更文件分类
echo "=== 变更文件 ==="
git diff --name-only HEAD | while read f; do
  EXT="${f##*.}"
  case "$EXT" in
    ts|js|tsx|jsx) echo "📜 $f" ;;
    css|scss|less) echo "🎨 $f" ;;
    md|txt) echo "📝 $f" ;;
    json|yaml|yml) echo "⚙️ $f" ;;
    *) echo "📄 $f" ;;
  esac
done

# 新增/修改/删除统计
echo "=== 操作统计 ==="
ADDED=$(git diff --diff-filter=A --name-only HEAD | wc -l | tr -d ' ')
MODIFIED=$(git diff --diff-filter=M --name-only HEAD | wc -l | tr -d ' ')
DELETED=$(git diff --diff-filter=D --name-only HEAD | wc -l | tr -d ' ')
echo "新增: $ADDED, 修改: $MODIFIED, 删除: $DELETED"
```

### 文件比较

```bash
# 使用 diff
diff -u "$FILE1" "$FILE2"

# 并排显示
diff -y "$FILE1" "$FILE2"

# 使用 colordiff (更好看)
brew install colordiff
colordiff -u "$FILE1" "$FILE2"

# 使用 delta (推荐)
brew install git-delta
diff -u "$FILE1" "$FILE2" | delta
```

### 可视化工具

```bash
# 使用 VS Code
code --diff "$FILE1" "$FILE2"

# 使用 Git 自带
git difftool -y "$FILE1" "$FILE2"

# 配置 delta 为默认 pager
git config --global core.pager delta
git config --global interactive.diffFilter "delta --color-only"
```

### 分支比较

```bash
# 当前分支 vs main 的变更
git log main..HEAD --oneline

# 文件级别差异
git diff main...HEAD --stat

# 生成补丁
git diff main > changes.patch
```

## 输出格式

```
┌─ 📊 Diff Summary ───────────────────────────────────────────────┐
│                                                                  │
│  比较: HEAD vs working tree                                      │
│  变更: 5 files changed, +127, -43                               │
│                                                                  │
├─ 文件列表 ───────────────────────────────────────────────────────┤
│                                                                  │
│  📜 src/index.ts          +45  -12                               │
│  📜 src/utils/helper.ts   +32  -8                                │
│  🎨 styles/main.css       +20  -15                               │
│  ⚙️ package.json          +5   -3                                │
│  📝 README.md             +25  -5                                │
│                                                                  │
├─ 主要变更 ───────────────────────────────────────────────────────┤
│                                                                  │
│  • src/index.ts: 新增 handleError 函数                           │
│  • src/utils: 重构 helper 工具函数                               │
│  • package.json: 更新 typescript 版本                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Git Delta 配置 (推荐)

```gitconfig
# ~/.gitconfig
[core]
    pager = delta

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    light = false
    side-by-side = true
    line-numbers = true
```

## 常用别名

```bash
# ~/.zshrc
alias gd="git diff"
alias gds="git diff --staged"
alias gdn="git diff --name-only"
alias gdst="git diff --stat"
```
