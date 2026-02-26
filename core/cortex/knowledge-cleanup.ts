#!/usr/bin/env bun
/**
 * Knowledge Cleanup - 知识库垃圾数据清理
 *
 * 清理内容：
 * 1. 删除全部 co_occurs_in 垃圾关系 (~1730 条)
 * 2. 删除低质量 knowledge_claims (从 co_occurs_in 派生)
 * 3. 删除孤立实体 (清理后无任何有意义关系)
 * 4. 保留有意义的非 co_occurs_in 关系 (~23 条)
 * 5. 保留 cortex_sources, cortex_artifacts, cortex_claims
 *
 * @created 2026-02-22
 */

import { Database } from 'bun:sqlite';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// 清理前统计
// ============================================================

function getStats(): Record<string, number> {
  const tables = [
    'knowledge_entities',
    'knowledge_relations',
    'knowledge_claims',
    'cortex_sources',
    'cortex_artifacts',
    'cortex_claims',
  ];

  const stats: Record<string, number> = {};
  for (const t of tables) {
    try {
      const row = db.query(`SELECT COUNT(*) as count FROM ${t}`).get() as any;
      stats[t] = row?.count ?? 0;
    } catch {
      stats[t] = -1; // table doesn't exist
    }
  }
  return stats;
}

function getRelationTypeDistribution(): Array<{ type: string; count: number }> {
  return db.query(`
    SELECT relation_type as type, COUNT(*) as count
    FROM knowledge_relations
    GROUP BY relation_type
    ORDER BY count DESC
  `).all() as any[];
}

function getOrphanedEntityCount(): number {
  const row = db.query(`
    SELECT COUNT(*) as count FROM knowledge_entities
    WHERE name NOT IN (
      SELECT DISTINCT from_entity FROM knowledge_relations
      UNION
      SELECT DISTINCT to_entity FROM knowledge_relations
    )
  `).get() as any;
  return row?.count ?? 0;
}

// ============================================================
// 主逻辑
// ============================================================

console.log('🧹 Knowledge Cleanup - 知识库垃圾数据清理\n');

// --- 清理前 ---
const beforeStats = getStats();
const beforeRelTypes = getRelationTypeDistribution();
const beforeOrphans = getOrphanedEntityCount();

console.log('📊 清理前统计:');
for (const [table, count] of Object.entries(beforeStats)) {
  console.log(`   ${table}: ${count}`);
}
console.log(`\n📋 关系类型分布:`);
for (const r of beforeRelTypes) {
  const pct = ((r.count / beforeStats.knowledge_relations) * 100).toFixed(1);
  console.log(`   ${r.type}: ${r.count} (${pct}%)`);
}
console.log(`\n👻 孤立实体: ${beforeOrphans}`);

// --- 执行清理 ---
console.log('\n🔧 开始清理...\n');

db.run('BEGIN TRANSACTION');

try {
  // Step 1: 删除 co_occurs_in 垃圾关系
  const coOccursResult = db.run(`
    DELETE FROM knowledge_relations WHERE relation_type = 'co_occurs_in'
  `);
  console.log(`   ✅ 删除 co_occurs_in 关系: ${coOccursResult.changes} 条`);

  // Step 2: 删除低质量 knowledge_claims
  // 这些 claims 大多是从 co_occurs_in 关系派生的，置信度低且 domain='general'
  const claimsResult = db.run(`
    DELETE FROM knowledge_claims
    WHERE confidence < 0.5
  `);
  console.log(`   ✅ 删除低质量 claims (confidence < 0.5): ${claimsResult.changes} 条`);

  // 额外删除残余的低价值 claims (domain=general 且无实质内容)
  const generalClaimsResult = db.run(`
    DELETE FROM knowledge_claims
    WHERE domain = 'general'
      AND claim_text LIKE '%co_occurs%'
  `);
  console.log(`   ✅ 删除 co_occurs 派生 claims: ${generalClaimsResult.changes} 条`);

  // Step 3: 删除孤立实体 (清理关系后无任何连接的实体)
  const orphanResult = db.run(`
    DELETE FROM knowledge_entities
    WHERE name NOT IN (
      SELECT DISTINCT from_entity FROM knowledge_relations
      UNION
      SELECT DISTINCT to_entity FROM knowledge_relations
    )
  `);
  console.log(`   ✅ 删除孤立实体: ${orphanResult.changes} 条`);

  // Step 4: 清理 knowledge_source_links 中引用已删除实体的记录
  const linksResult = db.run(`
    DELETE FROM knowledge_source_links
    WHERE entity_id NOT IN (SELECT entity_id FROM knowledge_entities)
  `);
  console.log(`   ✅ 清理失效 source_links: ${linksResult.changes} 条`);

  db.run('COMMIT');
  console.log('\n✅ 清理事务已提交');

} catch (error) {
  db.run('ROLLBACK');
  console.error('\n❌ 清理失败，已回滚:', error);
  process.exit(1);
}

// --- 清理后 ---
const afterStats = getStats();
const afterRelTypes = getRelationTypeDistribution();
const afterOrphans = getOrphanedEntityCount();

console.log('\n📊 清理后统计:');
for (const [table, count] of Object.entries(afterStats)) {
  const before = beforeStats[table];
  const diff = count - before;
  const diffStr = diff === 0 ? '' : ` (${diff > 0 ? '+' : ''}${diff})`;
  console.log(`   ${table}: ${count}${diffStr}`);
}

console.log(`\n📋 剩余关系类型:`);
for (const r of afterRelTypes) {
  console.log(`   ${r.type}: ${r.count}`);
}

console.log(`\n👻 孤立实体: ${afterOrphans}`);

// --- 对比表 ---
console.log('\n┌────────────────────────┬──────────┬──────────┬──────────┐');
console.log('│ 指标                   │ 清理前   │ 清理后   │ 变化     │');
console.log('├────────────────────────┼──────────┼──────────┼──────────┤');

const rows = [
  ['entities', beforeStats.knowledge_entities, afterStats.knowledge_entities],
  ['relations', beforeStats.knowledge_relations, afterStats.knowledge_relations],
  ['claims', beforeStats.knowledge_claims, afterStats.knowledge_claims],
  ['co_occurs_in', beforeRelTypes.find(r => r.type === 'co_occurs_in')?.count ?? 0, afterRelTypes.find(r => r.type === 'co_occurs_in')?.count ?? 0],
  ['orphaned entities', beforeOrphans, afterOrphans],
  ['cortex_sources', beforeStats.cortex_sources, afterStats.cortex_sources],
  ['cortex_claims', beforeStats.cortex_claims, afterStats.cortex_claims],
];

for (const [label, before, after] of rows) {
  const diff = (after as number) - (before as number);
  const diffStr = diff === 0 ? '  -' : `${diff > 0 ? '+' : ''}${diff}`;
  console.log(`│ ${String(label).padEnd(22)} │ ${String(before).padStart(8)} │ ${String(after).padStart(8)} │ ${diffStr.padStart(8)} │`);
}

console.log('└────────────────────────┴──────────┴──────────┴──────────┘');

// --- 验证 ---
console.log('\n🔍 验证:');

const coOccursCheck = db.query(`
  SELECT COUNT(*) as count FROM knowledge_relations WHERE relation_type = 'co_occurs_in'
`).get() as any;
console.log(`   co_occurs_in 残留: ${coOccursCheck.count} (期望: 0) ${coOccursCheck.count === 0 ? '✅' : '❌'}`);

const relTypeCount = afterRelTypes.length;
console.log(`   关系类型数: ${relTypeCount}`);

const cortexIntact = afterStats.cortex_sources === beforeStats.cortex_sources
  && afterStats.cortex_claims === beforeStats.cortex_claims;
console.log(`   cortex 数据完整: ${cortexIntact ? '✅' : '❌'}`);

db.close();
console.log('\n🎉 知识库清理完成!');
