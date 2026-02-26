/**
 * Solar Abilities System
 *
 * 对偶理念的技术实现：
 * - LLM 只声明需要什么能力（Abilities）
 * - Registry 负责匹配具体实现（Skills）
 * - LLM 不感知物理世界的工具细节
 */

export * from './types';
export * from './registry';
export * from './builtin-skills';

import { AbilitiesRegistry } from './registry';
import { registerBuiltinSkills } from './builtin-skills';

/**
 * 创建配置好的 Abilities Registry
 */
export function createAbilitiesRegistry(context?: import('./types').SkillContext): AbilitiesRegistry {
  const registry = new AbilitiesRegistry(context);
  registerBuiltinSkills(registry);
  return registry;
}
