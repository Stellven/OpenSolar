/**
 * Solar Effect System - Main Entry
 *
 * 核心架构: Generator + Effect + Handler + Saga
 * 对偶理念: LLM 声明 Ability，系统匹配 Skill
 *
 * 使用方法:
 *
 * 1. 创建 Runtime
 *    const runtime = new EffectRuntime();
 *    registerAllHandlers(runtime);
 *
 * 2. 定义 Agent
 *    function* myAgent(input: string) {
 *      const memory = yield need('need:memory', { query: input });
 *      const decision = analyze(memory);
 *      yield perform('perform:store', { namespace: 'decisions', key: 'last', value: decision });
 *      return decision;
 *    }
 *
 * 3. 运行 Agent
 *    const result = await runtime.run(myAgent, '查询内容');
 *
 * 4. 审计日志
 *    const logs = runtime.getTracker().getLogs();
 *
 * @updated 2026-02-17 - D&D KNOBS 人格格式 + Cortex 集成
 */

export * from './types';
export * from './runtime';
export * from './handlers';

// Abilities 对偶系统
export * from './abilities/index';
export { createAbilitiesRegistry } from './abilities/index';

// Quick Start
import { EffectRuntime } from './runtime';
import { registerAllHandlers } from './handlers';

export function createRuntime(): EffectRuntime {
  const runtime = new EffectRuntime();
  registerAllHandlers(runtime);
  return runtime;
}

// 示例 Agent
import type { Effect } from './types';
import { need, perform } from './runtime';

export function* sampleAgent(input: string): Generator<Effect, string, any> {
  // 1. 获取记忆
  const memory = yield need('need:memory', { query: input, limit: 10 });

  // 2. 获取人格
  const personality = yield need('need:personality', {});

  // 3. 纯决策逻辑
  const decision = `分析 "${input}" 完成`;

  // 4. 存储结果
  yield perform('perform:store', {
    namespace: 'agent_decisions',
    key: `decision_${Date.now()}`,
    value: { input, decision, timestamp: Date.now() }
  });

  return decision;
}
