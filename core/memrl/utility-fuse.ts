/**
 * MEMRL Utility Fuse - 奖励熔断机制
 *
 * Phase 0 核心组件
 * 防止奖励欺骗和异常信号导致模型崩溃
 */

import { Database } from 'bun:sqlite';

interface FuseResult {
  action: 'OK' | 'WARNING' | 'FREEZE' | 'ROLLBACK';
  shouldUpdateQ: boolean;
  message: string;
}

interface UtilityHistory {
  utility_total: number;
  created_at: string;
}

export class UtilityFuse {
  private db: Database;
  private historySize: number = 100;
  private freezeMode: boolean = false;

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
  }

  /**
   * 检查 Utility 是否触发熔断
   */
  check(utility: number, intentHash: string): FuseResult {
    // 获取历史记录
    const history = this.getHistory(intentHash);

    // 级别 3: ROLLBACK - 连续 5 次 < 0.3
    if (history.length >= 5) {
      const recent5 = history.slice(-5).map(h => h.utility_total);
      if (recent5.every(u => u < 0.3)) {
        this.logFuseEvent(intentHash, 'ROLLBACK', utility, '连续5次Utility<0.3');
        return {
          action: 'ROLLBACK',
          shouldUpdateQ: false,
          message: '🚨 ROLLBACK: 连续5次Utility<0.3，需要人工介入'
        };
      }
    }

    // 级别 2: FREEZE - 连续 3 次 < 0.5 或 偏离均值 > 2σ
    if (history.length >= 3) {
      const recent3 = history.slice(-3).map(h => h.utility_total);
      if (recent3.every(u => u < 0.5)) {
        this.freezeMode = true;
        this.logFuseEvent(intentHash, 'FREEZE', utility, '连续3次Utility<0.5');
        return {
          action: 'FREEZE',
          shouldUpdateQ: false,
          message: '⚠️ FREEZE: 连续3次Utility<0.5，暂停Q值更新'
        };
      }
    }

    // 统计检验 (需要至少 20 个样本)
    if (history.length >= 20) {
      const stats = this.calculateStats(history.map(h => h.utility_total));
      if (utility < stats.mean - 2 * stats.std) {
        this.freezeMode = true;
        this.logFuseEvent(intentHash, 'FREEZE', utility,
          `Utility=${utility.toFixed(2)} < 均值-2σ (${(stats.mean - 2 * stats.std).toFixed(2)})`);
        return {
          action: 'FREEZE',
          shouldUpdateQ: false,
          message: `⚠️ FREEZE: Utility偏离历史均值超过2σ`
        };
      }
    }

    // 级别 1: WARNING
    if (utility < 0.3) {
      this.logFuseEvent(intentHash, 'WARNING', utility, '单次Utility<0.3');
      return {
        action: 'WARNING',
        shouldUpdateQ: true,
        message: '⚡ WARNING: 单次Utility<0.3，记录但继续'
      };
    }

    // 正常
    this.freezeMode = false;
    return {
      action: 'OK',
      shouldUpdateQ: true,
      message: '✅ OK: 正常范围'
    };
  }

  /**
   * 获取历史记录
   */
  private getHistory(intentHash: string): UtilityHistory[] {
    const stmt = this.db.prepare(`
      SELECT utility_total, created_at
      FROM memrl_utility_store
      WHERE intent_hash = ?
      ORDER BY created_at DESC
      LIMIT ?
    `);
    return stmt.all(intentHash, this.historySize) as UtilityHistory[];
  }

  /**
   * 计算统计量
   */
  private calculateStats(values: number[]): { mean: number; std: number } {
    const n = values.length;
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / n;
    const std = Math.sqrt(variance);
    return { mean, std };
  }

  /**
   * 记录熔断事件
   */
  private logFuseEvent(
    intentHash: string,
    action: string,
    utility: number,
    reason: string
  ): void {
    const stmt = this.db.prepare(`
      INSERT INTO memrl_utility_store
      (intent_hash, experience_id, utility_total, fuse_status, experience_type)
      VALUES (?, ?, ?, ?, ?)
    `);
    stmt.run(
      intentHash,
      `fuse_${Date.now()}`,
      utility,
      action,
      `FUSE_EVENT: ${reason}`
    );
  }

  /**
   * 获取当前熔断状态
   */
  isFrozen(): boolean {
    return this.freezeMode;
  }

  /**
   * 手动解冻 (需要管理员权限)
   */
  unfreeze(): void {
    this.freezeMode = false;
    console.log('🔓 熔断已手动解除');
  }

  /**
   * 获取统计摘要
   */
  getStats(intentHash?: string): {
    totalRecords: number;
    avgUtility: number;
    fuseEvents: number;
    recentTrend: 'up' | 'down' | 'stable';
  } {
    let query = `
      SELECT
        COUNT(*) as total,
        AVG(utility_total) as avg_utility,
        SUM(CASE WHEN fuse_status != 'OK' THEN 1 ELSE 0 END) as fuse_events
      FROM memrl_utility_store
    `;
    const params: string[] = [];

    if (intentHash) {
      query += ' WHERE intent_hash = ?';
      params.push(intentHash);
    }

    const result = this.db.prepare(query).get(...params) as any;

    // 计算趋势 (最近10条 vs 再之前10条)
    const trendQuery = `
      SELECT utility_total FROM memrl_utility_store
      ${intentHash ? 'WHERE intent_hash = ?' : ''}
      ORDER BY created_at DESC LIMIT 20
    `;
    const trendParams = intentHash ? [intentHash] : [];
    const trendData = this.db.prepare(trendQuery).all(...trendParams) as any[];

    let recentTrend: 'up' | 'down' | 'stable' = 'stable';
    if (trendData.length >= 10) {
      const recent10 = trendData.slice(0, 10).reduce((s: number, r: any) => s + r.utility_total, 0) / 10;
      const prev10 = trendData.slice(10, 20).reduce((s: number, r: any) => s + r.utility_total, 0) / 10;
      if (recent10 > prev10 + 0.1) recentTrend = 'up';
      else if (recent10 < prev10 - 0.1) recentTrend = 'down';
    }

    return {
      totalRecords: result?.total || 0,
      avgUtility: result?.avg_utility || 0.5,
      fuseEvents: result?.fuse_events || 0,
      recentTrend
    };
  }

  close(): void {
    this.db.close();
  }
}

/**
 * 计算 Utility 综合值
 */
export function calculateUtility(
  uExplicit: number,
  uImplicit: number,
  uOutcome: number,
  weights: { w1: number; w2: number; w3: number } = { w1: 0.5, w2: 0.3, w3: 0.2 }
): number {
  const raw = weights.w1 * uExplicit + weights.w2 * uImplicit + weights.w3 * uOutcome;
  // 归一化到 [0, 1]，假设原始范围 [-1, 2]
  return Math.max(0, Math.min(1, (raw + 1) / 3));
}

/**
 * Q-learning 更新
 */
export function updateQValue(
  oldQ: number,
  reward: number,
  alpha: number = 0.1
): number {
  // Q_new = Q_old + alpha * (r - Q_old)
  return oldQ + alpha * (reward - oldQ);
}

// CLI 测试
if (import.meta.main) {
  const fuse = new UtilityFuse();

  // 测试用例
  const testCases = [
    { utility: 0.8, intent: 'test_intent' },
    { utility: 0.2, intent: 'test_intent' },
    { utility: 0.1, intent: 'test_intent' },
    { utility: 0.15, intent: 'test_intent' },
    { utility: 0.05, intent: 'test_intent' },  // 应该触发 ROLLBACK
  ];

  console.log('🧪 熔断机制测试\n');

  for (const tc of testCases) {
    // 先插入测试数据
    const db = new Database(`${process.env.HOME}/.solar/solar.db`);
    db.prepare(`
      INSERT INTO memrl_utility_store
      (intent_hash, experience_id, utility_total)
      VALUES (?, ?, ?)
    `).run(tc.intent, `test_${Date.now()}`, tc.utility);
    db.close();

    const result = fuse.check(tc.utility, tc.intent);
    console.log(`Utility: ${tc.utility.toFixed(2)} → ${result.action}`);
    console.log(`  ${result.message}\n`);
  }

  // 显示统计
  const stats = fuse.getStats('test_intent');
  console.log('📊 统计:', stats);

  fuse.close();
}
