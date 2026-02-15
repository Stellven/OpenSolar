/**
 * Task Router v1.0 - 任务-旋钮路由
 *
 * 根据任务类型自动选择旋钮组合
 *
 * 来源: 用户洞察 - 人格对不同workload的影响地图
 */

import { ControlKnobs, ROLES_V3 } from './persona-router';

// ============================================================
// 任务类型定义
// ============================================================

export type TaskType =
  | 'deep_research'      // 学术研究/深度分析
  | 'architecture'       // 系统架构设计
  | 'code_design'        // 代码设计(接口/模块/协议)
  | 'implementation'     // 开发实现/修bug/性能优化
  | 'life_work'          // 工作生活(沟通/安排/总结)
  | 'creative'           // 创意/头脑风暴
  | 'review';            // 代码审查/风险评估

// ============================================================
// 任务类型 → 推荐旋钮组合
// ============================================================

export const TASK_KNOB_PRESETS: Record<TaskType, {
  knobs: Partial<ControlKnobs>;
  reason: string;
  risks: string[];
}> = {
  deep_research: {
    knobs: {
      rigor: 5,
      skepticism: 5,
      selfCritique: 5,
      exploration: 3,
      toolFirst: 4,
      riskAversion: 3
    },
    reason: '学术研究需要高证据洁癖、强怀疑、深度自检',
    risks: [
      'Persona过强会引入立场偏见',
      '身份一致性推理(motivated reasoning)导致选择性推理',
      '可能陷入"为找证据而找证据"'
    ]
  },

  architecture: {
    knobs: {
      rigor: 4,
      decisiveness: 4,
      exploration: 4,
      riskAversion: 3,
      selfCritique: 4,
      toolFirst: 2
    },
    reason: '架构设计需要高层抽象、权衡取舍、可落地',
    risks: [
      '过度发散导致不可执行',
      '过度保守导致缺乏创新',
      '忽视边界条件'
    ]
  },

  code_design: {
    knobs: {
      rigor: 5,
      toolFirst: 5,
      selfCritique: 5,
      compression: 3,
      decisiveness: 3,
      riskAversion: 3
    },
    reason: '代码设计需要规范、可实现、可测试',
    risks: [
      '很会说但不可编译',
      '缺少测试/约束',
      '接口设计过于复杂'
    ]
  },

  implementation: {
    knobs: {
      toolFirst: 5,
      decisiveness: 4,
      selfCritique: 4,
      riskAversion: 4,
      rigor: 3,
      exploration: 2
    },
    reason: '开发实现需要速度、可复现、回归安全',
    risks: [
      '过度自信直接改核心代码',
      '无最小复现就动手',
      '缺少回滚方案'
    ]
  },

  life_work: {
    knobs: {
      socialEmpathy: 5,
      compression: 4,
      decisiveness: 4,
      exploration: 2,
      skepticism: 1,
      rigor: 2
    },
    reason: '工作生活需要清晰、同理心、可执行',
    risks: [
      '过度学术化/太长',
      '忽略用户偏好',
      '缺少温度'
    ]
  },

  creative: {
    knobs: {
      exploration: 5,
      decisiveness: 2,
      riskAversion: 1,
      skepticism: 1,
      rigor: 2,
      socialEmpathy: 3
    },
    reason: '创意任务需要发散、低约束',
    risks: [
      '想法太散难以收敛',
      '缺乏可行性验证',
      '可能过于天马行空'
    ]
  },

  review: {
    knobs: {
      skepticism: 5,
      rigor: 5,
      riskAversion: 5,
      selfCritique: 4,
      toolFirst: 4,
      decisiveness: 3
    },
    reason: '审查任务需要极度怀疑、全面检查',
    risks: [
      '过于严苛打击积极性',
      '只找问题不给建议',
      '忽视上下文约束'
    ]
  }
};

// ============================================================
// 任务类型 → 推荐角色
// ============================================================

export const TASK_ROLES: Record<TaskType, {
  primary: string;
  secondary?: string;
  neutral?: boolean;  // 是否需要 neutral 对冲
}> = {
  deep_research: {
    primary: 'critic',
    secondary: 'synthesizer',
    neutral: true
  },
  architecture: {
    primary: 'architect',
    secondary: 'riskOfficer',
    neutral: true
  },
  code_design: {
    primary: 'spec',
    secondary: 'verifier',
    neutral: false
  },
  implementation: {
    primary: 'builder',
    secondary: 'verifier',
    neutral: false
  },
  life_work: {
    primary: 'concierge',
    neutral: false
  },
  creative: {
    primary: 'explorer',
    secondary: 'architect',
    neutral: false
  },
  review: {
    primary: 'verifier',
    secondary: 'critic',
    neutral: true
  }
};

// ============================================================
// 路由函数
// ============================================================

export interface TaskRoutingResult {
  taskType: TaskType;
  knobs: Partial<ControlKnobs>;
  primaryRole: string;
  secondaryRole?: string;
  needsNeutral: boolean;
  reason: string;
  risks: string[];
}

/**
 * 根据任务描述自动判断类型
 */
export function detectTaskType(description: string): TaskType {
  const lower = description.toLowerCase();

  // 学术研究
  if (/研究|论文|调查|分析|综述|文献|学术/.test(description)) {
    return 'deep_research';
  }

  // 架构设计
  if (/架构|设计|方案|规划|系统|平台|框架/.test(description)) {
    return 'architecture';
  }

  // 代码设计
  if (/接口|协议|模块|api|sdk|规范|spec/.test(lower)) {
    return 'code_design';
  }

  // 开发实现
  if (/实现|开发|编码|bug|修复|优化|性能|功能/.test(description)) {
    return 'implementation';
  }

  // 审查
  if (/审查|review|评估|风险|审计|检查/.test(description)) {
    return 'review';
  }

  // 创意
  if (/创意|头脑风暴|想法|brainstorm|探索/.test(lower)) {
    return 'creative';
  }

  // 默认工作生活
  return 'life_work';
}

/**
 * 获取任务路由配置
 */
export function routeTask(taskType: TaskType): TaskRoutingResult;
export function routeTask(description: string): TaskRoutingResult;
export function routeTask(input: TaskType | string): TaskRoutingResult {
  const taskType: TaskType = typeof input === 'string'
    ? (Object.keys(TASK_KNOB_PRESETS).includes(input) ? input as TaskType : detectTaskType(input))
    : input;

  const preset = TASK_KNOB_PRESETS[taskType];
  const roles = TASK_ROLES[taskType];

  return {
    taskType,
    knobs: preset.knobs,
    primaryRole: roles.primary,
    secondaryRole: roles.secondary,
    needsNeutral: roles.neutral || false,
    reason: preset.reason,
    risks: preset.risks
  };
}

/**
 * 生成任务路由 prompt
 */
export function buildTaskPrompt(taskType: TaskType, task: string): string {
  const routing = routeTask(taskType);
  const roleConfig = ROLES_V3[routing.primaryRole];

  if (!roleConfig) {
    return `任务: ${task}`;
  }

  const lines: string[] = [];

  lines.push(`【${routing.primaryRole}】`);
  lines.push(`任务类型: ${taskType}`);
  lines.push(`风格: ${roleConfig.style.tone}`);
  lines.push('');

  // 旋钮覆盖
  lines.push('控制面:');
  for (const [key, value] of Object.entries(routing.knobs)) {
    const knobName = getKnobDisplayName(key as keyof ControlKnobs);
    lines.push(`  ${knobName}: ${value}`);
  }
  lines.push('');

  // 风险提示
  if (routing.risks.length > 0) {
    lines.push('⚠️ 风险提示:');
    routing.risks.forEach(r => lines.push(`  - ${r}`));
    lines.push('');
  }

  // 任务
  lines.push('任务:');
  lines.push(task);

  return lines.join('\n');
}

function getKnobDisplayName(key: keyof ControlKnobs): string {
  const names: Record<keyof ControlKnobs, string> = {
    rigor: '证据洁癖',
    skepticism: '怀疑强度',
    exploration: '发散度',
    decisiveness: '决断性',
    riskAversion: '风险厌恶',
    toolFirst: '工具倾向',
    compression: '压缩率',
    selfCritique: '自检强度',
    socialEmpathy: '同理心',
    competitiveness: '竞技性'
  };
  return names[key] || key;
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'detect': {
      const desc = process.argv.slice(3).join(' ');
      if (!desc) {
        console.log('用法: bun task-router.ts detect <任务描述>');
        break;
      }
      const taskType = detectTaskType(desc);
      console.log(`\n🔍 检测结果: ${taskType}\n`);
      break;
    }

    case 'route': {
      const input = process.argv[3];
      if (!input) {
        console.log('用法: bun task-router.ts route <任务类型|描述>');
        break;
      }
      const result = routeTask(input);
      console.log(`\n📋 任务路由结果:\n`);
      console.log(`  类型: ${result.taskType}`);
      console.log(`  主角色: ${result.primaryRole}`);
      console.log(`  副角色: ${result.secondaryRole || '无'}`);
      console.log(`  需要neutral: ${result.needsNeutral ? '是' : '否'}`);
      console.log(`  原因: ${result.reason}`);
      console.log(`\n  旋钮配置:`);
      for (const [k, v] of Object.entries(result.knobs)) {
        console.log(`    ${k}: ${v}`);
      }
      console.log(`\n  ⚠️ 风险:`);
      result.risks.forEach(r => console.log(`    - ${r}`));
      break;
    }

    case 'list': {
      console.log('\n📋 任务类型预设:\n');
      for (const [type, preset] of Object.entries(TASK_KNOB_PRESETS)) {
        const roles = TASK_ROLES[type as TaskType];
        console.log(`【${type}】`);
        console.log(`  角色: ${roles.primary}${roles.secondary ? ' + ' + roles.secondary : ''}`);
        console.log(`  neutral: ${roles.neutral ? '需要' : '不需要'}`);
        console.log(`  旋钮: ${Object.entries(preset.knobs).map(([k, v]) => `${k}=${v}`).join(', ')}`);
        console.log(`  风险: ${preset.risks.length}条`);
        console.log('');
      }
      break;
    }

    case 'prompt': {
      const taskType = process.argv[3] as TaskType;
      const task = process.argv.slice(4).join(' ') || '示例任务';
      if (!Object.keys(TASK_KNOB_PRESETS).includes(taskType)) {
        console.log('用法: bun task-router.ts prompt <taskType> <任务>');
        console.log(`可用类型: ${Object.keys(TASK_KNOB_PRESETS).join(', ')}`);
        break;
      }
      console.log(buildTaskPrompt(taskType, task));
      break;
    }

    default:
      console.log(`
🎯 Task Router - 任务-旋钮路由

用法:
  bun task-router.ts detect <描述>     # 自动检测任务类型
  bun task-router.ts route <类型|描述>  # 获取路由配置
  bun task-router.ts list              # 列出所有预设
  bun task-router.ts prompt <类型> <任务>  # 生成任务prompt

任务类型:
  deep_research   - 学术研究/深度分析
  architecture    - 系统架构设计
  code_design     - 代码设计(接口/模块/协议)
  implementation  - 开发实现/修bug/性能优化
  life_work       - 工作生活(沟通/安排/总结)
  creative        - 创意/头脑风暴
  review          - 代码审查/风险评估

关键提醒:
  • Persona在主观/社交任务上更可能收益
  • 在客观推理/零样本上可能拉胯
  • 高风险任务需要 neutral 对冲
`);
  }
}

export default { detectTaskType, routeTask, buildTaskPrompt, TASK_KNOB_PRESETS, TASK_ROLES };
