#!/usr/bin/env bun
/**
 * Batch Data Linker - 批量数据关联器
 *
 * 策略:
 * 为旧数据批量分配模型，基于时间窗口的模型使用分布
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

export class BatchDataLinker {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
  }

  /**
   * 批量分配模型
   * 为未归因的 traces 批量分配最常用的模型
   */
  batchAssign(): number {
    console.log('  📊 批量分配模型...');

    // 获取模型使用分布
    const distribution = this.db.query<{
      model: string;
      count: number;
      weight: number;
    }>(`
      SELECT
        selected_model as model,
        COUNT(*) as count,
        COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sroe_requests WHERE selected_model IS NOT NULL) as weight
      FROM sroe_requests
      WHERE selected_model IS NOT NULL
      GROUP BY selected_model
      ORDER BY count DESC
    `).all();

    console.log('\n  模型使用分布:');
    for (const d of distribution) {
      console.log(`    ${d.model}: ${d.count} 次 (${d.weight.toFixed(1)}%)`);
    }

    // 批量分配（按比例）
    let totalAssigned = 0;

    for (const model of distribution) {
      // 计算应该分配多少条
      const targetCount = Math.ceil(model.weight / 100 * 29491); // 29491 是未归因的 traces

      const result = this.db.run(`
        UPDATE evo_traces
        SET selected_model = ?
        WHERE selected_model IS NULL
        LIMIT ?
      `, [model.model, targetCount]);

      totalAssigned += result.changes;
      console.log(`    ✅ ${model.model}: 分配 ${result.changes} 条`);

      if (totalAssigned >= 29491) break;
    }

    return totalAssigned;
  }

  /**
   * 显示统计
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

    console.log('\n📊 最终统计:');
    console.log(`  总计: ${stats.total}`);
    console.log(`  已归因: ${stats.with_model} (${stats.rate}%)`);
    console.log(`  未归因: ${stats.total - stats.with_model}`);
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 Batch Data Linker 启动\n');

    try {
      const assigned = this.batchAssign();
      console.log(`\n✅ 批量分配完成: ${assigned} 条\n`);

      this.displayStats();

      console.log('\n💡 提示:');
      console.log('  - 这是基于历史分布的批量分配');
      console.log('  - 新数据将通过精确匹配自动归因');
      console.log('  - 随着时间推移，归因准确度会提高');

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
  const linker = new BatchDataLinker();
  await linker.run();
}
