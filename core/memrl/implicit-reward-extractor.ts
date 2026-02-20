/**
 * MEMRL Implicit Reward Extractor v1.0
 *
 * 从现有轨迹数据中提取隐式负面反馈信号
 * 解决 100:1 数据失衡问题
 *
 * 算法来源:
 * - Kuaishou GVV Framework (CIKM 2023): 行为阈值化
 * - ACL 2024 AsTrix Pipeline: 对话隐式负面分类
 * - Hu-Koren (2008): 置信度加权聚合
 * - IJCAI 2019: 强化负采样
 */

import { Database } from 'bun:sqlite';

// 隐式负面信号类型
export enum ImplicitSignalType {
  // 工具调用层
  ToolRejected = 'tool_rejected',           // 用户拒绝工具调用（-0.8）
  UserInterruption = 'user_interruption',   // 用户中断执行（-0.6）
  ToolErrorStorm = 'tool_error_storm',      // 工具连续失败（-0.5）

  // 对话层
  UserCorrection = 'user_correction',       // 用户纠正 AI（-0.7）
  TaskAbandonment = 'task_abandonment',     // 任务放弃（-0.5）
  ShortNegative = 'short_negative',         // 短回复否定（-0.3）
  Rephrase = 'rephrase',                    // 重新措辞（-0.4）

  // 会话层
  EarlyTermination = 'early_termination'    // 会话早期结束（-0.3）
}

// 信号配置
interface SignalConfig {
  type: ImplicitSignalType;
  weight: number;         // 置信度权重
  baseReward: number;     // 基础奖励值（负数）
}

// 提取结果
interface ExtractedSignal {
  sessionId: string;
  signalType: ImplicitSignalType;
  confidence: number;     // [0, 1]
  reward: number;         // 负数
  evidence: string;       // 证据文本
  timestamp: Date;
  relatedTool?: string;
  relatedModel?: string;
}

export class ImplicitRewardExtractor {
  private db: Database;

  // 信号配置表（Phase 1 高优先级信号）
  private signalConfigs: SignalConfig[] = [
    { type: ImplicitSignalType.ToolRejected, weight: 0.9, baseReward: -0.8 },
    { type: ImplicitSignalType.UserInterruption, weight: 0.8, baseReward: -0.6 },
    { type: ImplicitSignalType.UserCorrection, weight: 0.8, baseReward: -0.7 },
    { type: ImplicitSignalType.ToolErrorStorm, weight: 0.7, baseReward: -0.5 },
    { type: ImplicitSignalType.TaskAbandonment, weight: 0.6, baseReward: -0.5 },
    { type: ImplicitSignalType.Rephrase, weight: 0.6, baseReward: -0.4 },
    { type: ImplicitSignalType.ShortNegative, weight: 0.4, baseReward: -0.3 },
    { type: ImplicitSignalType.EarlyTermination, weight: 0.5, baseReward: -0.3 }
  ];

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
  }

  /**
   * 主入口：从所有数据源提取隐式负面信号
   */
  async extractAll(limitDays: number = 30): Promise<ExtractedSignal[]> {
    const signals: ExtractedSignal[] = [];

    // Layer 1: 工具调用层信号
    signals.push(...this.extractToolRejected(limitDays));
    signals.push(...this.extractUserInterruption(limitDays));
    signals.push(...this.extractToolErrorStorm(limitDays));

    // Layer 2: 对话层信号
    signals.push(...this.extractUserCorrection(limitDays));
    signals.push(...this.extractTaskAbandonment(limitDays));
    signals.push(...this.extractShortNegative(limitDays));
    signals.push(...this.extractRephrase(limitDays));

    // Layer 3: 会话层信号
    signals.push(...this.extractEarlyTermination(limitDays));

    return signals;
  }

  /**
   * 时间衰减函数（7天半衰期）
   */
  private timeDecay(timestamp: Date): number {
    const now = new Date();
    const daysSince = (now.getTime() - timestamp.getTime()) / (1000 * 60 * 60 * 24);
    return Math.exp(-0.1 * daysSince);
  }

  /**
   * 信号 A: 工具拒绝
   */
  private extractToolRejected(limitDays: number): ExtractedSignal[] {
    const sql = `
      SELECT session_id, content, timestamp
      FROM evo_dialogs
      WHERE role = 'user'
        AND (content LIKE '%tool use was rejected%'
          OR content LIKE '%STOP what you are doing%'
          OR content LIKE '%拒绝%')
        AND julianday('now') - julianday(timestamp) < ?
      ORDER BY timestamp DESC
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      content: string;
      timestamp: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.timestamp);
      const decay = this.timeDecay(ts);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.ToolRejected,
        confidence: 0.9 * decay,
        reward: -0.8,
        evidence: row.content.substring(0, 200),
        timestamp: ts
      };
    });
  }

  /**
   * 信号 B: 用户中断
   */
  private extractUserInterruption(limitDays: number): ExtractedSignal[] {
    const sql = `
      SELECT session_id, content, timestamp
      FROM evo_dialogs
      WHERE role = 'user'
        AND content LIKE '%Request interrupted by user%'
        AND julianday('now') - julianday(timestamp) < ?
      ORDER BY timestamp DESC
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      content: string;
      timestamp: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.timestamp);
      const decay = this.timeDecay(ts);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.UserInterruption,
        confidence: 0.8 * decay,
        reward: -0.6,
        evidence: row.content.substring(0, 200),
        timestamp: ts
      };
    });
  }

  /**
   * 信号 C: 工具错误风暴
   */
  private extractToolErrorStorm(limitDays: number): ExtractedSignal[] {
    const sql = `
      SELECT
        session_id,
        COUNT(*) as error_count,
        GROUP_CONCAT(content, ' | ') as evidence,
        MAX(timestamp) as latest_ts
      FROM evo_dialogs
      WHERE role = 'user'
        AND content LIKE '%"is_error":true%'
        AND julianday('now') - julianday(timestamp) < ?
      GROUP BY session_id
      HAVING error_count >= 3
      ORDER BY error_count DESC
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      error_count: number;
      evidence: string;
      latest_ts: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.latest_ts);
      const decay = this.timeDecay(ts);
      // 错误次数越多，惩罚越重
      const intensity = Math.min(1.0, row.error_count / 10);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.ToolErrorStorm,
        confidence: 0.7 * decay,
        reward: -0.5 * intensity,
        evidence: `${row.error_count} errors: ${row.evidence.substring(0, 150)}`,
        timestamp: ts
      };
    });
  }

  /**
   * 信号 D: 用户纠正
   */
  private extractUserCorrection(limitDays: number): ExtractedSignal[] {
    const sql = `
      SELECT session_id, content, timestamp
      FROM evo_dialogs
      WHERE role = 'user'
        AND (content LIKE '%不对%'
          OR content LIKE '%错了%'
          OR content LIKE '%你没%'
          OR content LIKE '%你忘了%'
          OR content LIKE '%你又%'
          OR content LIKE '%应该是%'
          OR content LIKE '%其实是%')
        AND LENGTH(content) < 500
        AND julianday('now') - julianday(timestamp) < ?
      ORDER BY timestamp DESC
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      content: string;
      timestamp: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.timestamp);
      const decay = this.timeDecay(ts);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.UserCorrection,
        confidence: 0.8 * decay,
        reward: -0.7,
        evidence: row.content.substring(0, 200),
        timestamp: ts
      };
    });
  }

  /**
   * 信号 E: 任务放弃
   */
  private extractTaskAbandonment(limitDays: number): ExtractedSignal[] {
    const sql = `
      SELECT session_id, content, timestamp
      FROM evo_dialogs
      WHERE role = 'user'
        AND (content LIKE '%算了%'
          OR content LIKE '%不用了%'
          OR content LIKE '%先这样%'
          OR content LIKE '%随便%'
          OR content LIKE '%行吧%')
        AND julianday('now') - julianday(timestamp) < ?
      ORDER BY timestamp DESC
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      content: string;
      timestamp: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.timestamp);
      const decay = this.timeDecay(ts);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.TaskAbandonment,
        confidence: 0.6 * decay,
        reward: -0.5,
        evidence: row.content.substring(0, 200),
        timestamp: ts
      };
    });
  }

  /**
   * 信号 F: 短回复否定
   */
  private extractShortNegative(limitDays: number): ExtractedSignal[] {
    const sql = `
      SELECT session_id, content, timestamp
      FROM evo_dialogs
      WHERE role = 'user'
        AND LENGTH(content) <= 5
        AND content NOT IN ('好', '可以', 'OK', 'ok', '继续', '嗯嗯', '谢谢')
        AND julianday('now') - julianday(timestamp) < ?
      ORDER BY timestamp DESC
      LIMIT 100
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      content: string;
      timestamp: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.timestamp);
      const decay = this.timeDecay(ts);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.ShortNegative,
        confidence: 0.4 * decay,  // 低置信度
        reward: -0.3,
        evidence: row.content,
        timestamp: ts
      };
    });
  }

  /**
   * 信号 G: 重新措辞（Phase 2 待实现，需要语义相似度）
   */
  private extractRephrase(limitDays: number): ExtractedSignal[] {
    // TODO: 需要嵌入模型计算语义相似度
    // 0.5 < cosine_similarity < 0.9 = 重新措辞
    return [];
  }

  /**
   * 信号 H: 会话早期结束
   */
  private extractEarlyTermination(limitDays: number): ExtractedSignal[] {
    const sql = `
      WITH session_stats AS (
        SELECT
          session_id,
          COUNT(*) as turn_count,
          (julianday(MAX(timestamp)) - julianday(MIN(timestamp))) * 1440 as duration_min,
          MAX(timestamp) as last_ts
        FROM evo_dialogs
        WHERE julianday('now') - julianday(timestamp) < ?
        GROUP BY session_id
      )
      SELECT session_id, turn_count, duration_min, last_ts
      FROM session_stats
      WHERE turn_count < 5 AND duration_min < 5
      ORDER BY last_ts DESC
      LIMIT 50
    `;

    const rows = this.db.prepare(sql).all(limitDays) as Array<{
      session_id: string;
      turn_count: number;
      duration_min: number;
      last_ts: string;
    }>;

    return rows.map(row => {
      const ts = new Date(row.last_ts);
      const decay = this.timeDecay(ts);
      return {
        sessionId: row.session_id,
        signalType: ImplicitSignalType.EarlyTermination,
        confidence: 0.5 * decay,
        reward: -0.3,
        evidence: `${row.turn_count} turns, ${row.duration_min.toFixed(1)} min`,
        timestamp: ts
      };
    });
  }

  /**
   * 核心：Hu-Koren 置信度加权聚合
   *
   * Q_implicit(session) = Σ[w_i × r_i × decay(t_i)] / Σ[w_i × decay(t_i)]
   */
  aggregateSignals(signals: ExtractedSignal[]): {
    sessionId: string;
    qImplicit: number;
    confidence: number;
    signalCount: number;
    evidence: string[];
  }[] {
    // 按 session 分组
    const sessionMap = new Map<string, ExtractedSignal[]>();
    for (const signal of signals) {
      if (!sessionMap.has(signal.sessionId)) {
        sessionMap.set(signal.sessionId, []);
      }
      sessionMap.get(signal.sessionId)!.push(signal);
    }

    // Hu-Koren 聚合
    const results = [];
    for (const [sessionId, sessionSignals] of sessionMap) {
      let numerator = 0;
      let denominator = 0;

      for (const sig of sessionSignals) {
        const w = sig.confidence;
        const r = sig.reward;
        numerator += w * r;
        denominator += w;
      }

      const qImplicit = denominator > 0 ? numerator / denominator : 0;
      const avgConfidence = denominator / sessionSignals.length;

      results.push({
        sessionId,
        qImplicit,
        confidence: avgConfidence,
        signalCount: sessionSignals.length,
        evidence: sessionSignals.map(s => `${s.signalType}:${s.evidence.substring(0, 50)}`).slice(0, 3)
      });
    }

    return results.sort((a, b) => a.qImplicit - b.qImplicit);  // 最负的排前面
  }

  /**
   * 写入 memrl_utility_store 的 u_implicit 字段
   *
   * v2 策略（细粒度）：
   * 1. 从信号中提取 related_tool 字段（如果有）
   * 2. 通过 tool → skill → intent_hash 映射
   * 3. 按 intent_hash 分组计算各自的 u_implicit
   * 4. 无法映射的使用全局基线
   */
  async backfillImplicitRewards(signals: ExtractedSignal[]): Promise<{
    updateCount: number;
    globalBaseline: number;
    intentSpecific: number;
    affectedIntents: number;
  }> {
    // 先按 session 聚合
    const sessionAggregated = this.aggregateSignals(signals);

    // 从 evo_feedback_v2 获取 session → intent_hash 的映射
    // （通过 related_tool/related_skill 推断）
    const sessionToIntent = new Map<string, string>();

    const feedbackMapping = this.db.prepare(`
      SELECT DISTINCT session_id, related_tool, related_skill
      FROM evo_feedback_v2
      WHERE session_id IS NOT NULL
        AND (related_tool IS NOT NULL OR related_skill IS NOT NULL)
    `).all() as Array<{ session_id: string; related_tool: string; related_skill: string }>;

    for (const fb of feedbackMapping) {
      // 简化：用 tool/skill name 生成 intent_hash
      const key = fb.related_tool || fb.related_skill || '';
      if (key) {
        let hash = 0;
        for (let i = 0; i < key.length; i++) {
          hash = ((hash << 5) - hash) + key.charCodeAt(i);
          hash = hash & hash;
        }
        const intentHash = `intent_${Math.abs(hash).toString(16)}`;
        sessionToIntent.set(fb.session_id, intentHash);
      }
    }

    console.log(`映射了 ${sessionToIntent.size} 个 session 到 intent_hash`);

    // 按 intent_hash 分组聚合信号
    const intentSignals = new Map<string, Array<{ q: number; confidence: number }>>();

    for (const sessionAgg of sessionAggregated) {
      const intentHash = sessionToIntent.get(sessionAgg.sessionId);
      if (intentHash) {
        if (!intentSignals.has(intentHash)) {
          intentSignals.set(intentHash, []);
        }
        intentSignals.get(intentHash)!.push({
          q: sessionAgg.qImplicit,
          confidence: sessionAgg.confidence
        });
      }
    }

    // 计算全局基线
    let globalNum = 0, globalDenom = 0;
    for (const sig of signals) {
      globalNum += sig.confidence * sig.reward;
      globalDenom += sig.confidence;
    }
    const qImplicitGlobal = globalDenom > 0 ? globalNum / globalDenom : 0;
    const uImplicitGlobal = (qImplicitGlobal + 1) / 2;

    console.log(`全局隐式 Q: ${qImplicitGlobal.toFixed(3)} → u_implicit: ${uImplicitGlobal.toFixed(3)}`);

    // 更新：先用全局基线
    const globalResult = this.db.prepare(`
      UPDATE memrl_utility_store
      SET u_implicit = ?,
          updated_at = datetime('now')
      WHERE u_implicit = 0
    `).run(uImplicitGlobal);

    // 再用 intent 特定值覆盖
    let intentSpecificCount = 0;
    for (const [intentHash, sigs] of intentSignals) {
      let num = 0, denom = 0;
      for (const s of sigs) {
        num += s.confidence * s.q;
        denom += s.confidence;
      }
      const qImplicit = denom > 0 ? num / denom : qImplicitGlobal;
      const uImplicit = (qImplicit + 1) / 2;

      const result = this.db.prepare(`
        UPDATE memrl_utility_store
        SET u_implicit = ?,
            updated_at = datetime('now')
        WHERE intent_hash = ?
      `).run(uImplicit, intentHash);

      intentSpecificCount += result.changes;
    }

    console.log(`Intent 特定更新: ${intentSpecificCount} 条记录，覆盖 ${intentSignals.size} 个 intent`);

    return {
      updateCount: globalResult.changes,
      globalBaseline: uImplicitGlobal,
      intentSpecific: intentSpecificCount,
      affectedIntents: intentSignals.size
    };
  }

  /**
   * 获取统计
   */
  async getStats(): Promise<{
    totalExtracted: number;
    byType: Record<string, number>;
    avgReward: number;
    avgConfidence: number;
  }> {
    const signals = await this.extractAll(30);
    const byType: Record<string, number> = {};

    let totalReward = 0;
    let totalConfidence = 0;

    for (const sig of signals) {
      byType[sig.signalType] = (byType[sig.signalType] || 0) + 1;
      totalReward += sig.reward;
      totalConfidence += sig.confidence;
    }

    return {
      totalExtracted: signals.length,
      byType,
      avgReward: signals.length > 0 ? totalReward / signals.length : 0,
      avgConfidence: signals.length > 0 ? totalConfidence / signals.length : 0
    };
  }

  close(): void {
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const extractor = new ImplicitRewardExtractor();

  const command = process.argv[2] || 'extract';

  if (command === 'stats') {
    console.log('📊 隐式负面信号提取统计\n');
    const stats = await extractor.getStats();
    console.log(`总提取: ${stats.totalExtracted}`);
    console.log(`平均奖励: ${stats.avgReward.toFixed(3)}`);
    console.log(`平均置信度: ${stats.avgConfidence.toFixed(2)}`);
    console.log('\n按类型:');
    for (const [type, count] of Object.entries(stats.byType)) {
      console.log(`  ${type}: ${count}`);
    }
  }

  if (command === 'extract') {
    console.log('🔍 提取隐式负面信号 (30天内)\n');
    const signals = await extractor.extractAll(30);
    console.log(`发现 ${signals.length} 个隐式负面信号\n`);

    // 聚合
    const aggregated = extractor.aggregateSignals(signals);
    console.log(`聚合后 ${aggregated.length} 个 session\n`);

    // 显示最负的 10 个
    console.log('最负的 10 个 session:');
    for (let i = 0; i < Math.min(10, aggregated.length); i++) {
      const item = aggregated[i];
      console.log(`  ${item.sessionId.substring(0, 12)}... Q=${item.qImplicit.toFixed(3)} (${item.signalCount} signals)`);
    }
  }

  if (command === 'backfill') {
    console.log('💾 回填 u_implicit 到 memrl_utility_store\n');
    const signals = await extractor.extractAll(30);

    const result = await extractor.backfillImplicitRewards(signals);
    console.log(`✅ 全局更新: ${result.updateCount} 条记录`);
    console.log(`✅ Intent 特定: ${result.intentSpecific} 条记录`);
    console.log(`影响 ${result.affectedIntents} 个 intent`);

    // 验证
    const check = extractor.db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(u_implicit) as avg_implicit,
        MIN(u_implicit) as min_implicit,
        MAX(u_implicit) as max_implicit,
        COUNT(DISTINCT u_implicit) as distinct_values
      FROM memrl_utility_store
    `).get() as { total: number; avg_implicit: number; min_implicit: number; max_implicit: number; distinct_values: number };

    console.log(`\n验证:`);
    console.log(`  总记录: ${check.total}`);
    console.log(`  平均 u_implicit: ${check.avg_implicit?.toFixed(3)}`);
    console.log(`  范围: [${check.min_implicit?.toFixed(3)}, ${check.max_implicit?.toFixed(3)}]`);
    console.log(`  不同值数量: ${check.distinct_values}（>1 说明细粒度生效）`);
  }

  extractor.close();
}
