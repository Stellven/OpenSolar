/**
 * Solar Effect System - Abilities Types
 *
 * 核心理念：
 * - Abilities = 抽象能力需求（LLM 可见）
 * - Skills = 具体实现（LLM 不可见）
 * - LLM 只声明 Ability，System Wrapper 匹配 Skill
 *
 * 这是"对偶"理念的技术实现：
 * - LLM 不感知物理世界的具体工具
 * - 工具适配 LLM，不是 LLM 适配工具
 */

// ============================================
// Ability: 抽象能力需求 (LLM 可见)
// ============================================

export type AbilityCategory = 'need' | 'perform';

export interface AbilityParameter {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array' | 'any';
  description?: string;
  enum?: string[];
  optional?: boolean;
  default?: any;
}

export interface Ability {
  /** 能力 ID，如 "search", "store", "notify" */
  id: string;

  /** 分类：need (只读) | perform (写) */
  category: AbilityCategory;

  /** 简短描述（给 LLM 看的） */
  description: string;

  /** 参数定义（简化版 JSON Schema） */
  parameters: Record<string, AbilityParameter>;

  /** 约束条件 */
  constraints?: string[];

  /** 示例用法 */
  examples?: string[];
}

// ============================================
// Skill: 具体实现 (LLM 不可见)
// ============================================

export interface SkillCondition {
  /** 条件类型 */
  type: 'env' | 'context' | 'preference' | 'availability';

  /** 条件表达式 */
  expression: string;
}

export interface Skill {
  /** 技能 ID */
  id: string;

  /** 实现的 Ability ID */
  implements: string;

  /** 处理器 */
  handler: SkillHandler;

  /** 优先级 (0-1，越高越优先) */
  priority: number;

  /** 可用条件 */
  conditions?: SkillCondition[];

  /** 成本估算 (相对值) */
  cost?: number;

  /** 平均延迟 (ms) */
  avgLatency?: number;

  /** 描述 (内部使用) */
  description?: string;
}

// ============================================
// Skill Handler
// ============================================

export interface SkillContext {
  /** 当前会话 ID */
  sessionId?: string;

  /** 用户 ID */
  userId?: string;

  /** 环境变量 */
  env?: Record<string, string>;

  /** 偏好设置 */
  preferences?: Record<string, any>;
}

export interface SkillResult {
  success: boolean;
  data?: any;
  error?: string;
  duration: number;
}

export type SkillHandler = (
  payload: Record<string, any>,
  context: SkillContext
) => Promise<SkillResult>;

// ============================================
// Ability Request (LLM 发出的请求)
// ============================================

export interface AbilityRequest {
  /** 请求的 Ability ID */
  ability: string;

  /** 参数 */
  payload: Record<string, any>;

  /** 元数据 */
  meta?: {
    why?: string;
    timeout?: number;
    fallback?: string;
  };
}

// ============================================
// Match Result
// ============================================

export interface SkillMatch {
  skill: Skill;
  score: number;
  reasons: string[];
}

// ============================================
// Built-in Abilities
// ============================================

export const BUILTIN_ABILITIES: Ability[] = [
  // ========== Need Abilities (只读) ==========
  {
    id: 'search',
    category: 'need',
    description: '搜索信息',
    parameters: {
      query: { type: 'string', description: '搜索关键词' },
      scope: {
        type: 'string',
        enum: ['memory', 'knowledge', 'web', 'all'],
        optional: true,
        default: 'all'
      },
      limit: { type: 'number', optional: true, default: 10 }
    },
    examples: [
      'search({ query: "AI Agent 记忆" })',
      'search({ query: "上次决策", scope: "memory" })'
    ]
  },
  {
    id: 'recall',
    category: 'need',
    description: '回忆特定记忆',
    parameters: {
      key: { type: 'string', description: '记忆键' },
      namespace: { type: 'string', optional: true }
    }
  },
  {
    id: 'know',
    category: 'need',
    description: '获取知识',
    parameters: {
      topic: { type: 'string', description: '知识主题' },
      depth: { type: 'string', enum: ['brief', 'detailed'], optional: true }
    }
  },
  {
    id: 'check',
    category: 'need',
    description: '检查状态/条件',
    parameters: {
      target: { type: 'string', description: '检查目标' },
      criteria: { type: 'object', optional: true }
    }
  },

  // ========== Perform Abilities (写) ==========
  {
    id: 'store',
    category: 'perform',
    description: '持久化存储',
    parameters: {
      key: { type: 'string', description: '存储键' },
      value: { type: 'any', description: '存储值' },
      namespace: { type: 'string', optional: true, default: 'general' },
      ttl: { type: 'number', optional: true, description: '过期时间(秒)' }
    },
    examples: [
      'store({ key: "last_decision", value: decision })',
      'store({ key: "temp", value: data, ttl: 3600 })'
    ]
  },
  {
    id: 'write',
    category: 'perform',
    description: '写入文件',
    parameters: {
      path: { type: 'string', description: '文件路径' },
      content: { type: 'string', description: '文件内容' },
      mode: { type: 'string', enum: ['create', 'overwrite', 'append'], optional: true }
    }
  },
  {
    id: 'notify',
    category: 'perform',
    description: '通知用户',
    parameters: {
      message: { type: 'string', description: '通知内容' },
      channel: {
        type: 'string',
        enum: ['default', 'email', 'imessage', 'slack', 'sms'],
        optional: true
      },
      priority: { type: 'string', enum: ['low', 'normal', 'high'], optional: true }
    }
  },
  {
    id: 'delegate',
    category: 'perform',
    description: '委派任务给其他 Agent',
    parameters: {
      task: { type: 'string', description: '任务描述' },
      agent: { type: 'string', description: '目标 Agent', optional: true },
      context: { type: 'object', optional: true }
    }
  },
  {
    id: 'query',
    category: 'perform',
    description: '执行查询',
    parameters: {
      type: { type: 'string', enum: ['sql', 'grep', 'api'] },
      expression: { type: 'string', description: '查询表达式' },
      params: { type: 'array', optional: true }
    }
  }
];
