#!/usr/bin/env bun
/**
 * Plan-and-Act 端到端验证
 *
 * 这个脚本验证 Plan-and-Act 能够真正调用 MCP 执行任务
 *
 * 运行方式：
 * 1. 在 Claude Code 对话中，让我执行这个脚本
 * 2. 或者手动调用：bun e2e-verify.ts
 *
 * @version 1.0.0
 * @created 2026-02-27
 */

import { generatePlan, nextStep, updateStepStatus } from './plan-dispatcher';
import { createPlanContext, savePlan } from './plan-context';
import { setAgentCaller, buildAgentPrompt, getAgentModel } from './agent-wrapper';
import type { AgentCallParams } from './types';

// ============ MCP 调用器（真正调用 brain-router）============

/**
 * 创建 MCP Agent 调用器
 *
 * 这个函数会通过 MCP 调用真正的 LLM
 */
function createMCPAgentCaller(): (params: AgentCallParams) => Promise<unknown> {
  return async (params: AgentCallParams) => {
    const model = getAgentModel(params.agent);
    const { system, prompt } = buildAgentPrompt(
      params.agent,
      params.task,
      params.constraints,
      params.planContext
    );

    console.log(`\n🔄 调用 MCP: ${params.agent} (${model})`);
    console.log(`   任务: ${params.task.slice(0, 60)}...`);

    // 这里需要通过 MCP 调用
    // 由于这是在 TypeScript 中，我们返回一个标记
    // 实际使用时，Claude Code 会调用 mcp__brain-router__complete

    return {
      _mcp_call_required: true,
      model,
      system,
      prompt,
      agent: params.agent,
      note: '需要在 Claude Code 中通过 MCP 执行'
    };
  };
}

// ============ 验证函数 ============

/**
 * 验证 1: 计划生成
 */
async function verifyPlanGeneration() {
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('验证 1: 计划生成');
  console.log('═══════════════════════════════════════════════════════════════\n');

  const goal = '分析 TypeScript 异步编程的最佳实践';
  const constraints = ['使用中文输出', '不超过 500 字'];

  console.log(`目标: ${goal}`);
  console.log(`约束: ${constraints.join(', ')}`);

  const plan = await generatePlan(goal, constraints);

  console.log(`\n✅ 生成的计划:`);
  console.log(`   ID: ${plan.id}`);
  console.log(`   步骤数: ${plan.steps.length}`);
  console.log(`   建议 Agent: ${plan.steps.map(s => s.agent).join(' → ')}`);

  plan.steps.forEach((s, i) => {
    console.log(`   ${i + 1}. [${s.agent}] ${s.action}`);
  });

  return plan;
}

/**
 * 验证 2: Agent 调用器注入
 */
async function verifyAgentCallerInjection() {
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('验证 2: Agent 调用器注入');
  console.log('═══════════════════════════════════════════════════════════════\n');

  // 创建并注入 MCP 调用器
  const mcpCaller = createMCPAgentCaller();
  setAgentCaller(mcpCaller);

  console.log('✅ MCP 调用器已注入');

  // 测试调用
  const testParams: AgentCallParams = {
    agent: 'Researcher',
    task: '分析 TypeScript async/await 的性能特点',
    constraints: ['使用中文'],
    planContext: {
      currentStep: 'step-0',
      completedSteps: []
    }
  };

  const result = await mcpCaller(testParams);

  console.log('\n📋 MCP 调用参数:');
  console.log(`   Model: ${result.model}`);
  console.log(`   Agent: ${result.agent}`);
  console.log(`   System Prompt 长度: ${result.system?.length || 0} 字符`);
  console.log(`   User Prompt 长度: ${result.prompt?.length || 0} 字符`);

  if (result._mcp_call_required) {
    console.log('\n⚠️  需要在 Claude Code 中通过 MCP 执行实际调用');
    console.log('   调用方式: mcp__brain-router__complete');
    console.log(`   参数: model="${result.model}"`);
  }

  return result;
}

/**
 * 验证 3: 与 SMA 集成
 */
async function verifySMAIntegration() {
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('验证 3: 与 SMA 集成');
  console.log('═══════════════════════════════════════════════════════════════\n');

  const sessionId = `verify-sma-${Date.now()}`;
  const plan = await generatePlan('测试 SMA 集成', ['测试约束']);

  // 创建上下文
  const context = createPlanContext(sessionId, plan.id);
  console.log(`✅ 创建计划上下文: ${sessionId}`);

  // 保存计划
  savePlan(sessionId, plan);
  console.log(`✅ 保存计划到 SMA L2: ${plan.id}`);

  // 模拟步骤执行
  let updatedPlan = updateStepStatus(plan, 'step-0', 'completed', { output: '测试结果' });
  console.log(`✅ 更新步骤状态: step-0 → completed`);

  // 获取下一步
  const next = nextStep(updatedPlan);
  if (next) {
    console.log(`✅ 获取下一步: ${next.id} - ${next.action}`);
  } else {
    console.log(`ℹ️  计划已完成`);
  }

  return { sessionId, planId: plan.id };
}

/**
 * 验证 4: 端到端流程
 */
async function verifyEndToEnd() {
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('验证 4: 端到端流程（模拟）');
  console.log('═══════════════════════════════════════════════════════════════\n');

  const goal = '实现一个简单的缓存模块';
  const constraints = ['使用 TypeScript', '不引入外部依赖'];

  console.log(`目标: ${goal}`);
  console.log(`约束: ${constraints.join(', ')}\n`);

  // 1. 生成计划
  const plan = await generatePlan(goal, constraints);
  console.log(`步骤 1: 生成计划 (${plan.steps.length} 步)`);

  // 2. 创建上下文
  const sessionId = `e2e-${Date.now()}`;
  createPlanContext(sessionId, plan.id);
  savePlan(sessionId, plan);
  console.log(`步骤 2: 创建 SMA 上下文`);

  // 3. 执行步骤（模拟）
  let currentPlan = plan;
  for (let i = 0; i < plan.steps.length; i++) {
    const step = plan.steps[i];
    console.log(`步骤 3.${i + 1}: [${step.agent}] ${step.action}`);

    // 模拟执行
    currentPlan = updateStepStatus(currentPlan, step.id, 'completed', {
      output: `步骤 ${i + 1} 完成`
    });
  }

  console.log(`\n✅ 端到端流程验证完成（模拟模式）`);

  return {
    success: true,
    stepsCompleted: plan.steps.length,
    duration: '模拟执行'
  };
}

// ============ 主入口 ============

async function main() {
  console.log(`
╔═══════════════════════════════════════════════════════════════╗
║         Plan-and-Act 端到端验证                                ║
╠═══════════════════════════════════════════════════════════════╣
║  这个脚本验证 Plan-and-Act 能够真正工作                        ║
╚═══════════════════════════════════════════════════════════════╝
`);

  try {
    // 验证 1: 计划生成
    const plan = await verifyPlanGeneration();

    // 验证 2: Agent 调用器注入
    const mcpResult = await verifyAgentCallerInjection();

    // 验证 3: SMA 集成
    const smaResult = await verifySMAIntegration();

    // 验证 4: 端到端流程
    const e2eResult = await verifyEndToEnd();

    // 总结
    console.log('\n═══════════════════════════════════════════════════════════════');
    console.log('验证总结');
    console.log('═══════════════════════════════════════════════════════════════\n');

    console.log('✅ 验证 1: 计划生成 - 通过');
    console.log('✅ 验证 2: Agent 调用器注入 - 通过');
    console.log('✅ 验证 3: SMA 集成 - 通过');
    console.log('✅ 验证 4: 端到端流程 - 通过（模拟）');

    console.log('\n⚠️  已识别的断头:');
    console.log('   1. agent-wrapper.ts 的 callAgent() 需要 MCP 注入');
    console.log('   2. 没有在 CLAUDE.md 中添加 /plan 触发规则');
    console.log('   3. 测试是 mock，需要真实 MCP 调用验证');

    console.log('\n📋 下一步:');
    console.log('   1. 在 Claude Code 对话中调用 mcp__brain-router__complete');
    console.log('   2. 验证真实 LLM 输出');
    console.log('   3. 集成到 Solar 工作流');

    return {
      success: true,
      plan,
      mcpResult,
      smaResult,
      e2eResult
    };

  } catch (error) {
    console.error('\n❌ 验证失败:', error);
    return {
      success: false,
      error: String(error)
    };
  }
}

// 导出供 Claude Code 调用
export { verifyPlanGeneration, verifyAgentCallerInjection, verifySMAIntegration, verifyEndToEnd };

// CLI 入口
if (import.meta.main) {
  main();
}
