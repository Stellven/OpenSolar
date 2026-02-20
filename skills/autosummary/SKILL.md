# Auto Summary Skill

自动摘要工具 - 调用牛马生成五段式会话摘要，写入 STATE.md

## 功能

1. 读取最近 N 条对话记录
2. 调用牛马 (glm-4-flash) 生成五段式摘要
3. 写入 STATE.md (增量更新，不覆盖)
4. 可选：写入 sys_favorites

## 触发方式

### 1. 自动触发
- Hook: `context-monitor.sh` 检测上下文超过 80% 阈值

### 2. 手动触发
- 说 "保存快照"
- 说 "checkpoint"
- 执行 `/autosummary`

### 3. 外部监控
- launchd 定时调用

## 使用

```bash
# 手动执行
bun ~/.claude/core/auto-summarizer.ts

# 强制执行（忽略阈值检查）
bun ~/.claude/core/auto-summarizer.ts --force

# 预览模式（不实际写入）
bun ~/.claude/core/auto-summarizer.ts --dry-run
```

## 五段式输出

```
## Mission
[一句话目标]

## Constraints
- [约束1]
- [约束2]

## Current Plan
1) [计划1]
2) [计划2]

## Decisions
- [日期] [决策]：[原因]

## Progress
- Done: [...]
- In-Progress: [...]
- Blocked: [...]

## Next Actions
- [ ] [具体命令]
```

## 配置

编辑 `~/.claude/core/auto-summarizer.ts`:

```typescript
const CONFIG = {
  maxMessages: 50,           // 读取最近多少条消息
  summaryModel: 'glm-4-flash', // 摘要用的牛马
  contextThreshold: 0.8,      // 80% 阈值
  minInterval: 10 * 60 * 1000, // 最少间隔 10 分钟
};
```

## 依赖

- `~/.claude/core/brain-router/call.ts` - 牛马调用
- `~/.claude/.solar/STATE.md` - 状态文件
- `~/.solar/solar.db` - 数据库（可选，用于 sys_favorites）

## 相关文件

- `core/auto-summarizer.ts` - 核心逻辑
- `hooks/context-monitor.sh` - 自动触发 Hook
- `rules/state-persistence.md` - 状态持久化铁律
