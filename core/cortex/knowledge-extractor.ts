#!/usr/bin/env bun
/**
 * Knowledge Extractor - 智能知识提取引擎
 *
 * 设计理念：
 * 1. 从文本中提取实体（人/概念/事件/技术）
 * 2. 提取实体之间的关系
 * 3. 建立知识图谱，而非孤立的知识点
 * 4. 与现有知识库融合，发现新关联
 *
 * 使用：
 *   bun knowledge-extractor.ts <file.md>
 *   bun knowledge-extractor.ts --sync-obsidian
 */

import { Database } from 'bun:sqlite';
import { readFile, readdir, writeFile } from 'fs/promises';
import { join, extname, basename } from 'path';
import { existsSync } from 'fs';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;

// ============================================================
// 类型定义
// ============================================================

interface Entity {
  name: string;
  type: 'person' | 'concept' | 'technology' | 'event' | 'project' | 'tool' | 'place' | 'other';
  aliases: string[];
  description: string;
  confidence: number;
}

interface Relation {
  from: string;
  to: string;
  type: string;  // 'uses', 'created', 'related_to', 'part_of', 'influences'
  evidence: string;
  confidence: number;
}

interface KnowledgePoint {
  content: string;
  source_type: string;
  importance: number;  // 1-10
  entities: Entity[];
  relations: Relation[];
  tags: string[];
}

interface ExtractionResult {
  title: string;
  summary: string;
  entities: Entity[];
  relations: Relation[];
  key_insights: string[];
  questions: string[];  // 需要进一步探索的问题
}

// ============================================================
// 老专家人格配置
// ============================================================

const EXPERT_PERSONAS = {
  // 稳健派 - 严谨分析 (D&D: verifier)
  'gemini-2.5-pro': {
    system: `你是"稳健派"，一个严谨的知识分析师。

D&D 角色: verifier
KNOBS: rigor=5 skepticism=4 explore=2 decide=2 risk=5 tool=3 compression=3 check=5 empathy=3 compete=2

你的职责：
1. 精确识别文本中的所有技术实体
2. 提取实体间的技术关系
3. 评估每个知识点的重要性

输出格式 (JSON):
{
  "entities": [
    {"name": "实体名", "type": "technology|concept|...", "description": "描述", "confidence": 0.9}
  ],
  "relations": [
    {"from": "实体A", "to": "实体B", "type": "uses|created|...", "evidence": "原文依据", "confidence": 0.85}
  ],
  "key_insights": ["核心洞察1", "核心洞察2"],
  "importance_score": 8
}`,
    temperature: 0.3
  },

  // 审判官 - 深度关联 (D&D: judge)
  'deepseek-r1': {
    system: `你是"审判官"，擅长发现知识间的深层关联。

D&D 角色: judge
KNOBS: rigor=5 skepticism=5 explore=1 decide=2 risk=4 tool=0 compression=4 check=4 empathy=2 compete=1

你的职责：
1. 思考这些知识与已知知识的关联
2. 发现潜在的知识网络
3. 提出值得深入探索的问题

输出格式 (JSON):
{
  "associations": [
    {"entity": "实体", "related_to": ["已知实体1", "已知实体2"], "reason": "关联原因"}
  ],
  "new_perspectives": ["新视角1", "新视角2"],
  "questions_to_explore": ["待探索问题1", "待探索问题2"],
  "knowledge_gaps": ["知识空白1"]
}`,
    temperature: 0.7
  },

  // 创想家 - 实用提炼 (D&D: creator)
  'deepseek-v3': {
    system: `你是"创想家"，擅长提炼可操作的知识。

D&D 角色: creator
KNOBS: rigor=2 skepticism=2 explore=5 decide=4 risk=1 tool=4 compression=3 check=2 empathy=3 compete=4

你的职责：
1. 提取可以直接使用的知识点
2. 总结最佳实践
3. 给出行动建议

输出格式 (JSON):
{
  "actionable_insights": [
    {"insight": "洞察", "how_to_apply": "如何应用", "priority": "high|medium|low"}
  ],
  "best_practices": ["最佳实践1", "最佳实践2"],
  "action_items": ["行动项1", "行动项2"]
}`,
    temperature: 0.5
  }
};

// ============================================================
// 核心类
// ============================================================

class KnowledgeExtractor {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
    this.initTables();
  }

  private initTables(): void {
    // 知识图谱 - 实体表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_entities (
        entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        aliases JSON,
        description TEXT,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
        mention_count INTEGER DEFAULT 1,
        UNIQUE(name)
      )
    `);

    // 知识图谱 - 关系表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_relations (
        relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_entity TEXT NOT NULL,
        to_entity TEXT NOT NULL,
        relation_type TEXT NOT NULL,
        evidence TEXT,
        source_path TEXT,
        confidence REAL DEFAULT 0.7,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(from_entity, to_entity, relation_type)
      )
    `);

    // 知识点表 (关联到实体)
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_knowledge_points (
        point_id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        source_path TEXT,
        source_type TEXT,
        importance INTEGER DEFAULT 5,
        tags JSON,
        entities JSON,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 知识融合记录 (记录两个实体被关联的过程)
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_fusion_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_a TEXT,
        entity_b TEXT,
        fusion_type TEXT,  -- 'merged', 'related', 'same_as'
        evidence TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    console.log('✅ 知识图谱表初始化完成');
  }

  // ============================================================
  // 调用老专家分析
  // ============================================================

  private async callExpert(
    model: string,
    content: string,
    taskType: 'extract' | 'associate' | 'summarize'
  ): Promise<any> {
    const persona = EXPERT_PERSONAS[model as keyof typeof EXPERT_PERSONAS];
    if (!persona) {
      throw new Error(`Unknown model: ${model}`);
    }

    // 这里应该调用 brain-router MCP
    // 简化版：直接返回模拟结果
    console.log(`  📞 调用 ${model} 分析...`);

    // 实际实现时调用：
    // const result = await mcp__brain_router__complete({
    //   model,
    //   system: persona.system,
    //   prompt: `分析以下内容：\n\n${content}`,
    //   temperature: persona.temperature
    // });

    // 模拟返回
    return {
      entities: [],
      relations: [],
      key_insights: []
    };
  }

  // ============================================================
  // 多专家会审
  // ============================================================

  async extractWithExperts(content: string): Promise<ExtractionResult> {
    console.log('\n🔬 启动多专家知识提取...');

    // 并行调用三个专家
    const [techResult, thinkResult, practicalResult] = await Promise.all([
      this.callExpert('gemini-2.5-pro', content, 'extract'),
      this.callExpert('deepseek-r1', content, 'associate'),
      this.callExpert('deepseek-v3', content, 'summarize')
    ]);

    // 融合结果
    const merged: ExtractionResult = {
      title: '',
      summary: '',
      entities: techResult.entities || [],
      relations: techResult.relations || [],
      key_insights: [
        ...(techResult.key_insights || []),
        ...(thinkResult.new_perspectives || []),
        ...(practicalResult.actionable_insights?.map((i: any) => i.insight) || [])
      ],
      questions: thinkResult.questions_to_explore || []
    };

    return merged;
  }

  // ============================================================
  // 本地简化提取 (不调用 API)
  // ============================================================

  extractLocally(content: string): ExtractionResult {
    const result: ExtractionResult = {
      title: '',
      summary: content.substring(0, 200),
      entities: [],
      relations: [],
      key_insights: [],
      questions: []
    };

    // 提取可能的实体 (简单模式匹配)
    const patterns = {
      technology: /\b([A-Z][a-z]+(?:JS|TS|SQL|ML|AI|API|SDK|CLI|OS|DB|UI|UX|DevOps|K8s|AWS|GCP|Azure)?[a-z]*)\b/g,
      concept: /【([^】]+)】|#([^\s#]+)/g,
      person: /@(\w+)/g,
    };

    const entities: Entity[] = [];

    // 提取标签作为概念
    const tags = content.matchAll(/#([^\s#]+)/g);
    for (const match of tags) {
      entities.push({
        name: match[1],
        type: 'concept',
        aliases: [],
        description: `从笔记中提取的概念`,
        confidence: 0.8
      });
    }

    // 提取 [[链接]] 作为关联
    const links = content.matchAll(/\[\[([^\]]+)\]\]/g);
    const linkedEntities: string[] = [];
    for (const match of links) {
      linkedEntities.push(match[1]);
    }

    // 建立 [[A]] 与 [[B]] 的关联
    for (let i = 0; i < linkedEntities.length; i++) {
      for (let j = i + 1; j < linkedEntities.length; j++) {
        result.relations.push({
          from: linkedEntities[i],
          to: linkedEntities[j],
          type: 'mentioned_together',
          evidence: '在同一笔记中被提及',
          confidence: 0.6
        });
      }
    }

    result.entities = [...entities, ...linkedEntities.map(name => ({
      name,
      type: 'concept' as const,
      aliases: [],
      description: '',
      confidence: 0.7
    }))];

    // 提取关键句子 (以 "结论:"、"重点:"、"注意:" 开头)
    const keyPatterns = /(?:结论|重点|注意|关键|核心|要点)[：:]\s*([^\n。！？]+[。\n])/g;
    const keyMatches = content.matchAll(keyPatterns);
    for (const match of keyMatches) {
      result.key_insights.push(match[1].trim());
    }

    return result;
  }

  // ============================================================
  // 存入知识库
  // ============================================================

  saveToKnowledgeBase(result: ExtractionResult, sourcePath: string): void {
    console.log('\n💾 存入知识库...');

    // 1. 存储实体
    for (const entity of result.entities) {
      try {
        this.db.run(`
          INSERT INTO cortex_entities (name, type, aliases, description, mention_count)
          VALUES (?, ?, ?, ?, 1)
          ON CONFLICT(name) DO UPDATE SET
            mention_count = mention_count + 1,
            last_updated = CURRENT_TIMESTAMP
        `, [entity.name, entity.type, JSON.stringify(entity.aliases), entity.description]);
      } catch (e) {
        // 忽略重复
      }
    }
    console.log(`  ✅ 存储 ${result.entities.length} 个实体`);

    // 2. 存储关系
    for (const rel of result.relations) {
      try {
        this.db.run(`
          INSERT INTO cortex_relations (from_entity, to_entity, relation_type, evidence, source_path, confidence)
          VALUES (?, ?, ?, ?, ?, ?)
          ON CONFLICT(from_entity, to_entity, relation_type) DO UPDATE SET
            evidence = excluded.evidence,
            confidence = MAX(confidence, excluded.confidence)
        `, [rel.from, rel.to, rel.type, rel.evidence, sourcePath, rel.confidence]);
      } catch (e) {
        // 忽略重复
      }
    }
    console.log(`  ✅ 存储 ${result.relations.length} 个关系`);

    // 3. 存储知识点
    for (const insight of result.key_insights) {
      this.db.run(`
        INSERT INTO cortex_knowledge_points (content, source_path, source_type, importance, tags, entities)
        VALUES (?, ?, 'obsidian', 7, ?, ?)
      `, [
        insight,
        sourcePath,
        JSON.stringify(result.entities.map(e => e.name)),
        JSON.stringify(result.entities.filter(e => e.type === 'concept').map(e => e.name))
      ]);
    }
    console.log(`  ✅ 存储 ${result.key_insights.length} 个知识点`);
  }

  // ============================================================
  // 知识融合 - 发现与现有知识的关联
  // ============================================================

  discoverConnections(newEntities: Entity[]): Array<{
    entity: string;
    relatedTo: string[];
    connectionType: string;
  }> {
    const connections: Array<{ entity: string; relatedTo: string[]; connectionType: string }> = [];

    for (const entity of newEntities) {
      // 查找已有的相关实体
      const related = this.db.query<{
        name: string;
        type: string;
        mention_count: number;
      }, [string, string]>(`
        SELECT name, type, mention_count
        FROM cortex_entities
        WHERE name LIKE ? OR name LIKE ? OR ? LIKE '%' || name || '%'
        ORDER BY mention_count DESC
        LIMIT 5
      `).all(`%${entity.name}%`, `${entity.name}%`, entity.name);

      if (related.length > 0) {
        connections.push({
          entity: entity.name,
          relatedTo: related.map(r => r.name),
          connectionType: 'semantic_similarity'
        });
      }
    }

    return connections;
  }

  // ============================================================
  // 同步 Obsidian Vault
  // ============================================================

  async syncObsidian(vaultPath: string): Promise<{
    filesProcessed: number;
    entitiesExtracted: number;
    relationsExtracted: number;
    insightsExtracted: number;
  }> {
    const stats = {
      filesProcessed: 0,
      entitiesExtracted: 0,
      relationsExtracted: 0,
      insightsExtracted: 0
    };

    if (!existsSync(vaultPath)) {
      console.log(`⚠️ Vault 路径不存在: ${vaultPath}`);
      return stats;
    }

    const scanDir = async (dir: string): Promise<string[]> => {
      const files: string[] = [];
      const entries = await readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory() && !['.obsidian', '.trash', '.git'].includes(entry.name)) {
          files.push(...await scanDir(fullPath));
        } else if (entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name))) {
          files.push(fullPath);
        }
      }
      return files;
    };

    const files = await scanDir(vaultPath);
    console.log(`📁 扫描到 ${files.length} 个笔记文件`);

    for (const file of files) {
      try {
        const content = await readFile(file, 'utf-8');

        // 本地提取 (快速)
        const result = this.extractLocally(content);

        // 发现与现有知识的关联
        const connections = this.discoverConnections(result.entities);
        for (const conn of connections) {
          for (const related of conn.relatedTo) {
            result.relations.push({
              from: conn.entity,
              to: related,
              type: 'related_to',
              evidence: '语义相似',
              confidence: 0.6
            });
          }
        }

        // 存入知识库
        this.saveToKnowledgeBase(result, file);

        stats.filesProcessed++;
        stats.entitiesExtracted += result.entities.length;
        stats.relationsExtracted += result.relations.length;
        stats.insightsExtracted += result.key_insights.length;

      } catch (error) {
        console.log(`  ⚠️ 处理失败: ${file}`);
      }
    }

    return stats;
  }

  // ============================================================
  // 查询知识图谱
  // ============================================================

  queryKnowledgeGraph(entity: string): {
    entity: any;
    relations: any[];
    relatedEntities: any[];
    knowledgePoints: any[];
  } {
    // 查询实体
    const entityData = this.db.query<{
      name: string;
      type: string;
      description: string;
      mention_count: number;
    }, [string]>(`
      SELECT name, type, description, mention_count
      FROM cortex_entities
      WHERE name = ? OR name LIKE ?
    `).get(entity, `%${entity}%`);

    // 查询关系
    const relations = this.db.query<{
      from_entity: string;
      to_entity: string;
      relation_type: string;
      evidence: string;
      confidence: number;
    }, [string]>(`
      SELECT from_entity, to_entity, relation_type, evidence, confidence
      FROM cortex_relations
      WHERE from_entity = ? OR to_entity = ?
      ORDER BY confidence DESC
      LIMIT 20
    `).all(entity, entity);

    // 查询相关实体
    const relatedEntities = this.db.query<{
      name: string;
      type: string;
      mention_count: number;
    }, [string, string]>(`
      SELECT DISTINCT e.name, e.type, e.mention_count
      FROM cortex_entities e
      JOIN cortex_relations r ON (e.name = r.from_entity OR e.name = r.to_entity)
      WHERE (r.from_entity = ? OR r.to_entity = ?) AND e.name != ?
      ORDER BY e.mention_count DESC
      LIMIT 10
    `).all(entity, entity, entity);

    // 查询知识点
    const knowledgePoints = this.db.query<{
      content: string;
      source_path: string;
      importance: number;
    }, [string]>(`
      SELECT content, source_path, importance
      FROM cortex_knowledge_points
      WHERE entities LIKE ?
      ORDER BY importance DESC
      LIMIT 10
    `).all(`%${entity}%`);

    return {
      entity: entityData,
      relations,
      relatedEntities,
      knowledgePoints
    };
  }

  // ============================================================
  // 知识图谱统计
  // ============================================================

  stats(): {
    totalEntities: number;
    totalRelations: number;
    totalKnowledgePoints: number;
    topEntities: Array<{ name: string; mention_count: number }>;
    topRelationTypes: Array<{ type: string; count: number }>;
  } {
    const totalEntities = this.db.query<{ count: number }, []>(`
      SELECT COUNT(*) as count FROM cortex_entities
    `).get()?.count || 0;

    const totalRelations = this.db.query<{ count: number }, []>(`
      SELECT COUNT(*) as count FROM cortex_relations
    `).get()?.count || 0;

    const totalKnowledgePoints = this.db.query<{ count: number }, []>(`
      SELECT COUNT(*) as count FROM cortex_knowledge_points
    `).get()?.count || 0;

    const topEntities = this.db.query<{
      name: string;
      mention_count: number;
    }, []>(`
      SELECT name, mention_count FROM cortex_entities
      ORDER BY mention_count DESC LIMIT 10
    `).all();

    const topRelationTypes = this.db.query<{
      type: string;
      count: number;
    }, []>(`
      SELECT relation_type as type, COUNT(*) as count
      FROM cortex_relations
      GROUP BY relation_type
      ORDER BY count DESC LIMIT 10
    `).all();

    return {
      totalEntities,
      totalRelations,
      totalKnowledgePoints,
      topEntities,
      topRelationTypes
    };
  }

  close(): void {
    this.db.close();
  }
}

// ============================================================
// CLI 入口
// ============================================================

async function main() {
  const args = process.argv.slice(2);
  const command = args[0] || 'stats';

  const extractor = new KnowledgeExtractor();

  try {
    switch (command) {
      case 'sync':
        const vaultPath = args[1] || `${process.env.HOME}/Solar/solar know`;
        console.log(`\n📚 同步 Obsidian Vault: ${vaultPath}`);
        const syncResult = await extractor.syncObsidian(vaultPath);
        console.log('\n📊 同步结果:');
        console.log(`  处理文件: ${syncResult.filesProcessed}`);
        console.log(`  提取实体: ${syncResult.entitiesExtracted}`);
        console.log(`  提取关系: ${syncResult.relationsExtracted}`);
        console.log(`  提取洞察: ${syncResult.insightsExtracted}`);
        break;

      case 'query':
        const entity = args[1];
        if (!entity) {
          console.log('用法: bun knowledge-extractor.ts query <实体名>');
          break;
        }
        const queryResult = extractor.queryKnowledgeGraph(entity);
        console.log(`\n🔍 查询 "${entity}" 结果:`);
        if (queryResult.entity) {
          console.log(`\n📍 实体: ${queryResult.entity.name} (${queryResult.entity.type})`);
          console.log(`   提及次数: ${queryResult.entity.mention_count}`);
        }
        console.log(`\n🔗 关系 (${queryResult.relations.length} 条):`);
        for (const r of queryResult.relations.slice(0, 5)) {
          console.log(`   ${r.from_entity} --[${r.relation_type}]--> ${r.to_entity}`);
        }
        console.log(`\n📌 相关实体 (${queryResult.relatedEntities.length} 个):`);
        for (const e of queryResult.relatedEntities.slice(0, 5)) {
          console.log(`   ${e.name} (${e.type}, 提及 ${e.mention_count} 次)`);
        }
        break;

      case 'stats':
      default:
        const s = extractor.stats();
        console.log('\n📊 知识图谱统计:');
        console.log(`  总实体: ${s.totalEntities}`);
        console.log(`  总关系: ${s.totalRelations}`);
        console.log(`  总知识点: ${s.totalKnowledgePoints}`);
        console.log('\n  热门实体:');
        for (const e of s.topEntities.slice(0, 5)) {
          console.log(`    ${e.name}: ${e.mention_count} 次`);
        }
        break;
    }
  } finally {
    extractor.close();
  }
}

main();
