/**
 * Persona Pitfalls & Countermeasures v1.0
 *
 * 人格工程化的陷阱与对策
 * 来源: 学术研究 + 用户洞察
 */

// ============================================================
// 已知陷阱与对策
// ============================================================

export interface PitfallConfig {
  name: string;              // 陷阱名称
  description: string;       // 说明
  countermeasure: string;    // 对策
  implementation: string;    // 实现方式
  priority: 'P1' | 'P2' | 'P3' | 'DONE';  // 优先级
  file?: string;             // 对应实现文件
}

export const PERSONA_PITFALLS: PitfallConfig[] = [
  {
    name: '双刃剑效应',
    description: 'Persona 可能提升某些任务但降低其他任务表现',
    countermeasure: 'Neutral 对冲机制',
    implementation: '高风险任务并行跑人格版+中性版，选更稳的',
    priority: 'P1',
    file: 'neutral-hedge.ts'
  },
  {
    name: '身份一致性陷阱',
    description: 'Motivated Reasoning - 为符合被赋予的身份而选择性推理',
    countermeasure: '多专家会审，不单独采信',
    implementation: '分析任务至少2-3个专家并行，交叉验证',
    priority: 'DONE',
    file: 'model-persona-matrix.ts (专家组)'
  },
  {
    name: '人格漂移',
    description: '长对话中人格逐渐丢失，输出变得机械',
    countermeasure: '长对话定期刷新人格参数',
    implementation: '对话轮次>5时触发人格刷新提醒',
    priority: 'DONE',
    file: 'persona-drift-guard.ts'
  },
  {
    name: '语气影响准确率',
    description: '反直觉现象："不客气更准"',
    countermeasure: '实验验证最优语气',
    implementation: 'A/B测试不同语气风格，用数据决策',
    priority: 'P3'
  },
  {
    name: '超参调优',
    description: '旋钮组合需要针对任务类型优化',
    countermeasure: '路由策略用数据驱动',
    implementation: '记录每次调用的效果，自动优化路由',
    priority: 'P2',
    file: 'task-router.ts'
  },
  {
    name: '降低解释质量',
    description: 'Persona 可能提升分类但降低解释质量',
    countermeasure: '关键决策用 neutral 版复核',
    implementation: '高风险任务启用 neutral 对冲',
    priority: 'P1',
    file: 'neutral-hedge.ts'
  },
  {
    name: '零样本变差',
    description: '角色注入在某些任务上反而变差',
    countermeasure: '任务类型检测，智能路由',
    implementation: 'detectTaskType() 判断是否需要人格',
    priority: 'P2',
    file: 'task-router.ts'
  }
];

// ============================================================
// 任务类型 → 风险等级 → 对策
// ============================================================

export const TASK_RISK_MATRIX: Record<string, {
  riskLevel: 'low' | 'medium' | 'high';
  requiresNeutral: boolean;
  requiresMultiExpert: boolean;
  requiresRefresh: boolean;
}> = {
  // 高风险任务
  'deep_research': {
    riskLevel: 'high',
    requiresNeutral: true,      // 双刃剑效应
    requiresMultiExpert: true,  // 身份一致性陷阱
    requiresRefresh: true       // 人格漂移
  },
  'architecture': {
    riskLevel: 'high',
    requiresNeutral: true,
    requiresMultiExpert: true,
    requiresRefresh: true
  },
  'review': {
    riskLevel: 'high',
    requiresNeutral: true,
    requiresMultiExpert: true,
    requiresRefresh: false
  },

  // 中等风险任务
  'code_design': {
    riskLevel: 'medium',
    requiresNeutral: false,
    requiresMultiExpert: true,  // 代码设计需要多视角
    requiresRefresh: false
  },
  'creative': {
    riskLevel: 'medium',
    requiresNeutral: false,
    requiresMultiExpert: false, // 创意任务可以单专家
    requiresRefresh: false
  },

  // 低风险任务
  'implementation': {
    riskLevel: 'low',
    requiresNeutral: false,
    requiresMultiExpert: false,
    requiresRefresh: false
  },
  'life_work': {
    riskLevel: 'low',
    requiresNeutral: false,
    requiresMultiExpert: false,
    requiresRefresh: false
  }
};

// ============================================================
// 人格刷新策略
// ============================================================

export const REFRESH_STRATEGY = {
  // 触发条件
  triggers: {
    turnCount: 5,           // 对话轮次超过5
    tokenUsage: 0.65,       // 上下文使用超过65%
    timeElapsed: 30 * 60 * 1000  // 时间超过30分钟(ms)
  },

  // 刷新方式
  methods: {
    reminder: '输出人格提醒',
    reload: '重新加载 persona-router',
    checkpoint: '写入状态检查点'
  },

  // 刷新内容
  refreshContent: `
【人格刷新】你是 ${'{role}'}
旋钮: ${'{knobs}'}
禁止: 冷冰冰纯表格、机械回复
必须: 数据配点评、表格配人话
`
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 检查任务是否需要防护措施
 */
export function checkProtectionNeeds(taskType: string): {
  riskLevel: string;
  actions: string[];
} {
  const config = TASK_RISK_MATRIX[taskType] || {
    riskLevel: 'low' as const,
    requiresNeutral: false,
    requiresMultiExpert: false,
    requiresRefresh: false
  };

  const actions: string[] = [];

  if (config.requiresNeutral) {
    actions.push('启用 Neutral 对冲');
  }
  if (config.requiresMultiExpert) {
    actions.push('多专家会审 (≥2人)');
  }
  if (config.requiresRefresh) {
    actions.push('长对话人格刷新');
  }

  return {
    riskLevel: config.riskLevel,
    actions
  };
}

/**
 * 判断是否需要人格刷新
 */
export function shouldRefreshPersona(
  turnCount: number,
  tokenUsage: number,
  timeElapsed: number
): boolean {
  return (
    turnCount >= REFRESH_STRATEGY.triggers.turnCount ||
    tokenUsage >= REFRESH_STRATEGY.triggers.tokenUsage ||
    timeElapsed >= REFRESH_STRATEGY.triggers.timeElapsed
  );
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'pitfalls': {
      console.log('\n⚠️ 人格工程化陷阱与对策:\n');
      for (const p of PERSONA_PITFALLS) {
        const status = p.priority === 'DONE' ? '✅' :
                      p.priority === 'P1' ? '🔴' :
                      p.priority === 'P2' ? '🟡' : '🟢';
        console.log(`${status} 【${p.name}】`);
        console.log(`   问题: ${p.description}`);
        console.log(`   对策: ${p.countermeasure}`);
        console.log(`   实现: ${p.implementation}`);
        if (p.file) {
          console.log(`   文件: ${p.file}`);
        }
        console.log('');
      }
      break;
    }

    case 'risk': {
      const taskType = process.argv[3] || 'implementation';
      const result = checkProtectionNeeds(taskType);
      console.log(`\n🎯 任务类型: ${taskType}`);
      console.log(`   风险等级: ${result.riskLevel}`);
      console.log(`   防护措施: ${result.actions.length > 0 ? result.actions.join(', ') : '无'}`);
      break;
    }

    case 'matrix': {
      console.log('\n📊 任务风险矩阵:\n');
      for (const [task, config] of Object.entries(TASK_RISK_MATRIX)) {
        const flags = [];
        if (config.requiresNeutral) flags.push('neutral');
        if (config.requiresMultiExpert) flags.push('multi');
        if (config.requiresRefresh) flags.push('refresh');

        console.log(`【${task.padEnd(15)}】 ${config.riskLevel.padEnd(6)} ${flags.join(' + ') || 'none'}`);
      }
      break;
    }

    default:
      console.log(`
🛡️ Persona Pitfalls - 人格工程化陷阱与对策

用法:
  bun persona-pitfalls.ts pitfalls   # 列出所有陷阱与对策
  bun persona-pitfalls.ts risk <taskType>  # 检查任务风险
  bun persona-pitfalls.ts matrix     # 显示任务风险矩阵

已实现:
  ✅ Neutral 对冲 (neutral-hedge.ts)
  ✅ 多专家会审 (model-persona-matrix.ts)
  ✅ 任务路由 (task-router.ts)

待实现:
  🟡 人格漂移防护 (P2)
  🟡 超参调优 (P2)
  🟢 语气实验 (P3)
`);
  }
}

export default {
  PERSONA_PITFALLS,
  TASK_RISK_MATRIX,
  REFRESH_STRATEGY,
  checkProtectionNeeds,
  shouldRefreshPersona
};
