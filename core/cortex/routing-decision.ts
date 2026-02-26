#!/usr/bin/env bun
/**
 * Routing Decision - 路由决策辅助层
 *
 * 功能：
 * 1. 查询 sys_routing_model 获取 effective_score
 * 2. 预过滤候选模型（只保留高质量模型）
 * 3. 返回推荐模型列表供 Brain Router 选择
 *
 * 创建时间: 2026-02-20
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('🎯 Routing Decision 辅助层启动\n');

// 1. 查询当前路由规则及评分
const rules = db.query(`
  SELECT
    rule_name,
    target_model,
    base_weight,
    effective_score,
    conditions,
    description,
    enabled
  FROM sys_routing_model
  WHERE enabled = 1
  ORDER BY effective_score DESC
`).all() as any[];

console.log(`📋 当前路由规则: ${rules.length} 条\n`);

if (rules.length === 0) {
  console.log('⚠️  没有启用的路由规则');
  db.close();
  process.exit(0);
}

// 2. 按模型分组统计
interface ModelStats {
  model_id: string;
  avg_effective_score: number;
  min_effective_score: number;
  max_effective_score: number;
  rule_count: number;
  rules: string[];
}

const modelStats = new Map<string, ModelStats>();

for (const rule of rules) {
  const modelId = rule.target_model;

  if (!modelStats.has(modelId)) {
    modelStats.set(modelId, {
      model_id: modelId,
      avg_effective_score: 0,
      min_effective_score: 1,
      max_effective_score: 0,
      rule_count: 0,
      rules: []
    });
  }

  const stats = modelStats.get(modelId)!;
  stats.rule_count++;
  stats.rules.push(rule.rule_name);
  stats.min_effective_score = Math.min(stats.min_effective_score, rule.effective_score);
  stats.max_effective_score = Math.max(stats.max_effective_score, rule.effective_score);
}

// 计算平均分
modelStats.forEach((stats) => {
  const modelRules = rules.filter(r => r.target_model === stats.model_id);
  stats.avg_effective_score = modelRules.reduce((sum, r) => sum + r.effective_score, 0) / modelRules.length;
});

// 3. 按平均 effective_score 排序
const sortedModels = Array.from(modelStats.values())
  .sort((a, b) => b.avg_effective_score - a.avg_effective_score);

// 4. 输出推荐
console.log('🏆 模型推荐（按平均 effective_score 排序）:\n');
console.log('排名 | 模型              | 平均分 | 最小-最大  | 规则数 | 推荐级别');
console.log('─'.repeat(80));

sortedModels.forEach((stats, index) => {
  const rank = (index + 1).toString().padStart(2);
  const model = stats.model_id.padEnd(18);
  const avgScore = stats.avg_effective_score.toFixed(3);
  const range = `${stats.min_effective_score.toFixed(2)}-${stats.max_effective_score.toFixed(2)}`.padStart(9);
  const count = stats.rule_count.toString().padStart(3);

  // 推荐级别
  let recommendation = '';
  if (stats.avg_effective_score >= 0.9) {
    recommendation = '⭐⭐⭐ 强烈推荐';
  } else if (stats.avg_effective_score >= 0.8) {
    recommendation = '⭐⭐ 推荐';
  } else if (stats.avg_effective_score >= 0.7) {
    recommendation = '⭐ 可用';
  } else if (stats.avg_effective_score >= 0.5) {
    recommendation = '⚠️  谨慎使用';
  } else {
    recommendation = '❌ 不推荐';
  }

  console.log(`${rank}  | ${model} | ${avgScore} | ${range} | ${count}    | ${recommendation}`);
});

// 5. 预过滤建议
const threshold = 0.7;
const recommendedModels = sortedModels.filter(m => m.avg_effective_score >= threshold);

console.log('\n─'.repeat(80));
console.log(`\n📊 预过滤建议（effective_score >= ${threshold}）:\n`);
console.log(`   推荐模型: ${recommendedModels.map(m => m.model_id).join(', ')}`);
console.log(`   数量: ${recommendedModels.length}/${sortedModels.length}`);

// 6. 生成配置建议
console.log('\n─'.repeat(80));
console.log('\n💡 Brain Router 配置建议:\n');

console.log('方案 1: 高质量模型优先');
console.log(`  候选模型: ${recommendedModels.slice(0, 5).map(m => m.model_id).join(', ')}`);
console.log(`  过滤阈值: effective_score >= ${threshold}\n`);

console.log('方案 2: 分层路由');
console.log('  Tier 1 (≥0.9): ' + sortedModels.filter(m => m.avg_effective_score >= 0.9).map(m => m.model_id).join(', '));
console.log('  Tier 2 (0.8-0.9): ' + sortedModels.filter(m => m.avg_effective_score >= 0.8 && m.avg_effective_score < 0.9).map(m => m.model_id).join(', '));
console.log('  Tier 3 (0.7-0.8): ' + sortedModels.filter(m => m.avg_effective_score >= 0.7 && m.avg_effective_score < 0.8).map(m => m.model_id).join(', '));

// 7. 输出 JSON 供程序使用
const decision = {
  timestamp: new Date().toISOString(),
  threshold,
  recommended_models: recommendedModels.map(m => ({
    model_id: m.model_id,
    avg_effective_score: m.avg_effective_score,
    min_effective_score: m.min_effective_score,
    max_effective_score: m.max_effective_score,
    rule_count: m.rule_count
  })),
  all_models: sortedModels.map(m => ({
    model_id: m.model_id,
    avg_effective_score: m.avg_effective_score
  }))
};

console.log('\n─'.repeat(80));
console.log('\n📄 JSON 输出（可保存到文件）:\n');
console.log(JSON.stringify(decision, null, 2));

db.close();

console.log('\n\n🎉 Routing Decision 分析完成!');
