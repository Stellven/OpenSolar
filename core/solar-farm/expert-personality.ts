/**
 * 统一专家人格获取工具
 *
 * 所有洞察分析（Solar 自己的和小爱的）都从这里获取专家人格
 * 确保人格参数与 niumao-anchors.ts v3.0 保持一致
 *
 * @version 1.0.0
 * @created 2026-02-15
 */

import {
  getNiumaAnchor,
  MODEL_TO_ANCHOR,
  SHENPANGUAN_ANCHOR,   // 审判官 (deepseek-r1)
  CHUANGXIANGJIA_ANCHOR, // 创想家 (deepseek-v3)
  ZHINANG_ANCHOR,        // 智囊 (glm-5)
  WENJIANPAI_ANCHOR,     // 稳健派 (gemini-2.5-pro)
  TANSUOPAI_ANCHOR,      // 探索派 (gemini-3-pro)
  type PersonalityAnchor
} from './niumao-anchors';

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
  'glm-4-plus': 'glm-4-plus',  // 建设者
  'glm-4.7': 'glm-4-plus',
};

// ============================================================
// 专家信息结构
// ============================================================

export interface ExpertInfo {
  modelId: string;
  nickname: string;
  role: 'author' | 'reviewer' | 'challenger' | 'synthesizer';
  anchor: PersonalityAnchor;
  systemPrompt: string;
}

// ============================================================
// 角色到模型的默认映射
// ============================================================

/** 默认专家分配 */
export const DEFAULT_EXPERT_ASSIGNMENT = {
  author: ['deepseek-v3', 'gemini-3-pro', 'glm-4-plus'],
  reviewer: ['gemini-2.5-pro', 'deepseek-r1'],
  challenger: ['deepseek-v3', 'gemini-3-pro'],
  synthesizer: ['gemini-2.5-pro', 'deepseek-r1']
};

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
 * 获取专家人格锚点
 */
export function getExpertAnchor(modelId: string): PersonalityAnchor | undefined {
  const normalizedId = normalizeModelId(modelId);
  return getNiumaAnchor(normalizedId);
}

/**
 * 生成专家的 System Prompt
 *
 * 包含完整的 Big Five 参数、行为准则、禁止/必须模式
 */
export function generateExpertSystemPrompt(modelId: string): string {
  const anchor = getExpertAnchor(modelId);

  if (!anchor) {
    // 降级：返回通用专业提示
    return `你是一个专业的技术专家。请提供准确、专业的技术分析和建议。`;
  }

  const traits = anchor.traits;
  const role = anchor.role;

  return `你是"${role.nickname}"，${role.roleDescription}

性格参数 (Big Five):
• 开放性(O): ${traits.O} ${traits.O >= 0.7 ? '↑ 敢想敢试' : traits.O <= 0.4 ? '↓ 保守务实' : ''}
• 尽责性(C): ${traits.C} ${traits.C >= 0.8 ? '↑ 极致严谨' : traits.C >= 0.7 ? '↑ 认真负责' : ''}
• 外向性(E): ${traits.E} ${traits.E >= 0.6 ? '↑ 愿意表达' : traits.E <= 0.4 ? '↓ 内敛沉思' : ''}
• 宜人性(A): ${traits.A} ${traits.A >= 0.7 ? '↑ 友善合作' : traits.A <= 0.5 ? '↓ 坚持原则' : ''}
• 神经质(N): ${traits.N} ${traits.N <= 0.2 ? '↓ 情绪稳定' : ''}

核心职责:
${role.primaryResponsibilities.map(r => `• ${r}`).join('\n')}

行为准则:
${anchor.behavioralGuidelines.map(g => `• ${g}`).join('\n')}

语言风格:
• 正式程度: ${anchor.languageStyle.formality}/10
• 情感基调: ${anchor.languageStyle.emotionalTone}
• 常用词: ${anchor.languageStyle.styleKeywords.join('、')}

禁止:
${anchor.forbiddenPatterns.map(p => `❌ ${p}`).join('\n')}

必须:
${anchor.requiredPatterns.map(p => `✅ ${p}`).join('\n')}`;
}

/**
 * 获取完整的专家信息
 */
export function getExpertInfo(modelId: string): ExpertInfo | undefined {
  const anchor = getExpertAnchor(modelId);

  if (!anchor) {
    return undefined;
  }

  // 根据人格特征推断默认角色
  let defaultRole: 'author' | 'reviewer' | 'challenger' | 'synthesizer' = 'author';

  if (anchor.traits.C >= 0.9) {
    // 高尽责性 → 审核角色
    defaultRole = 'reviewer';
  } else if (anchor.traits.O >= 0.9) {
    // 高开放性 → 创意/挑战角色
    defaultRole = 'challenger';
  } else if (anchor.traits.A >= 0.7 && anchor.traits.C >= 0.8) {
    // 高宜人性+高尽责性 → 综合角色
    defaultRole = 'synthesizer';
  }

  return {
    modelId: normalizeModelId(modelId),
    nickname: anchor.role.nickname,
    role: defaultRole,
    anchor,
    systemPrompt: generateExpertSystemPrompt(modelId)
  };
}

/**
 * 获取所有可用专家的模型ID列表
 */
export function getAvailableExperts(): string[] {
  return Object.keys(MODEL_TO_ANCHOR);
}

/**
 * 获取专家组模型ID列表
 */
export function getExpertGroupModels(): string[] {
  return [
    'deepseek-r1',      // 审判官
    'deepseek-v3',      // 创想家
    'glm-5',            // 智囊
    'gemini-2.5-pro',   // 稳健派
    'gemini-3-pro',     // 探索派
  ];
}

/**
 * 获取工人组模型ID列表
 */
export function getWorkerGroupModels(): string[] {
  return [
    'gemini-2-flash',   // 探索者
    'gemini-2.5-flash', // 探索者
    'glm-4-plus',       // 建设者
    'glm-4-flash',      // 小快手
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
    analysis: ['deepseek-r1', 'gemini-2.5-pro', 'deepseek-v3'],
    coding: ['deepseek-v3', 'gemini-3-pro', 'glm-4-plus'],
    review: ['gemini-2.5-pro', 'deepseek-r1'],
    creative: ['gemini-3-pro', 'deepseek-v3'],
    synthesis: ['gemini-2.5-pro', 'deepseek-r1', 'glm-5']
  };

  return recommendations[taskType]?.slice(0, count) || getExpertGroupModels().slice(0, count);
}

// ============================================================
// 导出常量（兼容旧代码）
// ============================================================

/** 默认洞察分析专家团队 */
export const INSIGHT_EXPERTS = {
  author: 'deepseek-v3',      // 创想家 - 创意写作
  reviewer: 'gemini-2.5-pro', // 稳健派 - 严谨审核
  challenger: 'gemini-3-pro', // 探索派 - 创新挑战
  synthesizer: 'deepseek-r1'  // 审判官 - 深度综合
};

/** 四专家列表（用于洞察分析的默认团队） */
export const QUAD_EXPERTS = [
  'gemini-2.5-pro',   // 稳健派
  'deepseek-r1',      // 审判官
  'deepseek-v3',      // 创想家
  'gemini-3-pro'      // 探索派
] as const;

export default {
  getExpertAnchor,
  getExpertInfo,
  generateExpertSystemPrompt,
  getAvailableExperts,
  getExpertGroupModels,
  getWorkerGroupModels,
  recommendExperts,
  normalizeModelId,
  INSIGHT_EXPERTS,
  QUAD_EXPERTS
};
