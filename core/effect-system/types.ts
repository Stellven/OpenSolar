/**
 * Solar Effect System - Types Definition
 *
 * POC: 验证 Generator 模式模拟 Effect 语义
 *
 * 核心理念:
 * - LLM 是纯函数（无状态）
 * - 记忆/人格/工具调用 都是外部 Effect
 * - 通过 yield 声明式表达需求
 */

// ============================================
// Effect Types
// ============================================

/**
 * Need Effects: 只读，获取信息
 */
export type NeedEffectType =
  | 'need:memory'      // 查询记忆
  | 'need:personality' // 加载人格
  | 'need:knowledge'   // 查询知识库
  | 'need:context';    // 获取上下文

/**
 * Perform Effects: 有副作用，产生变更
 */
export type PerformEffectType =
  | 'perform:write'    // 写文件
  | 'perform:store'    // 存记忆
  | 'perform:delegate' // 委派给牛马
  | 'perform:query';   // 执行数据库查询

export type EffectType = NeedEffectType | PerformEffectType;

// ============================================
// Effect Interfaces
// ============================================

/**
 * Effect 元数据
 */
export interface EffectMeta {
  /** 为什么需要这个 Effect */
  why?: string;
  /** 补偿方案（Saga 模式） */
  compensation?: string;
  /** 优先级 */
  priority?: number;
  /** 关联的 step ID（用于 Saga） */
  stepId?: string;
}

/**
 * Effect 基础接口
 */
export interface Effect<T = any> {
  /** Effect 类型 */
  type: EffectType;
  /** 负载数据 */
  payload: T;
  /** 元数据 */
  meta?: EffectMeta;
}

// ============================================
// Specific Effect Payloads
// ============================================

export interface MemoryQueryPayload {
  query: string;
  limit?: number;
  namespace?: string;
}

export interface PersonalityPayload {
  personalityId?: string;
}

export interface KnowledgeQueryPayload {
  query: string;
  limit?: number;
  sources?: string[];
}

export interface ContextPayload {
  includeHistory?: boolean;
  maxTokens?: number;
}

export interface WritePayload {
  path: string;
  content: string;
  mode?: 'create' | 'append' | 'overwrite';
}

export interface StorePayload {
  namespace: string;
  key: string;
  value: any;
  ttl?: number;
}

export interface DelegatePayload {
  model: string;
  task: string;
  context?: string;
  personality?: boolean;
}

export interface QueryPayload {
  sql: string;
  params?: any[];
}

// ============================================
// Typed Effects
// ============================================

export type MemoryEffect = Effect<MemoryQueryPayload>;
export type PersonalityEffect = Effect<PersonalityPayload>;
export type KnowledgeEffect = Effect<KnowledgeQueryPayload>;
export type ContextEffect = Effect<ContextPayload>;
export type WriteEffect = Effect<WritePayload>;
export type StoreEffect = Effect<StorePayload>;
export type DelegateEffect = Effect<DelegatePayload>;
export type QueryEffect = Effect<QueryPayload>;

// ============================================
// Effect Result
// ============================================

export interface EffectResult<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  duration: number;
}

// ============================================
// Agent Protocol
// ============================================

/**
 * Agent 函数类型：接收输入，返回 Effect Generator
 *
 * 示例:
 * function* myAgent(input: string): Generator<Effect, string, any> {
 *   const memory = yield { type: 'need:memory', payload: { query: input } };
 *   const decision = analyze(memory);
 *   yield { type: 'perform:store', payload: { namespace: 'decisions', key: 'last', value: decision } };
 *   return decision;
 * }
 */
export type AgentFunction<Input, Output> = (input: Input) => Generator<Effect, Output, any>;

// ============================================
// Saga Support
// ============================================

export interface SagaStep {
  stepId: string;
  effect: Effect;
  /** 补偿 Effect */
  compensation?: Effect;
  /** 依赖的 stepId */
  dependsOn?: string[];
  status: 'pending' | 'running' | 'completed' | 'compensated' | 'failed';
}

export interface SagaContext {
  sagaId: string;
  steps: SagaStep[];
  completedSteps: string[];
  compensationLog: string[];
}
