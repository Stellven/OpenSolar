#!/usr/bin/env bun
/**
 * 自演进闭环系统 - 快速状态查询
 *
 * 快速查看闭环系统健康状态
 */

import { Database } from 'bun:sqlite';
import path from 'path';

const dbPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
const db = new Database(dbPath);

console.log('🔄 Solar 自演进闭环系统 - 快速状态\n');
console.log('═'.repeat(70));

// 1. 数据流完整性
console.log('\n📊 数据流完整性:');
const traceAttribution = db.query<{rate: number}>(`
  SELECT COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as rate
  FROM evo_traces
`).get()!;
console.log(`  Trace 归因率: ${traceAttribution.rate.toFixed(1)}% ${traceAttribution.rate > 80 ? '✅' : '⚠️'}`);

const qScores = db.query<{count: number}>(`SELECT COUNT(*) as count FROM sys_quality_scores`).get()!;
console.log(`  Q-scores: ${qScores.count} 条 ${qScores.count > 30 ? '✅' : '⚠️'}`);

const routingRules = db.query<{count: number}>(`SELECT COUNT(*) as count FROM sys_routing_model WHERE effective_score IS NOT NULL`).get()!;
console.log(`  路由规则: ${routingRules.count} 条 ${routingRules.count > 20 ? '✅' : '⚠️'}`);

const memories = db.query<{count: number}>(`
  SELECT COUNT(*) as count FROM evo_memory_semantic WHERE namespace IN ('lessons', 'experiences')
`).get()!;
console.log(`  记忆资产: ${memories.count} 条 ${memories.count > 100 ? '✅' : '⚠️'}`);

// 2. 定时任务状态
console.log('\n⏰ 定时任务状态:');
const tasks = [
  'com.solar.data-linker',
  'com.solar.routing-score-updater',
  'com.solar.feedback-to-memory',
  'com.solar.intelligence-metrics',
  'com.solar.auto-strategy-tuning'
];

const { execSync } = require('child_process');
let runningCount = 0;
for (const task of tasks) {
  try {
    const result = execSync(`launchctl list | grep "${task}"`, { encoding: 'utf-8' }).trim();
    if (result) {
      console.log(`  ✅ ${task}`);
      runningCount++;
    }
  } catch {
    console.log(`  ❌ ${task}`);
  }
}
console.log(`  运行率: ${(runningCount / tasks.length * 100).toFixed(0)}%`);

// 3. Top-5 模型
console.log('\n🏆 Top-5 模型 (按满意度):');
const topModels = db.query<{entity_id: string, satisfaction: number, samples: number}>(`
  SELECT entity_id, satisfaction, sample_size as samples
  FROM sys_quality_scores
  WHERE entity_type = 'model' AND sample_size > 10
  ORDER BY satisfaction DESC
  LIMIT 5
`).all();

topModels.forEach((m, i) => {
  console.log(`  ${i + 1}. ${m.entity_id.padEnd(25)} ${(m.satisfaction * 100).toFixed(1)}% (${m.samples} samples)`);
});

// 4. 综合评分
console.log('\n' + '═'.repeat(70));
const traceScore = traceAttribution.rate > 80 ? 100 : traceAttribution.rate;
const qScore = Math.min(100, qScores.count / 30 * 100);
const routingScore = Math.min(100, routingRules.count / 20 * 100);
const memoryScore = Math.min(100, memories.count / 100 * 100);
const taskScore = runningCount / tasks.length * 100;

const overallHealth = (traceScore + qScore + routingScore + memoryScore + taskScore) / 5;

console.log(`\n🎯 综合健康度: ${overallHealth.toFixed(0)}/100`);
if (overallHealth >= 90) {
  console.log('   状态: ✅ 优秀');
} else if (overallHealth >= 75) {
  console.log('   状态: ✅ 良好');
} else if (overallHealth >= 60) {
  console.log('   状态: ⚠️ 需改进');
} else {
  console.log('   状态: ❌ 需修复');
}

console.log('\n' + '═'.repeat(70));
console.log('\n💡 详细报告: ~/.solar/reports/closed-loop-health-YYYYMMDD.md');
console.log('   手动运行智能指标: bun ~/.claude/core/cortex/intelligence-metrics.ts');
console.log('   手动运行策略调优: bun ~/.claude/core/cortex/auto-strategy-tuning.ts\n');

db.close();
