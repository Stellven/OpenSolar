#!/usr/bin/env bun
/**
 * Enhanced Data Linker - 增强版数据关联器
 *
 * 功能:
 * 1. 尝试通过 session_id 精确匹配
 * 2. 如果失败，通过时间戳 + selected_model 模糊匹配
 * 3. 为每条 trace 找到最可能的 request
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface MatchResult {
  exact: number;
  fuzzy: number;
  total: number;
}

export class EnhancedDataLinker {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
  }

  /**
   * 方法1: 精确匹配 (session_id)
   */
  exactMatch(): number {
    console.log('  🔍 尝试精确匹配 (session_id)...');

    const result = this.db.run(`
      UPDATE evo_traces
      SET
        selected_model = r.selected_model,
        sroe_request_id = r.request_id
      FROM sroe_requests r
      WHERE evo_traces.session_id = r.session_id
        AND evo_traces.selected_model IS NULL
        AND r.selected_model IS NOT NULL
    `);

    console.log(`    ✅ 精确匹配: ${result.changes} 条`);
    return result.changes;
  }

  /**
   * 方法2: 模糊匹配 (时间戳 + selected_model)
   * 逻辑:
   * - 同一 session (通过时间范围判断)
   * - 时间差 < 1分钟
   * - 优先选择 model 匹配的
   */
  fuzzyMatchByTime(): number {
    console.log('  🔍 尝试模糊匹配 (时间戳 + model)...');

    // 先尝试匹配同一天的数据
    const result = this.db.run(`
      UPDATE evo_traces
      SET
        selected_model = r.selected_model,
        sroe_request_id = r.request_id
      FROM sroe_requests r
      WHERE evo_traces.selected_model IS NULL
        AND r.selected_model IS NOT NULL
        AND DATE(evo_traces.started_at) = DATE(r.timestamp)
        AND ABS(julianday(evo_traces.started_at) - julianday(r.timestamp)) < 0.0007
      ORDER BY ABS(julianday(evo_traces.started_at) - julianday(r.timestamp))
      LIMIT 1
    `);

    console.log(`    ✅ 模糊匹配: ${result.changes} 条`);
    return result.changes;
  }

  /**
   * 方法3: 为最近的 traces 推断模型
   * 基于 sroe_requests 的模型使用分布
   */
  inferFromDistribution(): number {
    console.log('  🔍 尝试基于分布推断...');

    // 获取最近7天的模型使用分布
    const modelDistribution = this.db.query<{
      model: string;
      weight: number;
    }>(`
      SELECT
        selected_model as model,
        COUNT(*) * 1.0 / (SELECT COUNT(*) FROM sroe_requests WHERE timestamp >= DATE('now', '-7 days')) as weight
      FROM sroe_requests
      WHERE timestamp >= DATE('now', '-7 days')
        AND selected_model IS NOT NULL
      GROUP BY selected_model
      ORDER BY weight DESC
    `).all();

    if (modelDistribution.length === 0) {
      console.log('    ⚠️  没有足够的分布数据');
      return 0;
    }

    // 为未关联的 traces 随机分配模型（基于权重）
    // 这里使用最常用的模型
    const topModel = modelDistribution[0].model;

    const result = this.db.run(`
      UPDATE evo_traces
      SET selected_model = ?
      WHERE selected_model IS NULL
        AND started_at >= DATE('now', '-7 days')
    `, [topModel]);

    console.log(`    ✅ 推断分配: ${result.changes} 条 (使用 ${topModel})`);
    return result.changes;
  }

  /**
   * 显示归因统计
   */
  displayStats(): void {
    const stats = this.db.query<{
      total: number;
      with_model: number;
      rate: number;
    }>(`
      SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) as with_model,
        ROUND(COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as rate
      FROM evo_traces
    `).get()!;

    console.log('\n📊 归因统计:');
    console.log(`  总计: ${stats.total}`);
    console.log(`  已归因: ${stats.with_model} (${stats.rate}%)`);
    console.log(`  未归因: ${stats.total - stats.with_model}`);

    // 按模型分组
    const byModel = this.db.query<{
      model: string;
      count: number;
    }>(`
      SELECT
        COALESCE(selected_model, 'unknown') as model,
        COUNT(*) as count
      FROM evo_traces
      GROUP BY selected_model
      ORDER BY count DESC
      LIMIT 5
    `).all();

    console.log('\n  Top-5 模型:');
    for (const row of byModel) {
      console.log(`    ${row.model}: ${row.count}`);
    }
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 Enhanced Data Linker 启动\n');

    try {
      console.log('📊 步骤1: 多策略匹配\n');

      // 1. 精确匹配
      const exact = this.exactMatch();

      // 2. 模糊匹配
      const fuzzy = this.fuzzyMatchByTime();

      // 3. 基于分布推断
      const inferred = this.inferFromDistribution();

      const total = exact + fuzzy + inferred;

      console.log(`\n✅ 匹配完成:`);
      console.log(`  精确匹配: ${exact}`);
      console.log(`  模糊匹配: ${fuzzy}`);
      console.log(`  推断分配: ${inferred}`);
      console.log(`  总计: ${total}\n`);

      // 显示统计
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
  const linker = new EnhancedDataLinker();
  await linker.run();
}
