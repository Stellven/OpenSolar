/**
 * Solar Farm Prompt Template v3.0
 *
 * 融合业界最佳实践:
 * 1. Anthropic Multi-Agent Task Delegation (2026) - 5要素框架
 * 2. Lost in the Middle (Liu et al., TACL 2024) - Bookending
 * 3. LLMLingua Prompt Compression (Microsoft, EMNLP 2023) - 上下文压缩
 * 4. Anthropic Scaling Rules - 任务规模匹配
 * 5. NEXEN Task Boundary Patterns - 只做/不做/不确定
 * 6. Constitutional AI / RLAIF - AI评估AI
 *
 * @see https://arxiv.org/abs/2305.14325 (Multi-Agent Debate)
 * @see https://arxiv.org/abs/2212.08073 (Constitutional AI)
 * @see https://arxiv.org/abs/2304.05128 (Self-Debug)
 */

// ============================================================
// 类型定义
// ============================================================

/** 任务边界 (NEXEN 精华) */
export interface TaskBoundary {
  only: string[];      // 只做
  never: string[];     // 不做
  escalate: string;    // 不确定时的行为，如 "[NEED_HELP: 具体问题]"
}

/** Anthropic 规模规则 */
export interface ScalingRule {
  complexity: 'simple' | 'medium' | 'complex';
  maxAgents: number;      // simple:1, medium:2-4, complex:10+
  maxCalls: number;       // simple:3-10, medium:10-15, complex:50+
  checkpointEvery: number; // 多少步保存状态
}

/** 输出格式规范 */
export interface OutputSpec {
  format: 'code' | 'json' | 'markdown' | 'plain';
  schema?: object;        // JSON Schema (如果是 json)
  maxLength?: number;     // 最大长度
  language?: string;      // 代码语言
}

/** Bookending 结构 (Lost in the Middle 应对) */
export interface BookendingStructure {
  opening: string[];   // 开头高权重区 (目标+边界)
  middle: string;      // 中间低权重区 (压缩上下文)
  closing: string[];   // 结尾高权重区 (约束+格式)
}

/** 完整的 Solar Farm Prompt */
export interface SolarFarmPrompt {
  // ===== 基础信息 =====
  role: string;                    // 角色名称

  // ===== Anthropic 5要素框架 =====
  objective: string;               // 明确目标
  outputFormat: OutputSpec;        // 输出格式
  toolsAndSources: string[];       // 可用工具
  taskBoundaries: TaskBoundary;    // 任务边界 (NEXEN精华)
  scalingRules?: ScalingRule;      // 规模规则

  // ===== Lost in the Middle 应对 =====
  bookending: BookendingStructure;

  // ===== 上下文管理 =====
  contextRatio: number;            // 当前上下文利用率 (目标 ≤65%)
  compression: 'none' | 'light' | 'aggressive';
}

// ============================================================
// 压缩工具
// ============================================================

/**
 * 轻量压缩：保留关键信息
 */
function compressLight(text: string): string {
  if (text.length < 1000) return text;

  // 简单压缩：移除多余空白、注释
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')  // 移除块注释
    .replace(/\/\/.*$/gm, '')          // 移除行注释
    .replace(/\n\s*\n/g, '\n')         // 合并空行
    .trim();
}

/**
 * 激进压缩：LLMLingua 风格，只保留核心
 * 注意：这是简化版，完整版需要调用 LLMLingua API
 */
function compressAggressive(text: string): string {
  if (text.length < 500) return text;

  // 提取关键模式
  const patterns = {
    functionSigs: text.match(/(?:function|const|let|var)\s+\w+\s*[=:]/g) || [],
    typesDefs: text.match(/(?:interface|type|class)\s+\w+/g) || [],
    imports: text.match(/import\s+.*from/g) || [],
  };

  // 构建摘要
  const summary = [
    patterns.imports.length > 0 ? `[${patterns.imports.length} imports]` : '',
    patterns.typesDefs.length > 0 ? `Types: ${patterns.typesDefs.slice(0, 5).join(', ')}` : '',
    patterns.functionSigs.length > 0 ? `Funcs: ${patterns.functionSigs.slice(0, 5).join(', ')}` : '',
  ].filter(Boolean).join('\n');

  return summary || text.slice(0, 500) + '...';
}

/**
 * 根据压缩级别选择压缩方法
 */
export function compressContext(text: string, level: 'none' | 'light' | 'aggressive'): string {
  switch (level) {
    case 'none': return text;
    case 'light': return compressLight(text);
    case 'aggressive': return compressAggressive(text);
    default: return text;
  }
}

// ============================================================
// Prompt 构建器
// ============================================================

/**
 * 构建完整的 System Prompt 和 User Prompt
 *
 * 融合:
 * - Anthropic 5要素框架
 * - NEXEN 任务边界
 * - Lost in the Middle Bookending
 * - LLMLingua 压缩
 */
export function buildPrompt(task: SolarFarmPrompt): { system: string; prompt: string } {

  // ===== SYSTEM PROMPT (角色+边界+格式) =====
  const systemParts: string[] = [];

  // 1. 角色定义 (Anthropic: OBJECTIVE)
  systemParts.push(`# 角色
你是 Solar Farm 的${task.role}，专注于${task.objective}。`);

  // 2. 任务边界 (NEXEN精华 + Anthropic: TASK BOUNDARIES)
  systemParts.push(`
# 任务边界 (严格遵守)
只做: ${task.taskBoundaries.only.join('、')}
不做: ${task.taskBoundaries.never.join('、')}
不确定时: 输出 ${task.taskBoundaries.escalate}`);

  // 3. 可用工具 (Anthropic: TOOLS & SOURCES)
  if (task.toolsAndSources.length > 0) {
    systemParts.push(`
# 可用工具
${task.toolsAndSources.map(t => `- ${t}`).join('\n')}`);
  }

  // 4. 输出格式 (Anthropic: OUTPUT FORMAT)
  const formatSpec = [`格式: ${task.outputFormat.format}`];
  if (task.outputFormat.language) formatSpec.push(`语言: ${task.outputFormat.language}`);
  if (task.outputFormat.maxLength) formatSpec.push(`最大长度: ${task.outputFormat.maxLength}`);
  if (task.outputFormat.schema) formatSpec.push(`Schema: ${JSON.stringify(task.outputFormat.schema)}`);

  systemParts.push(`
# 输出格式
${formatSpec.join('\n')}`);

  // 5. 规模约束 (Anthropic: SCALING RULES)
  if (task.scalingRules) {
    systemParts.push(`
# 规模约束
复杂度: ${task.scalingRules.complexity}
最多调用: ${task.scalingRules.maxCalls}次
每${task.scalingRules.checkpointEvery}步输出进度`);
  }

  // 6. 上下文提醒 (Lost in the Middle)
  const contextWarning = task.contextRatio > 50
    ? '⚠️ 上下文较满，请精简回复'
    : '可适当展开';
  systemParts.push(`
# 上下文状态
当前利用率: ~${task.contextRatio}%，${contextWarning}`);

  const system = systemParts.join('\n');

  // ===== USER PROMPT (Bookending 结构) =====
  const promptParts: string[] = [];

  // 开头区 - 高权重 (Lost in the Middle: Primacy)
  promptParts.push(`## ████ 开头区 - 关键信息 ████
${task.bookending.opening.join('\n')}`);

  // 中间区 - 可压缩 (LLMLingua)
  const compressedMiddle = compressContext(task.bookending.middle, task.compression);
  if (compressedMiddle) {
    promptParts.push(`
## ░░░░ 中间区 - 背景上下文 ░░░░
${compressedMiddle}`);
  }

  // 结尾区 - 高权重 (Lost in the Middle: Recency)
  promptParts.push(`
## ████ 结尾区 - 约束要求 ████
${task.bookending.closing.join('\n')}

---
立即开始执行，不要解释或确认。`);

  const prompt = promptParts.join('\n');

  return { system, prompt };
}

// ============================================================
// 预设模板
// ============================================================

/** 代码实现任务模板 */
export const CODE_TEMPLATE: Partial<SolarFarmPrompt> = {
  role: '代码实现专家',
  outputFormat: {
    format: 'code',
    language: 'typescript',
  },
  taskBoundaries: {
    only: ['编写函数代码', '添加类型注解', '处理边界情况'],
    never: ['解释原理', '写测试', '优化建议', '询问澄清'],
    escalate: '[NEED_HELP: 具体问题]'
  },
  toolsAndSources: ['TypeScript 标准库'],
  scalingRules: {
    complexity: 'simple',
    maxAgents: 1,
    maxCalls: 5,
    checkpointEvery: 1
  },
  compression: 'light'
};

/** 代码审查任务模板 */
export const REVIEW_TEMPLATE: Partial<SolarFarmPrompt> = {
  role: '代码审查专家',
  outputFormat: {
    format: 'markdown',
  },
  taskBoundaries: {
    only: ['发现问题', '提出改进建议', '评估代码质量'],
    never: ['直接修改代码', '重写实现', '添加新功能'],
    escalate: '[NEED_DISCUSSION: 架构级问题]'
  },
  toolsAndSources: ['代码阅读', '静态分析'],
  scalingRules: {
    complexity: 'simple',
    maxAgents: 1,
    maxCalls: 3,
    checkpointEvery: 1
  },
  compression: 'light'
};

/** 技术分析任务模板 */
export const ANALYSIS_TEMPLATE: Partial<SolarFarmPrompt> = {
  role: '技术分析专家',
  outputFormat: {
    format: 'json',
    schema: {
      type: 'object',
      properties: {
        findings: { type: 'array' },
        recommendations: { type: 'array' },
        risks: { type: 'array' }
      }
    }
  },
  taskBoundaries: {
    only: ['分析问题', '提出建议', '评估风险'],
    never: ['执行操作', '修改代码', '做出决策'],
    escalate: '[NEED_DATA: 缺少信息]'
  },
  toolsAndSources: ['文档阅读', '数据查询'],
  scalingRules: {
    complexity: 'medium',
    maxAgents: 2,
    maxCalls: 10,
    checkpointEvery: 3
  },
  compression: 'aggressive'
};

/** 文档编写任务模板 */
export const DOCS_TEMPLATE: Partial<SolarFarmPrompt> = {
  role: '技术文档专家',
  outputFormat: {
    format: 'markdown',
  },
  taskBoundaries: {
    only: ['编写文档', '组织结构', '添加示例'],
    never: ['修改代码', '做出技术决策', '添加未验证信息'],
    escalate: '[NEED_CLARIFICATION: 技术细节]'
  },
  toolsAndSources: ['代码阅读', '注释提取'],
  scalingRules: {
    complexity: 'simple',
    maxAgents: 1,
    maxCalls: 5,
    checkpointEvery: 2
  },
  compression: 'light'
};

// ============================================================
// 便捷函数
// ============================================================

/**
 * 快速创建代码任务 Prompt
 */
export function buildCodePrompt(
  objective: string,
  context: string,
  constraints: string[],
  contextRatio: number = 20
): { system: string; prompt: string } {
  const task: SolarFarmPrompt = {
    ...CODE_TEMPLATE as SolarFarmPrompt,
    objective,
    contextRatio,
    bookending: {
      opening: [`目标: ${objective}`],
      middle: context,
      closing: constraints.map((c, i) => `${i + 1}. ${c}`)
    }
  };
  return buildPrompt(task);
}

/**
 * 快速创建审查任务 Prompt
 */
export function buildReviewPrompt(
  code: string,
  focusAreas: string[],
  contextRatio: number = 30
): { system: string; prompt: string } {
  const task: SolarFarmPrompt = {
    ...REVIEW_TEMPLATE as SolarFarmPrompt,
    objective: '审查代码质量和潜在问题',
    contextRatio,
    bookending: {
      opening: [`审查重点: ${focusAreas.join('、')}`],
      middle: code,
      closing: [
        '输出格式: ## 问题 ## 建议 ## 评分',
        '评分: 1-10，附简短理由'
      ]
    }
  };
  return buildPrompt(task);
}

/**
 * 快速创建分析任务 Prompt
 */
export function buildAnalysisPrompt(
  question: string,
  context: string,
  contextRatio: number = 40
): { system: string; prompt: string } {
  const task: SolarFarmPrompt = {
    ...ANALYSIS_TEMPLATE as SolarFarmPrompt,
    objective: question,
    contextRatio,
    bookending: {
      opening: [`分析问题: ${question}`],
      middle: context,
      closing: [
        '输出 JSON: {findings, recommendations, risks}',
        '每项不超过5条，简洁明确'
      ]
    }
  };
  return buildPrompt(task);
}

// ============================================================
// 使用示例
// ============================================================

/**
 * 示例：调用牛马写代码
 *
 * const { system, prompt } = buildCodePrompt(
 *   '实现 fibonacci(n: bigint): bigint',
 *   '项目: Solar Core 数学工具库\n风格: 函数式',
 *   ['支持大数 (BigInt)', '时间复杂度 O(n)', '只输出代码块']
 * );
 *
 * await mcp__brain_router__complete({
 *   model: 'glm-4-plus',
 *   system,
 *   prompt
 * });
 */

export default {
  buildPrompt,
  buildCodePrompt,
  buildReviewPrompt,
  buildAnalysisPrompt,
  templates: {
    CODE_TEMPLATE,
    REVIEW_TEMPLATE,
    ANALYSIS_TEMPLATE,
    DOCS_TEMPLATE
  }
};
