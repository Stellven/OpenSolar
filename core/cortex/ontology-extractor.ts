#!/usr/bin/env bun
/**
 * Knowledge Ontology Extractor
 * 使用 Ontology 指导从文本中提取知识图谱
 *
 * 参考 graph_maker 设计
 */

import { Database } from 'bun:sqlite';

const DB_PATH = process.env.HOME + '/.solar/solar.db';

interface OntologyLabel {
  name: string;
  description: string;
  extraction_prompt: string;
  priority: number;
}

interface OntologyRelation {
  name: string;
  description: string;
  extraction_prompt: string;
  source_labels: string[] | null;
  target_labels: string[] | null;
}

interface Entity {
  name: string;
  type: string;
  description?: string;
}

interface Relation {
  source: string;
  target: string;
  relation: string;
}

/**
 * 加载 Ontology 配置
 */
export function loadOntology(): {
  labels: OntologyLabel[];
  relations: OntologyRelation[];
} {
  const db = new Database(DB_PATH);

  const labels = db
    .query(`
      SELECT name, description, extraction_prompt, priority
      FROM knowledge_ontology_labels
      WHERE enabled = TRUE
      ORDER BY priority DESC
    `)
    .all() as OntologyLabel[];

  const relations = db
    .query(`
      SELECT name, description, extraction_prompt, source_labels, target_labels
      FROM knowledge_ontology_relations
      WHERE enabled = TRUE
    `)
    .all() as OntologyRelation[];

  db.close();

  return { labels, relations };
}

/**
 * 生成知识提取的 System Prompt
 */
export function generateExtractionPrompt(): string {
  const { labels, relations } = loadOntology();

  const labelPrompts = labels
    .map((l) => `- **${l.name}**: ${l.extraction_prompt}`)
    .join('\n');

  const relationPrompts = relations
    .slice(0, 10) // 只显示前 10 个常用关系
    .map((r) => `- **${r.name}**: ${r.description}`)
    .join('\n');

  return `你是一个知识图谱提取专家。从文本中提取实体和关系。

## 实体类型 (按优先级排序)

${labelPrompts}

## 关系类型

${relationPrompts}

## 提取规则

1. **优先匹配高优先级类型**：如果不确定，选择优先级更高的类型
2. **使用标准名称**：提取官方/常用名称，不要别名或缩写
3. **保持粒度一致**：同一概念使用相同的实体名
4. **关系要明确**：只提取文本中明确提到的关系，不要推测

## 输出格式

返回 JSON 格式：
\`\`\`json
{
  "entities": [
    {"name": "实体名", "type": "类型", "description": "简短描述"}
  ],
  "relations": [
    {"source": "源实体", "target": "目标实体", "relation": "关系类型"}
  ]
}
\`\`\`
`;
}

/**
 * 获取特定领域的 Ontology
 */
export function getDomainOntology(domain: string): {
  labels: OntologyLabel[];
  relations: OntologyRelation[];
} {
  const db = new Database(DB_PATH);

  // 根据领域过滤相关的实体类型
  const domainFilters: Record<string, string[]> = {
    tech: ['technology', 'framework', 'tool', 'language', 'algorithm'],
    ai: ['technology', 'framework', 'algorithm', 'concept', 'paper'],
    business: ['organization', 'person', 'product', 'event'],
    research: ['paper', 'person', 'concept', 'algorithm', 'method'],
  };

  const types = domainFilters[domain.toLowerCase()] || null;

  let labels: OntologyLabel[];
  if (types) {
    const placeholders = types.map(() => '?').join(',');
    labels = db
      .query(`
        SELECT name, description, extraction_prompt, priority
        FROM knowledge_ontology_labels
        WHERE enabled = TRUE AND name IN (${placeholders})
        ORDER BY priority DESC
      `)
      .all(...types) as OntologyLabel[];
  } else {
    labels = db
      .query(`
        SELECT name, description, extraction_prompt, priority
        FROM knowledge_ontology_labels
        WHERE enabled = TRUE
        ORDER BY priority DESC
      `)
      .all() as OntologyLabel[];
  }

  const relations = db
    .query(`
      SELECT name, description, extraction_prompt, source_labels, target_labels
      FROM knowledge_ontology_relations
      WHERE enabled = TRUE
    `)
    .all() as OntologyRelation[];

  db.close();

  return { labels, relations };
}

/**
 * 将提取的实体和关系写入知识库
 */
export function saveToKnowledgeBase(
  entities: Entity[],
  relations: Relation[],
  sourceId?: string
): { entityCount: number; relationCount: number } {
  const db = new Database(DB_PATH);

  // 插入实体
  const insertEntity = db.prepare(`
    INSERT OR IGNORE INTO knowledge_entities (name, type, description, source_favorite_id)
    VALUES ($name, $type, $description, $sourceId)
  `);

  for (const entity of entities) {
    insertEntity.run({
      $name: entity.name,
      $type: entity.type,
      $description: entity.description || null,
      $sourceId: sourceId || null,
    });
  }

  // 插入关系
  const insertRelation = db.prepare(`
    INSERT OR IGNORE INTO knowledge_relations (from_entity, to_entity, relation_type)
    VALUES ($source, $target, $relation)
  `);

  for (const rel of relations) {
    insertRelation.run({
      $source: rel.source,
      $target: rel.target,
      $relation: rel.relation,
    });
  }

  db.close();

  return {
    entityCount: entities.length,
    relationCount: relations.length,
  };
}

/**
 * 显示当前 Ontology 配置
 */
function showOntology() {
  const { labels, relations } = loadOntology();

  console.log('\n┌─ Knowledge Ontology ─────────────────────────┐');
  console.log('│                                              │');
  console.log('│  📦 实体类型 (%d 个)                          │', labels.length);
  console.log('│  ─────────────────────────────────────────   │');
  for (const label of labels.slice(0, 8)) {
    console.log('│  %-15s %s', label.name, label.description || '');
  }
  if (labels.length > 8) {
    console.log('│  ... 还有 %d 个类型                          │', labels.length - 8);
  }
  console.log('│                                              │');
  console.log('│  🔗 关系类型 (%d 个)                          │', relations.length);
  console.log('│  ─────────────────────────────────────────   │');
  for (const rel of relations.slice(0, 6)) {
    console.log('│  %-20s %s', rel.name, rel.description || '');
  }
  if (relations.length > 6) {
    console.log('│  ... 还有 %d 个关系                          │', relations.length - 6);
  }
  console.log('│                                              │');
  console.log('└──────────────────────────────────────────────┘\n');
}

// CLI 入口
const args = process.argv.slice(2);
const command = args[0];

if (command === 'show' || !command) {
  showOntology();
} else if (command === 'prompt') {
  console.log(generateExtractionPrompt());
} else if (command === 'domain') {
  const domain = args[1] || 'tech';
  const ontology = getDomainOntology(domain);
  console.log(JSON.stringify(ontology, null, 2));
} else {
  console.log(`
Usage:
  bun ontology-extractor.ts show      显示 Ontology 配置
  bun ontology-extractor.ts prompt    生成提取 prompt
  bun ontology-extractor.ts domain    获取领域 Ontology
`);
}
