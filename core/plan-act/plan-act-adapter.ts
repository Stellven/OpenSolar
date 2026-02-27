#!/usr/bin/env bun
/**
 * Plan-Act Adapter - Solar Agent 集成适配器
 *
 * 将 Plan-and-Act 集成到现有 Solar Agent 调用流程
 *
 * @module plan-act-adapter
 * @version 1.0.0
 * @created 2026-02-27
 */

import type {
  Plan,
  PlanStep,
  ExecutionResult,
  AgentCallParams,
} from './types';
import { generatePlan, nextStep, updateStepStatus, getPlanProgress } from './plan-dispatcher';
import { createPlanContext, savePlan, loadPlan, loadPlanContext } from './plan-context';
import { executePlan, formatExecutionReport, type ExecutionReport } from './plan-executor';
import { recordMetrics, generateMetricsReport } from './plan-metrics';

// ============ 类型定义 ============

export interface PlanActRequest {
  goal: string;
  constraints?: string[];
  sessionId?: string;
  enableReplan?: boolean;
  onProgress?: (progress: string) => void;
}

export interface PlanActResponse {
  success: boolean;
  planId: string;
  report?: ExecutionReport;
  error?: string;
  summary: string;
}

export interface QuickPlanResult {
  plan: Plan;
  estimatedSteps: number;
  suggestedAgents: string[];
}

// ============ 复杂度检测 ============

/**
 * 复杂任务关键词
 */
const COMPLEX_TASK_PATTERNS = [
  /实现.*功能/,
  /开发.*系统/,
  /设计.*架构/,
  /重构.*模块/,
  /优化.*性能/,
  /集成.*服务/,
  /部署.*环境/,
  /迁移.*数据/,
  /分析.*报告/,
  /研究.*方案/,
];

/**
 * 判断任务是否需要 Plan-and-Act
 *
 * @param task - 任务描述
 * @returns 是否复杂任务
 */
export function isComplexTask(task: string): boolean {
  // 1. 检查关键词
  for (const pattern of COMPLEX_TASK_PATTERNS) {
    if (pattern.test(task)) {
      return true;
    }
  }

  // 2. 检查任务长度（超过 50 字可能是复杂任务）
  if (task.length > 50) {
    return true;
  }

  // 3. 检查是否包含多个子任务
  const subtaskCount = (task.match(/[，,;；\n]/g) || []).length;
  if (subtaskCount >= 2) {
    return true;
  }

  return false;
}

/**
 * 从任务描述中提取约束
 */
export function extractConstraints(task: string): string[] {
  const constraints: string[] = [];

  // 常见约束模式
  const patterns = [
    { regex: /不[引入用].*依赖/g, template: '不引入新依赖' },
    { regex: /保持.*兼容/g, template: '保持向后兼容' },
    { regex: /性能.*[不能不].*[回退降低]/g, template: '性能不能回退' },
    { regex: /不破坏.*接口/g, template: '不破坏现有 API' },
    { regex: /[必须需要].*测试/g, template: '必须编写测试' },
  ];

  for (const { regex, template } of patterns) {
    if (regex.test(task)) {
      constraints.push(template);
    }
  }

  return constraints;
}

// ============ 主要 API ============

/**
 * 快速规划 - 生成计划但不执行
 *
 * 用于预览计划，让用户确认后再执行
 *
 * @param goal - 目标描述
 * @param constraints - 约束条件
 * @returns 规划结果
 */
export async function quickPlan(
  goal: string,
  constraints: string[] = []
): Promise<QuickPlanResult> {
  const plan = await generatePlan(goal, constraints);

  const suggestedAgents = [...new Set(
    plan.steps.map(s => s.agent).filter(Boolean) as string[]
  )];

  return {
    plan,
    estimatedSteps: plan.steps.length,
    suggestedAgents
  };
}

/**
 * 执行 Plan-and-Act 流程
 *
 * 这是主要的入口点，用于执行复杂任务
 *
 * @param request - 请求参数
 * @returns 执行结果
 */
export async function executeWithPlanAct(
  request: PlanActRequest
): Promise<PlanActResponse> {
  const {
    goal,
    constraints = [],
    sessionId = `plan-act-${Date.now()}`,
    enableReplan = true,
    onProgress
  } = request;

  try {
    // 1. 生成计划
    onProgress?.('生成执行计划...');
    const plan = await generatePlan(goal, constraints);

    // 2. 创建上下文
    createPlanContext(sessionId, plan.id);
    savePlan(sessionId, plan);

    // 3. 执行计划
    onProgress?.(`执行计划 (${plan.steps.length} 步)...`);

    const report = await executePlan(
      plan,
      sessionId,
      constraints,
      {
        enableReplan,
        onProgress: (p) => {
          onProgress?.(`进度: ${p.percentComplete}% (${p.completedSteps}/${p.totalSteps})`);
        }
      }
    );

    // 4. 记录指标
    recordMetrics(report);

    // 5. 生成摘要
    const summary = generateSummary(report);

    return {
      success: report.status === 'success',
      planId: plan.id,
      report,
      summary
    };

  } catch (error) {
    return {
      success: false,
      planId: '',
      error: error instanceof Error ? error.message : String(error),
      summary: `执行失败: ${error}`
    };
  }
}

/**
 * 从现有会话恢复计划
 *
 * @param sessionId - 会话 ID
 * @returns 恢复的计划或 null
 */
export async function resumePlan(sessionId: string): Promise<Plan | null> {
  const context = loadPlanContext(sessionId);
  if (!context) return null;

  return loadPlan(sessionId, context.currentPlanId);
}

/**
 * 获取计划进度
 *
 * @param sessionId - 会话 ID
 * @returns 进度信息
 */
export function getPlanStatus(sessionId: string): {
  exists: boolean;
  progress?: {
    total: number;
    completed: number;
    percent: number;
  };
} {
  const context = loadPlanContext(sessionId);
  if (!context) {
    return { exists: false };
  }

  const plan = loadPlan(sessionId, context.currentPlanId);
  if (!plan) {
    return { exists: false };
  }

  const progress = getPlanProgress(plan);

  return {
    exists: true,
    progress: {
      total: progress.total,
      completed: progress.completed,
      percent: progress.percentComplete
    }
  };
}

// ============ 辅助函数 ============

/**
 * 生成执行摘要
 */
function generateSummary(report: ExecutionReport): string {
  const statusIcon = {
    success: '✅',
    partial: '⚠️',
    failed: '❌'
  }[report.status];

  const lines = [
    `${statusIcon} Plan-and-Act 执行完成`,
    `   计划 ID: ${report.planId}`,
    `   状态: ${report.status === 'success' ? '成功' : report.status === 'partial' ? '部分成功' : '失败'}`,
    `   步骤: ${report.completedSteps}/${report.totalSteps} 完成`,
    `   耗时: ${(report.durationMs / 1000).toFixed(2)}s`,
  ];

  if (report.replanCount > 0) {
    lines.push(`   重规划: ${report.replanCount} 次`);
  }

  if (report.errors.length > 0) {
    lines.push(`   错误: ${report.errors.length} 个`);
  }

  return lines.join('\n');
}

/**
 * 格式化计划预览
 */
export function formatPlanPreview(plan: Plan): string {
  const lines = [
    '📋 执行计划预览',
    '─────────────────────────────────────',
    `目标: ${plan.goal}`,
    `步骤数: ${plan.steps.length}`,
    '',
    '步骤:',
  ];

  plan.steps.forEach((step, i) => {
    const deps = step.dependencies.length > 0
      ? ` (依赖: ${step.dependencies.map(d => d.replace('step-', '#')).join(', ')})`
      : '';
    lines.push(`  ${i + 1}. [${step.agent}] ${step.action}${deps}`);
  });

  if (plan.constraints.length > 0) {
    lines.push('', '约束:');
    plan.constraints.forEach(c => lines.push(`  - ${c}`));
  }

  return lines.join('\n');
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'plan') {
    const goal = args.slice(1).join(' ') || '实现用户登录功能';
    console.log(`\n=== 规划: ${goal} ===\n`);

    quickPlan(goal, ['不引入新依赖']).then(result => {
      console.log(formatPlanPreview(result.plan));
      console.log(`\n建议 Agent: ${result.suggestedAgents.join(', ')}`);
    });

  } else if (command === 'execute') {
    const goal = args.slice(1).join(' ') || '测试计划执行';
    console.log(`\n=== 执行: ${goal} ===\n`);

    executeWithPlanAct({
      goal,
      constraints: ['演示模式'],
      onProgress: (p) => console.log(`  ${p}`)
    }).then(result => {
      console.log('\n' + result.summary);
    });

  } else if (command === 'metrics') {
    console.log('\n' + generateMetricsReport(7));

  } else {
    console.log(`
Plan-Act Adapter CLI

Usage:
  bun plan-act-adapter.ts plan <goal>     - 生成计划预览
  bun plan-act-adapter.ts execute <goal>  - 执行计划
  bun plan-act-adapter.ts metrics         - 查看统计报告

Examples:
  bun plan-act-adapter.ts plan "实现用户认证系统"
  bun plan-act-adapter.ts execute "测试任务"
    `);
  }
}

export type { PlanActRequest, PlanActResponse, QuickPlanResult };
