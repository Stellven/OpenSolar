---
name: precise-edit
description: 精准定位编辑 - Grep→Read→Edit 三步合一
user-invocable: true
argument-hint: "<file> <pattern> <new-content>"
---

# /precise-edit - 精准定位编辑

> **来源: 2026-02-03 "熟练"的证明 = 封装成更好用的工具**

把 Grep→Read→Edit 三步操作封装成一步。

## 用法

```
/precise-edit <file> <pattern> <new-content>
```

## 参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `file` | 目标文件路径 | `src/index.ts` |
| `pattern` | 要匹配的正则/文本 | `function oldName` |
| `new-content` | 替换后的内容 | `function newName` |

## 执行流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRECISE EDIT FLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Grep 定位                                              │
│  ─────────────────────────────────────────────────────────────  │
│  • 搜索 pattern 在 file 中的位置                                │
│  • 获取行号和上下文                                             │
│  • 如果无匹配 → 报告并退出                                      │
│  • 如果多处匹配 → 列出让用户选择                                │
│                                                                 │
│  Step 2: Read 验证                                              │
│  ─────────────────────────────────────────────────────────────  │
│  • 读取匹配位置 ±5 行上下文                                     │
│  • 展示给用户确认                                               │
│  • 高亮匹配部分                                                 │
│                                                                 │
│  Step 3: Edit 替换                                              │
│  ─────────────────────────────────────────────────────────────  │
│  • 执行精准替换                                                 │
│  • 显示 diff                                                    │
│  • 确认成功                                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 示例

### 基本用法

```
/precise-edit src/utils.ts "function calculateTotal" "function computeSum"
```

输出：
```
┌─ 🎯 Precise Edit ───────────────────────────────────────────────┐
│                                                                 │
│  File     src/utils.ts                                          │
│  Pattern  function calculateTotal                               │
│  Found    Line 42                                                │
│                                                                 │
│  Context (±5 lines):                                            │
│  ─────────────────────────────────────────────────────────────  │
│  37 │ // Helper functions                                       │
│  38 │                                                           │
│  39 │ /**                                                       │
│  40 │  * Calculate the total price                              │
│  41 │  */                                                       │
│  42 │ function calculateTotal(items: Item[]) {  ← MATCH         │
│  43 │   return items.reduce((sum, i) => sum + i.price, 0);      │
│  44 │ }                                                         │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Replace with: function computeSum                              │
│                                                                 │
│  [Y] Confirm  [N] Cancel  [E] Edit pattern                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 多处匹配

```
/precise-edit src/api.ts "TODO" "DONE"
```

输出：
```
┌─ 🎯 Precise Edit ───────────────────────────────────────────────┐
│                                                                 │
│  Found 3 matches:                                               │
│                                                                 │
│  [1] Line 15: // TODO: add error handling                       │
│  [2] Line 89: // TODO: optimize this loop                       │
│  [3] Line 156: // TODO: add tests                               │
│                                                                 │
│  Select: [1] [2] [3] [A]ll [C]ancel                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 对比

| 之前 (手动三步) | 之后 (/precise-edit) |
|-----------------|---------------------|
| 1. `Grep pattern file` | 1. `/precise-edit file pattern new` |
| 2. `Read file offset limit` | (自动) |
| 3. `Edit file old new` | (自动) |
| 需要 3 次工具调用 | 1 次命令 |
| 需要手动算行号 | 自动计算 |
| 容易出错 | 有确认步骤 |

## 选项

| 选项 | 说明 |
|------|------|
| `--all` | 替换所有匹配（不询问） |
| `--dry-run` | 只显示会替换什么，不实际执行 |
| `--context N` | 显示 ±N 行上下文（默认 5） |

## 错误处理

| 情况 | 行为 |
|------|------|
| 文件不存在 | 报错并退出 |
| 无匹配 | 提示 "Pattern not found" |
| 多处匹配 | 列出选项让用户选择 |
| 替换失败 | 显示错误，不修改文件 |

## 为什么这是"熟练"的证明

```
使用 Grep→Read→Edit 多次
    ↓
发现痛点：三步太繁琐，容易出错
    ↓
抽象成通用模式
    ↓
封装成 /precise-edit
    ↓
下次一步完成
    ↓
这才是"熟练" ✓
```

---

*Precise Edit Skill*
*从 Grep→Read→Edit 模式中封装*
*2026-02-03*
