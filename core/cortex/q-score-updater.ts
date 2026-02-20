#!/usr/bin/env bun
/**
 * Q值质量评分刷新脚本
 * 基于反馈信号和路由请求数据计算质量评分
 */

import { Database } from 'bun:sqlite';
import path from 'path';

// 配置
const CONFIG = {
  periodDays: 30,
  minSampleSize: 5,
  confidenceLevel: 1.96
};

interface UpdateStats {
  modelsUpdated: number;
  skippedLowSample: number;
  errors: string[];
}

class QualityScoreUpdater {
  private db: Database;
  private stats: UpdateStats;

  constructor() {
    const homeDir = process.env.HOME || '.';
    const dbPath = path.join(homeDir, '.solar', 'solar.db');
    this.db = new Database(dbPath);
    this.stats = { modelsUpdated: 0, skippedLowSample: 0, errors: [] };
  }

  /**
   * Wilson 置信区间计算
   */
  private wilsonInterval(p: number, n: number): [number, number] {
    if (n === 0) return [0, 1];
    const z = CONFIG.confidenceLevel;
    const denominator = 1 + z * z / n;
    const center = (p + z * z / (2 * n)) / denominator;
    const halfWidth = (z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denominator;
    return [Math.max(0, center - halfWidth), Math.min(1, center + halfWidth)];
  }

  /**
   * 计算模型质量评分
   */
  private calculateModelScores(): void {
    // 从 sroe_requests 获取每个模型的统计数据
    const query = `
      SELECT
        selected_model as model_id,
        COUNT(*) as total_requests,
        SUM(CASE WHEN finish_reason IN ('stop', 'end_turn', 'complete') THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN error_type IS NULL OR error_type = '' THEN 1 ELSE 0 END) as first_try,
        AVG(latency_ms) as avg_latency,
        AVG(cost_usd) as avg_cost
      FROM sroe_requests
      WHERE timestamp >= date('now', '-${CONFIG.periodDays} days')
        AND selected_model IS NOT NULL
      GROUP BY selected_model
    `;

    const results = this.db.query(query).all() as any[];

    const now = new Date().toISOString();
    const periodStart = new Date(Date.now() - CONFIG.periodDays * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const periodEnd = new Date().toISOString().split('T')[0];
    const period = 'all_time';  // 使用 all_time 避免约束冲突

    const insert = this.db.prepare(`
      INSERT OR REPLACE INTO sys_quality_scores
      (score_id, entity_type, entity_id, completion_rate, first_try_rate,
       satisfaction, efficiency, sample_size, confidence_lower, confidence_upper,
       period, period_start, period_end)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    for (const row of results) {
      if (row.total_requests < CONFIG.minSampleSize) {
        this.stats.skippedLowSample++;
        continue;
      }

      const completionRate = row.completed / row.total_requests;
      const firstTryRate = row.first_try / row.total_requests;

      // 效率计算 (归一化延迟和成本)
      const maxLatency = 10000; // 10秒
      const maxCost = 0.1; // 10美分
      const normalizedLatency = Math.min((row.avg_latency || 0) / maxLatency, 1);
      const normalizedCost = Math.min((row.avg_cost || 0) / maxCost, 1);
      const efficiency = 1 - (normalizedLatency * 0.5 + normalizedCost * 0.5);

      // 满意度暂时用完成率近似 (后续可结合反馈数据)
      const satisfaction = completionRate;

      // 综合评分
      const compositeScore = satisfaction * 0.3 + completionRate * 0.3 + firstTryRate * 0.2 + efficiency * 0.2;
      const [confLower, confUpper] = this.wilsonInterval(compositeScore, row.total_requests);

      try {
        insert.run(
          `model_${row.model_id}_all_time`,
          'model',
          row.model_id,
          Math.round(completionRate * 1000) / 1000,
          Math.round(firstTryRate * 1000) / 1000,
          Math.round(satisfaction * 1000) / 1000,
          Math.round(efficiency * 1000) / 1000,
          row.total_requests,
          Math.round(confLower * 1000) / 1000,
          Math.round(confUpper * 1000) / 1000,
          period,
          periodStart,
          periodEnd
        );
        this.stats.modelsUpdated++;
      } catch (error) {
        this.stats.errors.push(`${row.model_id}: ${error}`);
      }
    }
  }

  /**
   * 计算工具质量评分
   */
  private calculateToolScores(): void {
    // 从反馈数据获取工具统计
    const query = `
      SELECT
        related_tool as tool_id,
        COUNT(*) as total,
        SUM(CASE WHEN signal_type LIKE '%positive%' OR signal_type = 'task_success' THEN 1 ELSE 0 END) as positive,
        SUM(CASE WHEN signal_type LIKE '%negative%' OR signal_type = 'task_failure' THEN 1 ELSE 0 END) as negative
      FROM evo_feedback_v2
      WHERE related_tool IS NOT NULL AND related_tool != ''
        AND created_at >= date('now', '-${CONFIG.periodDays} days')
      GROUP BY related_tool
    `;

    const results = this.db.query(query).all() as any[];

    const now = new Date().toISOString();
    const periodStart = new Date(Date.now() - CONFIG.periodDays * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const periodEnd = new Date().toISOString().split('T')[0];
    const period = 'all_time';  // 使用 all_time 避免约束冲突

    const insert = this.db.prepare(`
      INSERT OR REPLACE INTO sys_quality_scores
      (score_id, entity_type, entity_id, completion_rate, first_try_rate,
       satisfaction, efficiency, sample_size, confidence_lower, confidence_upper,
       period, period_start, period_end)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    for (const row of results) {
      if (row.total < CONFIG.minSampleSize) {
        this.stats.skippedLowSample++;
        continue;
      }

      const satisfaction = ((row.positive || 0) - (row.negative || 0)) / row.total;
      const normalizedSatisfaction = (satisfaction + 1) / 2;

      const [confLower, confUpper] = this.wilsonInterval(normalizedSatisfaction, row.total);

      try {
        insert.run(
          `tool_${row.tool_id}_all_time`,
          'skill',
          row.tool_id,
          0.5, // completion_rate 未知
          0.5, // first_try_rate 未知
          Math.round(normalizedSatisfaction * 1000) / 1000,
          0.5, // efficiency 未知
          row.total,
          Math.round(confLower * 1000) / 1000,
          Math.round(confUpper * 1000) / 1000,
          period,
          periodStart,
          periodEnd
        );
        this.stats.modelsUpdated++;
      } catch (error) {
        this.stats.errors.push(`${row.tool_id}: ${error}`);
      }
    }
  }

  /**
   * 执行更新
   */
  public async run(): Promise<UpdateStats> {
    console.log('🚀 开始刷新Q值质量评分...');

    try {
      // 计算模型评分
      console.log('\n📊 计算模型质量评分...');
      this.calculateModelScores();

      // 计算工具评分
      console.log('📊 计算工具质量评分...');
      this.calculateToolScores();

      // 输出统计
      console.log('\n📈 更新统计:');
      console.log(`   评分更新: ${this.stats.modelsUpdated}`);
      console.log(`   样本不足跳过: ${this.stats.skippedLowSample}`);
      console.log(`   错误数: ${this.stats.errors.length}`);

      if (this.stats.errors.length > 0) {
        console.log('\n❌ 错误详情:');
        this.stats.errors.slice(0, 5).forEach(e => console.log(`   ${e}`));
      }

      // 验证数据
      const count = this.db.query('SELECT COUNT(*) as count FROM sys_quality_scores').get() as { count: number };
      console.log(`\n✅ 总质量评分记录: ${count.count}`);

      console.log('\n🎉 Q值刷新完成！');
      return this.stats;

    } catch (error) {
      console.error('❌ 更新失败:', error);
      throw error;
    } finally {
      this.db.close();
    }
  }
}

// 主函数
async function main() {
  const updater = new QualityScoreUpdater();
  await updater.run();
}

if (import.meta.main) {
  main();
}

export { QualityScoreUpdater };
