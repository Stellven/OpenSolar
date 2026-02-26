/**
 * Solar Effect System - Abilities Registry
 *
 * 职责：
 * 1. 管理 Abilities（抽象能力，LLM 可见）
 * 2. 管理 Skills（具体实现，LLM 不可见）
 * 3. 匹配 Ability → 最佳 Skill
 *
 * 这是"对偶"理念的核心：
 * - LLM 只声明需要什么能力
 * - Registry 负责匹配具体实现
 * - LLM 不感知物理世界的工具细节
 */

import type {
  Ability,
  Skill,
  SkillHandler,
  SkillContext,
  SkillResult,
  AbilityRequest,
  SkillMatch
} from './types';
import { BUILTIN_ABILITIES } from './types';

// ============================================
// Abilities Registry
// ============================================

export class AbilitiesRegistry {
  private abilities: Map<string, Ability> = new Map();
  private skills: Map<string, Skill[]> = new Map();
  private context: SkillContext;

  constructor(context?: SkillContext) {
    this.context = context || {};

    // 注册内置 Abilities
    for (const ability of BUILTIN_ABILITIES) {
      this.registerAbility(ability);
    }
  }

  // ============================================
  // Ability Management
  // ============================================

  /**
   * 注册 Ability
   */
  registerAbility(ability: Ability): void {
    this.abilities.set(ability.id, ability);
  }

  /**
   * 获取 Ability
   */
  getAbility(id: string): Ability | undefined {
    return this.abilities.get(id);
  }

  /**
   * 列出所有 Abilities (给 LLM 看的)
   */
  listAbilities(): Ability[] {
    return Array.from(this.abilities.values());
  }

  /**
   * 生成 Abilities Schema (极简版，给 LLM 的)
   */
  generateSchema(): string {
    const lines: string[] = ['# 可用能力 (Abilities)', ''];

    const needs = Array.from(this.abilities.values()).filter(a => a.category === 'need');
    const performs = Array.from(this.abilities.values()).filter(a => a.category === 'perform');

    if (needs.length > 0) {
      lines.push('## Need (只读)');
      for (const ability of needs) {
        const params = Object.entries(ability.parameters)
          .map(([k, v]) => v.optional ? `${k}?` : k)
          .join(', ');
        lines.push(`${ability.id}(${params}) → ${ability.description}`);
      }
      lines.push('');
    }

    if (performs.length > 0) {
      lines.push('## Perform (写)');
      for (const ability of performs) {
        const params = Object.entries(ability.parameters)
          .map(([k, v]) => v.optional ? `${k}?` : k)
          .join(', ');
        lines.push(`${ability.id}(${params}) → ${ability.description}`);
      }
    }

    return lines.join('\n');
  }

  // ============================================
  // Skill Management
  // ============================================

  /**
   * 注册 Skill
   */
  registerSkill(skill: Skill): void {
    const ability = this.abilities.get(skill.implements);
    if (!ability) {
      throw new Error(`Ability not found: ${skill.implements}`);
    }

    if (!this.skills.has(skill.implements)) {
      this.skills.set(skill.implements, []);
    }
    this.skills.get(skill.implements)!.push(skill);

    // 按优先级排序
    this.skills.get(skill.implements)!.sort((a, b) => b.priority - a.priority);
  }

  /**
   * 批量注册 Skills
   */
  registerSkills(skills: Skill[]): void {
    for (const skill of skills) {
      this.registerSkill(skill);
    }
  }

  /**
   * 获取 Ability 的所有 Skills
   */
  getSkills(abilityId: string): Skill[] {
    return this.skills.get(abilityId) || [];
  }

  // ============================================
  // Skill Matching
  // ============================================

  /**
   * 匹配最佳 Skill
   */
  matchSkill(request: AbilityRequest): SkillMatch | null {
    const { ability: abilityId, payload, meta } = request;

    // 1. 检查 Ability 是否存在
    const ability = this.abilities.get(abilityId);
    if (!ability) {
      return null;
    }

    // 2. 获取所有候选 Skills
    const candidates = this.skills.get(abilityId);
    if (!candidates || candidates.length === 0) {
      return null;
    }

    // 3. 评估每个 Skill
    const matches: SkillMatch[] = [];

    for (const skill of candidates) {
      const match = this.evaluateSkill(skill, payload, meta);
      if (match.score > 0) {
        matches.push(match);
      }
    }

    // 4. 返回最佳匹配
    if (matches.length === 0) {
      return null;
    }

    matches.sort((a, b) => b.score - a.score);
    return matches[0];
  }

  /**
   * 评估 Skill 匹配度
   */
  private evaluateSkill(
    skill: Skill,
    payload: Record<string, any>,
    meta?: AbilityRequest['meta']
  ): SkillMatch {
    let score = skill.priority;
    const reasons: string[] = [];

    // 1. 检查条件
    if (skill.conditions) {
      for (const condition of skill.conditions) {
        const passed = this.evaluateCondition(condition, payload);
        if (!passed) {
          return { skill, score: 0, reasons: [`Condition failed: ${condition.expression}`] };
        }
        reasons.push(`Condition passed: ${condition.expression}`);
      }
    }

    // 2. 根据上下文调整分数
    // 例如：如果用户偏好某个渠道
    if (meta?.why) {
      score += 0.1; // 有理由说明的请求优先
    }

    // 3. 成本惩罚
    if (skill.cost) {
      score -= skill.cost * 0.1;
    }

    // 4. 延迟惩罚
    if (skill.avgLatency && skill.avgLatency > 1000) {
      score -= 0.05;
    }

    reasons.push(`Priority: ${skill.priority.toFixed(2)}`);

    return { skill, score: Math.max(0, Math.min(1, score)), reasons };
  }

  /**
   * 评估条件
   */
  private evaluateCondition(
    condition: SkillCondition,
    payload: Record<string, any>
  ): boolean {
    switch (condition.type) {
      case 'env':
        // 环境变量检查
        const envVar = condition.expression;
        return !!this.context.env?.[envVar] || !!process.env[envVar];

      case 'context':
        // 上下文检查
        return this.evaluateExpression(condition.expression, { ...this.context, payload });

      case 'preference':
        // 偏好检查
        return this.evaluateExpression(condition.expression, this.context.preferences || {});

      case 'availability':
        // 可用性检查（简化版）
        return true;

      default:
        return true;
    }
  }

  /**
   * 简单表达式求值
   */
  private evaluateExpression(expression: string, context: Record<string, any>): boolean {
    try {
      // 简化版：只支持简单的属性访问和比较
      // 例如: "channel === 'email'" 或 "env.GEMINI_API_KEY"
      const keys = Object.keys(context);
      let evalExpr = expression;
      for (const key of keys) {
        evalExpr = evalExpr.replace(new RegExp(`\\b${key}\\b`, 'g'), `context.${key}`);
      }
      return eval(evalExpr);
    } catch {
      return false;
    }
  }

  // ============================================
  // Execution
  // ============================================

  /**
   * 执行 Ability 请求
   */
  async execute(request: AbilityRequest): Promise<SkillResult> {
    const startTime = Date.now();

    // 1. 匹配 Skill
    const match = this.matchSkill(request);
    if (!match) {
      return {
        success: false,
        error: `No skill available for ability: ${request.ability}`,
        duration: Date.now() - startTime
      };
    }

    // 2. 执行
    try {
      const result = await match.skill.handler(request.payload, this.context);
      result.duration = Date.now() - startTime;
      return result;
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: Date.now() - startTime
      };
    }
  }

  // ============================================
  // Context Management
  // ============================================

  /**
   * 更新上下文
   */
  updateContext(context: Partial<SkillContext>): void {
    this.context = { ...this.context, ...context };
  }

  /**
   * 获取当前上下文
   */
  getContext(): SkillContext {
    return { ...this.context };
  }

  // ============================================
  // Statistics
  // ============================================

  /**
   * 获取统计信息
   */
  getStats(): {
    abilities: number;
    skills: number;
    byCategory: Record<string, number>;
  } {
    let totalSkills = 0;
    const byCategory: Record<string, number> = {};

    for (const [abilityId, skills] of this.skills) {
      totalSkills += skills.length;
      byCategory[abilityId] = skills.length;
    }

    return {
      abilities: this.abilities.size,
      skills: totalSkills,
      byCategory
    };
  }
}

// ============================================
// Helper Functions
// ============================================

/**
 * 创建 Ability 请求
 */
export function need(ability: string, payload: Record<string, any>, meta?: AbilityRequest['meta']): AbilityRequest {
  return { ability, payload, meta };
}

/**
 * 创建 Perform Ability 请求
 */
export function perform(ability: string, payload: Record<string, any>, meta?: AbilityRequest['meta']): AbilityRequest {
  return { ability, payload, meta };
}
