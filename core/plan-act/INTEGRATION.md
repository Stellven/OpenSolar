# Plan-and-Act 集成说明

## 状态：已集成到语义引擎

### 1. 自然语言触发

当用户输入以下类型的语句时，系统会自动识别并触发 Plan-and-Act：

| 触发词 | 示例 | 置信度 |
|--------|------|--------|
| 实现一个 | "实现一个用户登录功能" | 68%+ |
| 开发一个 | "开发一个缓存模块" | 68%+ |
| 写一个 | "写个工具函数" | 66%+ |
| 做个 | "做个登录页面" | 66%+ |
| 帮我实现 | "帮我实现支付功能" | 68%+ |
| 重构 | "重构支付模块" | 68%+ |
| 集成 | "集成微信支付" | 68%+ |
| 修复这个 | "修复登录bug" | 72%+ |
| 调试 | "调试这个错误" | 68%+ |

### 2. 调用链路

```
用户输入 "实现一个登录功能"
    ↓
intent-matcher.ts (语义匹配)
    ↓ 识别为 plan_and_act
intent-dispatcher.ts (调度)
    ↓
real-executor.ts (执行)
    ↓
mcp__brain-router__complete (调用 LLM)
    ↓
返回执行结果
```

### 3. 手动测试

```bash
# 测试意图识别
bun ~/.claude/core/nerve/intent-matcher.ts match "实现一个登录功能"

# 测试调度器（需确认）
bun ~/.claude/core/nerve/intent-dispatcher.ts dispatch "实现一个登录功能"

# 快速执行（跳过确认）
bun ~/.claude/core/nerve/intent-dispatcher.ts quick "实现一个登录功能"
```

### 4. 在 Claude Code 中使用

当用户说以下话时，Claude Code 应该：

1. **检测意图**：调用 `matchIntent()` 识别用户意图
2. **如果是 plan_and_act**：调用 `executePlanWithMCP()` 执行
3. **返回 MCP 调用列表**：让 Claude Code 通过 MCP 执行实际调用

### 5. 文件结构

```
~/.claude/core/
├── nerve/
│   ├── intent-matcher.ts     # 语义匹配器 (已优化)
│   └── intent-dispatcher.ts  # 意图调度器 (新建)
└── plan-act/
    ├── real-executor.ts      # 真实执行器
    ├── agent-wrapper.ts      # Agent 包装器 (已修复)
    └── ... (其他文件)
```

### 6. 铁律遵守

- ✅ 无 Mock：所有调用都是真实的 MCP 调用
- ✅ 有入口：intent-dispatcher.ts 提供统一入口
- ✅ 可验证：端到端测试通过

---

*集成完成: 2026-02-27*
