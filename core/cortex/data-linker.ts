#!/usr/bin/env bun
/**
 * Data Linker - 数据关联器
 *
 * 功能:
 * 1. 将 evo_traces 与 sroe_requests 关联 (通过 session_id + timestamp)
 * 2. 提取模型归因 (selected_model)
 * 3. 计算归因率统计
 *
 * 解决断点 #1: Traces 没有模型归因
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface LinkStats {
  totalTraces: number;
  alreadyLinked: number;
  newlyLinked: number;
  failedToLink: number;
}

interface AttributionStats {
  total: number;
  withModel: number;
  withSkill: number;
  withTools: number;
  modelRate: number;
}

export class DataLinker {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
  }

  /**
   * 关联 evo_traces 与 sroe_requests
   * 匹配逻辑:
   * 1. 同一 session_id
   * 2. trace.started_at 与 request.timestamp 时间差 < 5秒
   */
  async linkTracesToRequests(): Promise<LinkStats> {
    console.log('🔗 开始关联 Traces 与 Requests...');

    // 1. 统计总数
    const total = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count FROM evo_traces
    `).get()?.count || 0;

    // 2. 统计已关联
    const alreadyLinked = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count FROM evo_traces WHERE selected_model IS NOT NULL
    `).get()?.count || 0;

    // 3. 执行关联
    // 时间差阈值: 5秒 = 5/86400 天 ≈ 0.000058
    const timeThreshold = 0.000058;

    const result = this.db.run(`
      UPDATE evo_traces
      SET
        selected_model = r.selected_model,
        sroe_request_id = r.request_id
      FROM sroe_requests r
      WHERE evo_traces.session_id = r.session_id
        AND evo_traces.selected_model IS NULL
        AND r.selected_model IS NOT NULL
        AND ABS(julianday(evo_traces.started_at) - julianday(r.timestamp)) < ?
    `, [timeThreshold]);

    const newlyLinked = result.changes;

    // 4. 统计仍未关联的
    const stillUnlinked = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count FROM evo_traces WHERE selected_model IS NULL
    `).get()?.count || 0;

    console.log(`  ✅ 新关联: ${newlyLinked} 条`);
    console.log(`  📊 已有: ${alreadyLinked} 条`);
    console.log(`  ⚠️  未关联: ${stillUnlinked} 条`);

    return {
      totalTraces: total,
      alreadyLinked,
      newlyLinked,
      failedToLink: stillUnlinked
    };
  }

  /**
   * 计算归因率统计
   */
  getAttributionStats(): AttributionStats {
    const stats = this.db.query<{
      total: number;
      withModel: number;
      withSkill: number;
      withTools: number;
    }>(`
      SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) as withModel,
        COUNT(CASE WHEN selected_skill IS NOT NULL THEN 1 END) as withSkill,
        COUNT(CASE WHEN selected_tools IS NOT NULL THEN 1 END) as withTools
      FROM evo_traces
    `).get()!;

    return {
      ...stats,
      modelRate: stats.total > 0 ? (stats.withModel * 100.0 / stats.total) : 0
    };
  }

  /**
   * 显示归因率统计
   */
  displayStats(): void {
    const stats = this.getAttributionStats();

    console.log('\n📊 归因率统计:');
    console.log(`  总 Traces: ${stats.total}`);
    console.log(`  有 Model: ${stats.withModel} (${stats.modelRate.toFixed(1)}%)`);
    console.log(`  有 Skill:  ${stats.withSkill}`);
    console.log(`  有 Tools:  ${stats.withTools}`);

    // 按日期统计最近 7 天
    console.log('\n📅 最近 7 天归因率:');
    const dailyStats = this.db.query<{
      date: string;
      total: number;
      linked: number;
      rate: number;
    }>(`
      SELECT
        DATE(started_at) as date,
        COUNT(*) as total,
        COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) as linked,
        ROUND(COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as rate
      FROM evo_traces
      WHERE started_at >= DATE('now', '-7 days')
      GROUP BY DATE(started_at)
      ORDER BY date DESC
    `).all();

    for (const row of dailyStats) {
      console.log(`  ${row.date}: ${row.linked}/${row.total} (${row.rate}%)`);
    }
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 Data Linker 启动\n');

    try {
      // 1. 关联数据
      const linkStats = await this.linkTracesToRequests();
      console.log(`\n✅ 关联完成: ${linkStats.newlyLinked} 条新关联`);

      // 2. 显示统计
      this.displayStats();

      // 3. 检查是否有 sroe_requests 数据
      const sroeCount = this.db.query<{ count: number }>(`
        SELECT COUNT(*) as count FROM sroe_requests
      `).get()?.count || 0;

      if (sroeCount === 0) {
        console.log('\n⚠️  警告: sroe_requests 表为空，无法关联');
        console.log('   请确保 SROE Router 正在记录请求');
      } else {
        console.log(`\n📋 sroe_requests 记录数: ${sroeCount}`);
      }

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
  const linker = new DataLinker();
  await linker.run();
}
