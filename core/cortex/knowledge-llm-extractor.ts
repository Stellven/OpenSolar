#!/usr/bin/env bun
/**
 * Knowledge LLM Extractor - LLM 驱动的知识抽取器
 *
 * 功能：
 * 1. 调用 brain-router HTTP API 提取结构化知识
 * 2. 注入 D&D KNOBS 人格（从 niumao-anchors.json 读取）
 * 3. 22 种语义关系类型（非 co_occurs_in 垃圾）
 * 4. 自动写入 knowledge_entities/relations/claims
 * 5. 高置信度 claims (≥0.7) 自动升级到 cortex_claims
 *
 * @created 2026-02-22
 */

import { Database } from 'bun:sqlite';
import { readFileSync } from 'fs';
import { callLLM } from './llm-api-client';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const ANCHORS_PATH = `${process.env.HOME}/.claude/core/solar-farm/niumao-anchors.json`;

// ============================================================
// 22 种语义关系类型
// ============================================================

const VALID_RELATION_TYPES = new Set([
  // 人物关系
  'mentor_of', 'student_of', 'collaborator_with', 'founded_by',
  // 技术关系
  'evolved_from', 'enables', 'requires', 'alternative_to', 'component_of', 'extends',
  // 时间关系
  'preceded_by', 'succeeded_by', 'concurrent_with',
  // 因果关系
  'caused_by', 'leads_to', 'mitigates',
  // 学术关系
  'cited_by', 'builds_upon', 'contradicts', 'validates',
  // 层级关系
  'part_of', 'instance_of',
]);

// ============================================================
// 类型定义
// ============================================================

interface ExtractionResult {
  entities: Array<{
    name: string;
    type: 'person' | 'technology' | 'concept' | 'org' | 'framework' | 'tool' | 'other';
    description: string;
  }>;
  relations: Array<{
    from: string;
    to: string;
    type: string;
    evidence: string;
    confidence: number;
  }>;
  claims: Array<{
    text: string;
    confidence: number;
    supporting_entities: string[];
    evidence: string;
    domain?: string;
  }>;
  model_used: string;
  extraction_time_ms: number;
}

interface ExtractionOptions {
  model?: string;
  sourceId?: string;
  favoriteId?: number;
  temperature?: number;
}

// ============================================================
// D&D KNOBS 人格加载
// ============================================================

function loadAnchorSystemPrompt(modelKey: string): string | null {
  try {
    const anchors = JSON.parse(readFileSync(ANCHORS_PATH, 'utf-8'));
    if (anchors[modelKey]?.system_prompt) {
      return anchors[modelKey].system_prompt;
    }
  } catch {
    // anchors file not found or parse error
  }
  return null;
}

/**
 * 构建知识抽取专用的 system prompt
 * 基于 D&D KNOBS SYSTEM CORE v0.2 格式
 */
function buildExtractionSystemPrompt(model: string): string {
  // 尝试从 niumao-anchors 加载基础人格
  const anchorPrompt = loadAnchorSystemPrompt(model);

  // 知识抽取专用的 OUTPUT_SCHEMA
  const extractionSchema = `
## OUTPUT_SCHEMA (知识抽取专用)

你是一名知识图谱专家。从给定文本中抽取结构化知识。

### 实体类型
person | technology | concept | org | framework | tool | other

### 关系类型 (22 种语义关系，必须从中选择)
人物关系: mentor_of, student_of, collaborator_with, founded_by
技术关系: evolved_from, enables, requires, alternative_to, component_of, extends
时间关系: preceded_by, succeeded_by, concurrent_with
因果关系: caused_by, leads_to, mitigates
学术关系: cited_by, builds_upon, contradicts, validates
层级关系: part_of, instance_of

### 输出 JSON 格式
{
  "entities": [
    { "name": "实体名(统一命名)", "type": "类型", "description": "一句话描述" }
  ],
  "relations": [
    { "from": "实体A", "to": "实体B", "type": "上述22种之一", "evidence": "原文依据", "confidence": 0.0-1.0 }
  ],
  "claims": [
    { "text": "核心论断(20-60字)", "confidence": 0.0-1.0, "supporting_entities": ["实体名"], "evidence": "支撑证据", "domain": "领域" }
  ]
}

### 质量要求
1. 实体名称统一：同一实体只用一个名称，优先英文原名
2. 关系必须有意义：不提取共现关系，只提取语义关系
3. 每条关系必须有 evidence（原文依据）
4. claims 精炼：一个论断一个核心观点
5. confidence 基于证据强度：直接陈述=0.9, 推断=0.7, 猜测=0.5
6. 只输出 JSON，不要其他内容`;

  if (anchorPrompt) {
    // 有 anchor: 在基础人格后追加知识抽取 schema
    return `${anchorPrompt}\n\n${extractionSchema}`;
  }

  // 无 anchor (如 glm-5): 构建完整的 system prompt
  return `# SYSTEM CORE v0.2

## ROLE
你是建设者(builder)，一个严谨高效的知识图谱抽取专家。

## KNOBS
rigor=4, skepticism=3, exploration=2, decisiveness=4, riskAversion=3
toolFirst=4, compression=4, selfCritique=3, socialEmpathy=2, competitiveness=2

## HARD RULES
- 只输出合法 JSON，不输出任何其他文字
- 关系类型必须从 22 种中选择
- 实体名称必须统一，不重复
- 每条关系必须有 evidence 字段
- confidence 基于证据强度评估

${extractionSchema}`;
}

// ============================================================
// JSON 解析（容错）
// ============================================================

function parseExtractionJSON(raw: string): {
  entities: any[];
  relations: any[];
  claims: any[];
} {
  // 尝试直接解析
  try {
    const parsed = JSON.parse(raw);
    return {
      entities: parsed.entities || [],
      relations: parsed.relations || [],
      claims: parsed.claims || [],
    };
  } catch {
    // 从文本中提取 JSON
  }

  // 尝试提取 JSON 块
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error('未找到 JSON 输出');
  }

  const parsed = JSON.parse(jsonMatch[0]);
  return {
    entities: parsed.entities || [],
    relations: parsed.relations || [],
    claims: parsed.claims || [],
  };
}

// ============================================================
// 关系类型验证和修正
// ============================================================

function normalizeRelationType(type: string): string | null {
  const normalized = type.toLowerCase().trim();
  if (VALID_RELATION_TYPES.has(normalized)) {
    return normalized;
  }

  // 常见别名映射
  const aliases: Record<string, string> = {
    'based_on': 'builds_upon',
    'basis_for': 'builds_upon',
    'uses': 'requires',
    'used_by': 'enables',
    'created_by': 'founded_by',
    'invented_by': 'founded_by',
    'developed_by': 'founded_by',
    'depends_on': 'requires',
    'related_to': '', // 丢弃无意义关系
    'co_occurs_in': '', // 丢弃垃圾关系
    'similar_to': 'alternative_to',
    'replaces': 'succeeded_by',
    'replaced_by': 'preceded_by',
    'supports': 'validates',
    'implements': 'extends',
    'includes': 'component_of',
    'contains': 'component_of',
    'derived_from': 'evolved_from',
    'inspired_by': 'builds_upon',
    'competes_with': 'alternative_to',
    'works_with': 'enables',
    'teaches': 'mentor_of',
    'learns_from': 'student_of',
  };

  if (aliases[normalized] !== undefined) {
    return aliases[normalized] || null; // empty string = discard
  }

  return null; // unknown type, discard
}

// ============================================================
// 规则回退抽取（LLM 失败时）
// ============================================================

function fallbackExtract(text: string): {
  entities: any[];
  relations: any[];
  claims: any[];
} {
  const entities: any[] = [];
  const relations: any[] = [];
  const claims: any[] = [];

  // 简单的命名实体识别（正则）
  const techPatterns = [
    /\b(GPT-\d[\w.-]*|Claude[\w.-]*|Gemini[\w.-]*|LLaMA[\w.-]*|Mistral[\w.-]*)\b/gi,
    /\b(Python|TypeScript|JavaScript|Rust|Go|Java|C\+\+)\b/g,
    /\b(React|Vue|Angular|Next\.js|Svelte)\b/g,
    /\b(Docker|Kubernetes|Redis|PostgreSQL|MongoDB|SQLite)\b/g,
    /\b(TensorFlow|PyTorch|JAX|MLX)\b/g,
    /\b(Transformer|BERT|GPT|Attention|RAG|MoE)\b/g,
  ];

  const seen = new Set<string>();
  for (const pattern of techPatterns) {
    const matches = text.matchAll(pattern);
    for (const match of matches) {
      const name = match[0];
      if (!seen.has(name.toLowerCase())) {
        seen.add(name.toLowerCase());
        entities.push({
          name,
          type: 'technology',
          description: `Extracted from text via pattern matching`,
        });
      }
    }
  }

  return { entities, relations, claims };
}

// ============================================================
// 核心：知识抽取函数
// ============================================================

export async function extractKnowledge(
  text: string,
  options: ExtractionOptions = {}
): Promise<ExtractionResult> {
  const model = options.model || 'glm-5';
  const temperature = options.temperature ?? 0.3;
  const startTime = Date.now();

  // 截断过长文本（保留前 4000 字符）
  const truncatedText = text.length > 4000 ? text.substring(0, 4000) + '\n...(截断)' : text;

  const systemPrompt = buildExtractionSystemPrompt(model);
  const userPrompt = `请从以下文本中抽取结构化知识，输出 JSON：

---
${truncatedText}
---

只输出 JSON，不要其他内容。`;

  let rawEntities: any[] = [];
  let rawRelations: any[] = [];
  let rawClaims: any[] = [];
  let usedModel = model;

  try {
    const raw = await callLLM(model, systemPrompt, userPrompt, temperature);
    const parsed = parseExtractionJSON(raw);
    rawEntities = parsed.entities;
    rawRelations = parsed.relations;
    rawClaims = parsed.claims;
  } catch (error: any) {
    console.error(`   LLM 抽取失败 (${model}): ${error.message}`);
    console.error(`   降级到规则抽取...`);
    const fallback = fallbackExtract(text);
    rawEntities = fallback.entities;
    rawRelations = fallback.relations;
    rawClaims = fallback.claims;
    usedModel = 'fallback-regex';
  }

  // 验证和清理关系类型
  const validRelations = rawRelations
    .map(r => ({
      ...r,
      type: normalizeRelationType(r.type),
    }))
    .filter(r => r.type !== null && r.type !== '');

  // 验证实体类型
  const validEntityTypes = new Set(['person', 'technology', 'concept', 'org', 'framework', 'tool', 'other']);
  const validEntities = rawEntities.map(e => ({
    ...e,
    type: validEntityTypes.has(e.type) ? e.type : 'other',
  }));

  // 验证 claims
  const validClaims = rawClaims.filter(c => c.text && c.text.length > 5);

  return {
    entities: validEntities,
    relations: validRelations,
    claims: validClaims,
    model_used: usedModel,
    extraction_time_ms: Date.now() - startTime,
  };
}

// ============================================================
// 数据库写入
// ============================================================

export function writeExtractionToDb(
  db: Database,
  result: ExtractionResult,
  sourceDoc?: string
): {
  entitiesWritten: number;
  relationsWritten: number;
  claimsWritten: number;
  cortexClaimsUpgraded: number;
} {
  let entitiesWritten = 0;
  let relationsWritten = 0;
  let claimsWritten = 0;
  let cortexClaimsUpgraded = 0;

  // 1. 写入实体 (UPSERT)
  const entityStmt = db.prepare(`
    INSERT INTO knowledge_entities (name, type, description, importance)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(name) DO UPDATE SET
      description = CASE
        WHEN length(excluded.description) > length(COALESCE(description, ''))
        THEN excluded.description
        ELSE description
      END,
      importance = MAX(excluded.importance, importance),
      updated_at = CURRENT_TIMESTAMP,
      access_count = access_count + 1
  `);

  for (const entity of result.entities) {
    try {
      entityStmt.run(
        entity.name,
        entity.type,
        entity.description || '',
        0.6 // default importance
      );
      entitiesWritten++;
    } catch (error: any) {
      // silent: duplicate or constraint violation
    }
  }

  // 2. 写入关系 (INSERT OR IGNORE, type 已在抽取阶段验证)
  const relationStmt = db.prepare(`
    INSERT OR IGNORE INTO knowledge_relations
    (from_entity, to_entity, relation_type, evidence, confidence, source_doc)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  for (const rel of result.relations) {
    try {
      relationStmt.run(
        rel.from,
        rel.to,
        rel.type,
        rel.evidence || '',
        rel.confidence ?? 0.5,
        sourceDoc || ''
      );
      relationsWritten++;
    } catch (error: any) {
      // silent: duplicate
    }
  }

  // 3. 写入 knowledge_claims
  const claimStmt = db.prepare(`
    INSERT INTO knowledge_claims
    (claim_text, supporting_entities, supporting_sources, confidence, domain)
    VALUES (?, ?, ?, ?, ?)
  `);

  // 4. 高置信度 claims 升级到 cortex_claims
  // cortex_claims schema: claim_id, task_id, claim_text, supporting_sources, counter_sources, expert_model, confidence, created_at
  const cortexClaimStmt = db.prepare(`
    INSERT INTO cortex_claims
    (task_id, claim_text, supporting_sources, counter_sources, confidence, created_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
  `);

  for (const claim of result.claims) {
    try {
      claimStmt.run(
        claim.text,
        JSON.stringify(claim.supporting_entities || []),
        JSON.stringify(sourceDoc ? [sourceDoc] : []),
        claim.confidence ?? 0.5,
        claim.domain || 'general'
      );
      claimsWritten++;

      // 自动升级: confidence >= 0.7 → cortex_claims
      if ((claim.confidence ?? 0) >= 0.7) {
        try {
          cortexClaimStmt.run(
            sourceDoc || 'knowledge_extraction',  // task_id (NOT NULL)
            claim.text,
            JSON.stringify(sourceDoc ? [sourceDoc] : []),  // supporting_sources
            JSON.stringify([]),  // counter_sources
            claim.confidence
          );
          cortexClaimsUpgraded++;
        } catch {
          // cortex_claims 可能没有 UNIQUE 约束，忽略
        }
      }
    } catch (error: any) {
      // silent
    }
  }

  return { entitiesWritten, relationsWritten, claimsWritten, cortexClaimsUpgraded };
}

// ============================================================
// 便捷函数：抽取 + 写入一体化
// ============================================================

export async function extractAndStore(
  text: string,
  options: ExtractionOptions = {}
): Promise<{
  extraction: ExtractionResult;
  writeResult: ReturnType<typeof writeExtractionToDb>;
}> {
  const db = new Database(DB_PATH);
  try {
    const extraction = await extractKnowledge(text, options);
    const sourceDoc = options.sourceId || options.favoriteId?.toString() || undefined;

    db.run('BEGIN TRANSACTION');
    try {
      const writeResult = writeExtractionToDb(db, extraction, sourceDoc);
      db.run('COMMIT');
      return { extraction, writeResult };
    } catch (error) {
      db.run('ROLLBACK');
      throw error;
    }
  } finally {
    db.close();
  }
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const subcommand = args[0];

  if (subcommand === 'extract') {
    // 从 stdin 或参数读取文本
    const text = args[1] || await Bun.stdin.text();
    if (!text.trim()) {
      console.error('用法: bun knowledge-llm-extractor.ts extract "文本内容"');
      console.error('  或: echo "文本" | bun knowledge-llm-extractor.ts extract');
      process.exit(1);
    }

    const model = args.find(a => a.startsWith('--model='))?.split('=')[1] || 'glm-5';

    console.log(`🧠 知识抽取器 (model: ${model})\n`);
    console.log(`📝 输入文本: ${text.substring(0, 80)}...`);
    console.log();

    const { extraction, writeResult } = await extractAndStore(text, { model });

    console.log(`✅ 抽取完成 (${extraction.extraction_time_ms}ms, model: ${extraction.model_used})`);
    console.log();
    console.log(`📊 抽取结果:`);
    console.log(`   实体: ${extraction.entities.length}`);
    console.log(`   关系: ${extraction.relations.length}`);
    console.log(`   结论: ${extraction.claims.length}`);
    console.log();
    console.log(`💾 写入结果:`);
    console.log(`   实体写入: ${writeResult.entitiesWritten}`);
    console.log(`   关系写入: ${writeResult.relationsWritten}`);
    console.log(`   结论写入: ${writeResult.claimsWritten}`);
    console.log(`   升级到 cortex_claims: ${writeResult.cortexClaimsUpgraded}`);

    if (extraction.entities.length > 0) {
      console.log();
      console.log(`👤 实体列表:`);
      for (const e of extraction.entities) {
        console.log(`   [${e.type}] ${e.name}: ${e.description}`);
      }
    }

    if (extraction.relations.length > 0) {
      console.log();
      console.log(`🔗 关系列表:`);
      for (const r of extraction.relations) {
        console.log(`   ${r.from} --[${r.type}]--> ${r.to} (${r.confidence})`);
      }
    }

    if (extraction.claims.length > 0) {
      console.log();
      console.log(`📋 结论列表:`);
      for (const c of extraction.claims) {
        const star = (c.confidence ?? 0) >= 0.7 ? ' ⭐→cortex' : '';
        console.log(`   [${c.confidence}] ${c.text}${star}`);
      }
    }

  } else if (subcommand === 'test') {
    // 测试模式：用样例文本测试抽取
    const testText = `
Transformer 架构由 Google Brain 团队的 Vaswani 等人在 2017 年提出，
论文《Attention Is All You Need》开创了自注意力机制的先河。
BERT 由 Google 的 Jacob Devlin 开发，基于 Transformer 编码器，
在 2018 年刷新了 11 项 NLP 基准。GPT 系列由 OpenAI 开发，
基于 Transformer 解码器，从 GPT-1 到 GPT-4 经历了多次迭代。
LLaMA 是 Meta AI 推出的开源大模型系列，被认为是开源 LLM 的重要里程碑。
RAG（Retrieval-Augmented Generation）将检索系统与生成模型结合，
有效缓解了大模型的幻觉问题。
    `.trim();

    const model = args.find(a => a.startsWith('--model='))?.split('=')[1] || 'glm-5';

    console.log(`🧪 测试模式 (model: ${model})\n`);
    const result = await extractKnowledge(testText, { model });

    console.log(`⏱️  耗时: ${result.extraction_time_ms}ms`);
    console.log(`🤖 模型: ${result.model_used}`);
    console.log();
    console.log(`📊 抽取结果:`);
    console.log(`   实体: ${result.entities.length}`);
    for (const e of result.entities) {
      console.log(`     [${e.type}] ${e.name}`);
    }
    console.log(`   关系: ${result.relations.length}`);
    for (const r of result.relations) {
      console.log(`     ${r.from} --[${r.type}]--> ${r.to}`);
    }
    console.log(`   结论: ${result.claims.length}`);
    for (const c of result.claims) {
      console.log(`     [${(c.confidence ?? 0).toFixed(1)}] ${c.text}`);
    }

  } else if (subcommand === 'types') {
    // 显示支持的关系类型
    console.log('📋 支持的 22 种语义关系类型:\n');
    const categories: Record<string, string[]> = {
      '人物关系': ['mentor_of', 'student_of', 'collaborator_with', 'founded_by'],
      '技术关系': ['evolved_from', 'enables', 'requires', 'alternative_to', 'component_of', 'extends'],
      '时间关系': ['preceded_by', 'succeeded_by', 'concurrent_with'],
      '因果关系': ['caused_by', 'leads_to', 'mitigates'],
      '学术关系': ['cited_by', 'builds_upon', 'contradicts', 'validates'],
      '层级关系': ['part_of', 'instance_of'],
    };
    for (const [cat, types] of Object.entries(categories)) {
      console.log(`  ${cat}:`);
      for (const t of types) {
        console.log(`    - ${t}`);
      }
    }

  } else {
    console.log('🧠 Knowledge LLM Extractor\n');
    console.log('用法:');
    console.log('  bun knowledge-llm-extractor.ts extract "文本" [--model=glm-5]');
    console.log('  bun knowledge-llm-extractor.ts test [--model=glm-5]');
    console.log('  bun knowledge-llm-extractor.ts types');
    console.log();
    console.log('支持的模型:');
    console.log('  glm-5 (默认，日常抽取)');
    console.log('  deepseek-r1 (深度推理，复杂内容)');
    console.log('  deepseek-v3 (创意抽取)');
    console.log('  gemini-2.5-pro (严谨审查)');
  }
}
