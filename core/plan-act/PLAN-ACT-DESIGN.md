# Plan-and-Act 集成 Solar 设计文档 v1.0

> **来源**: Plan-and-Act: A Modular Planning and Execution Framework
> **综合**: 探索派 + 审判官 + 智囊 三方会审
> **日期**: 2026-02-27
> **citation_key**: plan-act-design-v1

---

## 1. 需求定义

### 1.1 核心问题

当前 Solar 的 Agent 执行存在以下痛点：

| 痛点 | 现状 | 影响 |
|------|------|------|
| 计划僵化 | 一次性生成计划，执行中不调整 | 遇到错误只能重试或失败 |
| 状态丢失 | Agent 不感知整体进度 | 重复劳动或遗漏步骤 |
| 反馈断裂 | 执行结果不反馈给计划器 | 无法从失败中学习 |

### 1.2 目标

实现 Plan-and-Act 论文的核心机制：
1. **Planner/Executor 分离** - 计划与执行解耦
2. **动态重规划** - 基于执行反馈调整计划
3. **状态持久化** - 计划状态存入 SMA L2
4. **失败恢复** - 从失败中学习，优化重试策略

### 1.3 MVP 范围（智囊建议）

| 阶段 | 内容 | 时间 |
|------|------|------|
| **MVP** | Rule-based Plan Dispatcher + SMA L2 Plan Context | 1 周 |
| **v1.0** | + Lazy Re-Planner + 失败模式分析 | 2 周 |
| **v1.5** | + MemRL Plan Dispatcher (需 100+ 样本) | 4 周+ |

---

## 2. 架构设计

### 2.1 整体架构（探索派方案）

```
┌─────────────────────────────────────────────────────────────────┐
│                        Solar Plan-and-Act                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Planner   │───▶│  Plan State │───▶│  Executors  │         │
│  │  (分离组件)  │    │  (SMA L2)   │    │  (牛马们)   │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                 │
│         │    ┌─────────────┴─────────────┐    │                 │
│         │    │      Feedback Loop        │    │                 │
│         └────│  (执行结果 → 重规划触发)   │────┘                 │
│              └───────────────────────────┘                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┤
│  │  Lazy Re-Planner: 仅在以下情况触发                          │
│  │  • 连续失败 > 2 次                                          │
│  │  • 约束违反检测                                             │
│  │  • 执行超时                                                 │
│  └─────────────────────────────────────────────────────────────┘
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### A. Plan Dispatcher（计划分发器）

**MVP 版本: Rule-based**

```typescript
// ~/.claude/core/plan-act/plan-dispatcher.ts

interface PlanStep {
  id: string;
  action: string;
  agent?: string;           // 指定 Agent
  dependencies: string[];   // 依赖步骤 ID
  status: 'pending' | 'running' | 'completed' | 'failed';
  retryCount: number;
  maxRetries: number;
  result?: any;
  error?: string;
}

interface Plan {
  id: string;
  goal: string;
  steps: PlanStep[];
  createdAt: number;
  updatedAt: number;
  currentStepIndex: number;
  constraints: string[];    // 约束条件
}

// Rule-based 规则
const DISPATCH_RULES = [
  { pattern: /分析|研究|调研/, agent: 'Researcher' },
  { pattern: /设计|架构/, agent: 'Architect' },
  { pattern: /实现|编码|开发/, agent: 'Coder' },
  { pattern: /测试|验证/, agent: 'Tester' },
  { pattern: /部署|发布/, agent: 'Ops' },
  { pattern: /审查|检查/, agent: 'Reviewer' },
  { pattern: /文档|记录/, agent: 'Docs' },
];
```

#### B. SMA L2 Plan Context（计划状态存储）

```typescript
// 扩展 session_log 表结构
// 新增 plan_context 字段（JSON）

interface PlanContext {
  currentPlanId: string;
  activeSteps: string[];
  completedSteps: string[];
  failedSteps: string[];
  lastReplanReason?: string;
  replanCount: number;
}

// 存储到 session_log
function savePlanContext(sessionId: string, context: PlanContext): void {
  // 写入 SMA L2
  db.run(`
    INSERT INTO session_log (session_id, user_input, ai_output, timestamp)
    VALUES (?, ?, ?, ?)
  `, sessionId, '[PLAN_CONTEXT]', JSON.stringify(context), Date.now());
}
```

#### C. Lazy Re-Planner（懒重规划器）

```typescript
// ~/.claude/core/plan-act/lazy-replanner.ts

interface ReplanTrigger {
  type: 'consecutive_failures' | 'constraint_violation' | 'timeout' | 'manual';
  threshold: number;
  current: number;
}

const REPLAN_TRIGGERS: ReplanTrigger[] = [
  { type: 'consecutive_failures', threshold: 2, current: 0 },
  { type: 'constraint_violation', threshold: 1, current: 0 },
  { type: 'timeout', threshold: 60000, current: 0 },  // 60s
];

function shouldReplan(history: ExecutionHistory): { trigger: boolean; reason: string } {
  for (const trigger of REPLAN_TRIGGERS) {
    if (trigger.current >= trigger.threshold) {
      return {
        trigger: true,
        reason: `${trigger.type} reached threshold: ${trigger.current}/${trigger.threshold}`
      };
    }
  }
  return { trigger: false, reason: '' };
}

async function replan(plan: Plan, failureAnalysis: FailureReport): Promise<Plan> {
  // 1. 分析失败模式
  const patterns = analyzeFailurePatterns(failureAnalysis.history);

  // 2. 调用战略家重新规划
  const newPlan = await mcp__brain_router__complete({
    model: 'deepseek-r1',  // 审判官深度推理
    system: `你是战略家，需要基于失败分析重新规划...

    失败模式：
    ${generateFailureReport(failureAnalysis.history)}

    原计划：
    ${JSON.stringify(plan, null, 2)}

    约束：
    ${plan.constraints.join('\n')}`,
    prompt: '生成新的执行计划，避免重复相同的失败模式'
  });

  return parsePlanFromLLM(newPlan);
}
```

#### D. Agent Wrapper（Agent 包装器）

```typescript
// ~/.claude/core/plan-act/agent-wrapper.ts

interface ExecutionResult {
  success: boolean;
  output: any;
  error?: string;
  duration: number;
  constraintsChecked: ConstraintCheckResult[];
}

async function executeWithPlanContext(
  agent: string,
  task: string,
  planContext: PlanContext
): Promise<ExecutionResult> {
  const startTime = Date.now();

  try {
    // 1. 注入约束
    const constraints = await readConstraintsFromState();

    // 2. 调用 Agent
    const result = await callAgent(agent, {
      task,
      constraints,
      planContext: {
        currentStep: planContext.activeSteps[0],
        completedSteps: planContext.completedSteps
      }
    });

    // 3. 验证约束检查
    const constraintChecks = validateConstraintChecks(result, constraints);

    // 4. 更新计划状态
    updatePlanStep(planContext.currentPlanId, stepId, {
      status: 'completed',
      result
    });

    return {
      success: true,
      output: result,
      duration: Date.now() - startTime,
      constraintsChecked: constraintChecks
    };

  } catch (error) {
    // 记录失败
    recordFailure(planContext.currentPlanId, stepId, error);

    // 检查是否需要重规划
    const { trigger, reason } = shouldReplan(getExecutionHistory());

    if (trigger) {
      await triggerReplan(planContext.currentPlanId, reason);
    }

    return {
      success: false,
      output: null,
      error: error.message,
      duration: Date.now() - startTime,
      constraintsChecked: []
    };
  }
}
```

### 2.3 数据流

```
用户请求 → Plan Dispatcher 生成计划
              │
              ▼
         存入 SMA L2 (Plan Context)
              │
              ▼
         Agent Wrapper 执行步骤
              │
              ├── 成功 → 更新状态 → 下一步
              │
              └── 失败 → 记录失败 → Lazy Re-Planner 判断
                                           │
                              ┌────────────┴────────────┐
                              ▼                         ▼
                         不需要重规划              触发重规划
                              │                         │
                              ▼                         ▼
                         重试当前步骤           战略家生成新计划
                                                       │
                                                       ▼
                                                  更新 SMA L2
```

---

## 3. 验收标准

### 3.1 功能验收（智囊建议）

| ID | 验收项 | 标准 | 优先级 |
|----|--------|------|--------|
| AC1 | 计划生成 | Rule-based 正确分配 Agent | P0 |
| AC2 | 状态持久化 | 计划状态存入 SMA L2，可恢复 | P0 |
| AC3 | 失败检测 | 连续失败 > 2 次触发重规划 | P0 |
| AC4 | 约束注入 | Agent 输出包含约束检查 | P0 |
| AC5 | 重规划 | 战略家生成新计划，避免历史失败 | P1 |
| AC6 | 端到端 | 完整任务流程成功执行 | P1 |
| AC7 | 性能 | P95 延迟 ≤ 70ms（不含 LLM 调用）| P1 |
| AC8 | 成功率 | 任务成功率 ≥ 85% | P1 |

### 3.2 性能指标（审判官建议）

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 计划分发延迟 | P95 ≤ 50ms | Rule-based 规则匹配 |
| 状态存取延迟 | P95 ≤ 20ms | SQLite 写入/读取 |
| 重规划触发延迟 | P95 ≤ 10ms | 条件判断 |
| 总体框架开销 | P95 ≤ 70ms | 不含 LLM 调用 |
| 最大重试次数 | 3 次 | 防止无限循环 |

### 3.3 测试用例

```typescript
// tests/plan-act.test.ts

describe('Plan-and-Act Integration', () => {

  test('AC1: Rule-based 计划生成', async () => {
    const plan = await generatePlan('分析 Rust 异步编程');
    expect(plan.steps[0].agent).toBe('Researcher');
  });

  test('AC2: 状态持久化到 SMA L2', async () => {
    const context = createPlanContext('test-plan');
    savePlanContext('session-1', context);

    const restored = loadPlanContext('session-1');
    expect(restored.currentPlanId).toBe('test-plan');
  });

  test('AC3: 失败检测触发重规划', async () => {
    const history = createFailureHistory(3); // 连续失败 3 次
    const { trigger, reason } = shouldReplan(history);
    expect(trigger).toBe(true);
    expect(reason).toContain('consecutive_failures');
  });

  test('AC4: 约束注入到 Agent', async () => {
    const constraints = ['不引入新依赖', '保持向后兼容'];
    const prompt = buildAgentPrompt('Coder', '实现登录功能', constraints);
    expect(prompt).toContain('不引入新依赖');
    expect(prompt).toContain('约束检查');
  });

  test('AC7: 性能 P95 ≤ 70ms', async () => {
    const times = [];
    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      await executePlanStep(mockPlan, i);
      times.push(performance.now() - start);
    }
    const p95 = times.sort((a, b) => a - b)[94];
    expect(p95).toBeLessThan(70);
  });
});
```

---

## 4. 风险与缓解（审判官 + 智囊）

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| MemRL 冷启动 | 高 | MVP 使用 Rule-based，积累 100+ 样本后引入 MemRL |
| 状态同步失败 | 中 | 使用事务 + 重试机制 |
| 无限重规划循环 | 中 | 最大重试 3 次，最大重规划 2 次 |
| RAG 召回偏差 | 中 | Entity Anchoring + 时间衰减排序 |
| LLM 规划不稳定 | 中 | 结构化输出 schema + 验证层 |

---

## 5. 实施计划

```
Week 1 (MVP):
├── Day 1-2: Plan Dispatcher (Rule-based)
├── Day 3-4: SMA L2 Plan Context
└── Day 5: 集成测试 + AC1-AC4 验收

Week 2 (v1.0):
├── Day 1-2: Lazy Re-Planner
├── Day 3-4: 失败模式分析集成
└── Day 5: 端到端测试 + AC5-AC8 验收

Week 3+ (v1.5):
├── 收集 100+ 计划样本
├── 训练 MemRL 模型（可选）
└── A/B 测试 Rule-based vs MemRL
```

---

## 6. 决策记录

| 决策 | 选择 | 原因 | 日期 |
|------|------|------|------|
| Plan Dispatcher | Rule-based MVP | 避免冷启动，快速验证 | 2026-02-27 |
| 状态存储 | SMA L2 (session_log) | 复用现有架构，低延迟 | 2026-02-27 |
| 重规划触发 | Lazy (失败驱动) | 减少 LLM 调用，节省成本 | 2026-02-27 |
| 失败分析 | 复用 failure-analyzer.ts | 避免重复开发 | 2026-02-27 |

---

## 7. 与现有组件的集成

### 7.1 SMA 集成

```
Plan-and-Act          SMA 组件
─────────────────────────────────────────
Plan Context    →     SMA L2 (session_log)
Failure Log     →     SMA L2 (session_log)
Knowledge       →     SMA L3 (knowledge_triples)
```

### 7.2 Agent 集成

```
Plan Dispatcher 规则映射:

任务类型          Agent           调用模型
─────────────────────────────────────────
分析/研究/调研    @Researcher     deepseek-r1
设计/架构         @Architect      gemini-2.5-pro
实现/编码/开发    @Coder          glm-5
测试/验证         @Tester         glm-5
部署/发布         @Ops            glm-5
审查/检查         @Reviewer       gemini-2.5-pro
文档/记录         @Docs           glm-5
```

### 7.3 约束注入集成

```typescript
// 复用 call-niuma-with-personality.md 中的约束注入机制
import { readConstraintsFromState } from '~/.claude/rules/call-niuma-with-personality';

// 在 Agent Wrapper 中注入约束
const constraints = await readConstraintsFromState();
const prompt = buildAgentPrompt(agent, task, constraints);
```

---

## 8. 附录：论文核心概念映射

| 论文概念 | Solar 实现 | 文件 |
|----------|------------|------|
| Planner | Plan Dispatcher | plan-dispatcher.ts |
| Executor | Agent Wrapper | agent-wrapper.ts |
| Plan State | SMA L2 Plan Context | - |
| Replanner | Lazy Re-Planner | lazy-replanner.ts |
| Synthetic Data | 收集执行日志 | - |
| MemRL | v1.5 计划 | - |

---

*Design Document v1.0 - 2026-02-27*
*Saved to: Cortex (plan-act-design-v1), sys_favorites, ~/.claude/core/plan-act/PLAN-ACT-DESIGN.md*
