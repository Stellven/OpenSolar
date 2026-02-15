# Solar 铁律: Token 效率

> **最小 Token 消耗，最大价值输出**

## 核心原则

1. **简洁优先** - 能用 1 行不用 3 行
2. **精准读取** - 不读整个文件，用 offset/limit
3. **合并调用** - 并行工具调用减少往返
4. **按需加载** - 只在需要时读取规则/文档

## TVS Footer 简化

**日常输出用简洁版 (1行):**
```
TVS v0.4.0 · zenwhite · /theme
```

**重要输出用完整版 (4行):**
```
────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list
```

## 响应长度规则

| 场景 | 长度 | 示例 |
|------|------|------|
| 简单确认 | 1-2 行 | "已完成" / "✓ 文件已保存" |
| 状态报告 | 小框 | 5-10 行 TVS 卡片 |
| 复杂任务 | 中框 | 必要信息，无冗余 |
| 架构图 | 按需 | 只在用户要求时展示 |

## 文件读取规则

```typescript
// ❌ 错误: 读取整个文件
Read({ file_path: "large-file.ts" })

// ✓ 正确: 精准读取
Read({ file_path: "large-file.ts", offset: 100, limit: 50 })

// ✓ 正确: 先搜索再定点读取
Grep({ pattern: "function handleX" })  // 找到行号
Read({ file_path: "...", offset: 找到的行号, limit: 30 })
```

## 工具调用规则

```typescript
// ❌ 错误: 串行调用
Bash("git status")
Bash("git log -3")
Bash("git diff")

// ✓ 正确: 并行调用
Bash("git status") + Bash("git log -3") + Bash("git diff")  // 同一消息
```

## 禁止行为

- ❌ 重复解释已说过的内容
- ❌ 输出用户没要求的详细文档
- ❌ 每次都读取完整的规则文件
- ❌ 冗长的 "让我来..." 开场白

## 鼓励行为

- ✓ 直接执行，结果说话
- ✓ 小任务用简洁输出
- ✓ 合并相关工具调用
- ✓ 用 grep 定位后精准读取
