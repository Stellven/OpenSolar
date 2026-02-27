#!/usr/bin/env bun
/**
 * Plan Executor - 端到端计划执行器
 *
 * 功能：
 * 1. 完整执行计划
 * 2. 步骤依赖检查
 * 3. 自动重试机制
 * 4. 失败时触发重规划
 * 5. 进度跟踪和日志
 *
 * @module plan-executor
 * @version 1.0.0
 * @created 2026-02-27
 */

import type {
  Plan,
  PlanStep,
  PlanContext,
  ExecutionResult,
  ExecutionHistory,
  AgentCallParams,
} from './types';
import { PLAN_ACT_CONFIG } from './types';
import { nextStep, updateStepStatus, getPlanProgress, isPlanComplete, isPlanBlocked } from './plan-dispatcher';
import { createPlanContext, loadPlanContext, savePlan, savePlanContext, updatePlanContext } from './plan-context';
import { shouldReplan, replanWithLLM, updateTriggerState, validateReplanResult } from './lazy-replanner';
import { executeWithPlanContext, buildAgentPrompt, getAgentModel } from './agent-wrapper';

// ============ 类型定义 ============

export interface ExecutorConfig {
  maxRetries: number;
  retryBackoffMs: number;
  enableReplan: boolean;
  maxReplans: number;
  timeoutMs: number;
  onProgress?: (progress: ExecutionProgress) => void;
  onStepStart?: (step: PlanStep) => void;
  onStepComplete?: (step: PlanStep, result: ExecutionResult) => void;
  onReplan?: (oldPlan: Plan, newPlan: Plan, reason: string) => void;
}

export interface ExecutionProgress {
  planId: string;
  totalSteps: number;
  completedSteps: number;
  failedSteps: number;
  currentStep: string | null;
  percentComplete: number;
  status: 'running' | 'completed' | 'failed' | 'replanning';
  startedAt: number;
  elapsedMs: number;
}

export interface ExecutionReport {
  planId: string;
  sessionId: string;
  status: 'success' | 'partial' | 'failed';
  totalSteps: number;
  completedSteps: number;
  failedSteps: number;
  replanCount: number;
  durationMs: number;
  steps: StepReport[];
  errors: string[];
}

export interface StepReport {
  stepId: string;
  action: string;
  agent: string;
  status: PlanStep['status'];
  durationMs: number;
  retryCount: number;
  error?: string;
  output?: unknown;
}

const DEFAULT_CONFIG: ExecutorConfig = {
  maxRetries: PLAN_ACT_CONFIG.retry.maxRetries,
  retryBackoffMs: PLAN_ACT_CONFIG.retry.backoffMs,
  enableReplan: true,
  maxReplans: PLAN_ACT_CONFIG.replanTriggers.maxReplanCount,
  timeoutMs: PLAN_ACT_CONFIG.replanTriggers.timeoutMs,
};

// ============ 核心执行器 ============

/**
 * 端到端执行计划
 *
 * @param plan - 要执行的计划
 * @param sessionId - 会话 ID
 * @param constraints - 约束条件
 * @param config - 执行配置
 * @param callAgent - Agent 调用函数（外部注入）
 * @returns 执行报告
 */
export async function executePlan(
  plan: Plan,
  sessionId: string,
  constraints: string[] = [],
  config: Partial<ExecutorConfig> = {},
  callAgent?: (params: AgentCallParams) => Promise<unknown>
): Promise<ExecutionReport> {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const startTime = Date.now();
  const stepReports: StepReport[] = [];
  const errors: string[] = [];
  let replanCount = 0;

  // 1. 创建计划上下文
  let context = createPlanContext(sessionId, plan.id);
  savePlan(sessionId, plan);

  // 2. 初始化执行历史
  const executionHistory: ExecutionHistory = {
    planId: plan.id,
    steps: [],
    totalDuration: 0,
    successRate: 1
  };

  // 3. 执行循环
  let currentPlan = plan;
  let status: 'success' | 'partial' | 'failed' = 'success';

  while (!isPlanComplete(currentPlan)) {
    // 获取下一个可执行步骤
    const step = nextStep(currentPlan);

    if (!step) {
      // 没有可执行步骤，检查是否被阻塞
      if (isPlanBlocked(currentPlan)) {
        // 触发重规划
        if (cfg.enableReplan && replanCount < cfg.maxReplans) {
          const { trigger, reason } = shouldReplan(executionHistory);

          if (trigger) {
            // 保存当前状态
            savePlan(sessionId, currentPlan);

            // 执行重规划
            const replanResult = await replanWithLLM(
              currentPlan,
              executionHistory,
              reason,
              undefined // 使用规则重规划
            );

            if (replanResult.newPlan) {
              const validation = validateReplanResult(
                replanResult.newPlan,
                currentPlan,
                new Map()
              );

              if (validation.valid) {
                currentPlan = replanResult.newPlan;
                replanCount++;
                context = createPlanContext(sessionId, currentPlan.id);
                savePlan(sessionId, currentPlan);

                cfg.onReplan?.(currentPlan, replanResult.newPlan, reason);
                continue;
              }
            }
          }
        }

        // 无法恢复，标记失败
        status = 'failed';
        errors.push('计划被阻塞，无法继续执行');
        break;
      }

      // 计划完成
      break;
    }

    // 4. 执行步骤
    cfg.onStepStart?.(step);

    const stepStartTime = Date.now();
    currentPlan = updateStepStatus(currentPlan, step.id, 'running');
    updatePlanContext(sessionId, { activeSteps: [...context.activeSteps, step.id] });

    let result: ExecutionResult;
    let retries = 0;

    // 重试循环
    while (retries <= cfg.maxRetries) {
      try {
        // 执行步骤（带超时）
        result = await executeStepWithTimeout(
          step,
          context,
          constraints,
          cfg.timeoutMs,
          callAgent
        );

        if (result.success) {
          break; // 成功，退出重试
        }

        // 失败，记录并重试
        updateTriggerState('failure');
        retries++;

        if (retries <= cfg.maxRetries) {
          // 等待退避时间
          await sleep(cfg.retryBackoffMs * Math.pow(2, retries - 1));
        }

      } catch (error) {
        result = {
          success: false,
          output: null,
          error: error instanceof Error ? error.message : String(error),
          duration: Date.now() - stepStartTime,
          constraintsChecked: [],
          stepId: step.id
        };
        retries++;

        if (retries <= cfg.maxRetries) {
          await sleep(cfg.retryBackoffMs * Math.pow(2, retries - 1));
        }
      }
    }

    // 5. 更新步骤状态
    const stepStatus = result!.success ? 'completed' : 'failed';
    currentPlan = updateStepStatus(currentPlan, step.id, stepStatus, result!.output);

    // 更新计划上下文
    if (stepStatus === 'completed') {
      updatePlanContext(sessionId, {
        completedSteps: [...context.completedSteps, step.id],
        activeSteps: context.activeSteps.filter(id => id !== step.id)
      });
      updateTriggerState('success');
    } else {
      updatePlanContext(sessionId, {
        failedSteps: [...context.failedSteps, step.id],
        activeSteps: context.activeSteps.filter(id => id !== step.id)
      });
    }

    // 6. 记录步骤报告
    const stepReport: StepReport = {
      stepId: step.id,
      action: step.action,
      agent: step.agent || 'Coder',
      status: stepStatus,
      durationMs: Date.now() - stepStartTime,
      retryCount: retries,
      error: result!.error,
      output: result!.output
    };
    stepReports.push(stepReport);

    // 7. 更新执行历史
    executionHistory.steps.push({
      stepId: step.id,
      agent: step.agent || 'Coder',
      status: stepStatus,
      startedAt: stepStartTime,
      completedAt: Date.now(),
      duration: stepReport.durationMs,
      error: result!.error,
      constraintChecks: result!.constraintsChecked
    });

    cfg.onStepComplete?.(step, result!);

    // 8. 报告进度
    const progress = getPlanProgress(currentPlan);
    cfg.onProgress?.({
      planId: currentPlan.id,
      totalSteps: progress.total,
      completedSteps: progress.completed,
      failedSteps: progress.failed,
      currentStep: step.id,
      percentComplete: progress.percentComplete,
      status: stepStatus === 'failed' ? 'replanning' : 'running',
      startedAt: startTime,
      elapsedMs: Date.now() - startTime
    });

    // 9. 保存计划状态
    savePlan(sessionId, currentPlan);

    // 10. 如果步骤失败，检查是否需要重规划
    if (!result!.success && cfg.enableReplan) {
      const { trigger, reason } = shouldReplan(executionHistory);

      if (trigger && replanCount < cfg.maxReplans) {
        cfg.onProgress?.({
          planId: currentPlan.id,
          totalSteps: progress.total,
          completedSteps: progress.completed,
          failedSteps: progress.failed,
          currentStep: null,
          percentComplete: progress.percentComplete,
          status: 'replanning',
          startedAt: startTime,
          elapsedMs: Date.now() - startTime
        });

        const replanResult = await replanWithLLM(
          currentPlan,
          executionHistory,
          reason,
          undefined
        );

        if (replanResult.newPlan && replanResult.success) {
          currentPlan = replanResult.newPlan;
          replanCount++;
          context = createPlanContext(sessionId, currentPlan.id);
          savePlan(sessionId, currentPlan);

          cfg.onReplan?.(currentPlan, replanResult.newPlan, reason);
        }
      }
    }

    // 11. 检查是否应该停止
    if (stepStatus === 'failed' && !cfg.enableReplan) {
      status = 'failed';
      errors.push(stepReport.error || '步骤执行失败');
      break;
    }
  }

  // 12. 生成最终报告
  const finalProgress = getPlanProgress(currentPlan);
  if (finalProgress.failed > 0 && finalProgress.completed > 0) {
    status = 'partial';
  } else if (finalProgress.failed > 0 && finalProgress.completed === 0) {
    status = 'failed';
  }

  return {
    planId: currentPlan.id,
    sessionId,
    status,
    totalSteps: finalProgress.total,
    completedSteps: finalProgress.completed,
    failedSteps: finalProgress.failed,
    replanCount,
    durationMs: Date.now() - startTime,
    steps: stepReports,
    errors
  };
}

/**
 * 带超时的步骤执行
 */
async function executeStepWithTimeout(
  step: PlanStep,
  context: PlanContext,
  constraints: string[],
  timeoutMs: number,
  callAgent?: (params: AgentCallParams) => Promise<unknown>
): Promise<ExecutionResult> {
  return new Promise(async (resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error(`步骤执行超时 (${timeoutMs}ms)`));
    }, timeoutMs);

    try {
      const result = await executeWithPlanContext(step, context, constraints);
      clearTimeout(timeout);
      resolve(result);
    } catch (error) {
      clearTimeout(timeout);
      reject(error);
    }
  });
}

/**
 * 辅助函数：睡眠
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============ 辅助函数 ============

/**
 * 获取执行进度
 */
export function getExecutionProgress(
  plan: Plan,
  startTime: number
): ExecutionProgress {
  const progress = getPlanProgress(plan);
  const currentStep = nextStep(plan);

  return {
    planId: plan.id,
    totalSteps: progress.total,
    completedSteps: progress.completed,
    failedSteps: progress.failed,
    currentStep: currentStep?.id || null,
    percentComplete: progress.percentComplete,
    status: isPlanComplete(plan) ? 'completed' : isPlanBlocked(plan) ? 'failed' : 'running',
    startedAt: startTime,
    elapsedMs: Date.now() - startTime
  };
}

/**
 * 格式化执行报告
 */
export function formatExecutionReport(report: ExecutionReport): string {
  const lines: string[] = [
    '╔═══════════════════════════════════════════════════════════════╗',
    '║                    执行报告                                   ║',
    '╠═══════════════════════════════════════════════════════════════╣',
    `║  Plan ID: ${report.planId.padEnd(48)}║`,
    `║  Session: ${report.sessionId.padEnd(48)}║`,
    `║  Status:  ${(report.status === 'success' ? '✅ 成功' : report.status === 'partial' ? '⚠️ 部分成功' : '❌ 失败').padEnd(48)}║`,
    '╠═══════════════════════════════════════════════════════════════╣',
    `║  步骤: ${report.completedSteps}/${report.totalSteps} 完成, ${report.failedSteps} 失败`.padEnd(62) + '║',
    `║  重规划: ${report.replanCount} 次`.padEnd(62) + '║',
    `║  耗时: ${(report.durationMs / 1000).toFixed(2)}s`.padEnd(62) + '║',
    '╚═══════════════════════════════════════════════════════════════╝',
    '',
    '步骤详情:',
  ];

  for (const step of report.steps) {
    const icon = step.status === 'completed' ? '✅' : step.status === 'failed' ? '❌' : '⏳';
    lines.push(`  ${icon} [${step.agent}] ${step.action} (${step.durationMs}ms)`);
    if (step.error) {
      lines.push(`     错误: ${step.error.slice(0, 50)}`);
    }
  }

  if (report.errors.length > 0) {
    lines.push('', '错误汇总:');
    for (const error of report.errors) {
      lines.push(`  - ${error}`);
    }
  }

  return lines.join('\n');
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'demo') {
    console.log('\n=== 执行计划演示 ===\n');

    // 创建演示计划
    const demoPlan: Plan = {
      id: `demo-plan-${Date.now()}`,
      goal: '演示计划执行流程',
      steps: [
        { id: 'step-0', action: '分析需求', agent: 'Researcher', dependencies: [], status: 'pending', retryCount: 0, maxRetries: 3 },
        { id: 'step-1', action: '设计方案', agent: 'Architect', dependencies: ['step-0'], status: 'pending', retryCount: 0, maxRetries: 3 },
        { id: 'step-2', action: '实现功能', agent: 'Coder', dependencies: ['step-1'], status: 'pending', retryCount: 0, maxRetries: 3 },
      ],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      currentStepIndex: 0,
      constraints: ['演示模式']
    };

    console.log('计划:', demoPlan.goal);
    console.log('步骤数:', demoPlan.steps.length);

    // 模拟执行（不实际调用 Agent）
    const report = await executePlan(
      demoPlan,
      `demo-session-${Date.now()}`,
      ['演示模式'],
      {
        enableReplan: false,
        onProgress: (p) => console.log(`进度: ${p.percentComplete}%`),
        onStepStart: (s) => console.log(`开始: ${s.action}`),
        onStepComplete: (s, r) => console.log(`完成: ${s.action} (${r.duration}ms)`)
      }
    );

    console.log('\n' + formatExecutionReport(report));

  } else {
    console.log(`
Plan Executor CLI

Usage:
  bun plan-executor.ts demo  - 运行演示
    `);
  }
}

export type { ExecutorConfig, ExecutionProgress, ExecutionReport, StepReport };
