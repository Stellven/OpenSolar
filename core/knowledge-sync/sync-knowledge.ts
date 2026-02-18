#!/usr/bin/env bun
/**
 * 三层知识库同步机制
 *
 * Level 1: sys_favorites (高价值存档) - 原始内容
 * Level 2: Cortex (中枢神经) - 结构化来源
 * Level 3: Knowledge Graph (知识图谱) - 实体/关系/结论
 *
 * 同步流程：
 * 1. 扫描 sys_favorites 中未同步的内容
 * 2. 提取实体、关系、规则
 * 3. 注入到 Knowledge Graph
 * 4. 更新同步状态
 */

import { Database } from 'bun:sqlite';

const DB_PATH = process.env.SOLAR_DB || expandPath('~/.solar/solar.db');

function expandPath(path: string): string {
  if (path.startsWith('~')) {
    return path.replace('~', process.env.HOME || '');
  }
  return path;
}

interface Favorite {
  favorite_id: number;
  title: string;
  question: string;
  answer: string;
  tags: string;
  importance: number;
  synced_to_graph: number;
}

interface Entity {
  name: string;
  type: string;
  description: string;
  source_id?: number;
  confidence?: number;
}

interface Relation {
  source_entity: string;
  target_entity: string;
  relation_type: string;
  confidence?: number;
  evidence?: string;
}

interface Claim {
  claim_text: string;
  confidence: number;
  source_id?: number;
}

// 实体类型映射
const ENTITY_PATTERNS: Record<string, RegExp> = {
  person: /([A-Z][a-z]+\s+[A-Z][a-z]+|黄仁勋|马斯克|Thiel|Musk|Huang|Wiener)/g,
  technology: /(LLM|GPU|CPU|ANE|MLX|CoreML|CUDA|Transformer|RIFE|AI|Agent|Embedding|Vector|Tantivy|SQLite|TypeScript|Swift)/g,
  concept: /(人格|Big Five|HEXACO|KNOBS|人格工程化|技术官僚|技术治国|控制论|监控资本主义|知识图谱|记忆系统|认知负荷)/g,
  organization: /(NVIDIA|OpenAI|Google|Apple|CSIS|Anthropic)/g,
  framework: /(Solar|Solar Farm|Cortex|REE|TVS|NotebookLM)/g,
  rule: /(铁律|法则|原则|规则)/g,
};

// 关系类型模式
const RELATION_PATTERNS = [
  { pattern: /(\w+)\s+(发明|创建|设计|提出|建立)\s+(\w+)/g, type: 'created_by' },
  { pattern: /(\w+)\s+(属于|是)\s+(\w+)(的|之一)/g, type: 'is_a' },
  { pattern: /(\w+)\s+(包含|包括|由)\s+(\w+)/g, type: 'contains' },
  { pattern: /(\w+)\s+(影响|决定|导致)\s+(\w+)/g, type: 'influences' },
  { pattern: /(\w+)\s+(优于|快于|高于)\s+(\w+)/g, type: 'better_than' },
];

class KnowledgeSync {
  private db: Database;
  private stats = { favorites: 0, entities: 0, relations: 0, claims: 0 };

  constructor() {
    this.db = new Database(DB_PATH);
    this.ensureSchema();
  }

  private ensureSchema(): void {
    // 确保 sys_favorites 有 synced_to_graph 字段
    const tableInfo = this.db.query("PRAGMA table_info(sys_favorites)").all() as any[];
    const hasSyncField = tableInfo.some(col => col.name === 'synced_to_graph');

    if (!hasSyncField) {
      this.db.run("ALTER TABLE sys_favorites ADD COLUMN synced_to_graph INTEGER DEFAULT 0");
      console.log("✓ Added synced_to_graph column to sys_favorites");
    }

    // 确保 knowledge_entities 有 source_favorite_id 字段
    const entityInfo = this.db.query("PRAGMA table_info(knowledge_entities)").all() as any[];
    const hasSourceFav = entityInfo.some(col => col.name === 'source_favorite_id');

    if (!hasSourceFav) {
      this.db.run("ALTER TABLE knowledge_entities ADD COLUMN source_favorite_id INTEGER");
      console.log("✓ Added source_favorite_id column to knowledge_entities");
    }
  }

  async sync(): Promise<void> {
    console.log("🔄 开始三层知识库同步...\n");
    console.log(`📅 ${new Date().toISOString()}\n`);

    // Step 1: 获取未同步的 favorites
    const unsynced = this.getUnsyncedFavorites();
    console.log(`📚 发现 ${unsynced.length} 条未同步的 favorites\n`);

    if (unsynced.length === 0) {
      console.log("✅ 所有内容已同步，无需处理");
      return;
    }

    // Step 2: 逐条处理
    for (const fav of unsynced) {
      await this.processFavorite(fav);
    }

    // Step 3: 输出统计
    this.printStats();
  }

  private getUnsyncedFavorites(): Favorite[] {
    return this.db.query<Favorite>(`
      SELECT favorite_id, title, question, answer, tags, importance,
             COALESCE(synced_to_graph, 0) as synced_to_graph
      FROM sys_favorites
      WHERE COALESCE(synced_to_graph, 0) = 0
      ORDER BY importance DESC, created_at DESC
      LIMIT 50
    `).all();
  }

  private async processFavorite(fav: Favorite): Promise<void> {
    console.log(`📝 处理: ${fav.title.substring(0, 50)}...`);

    const content = `${fav.title}\n\n${fav.question}\n\n${fav.answer}`;

    // 提取实体
    const entities = this.extractEntities(content, fav.favorite_id);

    // 提取关系
    const relations = this.extractRelations(content);

    // 提取结论/规则
    const claims = this.extractClaims(fav);

    // 注入到 Knowledge Graph
    this.injectEntities(entities);
    this.injectRelations(relations);
    this.injectClaims(claims, fav.favorite_id);

    // 标记为已同步
    this.db.run(
      "UPDATE sys_favorites SET synced_to_graph = 1 WHERE favorite_id = ?",
      [fav.favorite_id]
    );

    this.stats.favorites++;
    console.log(`   ✓ 实体: ${entities.length}, 关系: ${relations.length}, 结论: ${claims.length}\n`);
  }

  private extractEntities(content: string, sourceId: number): Entity[] {
    const entities: Entity[] = [];
    const seen = new Set<string>();

    for (const [type, pattern] of Object.entries(ENTITY_PATTERNS)) {
      const matches = content.matchAll(pattern);
      for (const match of matches) {
        const name = match[1] || match[0];
        if (name && name.length > 1 && !seen.has(name.toLowerCase())) {
          seen.add(name.toLowerCase());
          entities.push({
            name,
            type,
            description: `${type} entity from sys_favorites`,
            source_id: sourceId,
            confidence: 0.8,
          });
        }
      }
    }

    // 从 tags 提取
    try {
      const tags = JSON.parse(content.match(/tags.*?\[.*?\]/s)?.[0] || '[]');
      for (const tag of tags) {
        if (!seen.has(tag.toLowerCase())) {
          seen.add(tag.toLowerCase());
          entities.push({
            name: tag,
            type: 'tag',
            description: `Tag from sys_favorites`,
            source_id: sourceId,
            confidence: 0.9,
          });
        }
      }
    } catch {}

    return entities;
  }

  private extractRelations(content: string): Relation[] {
    const relations: Relation[] = [];

    for (const { pattern, type } of RELATION_PATTERNS) {
      const matches = content.matchAll(pattern);
      for (const match of matches) {
        if (match[1] && match[3]) {
          relations.push({
            source_entity: match[1],
            target_entity: match[3],
            relation_type: type,
            confidence: 0.7,
            evidence: match[0],
          });
        }
      }
    }

    return relations;
  }

  private extractClaims(fav: Favorite): Claim[] {
    const claims: Claim[] = [];

    // 从 answer 中提取结论句
    const sentences = fav.answer.split(/[。！？\n]/).filter(s => s.length > 20);

    // 识别规则/结论句
    const claimPatterns = [
      /^(必须|禁止|应该|需要|核心|关键|铁律|法则)/,
      /(是|等于|优于|快于|高于|低于)/,
      /(→|→|=>|导致|意味着)/,
    ];

    for (const sentence of sentences.slice(0, 5)) { // 最多取5条
      const isClaim = claimPatterns.some(p => p.test(sentence));
      if (isClaim || sentence.includes('铁律') || sentence.includes('规则')) {
        claims.push({
          claim_text: sentence.trim().substring(0, 200),
          confidence: fav.importance / 10,
        });
      }
    }

    // 标题本身也是一条结论
    if (fav.title.includes('铁律') || fav.title.includes('规则') || fav.title.includes('架构')) {
      claims.push({
        claim_text: fav.title,
        confidence: fav.importance / 10,
      });
    }

    return claims;
  }

  private injectEntities(entities: Entity[]): void {
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO knowledge_entities (name, type, description, source_favorite_id, importance)
      VALUES (?, ?, ?, ?, ?)
    `);

    for (const entity of entities) {
      try {
        stmt.run(entity.name, entity.type, entity.description, entity.source_id, entity.confidence || 0.8);
        this.stats.entities++;
      } catch (e) {
        // 忽略重复
      }
    }
  }

  private injectRelations(relations: Relation[]): void {
    // 直接用实体名称作为 from_entity/to_entity
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO knowledge_relations (from_entity, to_entity, relation_type, confidence, evidence)
      VALUES (?, ?, ?, ?, ?)
    `);

    for (const rel of relations) {
      if (rel.source_entity && rel.target_entity && rel.source_entity !== rel.target_entity) {
        try {
          stmt.run(rel.source_entity, rel.target_entity, rel.relation_type, rel.confidence || 0.7, rel.evidence || '');
          this.stats.relations++;
        } catch (e) {
          // 忽略重复
        }
      }
    }
  }

  private injectClaims(claims: Claim[], sourceId: number): void {
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO knowledge_claims (claim_text, confidence, domain)
      VALUES (?, ?, 'synced_favorite')
    `);

    for (const claim of claims) {
      try {
        stmt.run(claim.claim_text, claim.confidence);
        this.stats.claims++;
      } catch (e) {
        // 忽略重复
      }
    }
  }

  private printStats(): void {
    console.log("\n" + "═".repeat(50));
    console.log("📊 同步完成统计");
    console.log("═".repeat(50));
    console.log(`  📚 处理 favorites: ${this.stats.favorites}`);
    console.log(`  🏷️  注入实体: ${this.stats.entities}`);
    console.log(`  🔗 注入关系: ${this.stats.relations}`);
    console.log(`  📝 注入结论: ${this.stats.claims}`);
    console.log("═".repeat(50));

    // 查询当前知识库状态
    const stats = this.db.query<{
      favorites: number;
      entities: number;
      relations: number;
      claims: number;
    }>(`
      SELECT
        (SELECT COUNT(*) FROM sys_favorites) as favorites,
        (SELECT COUNT(*) FROM knowledge_entities) as entities,
        (SELECT COUNT(*) FROM knowledge_relations) as relations,
        (SELECT COUNT(*) FROM knowledge_claims) as claims
    `).get();

    console.log("\n📈 当前知识库状态:");
    console.log(`   sys_favorites: ${stats?.favorites || 0}`);
    console.log(`   knowledge_entities: ${stats?.entities || 0}`);
    console.log(`   knowledge_relations: ${stats?.relations || 0}`);
    console.log(`   knowledge_claims: ${stats?.claims || 0}`);
  }

  close(): void {
    this.db.close();
  }
}

// 主入口
async function main() {
  const sync = new KnowledgeSync();
  try {
    await sync.sync();
  } finally {
    sync.close();
  }
}

main().catch(console.error);
