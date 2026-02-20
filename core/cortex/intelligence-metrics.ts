#!/usr/bin/env bun
/**
 * Intelligence Metrics - 智能指标计算器
 *
 * 功能:
 * 1. 计算整体智能分数 (0-100)
 * 2. 分领域智能 (编码/分析/创意/通用)
 * 3. 趋势分析 (7天/30天)
 * 4. 生成智能报告
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface IntelligenceScore {
  overall: number;
  coding: number;
  analysis: number;
  creativity: number;
  general: number;
}

interface TrendData {
  period: string;
  avg_satisfaction: number;
  success_rate: number;
  sample_count: number;
}

interface Improvement {
  area: string;
  current: number;
  previous: number;
  change: number;
  trend: 'improving' | 'declining' | 'stable';
}

export class IntelligenceMetrics {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
  }

  /**
   * 计算整体智能分数
   * 公式: satisfaction × 0.4 + completion_rate × 0.3 + efficiency × 0.2 + memory_utilization × 0.1
   */
  calculateOverallIntelligence(): number {
    // 1. Satisfaction (满意度)
    const satisfaction = this.db.query<{ avg: number }>(`
      SELECT COALESCE(AVG(satisfaction), 0.5) as avg
      FROM sys_quality_scores
      WHERE entity_type = 'model'
    `).get()?.avg || 0.5;

    // 2. Completion Rate (完成率)
    const completion = this.db.query<{ avg: number }>(`
      SELECT COALESCE(AVG(completion_rate), 0.5) as avg
      FROM sys_quality_scores
      WHERE entity_type = 'model'
    `).get()?.avg || 0.5;

    // 3. Efficiency (效率)
    const efficiency = this.db.query<{ avg: number }>(`
      SELECT COALESCE(AVG(efficiency), 0.5) as avg
      FROM sys_quality_scores
      WHERE entity_type = 'model'
    `).get()?.avg || 0.5;

    // 4. Memory Utilization (记忆利用率)
    const totalMemory = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count FROM evo_memory_semantic
      WHERE namespace IN ('lessons', 'experiences')
    `).get()?.count || 0;

    const memoryUtilization = Math.min(totalMemory / 100, 1); // 100条为满分

    // 加权平均
    const score =
      satisfaction * 40 +
      completion * 30 +
      efficiency * 20 +
      memoryUtilization * 10;

    return Math.round(score * 100) / 100;
  }

  /**
   * 计算分领域智能
   */
  calculateDomainIntelligence(): IntelligenceScore {
    const domains = this.db.query<{
      entity_id: string;
      avg_score: number;
    }>(`
      SELECT
        entity_id,
        AVG(satisfaction) as avg_score
      FROM sys_quality_scores
      WHERE entity_type = 'task_type'
      GROUP BY entity_id
    `).all();

    const domainMap = new Map(domains.map(d => [d.entity_id, d.avg_score * 100]));

    return {
      overall: this.calculateOverallIntelligence(),
      coding: domainMap.get('coding') || 50,
      analysis: domainMap.get('analysis') || 50,
      creativity: domainMap.get('chinese') || 50, // chinese 作为创意指标
      general: domainMap.get('general') || 50
    };
  }

  /**
   * 计算趋势 (7天 vs 前7天)
   */
  calculateTrends(): Improvement[] {
    // 最近7天
    const recent7Days = this.db.query<TrendData>(`
      SELECT
        'last_7_days' as period,
        AVG(satisfaction) as avg_satisfaction,
        AVG(completion_rate) as success_rate,
        COUNT(*) as sample_count
      FROM sys_quality_scores
      WHERE calculated_at >= DATE('now', '-7 days')
    `).get();

    // 前7天
    const previous7Days = this.db.query<TrendData>(`
      SELECT
        'previous_7_days' as period,
        AVG(satisfaction) as avg_satisfaction,
        AVG(completion_rate) as success_rate,
        COUNT(*) as sample_count
      FROM sys_quality_scores
      WHERE calculated_at >= DATE('now', '-14 days')
        AND calculated_at < DATE('now', '-7 days')
    `).get();

    const improvements: Improvement[] = [];

    // Satisfaction 趋势
    if (recent7Days && previous7Days) {
      const satChange = recent7Days.avg_satisfaction - previous7Days.avg_satisfaction;
      improvements.push({
        area: '用户满意度',
        current: recent7Days.avg_satisfaction * 100,
        previous: previous7Days.avg_satisfaction * 100,
        change: satChange * 100,
        trend: satChange > 0.01 ? 'improving' : (satChange < -0.01 ? 'declining' : 'stable')
      });

      const compChange = recent7Days.success_rate - previous7Days.success_rate;
      improvements.push({
        area: '任务完成率',
        current: recent7Days.success_rate * 100,
        previous: previous7Days.success_rate * 100,
        change: compChange * 100,
        trend: compChange > 0.01 ? 'improving' : (compChange < -0.01 ? 'declining' : 'stable')
      });
    }

    return improvements;
  }

  /**
   * 生成智能报告
   */
  generateReport(): void {
    console.log('🧠 Solar 智能指标报告\n');
    console.log('═'.repeat(50) + '\n');

    // 1. 整体智能
    const scores = this.calculateDomainIntelligence();
    console.log('📊 整体智能分数:');
    console.log(`  综合: ${scores.overall.toFixed(1)} / 100`);

    const grade = scores.overall >= 90 ? 'A (优秀)' :
                  scores.overall >= 80 ? 'B (良好)' :
                  scores.overall >= 70 ? 'C (一般)' :
                  scores.overall >= 60 ? 'D (及格)' : 'F (不及格)';
    console.log(`  等级: ${grade}\n`);

    // 2. 分领域智能
    console.log('📊 分领域智能:');
    console.log(`  编码能力: ${'█'.repeat(Math.floor(scores.coding / 10))}${'░'.repeat(10 - Math.floor(scores.coding / 10))} ${scores.coding.toFixed(1)}`);
    console.log(`  分析能力: ${'█'.repeat(Math.floor(scores.analysis / 10))}${'░'.repeat(10 - Math.floor(scores.analysis / 10))} ${scores.analysis.toFixed(1)}`);
    console.log(`  创意能力: ${'█'.repeat(Math.floor(scores.creativity / 10))}${'░'.repeat(10 - Math.floor(scores.creativity / 10))} ${scores.creativity.toFixed(1)}`);
    console.log(`  通用能力: ${'█'.repeat(Math.floor(scores.general / 10))}${'░'.repeat(10 - Math.floor(scores.general / 10))} ${scores.general.toFixed(1)}\n`);

    // 3. 趋势分析
    const trends = this.calculateTrends();
    if (trends.length > 0) {
      console.log('📈 7天趋势分析:');
      for (const t of trends) {
        const icon = t.trend === 'improving' ? '📈' : (t.trend === 'declining' ? '📉' : '➡️');
        const changeStr = t.change > 0 ? `+${t.change.toFixed(1)}` : t.change.toFixed(1);
        console.log(`  ${icon} ${t.area}: ${t.previous.toFixed(1)} → ${t.current.toFixed(1)} (${changeStr})`);
      }
      console.log();
    }

    // 4. 记忆资产
    const memoryStats = this.db.query<{
      lessons: number;
      experiences: number;
    }>(`
      SELECT
        COUNT(CASE WHEN namespace = 'lessons' THEN 1 END) as lessons,
        COUNT(CASE WHEN namespace = 'experiences' THEN 1 END) as experiences
      FROM evo_memory_semantic
    `).get()!;

    console.log('📚 记忆资产:');
    console.log(`  教训: ${memoryStats.lessons} 条`);
    console.log(`  经验: ${memoryStats.experiences} 条`);
    console.log(`  总计: ${memoryStats.lessons + memoryStats.experiences} 条\n`);

    // 5. 模型能力排名
    const topModels = this.db.query<{
      model: string;
      score: number;
      samples: number;
    }>(`
      SELECT
        entity_id as model,
        ROUND(satisfaction * 100, 1) as score,
        sample_size as samples
      FROM sys_quality_scores
      WHERE entity_type = 'model'
      ORDER BY satisfaction DESC
      LIMIT 5
    `).all();

    console.log('🏆 Top-5 模型:');
    for (let i = 0; i < topModels.length; i++) {
      const m = topModels[i];
      console.log(`  ${i + 1}. ${m.model}: ${m.score} (样本: ${m.samples})`);
    }
    console.log();

    // 6. 改进建议
    console.log('💡 改进建议:');
    const suggestions: string[] = [];

    if (scores.overall < 70) {
      suggestions.push('• 整体智能偏低，建议增加高质量训练数据');
    }

    if (memoryStats.lessons + memoryStats.experiences < 100) {
      suggestions.push('• 记忆资产不足，建议积累更多反馈');
    }

    const decliningAreas = trends.filter(t => t.trend === 'declining');
    if (decliningAreas.length > 0) {
      suggestions.push(`• ${decliningAreas.map(a => a.area).join('、')} 呈下降趋势，需要关注`);
    }

    if (suggestions.length === 0) {
      suggestions.push('• 系统运行良好，继续保持 🎉');
    }

    for (const s of suggestions) {
      console.log(`  ${s}`);
    }

    console.log('\n' + '═'.repeat(50));
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    this.generateReport();
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const metrics = new IntelligenceMetrics();
  await metrics.run();
}
