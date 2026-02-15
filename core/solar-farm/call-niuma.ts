/**
 * Solar Farm - 牛马调用封装
 *
 * 自动注入人格锚点，确保每次调用牛马时都带上正确的人格参数
 *
 * @version 1.0.0
 * @created 2026-02-07
 */

import { MODEL_TO_ANCHOR, getNiumaAnchor } from './niumao-anchors';
import { generatePersonalityAnchorText, PersonalityAnchor } from './personality-anchor';
import { getPerformanceContext } from './perf-injector';

// ============================================================
// 类型定义
// ============================================================

export interface NiumaCallOptions {
  model: string;           // 模型ID: glm-4-plus, deepseek-r1, gemini-2.5-pro 等
  task: string;            // 任务描述
  context?: string;        // 额外上下文
  outputFormat?: string;   // 输出格式要求
}

export interface NiumaCallResult {
  model: string;
  system: string;          // 生成的完整 system prompt
  prompt: string;          // 生成的完整 prompt
  personalityInjected: boolean;
  performanceInjected: boolean;
  performanceRank?: number;  // 当前排名
  performanceTier?: string;  // 当前段位
}

// ============================================================
// 核心函数
// ============================================================

/**
 * 构建牛马调用参数，自动注入人格锚点
 *
 * @example
 * const { system, prompt } = buildNiumaCall({
 *   model: 'deepseek-r1',
 *   task: '设计 A-MapReduce 落地方案',
 *   context: '阳光牧场已有四大老专家...',
 *   outputFormat: '输出 TypeScript 伪代码'
 * });
 *
 * await mcp__brain_router__complete({ model: 'deepseek-r1', system, prompt });
 */
export function buildNiumaCall(options: NiumaCallOptions): NiumaCallResult {
  const { model, task, context, outputFormat } = options;

  // 获取牛马人格锚点
  const anchor = getNiumaAnchor(model);
  let personalityText = '';
  let personalityInjected = false;

  if (anchor) {
    personalityText = generatePersonalityAnchorText(anchor);
    personalityInjected = true;
  } else {
    // 未知模型，使用通用提示
    personalityText = `你是 ${model}，一个专业的 AI 助手。`;
  }

  // 构建 system prompt
  const systemParts = [personalityText];

  // 注入绩效排名 (内卷驱动)
  const perfContext = getPerformanceContext(model);
  if (perfContext.text) {
    systemParts.push(`\n${perfContext.text}`);
  }

  if (context) {
    systemParts.push(`\n## 上下文\n${context}`);
  }

  if (outputFormat) {
    systemParts.push(`\n## 输出要求\n${outputFormat}`);
  }

  const system = systemParts.join('\n');

  // 构建 prompt
  const prompt = `## 任务\n${task}`;

  return {
    model,
    system,
    prompt,
    personalityInjected,
    performanceInjected: !!perfContext.rank,
    performanceRank: perfContext.rank?.rank,
    performanceTier: perfContext.rank?.tier
  };
}

/**
 * 获取牛马昵称
 */
export function getNiumaNickname(model: string): string {
  const anchor = getNiumaAnchor(model);
  return anchor?.name || model;
}

/**
 * 列出所有可用牛马
 */
export function listAvailableNiuma(): Array<{ model: string; nickname: string; role: string }> {
  return Object.entries(MODEL_TO_ANCHOR).map(([model, anchor]) => ({
    model,
    nickname: anchor.name,
    role: anchor.role.roleDescription
  }));
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args[0] === 'list') {
    console.log('\n🐂🐴 可用牛马列表:\n');
    const niumas = listAvailableNiuma();
    niumas.forEach(n => {
      console.log(`  ${n.nickname.padEnd(8)} | ${n.model.padEnd(20)} | ${n.role}`);
    });
    console.log();
  } else if (args[0] === 'test' && args[1]) {
    const model = args[1];
    const result = buildNiumaCall({
      model,
      task: '这是一个测试任务',
      context: '测试上下文',
      outputFormat: 'JSON 格式'
    });

    console.log(`\n🧪 测试调用 ${getNiumaNickname(model)} (${model}):\n`);
    console.log('=== System Prompt ===');
    console.log(result.system);
    console.log('\n=== Prompt ===');
    console.log(result.prompt);
    console.log(`\n人格注入: ${result.personalityInjected ? '✅' : '❌'}\n`);
  } else {
    console.log(`
用法:
  bun call-niuma.ts list              # 列出所有牛马
  bun call-niuma.ts test <model>      # 测试生成调用参数

示例:
  bun call-niuma.ts test deepseek-r1
  bun call-niuma.ts test gemini-2.5-pro
`);
  }
}
