#!/usr/bin/env bun
/**
 * Auto-Strategy Tuning - 自动策略调优
 *
 * 功能:
 * 1. 识别失败模式
 * 2. 自动调整路由权重
 * 3. 生成改进建议
 * 4. 预测潜在问题
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface FailurePattern {
  pattern_id: string;
  description: string;
  affected_models: string[];
  frequency: number;
  severity: 'high' | 'medium' | 'low';
}

interface StrategyAdjustment {
  model: string;
  current_weight: number;
  suggested_weight: number;
  reason: string;
  confidence: number;
}

interface ImprovementSuggestion {
  area: string;
  current_state: string;
  suggested_action: string;
  expected_improvement: string;
  priority: 'high' | 'medium' | 'low';
}

export class AutoStrategyTuning {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
  }

  /**
   * 识别失败模式
   */
  identifyFailurePatterns(): FailurePattern[] {
    const patterns: FailurePattern[] = [];

    // 1. 识别高错误率的模型
    const highErrorModels = this.db.query<{
      model: string;
      error_count: number;
      total_count: number;
      error_rate: number;
    }>(`
      SELECT
        selected_model as model,
        COUNT(CASE WHEN finish_reason != 'stop' THEN 1 END) as error_count,
        COUNT(*) as total_count,
        COUNT(CASE WHEN finish_reason != 'stop' THEN 1 END) * 100.0 / COUNT(*) as error_rate
      FROM sroe_requests
      WHERE selected_model IS NOT NULL
      GROUP BY selected_model
      HAVING error_rate > 10
      ORDER BY error_rate DESC
    `).all();

    for (const m of highErrorModels) {
      patterns.push({
        pattern_id: `high_error_${m.model}`,
        description: `模型 ${m.model} 错误率过高 (${m.error_rate.toFixed(1)}%)`,
        affected_models: [m.model],
        frequency: m.error_count,
        severity: m.error_rate > 20 ? 'high' : (m.error_rate > 15 ? 'medium' : 'low')
      });
    }

    // 2. 识别低满意度的模型
    const lowSatisfactionModels = this.db.query<{
      model: string;
      satisfaction: number;
    }>(`
      SELECT
        entity_id as model,
        satisfaction
      FROM sys_quality_scores
      WHERE entity_type = 'model'
        AND satisfaction < 0.8
      ORDER BY satisfaction ASC
    `).all();

    for (const m of lowSatisfactionModels) {
      patterns.push({
        pattern_id: `low_satisfaction_${m.model}`,
        description: `模型 ${m.model} 满意度偏低 (${(m.satisfaction * 100).toFixed(1)}%)`,
        affected_models: [m.model],
        frequency: 1,
        severity: m.satisfaction < 0.6 ? 'high' : (m.satisfaction < 0.7 ? 'medium' : 'low')
      });
    }

    return patterns;
  }

  /**
   * 生成策略调整建议
   */
  generateAdjustments(): StrategyAdjustment[] {
    const adjustments: StrategyAdjustment[] = [];

    // 获取当前路由权重
    const currentWeights = this.db.query<{
      model: string;
      base_weight: number;
      effective_score: number;
    }>(`
      SELECT
        target_model as model,
        base_weight,
        effective_score
      FROM sys_routing_model
      WHERE enabled = 1
    `).all();

    for (const cw of currentWeights) {
      // 获取该模型的 Q-score
      const qScore = this.db.query<{ satisfaction: number }>(`
        SELECT satisfaction
        FROM sys_quality_scores
        WHERE entity_type = 'model' AND entity_id = ?
        ORDER BY calculated_at DESC
        LIMIT 1
      `, [cw.model]).get();

      if (!qScore) continue;

      // 计算建议权重
      let suggestedWeight = cw.base_weight;
      let reason = '';

      if (qScore.satisfaction < 0.7) {
        suggestedWeight = cw.base_weight * 0.8; // 降低20%
        reason = `满意度偏低 (${(qScore.satisfaction * 100).toFixed(1)}%)，建议降低权重`;
      } else if (qScore.satisfaction > 0.95) {
        suggestedWeight = Math.min(cw.base_weight * 1.1, 1.0); // 提升10%
        reason = `表现优秀 (${(qScore.satisfaction * 100).toFixed(1)}%)，建议提升权重`;
      } else {
        reason = '表现稳定，保持当前权重';
      }

      adjustments.push({
        model: cw.model,
        current_weight: cw.base_weight,
        suggested_weight: Math.round(suggestedWeight * 1000) / 1000,
        reason,
        confidence: qScore.satisfaction
      });
    }

    return adjustments;
  }

  /**
   * 生成改进建议
   */
  generateImprovements(): ImprovementSuggestion[] {
    const suggestions: ImprovementSuggestion[] = [];

    // 1. 检查记忆资产
    const memoryCount = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count
      FROM evo_memory_semantic
      WHERE namespace IN ('lessons', 'experiences')
    `).get()?.count || 0;

    if (memoryCount < 200) {
      suggestions.push({
        area: '记忆资产',
        current_state: `当前 ${memoryCount} 条记忆`,
        suggested_action: '增加反馈采集频率，提高记忆沉淀速度',
        expected_improvement: '决策质量提升 10-20%',
        priority: 'medium'
      });
    }

    // 2. 检查归因率
    const attributionRate = this.db.query<{ rate: number }>(`
      SELECT
        COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as rate
      FROM evo_traces
    `).get()?.rate || 0;

    if (attributionRate < 95) {
      suggestions.push({
        area: '数据归因',
        current_state: `归因率 ${attributionRate.toFixed(1)}%`,
        suggested_action: '加强 data-linker 运行频率',
        expected_improvement: '数据质量提升，Q-score 更准确',
        priority: 'high'
      });
    }

    // 3. 检查路由规则覆盖
    const ruleCount = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count FROM sys_routing_model WHERE enabled = 1
    `).get()?.count || 0;

    if (ruleCount < 10) {
      suggestions.push({
        area: '路由规则',
        current_state: `当前 ${ruleCount} 条规则`,
        suggested_action: '运行 routing-rules-initializer 补充规则',
        expected_improvement: '决策覆盖率提升 30%',
        priority: 'low'
      });
    }

    return suggestions;
  }

  /**
   * 生成调优报告
   */
  generateTuningReport(): void {
    console.log('🔧 Auto-Strategy Tuning Report\n');
    console.log('═'.repeat(60) + '\n');

    // 1. 失败模式
    const patterns = this.identifyFailurePatterns();
    if (patterns.length > 0) {
      console.log('⚠️  识别的失败模式:');
      for (const p of patterns) {
        const icon = p.severity === 'high' ? '🔴' : (p.severity === 'medium' ? '🟡' : '🟢');
        console.log(`  ${icon} ${p.description}`);
        console.log(`     影响模型: ${p.affected_models.join(', ')}`);
        console.log(`     发生频次: ${p.frequency} 次\n`);
      }
    } else {
      console.log('✅ 未发现严重失败模式\n');
    }

    // 2. 策略调整建议
    const adjustments = this.generateAdjustments();
    if (adjustments.length > 0) {
      console.log('📊 策略调整建议:');
      for (const a of adjustments) {
        const change = a.suggested_weight - a.current_weight;
        const arrow = change > 0 ? '📈' : (change < 0 ? '📉' : '➡️');

        console.log(`  ${arrow} ${a.model}:`);
        console.log(`     当前权重: ${a.current_weight.toFixed(3)}`);
        console.log(`     建议权重: ${a.suggested_weight.toFixed(3)} (${change > 0 ? '+' : ''}${(change * 100).toFixed(1)}%)`);
        console.log(`     原因: ${a.reason}\n`);
      }
    }

    // 3. 改进建议
    const improvements = this.generateImprovements();
    if (improvements.length > 0) {
      console.log('💡 系统改进建议:');
      for (const i of improvements) {
        const icon = i.priority === 'high' ? '🔥' : (i.priority === 'medium' ? '⭐' : '💡');
        console.log(`  ${icon} [${i.area}] ${i.current_state}`);
        console.log(`     建议行动: ${i.suggested_action}`);
        console.log(`     预期提升: ${i.expected_improvement}\n`);
      }
    }

    console.log('═'.repeat(60));
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    this.generateTuningReport();
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const tuning = new AutoStrategyTuning();
  await tuning.run();
}
