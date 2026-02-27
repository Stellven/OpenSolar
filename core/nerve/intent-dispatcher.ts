#!/usr/bin/env bun
/**
 * Intent Dispatcher - 意图调度器
 *
 * 功能：
 * 1. 接收用户输入
 * 2. 调用 intent-matcher 识别意图
 * 3. 根据意图类型执行相应工具
 *
 * @created 2026-02-27
 */

import { matchIntent, generateComparison } from './intent-matcher';

// ============ 工具执行器 ============

interface ExecutionResult {
  success: boolean;
  tool: string;
  output?: string;
  error?: string;
  needsConfirmation?: boolean;
  mcpCalls?: Array<{
    model: string;
    system: string;
    prompt: string;
  }>;
}

/**
 * 执行 Plan-and-Act
 */
async function executePlanAndAct(
  userInput: string,
  constraints: string[] = []
): Promise<ExecutionResult> {
  // 动态导入 real-executor
  const { executePlanWithMCP } = await import('../plan-act/real-executor');

  try {
    const result = await executePlanWithMCP(userInput, constraints);

    return {
      success: true,
      tool: 'plan_and_act',
      output: `计划已生成，共 ${result.plan.steps.length} 步`,
      needsConfirmation: true,
      mcpCalls: result.pendingCalls.map(call => ({
        model: call.model,
        system: call.system,
        prompt: call.prompt
      }))
    };
  } catch (error) {
    return {
      success: false,
      tool: 'plan_and_act',
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

/**
 * 执行 Researcher 调研
 */
async function executeResearcher(userInput: string): Promise<ExecutionResult> {
  // 这里应该调用 @Researcher Agent
  // 目前返回需要手动触发的提示
  return {
    success: true,
    tool: 'researcher',
    output: `将调用 @Researcher 进行深度调研`,
    needsConfirmation: true
  };
}

/**
 * 执行 Evolution Council 决策
 */
async function executeEvolutionCouncil(userInput: string): Promise<ExecutionResult> {
  // 这里应该调用 Evolution Council
  // 目前返回需要手动触发的提示
  return {
    success: true,
    tool: 'evolution_council',
    output: `将调用 Evolution Council 进行 6 角色会审`,
    needsConfirmation: true
  };
}

// ============ 主调度器 ============

/**
 * 调度用户输入
 *
 * @param userInput - 用户输入
 * @param autoConfirm - 是否自动确认（默认 false，需要用户确认）
 * @returns 执行结果
 */
export async function dispatchIntent(
  userInput: string,
  autoConfirm: boolean = false
): Promise<ExecutionResult> {
  // 1. 匹配意图
  const matchResult = matchIntent(userInput);

  console.log(`\n🎯 意图识别结果:`);
  console.log(`   工具: ${matchResult.tool}`);
  console.log(`   置信度: ${(matchResult.confidence * 100).toFixed(0)}%`);
  console.log(`   描述: ${matchResult.matched_patterns[0]?.description || '未知'}`);

  // 2. 根据意图类型执行
  switch (matchResult.tool) {
    case 'plan_and_act':
      if (!autoConfirm) {
        console.log(`\n${matchResult.suggestion}`);
        return {
          success: true,
          tool: 'plan_and_act',
          output: matchResult.suggestion,
          needsConfirmation: true
        };
      }
      return executePlanAndAct(userInput);

    case 'researcher':
      if (!autoConfirm) {
        console.log(`\n${matchResult.suggestion}`);
        return {
          success: true,
          tool: 'researcher',
          output: matchResult.suggestion,
          needsConfirmation: true
        };
      }
      return executeResearcher(userInput);

    case 'evolution_council':
      if (!autoConfirm) {
        console.log(`\n${matchResult.suggestion}`);
        return {
          success: true,
          tool: 'evolution_council',
          output: matchResult.suggestion,
          needsConfirmation: true
        };
      }
      return executeEvolutionCouncil(userInput);

    case 'both':
      if (!autoConfirm) {
        console.log(`\n${matchResult.suggestion}`);
        return {
          success: true,
          tool: 'both',
          output: matchResult.suggestion,
          needsConfirmation: true
        };
      }
      // 先 Researcher 后 Evolution Council
      const researchResult = await executeResearcher(userInput);
      if (!researchResult.success) return researchResult;
      return executeEvolutionCouncil(userInput);

    case 'uncertain':
    default:
      console.log(`\n${matchResult.suggestion}`);
      return {
        success: false,
        tool: 'uncertain',
        output: matchResult.suggestion,
        error: '无法确定意图'
      };
  }
}

/**
 * 快速执行（跳过确认，直接执行）
 */
export async function quickExecute(userInput: string): Promise<ExecutionResult> {
  return dispatchIntent(userInput, true);
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'dispatch') {
    const userInput = args.slice(1).join(' ');
    if (!userInput) {
      console.error('用法: bun intent-dispatcher.ts dispatch "用户输入"');
      process.exit(1);
    }
    dispatchIntent(userInput);

  } else if (command === 'quick') {
    const userInput = args.slice(1).join(' ');
    if (!userInput) {
      console.error('用法: bun intent-dispatcher.ts quick "用户输入"');
      process.exit(1);
    }
    quickExecute(userInput);

  } else if (command === 'compare') {
    console.log(generateComparison());

  } else {
    console.log(`
Intent Dispatcher - 意图调度器

用法:
  bun intent-dispatcher.ts dispatch "用户输入"  # 识别意图并请求确认
  bun intent-dispatcher.ts quick "用户输入"     # 快速执行（跳过确认）
  bun intent-dispatcher.ts compare              # 查看工具对比

示例:
  bun intent-dispatcher.ts dispatch "实现一个登录功能"
  bun intent-dispatcher.ts quick "重构支付模块"
`);
  }
}

export type { ExecutionResult };
