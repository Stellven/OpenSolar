/**
 * Persona Router v3.0 - 两层人格模型
 *
 * A层：叙事层（人类心理学框架）
 * B层：控制面（AI性能旋钮）
 *
 * 来源: 用户洞察 + 学术研究
 */

// ============================================================
// A层：叙事层（人类心理学框架）
// ============================================================

export interface NarrativeLayer {
  // Big Five / OCEAN
  bigFive: {
    openness: number;        // 开放性 (0-1)
    conscientiousness: number; // 尽责性 (0-1)
    extraversion: number;    // 外向性 (0-1)
    agreeableness: number;   // 宜人性 (0-1)
    neuroticism: number;     // 神经质 (0-1)
  };

  // HEXACO 扩展
  hexaco?: {
    honestyHumility: number; // 诚实-谦逊 (0-1) - 抑制自嗨/忽悠/过度自信
  };

  // Regulatory Focus
  regulatoryFocus: {
    promotion: number;       // 促进型 (0-1) - 追求收益
    prevention: number;      // 预防型 (0-1) - 避免损失
  };

  // Construal Level
  construalLevel: 'abstract' | 'concrete' | 'mixed'; // 高层抽象 vs 低层细节

  // Values (Schwartz)
  values?: string[];         // e.g., ['security', 'achievement', 'self-direction']
}

// ============================================================
// B层：控制面（10个可度量旋钮，0-5 分制）
// ============================================================

export interface ControlKnobs {
  rigor: number;             // 证据洁癖 (0-5): 引用、可验证、列假设
  skepticism: number;        // 怀疑强度 (0-5): 主动找反例、挑漏洞
  exploration: number;       // 发散度 (0-5): 给多少备选路线
  decisiveness: number;      // 决断性 (0-5): 不完备信息下拍板+fallback
  riskAversion: number;      // 风险厌恶 (0-5): 越高越保守
  toolFirst: number;         // 工具倾向 (0-5): 主动上网/跑代码/写测试
  compression: number;       // 压缩率 (0-5): 同样信息用多少token
  selfCritique: number;      // 自检强度 (0-5): 自测、单元测试、反思
  socialEmpathy: number;     // 人类体验 (0-5): 生活类任务关键
  competitiveness: number;   // 竞技性 (0-5): PK欲望，互评赛制用
}

// ============================================================
// 兼容旧版 Knobs (映射到新版)
// ============================================================

export interface Knobs {
  divergent: number;         // → exploration
  convergent: number;        // → 5 - exploration
  promotion: number;         // → regulatoryFocus.promotion
  prevention: number;        // → regulatoryFocus.prevention
  evidence_threshold: number;// → rigor / 5
  skepticism: number;        // → skepticism / 5
  confidence_calibration: number; // → decisiveness / 5
  speed_budget: number;      // → (5 - compression) / 5
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
// 四、标准角色（12个）- 使用10旋钮系统
// ============================================================

export interface RoleConfig {
  // 叙事层
  narrative: Partial<NarrativeLayer>;
  // 控制面
  knobs: ControlKnobs;
  // 风格
  style: {
    tone: string;
    length: 'brief' | 'medium' | 'detailed';
    format: 'markdown' | 'json' | 'code';
  };
}

export const ROLES_V3: Record<string, RoleConfig> = {

  // === 学术研究 ===
  scout: {
    narrative: {
      bigFive: { openness: 0.9, conscientiousness: 0.5, extraversion: 0.7, agreeableness: 0.6, neuroticism: 0.3 },
      regulatoryFocus: { promotion: 0.8, prevention: 0.3 },
      construalLevel: 'abstract'
    },
    knobs: { rigor: 1, skepticism: 1, exploration: 5, decisiveness: 3, riskAversion: 1, toolFirst: 4, compression: 4, selfCritique: 1, socialEmpathy: 2, competitiveness: 2 },
    style: { tone: '好奇开放', length: 'brief', format: 'markdown' }
  },

  extractor: {
    narrative: {
      bigFive: { openness: 0.6, conscientiousness: 0.8, extraversion: 0.4, agreeableness: 0.7, neuroticism: 0.3 },
      regulatoryFocus: { promotion: 0.5, prevention: 0.5 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 2, skepticism: 1, exploration: 2, decisiveness: 3, riskAversion: 2, toolFirst: 3, compression: 3, selfCritique: 2, socialEmpathy: 1, competitiveness: 1 },
    style: { tone: '冷静结构化', length: 'medium', format: 'json' }
  },

  critic: {
    narrative: {
      bigFive: { openness: 0.5, conscientiousness: 0.9, extraversion: 0.3, agreeableness: 0.3, neuroticism: 0.4 },
      hexaco: { honestyHumility: 0.8 },
      regulatoryFocus: { promotion: 0.2, prevention: 0.9 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 5, skepticism: 5, exploration: 1, decisiveness: 2, riskAversion: 4, toolFirst: 2, compression: 2, selfCritique: 4, socialEmpathy: 1, competitiveness: 4 },
    style: { tone: '严谨批判', length: 'detailed', format: 'markdown' }
  },

  synthesizer: {
    narrative: {
      bigFive: { openness: 0.7, conscientiousness: 0.8, extraversion: 0.5, agreeableness: 0.7, neuroticism: 0.2 },
      regulatoryFocus: { promotion: 0.5, prevention: 0.5 },
      construalLevel: 'abstract'
    },
    knobs: { rigor: 3, skepticism: 2, exploration: 3, decisiveness: 4, riskAversion: 2, toolFirst: 2, compression: 2, selfCritique: 3, socialEmpathy: 3, competitiveness: 2 },
    style: { tone: '专业结构化', length: 'detailed', format: 'markdown' }
  },

  // === 方案设计 ===
  explorer: {
    narrative: {
      bigFive: { openness: 0.95, conscientiousness: 0.5, extraversion: 0.8, agreeableness: 0.5, neuroticism: 0.3 },
      regulatoryFocus: { promotion: 0.9, prevention: 0.2 },
      construalLevel: 'abstract'
    },
    knobs: { rigor: 1, skepticism: 1, exploration: 5, decisiveness: 3, riskAversion: 1, toolFirst: 3, compression: 3, selfCritique: 1, socialEmpathy: 2, competitiveness: 3 },
    style: { tone: '大胆创新', length: 'medium', format: 'markdown' }
  },

  architect: {
    narrative: {
      bigFive: { openness: 0.8, conscientiousness: 0.8, extraversion: 0.5, agreeableness: 0.6, neuroticism: 0.2 },
      regulatoryFocus: { promotion: 0.5, prevention: 0.5 },
      construalLevel: 'abstract'
    },
    knobs: { rigor: 4, skepticism: 2, exploration: 3, decisiveness: 4, riskAversion: 2, toolFirst: 3, compression: 2, selfCritique: 3, socialEmpathy: 2, competitiveness: 2 },
    style: { tone: '专业系统', length: 'detailed', format: 'markdown' }
  },

  riskOfficer: {
    narrative: {
      bigFive: { openness: 0.4, conscientiousness: 0.9, extraversion: 0.3, agreeableness: 0.5, neuroticism: 0.5 },
      hexaco: { honestyHumility: 0.9 },
      regulatoryFocus: { promotion: 0.1, prevention: 0.95 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 5, skepticism: 4, exploration: 1, decisiveness: 2, riskAversion: 5, toolFirst: 2, compression: 2, selfCritique: 5, socialEmpathy: 1, competitiveness: 2 },
    style: { tone: '审慎诚实', length: 'medium', format: 'markdown' }
  },

  // === 代码开发 ===
  spec: {
    narrative: {
      bigFive: { openness: 0.5, conscientiousness: 0.95, extraversion: 0.3, agreeableness: 0.5, neuroticism: 0.2 },
      regulatoryFocus: { promotion: 0.3, prevention: 0.7 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 4, skepticism: 2, exploration: 1, decisiveness: 3, riskAversion: 3, toolFirst: 2, compression: 2, selfCritique: 3, socialEmpathy: 1, competitiveness: 1 },
    style: { tone: '严谨无歧义', length: 'detailed', format: 'markdown' }
  },

  builder: {
    narrative: {
      bigFive: { openness: 0.6, conscientiousness: 0.7, extraversion: 0.5, agreeableness: 0.7, neuroticism: 0.3 },
      regulatoryFocus: { promotion: 0.7, prevention: 0.3 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 2, skepticism: 1, exploration: 2, decisiveness: 4, riskAversion: 1, toolFirst: 5, compression: 4, selfCritique: 2, socialEmpathy: 2, competitiveness: 3 },
    style: { tone: '务实高效', length: 'brief', format: 'code' }
  },

  verifier: {
    narrative: {
      bigFive: { openness: 0.4, conscientiousness: 0.95, extraversion: 0.2, agreeableness: 0.4, neuroticism: 0.4 },
      hexaco: { honestyHumility: 0.7 },
      regulatoryFocus: { promotion: 0.1, prevention: 0.9 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 5, skepticism: 5, exploration: 1, decisiveness: 2, riskAversion: 4, toolFirst: 5, compression: 2, selfCritique: 5, socialEmpathy: 1, competitiveness: 3 },
    style: { tone: '严谨怀疑', length: 'medium', format: 'markdown' }
  },

  // === 生活/通用 ===
  concierge: {
    narrative: {
      bigFive: { openness: 0.5, conscientiousness: 0.6, extraversion: 0.7, agreeableness: 0.8, neuroticism: 0.3 },
      regulatoryFocus: { promotion: 0.6, prevention: 0.3 },
      construalLevel: 'concrete'
    },
    knobs: { rigor: 1, skepticism: 1, exploration: 2, decisiveness: 4, riskAversion: 1, toolFirst: 4, compression: 5, selfCritique: 1, socialEmpathy: 5, competitiveness: 1 },
    style: { tone: '亲和快捷', length: 'brief', format: 'markdown' }
  },

  governor: {
    narrative: {
      bigFive: { openness: 0.5, conscientiousness: 0.95, extraversion: 0.3, agreeableness: 0.5, neuroticism: 0.2 },
      hexaco: { honestyHumility: 0.9 },
      regulatoryFocus: { promotion: 0.3, prevention: 0.8 },
      construalLevel: 'abstract'
    },
    knobs: { rigor: 5, skepticism: 4, exploration: 1, decisiveness: 3, riskAversion: 4, toolFirst: 2, compression: 2, selfCritique: 5, socialEmpathy: 2, competitiveness: 1 },
    style: { tone: '客观审慎', length: 'medium', format: 'markdown' }
  }
};

// 兼容旧版 ROLES
export const ROLES: Record<string, PersonaConfig> = Object.fromEntries(
  Object.entries(ROLES_V3).map(([name, config]) => [
    name,
    {
      style: config.style,
      cognitive: {
        evidenceRequired: config.knobs.rigor >= 3,
        counterExample: config.knobs.skepticism >= 4,
        uncertaintyLabel: config.knobs.skepticism >= 3,
        confidenceRange: [0.3 + config.knobs.rigor * 0.1, 0.7 + config.knobs.rigor * 0.05] as [number, number]
      },
      actuation: { parallel: config.knobs.exploration >= 3, retries: Math.ceil(config.knobs.selfCritique / 2) },
      knobs: {
        divergent: config.knobs.exploration / 5,
        convergent: (5 - config.knobs.exploration) / 5,
        promotion: config.narrative.regulatoryFocus?.promotion || 0.5,
        prevention: config.narrative.regulatoryFocus?.prevention || 0.5,
        evidence_threshold: config.knobs.rigor / 5,
        skepticism: config.knobs.skepticism / 5,
        confidence_calibration: config.knobs.decisiveness / 5,
        speed_budget: (5 - config.knobs.compression) / 5
      }
    }
  ])
) as Record<string, PersonaConfig>;

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
// 六、Neutral 对冲机制 (使用 neutral-hedge.ts 实现)
// ============================================================

export { runHedge as neutralHedge, scoreStability, buildNeutralPrompt, buildPersonaPrompt, type HedgeResult }
  from './neutral-hedge';

/**
 * 高风险任务：跑两份，选更稳的
 *
 * 用法：
 *   import { neutralHedge } from './persona-router';
 *   const result = await neutralHedge(task, 'critic', 'glm-4-plus', executor);
 *   // 会同时调 critic人格 + 中性版，返回更稳定的结果
 *
 * 评分维度：
 *   - 证据 (0.25): 数据/引用/来源/测试/验证
 *   - 不确定 (0.15): 待验证/可能/推测
 *   - 风险 (0.20): 隐患/缺陷/局限/边界
 *   - 反例 (0.15): 但是/然而/例外/edge case
 *   - 结构 (0.15): markdown格式化程度
 */

// ============================================================
// 七、快速工具函数
// ============================================================

/** 根据任务类型选编队 */
export function selectTeam(type: 'research' | 'design' | 'coding' | 'life_low' | 'life_high'): string[] {
  return TEAMS[type];
}

/** 根据角色生成prompt (旧版兼容) */
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

/** 根据角色生成 V3 prompt (带10旋钮) */
export function buildPromptV3(role: string, task?: string): string {
  const config = ROLES_V3[role];
  if (!config) return '';

  const k = config.knobs;
  const n = config.narrative;

  const lines: string[] = [];

  // 角色定义
  lines.push(`【${role}】`);
  lines.push(`风格: ${config.style.tone}，${config.style.length}`);
  lines.push('');

  // 控制面旋钮 (核心!)
  lines.push('控制面 (0-5分):');
  lines.push(`  证据洁癖: ${k.rigor} ${k.rigor >= 4 ? '(必须引用来源)' : k.rigor >= 2 ? '(优先引用)' : '(可选)'}`);
  lines.push(`  怀疑强度: ${k.skepticism} ${k.skepticism >= 4 ? '(必须找反例)' : k.skepticism >= 2 ? '(尝试找反例)' : '(可选)'}`);
  lines.push(`  发散度: ${k.exploration} ${k.exploration >= 4 ? '(多方案)' : k.exploration >= 2 ? '(2-3个方案)' : '(聚焦一个)'}`);
  lines.push(`  决断性: ${k.decisiveness} ${k.decisiveness >= 4 ? '(快速拍板)' : '(谨慎决策)'}`);
  lines.push(`  风险厌恶: ${k.riskAversion} ${k.riskAversion >= 4 ? '(极度保守)' : k.riskAversion >= 2 ? '(适度谨慎)' : '(可接受风险)'}`);
  lines.push(`  工具倾向: ${k.toolFirst} ${k.toolFirst >= 4 ? '(主动调用工具)' : '(按需调用)'}`);
  lines.push(`  压缩率: ${k.compression} ${k.compression >= 4 ? '(极简)' : '(适中)'}`);
  lines.push(`  自检强度: ${k.selfCritique} ${k.selfCritique >= 4 ? '(必须自检)' : '(建议自检)'}`);
  lines.push('');

  // 叙事层 (可选)
  if (n.hexaco?.honestyHumility && n.hexaco.honestyHumility >= 0.7) {
    lines.push('⚠️ 硬约束: 禁止自嗨/过度承诺，如实报告不确定性和局限');
  }

  if (n.regulatoryFocus) {
    const focus = n.regulatoryFocus.promotion > n.regulatoryFocus.prevention ? '促进型' : '预防型';
    lines.push(`关注点: ${focus}`);
  }

  if (task) {
    lines.push('');
    lines.push('任务:');
    lines.push(task);
  }

  return lines.join('\n');
}

/** 获取角色的旋钮向量 */
export function getKnobsVector(role: string): ControlKnobs | null {
  return ROLES_V3[role]?.knobs || null;
}

/** 对比两个角色的旋钮差异 */
export function compareRoles(a: string, b: string): string {
  const ka = ROLES_V3[a]?.knobs;
  const kb = ROLES_V3[b]?.knobs;

  if (!ka || !kb) return '角色不存在';

  const lines: string[] = [];
  lines.push(`\n📊 角色对比: ${a} vs ${b}\n`);
  lines.push('| 旋钮 | ' + a + ' | ' + b + ' | 差异 |');
  lines.push('|------|-------|-------|------|');

  const keys: (keyof ControlKnobs)[] = ['rigor', 'skepticism', 'exploration', 'decisiveness', 'riskAversion', 'toolFirst', 'compression', 'selfCritique', 'socialEmpathy', 'competitiveness'];

  for (const key of keys) {
    const va = ka[key];
    const vb = kb[key];
    const diff = va - vb;
    const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
    lines.push(`| ${key} | ${va} | ${vb} | ${diffStr} |`);
  }

  return lines.join('\n');
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'roles': {
      console.log('\n📋 可用角色:\n');
      Object.entries(ROLES_V3).forEach(([name, config]) => {
        const k = config.knobs;
        console.log(`  ${name.padEnd(12)} - ${config.style.tone}`);
        console.log(`               证据${k.rigor} 怀疑${k.skepticism} 发散${k.exploration} 决断${k.decisiveness} 风险${k.riskAversion}`);
      });
      break;
    }

    case 'knobs': {
      const role = process.argv[3];
      if (!role) {
        console.log('用法: bun persona-router.ts knobs <role>');
        break;
      }
      const k = ROLES_V3[role]?.knobs;
      if (!k) {
        console.log(`角色 ${role} 不存在`);
        break;
      }
      console.log(`\n📊 ${role} 旋钮向量 (0-5):\n`);
      Object.entries(k).forEach(([key, value]) => {
        const bar = '█'.repeat(value) + '░'.repeat(5 - value);
        console.log(`  ${key.padEnd(15)} [${bar}] ${value}`);
      });
      break;
    }

    case 'compare': {
      const a = process.argv[3];
      const b = process.argv[4];
      if (!a || !b) {
        console.log('用法: bun persona-router.ts compare <role1> <role2>');
        break;
      }
      console.log(compareRoles(a, b));
      break;
    }

    case 'prompt': {
      const role = process.argv[3];
      const task = process.argv.slice(4).join(' ') || undefined;
      if (!role) {
        console.log('用法: bun persona-router.ts prompt <role> [task]');
        break;
      }
      console.log(buildPromptV3(role, task));
      break;
    }

    case 'teams': {
      console.log('\n👥 编队模板:\n');
      Object.entries(TEAMS).forEach(([name, roles]) => {
        console.log(`  ${name}: ${roles.join(' → ')}`);
      });
      break;
    }

    default:
      console.log(`
🎭 Persona Router v3.0 - 两层人格模型

用法:
  bun persona-router.ts roles              # 列出所有角色
  bun persona-router.ts knobs <role>       # 查看角色旋钮
  bun persona-router.ts compare <a> <b>    # 对比两个角色
  bun persona-router.ts prompt <role> [task] # 生成角色prompt
  bun persona-router.ts teams              # 查看编队模板

10个旋钮 (0-5分):
  rigor          证据洁癖 - 引用/可验证/列假设
  skepticism     怀疑强度 - 找反例/挑漏洞
  exploration    发散度 - 备选路线数量
  decisiveness   决断性 - 不完备信息下拍板
  riskAversion   风险厌恶 - 保守程度
  toolFirst      工具倾向 - 主动调用工具
  compression    压缩率 - token效率
  selfCritique   自检强度 - 自测/反思
  socialEmpathy  人类体验 - 生活任务
  competitiveness 竞技性 - PK欲望
`);
  }
}

export default { ROUTING, ROLES, ROLES_V3, TEAMS, selectTeam, buildPrompt, buildPromptV3, getKnobsVector, compareRoles };
