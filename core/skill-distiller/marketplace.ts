/**
 * Skill Marketplace
 * 跨牛马技能市场模块（P2）
 *
 * 功能：
 * 1. 技能发布与订阅
 * 2. 技能评分与评价
 * 3. 技能推荐
 */

import type { Skill } from './schema';
import { Database } from 'bun:sqlite';

// 牛马角色
export type AgentRole =
  | 'inquisitor'     // 审判官
  | 'builder'        // 建设者
  | 'architect'      // 智囊
  | 'explorer'       // 探索派
  | 'creator'        // 创想家
  | 'verifier';      // 稳健派

// 技能发布
export interface SkillPublication {
  publication_id: string;
  skill_id: string;
  author_agent: AgentRole;
  published_at: string;
  downloads: number;
  rating: number;
  review_count: number;
}

// 技能评价
export interface SkillReview {
  review_id: string;
  publication_id: string;
  reviewer_agent: AgentRole;
  rating: number;  // 1-5
  comment: string;
  created_at: string;
}

// 技能订阅
export interface SkillSubscription {
  subscription_id: string;
  agent_role: AgentRole;
  skill_id: string;
  subscribed_at: string;
  last_used_at: string;
  usage_count: number;
}

// 市场统计
export interface MarketplaceStats {
  total_publications: number;
  total_downloads: number;
  avg_rating: number;
  top_skills: { skill_id: string; name: string; downloads: number; rating: number }[];
  top_authors: { agent: AgentRole; publications: number; avg_rating: number }[];
}

/**
 * 创建市场表
 */
export function ensureMarketTables(): void {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  db.run(`
    CREATE TABLE IF NOT EXISTS skill_publications (
      publication_id TEXT PRIMARY KEY,
      skill_id TEXT NOT NULL UNIQUE,
      author_agent TEXT NOT NULL,
      published_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      downloads INTEGER DEFAULT 0,
      rating REAL DEFAULT 0,
      review_count INTEGER DEFAULT 0,
      FOREIGN KEY (skill_id) REFERENCES sys_skill_bank(skill_id)
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS skill_reviews (
      review_id TEXT PRIMARY KEY,
      publication_id TEXT NOT NULL,
      reviewer_agent TEXT NOT NULL,
      rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
      comment TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (publication_id) REFERENCES skill_publications(publication_id)
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS skill_subscriptions (
      subscription_id TEXT PRIMARY KEY,
      agent_role TEXT NOT NULL,
      skill_id TEXT NOT NULL,
      subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      last_used_at DATETIME,
      usage_count INTEGER DEFAULT 0,
      FOREIGN KEY (skill_id) REFERENCES sys_skill_bank(skill_id),
      UNIQUE(agent_role, skill_id)
    )
  `);

  db.close();
}

/**
 * 发布技能到市场
 */
export function publishSkill(
  skillId: string,
  authorAgent: AgentRole
): { success: boolean; publication_id?: string; message: string } {
  ensureMarketTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 检查技能是否存在且已验证
  const skill = db.prepare(`
    SELECT skill_id, validated, status FROM sys_skill_bank WHERE skill_id = ?
  `).get(skillId) as { skill_id: string; validated: number; status: string } | undefined;

  if (!skill) {
    db.close();
    return { success: false, message: '技能不存在' };
  }

  if (skill.status !== 'active') {
    db.close();
    return { success: false, message: '只能发布已激活的技能' };
  }

  // 检查是否已发布
  const existing = db.prepare(`
    SELECT publication_id FROM skill_publications WHERE skill_id = ?
  `).get(skillId);

  if (existing) {
    db.close();
    return { success: false, message: '技能已发布' };
  }

  const publicationId = `pub_${Date.now().toString(36)}`;

  db.run(`
    INSERT INTO skill_publications (publication_id, skill_id, author_agent)
    VALUES (?, ?, ?)
  `, [publicationId, skillId, authorAgent]);

  db.close();

  return {
    success: true,
    publication_id: publicationId,
    message: `技能已发布到市场`
  };
}

/**
 * 订阅技能
 */
export function subscribeSkill(
  skillId: string,
  agentRole: AgentRole
): { success: boolean; message: string } {
  ensureMarketTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  try {
    const subscriptionId = `sub_${Date.now().toString(36)}_${agentRole}`;

    db.run(`
      INSERT INTO skill_subscriptions (subscription_id, agent_role, skill_id)
      VALUES (?, ?, ?)
    `, [subscriptionId, agentRole, skillId]);

    // 增加下载计数
    db.run(`
      UPDATE skill_publications SET downloads = downloads + 1 WHERE skill_id = ?
    `, [skillId]);

    db.close();

    return { success: true, message: `已订阅技能` };
  } catch (error) {
    db.close();
    return { success: false, message: '已订阅此技能' };
  }
}

/**
 * 记录技能使用
 */
export function recordUsage(skillId: string, agentRole: AgentRole): void {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  db.run(`
    UPDATE skill_subscriptions
    SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP
    WHERE skill_id = ? AND agent_role = ?
  `, [skillId, agentRole]);

  db.close();
}

/**
 * 评价技能
 */
export function reviewSkill(
  skillId: string,
  reviewerAgent: AgentRole,
  rating: number,
  comment: string
): { success: boolean; message: string } {
  ensureMarketTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 获取发布ID
  const publication = db.prepare(`
    SELECT publication_id FROM skill_publications WHERE skill_id = ?
  `).get(skillId) as { publication_id: string } | undefined;

  if (!publication) {
    db.close();
    return { success: false, message: '技能未发布' };
  }

  const reviewId = `rev_${Date.now().toString(36)}`;

  db.run(`
    INSERT INTO skill_reviews (review_id, publication_id, reviewer_agent, rating, comment)
    VALUES (?, ?, ?, ?, ?)
  `, [reviewId, publication.publication_id, reviewerAgent, rating, comment]);

  // 更新平均评分
  db.run(`
    UPDATE skill_publications
    SET rating = (
      SELECT AVG(rating) FROM skill_reviews WHERE publication_id = ?
    ),
    review_count = (
      SELECT COUNT(*) FROM skill_reviews WHERE publication_id = ?
    )
    WHERE publication_id = ?
  `, [publication.publication_id, publication.publication_id, publication.publication_id]);

  db.close();

  return { success: true, message: '评价已提交' };
}

/**
 * 获取市场统计
 */
export function getMarketplaceStats(): MarketplaceStats {
  ensureMarketTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 总发布数
  const totalResult = db.prepare(`
    SELECT COUNT(*) as count FROM skill_publications
  `).get() as { count: number };

  // 总下载量
  const downloadsResult = db.prepare(`
    SELECT COALESCE(SUM(downloads), 0) as total FROM skill_publications
  `).get() as { total: number };

  // 平均评分
  const ratingResult = db.prepare(`
    SELECT COALESCE(AVG(rating), 0) as avg FROM skill_publications WHERE rating > 0
  `).get() as { avg: number };

  // 热门技能
  const topSkills = db.prepare(`
    SELECT p.skill_id, s.name, p.downloads, p.rating
    FROM skill_publications p
    JOIN sys_skill_bank s ON p.skill_id = s.skill_id
    ORDER BY p.downloads DESC
    LIMIT 10
  `).all() as { skill_id: string; name: string; downloads: number; rating: number }[];

  // 热门作者
  const topAuthors = db.prepare(`
    SELECT author_agent, COUNT(*) as publications, AVG(rating) as avg_rating
    FROM skill_publications
    GROUP BY author_agent
    ORDER BY publications DESC
    LIMIT 5
  `).all() as { author_agent: string; publications: number; avg_rating: number }[];

  db.close();

  return {
    total_publications: totalResult.count,
    total_downloads: downloadsResult.total,
    avg_rating: ratingResult.avg,
    top_skills: topSkills,
    top_authors: topAuthors.map(a => ({
      agent: a.author_agent as AgentRole,
      publications: a.publications,
      avg_rating: a.avg_rating
    }))
  };
}

/**
 * 获取推荐技能
 */
export function getRecommendedSkills(
  agentRole: AgentRole,
  limit: number = 5
): { skill_id: string; name: string; description: string; score: number }[] {
  ensureMarketTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 获取推荐：高评分 + 未订阅 + 适合角色
  const recommendations = db.prepare(`
    SELECT p.skill_id, s.name, s.description,
           (p.rating * 0.6 + p.downloads * 0.004) as score
    FROM skill_publications p
    JOIN sys_skill_bank s ON p.skill_id = s.skill_id
    WHERE p.skill_id NOT IN (
      SELECT skill_id FROM skill_subscriptions WHERE agent_role = ?
    )
    ORDER BY score DESC
    LIMIT ?
  `).all(agentRole, limit) as { skill_id: string; name: string; description: string; score: number }[];

  db.close();

  return recommendations;
}

/**
 * 获取牛马的技能库
 */
export function getAgentSkillLibrary(agentRole: AgentRole): {
  subscribed: { skill_id: string; name: string; usage_count: number }[];
  owned: { skill_id: string; name: string; downloads: number }[];
} {
  ensureMarketTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 订阅的技能
  const subscribed = db.prepare(`
    SELECT sub.skill_id, s.name, sub.usage_count
    FROM skill_subscriptions sub
    JOIN sys_skill_bank s ON sub.skill_id = s.skill_id
    WHERE sub.agent_role = ?
    ORDER BY sub.usage_count DESC
  `).all(agentRole) as { skill_id: string; name: string; usage_count: number }[];

  // 拥有的技能（发布的）
  const owned = db.prepare(`
    SELECT p.skill_id, s.name, p.downloads
    FROM skill_publications p
    JOIN sys_skill_bank s ON p.skill_id = s.skill_id
    WHERE p.author_agent = ?
    ORDER BY p.downloads DESC
  `).all(agentRole) as { skill_id: string; name: string; downloads: number }[];

  db.close();

  return { subscribed, owned };
}

/**
 * 获取技能的评价列表
 */
export function getSkillReviews(skillId: string): SkillReview[] {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  const reviews = db.prepare(`
    SELECT r.*
    FROM skill_reviews r
    JOIN skill_publications p ON r.publication_id = p.publication_id
    WHERE p.skill_id = ?
    ORDER BY r.created_at DESC
    LIMIT 20
  `).all(skillId) as Record<string, unknown>[];

  db.close();

  return reviews.map(r => ({
    review_id: r.review_id as string,
    publication_id: r.publication_id as string,
    reviewer_agent: r.reviewer_agent as AgentRole,
    rating: r.rating as number,
    comment: r.comment as string,
    created_at: r.created_at as string
  }));
}
