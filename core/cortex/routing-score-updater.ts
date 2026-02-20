#!/usr/bin/env bun
/**
 * Routing Score Updater - 路由评分更新器
 *
 * 功能:
 * 1. 从 sys_quality_scores 读取最新评分
 * 2. 更新 sys_routing_model/agent/tool 的 effective_score
 * 3. 计算: effective_score = base_weight × q_score
 *
 * 解决断点 #2: Q-scores 不影响路由决策
 * 解决断点 #6: 没有自动参数更新
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface UpdateStats {
  models: number;
  agents: number;
  tools: number;
}

interface ScoreStats {
  entity_type: string;
  entity_id: string;
  avg_satisfaction: number;
  sample_count: number;
}

export class RoutingScoreUpdater {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
  }

  /**
   * 更新 Model 路由表的有效评分
   * effective_score = base_weight × q_score
   */
  updateModelScores(): number {
    console.log('  📊 更新 Model 路由评分...');

    const result = this.db.run(`
      UPDATE sys_routing_model
      SET
        effective_score = COALESCE(base_weight, 0.5) * COALESCE(
          (SELECT satisfaction
           FROM sys_quality_scores
           WHERE entity_id = target_model
             AND entity_type = 'model'
           ORDER BY calculated_at DESC
           LIMIT 1),
          0.5
        )
    `);

    console.log(`    ✅ 更新了 ${result.changes} 条 Model 路由`);
    return result.changes;
  }

  /**
   * 更新 Agent 路由表的有效评分
   */
  updateAgentScores(): number {
    console.log('  📊 更新 Agent 路由评分...');

    const result = this.db.run(`
      UPDATE sys_routing_agent
      SET
        effective_score = COALESCE(base_weight, 0.5) * COALESCE(
          (SELECT satisfaction
           FROM sys_quality_scores
           WHERE entity_id = target_agent
             AND entity_type = 'agent'
           ORDER BY calculated_at DESC
           LIMIT 1),
          0.5
        )
    `);

    console.log(`    ✅ 更新了 ${result.changes} 条 Agent 路由`);
    return result.changes;
  }

  /**
   * 更新 Tool 路由表的有效评分
   */
  updateToolScores(): number {
    console.log('  📊 更新 Tool 路由评分...');

    const result = this.db.run(`
      UPDATE sys_routing_tool
      SET
        effective_score = COALESCE(base_weight, 0.5) * COALESCE(
          (SELECT satisfaction
           FROM sys_quality_scores
           WHERE entity_id = target_tool
             AND entity_type = 'skill'
           ORDER BY calculated_at DESC
           LIMIT 1),
          0.5
        )
    `);

    console.log(`    ✅ 更新了 ${result.changes} 条 Tool 路由`);
    return result.changes;
  }

  /**
   * 获取 Q-score 统计信息
   */
  getScoreStats(): ScoreStats[] {
    return this.db.query<ScoreStats>(`
      SELECT
        entity_type,
        entity_id,
        ROUND(AVG(satisfaction), 3) as avg_satisfaction,
        COUNT(*) as sample_count
      FROM sys_quality_scores
      GROUP BY entity_type, entity_id
      ORDER BY entity_type, avg_satisfaction DESC
    `).all();
  }

  /**
   * 显示路由评分统计
   */
  displayStats(): void {
    console.log('\n📊 路由评分统计:');

    // Model 路由
    const modelStats = this.db.query<{
      total: number;
      withScore: number;
      avgScore: number;
    }>(`
      SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN effective_score != 0.5 THEN 1 END) as withScore,
        ROUND(AVG(effective_score), 3) as avgScore
      FROM sys_routing_model
    `).get()!;

    console.log(`  Model: ${modelStats.withScore}/${modelStats.total} 有评分, 平均: ${modelStats.avgScore}`);

    // Agent 路由
    const agentStats = this.db.query<{
      total: number;
      withScore: number;
      avgScore: number;
    }>(`
      SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN effective_score != 0.5 THEN 1 END) as withScore,
        ROUND(AVG(effective_score), 3) as avgScore
      FROM sys_routing_agent
    `).get()!;

    console.log(`  Agent: ${agentStats.withScore}/${agentStats.total} 有评分, 平均: ${agentStats.avgScore}`);

    // Tool 路由
    const toolStats = this.db.query<{
      total: number;
      withScore: number;
      avgScore: number;
    }>(`
      SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN effective_score != 0.5 THEN 1 END) as withScore,
        ROUND(AVG(effective_score), 3) as avgScore
      FROM sys_routing_tool
    `).get()!;

    console.log(`  Tool: ${toolStats.withScore}/${toolStats.total} 有评分, 平均: ${toolStats.avgScore}`);

    // 显示 Top-5 高分 Model
    console.log('\n🏆 Top-5 Model (按 effective_score):');
    const topModels = this.db.query<{
      target_model: string;
      effective_score: number;
      base_weight: number;
    }>(`
      SELECT target_model, effective_score, base_weight
      FROM sys_routing_model
      WHERE enabled = 1
      ORDER BY effective_score DESC
      LIMIT 5
    `).all();

    for (const model of topModels) {
      console.log(`  ${model.target_model}: ${model.effective_score.toFixed(3)} (base: ${model.base_weight})`);
    }
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 Routing Score Updater 启动\n');

    try {
      // 1. 检查 Q-scores 是否有数据
      const qscoreCount = this.db.query<{ count: number }>(`
        SELECT COUNT(*) as count FROM sys_quality_scores
      `).get()?.count || 0;

      if (qscoreCount === 0) {
        console.log('⚠️  警告: sys_quality_scores 表为空');
        console.log('   请先运行 q-score-updater.ts 生成评分');
        return;
      }

      console.log(`📋 已有 ${qscoreCount} 条 Q-scores\n`);

      // 2. 更新路由评分
      const stats: UpdateStats = {
        models: this.updateModelScores(),
        agents: this.updateAgentScores(),
        tools: this.updateToolScores()
      };

      console.log(`\n✅ 更新完成: Models=${stats.models}, Agents=${stats.agents}, Tools=${stats.tools}`);

      // 3. 显示统计
      this.displayStats();

    } catch (error) {
      console.error('❌ 执行失败:', error);
      throw error;
    } finally {
      this.db.close();
    }
  }
}

// CLI 入口
if (import.meta.main) {
  const updater = new RoutingScoreUpdater();
  await updater.run();
}
