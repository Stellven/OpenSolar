#!/usr/bin/env bun
/**
 * 记忆质量审计 - 每周运行
 *
 * 功能:
 * 1. 统计各类型记忆数量
 * 2. 检查平均置信度
 * 3. 识别待提取的记忆（lesson = "待分析提取"）
 * 4. 生成审计报告
 *
 * 创建时间: 2026-02-20
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('🔍 Solar 记忆系统 - 每周质量审计\n');
console.log('审计时间:', new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }));
console.log('─'.repeat(80));

// 1. 统计各类型记忆
const stats = db.query(`
  SELECT
    namespace,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence
  FROM evo_memory_semantic
  GROUP BY namespace
  ORDER BY count DESC
`).all();

console.log('\n📊 1. 记忆类型统计');
stats.forEach((row: any) => {
  const conf = (row.avg_confidence * 100).toFixed(1);
  console.log(`   ${(row.namespace as string).padEnd(15)}: ${row.count} 条 (平均置信度: ${conf}%)`);
});

// 2. 识别待提取的记忆（容错处理）
const pendingExtractions = db.query(`
  SELECT namespace, COUNT(*) as count
  FROM evo_memory_semantic
  WHERE value LIKE '%待分析提取%'
     OR value LIKE '%待人工分析%'
  GROUP BY namespace
`).all();

if (pendingExtractions.length > 0) {
  console.log('\n⚠️  2. 待提取记忆（需 LLM 处理）');
  pendingExtractions.forEach((row: any) => {
    console.log(`   ${(row.namespace as string).padEnd(15)}: ${row.count} 条待提取`);
  });

  const totalPending = pendingExtractions.reduce((sum: number, row: any) => sum + (row.count as number), 0);
  console.log(`   总计: ${totalPending} 条待提取`);

  // 建议
  if (totalPending > 20) {
    console.log('\n   💡 建议: 运行 knowledge-extractor.ts 自动提取知识');
  }
} else {
  console.log('\n✅ 2. 待提取记忆: 无');
}

// 3. 检查低置信度记忆
const lowConfidence = db.query(`
  SELECT namespace, COUNT(*) as count
  FROM evo_memory_semantic
  WHERE confidence < 0.7
  GROUP BY namespace
`).all();

if (lowConfidence.length > 0) {
  console.log('\n⚠️  3. 低置信度记忆 (< 70%)');
  lowConfidence.forEach((row: any) => {
    console.log(`   ${(row.namespace as string).padEnd(15)}: ${row.count} 条`);
  });
} else {
  console.log('\n✅ 3. 低置信度记忆: 无');
}

// 4. 记忆增长趋势（最近7天）
const recentGrowth = db.query(`
  SELECT
    namespace,
    COUNT(*) as new_count
  FROM evo_memory_semantic
  WHERE created_at >= datetime('now', '-7 days')
  GROUP BY namespace
`).all();

console.log('\n📈 4. 最近7天记忆增长');
if (recentGrowth.length > 0) {
  recentGrowth.forEach((row: any) => {
    console.log(`   ${(row.namespace as string).padEnd(15)}: +${row.new_count} 条`);
  });

  const totalGrowth = recentGrowth.reduce((sum: number, row: any) => sum + (row.new_count as number), 0);
  console.log(`   总计: +${totalGrowth} 条 (7天增长)`);

  // 目标检查
  if (totalGrowth >= 30) {
    console.log('   ✅ 达到目标 (>= 30 条/周)');
  } else {
    console.log('   ⚠️  低于目标 (< 30 条/周)，考虑增加反馈采集频率');
  }
} else {
  console.log('   无新增记忆');
}

// 5. 偏好记忆分析
const preferences = db.query(`
  SELECT
    json_extract(value, '$.type') as preference_type,
    COUNT(*) as count
  FROM evo_memory_semantic
  WHERE namespace = 'preferences'
  GROUP BY preference_type
`).all();

if (preferences.length > 0) {
  console.log('\n🎯 5. 用户偏好分析');
  preferences.forEach((row: any) => {
    console.log(`   ${row.preference_type}: ${row.count} 条`);
  });
}

// 6. 总体健康度评分
const totalMemories = db.query(`
  SELECT COUNT(*) as total FROM evo_memory_semantic
`).get() as any;

const avgConfidence = db.query(`
  SELECT AVG(confidence) as avg FROM evo_memory_semantic
`).get() as any;

console.log('\n' + '─'.repeat(80));
console.log('📊 总体健康度:');
console.log(`   总记忆数: ${totalMemories.total} 条`);
console.log(`   平均置信度: ${(avgConfidence.avg * 100).toFixed(1)}%`);

let healthScore = 100;
if (totalMemories.total < 200) healthScore -= 20;
if (avgConfidence.avg < 0.8) healthScore -= 15;
if (pendingExtractions.length > 0) healthScore -= 10;

console.log(`   健康评分: ${healthScore}/100`);

if (healthScore >= 90) {
  console.log('   状态: ✅ 优秀');
} else if (healthScore >= 70) {
  console.log('   状态: ⚠️  良好（有改进空间）');
} else {
  console.log('   状态: 🔴 需要关注');
}

console.log('\n审计完成 ✅');

db.close();
