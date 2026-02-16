/**
 * Solar Farm - 牛马调用封装 v2.0
 *
 * 🎮 统一使用 D&D KNOBS 人格格式
 * 自动注入人格锚点，确保每次调用牛马时都带上正确的人格参数
 *
 * 数据源: niumao-anchors.json (由 prompt-runtime.ts sync 生成)
 *
 * @version 2.0.0
 * @updated 2026-02-16 - 从 Big Five 迁移到 D&D KNOBS
 */

import { readFileSync, existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

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
  system: string;          // 生成的完整 system prompt (D&D KNOBS)
  prompt: string;          // 生成的完整 prompt
  personalityInjected: boolean;
  performanceInjected: boolean;
  performanceRank?: number;
  performanceTier?: string;
  ddRole?: string;         // D&D 角色类型
  knobs?: string;          // KNOBS 参数
}

/** JSON 文件中的人格条目结构 */
interface NiumaJsonEntry {
  nickname: string;
  system_prompt: string;
  role: string;
  knobs?: string;
  token_estimate?: number;
  version?: string;
}

// ============================================================
// 人格数据加载 (从 JSON)
// ============================================================

const NIUMAO_JSON_PATH = join(homedir(), '.claude', 'core', 'solar-farm', 'niumao-anchors.json');
let _niumaoCache: Record<string, NiumaJsonEntry> | null = null;

/**
 * 加载人格数据 (带缓存)
 */
function loadNiumaoData(): Record<string, NiumaJsonEntry> {
  if (_niumaoCache) {
    return _niumaoCache;
  }

  if (!existsSync(NIUMAO_JSON_PATH)) {
    console.error(`⚠️ niumao-anchors.json 不存在: ${NIUMAO_JSON_PATH}`);
    return {};
  }

  try {
    const content = readFileSync(NIUMAO_JSON_PATH, 'utf-8');
    _niumaoCache = JSON.parse(content);
    return _niumaoCache!;
  } catch (e) {
    console.error(`⚠️ 加载 niumao-anchors.json 失败:`, e);
    return {};
  }
}

/**
 * 刷新缓存 (当 JSON 文件更新时调用)
 */
export function refreshNiumoCache(): void {
  _niumaoCache = null;
}

/**
 * 获取人格条目
 */
function getNiumoEntry(model: string): NiumaJsonEntry | undefined {
  const data = loadNiumaoData();
  return data[model];
}

// ============================================================
// 核心函数
// ============================================================

/**
 * 构建牛马调用参数，自动注入 D&D KNOBS 人格锚点
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

  // 获取牛马人格 (D&D KNOBS 格式)
  const entry = getNiumoEntry(model);
  let systemPrompt = '';
  let personalityInjected = false;
  let ddRole: string | undefined;
  let knobs: string | undefined;

  if (entry) {
    // 直接使用 JSON 中的 system_prompt (D&D KNOBS 格式)
    systemPrompt = entry.system_prompt;
    personalityInjected = true;
    ddRole = entry.role;
    knobs = entry.knobs;
  } else {
    // 未知模型，使用通用提示
    systemPrompt = `你是 ${model}，一个专业的 AI 助手。请提供准确、专业的技术分析和建议。`;
  }

  // 构建 system prompt
  const systemParts = [systemPrompt];

  // 添加上下文和输出格式
  if (context) {
    systemParts.push(`\n## 上下文\n${context}`);
  }

  if (outputFormat) {
    systemParts.push(`\n## 输出要求\n${outputFormat}`);
  }

  const system = systemParts.join('\n');

  // 构建 prompt
  const prompt = `## 任务\n${task}`;

  // 简化的绩效注入 (保留接口兼容性)
  const performanceInjected = false;

  return {
    model,
    system,
    prompt,
    personalityInjected,
    performanceInjected,
    performanceRank: undefined,
    performanceTier: undefined,
    ddRole,
    knobs
  };
}

/**
 * 获取牛马昵称
 */
export function getNiumaNickname(model: string): string {
  const entry = getNiumoEntry(model);
  return entry?.nickname || model;
}

/**
 * 获取牛马 D&D 角色
 */
export function getNiumaRole(model: string): string {
  const entry = getNiumoEntry(model);
  return entry?.role || 'unknown';
}

/**
 * 列出所有可用牛马
 */
export function listAvailableNiuma(): Array<{ model: string; nickname: string; role: string; knobs?: string }> {
  const data = loadNiumaoData();
  return Object.entries(data).map(([model, entry]) => ({
    model,
    nickname: entry.nickname,
    role: entry.role,
    knobs: entry.knobs
  }));
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args[0] === 'list') {
    console.log('\n🐂🐴 可用牛马列表 (D&D KNOBS 格式):\n');
    const niumas = listAvailableNiuma();
    niumas.forEach(n => {
      console.log(`  ${n.nickname.padEnd(8)} | ${n.model.padEnd(22)} | ${n.role}`);
    });
    console.log(`\n共 ${niumas.length} 个模型\n`);
  } else if (args[0] === 'test' && args[1]) {
    const model = args[1];
    const result = buildNiumaCall({
      model,
      task: '这是一个测试任务',
      context: '测试上下文',
      outputFormat: 'JSON 格式'
    });

    console.log(`\n🧪 测试调用 ${getNiumaNickname(model)} (${model}):\n`);
    console.log(`D&D 角色: ${result.ddRole || '未知'}`);
    console.log(`KNOBS: ${result.knobs || '无'}`);
    console.log('\n=== System Prompt (前500字) ===');
    console.log(result.system.substring(0, 500) + '...');
    console.log('\n=== Prompt ===');
    console.log(result.prompt);
    console.log(`\n人格注入: ${result.personalityInjected ? '✅' : '❌'}`);
    console.log(`格式: ${result.system.includes('KNOBS') ? '✅ D&D KNOBS' : '❌ 旧格式'}\n`);
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
