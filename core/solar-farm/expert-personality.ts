/**
 * 统一专家人格获取工具 v2.0
 *
 * 🎮 统一使用 D&D KNOBS 人格格式
 * 所有洞察分析（Solar 自己的和小爱的）都从这里获取专家人格
 *
 * 数据源: niumao-anchors.json (由 prompt-runtime.ts sync 生成)
 * 格式: D&D KNOBS (10个可调节旋钮 + 6个角色职业)
 *
 * @version 2.0.0
 * @updated 2026-02-16 - 从 Big Five 迁移到 D&D KNOBS
 */

import { readFileSync, existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

// ============================================================
// D&D KNOBS 人格格式 (来自 niumao-anchors.json)
// ============================================================

/** JSON 文件中的人格条目结构 */
export interface NiumaJsonEntry {
  nickname: string;
  system_prompt: string;  // 完整的 D&D KNOBS prompt
  role: string;           // builder/verifier/architect/judge/explorer/creator
  knobs?: string;         // KNOBS 参数字符串
  token_estimate?: number;
  version?: string;
  // 兼容旧格式
  group?: 'expert' | 'worker';
  big_five?: { O: number; C: number; E: number; A: number; N: number };
}

/** 专家信息结构 */
export interface ExpertInfo {
  modelId: string;
  nickname: string;
  role: 'author' | 'reviewer' | 'challenger' | 'synthesizer';
  systemPrompt: string;  // D&D KNOBS prompt
  ddRole?: string;       // D&D 角色类型
  knobs?: string;
}

// ============================================================
// 模型ID映射（兼容旧名称）
// ============================================================

/** 模型ID别名映射 */
const MODEL_ALIAS: Record<string, string> = {
  'gemini-pro': 'gemini-2.5-pro',
  'gemini-2-pro': 'gemini-2.5-pro',
  'gemini-3-pro-preview': 'gemini-3-pro',
  'deepseek-reasoner': 'deepseek-r1',
  'deepseek-chat': 'deepseek-v3',
  'glm-5': 'glm-5',
  'glm-4.7': 'glm-5',
  'zhipu/glm-5': 'glm-5',
};

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

// ============================================================
// 核心函数
// ============================================================

/**
 * 标准化模型ID
 */
export function normalizeModelId(modelId: string): string {
  return MODEL_ALIAS[modelId] || modelId;
}

/**
 * 获取人格条目 (从 JSON)
 */
export function getNiumoEntry(modelId: string): NiumaJsonEntry | undefined {
  const data = loadNiumaoData();
  const normalizedId = normalizeModelId(modelId);
  return data[normalizedId];
}

/**
 * 生成专家的 System Prompt (D&D KNOBS 格式)
 *
 * 直接使用 JSON 中的 system_prompt，已经是完整的 D&D KNOBS 格式
 */
export function generateExpertSystemPrompt(modelId: string): string {
  const entry = getNiumoEntry(modelId);

  if (!entry) {
    // 降级：返回通用专业提示
    console.warn(`⚠️ 未找到模型 ${modelId} 的人格配置，使用通用提示`);
    return `你是一个专业的技术专家。请提供准确、专业的技术分析和建议。`;
  }

  // 直接返回 D&D KNOBS 格式的 system_prompt
  return entry.system_prompt;
}

/**
 * 获取专家昵称
 */
export function getExpertNickname(modelId: string): string {
  const entry = getNiumoEntry(modelId);
  return entry?.nickname || modelId;
}

/**
 * 获取专家 D&D 角色
 */
export function getExpertRole(modelId: string): string {
  const entry = getNiumoEntry(modelId);
  return entry?.role || 'unknown';
}

/**
 * 获取完整的专家信息
 */
export function getExpertInfo(modelId: string): ExpertInfo | undefined {
  const entry = getNiumoEntry(modelId);

  if (!entry) {
    return undefined;
  }

  // 根据 D&D 角色推断默认分析角色
  let defaultRole: 'author' | 'reviewer' | 'challenger' | 'synthesizer' = 'author';

  const roleMapping: Record<string, 'author' | 'reviewer' | 'challenger' | 'synthesizer'> = {
    'creator': 'author',      // 创想家 → 写作
    'builder': 'author',      // 建设者 → 写作
    'verifier': 'reviewer',   // 稳健派 → 审核
    'judge': 'reviewer',      // 审判官 → 审核/综合
    'explorer': 'challenger', // 探索派 → 挑战
    'architect': 'synthesizer' // 智囊 → 综合
  };

  defaultRole = roleMapping[entry.role] || 'author';

  return {
    modelId: normalizeModelId(modelId),
    nickname: entry.nickname,
    role: defaultRole,
    systemPrompt: entry.system_prompt,
    ddRole: entry.role,
    knobs: entry.knobs
  };
}

/**
 * 获取所有可用专家的模型ID列表
 */
export function getAvailableExperts(): string[] {
  const data = loadNiumaoData();
  return Object.keys(data);
}

/**
 * 获取专家组模型ID列表 (D&D 强约束)
 */
export function getExpertGroupModels(): string[] {
  // 根据 D&D 角色排序：verifier, judge, architect, creator, explorer
  return [
    'gemini-2.5-pro',   // 稳健派 - verifier
    'deepseek-r1',      // 审判官 - judge
    'glm-5',            // 智囊 - architect
    'deepseek-v3',      // 创想家 - creator
    'gemini-3-pro',     // 探索派 - explorer (可能没映射)
    'gemini-3-pro-preview', // 探索派 - explorer
  ];
}

/**
 * 获取工人组模型ID列表 (D&D 弱约束)
 */
export function getWorkerGroupModels(): string[] {
  return [
    'gemini-2-flash',   // 快马
    'gemini-2.5-flash', // 快马
    'glm-5',       // 建设者 - builder
    'glm-4-flash',      // 小快手 - builder
  ];
}

/**
 * 根据任务类型推荐专家
 */
export function recommendExperts(
  taskType: 'analysis' | 'coding' | 'review' | 'creative' | 'synthesis',
  count: number = 3
): string[] {
  const recommendations: Record<string, string[]> = {
    analysis: ['deepseek-r1', 'gemini-2.5-pro', 'deepseek-v3'],   // judge + verifier + creator
    coding: ['deepseek-v3', 'glm-5', 'gemini-3-pro-preview'], // creator + builder + explorer
    review: ['gemini-2.5-pro', 'deepseek-r1'],                     // verifier + judge
    creative: ['gemini-3-pro-preview', 'deepseek-v3'],             // explorer + creator
    synthesis: ['gemini-2.5-pro', 'deepseek-r1', 'glm-5']          // verifier + judge + architect
  };

  return recommendations[taskType]?.slice(0, count) || getExpertGroupModels().slice(0, count);
}

// ============================================================
// 角色到模型的默认映射
// ============================================================

/** 默认专家分配 (D&D 角色映射) */
export const DEFAULT_EXPERT_ASSIGNMENT = {
  author: ['deepseek-v3', 'gemini-3-pro-preview', 'glm-5'],     // creator + explorer + builder
  reviewer: ['gemini-2.5-pro', 'deepseek-r1'],                        // verifier + judge
  challenger: ['gemini-3-pro-preview', 'deepseek-v3'],               // explorer + creator
  synthesizer: ['gemini-2.5-pro', 'deepseek-r1', 'glm-5']            // verifier + judge + architect
};

// ============================================================
// 导出常量（兼容旧代码）
// ============================================================

/** 默认洞察分析专家团队 */
export const INSIGHT_EXPERTS = {
  author: 'deepseek-v3',      // 创想家 - 创意写作
  reviewer: 'gemini-2.5-pro', // 稳健派 - 严谨审核
  challenger: 'gemini-3-pro-preview', // 探索派 - 创新挑战
  synthesizer: 'deepseek-r1'  // 审判官 - 深度综合
};

/** 四专家列表（用于洞察分析的默认团队） */
export const QUAD_EXPERTS = [
  'gemini-2.5-pro',   // 稳健派 - verifier
  'deepseek-r1',      // 审判官 - judge
  'deepseek-v3',      // 创想家 - creator
  'gemini-3-pro-preview' // 探索派 - explorer
] as const;

// ============================================================
// 兼容旧接口 (deprecated, 但保留以兼容旧代码)
// ============================================================

/** @deprecated 使用 getNiumoEntry 代替 */
export function getExpertAnchor(modelId: string): any {
  const entry = getNiumoEntry(modelId);
  if (!entry) return undefined;

  // 转换为旧格式
  return {
    name: entry.nickname,
    traits: entry.big_five || { O: 0.5, C: 0.5, E: 0.5, A: 0.5, N: 0.5 },
    role: {
      nickname: entry.nickname,
      roleDescription: `D&D 角色: ${entry.role}`,
      primaryResponsibilities: []
    },
    behavioralGuidelines: [],
    languageStyle: { formality: 7, emotionalTone: '专业', styleKeywords: [] },
    forbiddenPatterns: [],
    requiredPatterns: []
  };
}

export default {
  getNiumoEntry,
  getExpertInfo,
  generateExpertSystemPrompt,
  getAvailableExperts,
  getExpertGroupModels,
  getWorkerGroupModels,
  recommendExperts,
  normalizeModelId,
  getExpertNickname,
  getExpertRole,
  refreshNiumoCache,
  INSIGHT_EXPERTS,
  QUAD_EXPERTS,
  DEFAULT_EXPERT_ASSIGNMENT
};
