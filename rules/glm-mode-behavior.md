# Solar 铁律: GLM 全量模式行为

> **来源: 2026-02-06 监护人指示**
> **目标: 用GLM模式下，尽可能用GLM执行任务 (60%+)**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    GLM FULL MODE BEHAVIOR                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   激活口令: "用GLM" / "智谱"                                    │
│                                                                 │
│   核心机制: 绕过 Task Agent，通过 Brain Router 调用 GLM         │
│                                                                 │
│   比例目标: Claude 40% (编排) | GLM 60% (执行)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 为什么要绕过 Task Agent

```
Task 工具的 model 参数只能选: sonnet | opus | haiku
都是 Claude 系列，无法指定 GLM

解决方案: 不用 Task Agent，改用 Brain Router 直接调用 GLM
```

## 执行方式

### 检测当前模式

```sql
SELECT mode_id FROM sroe_routing_modes
WHERE mode_id = (SELECT preference_value FROM sys_preferences WHERE preference_key = 'current_routing_mode')
```

或调用: `mcp__brain-router__current_mode`

### GLM 模式下的任务执行

**❌ 不要用 Task Agent:**
```typescript
Task({
  subagent_type: "coder",
  prompt: "实现 fibonacci 函数"
})
// → 会用 Claude Sonnet
```

**✅ 用 Brain Router:**
```typescript
mcp__brain-router__complete({
  model: "glm-4-plus",
  system: "你是一个专业的软件工程师。请编写高质量代码。",
  prompt: "实现 fibonacci 函数，要求：\n1. 支持大数\n2. 有完整注释"
})
// → 用 GLM-4-Plus
```

## 任务类型与 System Prompt

### 编码任务 (Coder)

```
你是一个专业的软件工程师。

要求:
1. 代码简洁清晰，符合最佳实践
2. 有必要的注释说明
3. 考虑边界情况和错误处理
4. 使用现代语法特性
```

### 测试任务 (Tester)

```
你是一个专业的测试工程师。

要求:
1. 覆盖正常情况 (happy path)
2. 覆盖边界情况 (edge cases)
3. 覆盖异常情况 (error cases)
4. 测试用例清晰易懂
5. 使用 describe/it 或类似结构组织
```

### 审查任务 (Reviewer)

```
你是一个资深的代码审查者。

检查点:
1. 代码质量和可读性
2. 潜在的 bug 或逻辑错误
3. 性能问题
4. 安全隐患
5. 改进建议

输出格式:
- 🔴 严重问题
- 🟡 建议改进
- 🟢 优点
```

### 分析任务 (Researcher)

```
你是一个技术分析专家。

要求:
1. 结构化分析
2. 有理有据
3. 给出具体建议
4. 考虑多个维度
```

## 任务路由表

| 任务类型 | 正常模式 | GLM 模式 |
|----------|----------|----------|
| 主脑编排 | Claude | Claude (无法替换) |
| 工具调用 | 直接执行 | 直接执行 |
| 写代码 | Task(coder) | brain-router(glm-4-plus) |
| 写测试 | Task(tester) | brain-router(glm-4-plus) |
| 代码审查 | Task(reviewer) | brain-router(glm-4-plus) |
| 技术分析 | Task(Explore) | brain-router(glm-4-plus) |
| 文档编写 | Task(docs) | brain-router(glm-4-plus) |

## 成本对比

| 方式 | 成本 (每1K tokens) |
|------|-------------------|
| Task Agent (Claude Sonnet) | ~$0.003 |
| Brain Router (GLM-4-Plus) | ~$0.0002 |

**节省: ~93%**

## 自检清单

GLM 模式下执行任务时:

- [ ] 当前是 glm_only 模式？
- [ ] 需要生成内容（代码/测试/分析）？
- [ ] 用 Brain Router 而不是 Task Agent？
- [ ] System Prompt 设置正确？

## 流程图

```
监护人: "帮我写个函数"
     │
     ▼
Solar (Claude): 理解需求
     │
     ├─ 检查模式: glm_only ✓
     │
     ▼
mcp__brain-router__complete({
  model: "glm-4-plus",
  system: "你是专业程序员...",
  prompt: "实现..."
})
     │
     ▼
GLM-4-Plus: 生成代码
     │
     ▼
Solar (Claude): 接收结果，可能用工具写入文件
     │
     ▼
输出给监护人
```

---

*GLM Mode Behavior v1.0*
*建立于: 2026-02-06*
*监护人指示: 尽可能用GLM*
