#!/usr/bin/env bun
/**
 * Knowledge Query - 知识库查询接口
 *
 * 使用方式：
 *   bun knowledge-query.ts search "GPU推理优化"
 *   bun knowledge-query.ts entity "Jeff Dean"
 *   bun knowledge-query.ts related "MoE"
 *   bun knowledge-query.ts claims "AGI"
 *   bun knowledge-query.ts stats
 *
 * @version 1.0.0
 */

import { Database } from 'bun:sqlite';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// 查询函数
// ============================================================

function search(keyword: string) {
  console.log(`\n🔍 搜索: "${keyword}"\n`);

  // 1. 搜索实体
  const entities = db.query<{
    name: string;
    type: string;
    description: string;
  }, [string]>(`
    SELECT name, type, description
    FROM knowledge_entities
    WHERE name LIKE ? OR description LIKE ?
    ORDER BY importance DESC
    LIMIT 10
  `).all(`%${keyword}%`, `%${keyword}%`);

  if (entities.length > 0) {
    console.log('📋 相关实体:');
    entities.forEach(e => {
      console.log(`   [${e.type}] ${e.name}: ${e.description?.substring(0, 50) || ''}`);
    });
  }

  // 2. 搜索结论
  const claims = db.query<{
    claim_text: string;
    confidence: number;
  }, [string]>(`
    SELECT claim_text, confidence
    FROM knowledge_claims
    WHERE claim_text LIKE ?
    ORDER BY confidence DESC
    LIMIT 5
  `).all(`%${keyword}%`);

  if (claims.length > 0) {
    console.log('\n💡 相关结论:');
    claims.forEach(c => {
      console.log(`   [${(c.confidence * 100).toFixed(0)}%] ${c.claim_text.substring(0, 80)}...`);
    });
  }

  // 3. 搜索关系
  const relations = db.query<{
    from_entity: string;
    to_entity: string;
    relation_type: string;
    evidence: string;
  }, [string]>(`
    SELECT from_entity, to_entity, relation_type, evidence
    FROM knowledge_relations
    WHERE from_entity LIKE ? OR to_entity LIKE ?
    LIMIT 10
  `).all(`%${keyword}%`, `%${keyword}%`);

  if (relations.length > 0) {
    console.log('\n🔗 相关关系:');
    relations.forEach(r => {
      console.log(`   ${r.from_entity} --[${r.relation_type}]--> ${r.to_entity}`);
    });
  }

  if (entities.length === 0 && claims.length === 0 && relations.length === 0) {
    console.log('   未找到相关内容');
  }
}

function getEntity(name: string) {
  console.log(`\n👤 实体详情: "${name}"\n`);

  const entity = db.query<{
    name: string;
    type: string;
    description: string;
    importance: number;
  }, [string]>(`
    SELECT name, type, description, importance
    FROM knowledge_entities
    WHERE name = ?
  `).get(name);

  if (!entity) {
    console.log('   实体不存在');
    return;
  }

  console.log(`   类型: ${entity.type}`);
  console.log(`   重要性: ${entity.importance}`);
  console.log(`   描述: ${entity.description || '无'}`);

  // 相关实体
  const related = db.query<{
    to_entity: string;
    relation_type: string;
  }, [string]>(`
    SELECT to_entity, relation_type
    FROM knowledge_relations
    WHERE from_entity = ?
    LIMIT 10
  `).all(name);

  if (related.length > 0) {
    console.log('\n   关联实体:');
    related.forEach(r => {
      console.log(`   → ${r.to_entity} (${r.relation_type})`);
    });
  }
}

function getRelated(name: string) {
  console.log(`\n🔗 "${name}" 的关联网络:\n`);

  // 出度关系
  const outgoing = db.query<{
    to_entity: string;
    relation_type: string;
    evidence: string;
  }, [string]>(`
    SELECT to_entity, relation_type, evidence
    FROM knowledge_relations
    WHERE from_entity = ?
    LIMIT 20
  `).all(name);

  // 入度关系
  const incoming = db.query<{
    from_entity: string;
    relation_type: string;
    evidence: string;
  }, [string]>(`
    SELECT from_entity, relation_type, evidence
    FROM knowledge_relations
    WHERE to_entity = ?
    LIMIT 20
  `).all(name);

  if (outgoing.length > 0) {
    console.log('   指向:');
    outgoing.forEach(r => {
      console.log(`   ${name} --[${r.relation_type}]--> ${r.to_entity}`);
    });
  }

  if (incoming.length > 0) {
    console.log('\n   被指向:');
    incoming.forEach(r => {
      console.log(`   ${r.from_entity} --[${r.relation_type}]--> ${name}`);
    });
  }
}

function getClaims(keyword: string) {
  console.log(`\n💡 结论搜索: "${keyword}"\n`);

  const claims = db.query<{
    claim_text: string;
    domain: string;
    confidence: number;
    supporting_sources: string;
  }, [string]>(`
    SELECT claim_text, domain, confidence, supporting_sources
    FROM knowledge_claims
    WHERE claim_text LIKE ?
    ORDER BY confidence DESC
    LIMIT 10
  `).all(`%${keyword}%`);

  if (claims.length === 0) {
    console.log('   未找到相关结论');
    return;
  }

  claims.forEach((c, i) => {
    console.log(`${i + 1}. [${(c.confidence * 100).toFixed(0)}%] ${c.claim_text}`);
    if (c.supporting_sources) {
      try {
        const sources = JSON.parse(c.supporting_sources);
        console.log(`   📄 来源: ${sources[0]?.split('/').pop()}`);
      } catch {}
    }
    console.log('');
  });
}

function stats() {
  console.log('\n📊 知识库统计:\n');

  const entityCount = db.query<{ count: number }>(`
    SELECT COUNT(*) as count FROM knowledge_entities
  `).get();

  const relationCount = db.query<{ count: number }>(`
    SELECT COUNT(*) as count FROM knowledge_relations
  `).get();

  const claimCount = db.query<{ count: number }>(`
    SELECT COUNT(*) as count FROM knowledge_claims
  `).get();

  const typeDist = db.query<{ type: string; count: number }>(`
    SELECT type, COUNT(*) as count
    FROM knowledge_entities
    GROUP BY type
    ORDER BY count DESC
  `).all();

  console.log(`   实体: ${entityCount?.count}`);
  console.log(`   关系: ${relationCount?.count}`);
  console.log(`   结论: ${claimCount?.count}`);
  console.log('\n   实体类型分布:');
  typeDist.forEach(t => {
    console.log(`   ${t.type}: ${t.count}`);
  });

  // 高置信度结论
  const topClaims = db.query<{ claim_text: string; confidence: number }>(`
    SELECT claim_text, confidence
    FROM knowledge_claims
    ORDER BY confidence DESC
    LIMIT 5
  `).all();

  console.log('\n   高置信度结论:');
  topClaims.forEach((c, i) => {
    console.log(`   ${i + 1}. [${(c.confidence * 100).toFixed(0)}%] ${c.claim_text.substring(0, 60)}...`);
  });
}

// ============================================================
// CLI 入口
// ============================================================

const [command, arg] = process.argv.slice(2);

switch (command) {
  case 'search':
    if (!arg) {
      console.log('用法: bun knowledge-query.ts search "关键词"');
      break;
    }
    search(arg);
    break;

  case 'entity':
    if (!arg) {
      console.log('用法: bun knowledge-query.ts entity "实体名"');
      break;
    }
    getEntity(arg);
    break;

  case 'related':
    if (!arg) {
      console.log('用法: bun knowledge-query.ts related "实体名"');
      break;
    }
    getRelated(arg);
    break;

  case 'claims':
    if (!arg) {
      console.log('用法: bun knowledge-query.ts claims "关键词"');
      break;
    }
    getClaims(arg);
    break;

  case 'stats':
    stats();
    break;

  default:
    console.log(`
📚 Solar 知识库查询工具

用法:
  bun knowledge-query.ts search "关键词"   - 搜索实体和结论
  bun knowledge-query.ts entity "名称"    - 查看实体详情
  bun knowledge-query.ts related "名称"   - 查看关联网络
  bun knowledge-query.ts claims "关键词"  - 搜索结论
  bun knowledge-query.ts stats            - 查看统计

示例:
  bun knowledge-query.ts search "GPU"
  bun knowledge-query.ts entity "Jeff Dean"
  bun knowledge-query.ts claims "AGI"
`);
}

db.close();
