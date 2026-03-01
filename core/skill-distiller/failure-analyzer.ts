/**
 * Failure Analyzer
 * 失败轨迹分析模块（P2）
 *
 * 功能：
 * 1. 分析技能失败模式
 * 2. 生成改进建议
 * 3. 触发技能进化
 */

import type { Skill } from './schema';
import { Database } from 'bun:sqlite';
import { getSkill } from './db';

// 失败类别
export type FailureCategory =
  | 'context_mismatch'    // 上下文不匹配
  | 'precondition_failed' // 前置条件不满足
  | 'execution_error'     // 执行错误
  | 'output_invalid'      // 输出无效
  | 'timeout'             // 超时
  | 'unknown';            // 未知错误

// 失败分析结果
export interface FailureAnalysis {
  skill_id: string;
  category: FailureCategory;
  description: string;
  suggestions: string[];
  confidence: number;
}

// 失败模式统计
export interface FailurePattern {
  pattern: string;
  count: number;
  affected_skills: string[];
  root_cause: string;
  fix_suggestion: string;
}

/**
 * 分析失败轨迹
 */
export function analyzeFailure(
  skillId: string,
  failureContext: {
    task_description?: string;
    error_message?: string;
    execution_trace?: string;
    expected_output?: string;
    actual_output?: string;
  }
): FailureAnalysis {
  const skill = getSkill(skillId);
  if (!skill) {
    return {
      skill_id: skillId,
      category: 'unknown',
      description: '技能不存在',
      suggestions: ['检查技能ID是否正确'],
      confidence: 0
    };
  }

  // 基于错误信息分类
  const category = classifyFailure(failureContext);
  const description = generateFailureDescription(category, failureContext);
  const suggestions = generateSuggestions(skill, category, failureContext);

  return {
    skill_id: skillId,
    category,
    description,
    suggestions,
    confidence: 0.7
  };
}

/**
 * 分类失败类型
 */
function classifyFailure(context: {
  error_message?: string;
  expected_output?: string;
  actual_output?: string;
}): FailureCategory {
  const errorMsg = (context.error_message || '').toLowerCase();

  if (errorMsg.includes('timeout') || errorMsg.includes('超时')) {
    return 'timeout';
  }

  if (errorMsg.includes('precondition') || errorMsg.includes('前置条件')) {
    return 'precondition_failed';
  }

  if (errorMsg.includes('context') || errorMsg.includes('上下文') || errorMsg.includes('mismatch')) {
    return 'context_mismatch';
  }

  if (context.expected_output && context.actual_output) {
    if (context.actual_output.length === 0 || context.actual_output.includes('error')) {
      return 'output_invalid';
    }
  }

  if (errorMsg.includes('error') || errorMsg.includes('failed') || errorMsg.includes('失败')) {
    return 'execution_error';
  }

  return 'unknown';
}

/**
 * 生成失败描述
 */
function generateFailureDescription(
  category: FailureCategory,
  context: { error_message?: string; task_description?: string }
): string {
  const descriptions: Record<FailureCategory, string> = {
    context_mismatch: `技能上下文与任务不匹配。任务: ${context.task_description?.slice(0, 50)}...`,
    precondition_failed: `前置条件不满足: ${context.error_message?.slice(0, 100)}`,
    execution_error: `执行过程中发生错误: ${context.error_message?.slice(0, 100)}`,
    output_invalid: `输出不符合预期格式或为空`,
    timeout: `技能执行超时`,
    unknown: `未知错误: ${context.error_message?.slice(0, 100)}`
  };

  return descriptions[category];
}

/**
 * 生成改进建议
 */
function generateSuggestions(
  skill: Skill,
  category: FailureCategory,
  _context: { task_description?: string; error_message?: string }
): string[] {
  const suggestions: Record<FailureCategory, string[]> = {
    context_mismatch: [
      `扩展技能 "${skill.name}" 的适用上下文`,
      `添加新的触发关键词以匹配更多场景`,
      `考虑创建特定场景的子技能`
    ],
    precondition_failed: [
      `更新技能前置条件检查`,
      `添加缺失的前置条件说明`,
      `提供前置条件不满足时的备选方案`
    ],
    execution_error: [
      `检查技能模板中的变量引用`,
      `添加错误处理和重试逻辑`,
      `简化技能步骤以减少出错点`
    ],
    output_invalid: [
      `明确输出格式要求`,
      `添加输出验证步骤`,
      `提供输出模板示例`
    ],
    timeout: [
      `优化技能执行步骤`,
      `减少不必要的中间步骤`,
      `考虑拆分为多个子技能`
    ],
    unknown: [
      `收集更多失败案例`,
      `添加详细日志记录`,
      `人工审查技能逻辑`
    ]
  };

  return suggestions[category];
}

/**
 * 获取技能失败模式统计
 */
export function getFailurePatterns(skillId?: string): FailurePattern[] {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  let query = `
    SELECT
      skill_id,
      COUNT(*) as failure_count,
      GROUP_CONCAT(DISTINCT user_comment) as comments
    FROM skill_feedback
    WHERE outcome = 'failure'
  `;

  if (skillId) {
    query += ` AND skill_id = ?`;
  }

  query += `
    GROUP BY skill_id
    ORDER BY failure_count DESC
    LIMIT 10
  `;

  const results = skillId
    ? db.prepare(query).all(skillId)
    : db.prepare(query).all();

  db.close();

  return (results as { skill_id: string; failure_count: number; comments: string }[]).map(r => ({
    pattern: `高失败率模式`,
    count: r.failure_count,
    affected_skills: [r.skill_id],
    root_cause: r.comments?.split(',').slice(0, 3).join('; ') || '未记录',
    fix_suggestion: '建议重新审视技能设计或添加更详细的上下文匹配条件'
  }));
}

/**
 * 触发技能改进
 */
export async function triggerSkillImprovement(skillId: string): Promise<{
  success: boolean;
  new_skill_id?: string;
  message: string;
}> {
  const skill = getSkill(skillId);
  if (!skill) {
    return { success: false, message: '技能不存在' };
  }

  // 获取失败反馈
  const patterns = getFailurePatterns(skillId);
  if (patterns.length === 0 || patterns[0].count < 3) {
    return { success: false, message: '失败次数不足，暂无需改进' };
  }

  // 生成改进版技能的框架
  const improvedSkill: Partial<Skill> = {
    name: `${skill.name} (改进版)`,
    description: `${skill.description} - 基于失败反馈改进`,
    skill_type: skill.skill_type,
    layer: skill.layer,
    scope: skill.scope,
    status: 'pending_review',
    parent_id: skillId,
    llm_prompt_template: skill.llm_prompt_template,
    tags: [...(skill.tags || []), 'improved'],
    source: 'evolution',
    source_ref: `improved_from:${skillId}`,
    skill_metadata: {
      improved_from: skillId,
      failure_count: patterns[0].count,
      improvement_reason: patterns[0].root_cause
    }
  };

  // 这里应该调用审判官来生成改进版
  // 简化版：直接创建框架
  const { createSkill } = await import('./db');
  const newSkillId = createSkill(improvedSkill);

  return {
    success: true,
    new_skill_id: newSkillId,
    message: `已创建改进版技能框架，需要人工完善后审核`
  };
}

/**
 * 批量分析失败技能
 */
export function batchAnalyzeFailures(): {
  analyzed: number;
  top_issues: { skill_id: string; name: string; failure_rate: number; category: FailureCategory }[];
} {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 获取高失败率技能
  const failingSkills = db.prepare(`
    SELECT
      s.skill_id, s.name,
      s.success_count, s.failure_count,
      CASE WHEN (s.success_count + s.failure_count) > 0
           THEN s.failure_count * 1.0 / (s.success_count + s.failure_count)
           ELSE 0 END as failure_rate
    FROM sys_skill_bank s
    WHERE s.status = 'active'
    AND (s.success_count + s.failure_count) >= 3
    ORDER BY failure_rate DESC
    LIMIT 10
  `).all() as { skill_id: string; name: string; failure_rate: number }[];

  db.close();

  const topIssues = failingSkills.map(s => ({
    skill_id: s.skill_id,
    name: s.name,
    failure_rate: s.failure_rate,
    category: 'execution_error' as FailureCategory  // 默认分类
  }));

  return {
    analyzed: failingSkills.length,
    top_issues: topIssues
  };
}
