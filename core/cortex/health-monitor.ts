#!/usr/bin/env bun
import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');
const alerts: any[] = [];

console.log('🔍 Solar 系统健康监控 - ' + new Date().toLocaleString('zh-CN'));
console.log('─'.repeat(80));

// 1. GLM-5 表现
const glm5 = db.query("SELECT satisfaction, completion_rate, sample_size FROM sys_quality_scores WHERE entity_id = 'glm-5'").get() as any;
if (glm5 && glm5.completion_rate < 0.7) {
  alerts.push({level: 'critical', msg: `GLM-5 完成率过低: ${(glm5.completion_rate * 100).toFixed(1)}%`});
}
console.log('\n📌 1. GLM-5:', glm5 ? `${(glm5.satisfaction * 100).toFixed(1)}% 满意度, ${(glm5.completion_rate * 100).toFixed(1)}% 完成率` : '无数据');

// 2. 整体满意度
const sat = db.query("SELECT AVG(satisfaction) * 100 as avg FROM sys_quality_scores WHERE entity_type = 'model'").get() as any;
if (sat && sat.avg < 80) {
  alerts.push({level: 'warning', msg: `整体满意度偏低: ${sat.avg.toFixed(1)}%`});
}
console.log('📌 2. 整体满意度:', sat ? `${sat.avg.toFixed(1)}%` : '无数据');

// 3. Agent 失败
const agents = db.query("SELECT entity_id, satisfaction FROM sys_quality_scores WHERE entity_type = 'agent' AND satisfaction < 0.5").all();
if (agents.length > 0) {
  agents.forEach((a: any) => alerts.push({level: 'warning', msg: `${a.entity_id} 满意度低: ${(a.satisfaction * 100).toFixed(1)}%`}));
}
console.log('📌 3. 低满意度 Agent:', agents.length, '个');

// 4. 告警输出
console.log('\n' + '─'.repeat(80));
if (alerts.length === 0) {
  console.log('✅ 系统健康，无告警');
} else {
  console.log(`⚠️  发现 ${alerts.length} 个告警:`);
  alerts.forEach(a => console.log(`${a.level === 'critical' ? '🔴' : '🟡'} ${a.msg}`));
}

db.close();
