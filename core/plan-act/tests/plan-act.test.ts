#!/usr/bin/env bun
/**
 * Plan-and-Act 集成测试
 *
 * 验收标准：
 * - AC1: Rule-based 计划生成
 * - AC2: 状态持久化到 SMA L2
 * - AC3: 失败检测触发重规划
 * - AC4: 约束注入到 Agent
 * - AC7: 性能 P95 ≤ 70ms
 *
 * @version 1.0.0
 * @created 2026-02-27
 */

import { test, expect, describe, beforeAll } from 'bun:test';
import {
  generatePlan,
  dispatchToAgent,
  nextStep,
  updateStepStatus,
  splitGoalIntoSteps,
  getPlanProgress,
  isPlanComplete,
  isPlanBlocked,
} from '../plan-dispatcher';
import {
  createPlanContext,
  savePlanContext,
  loadPlanContext,
  savePlan,
  loadPlan,
} from '../plan-context';
import {
  shouldReplan,
  updateTriggerState,
  getTriggerState,
  resetTriggerState,
  checkConstraintViolations,
} from '../lazy-replanner';
import {
  buildAgentPrompt,
  validateConstraintChecks,
  getAgentModel,
  getAgentPersonality,
} from '../agent-wrapper';
import type { Plan, PlanContext, ExecutionHistory } from '../types';

// ============ 测试数据 ============

const TEST_SESSION = `test-session-plan-act-${Date.now()}`;
const TEST_CONSTRAINTS = ['不引入新依赖', '保持向后兼容', '性能不能回退'];

// ============ AC1: Rule-based 计划生成 ============

describe('AC1: Rule-based 计划生成', () => {
  test('应该将目标分解为步骤', async () => {
    const goal = '分析需求\n设计方案\n实现功能\n测试验证';
    const plan = await generatePlan(goal, TEST_CONSTRAINTS);

    expect(plan.steps.length).toBe(4);
    expect(plan.goal).toBe(goal);
    expect(plan.constraints).toEqual(TEST_CONSTRAINTS);
  });

  test('应该正确分配 Agent', async () => {
    const plan = await generatePlan('分析用户认证需求', TEST_CONSTRAINTS);
    expect(plan.steps[0].agent).toBe('Researcher');
  });

  test('dispatchToAgent 应该返回正确的 Agent', () => {
    expect(dispatchToAgent('分析性能问题').agent).toBe('Researcher');
    expect(dispatchToAgent('设计数据库架构').agent).toBe('Architect');
    expect(dispatchToAgent('实现登录功能').agent).toBe('Coder');
    expect(dispatchToAgent('编写单元测试').agent).toBe('Tester');
    expect(dispatchToAgent('部署到生产环境').agent).toBe('Ops');
    expect(dispatchToAgent('代码审查').agent).toBe('Reviewer');
  });

  test('splitGoalIntoSteps 应该正确分解', () => {
    // 编号列表
    const numbered = splitGoalIntoSteps('1. 第一步 2. 第二步 3. 第三步');
    expect(numbered.length).toBe(3);

    // 换行分隔
    const lines = splitGoalIntoSteps('步骤一\n步骤二\n步骤三');
    expect(lines.length).toBe(3);

    // 连词分隔
    const conjunctions = splitGoalIntoSteps('先做A 然后做B 接着做C');
    expect(conjunctions.length).toBeGreaterThan(1);
  });
});

// ============ AC2: 状态持久化到 SMA L2 ============

describe('AC2: 状态持久化到 SMA L2', () => {
  test('应该创建并保存计划上下文', () => {
    const sessionId = `${TEST_SESSION}-ac2-1`;
    const context = createPlanContext(sessionId, 'test-plan-1');

    expect(context.currentPlanId).toBe('test-plan-1');
    expect(context.sessionId).toBe(sessionId);
    expect(context.activeSteps).toEqual([]);
    expect(context.completedSteps).toEqual([]);
  });

  test('应该能加载已保存的上下文', () => {
    const sessionId = `${TEST_SESSION}-ac2-2`;
    createPlanContext(sessionId, 'test-plan-2');
    const loaded = loadPlanContext(sessionId);

    expect(loaded).not.toBeNull();
    expect(loaded!.currentPlanId).toBe('test-plan-2');
  });

  test('应该能保存和加载完整计划', async () => {
    const sessionId = `${TEST_SESSION}-ac2-3`;
    const plan = await generatePlan('测试计划持久化', TEST_CONSTRAINTS);
    savePlan(sessionId, plan);

    const loaded = loadPlan(sessionId, plan.id);

    expect(loaded).not.toBeNull();
    expect(loaded!.goal).toBe('测试计划持久化');
    expect(loaded!.steps.length).toBe(plan.steps.length);
  });
});

// ============ AC3: 失败检测触发重规划 ============

describe('AC3: 失败检测触发重规划', () => {
  beforeAll(() => {
    resetTriggerState();
  });

  test('连续失败 > 2 次应触发重规划', () => {
    const history: ExecutionHistory = {
      planId: 'test',
      steps: [],
      totalDuration: 0,
      successRate: 0
    };

    // 模拟连续失败
    updateTriggerState('failure');
    updateTriggerState('failure');
    updateTriggerState('failure');

    const result = shouldReplan(history, 3);

    expect(result.trigger).toBe(true);
    expect(result.reason).toContain('连续失败');
  });

  test('成功后应重置连续失败计数', () => {
    resetTriggerState();
    updateTriggerState('failure');
    updateTriggerState('failure');
    updateTriggerState('success');

    const state = getTriggerState();
    expect(state.consecutiveFailures).toBe(0);
  });

  test('高失败率应触发重规划', () => {
    resetTriggerState();

    const history: ExecutionHistory = {
      planId: 'test',
      steps: [
        { stepId: 's1', agent: 'Coder', status: 'failed', startedAt: Date.now(), error: 'Error 1' },
        { stepId: 's2', agent: 'Coder', status: 'failed', startedAt: Date.now(), error: 'Error 2' },
        { stepId: 's3', agent: 'Coder', status: 'failed', startedAt: Date.now(), error: 'Error 3' },
        { stepId: 's4', agent: 'Coder', status: 'completed', startedAt: Date.now() },
      ],
      totalDuration: 1000,
      successRate: 0.25
    };

    const result = shouldReplan(history, 0);
    // 失败率 75% > 50%，应触发
    expect(result.trigger).toBe(true);
  });
});

// ============ AC4: 约束注入到 Agent ============

describe('AC4: 约束注入到 Agent', () => {
  test('buildAgentPrompt 应该包含约束', () => {
    const { system } = buildAgentPrompt(
      'Coder',
      '实现登录功能',
      TEST_CONSTRAINTS,
      { currentStep: 'step-0', completedSteps: [] }
    );

    expect(system).toContain('不引入新依赖');
    expect(system).toContain('保持向后兼容');
    expect(system).toContain('约束检查');
  });

  test('validateConstraintChecks 应该验证约束', () => {
    const output = `
实现了登录功能...

约束检查：
✓ 不引入新依赖 - 通过 使用了项目已有的库
✓ 保持向后兼容 - 通过 保留了旧接口
✓ 性能不能回退 - 通过 响应时间 < 100ms
`;

    const results = validateConstraintChecks(output, TEST_CONSTRAINTS);

    expect(results.length).toBe(3);
    // 至少有两个约束被检测到
    const passedCount = results.filter(r => r.passed).length;
    expect(passedCount).toBeGreaterThanOrEqual(2);
  });

  test('缺少约束检查应标记为未通过', () => {
    const output = '实现了功能，但没有约束检查部分';
    const results = validateConstraintChecks(output, TEST_CONSTRAINTS);

    expect(results.every(r => !r.passed)).toBe(true);
  });
});

// ============ AC7: 性能 P95 ≤ 70ms ============

describe('AC7: 性能 P95 ≤ 70ms', () => {
  test('计划生成应在 50ms 内完成', async () => {
    const times: number[] = [];

    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      await generatePlan(`测试任务 ${i}`, TEST_CONSTRAINTS);
      times.push(performance.now() - start);
    }

    const p95 = times.sort((a, b) => a - b)[94];
    console.log(`计划生成 P95: ${p95.toFixed(2)}ms`);

    expect(p95).toBeLessThan(50);
  });

  test('状态存取应在 20ms 内完成', () => {
    const times: number[] = [];

    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      savePlanContext(`${TEST_SESSION}-${i}`, {
        currentPlanId: `plan-${i}`,
        activeSteps: [],
        completedSteps: [],
        failedSteps: [],
        replanCount: 0,
        sessionId: `${TEST_SESSION}-${i}`,
        updatedAt: Date.now()
      });
      loadPlanContext(`${TEST_SESSION}-${i}`);
      times.push(performance.now() - start);
    }

    const p95 = times.sort((a, b) => a - b)[94];
    console.log(`状态存取 P95: ${p95.toFixed(2)}ms`);

    expect(p95).toBeLessThan(20);
  });

  test('重规划判断应在 10ms 内完成', () => {
    const times: number[] = [];

    const history: ExecutionHistory = {
      planId: 'test',
      steps: Array(10).fill(null).map((_, i) => ({
        stepId: `s${i}`,
        agent: 'Coder',
        status: i % 2 === 0 ? 'failed' as const : 'completed' as const,
        startedAt: Date.now(),
        error: i % 2 === 0 ? 'Error' : undefined
      })),
      totalDuration: 1000,
      successRate: 0.5
    };

    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      shouldReplan(history, i % 3);
      times.push(performance.now() - start);
    }

    const p95 = times.sort((a, b) => a - b)[94];
    console.log(`重规划判断 P95: ${p95.toFixed(2)}ms`);

    expect(p95).toBeLessThan(10);
  });

  test('总体框架开销 P95 ≤ 70ms', async () => {
    const times: number[] = [];

    for (let i = 0; i < 100; i++) {
      const start = performance.now();

      // 模拟完整流程
      const plan = await generatePlan(`任务 ${i}`, TEST_CONSTRAINTS);
      const step = nextStep(plan);
      if (step) {
        updateStepStatus(plan, step.id, 'running');
      }
      shouldReplan({
        planId: plan.id,
        steps: [],
        totalDuration: 0,
        successRate: 0
      }, 0);

      times.push(performance.now() - start);
    }

    const p95 = times.sort((a, b) => a - b)[94];
    console.log(`总体框架开销 P95: ${p95.toFixed(2)}ms`);

    expect(p95).toBeLessThan(70);
  });
});

// ============ 辅助功能测试 ============

describe('辅助功能', () => {
  test('getPlanProgress 应该返回正确的进度', async () => {
    const plan = await generatePlan('A\nB\nC', []);
    let progress = getPlanProgress(plan);

    expect(progress.total).toBe(3);
    expect(progress.completed).toBe(0);
    expect(progress.pending).toBe(3);
    expect(progress.percentComplete).toBe(0);

    // 更新一个步骤
    const updated = updateStepStatus(plan, 'step-0', 'completed');
    progress = getPlanProgress(updated);

    expect(progress.completed).toBe(1);
    expect(progress.pending).toBe(2);
    expect(progress.percentComplete).toBe(33);
  });

  test('isPlanComplete 应该正确判断完成状态', async () => {
    const plan = await generatePlan('A\nB', []);

    expect(isPlanComplete(plan)).toBe(false);

    let updated = updateStepStatus(plan, 'step-0', 'completed');
    updated = updateStepStatus(updated, 'step-1', 'completed');

    expect(isPlanComplete(updated)).toBe(true);
  });

  test('isPlanBlocked 应该正确判断阻塞状态', async () => {
    const plan = await generatePlan('A\nB', []);

    // 依赖未满足时应该阻塞
    let updated = updateStepStatus(plan, 'step-0', 'failed');
    // step-1 依赖 step-0，但 step-0 失败了

    expect(isPlanBlocked(updated)).toBe(true);
  });

  test('checkConstraintViolations 应该检测违反', () => {
    const result = {
      constraintsChecked: [
        { constraint: '不引入新依赖', passed: true },
        { constraint: '保持向后兼容', passed: false },
      ]
    };

    const violations = checkConstraintViolations(result, TEST_CONSTRAINTS);
    expect(violations).toContain('保持向后兼容');
  });
});

// ============ 运行测试 ============

if (import.meta.main) {
  console.log(`
╔═══════════════════════════════════════════════════════════════╗
║         Plan-and-Act 集成测试                                  ║
╠═══════════════════════════════════════════════════════════════╣
║  AC1: Rule-based 计划生成                                      ║
║  AC2: 状态持久化到 SMA L2                                      ║
║  AC3: 失败检测触发重规划                                       ║
║  AC4: 约束注入到 Agent                                         ║
║  AC7: 性能 P95 ≤ 70ms                                          ║
╚═══════════════════════════════════════════════════════════════╝

运行: bun test plan-act.test.ts
  `);
}
