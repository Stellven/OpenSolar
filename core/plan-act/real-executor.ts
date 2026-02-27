#!/usr/bin/env bun
/**
 * Plan-and-Act 真实执行器
 *
 * 这个文件展示如何真正使用 Plan-and-Act
 * 必须在 Claude Code 对话中执行，通过 MCP 调用 LLM
 *
 * @version 1.0.0
 * @created 2026-02-27
 */

import {
  generatePlan,
  nextStep,
  updateStepStatus,
  getPlanProgress
} from './plan-dispatcher';
import {
  createPlanContext,
  savePlan,
  loadPlanContext
} from './plan-context';
import {
  setAgentCaller,
  getAgentModel,
  buildAgentPrompt,
  type AgentCaller
} from './agent-wrapper';
import {
  recordMetrics,
  initMetricsTable
} from './plan-metrics';
import {
  logExecution,
  initExecutionLogger
} from './execution-logger';
import type { Plan, AgentCallParams, ExecutionResult } from './types';

// ============ 真实 MCP 调用结果存储 ============

interface MCPCallResult {
  stepId: string;
  agent: string;
  model: string;
  system: string;
  prompt: string;
  output?: string;
  success: boolean;
}

// 存储需要执行的 MCP 调用
const pendingMCPCalls: MCPCallResult[] = [];

// 存储已完成的 MCP 调用结果
const completedMCPCalls: Map<string, string> = new Map();

// ============ 真实 Agent 调用器 ============

/**
 * 创建真实的 Agent 调用器
 *
 * 这个调用器会：
 * 1. 记录需要执行的 MCP 调用
 * 2. 等待 Claude Code 通过 MCP 执行
 * 3. 返回执行结果
 */
function createRealAgentCaller(): AgentCaller {
  return async (params: AgentCallParams): Promise<unknown> => {
    const model = getAgentModel(params.agent);
    const { system, prompt } = buildAgentPrompt(
      params.agent,
      params.task,
      params.constraints,
      params.planContext
    );

    const stepId = params.planContext.currentStep;

    // 检查是否已有结果（从 Claude Code 注入）
    const existingResult = completedMCPCalls.get(stepId);
    if (existingResult) {
      console.log(`[RealAgentCaller] 使用缓存结果: ${stepId}`);
      return {
        success: true,
        output: existingResult,
        constraintsChecked: params.constraints.map(c => ({
          constraint: c,
          passed: true
        }))
      };
    }

    // 记录待执行的调用
    const mcpCall: MCPCallResult = {
      stepId,
      agent: params.agent,
      model,
      system,
      prompt,
      success: false
    };

    pendingMCPCalls.push(mcpCall);

    console.log(`\n🔄 需要执行 MCP 调用:`);
    console.log(`   Step: ${stepId}`);
    console.log(`   Agent: ${params.agent} (${model})`);
    console.log(`   Task: ${params.task.slice(0, 60)}...`);

    // 返回待执行状态
    return {
      _pending_mcp: true,
      stepId,
      agent: params.agent,
      model,
      system,
      prompt,
      task: params.task
    };
  };
}

// ============ 执行流程 ============

/**
 * 执行计划（返回需要执行的 MCP 调用列表）
 */
export async function executePlanWithMCP(
  goal: string,
  constraints: string[] = [],
  sessionId?: string
): Promise<{
  plan: Plan;
  pendingCalls: MCPCallResult[];
  sessionId: string;
}> {
  // 初始化
  initMetricsTable();
  initExecutionLogger();

  // 注入真实调用器
  setAgentCaller(createRealAgentCaller());

  // 生成计划
  const plan = await generatePlan(goal, constraints);
  const actualSessionId = sessionId || `plan-act-${Date.now()}`;

  // 创建上下文
  createPlanContext(actualSessionId, plan.id);
  savePlan(actualSessionId, plan);

  // 执行每个步骤，收集 MCP 调用
  let currentPlan = plan;

  for (const step of plan.steps) {
    if (step.status !== 'pending') continue;

    // 检查依赖
    const depsOk = step.dependencies.every(depId => {
      const dep = currentPlan.steps.find(s => s.id === depId);
      return dep && dep.status === 'completed';
    });

    if (!depsOk) {
      console.log(`⏸️  跳过 ${step.id}：依赖未满足`);
      continue;
    }

    // 执行步骤（会记录 MCP 调用）
    const params: AgentCallParams = {
      agent: step.agent || 'Coder',
      task: step.action,
      constraints,
      planContext: {
        currentStep: step.id,
        completedSteps: currentPlan.steps
          .filter(s => s.status === 'completed')
          .map(s => s.id)
      }
    };

    // 这里会触发 MCP 调用记录
    const caller = createRealAgentCaller();
    await caller(params);

    // 暂停执行，等待 MCP 结果
    // 实际使用时，Claude Code 会在对话中执行 MCP 调用
  }

  return {
    plan: currentPlan,
    pendingCalls: [...pendingMCPCalls],
    sessionId: actualSessionId
  };
}

/**
 * 注入 MCP 调用结果
 *
 * 在 Claude Code 完成 MCP 调用后，调用这个函数注入结果
 */
export function injectMCPResult(stepId: string, output: string): void {
  completedMCPCalls.set(stepId, output);
  console.log(`✅ 注入 MCP 结果: ${stepId}`);
}

/**
 * 继续执行计划（使用注入的结果）
 */
export async function continueWithResults(
  plan: Plan,
  sessionId: string
): Promise<Plan> {
  let currentPlan = plan;

  for (const step of plan.steps) {
    if (step.status !== 'pending') continue;

    const result = completedMCPCalls.get(step.id);
    if (!result) {
      console.log(`⏸️  ${step.id}: 等待 MCP 结果`);
      continue;
    }

    // 更新步骤状态
    currentPlan = updateStepStatus(currentPlan, step.id, 'completed', {
      output: result
    });

    console.log(`✅ ${step.id}: 完成`);
  }

  // 保存更新后的计划
  savePlan(sessionId, currentPlan);

  return currentPlan;
}

/**
 * 获取待执行的 MCP 调用
 */
export function getPendingMCPCalls(): MCPCallResult[] {
  return [...pendingMCPCalls];
}

/**
 * 清空待执行列表
 */
export function clearPendingCalls(): void {
  pendingMCPCalls.length = 0;
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'demo') {
    console.log(`
╔═══════════════════════════════════════════════════════════════╗
║         Plan-and-Act 真实执行演示                              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                                 ║
║  这个脚本展示如何在 Claude Code 对话中使用 Plan-and-Act        ║
║                                                                 ║
║  步骤:                                                          ║
║  1. 执行 executePlanWithMCP() 获取待执行调用                    ║
║  2. Claude Code 调用 MCP 执行每个调用                           ║
║  3. 调用 injectMCPResult() 注入结果                             ║
║  4. 调用 continueWithResults() 继续执行                         ║
║                                                                 ║
╚═══════════════════════════════════════════════════════════════╝

示例代码：

// 1. 开始执行
const { plan, pendingCalls, sessionId } = await executePlanWithMCP(
  '实现用户登录功能',
  ['不引入新依赖', '保持向后兼容']
);

// 2. Claude Code 会看到 pendingCalls，然后调用 MCP
// 例如：mcp__brain-router__complete({
//   model: pendingCalls[0].model,
//   system: pendingCalls[0].system,
//   prompt: pendingCalls[0].prompt
// })

// 3. 注入结果
injectMCPResult('step-0', 'MCP 返回的真实输出');

// 4. 继续执行
const finalPlan = await continueWithResults(plan, sessionId);
`);
  } else {
    console.log(`
Plan-and-Act 真实执行器

Usage:
  bun real-executor.ts demo  - 查看使用说明
`);
  }
}

export type { MCPCallResult };
