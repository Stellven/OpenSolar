#!/usr/bin/env bun
/**
 * Intent Dispatcher - 意图调度器 v2.0
 *
 * 功能：
 * 1. 从 Skill Registry 获取技能信息
 * 2. 根据触发词匹配最佳技能
 * 3. 根据 delegationMode 执行相应逻辑
 *
 * @version 2.0.0
 * @created 2026-02-27
 */

import { matchIntent, generateComparison } from './intent-matcher';
import {
  skillRegistry,
  initSkillRegistry,
  type SkillDefinition,
  type DelegationMode
} from './skill-registry';
import { buildDAG, renderASCII, renderCompact, type DAGGraph } from '../plan-act/dag-visualizer';
import type { Plan } from '../plan-act/types';

// ============ 类型定义 ============

export interface ExecutionResult {
  success: boolean;
  skill?: SkillDefinition;        // 匹配到的技能
  tool: string;
  output?: string;
  error?: string;
  needsConfirmation?: boolean;
  mcpCalls?: Array<{
    stepId: string;
    model: string;
    system: string;
    prompt: string;
  }>;
  dag?: DAGGraph;                 // DAG 图（Plan-and-Act 时返回）
  plan?: Plan;                    // Plan 对象
}

// ============ 执行器映射 ============

interface ExecutorConfig {
  execute: (skill: SkillDefinition, userInput: string, constraints?: string[]) => Promise<ExecutionResult>;
  description: string;
}

const EXECUTORS: Record<DelegationMode, ExecutorConfig> = {
  /**
   * MCP 模式：调用 brain-router 执行
   */
  mcp: {
    description: '通过 MCP 调用 LLM',
    execute: async (skill, userInput) => {
      const models = skill.defaultModels || ['glm-5'];

      return {
        success: true,
        skill,
        tool: skill.id,
        output: `将调用 ${models.join(' + ')} 执行 ${skill.name}`,
        needsConfirmation: true,
        mcpCalls: models.map((model, i) => ({
          stepId: `step-${i}`,
          model,
          system: `你是 ${skill.name}，负责 ${skill.description}`,
          prompt: userInput
        }))
      };
    }
  },

  /**
   * Skill 模式：委派给其他 Skill
   */
  skill: {
    description: '委派给其他 Skill',
    execute: async (skill, userInput) => {
      const targetSkill = skill.mappedSkill || '/unknown';

      return {
        success: true,
        skill,
        tool: skill.id,
        output: `将执行 ${targetSkill}`,
        needsConfirmation: true
      };
    }
  },

  /**
   * Legacy 模式：角色扮演
   */
  legacy: {
    description: '角色扮演模式',
    execute: async (skill, userInput) => {
      return {
        success: true,
        skill,
        tool: skill.id,
        output: `将激活 @${skill.name} 进行处理`,
        needsConfirmation: true
      };
    }
  },

  /**
   * Internal 模式：内部实现
   */
  internal: {
    description: '内部实现',
    execute: async (skill, userInput, constraints = []) => {
      // Plan-and-Act 特殊处理
      if (skill.id === 'intent.plan_and_act') {
        try {
          const { executePlanWithMCP } = await import('../plan-act/real-executor');
          const result = await executePlanWithMCP(userInput, constraints);

          // 构建 DAG
          const dag = buildDAG(result.plan);

          // 显示 ASCII DAG
          console.log(renderCompact(dag));

          return {
            success: true,
            skill,
            tool: skill.id,
            output: `计划已生成，共 ${result.plan.steps.length} 步`,
            needsConfirmation: true,
            mcpCalls: result.pendingCalls.map(call => ({
              stepId: call.stepId,
              model: call.model,
              system: call.system,
              prompt: call.prompt
            })),
            dag,
            plan: result.plan
          };
        } catch (error) {
          return {
            success: false,
            skill,
            tool: skill.id,
            error: error instanceof Error ? error.message : String(error)
          };
        }
      }

      // 其他 internal 技能
      return {
        success: true,
        skill,
        tool: skill.id,
        output: `将使用 ${skill.name} 处理`,
        needsConfirmation: true
      };
    }
  }
};

// ============ 核心调度器 ============

let registryInitialized = false;

/**
 * 调度用户输入
 *
 * @param userInput - 用户输入
 * @param autoConfirm - 是否自动确认（默认 false）
 * @returns 执行结果
 */
export async function dispatchIntent(
  userInput: string,
  autoConfirm: boolean = false
): Promise<ExecutionResult> {
  // 1. 初始化注册表
  if (!registryInitialized) {
    initSkillRegistry();
    registryInitialized = true;
  }

  // 2. 从注册表搜索匹配技能
  const matchedSkills = skillRegistry.findByTrigger(userInput);

  // 3. 也用 intent-matcher 做交叉验证
  const matchResult = matchIntent(userInput);

  console.log(`\n🎯 意图识别结果:`);
  console.log(`   注册表匹配: ${matchedSkills.length} 个技能`);
  console.log(`   意图匹配: ${matchResult.tool} (${(matchResult.confidence * 100).toFixed(0)}%)`);

  // 4. 取最高优先级技能
  const topSkill = matchedSkills[0];

  if (!topSkill) {
    // 没有匹配到技能，使用 intent-matcher 结果
    console.log(`\n${matchResult.suggestion}`);
    return {
      success: false,
      tool: matchResult.tool,
      output: matchResult.suggestion,
      error: '无法确定意图'
    };
  }

  console.log(`   最佳匹配: ${topSkill.id} (优先级 ${topSkill.metadata.priority})`);
  console.log(`   描述: ${topSkill.description}`);
  console.log(`   执行模式: ${topSkill.delegationMode}`);

  // 5. 需要确认
  if (!autoConfirm) {
    console.log(`\n✅ 推荐使用: ${topSkill.name}`);
    console.log(`   分类: ${topSkill.metadata.category}`);
    console.log(`   触发词: ${topSkill.triggers.slice(0, 3).join(', ')}...`);
    if (topSkill.defaultModels) {
      console.log(`   模型: ${topSkill.defaultModels.join(', ')}`);
    }

    return {
      success: true,
      skill: topSkill,
      tool: topSkill.id,
      output: `推荐: ${topSkill.name}`,
      needsConfirmation: true
    };
  }

  // 6. 执行
  const executor = EXECUTORS[topSkill.delegationMode];
  return executor.execute(topSkill, userInput);
}

/**
 * 快速执行（跳过确认）
 */
export async function quickExecute(userInput: string): Promise<ExecutionResult> {
  return dispatchIntent(userInput, true);
}

/**
 * 获取所有可用技能
 */
export function listAvailableSkills(): SkillDefinition[] {
  if (!registryInitialized) {
    initSkillRegistry();
    registryInitialized = true;
  }
  return skillRegistry.list();
}

/**
 * 按分类获取技能
 */
export function getSkillsByCategory(category: string): SkillDefinition[] {
  if (!registryInitialized) {
    initSkillRegistry();
    registryInitialized = true;
  }
  return skillRegistry.findByCategory(category);
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

  } else if (command === 'list') {
    const skills = listAvailableSkills();
    console.log(`\n📋 可用技能 (${skills.length} 个):\n`);

    const byCategory: Record<string, SkillDefinition[]> = {};
    for (const skill of skills) {
      const cat = skill.metadata.category;
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(skill);
    }

    for (const [cat, catSkills] of Object.entries(byCategory)) {
      console.log(`\n[${cat.toUpperCase()}]`);
      for (const skill of catSkills) {
        console.log(`  ${skill.id.padEnd(25)} ${skill.name}`);
      }
    }

  } else if (command === 'compare') {
    console.log(generateComparison());

  } else {
    console.log(`
Intent Dispatcher v2.0 - 意图调度器

用法:
  bun intent-dispatcher.ts dispatch "用户输入"  # 识别并推荐
  bun intent-dispatcher.ts quick "用户输入"     # 快速执行
  bun intent-dispatcher.ts list                 # 列出所有技能
  bun intent-dispatcher.ts compare              # 工具对比

示例:
  bun intent-dispatcher.ts dispatch "实现一个登录功能"
  bun intent-dispatcher.ts quick "重构支付模块"
  bun intent-dispatcher.ts list
`);
  }
}

export type { SkillDefinition };
