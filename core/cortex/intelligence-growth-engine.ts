#!/usr/bin/env bun
/**
 * Intelligence Growth Engine - 智能增长引擎
 *
 * 整合三个关键机制:
 * 1. Intelligence Metrics - 智能指标
 * 2. Memory-Driven Decision - 记忆驱动决策
 * 3. Auto-Strategy Tuning - 自动策略调优
 *
 * 创建时间: 2026-02-19
 */

import { IntelligenceMetrics } from './intelligence-metrics';
import { AutoStrategyTuning } from './auto-strategy-tuning';
import { Database } from 'bun:sqlite';
import path from 'path';

export class IntelligenceGrowthEngine {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
  }

  /**
   * 运行完整的智能增长周期
   */
  async runGrowthCycle(): Promise<void> {
    console.log('🚀 Solar 智能增长引擎\n');
    console.log('═'.repeat(70));
    console.log('  让系统越来越智能的三大机制');
    console.log('═'.repeat(70) + '\n');

    // 阶段1: 自我评估
    console.log('📊 阶段1: 智能自我评估');
    console.log('─'.repeat(70) + '\n');

    const metrics = new IntelligenceMetrics();
    await metrics.run();

    console.log('\n');

    // 阶段2: 策略调优
    console.log('🔧 阶段2: 自动策略调优');
    console.log('─'.repeat(70) + '\n');

    const tuning = new AutoStrategyTuning();
    await tuning.run();

    console.log('\n');

    // 阶段3: 总结与建议
    console.log('📋 阶段3: 智能增长总结');
    console.log('─'.repeat(70) + '\n');

    this.generateSummary();
  }

  /**
   * 生成总结
   */
  private generateSummary(): void {
    // 获取关键指标
    const overallScore = this.db.query<{ score: number }>(`
      SELECT
        COALESCE(AVG(satisfaction), 0.5) * 40 +
        COALESCE(AVG(completion_rate), 0.5) * 30 +
        COALESCE(AVG(efficiency), 0.5) * 20 +
        CASE WHEN COUNT(*) > 100 THEN 10 ELSE COUNT(*) * 0.1 END as score
      FROM sys_quality_scores
      WHERE entity_type = 'model'
    `).get()?.score || 50;

    const memoryCount = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count
      FROM evo_memory_semantic
      WHERE namespace IN ('lessons', 'experiences')
    `).get()?.count || 0;

    const ruleCount = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count
      FROM sys_routing_model
      WHERE enabled = 1
    `).get()?.count || 0;

    const traceAttribution = this.db.query<{ rate: number }>(`
      SELECT
        COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as rate
      FROM evo_traces
    `).get()?.rate || 0;

    console.log('📊 核心指标:');
    console.log(`  整体智能分数: ${overallScore.toFixed(1)} / 100`);
    console.log(`  记忆资产: ${memoryCount} 条`);
    console.log(`  路由规则: ${ruleCount} 条`);
    console.log(`  数据归因率: ${traceAttribution.toFixed(1)}%\n`);

    // 智能增长保证机制
    console.log('🔄 智能增长保证机制:\n');

    console.log('  1️⃣  每小时 - 数据关联');
    console.log('     data-linker.ts → 保持 100% 归因率\n');

    console.log('  2️⃣  每4小时 - 评分同步');
    console.log('     routing-score-updater.ts → Q-scores 影响路由\n');

    console.log('  3️⃣  每6小时 - 记忆沉淀');
    console.log('     feedback-to-memory.ts → 积累教训和经验\n');

    console.log('  4️⃣  每天 - 智能评估 (建议新增)');
    console.log('     intelligence-metrics.ts → 评估智能增长\n');

    console.log('  5️⃣  每周 - 策略调优 (建议新增)');
    console.log('     auto-strategy-tuning.ts → 自动优化策略\n');

    // 增长预测
    console.log('📈 智能增长预测:\n');

    const currentLevel = overallScore;
    const weeklyGrowthRate = 0.02; // 假设每周增长 2%

    console.log(`  当前智能: ${currentLevel.toFixed(1)} 分`);
    console.log(`  1周后: ${(currentLevel * (1 + weeklyGrowthRate)).toFixed(1)} 分`);
    console.log(`  1月后: ${(currentLevel * Math.pow(1 + weeklyGrowthRate, 4)).toFixed(1)} 分`);
    console.log(`  3月后: ${(currentLevel * Math.pow(1 + weeklyGrowthRate, 12)).toFixed(1)} 分\n`);

    // 成功标志
    const successIndicators = [
      { name: '记忆资产增长', check: memoryCount > 50 },
      { name: '路由规则完善', check: ruleCount >= 5 },
      { name: '数据归因完整', check: traceAttribution >= 95 },
      { name: '智能分数达标', check: overallScore >= 70 }
    ];

    const passedCount = successIndicators.filter(s => s.check).length;

    console.log('✅ 智能增长标志:');
    for (const s of successIndicators) {
      console.log(`  ${s.check ? '✓' : '✗'} ${s.name}`);
    }
    console.log(`\n  通过: ${passedCount}/${successIndicators.length}\n`);

    if (passedCount === successIndicators.length) {
      console.log('🎉 系统已进入良性循环，会越来越智能！');
    } else {
      console.log('⚠️  系统还在初始化阶段，需要更多时间积累。');
    }

    console.log('\n' + '═'.repeat(70));
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    await this.runGrowthCycle();
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const engine = new IntelligenceGrowthEngine();
  await engine.run();
}
