/**
 * Skill Database Operations
 * 技能数据库操作封装
 */

import { Database } from 'bun:sqlite';
import type { Skill, SkillFeedback, RetrievalRequest, RetrievalResult } from './schema';

const DB_PATH = process.env.SOLAR_DB_PATH || `${process.env.HOME}/.solar/solar.db`;

let db: Database | null = null;

function getDb(): Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.run('PRAGMA journal_mode = WAL');
  }
  return db;
}

/**
 * 创建新技能
 */
export function createSkill(skill: Partial<Skill>): string {
  const db = getDb();
  const skillId = skill.skill_id || generateSkillId(skill.name || 'unknown');

  const stmt = db.prepare(`
    INSERT INTO sys_skill_bank (
      skill_id, intent_hash, name, description, skill_type,
      layer, scope, status, llm_prompt_template, parameters,
      trigger_keywords, applicable_contexts, preconditions, prerequisites,
      tags, version, source, source_ref, author_agent, parent_id,
      skill_metadata, validated, q_value
    ) VALUES (
      ?, ?, ?, ?, ?,
      ?, ?, ?, ?, ?,
      ?, ?, ?, ?,
      ?, ?, ?, ?, ?, ?,
      ?, 0, 0.5
    )
  `);

  const intentHash = hashString(skill.name + skill.description);

  stmt.run(
    skillId,
    intentHash,
    skill.name,
    skill.description,
    skill.skill_type || 'template',
    skill.layer || 'domain',
    skill.scope || 'task_specific',
    skill.status || 'pending_review',
    skill.llm_prompt_template || null,
    JSON.stringify(skill.parameters || []),
    JSON.stringify(skill.trigger_keywords || []),
    JSON.stringify(skill.applicable_contexts || []),
    JSON.stringify(skill.preconditions || []),
    JSON.stringify(skill.prerequisites || []),
    JSON.stringify(skill.tags || []),
    skill.version || '1.0.0',
    skill.source || 'distilled',
    skill.source_ref || null,
    skill.author_agent || null,
    skill.parent_id || null,
    JSON.stringify(skill.skill_metadata || {})
  );

  return skillId;
}

/**
 * 获取技能
 */
export function getSkill(skillId: string): Skill | null {
  const db = getDb();
  const stmt = db.prepare('SELECT * FROM sys_skill_bank WHERE skill_id = ?');
  const row = stmt.get(skillId) as unknown;

  if (!row) return null;

  return parseSkillRow(row as Record<string, unknown>);
}

/**
 * 更新技能状态
 */
export function updateSkillStatus(skillId: string, status: Skill['status']): boolean {
  const db = getDb();
  const stmt = db.prepare(`
    UPDATE sys_skill_bank
    SET status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE skill_id = ?
  `);
  const result = stmt.run(status, skillId);
  return result.changes > 0;
}

/**
 * 记录技能使用
 */
export function recordSkillUsage(skillId: string, success: boolean): void {
  const db = getDb();
  const field = success ? 'success_count' : 'failure_count';
  const stmt = db.prepare(`
    UPDATE sys_skill_bank
    SET ${field} = ${field} + 1,
        last_used_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE skill_id = ?
  `);
  stmt.run(skillId);
}

/**
 * 检索技能
 */
export function retrieveSkills(request: RetrievalRequest): RetrievalResult {
  const db = getDb();
  const startTime = Date.now();

  const topK = request.top_k || 5;
  const conditions: string[] = ["status = 'active'"];
  const params: unknown[] = [];

  // 标签匹配
  if (request.context?.tags && request.context.tags.length > 0) {
    const tagConditions = request.context.tags.map(() =>
      `EXISTS (SELECT 1 FROM json_each(tags) WHERE value = ?)`
    );
    conditions.push(`(${tagConditions.join(' OR ')})`);
    params.push(...request.context.tags);
  }

  // 层级过滤
  if (request.context?.layer) {
    conditions.push('layer = ?');
    params.push(request.context.layer);
  }

  // 关键词搜索（拆分多关键词）
  if (request.query) {
    const keywords = request.query.split(/\s+/).filter(k => k.length >= 2);
    if (keywords.length > 0) {
      const keywordConditions = keywords.map(() => `
        name LIKE ? OR
        description LIKE ? OR
        EXISTS (SELECT 1 FROM json_each(tags) WHERE value LIKE ?)
      `);
      conditions.push(`(${keywordConditions.join(' OR ')})`);
      for (const kw of keywords) {
        const searchTerm = `%${kw}%`;
        params.push(searchTerm, searchTerm, searchTerm);
      }
    }
  }

  const whereClause = conditions.join(' AND ');

  // 构建排序条件 - 名称匹配优先
  let orderBy = `
    CASE
      WHEN name LIKE ? THEN 0
      WHEN description LIKE ? THEN 1
      ELSE 2
    END,
    q_value DESC,
    (success_count * 1.0 / NULLIF(success_count + failure_count, 0)) DESC,
    CASE scope WHEN 'general' THEN 1 ELSE 2 END
  `;

  // 为排序添加第一个关键词参数
  const firstKeyword = request.query?.split(/\s+/).filter(k => k.length >= 2)[0];
  if (firstKeyword) {
    const searchTerm = `%${firstKeyword}%`;
    params.unshift(searchTerm, searchTerm);  // 添加到开头用于排序
  } else {
    params.unshift('%%', '%%');  // 无关键词时不影响排序
  }

  const stmt = db.prepare(`
    SELECT * FROM sys_skill_bank
    WHERE ${whereClause}
    ORDER BY ${orderBy}
    LIMIT ?
  `);

  params.push(topK);
  const rows = stmt.all(...params) as unknown[];

  const skills = rows.map(row => parseSkillRow(row as Record<string, unknown>));

  return {
    skills,
    total: skills.length,
    query_time_ms: Date.now() - startTime
  };
}

/**
 * 获取待审核技能
 */
export function getPendingSkills(): Skill[] {
  const db = getDb();
  const stmt = db.prepare(`
    SELECT * FROM sys_skill_bank
    WHERE status = 'pending_review'
    ORDER BY created_at DESC
  `);
  const rows = stmt.all() as unknown[];
  return rows.map(row => parseSkillRow(row as Record<string, unknown>));
}

/**
 * 获取技能统计
 */
export function getSkillStats(): {
  total: number;
  by_status: Record<string, number>;
  by_layer: Record<string, number>;
  by_source: Record<string, number>;
} {
  const db = getDb();

  const total = (db.prepare('SELECT COUNT(*) as count FROM sys_skill_bank').get() as { count: number }).count;

  const byStatus = db.prepare(`
    SELECT status, COUNT(*) as count
    FROM sys_skill_bank
    GROUP BY status
  `).all() as { status: string; count: number }[];

  const byLayer = db.prepare(`
    SELECT COALESCE(layer, 'domain') as layer, COUNT(*) as count
    FROM sys_skill_bank
    GROUP BY layer
  `).all() as { layer: string; count: number }[];

  const bySource = db.prepare(`
    SELECT source, COUNT(*) as count
    FROM sys_skill_bank
    GROUP BY source
  `).all() as { source: string; count: number }[];

  return {
    total,
    by_status: Object.fromEntries(byStatus.map(r => [r.status, r.count])),
    by_layer: Object.fromEntries(byLayer.map(r => [r.layer, r.count])),
    by_source: Object.fromEntries(bySource.map(r => [r.source, r.count]))
  };
}

/**
 * 从 sys_favorites 获取候选
 */
export function getFavoriteForDistillation(favoriteId: number): {
  title: string;
  question: string;
  answer: string;
  tags: string[];
} | null {
  const db = getDb();
  const stmt = db.prepare(`
    SELECT title, question, answer, tags, importance
    FROM sys_favorites
    WHERE favorite_id = ?
  `);
  const row = stmt.get(favoriteId) as unknown;

  if (!row) return null;

  const result = row as { title: string; question: string; answer: string; tags: string; importance: number };
  return {
    title: result.title,
    question: result.question,
    answer: result.answer,
    tags: parseJsonSafe(result.tags) || []
  };
}

// 辅助函数

function generateSkillId(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 30);
  const timestamp = Date.now().toString(36);
  return `skill_${slug}_${timestamp}`;
}

function hashString(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
}

function parseSkillRow(row: Record<string, unknown>): Skill {
  return {
    skill_id: row.skill_id as string,
    name: row.name as string,
    description: row.description as string,
    skill_type: (row.skill_type as Skill['skill_type']) || 'template',
    layer: (row.layer as Skill['layer']) || 'domain',
    scope: (row.scope as Skill['scope']) || 'task_specific',
    status: (row.status as Skill['status']) || 'active',
    llm_prompt_template: row.llm_prompt_template as string,
    parameters: parseJsonSafe(row.parameters as string) || [],
    timeout_ms: row.timeout_ms as number,
    max_retries: row.max_retries as number,
    trigger_keywords: parseJsonSafe(row.trigger_keywords as string) || [],
    applicable_contexts: parseJsonSafe(row.applicable_contexts as string) || [],
    preconditions: parseJsonSafe(row.preconditions as string) || [],
    prerequisites: parseJsonSafe(row.prerequisites as string) || [],
    success_count: (row.success_count as number) || 0,
    failure_count: (row.failure_count as number) || 0,
    q_value: (row.q_value as number) || 0.5,
    avg_execution_time_ms: row.avg_execution_time_ms as number,
    tags: parseJsonSafe(row.tags as string) || [],
    version: (row.version as string) || '1.0.0',
    source: (row.source as string) || 'manual',
    source_ref: row.source_ref as string,
    author_agent: row.author_agent as string,
    parent_id: row.parent_id as string,
    created_at: row.created_at as string,
    updated_at: row.updated_at as string,
    last_used_at: row.last_used_at as string,
    validated: Boolean(row.validated),
    test_cases: parseJsonSafe(row.test_cases as string),
    skill_metadata: parseJsonSafe(row.skill_metadata as string)
  };
}

function parseJsonSafe<T>(json: string | null | undefined): T | null {
  if (!json) return null;
  try {
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}
