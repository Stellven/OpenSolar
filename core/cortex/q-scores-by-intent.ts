#!/usr/bin/env bun
/**
 * Q-scores 按意图统计更新器
 * 从 evo_traces 和 evo_feedback_v2 中按 intent 分组统计质量分数
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('📊 开始按意图统计 Q-scores...\n');

// 1. 统计各意图的质量分数
const intentScores = db.query(`
  SELECT
    'intent' as entity_type,
    json_extract(t.intent, '$.primary') as entity_id,
    COUNT(*) as sample_size,
    AVG(CASE WHEN t.status IN ('completed', 'success') THEN 1.0 ELSE 0.0 END) as completion_rate
  FROM evo_traces t
  WHERE t.intent IS NOT NULL
    AND t.intent != '{}'
    AND json_extract(t.intent, '$.primary') IS NOT NULL
  GROUP BY json_extract(t.intent, '$.primary')
  HAVING sample_size > 0
  ORDER BY sample_size DESC
`).all() as any[];

console.log(`📝 统计到 ${intentScores.length} 个意图类型\n`);

if (intentScores.length === 0) {
  console.log('⚠️  没有找到意图数据');
  db.close();
  process.exit(0);
}

// 2. 写入 sys_quality_scores
const insertStmt = db.prepare(`
  INSERT OR REPLACE INTO sys_quality_scores
  (score_id, entity_type, entity_id, sample_size, completion_rate, calculated_at)
  VALUES (
    lower(hex(randomblob(16))),
    ?, ?, ?, ?,
    datetime('now')
  )
`);

db.run('BEGIN TRANSACTION');

try {
  let inserted = 0;
  for (const score of intentScores) {
    insertStmt.run(
      score.entity_type,
      score.entity_id,
      score.sample_size,
      score.completion_rate || 0
    );
    inserted++;

    console.log(`   ${score.entity_id.padEnd(15)} samples=${String(score.sample_size).padStart(5)} ` +
                `comp=${((score.completion_rate || 0) * 100).toFixed(1).padStart(5)}%`);
  }

  db.run('COMMIT');
  console.log(`\n✅ 成功更新 ${inserted} 个意图的 Q-scores`);

} catch (error) {
  db.run('ROLLBACK');
  throw error;
}

// 3. 验证结果
const totalIntentScores = db.query(`
  SELECT COUNT(*) as count
  FROM sys_quality_scores
  WHERE entity_type = 'intent'
`).get() as any;

console.log(`\n📊 数据库中共有 ${totalIntentScores.count} 个意图 Q-scores`);

// 4. 显示 Top-5 完成率
const topCompletion = db.query(`
  SELECT entity_id, sample_size, completion_rate
  FROM sys_quality_scores
  WHERE entity_type = 'intent' AND sample_size >= 50
  ORDER BY completion_rate DESC
  LIMIT 5
`).all() as any[];

console.log('\n🏆 Top-5 完成率 (样本≥50):');
topCompletion.forEach((s, i) => {
  console.log(`   ${i + 1}. ${s.entity_id.padEnd(15)} ${(s.completion_rate * 100).toFixed(1)}% (${s.sample_size} samples)`);
});

// 5. 显示 Bottom-3 完成率
const bottomCompletion = db.query(`
  SELECT entity_id, sample_size, completion_rate
  FROM sys_quality_scores
  WHERE entity_type = 'intent' AND sample_size >= 50
  ORDER BY completion_rate ASC
  LIMIT 3
`).all() as any[];

console.log('\n⚠️  Bottom-3 完成率 (样本≥50):');
bottomCompletion.forEach((s, i) => {
  console.log(`   ${i + 1}. ${s.entity_id.padEnd(15)} ${(s.completion_rate * 100).toFixed(1)}% (${s.sample_size} samples)`);
});

db.close();

console.log('\n🎉 Q-scores 意图统计完成!');
