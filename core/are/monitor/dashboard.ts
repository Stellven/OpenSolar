/**
 * ARE Monitoring Dashboard
 *
 * Production metrics, stats, and visualization
 */

import { Database } from 'bun:sqlite';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Dashboard Metrics
// ============================================

export interface DashboardMetrics {
  // Execution metrics
  execution: {
    total: number;
    success: number;
    failed: number;
    success_rate: number;
    avg_latency_ms: number;
    p50_latency_ms: number;
    p95_latency_ms: number;
    p99_latency_ms: number;
  };

  // Cache metrics
  cache: {
    plan_cache_entries: number;
    result_cache_entries: number;
    cache_hit_rate: number;
    cache_size_bytes: number;
  };

  // Compilation metrics
  compilation: {
    jit_plans: number;
    aot_plans: number;
    aot_ratio: number;
    recent_promotions: number;
  };

  // Task metrics
  tasks: {
    total_executed: number;
    by_tier: Record<string, number>;
    avg_tasks_per_plan: number;
  };

  // System metrics
  system: {
    uptime_seconds: number;
    memory_usage_mb: number;
    active_workers: number;
  };

  // Time range
  time_range: {
    start: string;
    end: string;
    period: string;
  };
}

// ============================================
// Real-time Stats
// ============================================

export interface RealtimeStats {
  executions_per_minute: number;
  current_latency_ms: number;
  error_rate: number;
  active_plans: number;
  queue_depth: number;
}

// ============================================
// Dashboard
// ============================================

export class Dashboard {
  private db: Database;
  private startTime: number;

  constructor() {
    this.db = new Database(DB_PATH);
    this.startTime = Date.now();
  }

  /**
   * Get full dashboard metrics
   */
  getMetrics(period: '1h' | '24h' | '7d' = '24h'): DashboardMetrics {
    const periodMap = {
      '1h': '-1 hour',
      '24h': '-1 day',
      '7d': '-7 days',
    };
    const sqlPeriod = periodMap[period];

    return {
      execution: this.getExecutionMetrics(sqlPeriod),
      cache: this.getCacheMetrics(),
      compilation: this.getCompilationMetrics(),
      tasks: this.getTaskMetrics(sqlPeriod),
      system: this.getSystemMetrics(),
      time_range: {
        start: new Date(Date.now() - this.periodToMs(period)).toISOString(),
        end: new Date().toISOString(),
        period,
      },
    };
  }

  /**
   * Get execution metrics
   */
  private getExecutionMetrics(sqlPeriod: string): DashboardMetrics['execution'] {
    const stats = this.db.query(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
        AVG(duration_ms) as avg_latency
      FROM are_execution_log
      WHERE start_time > datetime('now', ?)
    `).get(sqlPeriod) as any;

    // Get percentiles
    const latencies = this.db.query(`
      SELECT duration_ms FROM are_execution_log
      WHERE start_time > datetime('now', ?) AND duration_ms IS NOT NULL
      ORDER BY duration_ms
    `).all(sqlPeriod) as any[];

    const p50 = this.percentile(latencies.map(l => l.duration_ms), 50);
    const p95 = this.percentile(latencies.map(l => l.duration_ms), 95);
    const p99 = this.percentile(latencies.map(l => l.duration_ms), 99);

    const total = stats?.total || 0;
    const success = stats?.success || 0;

    return {
      total,
      success,
      failed: stats?.failed || 0,
      success_rate: total > 0 ? success / total : 0,
      avg_latency_ms: stats?.avg_latency || 0,
      p50_latency_ms: p50,
      p95_latency_ms: p95,
      p99_latency_ms: p99,
    };
  }

  /**
   * Get cache metrics
   */
  private getCacheMetrics(): DashboardMetrics['cache'] {
    const planCache = this.db.query(`SELECT COUNT(*) as count FROM are_plan_cache`).get() as any;
    const resultCache = this.db.query(`
      SELECT COUNT(*) as count, SUM(hit_count) as hits, SUM(size_bytes) as size
      FROM are_result_cache
    `).get() as any;

    const totalAccess = this.db.query(`
      SELECT COUNT(*) as count FROM are_task_execution WHERE cached = true
    `).get() as any;

    const totalTasks = this.db.query(`
      SELECT COUNT(*) as count FROM are_task_execution
    `).get() as any;

    const hitRate = (totalTasks?.count || 0) > 0
      ? (totalAccess?.count || 0) / (totalTasks?.count || 1)
      : 0;

    return {
      plan_cache_entries: planCache?.count || 0,
      result_cache_entries: resultCache?.count || 0,
      cache_hit_rate: hitRate,
      cache_size_bytes: resultCache?.size || 0,
    };
  }

  /**
   * Get compilation metrics
   */
  private getCompilationMetrics(): DashboardMetrics['compilation'] {
    const jit = this.db.query(`SELECT COUNT(*) as count FROM are_plan_cache WHERE compile_mode = 'jit' OR compile_mode IS NULL`).get() as any;
    const aot = this.db.query(`SELECT COUNT(*) as count FROM are_plan_cache WHERE compile_mode = 'aot'`).get() as any;

    const recentPromotions = this.db.query(`
      SELECT COUNT(*) as count FROM are_optimization_log
      WHERE optimization_type = 'jit_to_aot' AND applied_at > datetime('now', '-24 hours')
    `).get() as any;

    const total = (jit?.count || 0) + (aot?.count || 0);

    return {
      jit_plans: jit?.count || 0,
      aot_plans: aot?.count || 0,
      aot_ratio: total > 0 ? (aot?.count || 0) / total : 0,
      recent_promotions: recentPromotions?.count || 0,
    };
  }

  /**
   * Get task metrics
   */
  private getTaskMetrics(sqlPeriod: string): DashboardMetrics['tasks'] {
    const total = this.db.query(`
      SELECT COUNT(*) as count FROM are_task_execution t
      JOIN are_execution_log e ON t.execution_id = e.execution_id
      WHERE e.start_time > datetime('now', ?)
    `).get(sqlPeriod) as any;

    const byTier = this.db.query(`
      SELECT tier, COUNT(*) as count FROM are_task_execution t
      JOIN are_execution_log e ON t.execution_id = e.execution_id
      WHERE e.start_time > datetime('now', ?)
      GROUP BY tier
    `).all(sqlPeriod) as any[];

    const avgTasks = this.db.query(`
      SELECT AVG(total_tasks) as avg FROM are_execution_log
      WHERE start_time > datetime('now', ?)
    `).get(sqlPeriod) as any;

    const tierMap: Record<string, number> = {};
    for (const t of byTier) {
      tierMap[t.tier || 'unknown'] = t.count;
    }

    return {
      total_executed: total?.count || 0,
      by_tier: tierMap,
      avg_tasks_per_plan: avgTasks?.avg || 0,
    };
  }

  /**
   * Get system metrics
   */
  private getSystemMetrics(): DashboardMetrics['system'] {
    const uptimeSeconds = Math.floor((Date.now() - this.startTime) / 1000);

    // Get memory usage (approximate)
    const memUsage = process.memoryUsage();
    const memoryMB = Math.round(memUsage.heapUsed / 1024 / 1024);

    return {
      uptime_seconds: uptimeSeconds,
      memory_usage_mb: memoryMB,
      active_workers: 4, // Default worker count
    };
  }

  /**
   * Get real-time stats
   */
  getRealtimeStats(): RealtimeStats {
    const lastMinute = this.db.query(`
      SELECT
        COUNT(*) as executions,
        AVG(duration_ms) as avg_latency,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as error_rate
      FROM are_execution_log
      WHERE start_time > datetime('now', '-1 minute')
    `).get() as any;

    const activePlans = this.db.query(`
      SELECT COUNT(*) as count FROM are_execution_log WHERE status = 'running'
    `).get() as any;

    return {
      executions_per_minute: lastMinute?.executions || 0,
      current_latency_ms: lastMinute?.avg_latency || 0,
      error_rate: lastMinute?.error_rate || 0,
      active_plans: activePlans?.count || 0,
      queue_depth: 0, // Would need actual queue implementation
    };
  }

  /**
   * Format dashboard as ASCII
   */
  formatAscii(metrics: DashboardMetrics): string {
    const lines: string[] = [];

    lines.push('┌─────────────────────────────────────────────────────────────────┐');
    lines.push('│                    ARE MONITORING DASHBOARD                      │');
    lines.push('├─────────────────────────────────────────────────────────────────┤');
    lines.push(`│  Period: ${metrics.time_range.period.padEnd(10)} ${metrics.time_range.start.slice(0, 16)} - ${metrics.time_range.end.slice(0, 16)} │`);
    lines.push('├─────────────────────────────────────────────────────────────────┤');

    // Execution
    lines.push('│  EXECUTION                                                      │');
    lines.push(`│    Total: ${String(metrics.execution.total).padEnd(8)} Success: ${String(metrics.execution.success).padEnd(8)} Failed: ${String(metrics.execution.failed).padEnd(6)} │`);
    lines.push(`│    Success Rate: ${(metrics.execution.success_rate * 100).toFixed(1)}%    Avg Latency: ${metrics.execution.avg_latency_ms.toFixed(0)}ms          │`);
    lines.push(`│    P50: ${metrics.execution.p50_latency_ms.toFixed(0)}ms  P95: ${metrics.execution.p95_latency_ms.toFixed(0)}ms  P99: ${metrics.execution.p99_latency_ms.toFixed(0)}ms                       │`);
    lines.push('├─────────────────────────────────────────────────────────────────┤');

    // Cache
    lines.push('│  CACHE                                                          │');
    lines.push(`│    Plan Cache: ${String(metrics.cache.plan_cache_entries).padEnd(6)} Result Cache: ${String(metrics.cache.result_cache_entries).padEnd(6)}             │`);
    lines.push(`│    Hit Rate: ${(metrics.cache.cache_hit_rate * 100).toFixed(1)}%     Size: ${(metrics.cache.cache_size_bytes / 1024).toFixed(1)} KB                   │`);
    lines.push('├─────────────────────────────────────────────────────────────────┤');

    // Compilation
    lines.push('│  COMPILATION                                                    │');
    lines.push(`│    JIT: ${String(metrics.compilation.jit_plans).padEnd(6)} AOT: ${String(metrics.compilation.aot_plans).padEnd(6)} Ratio: ${(metrics.compilation.aot_ratio * 100).toFixed(1)}%           │`);
    lines.push(`│    Recent Promotions (24h): ${metrics.compilation.recent_promotions}                              │`);
    lines.push('├─────────────────────────────────────────────────────────────────┤');

    // Tasks
    lines.push('│  TASKS                                                          │');
    lines.push(`│    Total: ${String(metrics.tasks.total_executed).padEnd(8)} Avg/Plan: ${metrics.tasks.avg_tasks_per_plan.toFixed(1)}                       │`);
    const tiers = Object.entries(metrics.tasks.by_tier).map(([k, v]) => `${k}:${v}`).join(' ');
    lines.push(`│    By Tier: ${tiers.padEnd(50)} │`);
    lines.push('├─────────────────────────────────────────────────────────────────┤');

    // System
    lines.push('│  SYSTEM                                                         │');
    lines.push(`│    Uptime: ${this.formatUptime(metrics.system.uptime_seconds).padEnd(12)} Memory: ${metrics.system.memory_usage_mb} MB                  │`);
    lines.push('└─────────────────────────────────────────────────────────────────┘');

    return lines.join('\n');
  }

  /**
   * Helper: Calculate percentile
   */
  private percentile(arr: number[], p: number): number {
    if (arr.length === 0) return 0;
    const sorted = arr.sort((a, b) => a - b);
    const index = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  /**
   * Helper: Format uptime
   */
  private formatUptime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d`;
  }

  /**
   * Helper: Period to milliseconds
   */
  private periodToMs(period: string): number {
    const map: Record<string, number> = {
      '1h': 3600000,
      '24h': 86400000,
      '7d': 604800000,
    };
    return map[period] || 86400000;
  }
}

// ============================================
// Export
// ============================================

export const dashboard = new Dashboard();
