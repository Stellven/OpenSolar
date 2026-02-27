#!/usr/bin/env bun
/**
 * Plan-and-Act 类型定义
 *
 * @version 1.0.0
 * @created 2026-02-27
 */

// ============ 核心类型 ============

/**
 * 计划步骤
 */
export interface PlanStep {
  id: string;
  action: string;              // 动作描述
  agent?: string;              // 指定执行的 Agent
  dependencies: string[];      // 依赖的步骤 ID
  status: PlanStepStatus;
  retryCount: number;
  maxRetries: number;
  result?: unknown;
  error?: string;
  startedAt?: number;
  completedAt?: number;
}

export type PlanStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

/**
 * 执行计划
 */
export interface Plan {
  id: string;
  goal: string;                // 总体目标
  steps: PlanStep[];
  createdAt: number;
  updatedAt: number;
  currentStepIndex: number;
  constraints: string[];       // 约束条件
  metadata?: Record<string, unknown>;
}

/**
 * 计划上下文（存储在 SMA L2）
 */
export interface PlanContext {
  currentPlanId: string;
  activeSteps: string[];       // 当前活跃的步骤 ID
  completedSteps: string[];    // 已完成的步骤 ID
  failedSteps: string[];       // 失败的步骤 ID
  lastReplanReason?: string;   // 上次重规划原因
  replanCount: number;         // 重规划次数
  sessionId: string;
  updatedAt: number;
}

// ============ 触发器类型 ============

/**
 * 重规划触发器
 */
export interface ReplanTrigger {
  type: ReplanTriggerType;
  threshold: number;
  current: number;
}

export type ReplanTriggerType =
  | 'consecutive_failures'   // 连续失败
  | 'constraint_violation'   // 约束违反
  | 'timeout'                // 执行超时
  | 'manual';                // 手动触发

/**
 * 执行历史记录
 */
export interface ExecutionHistory {
  planId: string;
  steps: ExecutionStep[];
  totalDuration: number;
  successRate: number;
}

export interface ExecutionStep {
  stepId: string;
  agent: string;
  status: PlanStepStatus;
  startedAt: number;
  completedAt?: number;
  duration?: number;
  error?: string;
  constraintChecks?: ConstraintCheckResult[];
}

// ============ Agent 相关 ============

/**
 * 执行结果
 */
export interface ExecutionResult {
  success: boolean;
  output: unknown;
  error?: string;
  duration: number;
  constraintsChecked: ConstraintCheckResult[];
  stepId: string;
}

/**
 * 约束检查结果
 */
export interface ConstraintCheckResult {
  constraint: string;
  passed: boolean;
  reason?: string;
}

/**
 * Agent 调用参数
 */
export interface AgentCallParams {
  agent: string;
  task: string;
  constraints: string[];
  planContext: {
    currentStep: string;
    completedSteps: string[];
  };
  metadata?: Record<string, unknown>;
}

// ============ 分发规则 ============

/**
 * Agent 分发规则
 */
export interface DispatchRule {
  pattern: RegExp;
  agent: string;
  model?: string;             // 推荐使用的模型
  priority?: number;          // 优先级（高优先）
}

/**
 * 默认分发规则
 */
export const DISPATCH_RULES: DispatchRule[] = [
  // P0: 精确匹配 @Agent 语法
  { pattern: /@Researcher/, agent: 'Researcher', model: 'deepseek-r1', priority: 100 },
  { pattern: /@Architect/, agent: 'Architect', model: 'gemini-2.5-pro', priority: 100 },
  { pattern: /@Coder/, agent: 'Coder', model: 'glm-5', priority: 100 },
  { pattern: /@Tester/, agent: 'Tester', model: 'glm-5', priority: 100 },
  { pattern: /@Ops/, agent: 'Ops', model: 'glm-5', priority: 100 },
  { pattern: /@Reviewer/, agent: 'Reviewer', model: 'gemini-2.5-pro', priority: 100 },
  { pattern: /@Docs/, agent: 'Docs', model: 'glm-5', priority: 100 },
  { pattern: /@PM/, agent: 'PM', model: 'gemini-2.5-pro', priority: 100 },
  { pattern: /@Guard/, agent: 'Guard', model: 'gemini-2.5-pro', priority: 100 },
  { pattern: /@Secretary/, agent: 'Secretary', model: 'glm-4-flash', priority: 100 },

  // P1: 语义匹配 - Researcher (分析优先)
  { pattern: /分析|调研|研究|可行性|评估|诊断/, agent: 'Researcher', model: 'deepseek-r1', priority: 50 },

  // P1: 语义匹配 - Architect (设计优先)
  { pattern: /架构|设计|技术选型|系统设计|方案|规划/, agent: 'Architect', model: 'gemini-2.5-pro', priority: 50 },

  // P1: 语义匹配 - Coder (实现优先)
  { pattern: /实现|编码|开发|写代码|修复|bug|重构|优化/, agent: 'Coder', model: 'glm-5', priority: 50 },

  // P1: 语义匹配 - Tester
  { pattern: /测试|验证|单元测试|集成测试/, agent: 'Tester', model: 'glm-5', priority: 50 },

  // P1: 语义匹配 - Ops
  { pattern: /部署|发布|CI\/CD|Docker|容器/, agent: 'Ops', model: 'glm-5', priority: 50 },

  // P1: 语义匹配 - Reviewer
  { pattern: /审查|Code Review|安全检查|检查|确认/, agent: 'Reviewer', model: 'gemini-2.5-pro', priority: 50 },

  // P1: 语义匹配 - PM (项目管理，不包含需求分析)
  { pattern: /项目管理|里程碑|进度/, agent: 'PM', model: 'gemini-2.5-pro', priority: 50 },

  // P1: 语义匹配 - Docs
  { pattern: /文档|README|API文档/, agent: 'Docs', model: 'glm-5', priority: 50 },

  // P2: 通用匹配
  { pattern: /需求/, agent: 'PM', model: 'gemini-2.5-pro', priority: 20 },
];

// ============ 常量 ============

/**
 * 默认配置
 */
export const PLAN_ACT_CONFIG = {
  // 重规划触发阈值
  replanTriggers: {
    consecutiveFailures: 2,    // 连续失败次数
    constraintViolation: 1,    // 约束违反次数
    timeoutMs: 60000,          // 超时时间 (60s)
    maxReplanCount: 2,         // 最大重规划次数
  },

  // 重试配置
  retry: {
    maxRetries: 3,             // 最大重试次数
    backoffMs: 1000,           // 退避时间
    backoffMultiplier: 2,      // 退避倍数
  },

  // 性能目标
  performance: {
    planDispatchMs: 50,        // 计划分发延迟
    stateAccessMs: 20,         // 状态存取延迟
    replanTriggerMs: 10,       // 重规划触发延迟
    totalOverheadMs: 70,       // 总体框架开销
  },

  // 成功率目标
  successRate: {
    target: 0.85,              // 目标成功率
    min: 0.70,                 // 最低可接受成功率
  },
};

// ============ 工具函数类型 ============

/**
 * 计划生成器函数类型
 */
export type PlanGenerator = (goal: string, constraints: string[]) => Promise<Plan>;

/**
 * 步骤执行器函数类型
 */
export type StepExecutor = (step: PlanStep, context: PlanContext) => Promise<ExecutionResult>;

/**
 * 重规划器函数类型
 */
export type Replanner = (plan: Plan, failureAnalysis: ExecutionHistory) => Promise<Plan>;
