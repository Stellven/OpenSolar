/**
 * ARE Health Check & Alerting
 *
 * Monitor system health and trigger alerts
 */

import { Database } from 'bun:sqlite';
import { codeExecutor } from '../sandbox/executor';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Health Check Types
// ============================================

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  checks: HealthCheck[];
  summary: string;
}

export interface HealthCheck {
  name: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  latency_ms: number;
  details?: Record<string, any>;
}

export interface AlertRule {
  name: string;
  condition: string;
  threshold: number;
  severity: 'info' | 'warning' | 'critical';
  cooldown_minutes: number;
}

export interface Alert {
  id: string;
  rule: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  value: number;
  threshold: number;
  triggered_at: string;
  acknowledged: boolean;
}

// ============================================
// Default Alert Rules
// ============================================

export const DEFAULT_ALERT_RULES: AlertRule[] = [
  {
    name: 'high_error_rate',
    condition: 'error_rate > threshold',
    threshold: 0.1, // 10%
    severity: 'warning',
    cooldown_minutes: 15,
  },
  {
    name: 'critical_error_rate',
    condition: 'error_rate > threshold',
    threshold: 0.3, // 30%
    severity: 'critical',
    cooldown_minutes: 5,
  },
  {
    name: 'high_latency',
    condition: 'p95_latency > threshold',
    threshold: 5000, // 5 seconds
    severity: 'warning',
    cooldown_minutes: 10,
  },
  {
    name: 'low_cache_hit_rate',
    condition: 'cache_hit_rate < threshold',
    threshold: 0.3, // 30%
    severity: 'info',
    cooldown_minutes: 60,
  },
  {
    name: 'sandbox_unavailable',
    condition: 'sandbox_available == false',
    threshold: 0,
    severity: 'warning',
    cooldown_minutes: 30,
  },
];

// ============================================
// Health Checker
// ============================================

export class HealthChecker {
  private db: Database;
  private alertRules: AlertRule[];
  private lastAlerts: Map<string, number> = new Map(); // rule -> timestamp

  constructor(rules?: AlertRule[]) {
    this.db = new Database(DB_PATH);
    this.alertRules = rules || DEFAULT_ALERT_RULES;
  }

  /**
   * Run all health checks
   */
  async check(): Promise<HealthStatus> {
    const checks: HealthCheck[] = [];

    // Database check
    checks.push(await this.checkDatabase());

    // Cache check
    checks.push(await this.checkCache());

    // Execution check
    checks.push(await this.checkExecution());

    // Sandbox check
    checks.push(await this.checkSandbox());

    // Telemetry check
    checks.push(await this.checkTelemetry());

    // Determine overall status
    const failCount = checks.filter(c => c.status === 'fail').length;
    const warnCount = checks.filter(c => c.status === 'warn').length;

    let status: HealthStatus['status'] = 'healthy';
    if (failCount > 0) status = 'unhealthy';
    else if (warnCount > 0) status = 'degraded';

    const summary = `${checks.filter(c => c.status === 'pass').length}/${checks.length} checks passed`;

    return {
      status,
      timestamp: new Date().toISOString(),
      checks,
      summary,
    };
  }

  /**
   * Check database connectivity
   */
  private async checkDatabase(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      const result = this.db.query('SELECT 1 as ok').get() as any;
      return {
        name: 'database',
        status: result?.ok === 1 ? 'pass' : 'fail',
        message: 'Database connection OK',
        latency_ms: Date.now() - start,
      };
    } catch (e: any) {
      return {
        name: 'database',
        status: 'fail',
        message: `Database error: ${e.message}`,
        latency_ms: Date.now() - start,
      };
    }
  }

  /**
   * Check cache health
   */
  private async checkCache(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      const stats = this.db.query(`
        SELECT
          (SELECT COUNT(*) FROM are_plan_cache) as plan_cache,
          (SELECT COUNT(*) FROM are_result_cache) as result_cache,
          (SELECT SUM(hit_count) FROM are_result_cache) as hits
      `).get() as any;

      const totalEntries = (stats?.plan_cache || 0) + (stats?.result_cache || 0);
      const status = totalEntries > 0 ? 'pass' : 'warn';
      const message = totalEntries > 0
        ? `Cache healthy: ${stats.plan_cache} plans, ${stats.result_cache} results, ${stats.hits || 0} hits`
        : 'Cache empty';

      return {
        name: 'cache',
        status,
        message,
        latency_ms: Date.now() - start,
        details: stats,
      };
    } catch (e: any) {
      return {
        name: 'cache',
        status: 'fail',
        message: `Cache error: ${e.message}`,
        latency_ms: Date.now() - start,
      };
    }
  }

  /**
   * Check execution health
   */
  private async checkExecution(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      const stats = this.db.query(`
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
          AVG(duration_ms) as avg_latency
        FROM are_execution_log
        WHERE start_time > datetime('now', '-1 hour')
      `).get() as any;

      const successRate = stats?.total > 0 ? stats.success / stats.total : 1;
      let status: HealthCheck['status'] = 'pass';
      if (successRate < 0.7) status = 'fail';
      else if (successRate < 0.9) status = 'warn';

      return {
        name: 'execution',
        status,
        message: `Success rate: ${(successRate * 100).toFixed(1)}%, Avg latency: ${(stats?.avg_latency || 0).toFixed(0)}ms`,
        latency_ms: Date.now() - start,
        details: { success_rate: successRate, avg_latency: stats?.avg_latency },
      };
    } catch (e: any) {
      return {
        name: 'execution',
        status: 'fail',
        message: `Execution check error: ${e.message}`,
        latency_ms: Date.now() - start,
      };
    }
  }

  /**
   * Check sandbox availability
   */
  private async checkSandbox(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      const dockerAvailable = await codeExecutor.isDockerAvailable();
      return {
        name: 'sandbox',
        status: dockerAvailable ? 'pass' : 'warn',
        message: dockerAvailable ? 'Docker sandbox available' : 'Docker unavailable, using process fallback',
        latency_ms: Date.now() - start,
        details: { docker: dockerAvailable },
      };
    } catch (e: any) {
      return {
        name: 'sandbox',
        status: 'warn',
        message: `Sandbox check error: ${e.message}`,
        latency_ms: Date.now() - start,
      };
    }
  }

  /**
   * Check telemetry data
   */
  private async checkTelemetry(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      const stats = this.db.query(`
        SELECT COUNT(*) as count FROM tel_operations
        WHERE timestamp > datetime('now', '-1 hour')
      `).get() as any;

      const recentOps = stats?.count || 0;
      return {
        name: 'telemetry',
        status: 'pass',
        message: `${recentOps} operations in last hour`,
        latency_ms: Date.now() - start,
        details: { recent_operations: recentOps },
      };
    } catch (e: any) {
      return {
        name: 'telemetry',
        status: 'warn',
        message: `Telemetry check error: ${e.message}`,
        latency_ms: Date.now() - start,
      };
    }
  }

  /**
   * Evaluate alert rules
   */
  async evaluateAlerts(): Promise<Alert[]> {
    const alerts: Alert[] = [];
    const now = Date.now();

    // Get current metrics
    const metrics = await this.getAlertMetrics();

    for (const rule of this.alertRules) {
      // Check cooldown
      const lastAlert = this.lastAlerts.get(rule.name) || 0;
      if (now - lastAlert < rule.cooldown_minutes * 60 * 1000) {
        continue;
      }

      // Evaluate condition
      const triggered = this.evaluateCondition(rule, metrics);
      if (triggered) {
        const alert: Alert = {
          id: `alert_${now}_${Math.random().toString(36).slice(2, 8)}`,
          rule: rule.name,
          severity: rule.severity,
          message: this.formatAlertMessage(rule, metrics),
          value: metrics[this.getMetricName(rule.condition)] || 0,
          threshold: rule.threshold,
          triggered_at: new Date().toISOString(),
          acknowledged: false,
        };
        alerts.push(alert);
        this.lastAlerts.set(rule.name, now);

        // Log alert
        this.logAlert(alert);
      }
    }

    return alerts;
  }

  /**
   * Get metrics for alert evaluation
   */
  private async getAlertMetrics(): Promise<Record<string, number>> {
    const stats = this.db.query(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0) as error_rate,
        AVG(duration_ms) as avg_latency
      FROM are_execution_log
      WHERE start_time > datetime('now', '-1 hour')
    `).get() as any;

    const cacheStats = this.db.query(`
      SELECT
        SUM(CASE WHEN cached THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0) as cache_hit_rate
      FROM are_task_execution t
      JOIN are_execution_log e ON t.execution_id = e.execution_id
      WHERE e.start_time > datetime('now', '-1 hour')
    `).get() as any;

    const dockerAvailable = await codeExecutor.isDockerAvailable();

    return {
      error_rate: stats?.error_rate || 0,
      avg_latency: stats?.avg_latency || 0,
      p95_latency: (stats?.avg_latency || 0) * 2, // Approximation
      cache_hit_rate: cacheStats?.cache_hit_rate || 0,
      sandbox_available: dockerAvailable ? 1 : 0,
    };
  }

  /**
   * Evaluate alert condition
   */
  private evaluateCondition(rule: AlertRule, metrics: Record<string, number>): boolean {
    const metricName = this.getMetricName(rule.condition);
    const value = metrics[metricName] || 0;

    if (rule.condition.includes('>')) {
      return value > rule.threshold;
    } else if (rule.condition.includes('<')) {
      return value < rule.threshold;
    } else if (rule.condition.includes('==')) {
      return value === rule.threshold;
    }
    return false;
  }

  /**
   * Get metric name from condition
   */
  private getMetricName(condition: string): string {
    const match = condition.match(/^(\w+)/);
    return match ? match[1] : '';
  }

  /**
   * Format alert message
   */
  private formatAlertMessage(rule: AlertRule, metrics: Record<string, number>): string {
    const metricName = this.getMetricName(rule.condition);
    const value = metrics[metricName] || 0;
    return `${rule.name}: ${metricName} = ${value.toFixed(2)} (threshold: ${rule.threshold})`;
  }

  /**
   * Log alert to database
   */
  private logAlert(alert: Alert): void {
    try {
      this.db.run(`
        INSERT INTO are_optimization_log (
          optimization_type, target, old_value, new_value, evidence, applied
        ) VALUES (?, ?, ?, ?, ?, false)
      `, [
        'alert',
        alert.rule,
        String(alert.threshold),
        String(alert.value),
        JSON.stringify(alert),
      ]);
    } catch (e) {
      // Ignore logging errors
    }
  }

  /**
   * Format health status as ASCII
   */
  formatAscii(status: HealthStatus): string {
    const lines: string[] = [];
    const statusIcon = {
      healthy: '✓',
      degraded: '⚠',
      unhealthy: '✗',
    };
    const checkIcon = {
      pass: '✓',
      warn: '⚠',
      fail: '✗',
    };

    lines.push('┌─────────────────────────────────────────────────────────────────┐');
    lines.push(`│  ARE HEALTH CHECK  ${statusIcon[status.status]} ${status.status.toUpperCase().padEnd(10)} ${status.summary.padEnd(20)} │`);
    lines.push('├─────────────────────────────────────────────────────────────────┤');

    for (const check of status.checks) {
      const icon = checkIcon[check.status];
      lines.push(`│  ${icon} ${check.name.padEnd(12)} ${check.message.slice(0, 45).padEnd(45)} │`);
    }

    lines.push('├─────────────────────────────────────────────────────────────────┤');
    lines.push(`│  Timestamp: ${status.timestamp.padEnd(50)} │`);
    lines.push('└─────────────────────────────────────────────────────────────────┘');

    return lines.join('\n');
  }
}

// ============================================
// Export
// ============================================

export const healthChecker = new HealthChecker();
