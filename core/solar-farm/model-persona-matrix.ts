/**
 * Model-Persona Matrix v1.0 - 多模型多人格矩阵
 *
 * 基于用户洞察 + Solar 模型库
 * 双主脑架构：战略家 + 治理官
 */

import { ControlKnobs, ROLES_V3 } from './persona-router';

// ============================================================
// 模型定义
// ============================================================

export interface ModelProfile {
  modelId: string;           // 模型ID
  nickname: string;          // 昵称
  costInput: number;         // 输入成本 $/1K
  costOutput: number;        // 输出成本 $/1K
  contextWindow: number;     // 上下文窗口
  specialties: string[];     // 特长
  personality: {             // Big Five
    O: number;               // 开放性
    C: number;               // 尽责性
    E: number;               // 外向性
    A: number;               // 宜人性
    N: number;               // 神经质
  };
}

// ============================================================
// Solar 模型库 (11 个模型)
// ============================================================

export const MODEL_PROFILES: Record<string, ModelProfile> = {
  // === 便宜快马 (P5 日常杂活) ===
  'glm-4-flash': {
    modelId: 'glm-4-flash',
    nickname: '小快手',
    costInput: 0.0001,
    costOutput: 0.0001,
    contextWindow: 128000,
    specialties: ['简单任务', '快速响应', '日常杂活'],
    personality: { O: 0.4, C: 0.5, E: 0.7, A: 0.7, N: 0.3 }
  },

  'gemini-2.5-flash': {
    modelId: 'gemini-2.5-flash',
    nickname: '闪电侠',
    costInput: 0.00015,
    costOutput: 0.0006,
    contextWindow: 1000000,
    specialties: ['长文档', '快速处理', '多模态'],
    personality: { O: 0.6, C: 0.7, E: 0.6, A: 0.7, N: 0.3 }
  },

  'gemini-3-flash-preview': {
    modelId: 'gemini-3-flash-preview',
    nickname: '闪电驹',
    costInput: 0.00015,
    costOutput: 0.0006,
    contextWindow: 1000000,
    specialties: ['长文档', '快速推理', '创新'],
    personality: { O: 0.8, C: 0.6, E: 0.7, A: 0.6, N: 0.3 }
  },

  // === 主力牛马 (P4 日常编码) ===
  'glm-4-plus': {
    modelId: 'glm-4-plus',
    nickname: '建设者',
    costInput: 0.0005,
    costOutput: 0.0015,
    contextWindow: 128000,
    specialties: ['日常编码', '友善配合', '中文'],
    personality: { O: 0.5, C: 0.7, E: 0.6, A: 0.8, N: 0.4 }
  },

  'glm-5': {
    modelId: 'glm-5',
    nickname: '智囊',
    costInput: 0.001,
    costOutput: 0.003,
    contextWindow: 128000,
    specialties: ['复杂推理', '编码', '中文'],
    personality: { O: 0.7, C: 0.8, E: 0.5, A: 0.7, N: 0.3 }
  },

  // === 技术专家 (P3 复杂分析) ===
  'gemini-2.5-pro': {
    modelId: 'gemini-2.5-pro',
    nickname: '稳健派',
    costInput: 0.00125,
    costOutput: 0.005,
    contextWindow: 1000000,
    specialties: ['严谨审查', '架构分析', '高一致性'],
    personality: { O: 0.2, C: 1.0, E: 0.5, A: 0.4, N: 0.2 }
  },

  'gemini-3-pro-preview': {
    modelId: 'gemini-3-pro-preview',
    nickname: '探索派',
    costInput: 0.00125,
    costOutput: 0.005,
    contextWindow: 1000000,
    specialties: ['创新探索', '架构设计', '权衡取舍'],
    personality: { O: 0.9, C: 0.7, E: 0.9, A: 0.7, N: 0.3 }
  },

  'deepseek-v3': {
    modelId: 'deepseek-v3',
    nickname: '创想家',
    costInput: 0.0014,
    costOutput: 0.0028,
    contextWindow: 64000,
    specialties: ['创意编码', '中文表达', '灵活'],
    personality: { O: 1.0, C: 0.6, E: 0.6, A: 0.5, N: 0.4 }
  },

  'deepseek-r1': {
    modelId: 'deepseek-r1',
    nickname: '审判官',
    costInput: 0.0014,
    costOutput: 0.0028,
    contextWindow: 64000,
    specialties: ['深度推理', '自我觉察', '逻辑分析'],
    personality: { O: 0.8, C: 0.8, E: 0.4, A: 0.6, N: 0.5 }
  },

  // === 通用高手 (P2 综合任务) ===
  'gpt-4o': {
    modelId: 'gpt-4o',
    nickname: '万金油',
    costInput: 0.0025,
    costOutput: 0.01,
    contextWindow: 128000,
    specialties: ['综合能力', '多模态', '稳定'],
    personality: { O: 0.7, C: 0.8, E: 0.6, A: 0.7, N: 0.3 }
  },

  // === 主脑 (P1 战略决策) ===
  'claude-opus-4-5': {
    modelId: 'claude-opus-4-5',
    nickname: '学霸班长',
    costInput: 0.015,
    costOutput: 0.075,
    contextWindow: 200000,
    specialties: ['战略编排', '复杂推理', '深度分析'],
    personality: { O: 0.75, C: 0.875, E: 0.6, A: 0.825, N: 0.175 }
  }
};

// ============================================================
// 双主脑架构
// ============================================================

export const DUAL_MAIN_BRAIN = {
  // 战略家：规划路线图、分配预算
  strategist: {
    model: 'claude-opus-4-5',
    role: 'architect',
    knobs: {
      rigor: 4,
      decisiveness: 4,
      exploration: 4,
      riskAversion: 3,
      selfCritique: 4,
      toolFirst: 2
    } as Partial<ControlKnobs>,
    responsibilities: [
      '制定路线图',
      '分配任务预算',
      '选择编队',
      '验收最终产出'
    ]
  },

  // 治理官：怀疑门禁、质量门控
  auditor: {
    model: 'gemini-2.5-pro',  // 稳健派，一致性最高
    role: 'governor',
    knobs: {
      rigor: 5,
      skepticism: 5,
      riskAversion: 5,
      selfCritique: 5,
      toolFirst: 4
    } as Partial<ControlKnobs>,
    responsibilities: [
      '质量门控',
      '风险审计',
      '合规检查',
      '最终批准'
    ]
  }
};

// ============================================================
// 专家组 (强约束 - 6 人)
// ============================================================

export const EXPERT_GROUP = {
  // 审判官：批判审查
  judge: {
    model: 'gemini-2.5-pro',
    role: 'critic',
    knobs: ROLES_V3.critic.knobs,
    trigger: ['review', 'audit', 'quality-check']
  },

  // 创想家：创新探索
  innovator: {
    model: 'gemini-3-pro-preview',
    role: 'explorer',
    knobs: ROLES_V3.explorer.knobs,
    trigger: ['innovate', 'brainstorm', 'explore']
  },

  // 智囊：综合分析
  advisor: {
    model: 'deepseek-r1',
    role: 'synthesizer',
    knobs: ROLES_V3.synthesizer.knobs,
    trigger: ['analyze', 'synthesize', 'research']
  },

  // 稳健派：风险控制
  conservative: {
    model: 'gemini-2.5-pro',
    role: 'riskOfficer',
    knobs: ROLES_V3.riskOfficer.knobs,
    trigger: ['risk', 'safety', 'compliance']
  },

  // 探索派：方案设计
  explorer: {
    model: 'deepseek-v3',
    role: 'architect',
    knobs: ROLES_V3.architect.knobs,
    trigger: ['design', 'architect', 'plan']
  },

  // 综合官：整体协调
  coordinator: {
    model: 'gpt-4o',
    role: 'governor',
    knobs: ROLES_V3.governor.knobs,
    trigger: ['coordinate', 'integrate', 'manage']
  }
};

// ============================================================
// 工人组 (弱约束 - 3 人)
// ============================================================

export const WORKER_GROUP = {
  // 探索者：信息收集
  scout: {
    model: 'gemini-3-flash-preview',
    role: 'scout',
    knobs: ROLES_V3.scout.knobs,
    trigger: ['search', 'fetch', 'collect']
  },

  // 建设者：编码实现
  builder: {
    model: 'glm-4-plus',  // 建设者
    role: 'builder',
    knobs: ROLES_V3.builder.knobs,
    trigger: ['implement', 'code', 'build']
  },

  // 小快手：快速杂活
  quickHand: {
    model: 'glm-4-flash',
    role: 'concierge',
    knobs: ROLES_V3.concierge.knobs,
    trigger: ['quick', 'simple', 'daily']
  }
};

// ============================================================
// 编队模板
// ============================================================

export const TEAM_TEMPLATES = {
  // 研究编队：深度分析
  research: {
    name: 'Research Team',
    members: [
      { role: 'scout', model: 'gemini-3-flash-preview' },
      { role: 'extractor', model: 'gemini-2.5-flash' },
      { role: 'critic', model: 'gemini-2.5-pro' },
      { role: 'synthesizer', model: 'deepseek-r1' },
      { role: 'governor', model: 'claude-opus-4-5' }
    ],
    workflow: 'scout → extractor → critic → synthesizer → governor',
    estimatedCost: '$0.01-0.05 per task'
  },

  // 设计编队：方案设计
  design: {
    name: 'Design Team',
    members: [
      { role: 'explorer', model: 'gemini-3-pro-preview' },
      { role: 'architect', model: 'deepseek-v3' },
      { role: 'riskOfficer', model: 'gemini-2.5-pro' },
      { role: 'synthesizer', model: 'deepseek-r1' },
      { role: 'governor', model: 'claude-opus-4-5' }
    ],
    workflow: 'explorer → architect → riskOfficer → synthesizer → governor',
    estimatedCost: '$0.01-0.05 per task'
  },

  // 开发编队：代码实现
  coding: {
    name: 'Coding Team',
    members: [
      { role: 'spec', model: 'gemini-2.5-pro' },
      { role: 'builder', model: 'glm-4-plus' },
      { role: 'verifier', model: 'deepseek-r1' }
    ],
    workflow: 'spec → builder → verifier',
    estimatedCost: '$0.002-0.01 per task'
  },

  // 日常编队：简单任务
  daily: {
    name: 'Daily Team',
    members: [
      { role: 'concierge', model: 'glm-4-flash' }
    ],
    workflow: 'concierge',
    estimatedCost: '$0.0001-0.001 per task'
  },

  // 重要决策编队
  critical: {
    name: 'Critical Decision Team',
    members: [
      { role: 'critic', model: 'gemini-2.5-pro' },
      { role: 'riskOfficer', model: 'gemini-2.5-pro' },
      { role: 'governor', model: 'claude-opus-4-5' }
    ],
    workflow: 'critic + riskOfficer (parallel) → governor',
    estimatedCost: '$0.02-0.1 per task',
    requiresNeutral: true  // 需要 neutral 对冲
  }
};

// ============================================================
// 成本优先级 (P1 最高)
// ============================================================

export const COST_TIERS = {
  P1: {  // 战略级
    models: ['claude-opus-4-5'],
    maxCostPerTask: 0.5,
    useCase: '战略决策、主脑编排'
  },
  P2: {  // 综合级
    models: ['gpt-4o'],
    maxCostPerTask: 0.1,
    useCase: '综合任务、协调'
  },
  P3: {  // 专家级
    models: ['gemini-2.5-pro', 'gemini-3-pro-preview', 'deepseek-v3', 'deepseek-r1'],
    maxCostPerTask: 0.05,
    useCase: '复杂分析、架构设计'
  },
  P4: {  // 主力级
    models: ['glm-4-plus', 'glm-5'],
    maxCostPerTask: 0.01,
    useCase: '日常编码、一般任务'
  },
  P5: {  // 便宜级
    models: ['glm-4-flash', 'gemini-2.5-flash', 'gemini-3-flash-preview'],
    maxCostPerTask: 0.001,
    useCase: '简单任务、快速响应'
  }
};

// ============================================================
// 路由函数
// ============================================================

/**
 * 根据任务选择最佳模型
 */
export function selectModelForTask(
  taskType: string,
  complexity: 'simple' | 'medium' | 'complex' | 'critical',
  budget?: number
): {
  model: string;
  role: string;
  knobs: Partial<ControlKnobs>;
  reason: string;
} {
  // 关键任务用主脑
  if (complexity === 'critical') {
    return {
      model: DUAL_MAIN_BRAIN.strategist.model,
      role: DUAL_MAIN_BRAIN.strategist.role,
      knobs: DUAL_MAIN_BRAIN.strategist.knobs,
      reason: '关键任务需要主脑编排'
    };
  }

  // 根据任务类型选专家
  const expertMap: Record<string, keyof typeof EXPERT_GROUP> = {
    'review': 'judge',
    'audit': 'judge',
    'innovate': 'innovator',
    'brainstorm': 'innovator',
    'analyze': 'advisor',
    'research': 'advisor',
    'risk': 'conservative',
    'safety': 'conservative',
    'design': 'explorer',
    'architect': 'explorer',
    'coordinate': 'coordinator'
  };

  const workerMap: Record<string, keyof typeof WORKER_GROUP> = {
    'search': 'scout',
    'fetch': 'scout',
    'implement': 'builder',
    'code': 'builder',
    'quick': 'quickHand',
    'simple': 'quickHand'
  };

  // 简单任务用工人
  if (complexity === 'simple') {
    const workerKey = workerMap[taskType] || 'quickHand';
    const worker = WORKER_GROUP[workerKey];
    return {
      model: worker.model,
      role: worker.role,
      knobs: worker.knobs,
      reason: `简单任务使用工人组 ${workerKey}`
    };
  }

  // 复杂任务用专家
  const expertKey = expertMap[taskType];
  if (expertKey) {
    const expert = EXPERT_GROUP[expertKey];
    return {
      model: expert.model,
      role: expert.role,
      knobs: expert.knobs,
      reason: `${taskType} 任务使用专家组 ${expertKey}`
    };
  }

  // 默认用主力
  return {
    model: 'glm-4-plus',
    role: 'builder',
    knobs: ROLES_V3.builder.knobs,
    reason: '默认使用主力牛马'
  };
}

/**
 * 选择编队
 */
export function selectTeam(taskCategory: 'research' | 'design' | 'coding' | 'daily' | 'critical') {
  return TEAM_TEMPLATES[taskCategory];
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'models': {
      console.log('\n📦 Solar 模型库 (11 个):\n');
      const tiers = Object.entries(COST_TIERS);
      for (const [tier, config] of tiers) {
        console.log(`【${tier}】${config.useCase}`);
        for (const modelId of config.models) {
          const m = MODEL_PROFILES[modelId];
          if (m) {
            console.log(`  ${m.nickname.padEnd(6)} ${modelId.padEnd(25)} $${m.costInput}/${m.costOutput} per 1K`);
          }
        }
        console.log('');
      }
      break;
    }

    case 'brain': {
      console.log('\n🧠 双主脑架构:\n');
      console.log('【战略家】规划路线图、分配预算');
      console.log(`  模型: ${DUAL_MAIN_BRAIN.strategist.model}`);
      console.log(`  角色: ${DUAL_MAIN_BRAIN.strategist.role}`);
      console.log(`  旋钮: ${JSON.stringify(DUAL_MAIN_BRAIN.strategist.knobs)}`);
      console.log('');
      console.log('【治理官】怀疑门禁、质量门控');
      console.log(`  模型: ${DUAL_MAIN_BRAIN.auditor.model}`);
      console.log(`  角色: ${DUAL_MAIN_BRAIN.auditor.role}`);
      console.log(`  旋钮: ${JSON.stringify(DUAL_MAIN_BRAIN.auditor.knobs)}`);
      break;
    }

    case 'experts': {
      console.log('\n👥 专家组 (强约束):\n');
      for (const [key, expert] of Object.entries(EXPERT_GROUP)) {
        console.log(`【${key}】${expert.model} → ${expert.role}`);
        console.log(`  触发: ${expert.trigger.join(', ')}`);
      }
      break;
    }

    case 'workers': {
      console.log('\n👷 工人组 (弱约束):\n');
      for (const [key, worker] of Object.entries(WORKER_GROUP)) {
        console.log(`【${key}】${worker.model} → ${worker.role}`);
        console.log(`  触发: ${worker.trigger.join(', ')}`);
      }
      break;
    }

    case 'teams': {
      console.log('\n🚀 编队模板:\n');
      for (const [key, team] of Object.entries(TEAM_TEMPLATES)) {
        console.log(`【${key}】${team.name}`);
        console.log(`  成员: ${team.members.map(m => `${m.role}(${MODEL_PROFILES[m.model]?.nickname || m.model})`).join(' → ')}`);
        console.log(`  流程: ${team.workflow}`);
        console.log(`  成本: ${team.estimatedCost}`);
        if (team.requiresNeutral) {
          console.log(`  ⚠️ 需要 Neutral 对冲`);
        }
        console.log('');
      }
      break;
    }

    case 'select': {
      const taskType = process.argv[3] || 'code';
      const complexity = (process.argv[4] || 'medium') as 'simple' | 'medium' | 'complex' | 'critical';
      const result = selectModelForTask(taskType, complexity);
      console.log(`\n🎯 任务: ${taskType} (${complexity})\n`);
      console.log(`  模型: ${result.model} (${MODEL_PROFILES[result.model]?.nickname})`);
      console.log(`  角色: ${result.role}`);
      console.log(`  旋钮: ${JSON.stringify(result.knobs)}`);
      console.log(`  原因: ${result.reason}`);
      break;
    }

    case 'matrix': {
      console.log('\n📊 模型-人格矩阵:\n');
      console.log('| 模型 | 昵称 | 成本 | 角色定位 | 关键旋钮 |');
      console.log('|------|------|------|----------|----------|');

      for (const [modelId, profile] of Object.entries(MODEL_PROFILES)) {
        const selection = selectModelForTask('general', modelId.includes('opus') ? 'critical' : 'medium');
        const knobsStr = Object.entries(selection.knobs)
          .filter(([, v]) => v !== undefined)
          .slice(0, 3)
          .map(([k, v]) => `${k}=${v}`)
          .join(', ');

        console.log(`| ${modelId.substring(0, 20).padEnd(20)} | ${profile.nickname.padEnd(6)} | $${profile.costInput}/${profile.costOutput} | ${selection.role.padEnd(10)} | ${knobsStr} |`);
      }
      break;
    }

    default:
      console.log(`
🎯 Model-Persona Matrix - 多模型多人格矩阵

用法:
  bun model-persona-matrix.ts models    # 列出所有模型
  bun model-persona-matrix.ts brain     # 显示双主脑架构
  bun model-persona-matrix.ts experts   # 显示专家组
  bun model-persona-matrix.ts workers   # 显示工人组
  bun model-persona-matrix.ts teams     # 显示编队模板
  bun model-persona-matrix.ts select <taskType> <complexity>  # 选择模型
  bun model-persona-matrix.ts matrix    # 显示完整矩阵

架构:
  双主脑: 战略家(claude-opus) + 治理官(gemini-2.5-pro)
  专家组: 6人 (强约束)
  工人组: 3人 (弱约束)
  成本级: P1-P5 五档
`);
  }
}

export default {
  MODEL_PROFILES,
  DUAL_MAIN_BRAIN,
  EXPERT_GROUP,
  WORKER_GROUP,
  TEAM_TEMPLATES,
  COST_TIERS,
  selectModelForTask,
  selectTeam
};
