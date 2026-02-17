/**
 * MEMRL Q-Updater - Q 值更新器
 *
 * Phase 1 核心组件
 * 职责: Monte Carlo Q-learning 更新
 */

import { Database } from 'bun:sqlite';

interface QRecord {
  id: number;
  intent_hash: string;
  experience_id: string;
  q_value: number;
  update_count: number;
  alpha: number;
  utility_total: number;
  created_at: string;
  updated_at: string;
}

interface Experience {
  experience_id: string;
  intent_hash: string;
  experience_type: string;
  q_value: number;
  evidence_json: string | null;
  created_at: string;
}

export class QUpdater {
  private db: Database;
  private defaultAlpha: number = 0.1;
  private alphaDecay: number = 0.999;
  private minAlpha: number = 0.01;

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
  }

  /**
   * 更新 Q 值 (Monte Carlo Q-learning)
   *
   * Q_new = Q_old + α × (r - Q_old)
   *
   * @param intentHash 意图哈希
   * @param experienceId 经验 ID
   * @param reward 奖励值 (1=Success, 0=Failure)
   * @returns 更新后的 Q 值
   */
  update(intentHash: string, experienceId: string, reward: number): number {
    // 获取现有记录
    const existing = this.db.prepare(`
      SELECT id, q_value, update_count, alpha
      FROM memrl_utility_store
      WHERE intent_hash = ? AND experience_id = ?
    `).get(intentHash, experienceId) as QRecord | undefined;

    if (existing) {
      // 更新现有记录
      const qOld = existing.q_value;
      const alpha = Math.max(this.minAlpha, existing.alpha * this.alphaDecay);
      const qNew = qOld + alpha * (reward - qOld);

      this.db.prepare(`
        UPDATE memrl_utility_store
        SET q_value = ?,
            utility_total = ?,
            update_count = update_count + 1,
            alpha = ?,
            updated_at = datetime('now')
        WHERE id = ?
      `).run(qNew, reward, alpha, existing.id);

      return qNew;
    } else {
      // 创建新记录
      const qNew = 0.5 + this.defaultAlpha * (reward - 0.5);

      this.db.prepare(`
        INSERT INTO memrl_utility_store
        (intent_hash, experience_id, q_value, utility_total, alpha, update_count, experience_type)
        VALUES (?, ?, ?, ?, ?, 1, 'unknown')
      `).run(intentHash, experienceId, qNew, reward, this.defaultAlpha);

      return qNew;
    }
  }

  /**
   * 批量更新 Q 值
   */
  batchUpdate(updates: Array<{ intentHash: string; experienceId: string; reward: number }>): number {
    let count = 0;
    const transaction = this.db.transaction(() => {
      for (const { intentHash, experienceId, reward } of updates) {
        this.update(intentHash, experienceId, reward);
        count++;
      }
    });

    transaction();
    return count;
  }

  /**
   * 获取单个 Q 值
   */
  getQ(intentHash: string, experienceId?: string): number {
    if (experienceId) {
      const record = this.db.prepare(`
        SELECT q_value FROM memrl_utility_store
        WHERE intent_hash = ? AND experience_id = ?
      `).get(intentHash, experienceId) as { q_value: number } | undefined;

      return record?.q_value ?? 0.5;
    }

    // 获取该意图的平均 Q 值
    const result = this.db.prepare(`
      SELECT AVG(q_value) as avg_q
      FROM memrl_utility_store
      WHERE intent_hash = ?
    `).get(intentHash) as { avg_q: number } | undefined;

    return result?.avg_q ?? 0.5;
  }

  /**
   * 获取 Top-K 高 Q 值 Experience
   */
  getTopExperiences(intentHash: string, k: number = 5): Experience[] {
    return this.db.prepare(`
      SELECT
        experience_id,
        intent_hash,
        experience_type,
        q_value,
        evidence_json,
        created_at
      FROM memrl_utility_store
      WHERE intent_hash = ? AND q_value > 0.5
      ORDER BY q_value DESC, updated_at DESC
      LIMIT ?
    `).all(intentHash, k) as Experience[];
  }

  /**
   * 获取所有高 Q 值 Experience (跨意图)
   */
  getAllTopExperiences(k: number = 20): Experience[] {
    return this.db.prepare(`
      SELECT
        experience_id,
        intent_hash,
        experience_type,
        q_value,
        evidence_json,
        created_at
      FROM memrl_utility_store
      WHERE q_value > 0.6
      ORDER BY q_value DESC, update_count DESC
      LIMIT ?
    `).all(k) as Experience[];
  }

  /**
   * 获取低 Q 值 Experience (需要改进)
   */
  getLowQExperiences(threshold: number = 0.4, k: number = 10): Experience[] {
    return this.db.prepare(`
      SELECT
        experience_id,
        intent_hash,
        experience_type,
        q_value,
        evidence_json,
        created_at
      FROM memrl_utility_store
      WHERE q_value < ?
      ORDER BY q_value ASC, update_count DESC
      LIMIT ?
    `).all(threshold, k) as Experience[];
  }

  /**
   * 获取 Q 值统计
   */
  getStats(): {
    totalRecords: number;
    avgQ: number;
    highQ: number;
    mediumQ: number;
    lowQ: number;
    avgUpdates: number;
  } {
    const result = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(q_value) as avg_q,
        SUM(CASE WHEN q_value >= 0.6 THEN 1 ELSE 0 END) as high_q,
        SUM(CASE WHEN q_value >= 0.4 AND q_value < 0.6 THEN 1 ELSE 0 END) as medium_q,
        SUM(CASE WHEN q_value < 0.4 THEN 1 ELSE 0 END) as low_q,
        AVG(update_count) as avg_updates
      FROM memrl_utility_store
    `).get() as any;

    return {
      totalRecords: result?.total || 0,
      avgQ: result?.avg_q || 0.5,
      highQ: result?.high_q || 0,
      mediumQ: result?.medium_q || 0,
      lowQ: result?.low_q || 0,
      avgUpdates: result?.avg_updates || 0
    };
  }

  /**
   * 获取意图分布
   */
  getIntentDistribution(limit: number = 10): Array<{ intent_hash: string; count: number; avg_q: number }> {
    return this.db.prepare(`
      SELECT
        intent_hash,
        COUNT(*) as count,
        AVG(q_value) as avg_q
      FROM memrl_utility_store
      GROUP BY intent_hash
      ORDER BY count DESC
      LIMIT ?
    `).all(limit) as any[];
  }

  /**
   * 重置学习率 (用于新阶段)
   */
  resetAlpha(intentHash?: string): void {
    if (intentHash) {
      this.db.prepare(`
        UPDATE memrl_utility_store
        SET alpha = ?
        WHERE intent_hash = ?
      `).run(this.defaultAlpha, intentHash);
    } else {
      this.db.prepare(`
        UPDATE memrl_utility_store
        SET alpha = ?
      `).run(this.defaultAlpha);
    }
  }

  close(): void {
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const updater = new QUpdater();

  const command = process.argv[2] || 'stats';

  if (command === 'stats') {
    console.log('📊 Q 值统计\n');
    const stats = updater.getStats();
    console.log(`总记录: ${stats.totalRecords}`);
    console.log(`平均 Q: ${stats.avgQ.toFixed(3)}`);
    console.log(`高 Q (≥0.6): ${stats.highQ}`);
    console.log(`中 Q (0.4-0.6): ${stats.mediumQ}`);
    console.log(`低 Q (<0.4): ${stats.lowQ}`);
    console.log(`平均更新次数: ${stats.avgUpdates.toFixed(1)}`);
  }

  if (command === 'top') {
    const k = parseInt(process.argv[3] || '10');
    console.log(`🏆 Top-${k} Experience\n`);
    const top = updater.getAllTopExperiences(k);
    for (let i = 0; i < top.length; i++) {
      const exp = top[i];
      console.log(`${i + 1}. [${exp.intent_hash.substring(0, 16)}...] Q=${exp.q_value.toFixed(2)}`);
    }
  }

  if (command === 'update') {
    const intent = process.argv[3] || 'test_intent';
    const expId = process.argv[4] || `exp_${Date.now()}`;
    const reward = parseFloat(process.argv[5] || '1');

    const qNew = updater.update(intent, expId, reward);
    console.log(`✅ Q 更新: ${intent} / ${expId} → Q=${qNew.toFixed(3)}`);
  }

  if (command === 'distribution') {
    console.log('📈 意图分布\n');
    const dist = updater.getIntentDistribution(10);
    for (const row of dist) {
      console.log(`${row.intent_hash.substring(0, 20)}... count=${row.count} avg_q=${row.avg_q.toFixed(2)}`);
    }
  }

  updater.close();
}
