/**
 * MEMRL SessionEnd Hook
 *
 * 在会话结束时批量更新 Q 值
 * 并生成会话级别的统计报告
 */

import { Database } from 'bun:sqlite';
import { QUpdater } from '../q-updater';
import { UtilityCollector } from '../utility-collector';

interface SessionSignal {
  experience_id: string;
  intent_hash: string;
  signal: 'success' | 'failure';
  evidence: string[];
  timestamp: string;
}

interface SessionSummary {
  sessionId: string;
  totalSignals: number;
  successCount: number;
  failureCount: number;
  avgQValue: number;
  qValueChange: number;
  topIntents: Array<{ intent_hash: string; count: number; avg_q: number }>;
}

export class MEMRLSessionEndHook {
  private db: Database;
  private updater: QUpdater;
  private collector: UtilityCollector;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`
  ) {
    this.db = new Database(dbPath);
    this.updater = new QUpdater(dbPath);
    this.collector = new UtilityCollector(dbPath);
  }

  /**
   * Hook 主入口
   *
   * 在会话结束时执行
   */
  async execute(sessionId: string): Promise<SessionSummary> {
    // 1. 获取本会话的所有信号
    const signals = this.getSessionSignals(sessionId);

    if (signals.length === 0) {
      return {
        sessionId,
        totalSignals: 0,
        successCount: 0,
        failureCount: 0,
        avgQValue: 0,
        qValueChange: 0,
        topIntents: []
      };
    }

    // 2. 批量更新 Q 值
    const updates = signals.map(s => ({
      intentHash: s.intent_hash,
      experienceId: s.experience_id,
      reward: s.signal === 'success' ? 1 : 0
    }));

    const updateCount = this.updater.batchUpdate(updates);

    // 3. 计算统计
    const successCount = signals.filter(s => s.signal === 'success').length;
    const failureCount = signals.length - successCount;

    // 4. 获取意图分布
    const intentMap = new Map<string, { count: number; totalQ: number }>();
    for (const signal of signals) {
      const current = intentMap.get(signal.intent_hash) || { count: 0, totalQ: 0 };
      const q = this.updater.getQ(signal.intent_hash, signal.experience_id);
      intentMap.set(signal.intent_hash, {
        count: current.count + 1,
        totalQ: current.totalQ + q
      });
    }

    const topIntents = Array.from(intentMap.entries())
      .map(([intent_hash, { count, totalQ }]) => ({
        intent_hash,
        count,
        avg_q: totalQ / count
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    // 5. 计算平均 Q 值变化
    const allQValues = signals.map(s =>
      this.updater.getQ(s.intent_hash, s.experience_id)
    );
    const avgQValue = allQValues.reduce((a, b) => a + b, 0) / allQValues.length;

    // 6. 记录会话总结
    this.saveSessionSummary(sessionId, {
      totalSignals: signals.length,
      successCount,
      failureCount,
      avgQValue,
      topIntents
    });

    return {
      sessionId,
      totalSignals: signals.length,
      successCount,
      failureCount,
      avgQValue,
      qValueChange: updateCount,
      topIntents
    };
  }

  /**
   * 获取会话信号
   */
  private getSessionSignals(sessionId: string): SessionSignal[] {
    return this.db.prepare(`
      SELECT
        experience_id,
        intent_hash,
        signal_type as signal,
        evidence_json,
        created_at as timestamp
      FROM memrl_utility_store
      WHERE experience_id LIKE ? || '%'
      ORDER BY created_at DESC
    `).all(`session_${sessionId}`) as SessionSignal[];
  }

  /**
   * 保存会话总结
   */
  private saveSessionSummary(
    sessionId: string,
    summary: {
      totalSignals: number;
      successCount: number;
      failureCount: number;
      avgQValue: number;
      topIntents: Array<{ intent_hash: string; count: number; avg_q: number }>;
    }
  ): void {
    this.db.prepare(`
      INSERT OR REPLACE INTO memrl_session_summaries
      (session_id, total_signals, success_count, failure_count, avg_q_value, top_intents_json, created_at)
      VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    `).run(
      sessionId,
      summary.totalSignals,
      summary.successCount,
      summary.failureCount,
      summary.avgQValue,
      JSON.stringify(summary.topIntents)
    );
  }

  /**
   * 获取历史会话总结
   */
  getSessionHistory(limit: number = 10): Array<{
    session_id: string;
    total_signals: number;
    success_rate: number;
    avg_q_value: number;
    created_at: string;
  }> {
    return this.db.prepare(`
      SELECT
        session_id,
        total_signals,
        CASE WHEN total_signals > 0
          THEN CAST(success_count AS REAL) / total_signals
          ELSE 0
        END as success_rate,
        avg_q_value,
        created_at
      FROM memrl_session_summaries
      ORDER BY created_at DESC
      LIMIT ?
    `).all(limit) as any[];
  }

  /**
   * 获取全局统计
   */
  getGlobalStats(): {
    totalSessions: number;
    totalSignals: number;
    globalSuccessRate: number;
    avgQValue: number;
    improvingIntents: number;
    decliningIntents: number;
  } {
    const result = this.db.prepare(`
      SELECT
        COUNT(DISTINCT session_id) as total_sessions,
        SUM(total_signals) as total_signals,
        SUM(success_count) as total_success,
        AVG(avg_q_value) as avg_q
      FROM memrl_session_summaries
    `).get() as any;

    const trendResult = this.db.prepare(`
      SELECT
        SUM(CASE WHEN q_value > 0.5 THEN 1 ELSE 0 END) as improving,
        SUM(CASE WHEN q_value < 0.4 THEN 1 ELSE 0 END) as declining
      FROM memrl_utility_store
      WHERE update_count > 3
    `).get() as any;

    return {
      totalSessions: result?.total_sessions || 0,
      totalSignals: result?.total_signals || 0,
      globalSuccessRate: result?.total_signals > 0
        ? (result?.total_success || 0) / result.total_signals
        : 0,
      avgQValue: result?.avg_q || 0.5,
      improvingIntents: trendResult?.improving || 0,
      decliningIntents: trendResult?.declining || 0
    };
  }

  close(): void {
    this.db.close();
    this.updater.close();
    this.collector.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const hook = new MEMRLSessionEndHook();

  const command = process.argv[2] || 'stats';
  const sessionId = process.argv[3] || `session_${Date.now()}`;

  if (command === 'stats') {
    console.log('📊 MEMRL 全局统计\n');
    const stats = hook.getGlobalStats();
    console.log(`总会话数: ${stats.totalSessions}`);
    console.log(`总信号数: ${stats.totalSignals}`);
    console.log(`全局成功率: ${(stats.globalSuccessRate * 100).toFixed(1)}%`);
    console.log(`平均 Q 值: ${stats.avgQValue.toFixed(3)}`);
    console.log(`改善意图: ${stats.improvingIntents}`);
    console.log(`下降意图: ${stats.decliningIntents}`);
  }

  if (command === 'history') {
    const limit = parseInt(process.argv[3] || '10');
    console.log(`📜 最近 ${limit} 个会话\n`);
    const history = hook.getSessionHistory(limit);
    for (const session of history) {
      console.log(`${session.session_id}`);
      console.log(`  信号: ${session.total_signals} | 成功率: ${(session.success_rate * 100).toFixed(0)}% | Q: ${session.avg_q_value.toFixed(2)}`);
      console.log(`  时间: ${session.created_at}`);
      console.log();
    }
  }

  if (command === 'test') {
    console.log(`🧪 测试会话结束 Hook: ${sessionId}\n`);
    const summary = hook.execute(sessionId);
    console.log('会话总结:');
    console.log(`  总信号: ${summary.totalSignals}`);
    console.log(`  成功: ${summary.successCount}`);
    console.log(`  失败: ${summary.failureCount}`);
    console.log(`  平均 Q: ${summary.avgQValue.toFixed(3)}`);
    console.log(`  Q 值更新: ${summary.qValueChange} 次`);
  }

  hook.close();
}
