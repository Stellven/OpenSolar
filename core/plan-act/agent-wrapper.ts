#!/usr/bin/env bun
/**
 * Agent Wrapper - Agent 包装器
 *
 * 功能：
 * 1. 注入约束到 Agent prompt
 * 2. 调用 Agent 执行任务
 * 3. 验证输出包含约束检查
 * 4. 记录执行结果
 *
 * @module agent-wrapper
 * @version 1.0.0
 * @created 2026-02-27
 */

import type {
  ExecutionResult,
  ConstraintCheckResult,
  AgentCallParams,
  PlanContext,
  PlanStep,
} from './types';

// ============ Agent 模型映射 ============

/**
 * Agent 到模型的映射
 */
const AGENT_MODEL_MAP: Record<string, string> = {
  Researcher: 'deepseek-r1',
  Architect: 'gemini-2.5-pro',
  Coder: 'glm-5',
  Tester: 'glm-5',
  Ops: 'glm-5',
  Reviewer: 'gemini-2.5-pro',
  Docs: 'glm-5',
  PM: 'gemini-2.5-pro',
  Guard: 'gemini-2.5-pro',
  Secretary: 'glm-4-flash',
};

/**
 * Agent D&D 人格映射
 */
const AGENT_PERSONALITY_MAP: Record<string, { role: string; knobs: string }> = {
  Researcher: {
    role: 'verifier',
    knobs: 'rigor=5, skepticism=4, explore=4, decide=2, risk=2'
  },
  Architect: {
    role: 'architect',
    knobs: 'rigor=4, skepticism=3, explore=4, decide=4, risk=3'
  },
  Coder: {
    role: 'builder',
    knobs: 'rigor=3, skepticism=2, explore=3, decide=3, risk=2'
  },
  Tester: {
    role: 'verifier',
    knobs: 'rigor=5, skepticism=4, explore=2, decide=3, risk=2'
  },
  Ops: {
    role: 'builder',
    knobs: 'rigor=4, skepticism=3, explore=2, decide=4, risk=4'
  },
  Reviewer: {
    role: 'judge',
    knobs: 'rigor=5, skepticism=5, explore=1, decide=3, risk=5'
  },
  Docs: {
    role: 'builder',
    knobs: 'rigor=3, skepticism=2, explore=2, decide=3, risk=2'
  },
  PM: {
    role: 'architect',
    knobs: 'rigor=4, skepticism=3, explore=4, decide=5, risk=3'
  },
  Guard: {
    role: 'verifier',
    knobs: 'rigor=5, skepticism=4, explore=1, decide=4, risk=5'
  },
  Secretary: {
    role: 'builder',
    knobs: 'rigor=3, skepticism=2, explore=2, decide=3, risk=2'
  },
};

// ============ 核心函数 ============

/**
 * 构建 Agent 调用提示
 *
 * @param agent - Agent 名称
 * @param task - 任务描述
 * @param constraints - 约束条件
 * @param planContext - 计划上下文
 * @returns system 和 prompt
 */
export function buildAgentPrompt(
  agent: string,
  task: string,
  constraints: string[],
  planContext: { currentStep: string; completedSteps: string[] }
): { system: string; prompt: string } {
  const personality = AGENT_PERSONALITY_MAP[agent] || {
    role: 'builder',
    knobs: 'rigor=3, skepticism=2, explore=3, decide=3, risk=2'
  };

  const system = `你是 ${agent}，D&D 角色是 ${personality.role}。

KNOBS: ${personality.knobs}, tool=4, compression=3, check=4, empathy=2, compete=2
LEVEL=4

**约束条件（必须严格遵守）**：
${constraints.length > 0 ? constraints.map(c => `- ${c}`).join('\n') : '（无特定约束）'}

**计划上下文**：
- 当前步骤: ${planContext.currentStep}
- 已完成步骤: ${planContext.completedSteps.length} 个

**输出要求**：
在你的回复末尾，必须包含 "约束检查" 部分，格式如下：
\`\`\`
约束检查：
✓ [约束1] - 通过 [如何遵守的]
✓ [约束2] - 通过 [如何遵守的]
\`\`\``;

  const prompt = `**任务**: ${task}

请执行上述任务，并在输出末尾包含约束检查部分。`;

  return { system, prompt };
}

/**
 * 验证约束检查
 *
 * @param output - Agent 输出
 * @param constraints - 约束条件
 * @returns 约束检查结果数组
 */
export function validateConstraintChecks(
  output: string,
  constraints: string[]
): ConstraintCheckResult[] {
  const results: ConstraintCheckResult[] = [];

  // 查找约束检查部分
  const constraintCheckMatch = output.match(/约束检查[：:]\s*([\s\S]*?)(?=\n\n|\n```|$)/);

  if (!constraintCheckMatch) {
    // 没有找到约束检查部分，标记所有约束为未检查
    return constraints.map(c => ({
      constraint: c,
      passed: false,
      reason: '输出中未找到约束检查部分'
    }));
  }

  const checkSection = constraintCheckMatch[1];

  for (const constraint of constraints) {
    // 检查是否提到了这个约束
    const constraintKeywords = constraint.split(/\s+/).filter(w => w.length > 2);
    const mentioned = constraintKeywords.some(kw =>
      checkSection.toLowerCase().includes(kw.toLowerCase())
    );

    if (mentioned) {
      // 检查是否标记为通过
      const passed = /✓|通过|pass/i.test(checkSection);
      results.push({
        constraint,
        passed,
        reason: passed ? '约束检查通过' : '约束检查未通过'
      });
    } else {
      results.push({
        constraint,
        passed: false,
        reason: '约束未被检查'
      });
    }
  }

  return results;
}

/**
 * 调用 Agent（模拟 - 实际需要 MCP）
 *
 * 注意：这是一个桩实现，实际使用时需要调用 brain-router MCP
 *
 * @param params - Agent 调用参数
 * @returns Agent 输出
 */
export async function callAgent(params: AgentCallParams): Promise<unknown> {
  const model = AGENT_MODEL_MAP[params.agent] || 'glm-5';
  const { system, prompt } = buildAgentPrompt(
    params.agent,
    params.task,
    params.constraints,
    params.planContext
  );

  // 这里应该调用 mcp__brain-router__complete
  // 但由于这是 TypeScript 文件，我们返回一个模拟结果
  // 实际使用时，这个函数会被注入 MCP 调用能力

  console.log(`[AgentWrapper] Calling ${params.agent} with model ${model}`);
  console.log(`[AgentWrapper] Task: ${params.task.slice(0, 50)}...`);

  // 模拟调用结果
  return {
    model,
    agent: params.agent,
    output: `[${params.agent}] 执行完成: ${params.task}`,
    note: '这是模拟输出，实际使用时需要调用 MCP'
  };
}

/**
 * 带计划上下文执行 Agent
 *
 * @param step - 要执行的步骤
 * @param context - 计划上下文
 * @param constraints - 约束条件
 * @returns 执行结果
 */
export async function executeWithPlanContext(
  step: PlanStep,
  context: PlanContext,
  constraints: string[] = []
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const stepId = step.id;

  try {
    // 1. 构建调用参数
    const params: AgentCallParams = {
      agent: step.agent || 'Coder',
      task: step.action,
      constraints,
      planContext: {
        currentStep: stepId,
        completedSteps: context.completedSteps
      }
    };

    // 2. 调用 Agent
    const output = await callAgent(params);

    // 3. 验证约束检查
    const outputStr = typeof output === 'string' ? output : JSON.stringify(output);
    const constraintChecks = validateConstraintChecks(outputStr, constraints);

    // 4. 检查是否有约束违反
    const hasViolation = constraintChecks.some(c => !c.passed);

    const duration = Date.now() - startTime;

    return {
      success: !hasViolation,
      output,
      duration,
      constraintsChecked: constraintChecks,
      stepId
    };

  } catch (error) {
    const duration = Date.now() - startTime;

    return {
      success: false,
      output: null,
      error: error instanceof Error ? error.message : String(error),
      duration,
      constraintsChecked: [],
      stepId
    };
  }
}

/**
 * 批量执行步骤
 *
 * @param steps - 步骤列表
 * @param context - 计划上下文
 * @param constraints - 约束条件
 * @returns 执行结果数组
 */
export async function executeSteps(
  steps: PlanStep[],
  context: PlanContext,
  constraints: string[] = []
): Promise<ExecutionResult[]> {
  const results: ExecutionResult[] = [];

  for (const step of steps) {
    if (step.status !== 'pending') continue;

    const result = await executeWithPlanContext(step, context, constraints);
    results.push(result);

    // 如果失败，停止后续执行
    if (!result.success) {
      console.log(`[AgentWrapper] Step ${step.id} failed, stopping execution`);
      break;
    }
  }

  return results;
}

// ============ 辅助函数 ============

/**
 * 获取 Agent 推荐模型
 */
export function getAgentModel(agent: string): string {
  return AGENT_MODEL_MAP[agent] || 'glm-5';
}

/**
 * 获取 Agent 人格配置
 */
export function getAgentPersonality(agent: string): { role: string; knobs: string } {
  return AGENT_PERSONALITY_MAP[agent] || {
    role: 'builder',
    knobs: 'rigor=3, skepticism=2, explore=3, decide=3, risk=2'
  };
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'test') {
    console.log('\n=== 测试 Agent Wrapper ===\n');

    const testStep: PlanStep = {
      id: 'step-0',
      action: '实现用户登录功能',
      agent: 'Coder',
      dependencies: [],
      status: 'pending',
      retryCount: 0,
      maxRetries: 3
    };

    const testContext: PlanContext = {
      currentPlanId: 'test-plan',
      activeSteps: ['step-0'],
      completedSteps: [],
      failedSteps: [],
      replanCount: 0,
      sessionId: 'test-session',
      updatedAt: Date.now()
    };

    const constraints = ['不引入新依赖', '保持向后兼容'];

    // 测试构建提示
    const { system, prompt } = buildAgentPrompt('Coder', testStep.action, constraints, {
      currentStep: testStep.id,
      completedSteps: []
    });

    console.log('=== System Prompt ===');
    console.log(system);
    console.log('\n=== User Prompt ===');
    console.log(prompt);

    // 测试约束验证
    const testOutput = `
实现了用户登录功能...

约束检查：
✓ 不引入新依赖 - 通过 使用了项目已有的 jsonwebtoken 库
✓ 保持向后兼容 - 通过 保留了原有的 session 认证方式
`;

    console.log('\n=== 约束验证结果 ===');
    const checks = validateConstraintChecks(testOutput, constraints);
    checks.forEach(c => {
      console.log(`${c.passed ? '✓' : '✗'} ${c.constraint}: ${c.reason}`);
    });

  } else if (command === 'agents') {
    console.log('\n=== Agent 模型映射 ===\n');
    Object.entries(AGENT_MODEL_MAP).forEach(([agent, model]) => {
      const personality = AGENT_PERSONALITY_MAP[agent];
      console.log(`${agent.padEnd(12)} → ${model.padEnd(20)} (${personality?.role || '?'})`);
    });

  } else {
    console.log(`
Agent Wrapper CLI

Usage:
  bun agent-wrapper.ts test    - 测试包装器功能
  bun agent-wrapper.ts agents  - 显示 Agent 模型映射
    `);
  }
}

export type { ExecutionResult, ConstraintCheckResult, AgentCallParams };
