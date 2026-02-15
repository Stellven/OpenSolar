#!/usr/bin/env bun
/**
 * Knowledge Network - 智能知识网络引擎
 *
 * 设计理念：
 * 1. 知识不是孤立的点，而是连接的网络
 * 2. 从文档中提取：实体、概念、关系、结论
 * 3. 自动建立知识间的链接
 * 4. 支持知识演化和衰减
 *
 * 核心概念：
 * - 实体 (Entity): 人、项目、概念、技术等
 * - 概念 (Concept): 抽象的思维单元
 * - 关系 (Relation): 实体/概念之间的连接
 * - 结论 (Claim): 可复用的论点
 * - 证据 (Evidence): 支持结论的材料
 *
 * @version 1.0.0
 * @created 2026-02-15
 */

import { Database } from 'bun:sqlite';
import { readdir, readFile, stat, writeFile } from 'fs/promises';
import { join, extname, basename } from 'path';
import { existsSync } from 'fs';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;

// ============================================================
// 类型定义
// ============================================================

interface KnowledgeEntity {
  entity_id?: number;
  name: string;
  type: 'person' | 'project' | 'concept' | 'technology' | 'tool' | 'event' | 'book' | 'paper' | 'other';
  description?: string;
  aliases?: string[];
  metadata?: Record<string, any>;
  importance?: number;
  created_at?: string;
}

interface KnowledgeRelation {
  relation_id?: number;
  from_entity: string;  // entity name
  to_entity: string;    // entity name
  relation_type: string; // 'related_to' | 'depends_on' | 'part_of' | 'causes' | 'contradicts' | 'supports' | ...
  evidence?: string;     // 支持这个关系的证据
  confidence?: number;
  source_doc?: string;   // 来源文档
  created_at?: string;
}

interface KnowledgeClaim {
  claim_id?: number;
  claim_text: string;
  supporting_entities?: string[];
  supporting_sources?: string[];
  counter_claims?: string[];
  confidence?: number;
  domain?: string;       // 领域标签
  created_at?: string;
}

interface ExtractedKnowledge {
  entities: KnowledgeEntity[];
  relations: KnowledgeRelation[];
  claims: KnowledgeClaim[];
  summary: string;
  key_insights: string[];
}

// ============================================================
// 知识网络引擎
// ============================================================

class KnowledgeNetworkEngine {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
    this.initTables();
  }

  private initTables(): void {
    // 知识实体表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS knowledge_entities (
        entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        type TEXT DEFAULT 'other',
        description TEXT,
        aliases JSON,
        metadata JSON,
        importance REAL DEFAULT 0.5,
        access_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 知识关系表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS knowledge_relations (
        relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_entity TEXT NOT NULL,
        to_entity TEXT NOT NULL,
        relation_type TEXT NOT NULL,
        evidence TEXT,
        confidence REAL DEFAULT 0.5,
        source_doc TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(from_entity, to_entity, relation_type)
      )
    `);

    // 知识结论表 (扩展 cortex_claims)
    this.db.run(`
      CREATE TABLE IF NOT EXISTS knowledge_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_text TEXT NOT NULL,
        supporting_entities JSON,
        supporting_sources JSON,
        counter_claims JSON,
        confidence REAL DEFAULT 0.5,
        domain TEXT,
        freshness REAL DEFAULT 1.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 知识来源关联表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS knowledge_source_links (
        source_id INTEGER,
        entity_id INTEGER,
        relevance REAL DEFAULT 0.5,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (source_id, entity_id),
        FOREIGN KEY (source_id) REFERENCES cortex_sources(source_id),
        FOREIGN KEY (entity_id) REFERENCES knowledge_entities(entity_id)
      )
    `);

    // 创建索引
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_entity_name ON knowledge_entities(name)`);
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_relation_from ON knowledge_relations(from_entity)`);
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_relation_to ON knowledge_relations(to_entity)`);
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_claim_domain ON knowledge_claims(domain)`);

    console.log('✅ 知识网络表初始化完成');
  }

  // ============================================================
  // 知识提取 - 调用老专家
  // ============================================================

  async extractKnowledge(content: string, sourceType: string): Promise<ExtractedKnowledge> {
    // 构建 prompt，让老专家提取知识
    const extractionPrompt = `你是一位知识管理专家。请分析以下${sourceType}内容，提取结构化知识。

内容:
---
${content.substring(0, 4000)}
---

请以 JSON 格式返回以下结构：
{
  "entities": [
    {"name": "实体名", "type": "person|project|concept|technology|tool|event|book|paper|other", "description": "简短描述"}
  ],
  "relations": [
    {"from": "实体A", "to": "实体B", "type": "related_to|depends_on|part_of|causes|contradicts|supports|implements|uses", "evidence": "依据"}
  ],
  "claims": [
    {"text": "核心论点", "domain": "领域", "confidence": 0.8}
  ],
  "summary": "一句话总结",
  "key_insights": ["洞察1", "洞察2"]
}

注意：
1. 实体名称要统一，避免同义词重复
2. 关系要有实际意义，不要提取无意义的关系
3. 论点要精炼，一个论点一个核心观点
4. 只返回 JSON，不要其他内容`;

    // 这里需要调用 brain-router
    // 暂时返回基础结构，后续接入老专家
    return {
      entities: [],
      relations: [],
      claims: [],
      summary: '待分析',
      key_insights: []
    };
  }

  // ============================================================
  // 实体管理
  // ============================================================

  addEntity(entity: KnowledgeEntity): number {
    const result = this.db.run(`
      INSERT INTO knowledge_entities (name, type, description, aliases, metadata, importance)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(name) DO UPDATE SET
        description = COALESCE(excluded.description, description),
        aliases = COALESCE(excluded.aliases, aliases),
        importance = MAX(excluded.importance, importance),
        updated_at = CURRENT_TIMESTAMP,
        access_count = access_count + 1
    `, [
      entity.name,
      entity.type,
      entity.description || '',
      JSON.stringify(entity.aliases || []),
      JSON.stringify(entity.metadata || {}),
      entity.importance || 0.5
    ]);

    return Number(result.lastInsertRowid);
  }

  getEntity(name: string): KnowledgeEntity | null {
    return this.db.query<KnowledgeEntity, [string]>(`
      SELECT * FROM knowledge_entities WHERE name = ?
    `).get(name);
  }

  searchEntities(keyword: string, limit: number = 10): KnowledgeEntity[] {
    return this.db.query<KnowledgeEntity, [string, number]>(`
      SELECT * FROM knowledge_entities
      WHERE name LIKE ? OR description LIKE ?
      ORDER BY importance DESC, access_count DESC
      LIMIT ?
    `).all(`%${keyword}%`, `%${keyword}%`, limit);
  }

  // ============================================================
  // 关系管理
  // ============================================================

  addRelation(relation: KnowledgeRelation): number {
    const result = this.db.run(`
      INSERT OR IGNORE INTO knowledge_relations
      (from_entity, to_entity, relation_type, evidence, confidence, source_doc)
      VALUES (?, ?, ?, ?, ?, ?)
    `, [
      relation.from_entity,
      relation.to_entity,
      relation.relation_type,
      relation.evidence || '',
      relation.confidence || 0.5,
      relation.source_doc || ''
    ]);

    return Number(result.lastInsertRowid);
  }

  getRelatedEntities(entityName: string, depth: number = 2): Array<{
    entity: string;
    relation: string;
    path: string[];
  }> {
    const results: Array<{ entity: string; relation: string; path: string[] }> = [];
    const visited = new Set<string>();

    const traverse = (current: string, path: string[], currentDepth: number) => {
      if (currentDepth > depth || visited.has(current)) return;
      visited.add(current);

      const relations = this.db.query<{
        from_entity: string;
        to_entity: string;
        relation_type: string;
      }, [string]>(`
        SELECT from_entity, to_entity, relation_type FROM knowledge_relations
        WHERE from_entity = ? OR to_entity = ?
      `).all(current, current);

      for (const rel of relations) {
        const target = rel.from_entity === current ? rel.to_entity : rel.from_entity;
        if (!visited.has(target)) {
          results.push({
            entity: target,
            relation: rel.relation_type,
            path: [...path, target]
          });
          traverse(target, [...path, target], currentDepth + 1);
        }
      }
    };

    traverse(entityName, [entityName], 1);
    return results;
  }

  // ============================================================
  // 结论管理
  // ============================================================

  addClaim(claim: KnowledgeClaim): number {
    const result = this.db.run(`
      INSERT INTO knowledge_claims
      (claim_text, supporting_entities, supporting_sources, counter_claims, confidence, domain)
      VALUES (?, ?, ?, ?, ?, ?)
    `, [
      claim.claim_text,
      JSON.stringify(claim.supporting_entities || []),
      JSON.stringify(claim.supporting_sources || []),
      JSON.stringify(claim.counter_claims || []),
      claim.confidence || 0.5,
      claim.domain || 'general'
    ]);

    return Number(result.lastInsertRowid);
  }

  searchClaims(keyword: string, domain?: string, limit: number = 10): KnowledgeClaim[] {
    let sql = `
      SELECT * FROM knowledge_claims
      WHERE claim_text LIKE ?
    `;
    const params: any[] = [`%${keyword}%`];

    if (domain) {
      sql += ` AND domain = ?`;
      params.push(domain);
    }

    sql += ` ORDER BY confidence DESC, freshness DESC LIMIT ?`;
    params.push(limit);

    return this.db.query<KnowledgeClaim, any[]>(sql).all(...params);
  }

  // ============================================================
  // 知识图谱可视化
  // ============================================================

  getGraph(centerEntity?: string, depth: number = 2): {
    nodes: Array<{ id: string; type: string; importance: number }>;
    edges: Array<{ source: string; target: string; type: string }>;
  } {
    const nodes: Array<{ id: string; type: string; importance: number }> = [];
    const edges: Array<{ source: string; target: string; type: string }> = [];
    const visited = new Set<string>();

    if (centerEntity) {
      // 从中心实体展开
      const related = this.getRelatedEntities(centerEntity, depth);

      // 添加中心节点
      const centerData = this.getEntity(centerEntity);
      if (centerData) {
        nodes.push({ id: centerEntity, type: centerData.type, importance: centerData.importance });
      }

      // 添加相关节点和边
      for (const r of related) {
        if (!visited.has(r.entity)) {
          visited.add(r.entity);
          const entityData = this.getEntity(r.entity);
          nodes.push({
            id: r.entity,
            type: entityData?.type || 'other',
            importance: entityData?.importance || 0.5
          });
        }
        edges.push({
          source: centerEntity,
          target: r.entity,
          type: r.relation
        });
      }
    } else {
      // 返回全局图谱
      const allEntities = this.db.query<KnowledgeEntity, []>(`
        SELECT * FROM knowledge_entities ORDER BY importance DESC LIMIT 50
      `).all();

      for (const e of allEntities) {
        nodes.push({ id: e.name, type: e.type, importance: e.importance || 0.5 });
      }

      const allRelations = this.db.query<{
        from_entity: string;
        to_entity: string;
        relation_type: string;
      }, []>(`
        SELECT from_entity, to_entity, relation_type FROM knowledge_relations LIMIT 100
      `).all();

      for (const r of allRelations) {
        edges.push({ source: r.from_entity, target: r.to_entity, type: r.relation_type });
      }
    }

    return { nodes, edges };
  }

  // ============================================================
  // 知识衰减和演化
  // ============================================================

  decayKnowledge(): void {
    // 知识新鲜度随时间衰减
    this.db.run(`
      UPDATE knowledge_claims
      SET freshness = freshness * 0.99
      WHERE freshness > 0.1
    `);

    // 长期未访问的实体重要性下降
    this.db.run(`
      UPDATE knowledge_entities
      SET importance = importance * 0.995
      WHERE updated_at < datetime('now', '-30 days') AND importance > 0.3
    `);
  }

  // ============================================================
  // 统计和报告
  // ============================================================

  stats(): {
    entities: number;
    relations: number;
    claims: number;
    topEntities: Array<{ name: string; type: string; importance: number }>;
    topDomains: Array<{ domain: string; count: number }>;
  } {
    const entities = this.db.query<{ count: number }>(`SELECT COUNT(*) as count FROM knowledge_entities`).get()?.count || 0;
    const relations = this.db.query<{ count: number }>(`SELECT COUNT(*) as count FROM knowledge_relations`).get()?.count || 0;
    const claims = this.db.query<{ count: number }>(`SELECT COUNT(*) as count FROM knowledge_claims`).get()?.count || 0;

    const topEntities = this.db.query<{
      name: string;
      type: string;
      importance: number;
    }>(`SELECT name, type, importance FROM knowledge_entities ORDER BY importance DESC LIMIT 10`).all();

    const topDomains = this.db.query<{
      domain: string;
      count: number;
    }>(`SELECT domain, COUNT(*) as count FROM knowledge_claims GROUP BY domain ORDER BY count DESC LIMIT 10`).all();

    return { entities, relations, claims, topEntities, topDomains };
  }

  close(): void {
    this.db.close();
  }
}

// ============================================================
// 导出
// ============================================================

export { KnowledgeNetworkEngine, KnowledgeEntity, KnowledgeRelation, KnowledgeClaim, ExtractedKnowledge };

// CLI 入口
if (import.meta.main) {
  const engine = new KnowledgeNetworkEngine();

  console.log('\n📊 知识网络状态:');
  const stats = engine.stats();
  console.log(`  实体: ${stats.entities}`);
  console.log(`  关系: ${stats.relations}`);
  console.log(`  结论: ${stats.claims}`);

  if (stats.topEntities.length > 0) {
    console.log('\n  重要实体:');
    for (const e of stats.topEntities.slice(0, 5)) {
      console.log(`    - ${e.name} (${e.type}): ${e.importance.toFixed(2)}`);
    }
  }

  engine.close();
}
