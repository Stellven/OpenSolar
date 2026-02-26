#!/usr/bin/env bun
/**
 * Agent Executor - MCP Delegation 自动化执行引擎
 *
 * 功能：
 * 1. 读取 agent YAML 定义
 * 2. 解析 delegation_mode, mcp_tool, default_models
 * 3. 为每个模型注入 D&D KNOBS 人格参数
 * 4. 并行调用多个专家
 * 5. 综合输出并验收
 *
 * Usage:
 *   import { executeAgent } from './agent-executor';
 *   const result = await executeAgent('Reporter', 'Write chapter 1');
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { buildNiumaCall } from '../solar-farm/call-niuma';
import { BrainRouterClient } from '../solar-farm/insight-agent-v2';

// ============================================================================
// Type Definitions
// ============================================================================

interface AgentYAML {
  name: string;
  description: string;
  delegation_mode: 'mcp' | 'legacy';
  mcp_tool?: string;
  default_models?: string[];
  tools?: string;
  ontology?: string;
}

interface ExpertOutput {
  model: string;
  role: string;
  content: string;
  personalityInjected: boolean;
  emotionPromptApplied: boolean;
  timestamp: number;
}

interface AgentExecutionResult {
  success: boolean;
  agentName: string;
  experts: ExpertOutput[];
  synthesis: string;
  validation: {
    passed: boolean;
    issues: string[];
  };
  metrics: {
    totalTime: number;
    expertCount: number;
    tokensUsed?: number;
  };
}

// ============================================================================
// Agent Definition Parser
// ============================================================================

/**
 * 读取并解析 agent YAML 定义
 */
function parseAgentDefinition(agentName: string): AgentYAML {
  const agentPath = join(homedir(), '.claude', 'agents', `${agentName.toLowerCase()}.md`);

  try {
    const content = readFileSync(agentPath, 'utf-8');

    // 提取 YAML frontmatter (--- ... ---)
    const yamlMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (!yamlMatch) {
      throw new Error(`No YAML frontmatter found in ${agentPath}`);
    }

    const yamlText = yamlMatch[1];
    const config: Partial<AgentYAML> = {};

    // 解析关键字段
    const lines = yamlText.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line.startsWith('name:')) {
        config.name = line.replace('name:', '').trim();
      } else if (line.startsWith('description:')) {
        config.description = line.replace('description:', '').trim();
      } else if (line.startsWith('delegation_mode:')) {
        config.delegation_mode = line.replace('delegation_mode:', '').trim() as 'mcp' | 'legacy';
      } else if (line.startsWith('mcp_tool:')) {
        config.mcp_tool = line.replace('mcp_tool:', '').trim();
      } else if (line.startsWith('default_models:')) {
        // 解析数组
        config.default_models = [];
        i++; // 跳到下一行
        while (i < lines.length && lines[i].startsWith('  -')) {
          const model = lines[i].replace(/^\s*-\s*/, '').split('#')[0].trim();
          config.default_models.push(model);
          i++;
        }
        i--; // 回退一行（for 循环会再 i++）
      } else if (line.startsWith('tools:')) {
        config.tools = line.replace('tools:', '').trim();
      } else if (line.startsWith('ontology:')) {
        config.ontology = line.replace('ontology:', '').trim();
      }
    }

    // 验证必需字段
    if (!config.name || !config.delegation_mode) {
      throw new Error(`Missing required fields in ${agentPath}`);
    }

    if (config.delegation_mode === 'mcp' && (!config.mcp_tool || !config.default_models || config.default_models.length === 0)) {
      throw new Error(`MCP delegation mode requires mcp_tool and default_models in ${agentPath}`);
    }

    return config as AgentYAML;
  } catch (error) {
    throw new Error(`Failed to parse agent definition: ${error instanceof Error ? error.message : String(error)}`);
  }
}

// ============================================================================
// Expert Execution
// ============================================================================

/**
 * 调用单个专家（牛马）
 */
async function callExpert(model: string, task: string, context?: string): Promise<ExpertOutput> {
  const startTime = Date.now();

  // 使用 buildNiumaCall 注入人格
  const { system, prompt, personalityInjected, emotionPromptApplied, ddRole } = buildNiumaCall({
    model,
    task,
    context,
    outputFormat: 'Markdown 格式，结构清晰'
  });

  // 实际调用 brain-router MCP
  console.log(`[Agent Executor] Calling ${model} (role: ${ddRole})`);
  console.log(`[Agent Executor] Personality injected: ${personalityInjected}, Emotion prompt: ${emotionPromptApplied}`);

  try {
    // 调用 brain-router HTTP API
    const result = await BrainRouterClient.call({
      model,
      system,
      prompt
    });

    const content = result || `[No response from ${model}]`;

    return {
      model,
      role: ddRole || 'unknown',
      content,
      personalityInjected,
      emotionPromptApplied,
      timestamp: Date.now() - startTime
    };
  } catch (error) {
    console.error(`[Agent Executor] Error calling ${model}:`, error);

    // 返回错误信息
    const content = `[Error from ${model}]: ${error instanceof Error ? error.message : String(error)}`;

    return {
      model,
      role: ddRole || 'unknown',
      content,
      personalityInjected,
      emotionPromptApplied,
      timestamp: Date.now() - startTime
    };
  }
}

/**
 * 并行调用多个专家
 */
async function callExperts(models: string[], task: string, context?: string): Promise<ExpertOutput[]> {
  console.log(`[Agent Executor] Calling ${models.length} experts in parallel...`);

  const promises = models.map(model => callExpert(model, task, context));
  const results = await Promise.all(promises);

  console.log(`[Agent Executor] All experts completed`);
  return results;
}

// ============================================================================
// Output Synthesis
// ============================================================================

/**
 * 综合多个专家的输出
 */
function synthesizeOutputs(experts: ExpertOutput[], agentName: string): string {
  const lines: string[] = [];

  lines.push(`# ${agentName} 多专家会审结果`);
  lines.push('');

  // 专家输出汇总
  for (let i = 0; i < experts.length; i++) {
    const expert = experts[i];
    lines.push(`## 专家 ${i + 1}: ${expert.model} (${expert.role})`);
    lines.push('');
    lines.push(expert.content);
    lines.push('');
    lines.push(`*执行时间: ${expert.timestamp}ms | 人格注入: ${expert.personalityInjected ? '✓' : '✗'} | 情感激励: ${expert.emotionPromptApplied ? '✓' : '✗'}*`);
    lines.push('');
    lines.push('---');
    lines.push('');
  }

  // 综合分析
  lines.push('## 综合结论');
  lines.push('');
  lines.push('*基于以上专家意见，综合分析如下：*');
  lines.push('');
  lines.push('[TODO: 实现智能综合逻辑]');

  return lines.join('\n');
}

// ============================================================================
// Output Validation
// ============================================================================

/**
 * 验证输出质量（基于 OUTPUT_SCHEMA）
 */
function validateOutput(experts: ExpertOutput[], agentName: string): { passed: boolean; issues: string[] } {
  const issues: string[] = [];

  // 检查专家数量
  if (experts.length === 0) {
    issues.push('No expert outputs received');
    return { passed: false, issues };
  }

  // 检查每个专家的输出
  for (const expert of experts) {
    if (!expert.content || expert.content.length < 10) {
      issues.push(`${expert.model}: Output too short or empty`);
    }

    if (!expert.personalityInjected) {
      issues.push(`${expert.model}: Personality not injected`);
    }

    // 根据角色检查 OUTPUT_SCHEMA 关键字段
    // TODO: 实现更详细的 OUTPUT_SCHEMA 验证
  }

  return {
    passed: issues.length === 0,
    issues
  };
}

// ============================================================================
// Main Executor
// ============================================================================

/**
 * 执行 agent 任务
 *
 * @param agentName - Agent 名称（如 'Reporter', 'PM'）
 * @param userTask - 用户任务描述
 * @param context - 可选的上下文信息
 * @returns 执行结果
 */
export async function executeAgent(
  agentName: string,
  userTask: string,
  context?: string
): Promise<AgentExecutionResult> {
  const startTime = Date.now();

  console.log(`[Agent Executor] Starting execution for @${agentName}`);
  console.log(`[Agent Executor] Task: ${userTask}`);

  try {
    // 1. 读取并解析 agent 定义
    const agentDef = parseAgentDefinition(agentName);
    console.log(`[Agent Executor] Agent definition loaded: ${agentDef.name}`);
    console.log(`[Agent Executor] Delegation mode: ${agentDef.delegation_mode}`);

    // 2. 检查是否支持 MCP delegation
    if (agentDef.delegation_mode !== 'mcp') {
      throw new Error(`Agent ${agentName} is not configured for MCP delegation (mode: ${agentDef.delegation_mode})`);
    }

    // 3. 调用专家组
    const experts = await callExperts(agentDef.default_models!, userTask, context);

    // 4. 综合输出
    const synthesis = synthesizeOutputs(experts, agentName);

    // 5. 验证质量
    const validation = validateOutput(experts, agentName);

    // 6. 返回结果
    const totalTime = Date.now() - startTime;
    console.log(`[Agent Executor] Execution completed in ${totalTime}ms`);

    return {
      success: validation.passed,
      agentName,
      experts,
      synthesis,
      validation,
      metrics: {
        totalTime,
        expertCount: experts.length
      }
    };
  } catch (error) {
    console.error(`[Agent Executor] Execution failed:`, error);
    throw error;
  }
}

// ============================================================================
// CLI Entry Point
// ============================================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log('Usage: bun agent-executor.ts <agent-name> <task>');
    console.log('Example: bun agent-executor.ts Reporter "Write chapter 1"');
    process.exit(1);
  }

  const [agentName, ...taskParts] = args;
  const task = taskParts.join(' ');

  executeAgent(agentName, task)
    .then(result => {
      console.log('\n=== Execution Result ===');
      console.log(`Success: ${result.success}`);
      console.log(`Experts called: ${result.metrics.expertCount}`);
      console.log(`Total time: ${result.metrics.totalTime}ms`);
      console.log('\n=== Synthesis ===');
      console.log(result.synthesis);

      if (!result.validation.passed) {
        console.log('\n=== Validation Issues ===');
        result.validation.issues.forEach(issue => console.log(`- ${issue}`));
      }
    })
    .catch(error => {
      console.error('Execution failed:', error);
      process.exit(1);
    });
}
