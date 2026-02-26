#!/usr/bin/env bun
/**
 * 更新现有轨迹的意图分类
 * 从 evo_traces 中读取 intent 为空的轨迹，调用意图分类器并更新
 */

import { Database } from 'bun:sqlite';
import { classifyIntent } from './intent-classifier';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('🔄 开始更新轨迹意图分类...\n');

// 1. 统计待更新的轨迹
const stats = db.query(`
  SELECT
    COUNT(*) as total,
    SUM(CASE WHEN intent = '{}' OR intent IS NULL THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN intent != '{}' AND intent IS NOT NULL THEN 1 ELSE 0 END) as done
  FROM evo_traces
`).get() as any;

console.log(`📊 统计:`);
console.log(`   总轨迹数: ${stats.total}`);
console.log(`   待更新: ${stats.pending}`);
console.log(`   已分类: ${stats.done}\n`);

if (stats.pending === 0) {
  console.log('✅ 所有轨迹已完成意图分类');
  db.close();
  process.exit(0);
}

// 2. 读取待更新的轨迹
const traces = db.query(`
  SELECT trace_id, user_query
  FROM evo_traces
  WHERE intent = '{}' OR intent IS NULL
  ORDER BY started_at DESC
`).all() as any[];

console.log(`📝 本次处理: ${traces.length} 条轨迹\n`);

// 3. 批量更新
const updateStmt = db.prepare(`
  UPDATE evo_traces
  SET intent = ?
  WHERE trace_id = ?
`);

let updated = 0;
let errors = 0;

const startTime = Date.now();

for (const trace of traces) {
  try {
    const intentResult = classifyIntent(trace.user_query);
    updateStmt.run(JSON.stringify(intentResult), trace.trace_id);
    updated++;

    if (updated % 100 === 0) {
      console.log(`   进度: ${updated}/${traces.length}`);
    }
  } catch (error: any) {
    errors++;
    if (errors <= 5) {
      console.error(`   ⚠️  更新失败 [${trace.trace_id}]: ${error.message}`);
    }
  }
}

const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

// 4. 输出结果
console.log(`\n✅ 更新完成!`);
console.log(`   成功: ${updated}`);
console.log(`   失败: ${errors}`);
console.log(`   耗时: ${elapsed}s`);
console.log(`   速度: ${(updated / parseFloat(elapsed)).toFixed(1)} 条/秒`);

// 5. 验证结果
const afterStats = db.query(`
  SELECT
    SUM(CASE WHEN intent = '{}' OR intent IS NULL THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN intent != '{}' AND intent IS NOT NULL THEN 1 ELSE 0 END) as done
  FROM evo_traces
`).get() as any;

console.log(`\n📊 更新后统计:`);
console.log(`   待更新: ${afterStats.pending}`);
console.log(`   已分类: ${afterStats.done}`);

if (afterStats.pending > 0) {
  console.log(`\n💡 提示: 还有 ${afterStats.pending} 条待更新，可再次运行此脚本`);
}

db.close();
