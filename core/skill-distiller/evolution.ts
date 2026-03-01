/**
 * Skill Evolution
 * 技能进化模块（P1）
 *
 * 功能：
 * 1. 自动晋升：基于使用统计将 task_specific → general
 * 2. 自动降级：低成功率技能 → deprecated
 * 3. 技能剪枝：长期未使用 → archived
 */

import type { Skill } from './schema';
import { getSkillStats } from './db';
import { Database } from 'bun:sqlite';

// 晋升/降级阈值
const EVOLUTION_CONFIG = {
  // 晋升：通用性得分阈值
  promotion_generality_threshold: 0.5,
  promotion_min_usage: 20,

  // 降级：失败率阈值
  degradation_failure_rate: 0.6,
  degradation_min_attempts: 5,

  // 剪枝：未使用天数
  pruning_inactive_days: 90,
  pruning_min_usage: 0
};

/**
 * 计算技能通用性得分
 * 基于在不同任务类型中的使用分布
 */
export function calculateGeneralityScore(skill: Skill): number {
  // 简化版：基于标签数量和成功率估算
  const tagCount = skill.tags?.length || 0;
  const successRate = skill.success_count / (skill.success_count + skill.failure_count || 1);

  // 标签越多，成功率越高，通用性越强
  const tagScore = Math.min(tagCount / 5, 1);  // 5个标签满分
  const successScore = successRate;

  return (tagScore * 0.4 + successScore * 0.6);
}

/**
 * 检查是否应该晋升
 */
export function shouldPromote(skill: Skill): boolean {
  const totalUsage = skill.success_count + skill.failure_count;
  if (totalUsage < EVOLUTION_CONFIG.promotion_min_usage) {
    return false;
  }

  const generalityScore = calculateGeneralityScore(skill);
  return generalityScore >= EVOLUTION_CONFIG.promotion_generality_threshold;
}

/**
 * 检查是否应该降级
 */
export function shouldDegrade(skill: Skill): boolean {
  const totalUsage = skill.success_count + skill.failure_count;
  if (totalUsage < EVOLUTION_CONFIG.degradation_min_attempts) {
    return false;
  }

  const failureRate = skill.failure_count / totalUsage;
  return failureRate >= EVOLUTION_CONFIG.degradation_failure_rate;
}

/**
 * 检查是否应该归档
 */
export function shouldArchive(skill: Skill): boolean {
  const totalUsage = skill.success_count + skill.failure_count;
  if (totalUsage > EVOLUTION_CONFIG.pruning_min_usage) {
    return false;
  }

  if (!skill.last_used_at) {
    // 从未使用，检查创建时间
    const createdDays = (Date.now() - new Date(skill.created_at).getTime()) / (1000 * 60 * 60 * 24);
    return createdDays > EVOLUTION_CONFIG.pruning_inactive_days;
  }

  const lastUsedDays = (Date.now() - new Date(skill.last_used_at).getTime()) / (1000 * 60 * 60 * 24);
  return lastUsedDays > EVOLUTION_CONFIG.pruning_inactive_days;
}

/**
 * 执行技能进化
 * 扫描所有技能，执行晋升/降级/归档
 */
export async function evolveSkills(): Promise<{
  promoted: string[];
  degraded: string[];
  archived: string[];
}> {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  const results = {
    promoted: [] as string[],
    degraded: [] as string[],
    archived: [] as string[]
  };

  // 获取所有活跃技能
  const skills = db.prepare(`
    SELECT * FROM sys_skill_bank
    WHERE status = 'active'
  `).all() as unknown[];

  for (const row of skills) {
    const skill = parseSkillRow(row as Record<string, unknown>);

    // 检查晋升
    if (skill.scope === 'task_specific' && shouldPromote(skill)) {
      db.run(`
        UPDATE sys_skill_bank
        SET scope = 'general', updated_at = CURRENT_TIMESTAMP
        WHERE skill_id = ?
      `, [skill.skill_id]);
      results.promoted.push(skill.skill_id);
      continue;
    }

    // 检查降级
    if (shouldDegrade(skill)) {
      db.run(`
        UPDATE sys_skill_bank
        SET status = 'deprecated', updated_at = CURRENT_TIMESTAMP
        WHERE skill_id = ?
      `, [skill.skill_id]);
      results.degraded.push(skill.skill_id);
      continue;
    }

    // 检查归档
    if (shouldArchive(skill)) {
      db.run(`
        UPDATE sys_skill_bank
        SET status = 'archived', updated_at = CURRENT_TIMESTAMP
        WHERE skill_id = ?
      `, [skill.skill_id]);
      results.archived.push(skill.skill_id);
    }
  }

  db.close();
  return results;
}

/**
 * 更新技能 Q 值
 * 基于成功/失败历史
 */
export function updateQValue(skillId: string, success: boolean): void {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 获取当前统计
  const skill = db.prepare(`
    SELECT success_count, failure_count, q_value
    FROM sys_skill_bank
    WHERE skill_id = ?
  `).get(skillId) as { success_count: number; failure_count: number; q_value: number };

  if (!skill) {
    db.close();
    return;
  }

  // 计算新 Q 值（使用简单的移动平均）
  const alpha = 0.1;  // 学习率
  const reward = success ? 1 : 0;
  const newQValue = skill.q_value + alpha * (reward - skill.q_value);

  db.run(`
    UPDATE sys_skill_bank
    SET q_value = ?, updated_at = CURRENT_TIMESTAMP
    WHERE skill_id = ?
  `, [newQValue, skillId]);

  db.close();
}

/**
 * 获取进化报告
 */
export function getEvolutionReport(): {
  candidates_for_promotion: { skill_id: string; name: string; score: number }[];
  candidates_for_degradation: { skill_id: string; name: string; failure_rate: number }[];
  candidates_for_archive: { skill_id: string; name: string; last_used: string }[];
} {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 晋升候选 - 高成功率
  const promotionCandidates = db.prepare(`
    SELECT skill_id, name, success_count, failure_count,
           CASE WHEN (success_count + failure_count) > 0
                THEN success_count * 1.0 / (success_count + failure_count)
                ELSE 0 END as success_rate
    FROM sys_skill_bank
    WHERE status = 'active' AND scope = 'task_specific'
    AND (success_count + failure_count) >= 20
    ORDER BY success_rate DESC
    LIMIT 10
  `).all() as { skill_id: string; name: string; success_rate: number }[];

  // 降级候选 - 高失败率
  const degradationCandidates = db.prepare(`
    SELECT skill_id, name, success_count, failure_count,
           CASE WHEN (success_count + failure_count) > 0
                THEN failure_count * 1.0 / (success_count + failure_count)
                ELSE 0 END as failure_rate
    FROM sys_skill_bank
    WHERE status = 'active'
    AND (success_count + failure_count) >= 5
    ORDER BY failure_rate DESC
    LIMIT 10
  `).all() as { skill_id: string; name: string; failure_rate: number }[];

  // 归档候选 - 长期未使用
  const archiveCandidates = db.prepare(`
    SELECT skill_id, name, last_used_at
    FROM sys_skill_bank
    WHERE status = 'active'
    AND last_used_at IS NOT NULL
    AND (success_count + failure_count) = 0
    AND julianday('now') - julianday(last_used_at) >= 90
    ORDER BY last_used_at ASC
    LIMIT 10
  `).all() as { skill_id: string; name: string; last_used_at: string }[];

  db.close();

  return {
    candidates_for_promotion: promotionCandidates
      .filter(s => s.success_rate >= 0.7)
      .map(s => ({
        skill_id: s.skill_id,
        name: s.name,
        score: s.success_rate
      })),
    candidates_for_degradation: degradationCandidates
      .filter(s => s.failure_rate >= 0.6)
      .map(s => ({
        skill_id: s.skill_id,
        name: s.name,
        failure_rate: s.failure_rate
      })),
    candidates_for_archive: archiveCandidates.map(s => ({
      skill_id: s.skill_id,
      name: s.name,
      last_used: s.last_used_at
    }))
  };
}

// 辅助函数
function parseSkillRow(row: Record<string, unknown>): Skill {
  return {
    skill_id: row.skill_id as string,
    name: row.name as string,
    description: row.description as string,
    skill_type: (row.skill_type as Skill['skill_type']) || 'template',
    layer: (row.layer as Skill['layer']) || 'domain',
    scope: (row.scope as Skill['scope']) || 'task_specific',
    status: (row.status as Skill['status']) || 'active',
    success_count: (row.success_count as number) || 0,
    failure_count: (row.failure_count as number) || 0,
    q_value: (row.q_value as number) || 0.5,
    tags: parseJsonSafe(row.tags as string) || [],
    created_at: row.created_at as string,
    updated_at: row.updated_at as string,
    last_used_at: row.last_used_at as string,
    validated: Boolean(row.validated)
  } as Skill;
}

function parseJsonSafe<T>(json: string | null | undefined): T | null {
  if (!json) return null;
  try {
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}
