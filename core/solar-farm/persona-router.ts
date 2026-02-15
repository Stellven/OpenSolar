/**
 * Persona Router v2.0 - 极简版
 *
 * 核心设计：6个旋钮 + 3层配置 + neutral对冲
 */

// ============================================================
// 一、6个关键旋钮
// ============================================================

export interface Knobs {
  divergent: number;         // 发散 (0-1)
  convergent: number;        // 收敛 (0-1)
  promotion: number;         // 促进 (0-1)
  prevention: number;        // 预防 (0-1)
  evidence_threshold: number;// 证据门槛 (0-1)
  skepticism: number;        // 怀疑强度 (0-1)
  confidence_calibration: number; // 自信校准 (0-1)
  speed_budget: number;      // 速度预算 (0-1)
}

// ============================================================
// 二、路由规则（主脑直接用）
// ============================================================

export const ROUTING = {
  // 需要"正确率/严谨度/反例"的 → 专家 + Verifier
  rigor: {
    models: ['deepseek-r1', 'gemini-2.5-pro'],
    knobs: { skepticism: 0.9, evidence_threshold: 0.85, prevention: 0.8 }
  },

  // 需要"速度/并行/产量"的 → 快模型 + Builder
  speed: {
    models: ['gemini-flash', 'glm-4-plus', 'glm-flash'],
    knobs: { speed_budget: 0.9, divergent: 0.6, promotion: 0.7 }
  },

  // 需要"讲清楚/交付物"的 → Pro模型 + Synthesizer
  synth: {
    models: ['gpt-4', 'gemini-2.5-pro'],
    knobs: { convergent: 0.8, evidence_threshold: 0.6 }
  },

  // 高风险 → neutral对冲 + 复核
  highRisk: {
    requiresNeutral: true,
    requiresReview: true,
    knobs: { prevention: 0.9, skepticism: 0.85 }
  }
};

// ============================================================
// 三、Persona 配置骨架（三层）
// ============================================================

export interface PersonaConfig {
  // Style: 口吻、长度、格式
  style: {
    tone: string;
    length: 'brief' | 'medium' | 'detailed';
    format: 'markdown' | 'json' | 'code';
  };
  // Cognitive Policy: 证据门槛、发散/收敛、反证、置信校准
  cognitive: {
    evidenceRequired: boolean;
    counterExample: boolean;
    uncertaintyLabel: boolean;
    confidenceRange: [number, number];
  };
  // Actuation Policy: 工具调用、并行、回退、预算
  actuation: {
    parallel: boolean;
    fallback?: string;
    retries: number;
  };
  // 旋钮覆盖
  knobs: Partial<Knobs>;
}

// ============================================================
// 四、标准角色（12个）
// ============================================================

export const ROLES: Record<string, PersonaConfig> = {

  // === 学术研究 ===
  scout: {
    style: { tone: '好奇开放', length: 'brief', format: 'markdown' },
    cognitive: { evidenceRequired: false, counterExample: false, uncertaintyLabel: false, confidenceRange: [0.3, 0.7] },
    actuation: { parallel: true, retries: 2 },
    knobs: { divergent: 0.9, promotion: 0.8, speed_budget: 0.8 }
  },

  extractor: {
    style: { tone: '冷静结构化', length: 'medium', format: 'json' },
    cognitive: { evidenceRequired: false, counterExample: false, uncertaintyLabel: true, confidenceRange: [0.5, 0.8] },
    actuation: { parallel: true, retries: 1 },
    knobs: { convergent: 0.7, speed_budget: 0.7 }
  },

  critic: {
    style: { tone: '严谨批判', length: 'detailed', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: true, uncertaintyLabel: true, confidenceRange: [0.7, 0.95] },
    actuation: { parallel: false, retries: 3 },
    knobs: { skepticism: 0.9, evidence_threshold: 0.85, prevention: 0.8 }
  },

  synthesizer: {
    style: { tone: '专业结构化', length: 'detailed', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: false, uncertaintyLabel: true, confidenceRange: [0.6, 0.9] },
    actuation: { parallel: false, retries: 2 },
    knobs: { convergent: 0.8, evidence_threshold: 0.7 }
  },

  // === 方案设计 ===
  explorer: {
    style: { tone: '大胆创新', length: 'medium', format: 'markdown' },
    cognitive: { evidenceRequired: false, counterExample: false, uncertaintyLabel: false, confidenceRange: [0.3, 0.7] },
    actuation: { parallel: true, retries: 1 },
    knobs: { divergent: 0.95, promotion: 0.9, speed_budget: 0.7 }
  },

  architect: {
    style: { tone: '专业系统', length: 'detailed', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: false, uncertaintyLabel: true, confidenceRange: [0.6, 0.9] },
    actuation: { parallel: false, retries: 2 },
    knobs: { convergent: 0.7, evidence_threshold: 0.7, prevention: 0.5 }
  },

  riskOfficer: {
    style: { tone: '审慎诚实', length: 'medium', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: true, uncertaintyLabel: true, confidenceRange: [0.7, 0.95] },
    actuation: { parallel: false, retries: 3 },
    knobs: { prevention: 0.95, skepticism: 0.85 }
  },

  // === 代码开发 ===
  spec: {
    style: { tone: '严谨无歧义', length: 'detailed', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: false, uncertaintyLabel: true, confidenceRange: [0.7, 0.95] },
    actuation: { parallel: false, retries: 2 },
    knobs: { convergent: 0.9, evidence_threshold: 0.8, prevention: 0.7 }
  },

  builder: {
    style: { tone: '务实高效', length: 'brief', format: 'code' },
    cognitive: { evidenceRequired: false, counterExample: false, uncertaintyLabel: false, confidenceRange: [0.4, 0.8] },
    actuation: { parallel: true, retries: 2 },
    knobs: { speed_budget: 0.9, promotion: 0.8 }
  },

  verifier: {
    style: { tone: '严谨怀疑', length: 'medium', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: true, uncertaintyLabel: true, confidenceRange: [0.8, 0.98] },
    actuation: { parallel: false, retries: 3 },
    knobs: { skepticism: 0.95, evidence_threshold: 0.9, prevention: 0.9 }
  },

  // === 生活/通用 ===
  concierge: {
    style: { tone: '亲和快捷', length: 'brief', format: 'markdown' },
    cognitive: { evidenceRequired: false, counterExample: false, uncertaintyLabel: false, confidenceRange: [0.4, 0.8] },
    actuation: { parallel: true, retries: 1 },
    knobs: { speed_budget: 0.9, promotion: 0.7 }
  },

  governor: {
    style: { tone: '客观审慎', length: 'medium', format: 'markdown' },
    cognitive: { evidenceRequired: true, counterExample: true, uncertaintyLabel: true, confidenceRange: [0.85, 0.99] },
    actuation: { parallel: false, retries: 3 },
    knobs: { prevention: 0.95, skepticism: 0.9, evidence_threshold: 0.9, convergent: 0.9 }
  }
};

// ============================================================
// 五、编队模板
// ============================================================

export const TEAMS = {
  research: ['scout', 'extractor', 'critic', 'synthesizer', 'governor'],
  design: ['explorer', 'architect', 'riskOfficer', 'synthesizer', 'governor'],
  coding: ['spec', 'builder', 'verifier'],
  life_low: ['concierge'],
  life_high: ['critic', 'governor']
};

// ============================================================
// 六、Neutral 对冲机制
// ============================================================

/**
 * 高风险任务：跑两份，选更稳的
 *
 * 用法：
 *   const result = await neutralHedge(task, 'critic');
 *   // 会同时调 critic + neutral，返回更保守的结果
 */
export async function neutralHedge(
  task: string,
  primaryRole: string,
  executor: (role: string, task: string) => Promise<string>
): Promise<{ result: string; picked: 'primary' | 'neutral' | 'merged'; reason: string }> {

  // 并行跑两份
  const [primary, neutral] = await Promise.all([
    executor(primaryRole, task),
    executor('governor', task)  // neutral = governor 人格
  ]);

  // 选更稳的：证据更多、不确定标注更全、风险提示更明确
  const primaryScore = scoreStability(primary);
  const neutralScore = scoreStability(neutral);

  if (neutralScore > primaryScore + 0.1) {
    return { result: neutral, picked: 'neutral', reason: 'neutral更稳' };
  }
  if (primaryScore > neutralScore + 0.1) {
    return { result: primary, picked: 'primary', reason: 'primary更稳' };
  }

  // 差不多则合并
  return {
    result: mergeResults(primary, neutral),
    picked: 'merged',
    reason: '两者接近，合并'
  };
}

function scoreStability(text: string): number {
  let score = 0.5;
  // 证据词
  if (/证据|数据|引用|来源|根据/.test(text)) score += 0.15;
  // 不确定标注
  if (/不确定|待验证|需要确认|可能|推测/.test(text)) score += 0.1;
  // 风险提示
  if (/风险|注意|可能.*问题|需要.*复核/.test(text)) score += 0.15;
  // 反例
  if (/反例|但是|然而|另一种可能/.test(text)) score += 0.1;
  return Math.min(1, score);
}

function mergeResults(a: string, b: string): string {
  return `${a}\n\n---\n\n【Governor补充】\n${b}`;
}

// ============================================================
// 七、快速工具函数
// ============================================================

/** 根据任务类型选编队 */
export function selectTeam(type: 'research' | 'design' | 'coding' | 'life_low' | 'life_high'): string[] {
  return TEAMS[type];
}

/** 根据角色生成prompt */
export function buildPrompt(role: string): string {
  const r = ROLES[role];
  if (!r) return '';

  return `
【${role}】
风格: ${r.style.tone}，${r.style.length}
认知: 证据${r.cognitive.evidenceRequired ? '必填' : '可选'}，反例${r.cognitive.counterExample ? '必找' : '可选'}，不确定${r.cognitive.uncertaintyLabel ? '必标注' : '可选'}
旋钮: 发散${r.knobs.divergent || 0.5} | 收敛${r.knobs.convergent || 0.5} | 怀疑${r.knobs.skepticism || 0.5} | 证据门槛${r.knobs.evidence_threshold || 0.5}
`.trim();
}

export default { ROUTING, ROLES, TEAMS, Knobs, neutralHedge, selectTeam, buildPrompt };
