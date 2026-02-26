/**
 * Solar Effect System - Runtime
 *
 * POC: Effect 执行引擎
 *
 * 职责:
 * 1. 执行 Generator 产生的 Effect
 * 2. 路由到对应的 Handler
 * 3. 记录执行日志（审计/回放）
 * 4. 支持 Saga 补偿
 */

import type { Effect, EffectResult, AgentFunction, SagaStep, SagaContext, EffectMeta, NeedEffectType, PerformEffectType } from './types';

// ============================================
// Effect Handler Interface
// ============================================

export interface EffectHandler<T = any> {
  /** 支持的 Effect 类型 */
  type: string;
  /** 处理函数 */
  handle(effect: Effect<T>): Promise<EffectResult>;
}

// ============================================
// Effect Tracker (审计/回放)
// ============================================

interface EffectLog {
  id: string;
  effect: Effect;
  result: EffectResult | null;
  timestamp: number;
  duration: number;
}

export class EffectTracker {
  private logs: EffectLog[] = [];
  private idCounter = 0;

  record(effect: Effect): string {
    const id = `eff_${++this.idCounter}`;
    this.logs.push({
      id,
      effect,
      result: null,
      timestamp: Date.now(),
      duration: 0
    });
    return id;
  }

  recordResult(id: string, result: EffectResult): void {
    const log = this.logs.find(l => l.id === id);
    if (log) {
      log.result = result;
      log.duration = result.duration;
    }
  }

  getLogs(): EffectLog[] {
    return [...this.logs];
  }

  /**
   * 回放到某个点（用于调试）
   */
  replayUntil(logId: string): EffectLog[] {
    const idx = this.logs.findIndex(l => l.id === logId);
    return idx >= 0 ? this.logs.slice(0, idx + 1) : this.logs;
  }

  /**
   * 导出日志（用于持久化）
   */
  export(): string {
    return JSON.stringify(this.logs, null, 2);
  }
}

// ============================================
// Effect Runtime
// ============================================

export class EffectRuntime {
  private handlers: Map<string, EffectHandler> = new Map();
  private tracker: EffectTracker;
  private sagaContexts: Map<string, SagaContext> = new Map();

  constructor() {
    this.tracker = new EffectTracker();
  }

  /**
   * 注册 Handler
   */
  registerHandler(handler: EffectHandler): void {
    this.handlers.set(handler.type, handler);
  }

  /**
   * 执行单个 Effect
   */
  async execute<T>(effect: Effect<T>): Promise<EffectResult> {
    const startTime = Date.now();

    // 1. 记录 Effect
    const logId = this.tracker.record(effect);

    // 2. 获取 Handler
    const handler = this.handlers.get(effect.type);
    if (!handler) {
      const result: EffectResult = {
        success: false,
        error: `No handler for effect type: ${effect.type}`,
        duration: Date.now() - startTime
      };
      this.tracker.recordResult(logId, result);
      return result;
    }

    // 3. 执行
    try {
      const result = await handler.handle(effect);
      result.duration = Date.now() - startTime;
      this.tracker.recordResult(logId, result);
      return result;
    } catch (error) {
      const result: EffectResult = {
        success: false,
        error: String(error),
        duration: Date.now() - startTime
      };
      this.tracker.recordResult(logId, result);
      return result;
    }
  }

  /**
   * 运行 Agent Generator
   *
   * 这是核心：把 Generator 中的 Effect 一个个取出来执行，
   * 把结果传回给 Generator
   */
  async run<Input, Output>(agent: AgentFunction<Input, Output>, input: Input): Promise<Output> {
    const generator = agent(input);
    let result: any = undefined;
    let current = generator.next();

    while (!current.done) {
      const effect = current.value;
      const effectResult = await this.execute(effect);

      if (!effectResult.success) {
        // Effect 执行失败
        // 可以选择：抛出异常 / 返回默认值 / 尝试补偿
        console.error(`Effect failed: ${effect.type}`, effectResult.error);
        // 继续执行，但传回 undefined
        result = undefined;
      } else {
        result = effectResult.data;
      }

      current = generator.next(result);
    }

    return current.value;
  }

  /**
   * 获取 Tracker（用于审计）
   */
  getTracker(): EffectTracker {
    return this.tracker;
  }

  // ============================================
  // Saga Support
  // ============================================

  /**
   * 开始一个 Saga
   */
  beginSaga(sagaId: string, steps: SagaStep[]): void {
    this.sagaContexts.set(sagaId, {
      sagaId,
      steps,
      completedSteps: [],
      compensationLog: []
    });
  }

  /**
   * 执行 Saga（带补偿）
   */
  async executeSaga(sagaId: string): Promise<EffectResult> {
    const ctx = this.sagaContexts.get(sagaId);
    if (!ctx) {
      return { success: false, error: `Saga not found: ${sagaId}`, duration: 0 };
    }

    try {
      for (const step of ctx.steps) {
        step.status = 'running';
        const result = await this.execute(step.effect);

        if (!result.success) {
          // 失败，开始补偿
          await this.compensate(sagaId);
          return { success: false, error: `Step ${step.stepId} failed, compensated`, duration: 0 };
        }

        step.status = 'completed';
        ctx.completedSteps.push(step.stepId);
      }

      return { success: true, data: ctx.completedSteps, duration: 0 };
    } catch (error) {
      await this.compensate(sagaId);
      return { success: false, error: String(error), duration: 0 };
    }
  }

  /**
   * 补偿 Saga（按逆序执行补偿 Effect）
   */
  private async compensate(sagaId: string): Promise<void> {
    const ctx = this.sagaContexts.get(sagaId);
    if (!ctx) return;

    // 逆序补偿
    const completedSteps = [...ctx.completedSteps].reverse();

    for (const stepId of completedSteps) {
      const step = ctx.steps.find(s => s.stepId === stepId);
      if (step?.compensation) {
        console.log(`[Saga] Compensating step ${stepId}`);
        await this.execute(step.compensation);
        step.status = 'compensated';
        ctx.compensationLog.push(stepId);
      }
    }
  }
}

// ============================================
// Helper Functions
// ============================================

/**
 * 创建 Need Effect
 */
export function need<T>(type: NeedEffectType, payload: T, meta?: EffectMeta): Effect<T> {
  return { type, payload, meta };
}

/**
 * 创建 Perform Effect
 */
export function perform<T>(type: PerformEffectType, payload: T, meta?: EffectMeta): Effect<T> {
  return { type, payload, meta };
}
