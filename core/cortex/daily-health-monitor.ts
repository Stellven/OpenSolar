#!/usr/bin/env bun
/**
 * 自演进闭环系统每日健康监控
 *
 * 监控指标：
 * 1. 路由规则覆盖率
 * 2. GLM-5 调用频率
 * 3. 整体满意度
 * 4. 平均完成率
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('📊 Solar 自演进闭环系统 - 每日健康报告\n');
console.log('生成时间:', new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }));
console.log('─'.repeat(80));

// 1. 路由规则覆盖率
const routingStats = db.query(`
  SELECT
    json_extract(conditions, '$.task_type') as task_type,
    COUNT(*) as rule_count
  FROM sys_routing_model
  WHERE enabled = 1
  GROUP BY task_type
`).all();

const totalRules = routingStats.reduce((sum, r) => sum + (r.rule_count as number), 0);
const taskTypes = routingStats.length;

console.log('\n📌 1. 路由规则覆盖率');
console.log(`   总规则数: ${totalRules} 条 (目标: >= 20)`);
console.log(`   任务类型: ${taskTypes} 种`);
routingStats.forEach(r => {
  console.log(`   - ${(r.task_type as string).padEnd(10)}: ${r.rule_count} 条`);
});

// 2. GLM-5 调用统计
const glm5Stats = db.query(`
  SELECT
    COUNT(*) as total_calls,
    SUM(CASE WHEN selected_model = 'glm-5' THEN 1 ELSE 0 END) as glm5_calls
  FROM sroe_requests
  WHERE timestamp >= datetime('now', '-7 days')
`).get();

const glm5CallRate = (glm5Stats.glm5_calls as number / glm5Stats.total_calls as number * 100).toFixed(1);

console.log('\n📌 2. GLM-5 调用频率（最近7天）');
console.log(`   总调用: ${glm5Stats.total_calls} 次`);
console.log(`   GLM-5 调用: ${glm5Stats.glm5_calls} 次 (${glm5CallRate}%)`);
console.log(`   目标: 下降 50%（当前基线: ${glm5CallRate}%）`);

// 3. 整体满意度
const satisfactionStats = db.query(`
  SELECT
    AVG(satisfaction) * 100 as avg_satisfaction,
    COUNT(*) as sample_count
  FROM sys_quality_scores
  WHERE entity_type = 'model'
`).get();

console.log('\n📌 3. 整体满意度');
console.log(`   平均满意度: ${(satisfactionStats.avg_satisfaction as number).toFixed(1)}% (目标: >= 93%)`);
console.log(`   样本数量: ${satisfactionStats.sample_count} 个模型`);

// 4. 平均完成率
const completionStats = db.query(`
  SELECT
    AVG(completion_rate) * 100 as avg_completion,
    entity_type
  FROM sys_quality_scores
  WHERE entity_type = 'model'
  GROUP BY entity_type
`).all();

console.log('\n📌 4. 平均完成率（按实体类型）');
completionStats.forEach(s => {
  console.log(`   - ${(s.entity_type as string).padEnd(10)}: ${(s.avg_completion as number).toFixed(1)}%`);
});

// 5. GLM-5 详细表现
const glm5Quality = db.query(`
  SELECT
    satisfaction,
    completion_rate,
    sample_size
  FROM sys_quality_scores
  WHERE entity_id = 'glm-5' AND entity_type = 'model'
`).get();

if (glm5Quality) {
  console.log('\n📌 5. GLM-5 详细表现');
  console.log(`   满意度: ${((glm5Quality.satisfaction as number) * 100).toFixed(1)}%`);
  console.log(`   完成率: ${((glm5Quality.completion_rate as number) * 100).toFixed(1)}%`);
  console.log(`   样本数: ${glm5Quality.sample_size} 次`);

  // 告警判断（基于完成率）
  if ((glm5Quality.completion_rate as number) < 0.7) {
    console.log('\n   🔴 警告: GLM-5 完成率 < 70%');
  }
}

// 6. 告警检查
console.log('\n📌 6. 系统健康告警');
const alerts = [];

if (totalRules < 20) {
  alerts.push(`路由规则不足: ${totalRules} 条 < 20 条`);
}

if ((satisfactionStats.avg_satisfaction as number) < 93) {
  alerts.push(`满意度偏低: ${(satisfactionStats.avg_satisfaction as number).toFixed(1)}% < 93%`);
}

if (glm5Quality && (glm5Quality.completion_rate as number) < 0.7) {
  alerts.push(`GLM-5 完成率过低: ${((glm5Quality.completion_rate as number) * 100).toFixed(1)}% < 70%`);
}

if (alerts.length === 0) {
  console.log('   ✅ 系统健康，无告警');
} else {
  console.log(`   ⚠️ 发现 ${alerts.length} 个告警:`);
  alerts.forEach((alert, i) => {
    console.log(`   ${i + 1}. ${alert}`);
  });
}

console.log('\n' + '─'.repeat(80));
console.log('报告生成完成 ✅');
