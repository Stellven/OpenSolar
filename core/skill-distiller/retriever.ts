/**
 * Skill Retriever
 * 技能检索模块 - 与现有 Skill Retriever MCP 集成
 */

import type { Skill, RetrievalRequest, RetrievalResult } from './schema';
import { retrieveSkills, getSkill, recordSkillUsage } from './db';
import { Database } from 'bun:sqlite';

/**
 * 检索相关技能（供牛马调用）
 */
export async function retrieveSkillsForAgent(
  query: string,
  context?: {
    task_type?: string;
    tags?: string[];
    layer?: 'core' | 'domain' | 'utility';
  },
  topK: number = 5
): Promise<Skill[]> {
  const request: RetrievalRequest = {
    query,
    context,
    top_k: topK
  };

  const result = await Promise.resolve(retrieveSkills(request));
  return result.skills;
}

/**
 * 获取技能并记录使用
 */
export function getSkillForExecution(skillId: string): Skill | null {
  const skill = getSkill(skillId);
  if (skill) {
    // 记录使用（不区分成功失败，由调用方后续报告）
  }
  return skill;
}

/**
 * 报告技能执行结果
 */
export function reportSkillExecution(
  skillId: string,
  success: boolean,
  metadata?: {
    execution_time_ms?: number;
    user_rating?: number;
    comment?: string;
  }
): void {
  recordSkillUsage(skillId, success);

  // 如果有详细反馈，记录到 feedback 表
  if (metadata?.user_rating || metadata?.comment) {
    saveSkillFeedback(skillId, success, metadata);
  }
}

/**
 * 保存技能反馈
 */
function saveSkillFeedback(
  skillId: string,
  success: boolean,
  metadata: {
    execution_time_ms?: number;
    user_rating?: number;
    comment?: string;
  }
): void {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 确保表存在
  db.run(`
    CREATE TABLE IF NOT EXISTS skill_feedback (
      feedback_id TEXT PRIMARY KEY,
      skill_id TEXT NOT NULL,
      skill_version TEXT NOT NULL,
      session_id TEXT,
      task_description TEXT,
      user_agent TEXT,
      outcome TEXT NOT NULL CHECK(outcome IN ('success', 'failure', 'partial')),
      execution_time_ms INTEGER,
      user_rating INTEGER CHECK(user_rating BETWEEN 1 AND 5),
      user_comment TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (skill_id) REFERENCES sys_skill_bank(skill_id)
    )
  `);

  const feedbackId = `fb_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

  db.run(`
    INSERT INTO skill_feedback (
      feedback_id, skill_id, skill_version, outcome,
      execution_time_ms, user_rating, user_comment
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
  `, [
    feedbackId,
    skillId,
    '1.0.0',  // 简化版本处理
    success ? 'success' : 'failure',
    metadata.execution_time_ms || null,
    metadata.user_rating || null,
    metadata.comment || null
  ]);

  db.close();
}

/**
 * 格式化技能为提示词（供牛马使用）
 */
export function formatSkillForPrompt(skill: Skill): string {
  const triggerInfo = skill.trigger_keywords?.length
    ? `\n触发关键词: ${skill.trigger_keywords.join(', ')}`
    : '';

  const preconditionInfo = skill.preconditions?.length
    ? `\n前置条件: ${skill.preconditions.join('; ')}`
    : '';

  const templateInfo = skill.llm_prompt_template
    ? `\n\n**执行模板**:\n\`\`\`\n${skill.llm_prompt_template}\n\`\`\``
    : '';

  return `### ${skill.name}
${skill.description}

层级: ${skill.layer} | 范围: ${skill.scope}
使用统计: 成功 ${skill.success_count} / 失败 ${skill.failure_count}${triggerInfo}${preconditionInfo}${templateInfo}`;
}

/**
 * 格式化多个技能为上下文
 */
export function formatSkillsAsContext(skills: Skill[]): string {
  if (skills.length === 0) return '';

  return `
## 🎯 相关技能（可直接应用）

以下技能可能对当前任务有帮助：

${skills.map(formatSkillForPrompt).join('\n\n---\n\n')}

**使用建议**: 根据任务具体情况选择合适的技能应用。
`;
}

/**
 * 为 buildNiumaCall 注入技能
 */
export async function injectSkillsToPrompt(
  task: string,
  context: {
    task_type?: string;
    tags?: string[];
  },
  existingSystemPrompt: string
): Promise<{
  system: string;
  retrieved_skills: string[];
}> {
  // 1. 检索相关技能
  const skills = await retrieveSkillsForAgent(task, context, 3);

  // 2. 格式化技能
  const skillContext = formatSkillsAsContext(skills);

  // 3. 注入到系统提示词
  const enhancedSystem = skillContext
    ? `${existingSystemPrompt}\n\n${skillContext}`
    : existingSystemPrompt;

  return {
    system: enhancedSystem,
    retrieved_skills: skills.map(s => s.skill_id)
  };
}
