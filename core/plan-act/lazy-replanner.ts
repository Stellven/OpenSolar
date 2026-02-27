#!/usr/bin/env bun
/**
 * Lazy Re-Planner - 懒重规划器
 *
 * 仅在以下情况触发重规划：
 * 1. 连续失败 > 2 次
 * 2. 约束违反
 * 3. 执行超时
 * 4. 手动触发
 *
 * @module lazy-replanner
 * @version 1.0.0
 * @created 2026-02-27
 */

import type {
  Plan,
  PlanContext,
  ReplanTrigger,
  ReplanTriggerType,
  ExecutionHistory,
  ExecutionStep,
} from './types';
import { PLAN_ACT_CONFIG } from './types';
import {
  analyzeFailurePatterns,
  generateFailureReport,
  shouldReplan as checkShouldReplan,
  FailureCategory,
  type ExecutionStep as FailureExecutionStep,
} from '../failure-analyzer';

// ============ 触发器状态 ============

interface TriggerState {
  consecutiveFailures: number;
  constraintViolations: number;
  lastCheckTime: number;
  totalReplans: number;
}

const triggerState: TriggerState = {
  consecutiveFailures: 0,
  constraintViolations: 0,
  lastCheckTime: 0,
  totalReplans: 0,
};

// ============ 核心函数 ============

/**
 * 判断是否应该触发重规划
 *
 * @param history - 执行历史
 * @param consecutiveErrors - 连续错误次数
 * @returns 是否触发及原因
 */
export function shouldReplan(
  history: ExecutionHistory,
  consecutiveErrors: number = 0
): { trigger: boolean; reason: string } {
  const config = PLAN_ACT_CONFIG.replanTriggers;

  // 1. 检查连续失败
  if (consecutiveErrors >= config.consecutiveFailures) {
    return {
      trigger: true,
      reason: `连续失败 ${consecutiveErrors} 次达到阈值 ${config.consecutiveFailures}`
    };
  }

  // 2. 检查失败模式（复用 failure-analyzer）
  const failureSteps: FailureExecutionStep[] = history.steps.map(s => ({
    stepId: s.stepId,
    action: s.agent,
    result: s.status === 'failed' ? 'failure' : 'success',
    output: s.error ? { error: s.error } : {},
    executedAt: new Date(s.startedAt).toISOString()
  }));

  if (checkShouldReplan(failureSteps, consecutiveErrors)) {
    const report = generateFailureReport(failureSteps);
    return {
      trigger: true,
      reason: `失败模式触发重规划：${report.split('\n')[0]}`
    };
  }

  // 3. 检查最大重规划次数
  if (triggerState.totalReplans >= config.maxReplanCount) {
    return {
      trigger: false,
      reason: `已达到最大重规划次数 ${config.maxReplanCount}`
    };
  }

  return {
    trigger: false,
    reason: '无需重规划'
  };
}

/**
 * 检查约束是否被违反
 *
 * @param result - 执行结果
 * @param constraints - 约束条件
 * @returns 违反的约束列表
 */
export function checkConstraintViolations(
  result: { constraintsChecked?: Array<{ constraint: string; passed: boolean }> },
  constraints: string[]
): string[] {
  const violations: string[] = [];

  if (!result.constraintsChecked) {
    // 如果没有约束检查结果，假设所有约束都需要检查
    return constraints;
  }

  for (const check of result.constraintsChecked) {
    if (!check.passed) {
      violations.push(check.constraint);
    }
  }

  return violations;
}

/**
 * 执行重规划
 *
 * @param plan - 当前计划
 * @param history - 执行历史
 * @param reason - 重规划原因
 * @returns 新计划
 */
export async function replan(
  plan: Plan,
  history: ExecutionHistory,
  reason: string
): Promise<Plan> {
  // 1. 生成失败分析报告
  const failureSteps: FailureExecutionStep[] = history.steps.map(s => ({
    stepId: s.stepId,
    action: s.agent,
    result: s.status === 'failed' ? 'failure' : 'success',
    output: s.error ? { error: s.error } : {},
    executedAt: new Date(s.startedAt).toISOString()
  }));

  const failureReport = generateFailureReport(failureSteps);
  const patterns = analyzeFailurePatterns(failureSteps);

  // 2. 调用战略家（审判官 deepseek-r1）重新规划
  // 注意：这里返回一个待执行的计划结构，实际 LLM 调用在 agent-wrapper 中进行
  const now = Date.now();

  const newPlan: Plan = {
    id: `plan-${now}-replan-${triggerState.totalReplans + 1}`,
    goal: plan.goal,
    steps: generateNewSteps(plan, patterns, failureReport),
    createdAt: plan.createdAt,
    updatedAt: now,
    currentStepIndex: 0,
    constraints: plan.constraints,
    metadata: {
      ...plan.metadata,
      replanReason: reason,
      replanCount: triggerState.totalReplans + 1,
      failurePatterns: Array.from(patterns.entries())
        .filter(([_, p]) => p.count > 0)
        .map(([cat, p]) => ({ category: cat, count: p.count }))
    }
  };

  // 3. 更新触发器状态
  triggerState.totalReplans++;
  triggerState.consecutiveFailures = 0;
  triggerState.constraintViolations = 0;

  return newPlan;
}

/**
 * 基于失败分析生成新步骤
 */
function generateNewSteps(
  oldPlan: Plan,
  patterns: Map<FailureCategory, { count: number; examples: string[] }>,
  failureReport: string
): Plan['steps'] {
  // 简单策略：保留未执行的步骤，跳过已失败的步骤
  // 实际应该调用 LLM 重新生成

  const newSteps = oldPlan.steps
    .filter(s => s.status !== 'failed')
    .map((s, i) => ({
      ...s,
      id: `step-${i}`,
      status: 'pending' as const,
      retryCount: 0,
      dependencies: i > 0 ? [`step-${i - 1}`] : [],
      result: undefined,
      error: undefined
    }));

  // 如果所有步骤都失败了，生成一个诊断步骤
  if (newSteps.length === 0) {
    newSteps.push({
      id: 'step-0',
      action: `诊断失败原因：${failureReport.slice(0, 100)}`,
      agent: 'Researcher',
      dependencies: [],
      status: 'pending',
      retryCount: 0,
      maxRetries: 1
    });
  }

  return newSteps;
}

/**
 * 更新触发器状态
 */
export function updateTriggerState(
  type: 'failure' | 'success' | 'constraint_violation'
): void {
  switch (type) {
    case 'failure':
      triggerState.consecutiveFailures++;
      break;
    case 'success':
      triggerState.consecutiveFailures = 0;
      break;
    case 'constraint_violation':
      triggerState.constraintViolations++;
      break;
  }
  triggerState.lastCheckTime = Date.now();
}

/**
 * 获取当前触发器状态
 */
export function getTriggerState(): TriggerState {
  return { ...triggerState };
}

/**
 * 重置触发器状态
 */
export function resetTriggerState(): void {
  triggerState.consecutiveFailures = 0;
  triggerState.constraintViolations = 0;
  triggerState.lastCheckTime = 0;
  // 注意：totalReplans 不重置，用于限制总重规划次数
}

// ============ LLM 重规划 (AC5) ============

/**
 * LLM 重规划结果
 */
export interface ReplanResult {
  success: boolean;
  newPlan?: Plan;
  error?: string;
  analysis?: string;
}

/**
 * 使用 LLM (审判官) 执行重规划
 *
 * @param plan - 当前计划
 * @param history - 执行历史
 * @param reason - 重规划原因
 * @param callLLM - LLM 调用函数（由外部注入）
 * @returns 重规划结果
 */
export async function replanWithLLM(
  plan: Plan,
  history: ExecutionHistory,
  reason: string,
  callLLM?: (system: string, prompt: string) => Promise<string>
): Promise<ReplanResult> {
  const { system, prompt } = generateReplanPrompt(plan, history, reason);

  // 1. 分析失败模式
  const failureSteps: FailureExecutionStep[] = history.steps.map(s => ({
    stepId: s.stepId,
    action: s.agent,
    result: s.status === 'failed' ? 'failure' : 'success',
    output: s.error ? { error: s.error } : {},
    executedAt: new Date(s.startedAt).toISOString()
  }));

  const patterns = analyzeFailurePatterns(failureSteps);
  const failureReport = generateFailureReport(failureSteps);

  // 2. 如果没有 LLM 调用函数，使用规则重规划
  if (!callLLM) {
    const newPlan = await replan(plan, history, reason);
    return {
      success: true,
      newPlan,
      analysis: failureReport
    };
  }

  try {
    // 3. 调用审判官进行深度分析
    const llmOutput = await callLLM(system, prompt);

    // 4. 解析 LLM 输出为新计划
    const newPlan = parseLLMPlanOutput(llmOutput, plan, reason);

    // 5. 更新触发器状态
    triggerState.totalReplans++;
    triggerState.consecutiveFailures = 0;
    triggerState.constraintViolations = 0;

    return {
      success: true,
      newPlan,
      analysis: llmOutput
    };

  } catch (error) {
    // LLM 调用失败，回退到规则重规划
    console.warn('[Replanner] LLM 调用失败，回退到规则重规划:', error);
    const newPlan = await replan(plan, history, reason);

    return {
      success: true,
      newPlan,
      error: `LLM 调用失败: ${error}`,
      analysis: failureReport
    };
  }
}

/**
 * 解析 LLM 输出为计划对象
 */
function parseLLMPlanOutput(
  output: string,
  oldPlan: Plan,
  reason: string
): Plan {
  const now = Date.now();

  // 尝试从输出中提取 JSON
  const jsonMatch = output.match(/```json\s*([\s\S]*?)```/);
  let steps: Plan['steps'] = [];

  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[1]);
      if (Array.isArray(parsed.steps)) {
        steps = parsed.steps.map((s: any, i: number) => ({
          id: `step-${i}`,
          action: s.action || s.description || `步骤 ${i + 1}`,
          agent: s.agent || 'Coder',
          dependencies: i > 0 ? [`step-${i - 1}`] : [],
          status: 'pending' as const,
          retryCount: 0,
          maxRetries: 3
        }));
      }
    } catch {
      // JSON 解析失败
    }
  }

  // 如果没有提取到步骤，尝试从文本中提取
  if (steps.length === 0) {
    const lines = output.split('\n').filter(l => l.trim());
    const stepLines = lines.filter(l =>
      /^\d+\.|^[一二三四五六七八九十]、|^- |^\* /.test(l.trim())
    );

    steps = stepLines.slice(0, 10).map((line, i) => ({
      id: `step-${i}`,
      action: line.replace(/^[\d一二三四五六七八九十、.\-*\s]+/, '').trim(),
      agent: guessAgentFromText(line),
      dependencies: i > 0 ? [`step-${i - 1}`] : [],
      status: 'pending' as const,
      retryCount: 0,
      maxRetries: 3
    }));
  }

  // 如果仍然没有步骤，保留原计划未执行的步骤
  if (steps.length === 0) {
    steps = oldPlan.steps
      .filter(s => s.status !== 'failed')
      .map((s, i) => ({
        ...s,
        id: `step-${i}`,
        status: 'pending' as const,
        retryCount: 0
      }));
  }

  return {
    id: `plan-${now}-llm-replan-${triggerState.totalReplans + 1}`,
    goal: oldPlan.goal,
    steps,
    createdAt: oldPlan.createdAt,
    updatedAt: now,
    currentStepIndex: 0,
    constraints: oldPlan.constraints,
    metadata: {
      ...oldPlan.metadata,
      replanReason: reason,
      replanCount: triggerState.totalReplans + 1,
      replanMethod: 'llm'
    }
  };
}

/**
 * 从文本猜测 Agent
 */
function guessAgentFromText(text: string): string {
  const lowerText = text.toLowerCase();

  if (/分析|研究|调研|评估/.test(lowerText)) return 'Researcher';
  if (/设计|架构|方案/.test(lowerText)) return 'Architect';
  if (/实现|编码|开发|修复/.test(lowerText)) return 'Coder';
  if (/测试|验证/.test(lowerText)) return 'Tester';
  if (/部署|发布/.test(lowerText)) return 'Ops';
  if (/审查|检查/.test(lowerText)) return 'Reviewer';
  if (/文档/.test(lowerText)) return 'Docs';

  return 'Coder';
}

/**
 * 验证重规划结果
 */
export function validateReplanResult(
  newPlan: Plan,
  oldPlan: Plan,
  failurePatterns: Map<FailureCategory, { count: number }>
): { valid: boolean; issues: string[] } {
  const issues: string[] = [];

  // 1. 检查新计划是否有步骤
  if (newPlan.steps.length === 0) {
    issues.push('新计划没有步骤');
  }

  // 2. 检查是否保留了目标
  if (!newPlan.goal || newPlan.goal !== oldPlan.goal) {
    issues.push('新计划的目标与原计划不一致');
  }

  // 3. 检查约束是否保留
  if (newPlan.constraints.length !== oldPlan.constraints.length) {
    issues.push('新计划的约束数量与原计划不一致');
  }

  // 4. 检查是否有重复失败的 Agent 分配
  const logicFailures = failurePatterns.get(FailureCategory.LOGIC)?.count || 0;
  if (logicFailures > 2) {
    const failedAgents = new Set(
      oldPlan.steps.filter(s => s.status === 'failed').map(s => s.agent)
    );
    const newAgents = new Set(newPlan.steps.map(s => s.agent));

    for (const agent of failedAgents) {
      if (newAgents.has(agent)) {
        // 警告但不阻止
        issues.push(`警告: 新计划仍然使用之前失败的 Agent: ${agent}`);
      }
    }
  }

  return {
    valid: issues.filter(i => !i.startsWith('警告')).length === 0,
    issues
  };
}

/**
 * 生成重规划提示（用于调用 LLM）
 */
export function generateReplanPrompt(
  plan: Plan,
  history: ExecutionHistory,
  reason: string
): { system: string; prompt: string } {
  const failureSteps: FailureExecutionStep[] = history.steps.map(s => ({
    stepId: s.stepId,
    action: s.agent,
    result: s.status === 'failed' ? 'failure' : 'success',
    output: s.error ? { error: s.error } : {},
    executedAt: new Date(s.startedAt).toISOString()
  }));

  const failureReport = generateFailureReport(failureSteps);

  const system = `你是战略家，D&D 角色是 architect，擅长重新规划。

KNOBS: rigor=4, skepticism=3, explore=4, decide=4, risk=3,
       tool=3, compression=3, check=4, empathy=2, compete=2
LEVEL=5

**任务**: 基于失败分析重新规划执行步骤

**约束条件**:
${plan.constraints.map(c => `- ${c}`).join('\n')}

**输出要求**:
1. 分析失败原因
2. 提出新的执行策略
3. 生成具体的步骤列表（JSON 格式）
4. 避免重复相同的失败模式`;

  const prompt = `**原始目标**: ${plan.goal}

**重规划原因**: ${reason}

**失败分析报告**:
${failureReport}

**原计划步骤**:
${plan.steps.map((s, i) => `${i + 1}. [${s.status}] ${s.action}`).join('\n')}

请生成新的执行计划（JSON 格式，包含 steps 数组）：`;

  return { system, prompt };
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'state') {
    console.log('\n=== Re-Planner Trigger State ===\n');
    const state = getTriggerState();
    console.log(`Consecutive Failures: ${state.consecutiveFailures}`);
    console.log(`Constraint Violations: ${state.constraintViolations}`);
    console.log(`Total Replans: ${state.totalReplans}`);
    console.log(`Last Check: ${new Date(state.lastCheckTime).toLocaleString()}`);

  } else if (command === 'test') {
    // 测试重规划判断
    const mockHistory: ExecutionHistory = {
      planId: 'test-plan',
      steps: [
        { stepId: 's1', agent: 'Coder', status: 'failed', startedAt: Date.now(), error: 'TypeError: undefined' },
        { stepId: 's2', agent: 'Coder', status: 'failed', startedAt: Date.now(), error: 'TypeError: null' },
        { stepId: 's3', agent: 'Coder', status: 'failed', startedAt: Date.now(), error: 'Syntax Error' },
      ],
      totalDuration: 5000,
      successRate: 0
    };

    console.log('\n=== 测试重规划判断 ===\n');
    const result = shouldReplan(mockHistory, 3);
    console.log(`Trigger: ${result.trigger ? 'YES' : 'NO'}`);
    console.log(`Reason: ${result.reason}`);

  } else {
    console.log(`
Lazy Re-Planner CLI

Usage:
  bun lazy-replanner.ts state  - 查看触发器状态
  bun lazy-replanner.ts test   - 测试重规划判断
    `);
  }
}

export type { TriggerState, ReplanTrigger, ReplanTriggerType };
