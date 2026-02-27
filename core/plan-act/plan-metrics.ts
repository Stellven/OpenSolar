#!/usr/bin/env bun
/**
 * Plan Metrics - 计划执行统计
 *
 * 功能：
 * 1. 记录执行结果
 * 2. 计算成功率
 * 3. 生成统计报告
 * 4. 阈值告警
 *
 * @module plan-metrics
 * @version 1.0.0
 * @created 2026-02-27
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';
import type { ExecutionReport, StepReport } from './plan-executor';
import { PLAN_ACT_CONFIG } from './types';

const DB_PATH = path.join(os.homedir(), '.solar', 'solar.db');

// ============ 类型定义 ============

export interface PlanMetricsRecord {
  id: number;
  planId: string;
  sessionId: string;
  status: 'success' | 'partial' | 'failed';
  totalSteps: number;
  completedSteps: number;
  failedSteps: number;
  replanCount: number;
  durationMs: number;
  executedAt: number;
}

export interface MetricsSummary {
  totalPlans: number;
  successCount: number;
  partialCount: number;
  failedCount: number;
  successRate: number;
  avgDurationMs: number;
  avgStepsPerPlan: number;
  totalReplans: number;
  period: {
    start: number;
    end: number;
  };
}

export interface MetricsAlert {
  type: 'low_success_rate' | 'high_failure_rate' | 'too_many_replans' | 'slow_execution';
  severity: 'warning' | 'critical';
  message: string;
  value: number;
  threshold: number;
  timestamp: number;
}

// ============ 表结构 ============

const CREATE_METRICS_TABLE = `
CREATE TABLE IF NOT EXISTS plan_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  status TEXT NOT NULL,
  total_steps INTEGER DEFAULT 0,
  completed_steps INTEGER DEFAULT 0,
  failed_steps INTEGER DEFAULT 0,
  replan_count INTEGER DEFAULT 0,
  duration_ms INTEGER DEFAULT 0,
  executed_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_plan_metrics_status ON plan_metrics(status);
CREATE INDEX IF NOT EXISTS idx_plan_metrics_executed ON plan_metrics(executed_at);
`;

// ============ 核心函数 ============

/**
 * 初始化指标表
 */
export function initMetricsTable(): void {
  const db = new Database(DB_PATH);

  try {
    db.run(CREATE_METRICS_TABLE);
  } finally {
    db.close();
  }
}

/**
 * 记录执行结果
 *
 * @param report - 执行报告
 */
export function recordMetrics(report: ExecutionReport): void {
  const db = new Database(DB_PATH);

  try {
    db.run(`
      INSERT INTO plan_metrics
      (plan_id, session_id, status, total_steps, completed_steps, failed_steps, replan_count, duration_ms)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `,
      report.planId,
      report.sessionId,
      report.status,
      report.totalSteps,
      report.completedSteps,
      report.failedSteps,
      report.replanCount,
      report.durationMs
    );
  } finally {
    db.close();
  }
}

/**
 * 获取时间范围内的指标汇总
 *
 * @param startMs - 开始时间戳（毫秒）
 * @param endMs - 结束时间戳（毫秒）
 * @returns 指标汇总
 */
export function getMetricsSummary(startMs: number, endMs: number): MetricsSummary {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const startSec = Math.floor(startMs / 1000);
    const endSec = Math.floor(endMs / 1000);

    const stmt = db.prepare(`
      SELECT
        COUNT(*) as total_plans,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
        AVG(duration_ms) as avg_duration,
        AVG(total_steps) as avg_steps,
        SUM(replan_count) as total_replans
      FROM plan_metrics
      WHERE executed_at BETWEEN ? AND ?
    `);

    const result = stmt.get(startSec, endSec) as {
      total_plans: number;
      success_count: number;
      partial_count: number;
      failed_count: number;
      avg_duration: number;
      avg_steps: number;
      total_replans: number;
    };
    stmt.finalize();

    const totalPlans = result.total_plans || 0;
    const successCount = result.success_count || 0;
    const partialCount = result.partial_count || 0;

    return {
      totalPlans,
      successCount,
      partialCount,
      failedCount: result.failed_count || 0,
      successRate: totalPlans > 0 ? (successCount + partialCount * 0.5) / totalPlans : 0,
      avgDurationMs: Math.round(result.avg_duration || 0),
      avgStepsPerPlan: Math.round(result.avg_steps || 0),
      totalReplans: result.total_replans || 0,
      period: {
        start: startMs,
        end: endMs
      }
    };

  } finally {
    db.close();
  }
}

/**
 * 计算成功率
 *
 * @param days - 统计天数
 * @returns 成功率 (0-1)
 */
export function calculateSuccessRate(days: number = 7): number {
  const endMs = Date.now();
  const startMs = endMs - days * 24 * 60 * 60 * 1000;

  const summary = getMetricsSummary(startMs, endMs);
  return summary.successRate;
}

/**
 * 检查是否需要告警
 *
 * @param summary - 指标汇总
 * @returns 告警列表
 */
export function checkAlerts(summary: MetricsSummary): MetricsAlert[] {
  const alerts: MetricsAlert[] = [];
  const config = PLAN_ACT_CONFIG.successRate;
  const now = Date.now();

  // 1. 成功率低于阈值
  if (summary.successRate < config.min) {
    alerts.push({
      type: 'low_success_rate',
      severity: 'critical',
      message: `成功率 ${(summary.successRate * 100).toFixed(1)}% 低于最低阈值 ${(config.min * 100).toFixed(0)}%`,
      value: summary.successRate,
      threshold: config.min,
      timestamp: now
    });
  } else if (summary.successRate < config.target) {
    alerts.push({
      type: 'low_success_rate',
      severity: 'warning',
      message: `成功率 ${(summary.successRate * 100).toFixed(1)}% 低于目标 ${(config.target * 100).toFixed(0)}%`,
      value: summary.successRate,
      threshold: config.target,
      timestamp: now
    });
  }

  // 2. 失败率过高
  const failureRate = summary.totalPlans > 0
    ? summary.failedCount / summary.totalPlans
    : 0;

  if (failureRate > 0.3) {
    alerts.push({
      type: 'high_failure_rate',
      severity: 'critical',
      message: `失败率 ${(failureRate * 100).toFixed(1)}% 过高`,
      value: failureRate,
      threshold: 0.3,
      timestamp: now
    });
  }

  // 3. 重规划次数过多
  if (summary.totalPlans > 0) {
    const avgReplans = summary.totalReplans / summary.totalPlans;
    if (avgReplans > 1) {
      alerts.push({
        type: 'too_many_replans',
        severity: 'warning',
        message: `平均重规划次数 ${avgReplans.toFixed(1)} 过多`,
        value: avgReplans,
        threshold: 1,
        timestamp: now
      });
    }
  }

  // 4. 执行时间过长
  if (summary.avgDurationMs > 60000) {
    alerts.push({
      type: 'slow_execution',
      severity: 'warning',
      message: `平均执行时间 ${(summary.avgDurationMs / 1000).toFixed(1)}s 过长`,
      value: summary.avgDurationMs,
      threshold: 60000,
      timestamp: now
    });
  }

  return alerts;
}

/**
 * 生成统计报告
 *
 * @param days - 统计天数
 * @returns 格式化的报告
 */
export function generateMetricsReport(days: number = 7): string {
  const endMs = Date.now();
  const startMs = endMs - days * 24 * 60 * 60 * 1000;

  const summary = getMetricsSummary(startMs, endMs);
  const alerts = checkAlerts(summary);

  const lines: string[] = [
    '╔═══════════════════════════════════════════════════════════════╗',
    `║           Plan-and-Act 执行统计 (最近 ${days} 天)               ║`,
    '╠═══════════════════════════════════════════════════════════════╣',
    `║  总计划数: ${String(summary.totalPlans).padEnd(47)}║`,
    `║  成功: ${String(summary.successCount).padEnd(51)}║`,
    `║  部分成功: ${String(summary.partialCount).padEnd(48)}║`,
    `║  失败: ${String(summary.failedCount).padEnd(51)}║`,
    '╠═══════════════════════════════════════════════════════════════╣',
    `║  成功率: ${(summary.successRate * 100).toFixed(1)}%`.padEnd(62) + '║',
    `║  平均耗时: ${(summary.avgDurationMs / 1000).toFixed(2)}s`.padEnd(59) + '║',
    `║  平均步骤: ${summary.avgStepsPerPlan}`.padEnd(59) + '║',
    `║  重规划次数: ${summary.totalReplans}`.padEnd(56) + '║',
    '╚═══════════════════════════════════════════════════════════════╝',
  ];

  if (alerts.length > 0) {
    lines.push('', '⚠️ 告警:');
    for (const alert of alerts) {
      const icon = alert.severity === 'critical' ? '🔴' : '🟡';
      lines.push(`  ${icon} ${alert.message}`);
    }
  }

  return lines.join('\n');
}

/**
 * 获取最近的执行记录
 *
 * @param limit - 返回数量
 * @returns 记录列表
 */
export function getRecentRecords(limit: number = 10): PlanMetricsRecord[] {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT id, plan_id, session_id, status, total_steps, completed_steps,
             failed_steps, replan_count, duration_ms, executed_at
      FROM plan_metrics
      ORDER BY executed_at DESC
      LIMIT ?
    `);

    const results = stmt.all(limit) as PlanMetricsRecord[];
    stmt.finalize();

    return results;
  } finally {
    db.close();
  }
}

/**
 * 按状态统计
 */
export function getStatsByStatus(): Record<string, number> {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT status, COUNT(*) as count
      FROM plan_metrics
      GROUP BY status
    `);

    const results = stmt.all() as { status: string; count: number }[];
    stmt.finalize();

    const stats: Record<string, number> = {};
    for (const row of results) {
      stats[row.status] = row.count;
    }

    return stats;
  } finally {
    db.close();
  }
}

/**
 * 清理旧记录
 *
 * @param daysToKeep - 保留天数
 * @returns 删除的记录数
 */
export function cleanupOldRecords(daysToKeep: number = 30): number {
  const db = new Database(DB_PATH);

  try {
    const cutoffSec = Math.floor(Date.now() / 1000) - daysToKeep * 24 * 60 * 60;

    const result = db.run(`
      DELETE FROM plan_metrics
      WHERE executed_at < ?
    `, cutoffSec);

    return result.changes;
  } finally {
    db.close();
  }
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  // 初始化表
  initMetricsTable();

  if (command === 'report') {
    const days = parseInt(args[1]) || 7;
    console.log(generateMetricsReport(days));

  } else if (command === 'recent') {
    const limit = parseInt(args[1]) || 10;
    const records = getRecentRecords(limit);

    console.log('\n=== 最近执行记录 ===\n');
    for (const r of records) {
      const status = r.status === 'success' ? '✅' : r.status === 'partial' ? '⚠️' : '❌';
      console.log(`${status} ${r.plan_id} - ${r.completed_steps}/${r.total_steps} (${(r.duration_ms / 1000).toFixed(1)}s)`);
    }

  } else if (command === 'cleanup') {
    const days = parseInt(args[1]) || 30;
    const deleted = cleanupOldRecords(days);
    console.log(`✅ 已清理 ${deleted} 条旧记录`);

  } else {
    console.log(`
Plan Metrics CLI

Usage:
  bun plan-metrics.ts report [days]   - 生成统计报告
  bun plan-metrics.ts recent [limit]  - 查看最近记录
  bun plan-metrics.ts cleanup [days]  - 清理旧记录
    `);
  }
}

export type { PlanMetricsRecord, MetricsSummary, MetricsAlert };
