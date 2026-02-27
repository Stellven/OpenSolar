#!/usr/bin/env bun
/**
 * Plan Dispatcher (Rule-based)
 *
 * 功能:
 * 1. 将目标分解为步骤
 * 2. 使用规则匹配 Agent
 * 3. 自动检测依赖关系
 * 4. 返回完整计划
 *
 * @module plan-dispatcher
 * @version 1.0.0
 * @created 2026-02-27
 */

import type {
  Plan,
  PlanStep,
  PlanStepStatus,
  DispatchRule,
} from './types';
import { DISPATCH_RULES } from './types';

// ============ 常量 ============

/**
 * 默认 Agent 配置（无匹配时使用）
 */
const DEFAULT_AGENT = {
  agent: 'Coder',
  model: 'glm-5'
};

// ============ 核心函数 ============

/**
 * 将高级目标分解为可执行步骤
 *
 * 支持的分解模式：
 * 1. 编号列表 (1. 2. 3.)
 * 2. 换行分隔
 * 3. 连词分隔 (then, 然后)
 *
 * @param goal - 目标描述
 * @returns 步骤描述数组
 */
export function splitGoalIntoSteps(goal: string): string[] {
  if (!goal || typeof goal !== 'string') return [];

  // 1. 处理编号列表 (如 "1. 做 X")
  if (/\d+\.\s/.test(goal)) {
    return goal.split(/\s*(?=\d+\.\s)/)
      .map(s => s.replace(/^\d+\.\s*/, '').trim())
      .filter(Boolean);
  }

  // 2. 处理换行分隔
  const lines = goal.split(/\n+/).map(l => l.trim()).filter(Boolean);
  if (lines.length > 1) return lines;

  // 3. 处理连词 "然后", "接着", "followed by"
  const conjunctionSplit = goal.split(/\s*(?:and\s+then|then|followed\s+by|然后|接着)\s*/i);
  if (conjunctionSplit.length > 1) {
    return conjunctionSplit.map(s => s.trim()).filter(s => s.length > 0);
  }

  // 4. 回退：单个步骤
  return [goal.trim()].filter(Boolean);
}

/**
 * 根据规则将任务分发给最佳匹配的 Agent
 *
 * @param task - 任务描述
 * @returns 包含 agent 名称和 model 的对象
 */
export function dispatchToAgent(task: string): { agent: string; model: string } {
  if (!task) return DEFAULT_AGENT;

  const matches = DISPATCH_RULES
    .filter((rule: DispatchRule) => rule.pattern.test(task))
    .sort((a: DispatchRule, b: DispatchRule) => (b.priority || 0) - (a.priority || 0));

  if (matches.length === 0) return DEFAULT_AGENT;

  const best = matches[0];
  return {
    agent: best.agent,
    model: best.model || DEFAULT_AGENT.model
  };
}

/**
 * 从目标生成执行计划
 *
 * @param goal - 要达成的目标
 * @param constraints - 需要遵守的约束条件
 * @returns 返回完整计划的 Promise
 */
export async function generatePlan(goal: string, constraints: string[]): Promise<Plan> {
  const stepDescriptions = splitGoalIntoSteps(goal);
  const now = Date.now();

  // 检测依赖关系（简单线性依赖：步骤[i] 依赖 步骤[i-1]）
  const steps: PlanStep[] = stepDescriptions.map((desc, index) => {
    const { agent, model } = dispatchToAgent(desc);

    const deps: string[] = [];
    if (index > 0) {
      deps.push(`step-${index - 1}`);
    }

    return {
      id: `step-${index}`,
      action: desc,
      agent: agent,
      dependencies: deps,
      status: 'pending' as PlanStepStatus,
      retryCount: 0,
      maxRetries: 3,
      result: undefined,
      error: undefined
    };
  });

  const plan: Plan = {
    id: `plan-${now}`,
    goal: goal,
    steps: steps,
    createdAt: now,
    updatedAt: now,
    currentStepIndex: 0,
    constraints: constraints
  };

  return plan;
}

/**
 * 从计划中获取下一个可执行的步骤
 *
 * 检查依赖是否满足：
 * - 状态必须为 pending
 * - 所有依赖必须为 completed
 *
 * @param plan - 当前计划状态
 * @returns 下一个可执行的 PlanStep，如果完成或阻塞则返回 null
 */
export function nextStep(plan: Plan): PlanStep | null {
  const { steps } = plan;

  for (const step of steps) {
    if (step.status !== 'pending') continue;

    // 检查依赖是否满足
    const depsSatisfied = step.dependencies.every(depId => {
      const depStep = steps.find(s => s.id === depId);
      return depStep && depStep.status === 'completed';
    });

    if (depsSatisfied) {
      return step;
    }
  }

  // 检查计划是否真正完成
  const allDone = steps.every(s => s.status === 'completed' || s.status === 'skipped');
  if (allDone) return null;

  // 步骤待执行但依赖失败 -> 计划卡住
  return null;
}

/**
 * 以不可变方式更新特定步骤的状态
 *
 * @param plan - 当前计划
 * @param stepId - 要更新的步骤 ID
 * @param status - 新状态
 * @param result - 可选的结果数据
 * @returns 包含更新步骤的新 Plan 对象
 */
export function updateStepStatus(
  plan: Plan,
  stepId: string,
  status: PlanStepStatus,
  result?: unknown
): Plan {
  const now = Date.now();

  const updatedSteps = plan.steps.map(step => {
    if (step.id !== stepId) return step;

    return {
      ...step,
      status: status,
      result: result !== undefined ? result : step.result,
      retryCount: status === 'failed' ? step.retryCount + 1 : step.retryCount,
      error: status === 'failed' && result && typeof result === 'object' && 'message' in result
        ? (result as Error).message
        : undefined,
      completedAt: status === 'completed' ? now : step.completedAt,
      startedAt: status === 'running' ? now : step.startedAt
    };
  });

  return {
    ...plan,
    steps: updatedSteps,
    updatedAt: now
  };
}

/**
 * 获取计划的进度统计
 *
 * @param plan - 计划对象
 * @returns 进度统计信息
 */
export function getPlanProgress(plan: Plan): {
  total: number;
  completed: number;
  pending: number;
  failed: number;
  percentComplete: number;
} {
  const total = plan.steps.length;
  const completed = plan.steps.filter(s => s.status === 'completed').length;
  const pending = plan.steps.filter(s => s.status === 'pending').length;
  const failed = plan.steps.filter(s => s.status === 'failed').length;

  return {
    total,
    completed,
    pending,
    failed,
    percentComplete: total > 0 ? Math.round((completed / total) * 100) : 0
  };
}

/**
 * 检查计划是否已完成（全部成功或跳过）
 *
 * @param plan - 计划对象
 * @returns 是否已完成
 */
export function isPlanComplete(plan: Plan): boolean {
  return plan.steps.every(s => s.status === 'completed' || s.status === 'skipped');
}

/**
 * 检查计划是否被阻塞（有待执行步骤但依赖失败）
 *
 * @param plan - 计划对象
 * @returns 是否被阻塞
 */
export function isPlanBlocked(plan: Plan): boolean {
  const hasPending = plan.steps.some(s => s.status === 'pending');
  const noExecutable = nextStep(plan) === null;
  return hasPending && noExecutable && !isPlanComplete(plan);
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'test') {
    // 测试计划生成
    const testGoal = `
      分析用户认证需求
      设计认证架构
      实现 JWT 认证
      编写单元测试
      部署到测试环境
    `;

    console.log('=== 测试计划生成 ===\n');
    console.log(`目标: ${testGoal.trim()}\n`);

    const plan = generatePlan(testGoal, ['不引入新依赖', '保持向后兼容']);

    plan.then(p => {
      console.log(`计划 ID: ${p.id}`);
      console.log(`步骤数: ${p.steps.length}`);
      console.log(`约束: ${p.constraints.join(', ')}\n`);

      console.log('步骤:');
      p.steps.forEach((step, i) => {
        console.log(`  ${i + 1}. [${step.agent}] ${step.action}`);
        console.log(`     依赖: ${step.dependencies.length > 0 ? step.dependencies.join(', ') : '无'}`);
      });

      console.log('\n进度:', getPlanProgress(p));
    });
  } else {
    console.log(`
Plan Dispatcher CLI

Usage:
  bun plan-dispatcher.ts test  - 测试计划生成功能
    `);
  }
}

export type { Plan, PlanStep, PlanStepStatus };
