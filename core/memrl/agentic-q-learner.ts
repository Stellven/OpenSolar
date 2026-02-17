/**
 * CMU Agentic Search 数据 → Q 值学习
 *
 * 数据来源: DeepResearchGym Agentic Search Logs
 * 论文: "Agentic Search in the Wild" (arXiv:2601.17617)
 * 规模: 14M+ 查询记录
 *
 * 核心思路:
 * 1. 从查询行为推断用户满意度
 * 2. 生成伪 Q 值标签
 * 3. 用于 Solar 的 MEMRL 初始化
 */

import { Database } from 'bun:sqlite';

interface AgenticSession {
  session_id: string;
  session_len: number;
  queries: AgenticQuery[];
}

interface AgenticQuery {
  query_id: number;
  query: string;
  time_offset: number;
  retrieval_depth: number;
}

interface InferredSignal {
  session_id: string;
  intent_hash: string;  // 从 query 提取
  pseudo_q: number;     // 推断的伪 Q 值
  confidence: number;   // 推断置信度
  evidence: string[];   // 推断依据
}

export class AgenticSearchQLearner {
  private db: Database;
  private dataPath: string;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    dataPath: string = `${process.env.HOME}/Solar/data/agentic_search_sessions.tsv`
  ) {
    this.db = new Database(dbPath);
    this.dataPath = dataPath;
  }

  /**
   * 从查询文本生成 intent_hash (简化版)
   */
  hashIntent(query: string): string {
    // 提取关键词
    const keywords = query.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 2)
      .slice(0, 5)
      .sort()
      .join('_');

    // 简单 hash
    let hash = 0;
    for (let i = 0; i < keywords.length; i++) {
      const char = keywords.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return `intent_${Math.abs(hash).toString(16)}`;
  }

  /**
   * 从会话行为推断 Q 值
   *
   * 启发式规则:
   * 1. 短会话 (len=1) + 低检索深度 → 高 Q (快速成功)
   * 2. 短会话 + 高检索深度 → 中 Q (找到了，但需要更多信息)
   * 3. 长会话 + 最后查询间隔大 → 中高 Q (可能找到了)
   * 4. 长会话 + 频繁改写 → 低 Q (不满意)
   * 5. 重复相同查询 → 低 Q (没找到)
   */
  inferQValue(session: AgenticSession): InferredSignal {
    const evidence: string[] = [];
    let q = 0.5;
    let confidence = 0.3;

    const len = session.session_len;
    const lastQuery = session.queries[session.queries.length - 1];
    const firstQuery = session.queries[0];

    // 1. 会话长度
    if (len === 1) {
      evidence.push(`短会话 (len=1)`);
      q = 0.8;
      confidence = 0.6;
    } else if (len <= 3) {
      evidence.push(`中等会话 (len=${len})`);
      q = 0.6;
      confidence = 0.5;
    } else if (len <= 6) {
      evidence.push(`较长会话 (len=${len})`);
      q = 0.4;
      confidence = 0.4;
    } else {
      evidence.push(`长会话 (len=${len})`);
      q = 0.3;
      confidence = 0.5;
    }

    // 2. 检索深度
    const avgDepth = session.queries.reduce((s, q) => s + q.retrieval_depth, 0) / len;
    if (avgDepth <= 3) {
      evidence.push(`低检索深度 (${avgDepth.toFixed(1)})`);
      q += 0.1;
    } else if (avgDepth > 7) {
      evidence.push(`高检索深度 (${avgDepth.toFixed(1)})`);
      q -= 0.1;
    }

    // 3. 最后查询时间间隔
    if (len > 1 && lastQuery.time_offset > 60) {
      evidence.push(`最后查询间隔大 (${lastQuery.time_offset}s)`);
      q += 0.15;  // 可能找到了答案
    }

    // 4. 查询重复度
    const uniqueQueries = new Set(session.queries.map(q => q.query.toLowerCase()));
    if (uniqueQueries.size < len * 0.5) {
      evidence.push(`查询重复度高`);
      q -= 0.2;
    }

    // 5. 查询改写模式
    if (len > 2) {
      const intervals = [];
      for (let i = 1; i < session.queries.length; i++) {
        intervals.push(session.queries[i].time_offset - session.queries[i-1].time_offset);
      }
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;

      if (avgInterval < 10) {
        evidence.push(`快速改写 (${avgInterval.toFixed(0)}s/查询)`);
        q -= 0.1;  // 快速改写可能表示不满意
      }
    }

    // clip to [0, 1]
    q = Math.max(0, Math.min(1, q));

    return {
      session_id: session.session_id,
      intent_hash: this.hashIntent(firstQuery.query),
      pseudo_q: Math.round(q * 100) / 100,
      confidence: Math.round(confidence * 100) / 100,
      evidence
    };
  }

  /**
   * 解析 TSV 文件并批量处理
   */
  async processBatch(
    batchSize: number = 10000,
    maxSessions: number = 100000,
    onProgress?: (processed: number, total: number) => void
  ): Promise<{ processed: number; sessions: Map<string, AgenticSession> }> {
    const file = Bun.file(this.dataPath);
    const text = await file.text();
    const lines = text.trim().split('\n');

    // 跳过 header
    const dataLines = lines.slice(1);

    const sessions = new Map<string, AgenticSession>();
    let processed = 0;

    for (const line of dataLines) {
      if (processed >= maxSessions * 10) break; // 限制行数

      const parts = line.split('\t');
      if (parts.length < 6) continue;

      const [sessionId, sessionLen, queryId, query, timeOffset, retrievalDepth] = parts;

      if (!sessions.has(sessionId)) {
        sessions.set(sessionId, {
          session_id: sessionId,
          session_len: parseInt(sessionLen),
          queries: []
        });
      }

      const session = sessions.get(sessionId)!;
      session.queries.push({
        query_id: parseInt(queryId),
        query,
        time_offset: parseInt(timeOffset),
        retrieval_depth: parseInt(retrievalDepth)
      });

      processed++;
      if (onProgress && processed % batchSize === 0) {
        onProgress(processed, Math.min(dataLines.length, maxSessions * 10));
      }
    }

    return { processed, sessions };
  }

  /**
   * 将推断的 Q 值写入数据库
   */
  writeToDatabase(signals: InferredSignal[]): number {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO memrl_utility_store
      (intent_hash, experience_id, utility_total, q_value, evidence_json, experience_type)
      VALUES (?, ?, ?, ?, ?, 'agentic_search')
    `);

    let count = 0;
    for (const signal of signals) {
      stmt.run(
        signal.intent_hash,
        `agentic_${signal.session_id}`,
        signal.pseudo_q,
        signal.pseudo_q,
        JSON.stringify({
          confidence: signal.confidence,
          evidence: signal.evidence,
          source: 'cmu_agentic_search'
        })
      );
      count++;
    }

    return count;
  }

  /**
   * 分析数据集统计
   */
  async analyzeDataset(sampleSize: number = 10000): Promise<any> {
    const { sessions } = await this.processBatch(1000, sampleSize / 5);

    const stats = {
      total_sessions: sessions.size,
      session_lengths: { 1: 0, 2: 0, 3: 0, '4-5': 0, '6+': 0 },
      avg_depth: 0,
      intents: new Map<string, number>()
    };

    let totalDepth = 0;
    let totalQueries = 0;

    for (const [, session] of sessions) {
      const len = session.session_len;
      if (len === 1) stats.session_lengths['1']++;
      else if (len === 2) stats.session_lengths['2']++;
      else if (len === 3) stats.session_lengths['3']++;
      else if (len <= 5) stats.session_lengths['4-5']++;
      else stats.session_lengths['6+']++;

      for (const q of session.queries) {
        totalDepth += q.retrieval_depth;
        totalQueries++;

        const intent = this.hashIntent(q.query);
        stats.intents.set(intent, (stats.intents.get(intent) || 0) + 1);
      }
    }

    stats.avg_depth = totalQueries > 0 ? totalDepth / totalQueries : 0;

    return {
      ...stats,
      unique_intents: stats.intents.size
    };
  }

  close(): void {
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const learner = new AgenticSearchQLearner();

  const command = process.argv[2] || 'analyze';

  if (command === 'analyze') {
    console.log('📊 分析 CMU Agentic Search 数据集...\n');
    const stats = await learner.analyzeDataset(10000);
    console.log('数据集统计:');
    console.log(`  总会话数: ${stats.total_sessions}`);
    console.log(`  平均检索深度: ${stats.avg_depth.toFixed(2)}`);
    console.log(`  唯一意图数: ${stats.unique_intents}`);
    console.log(`  会话长度分布:`);
    for (const [len, count] of Object.entries(stats.session_lengths)) {
      console.log(`    ${len}查询: ${count}`);
    }
  }

  if (command === 'learn') {
    const sampleSize = parseInt(process.argv[3] || '10000');
    console.log(`🧠 从 ${sampleSize} 条记录学习 Q 值...\n`);

    const { processed, sessions } = await learner.processBatch(1000, sampleSize / 5);

    console.log(`处理了 ${processed} 行，${sessions.size} 个会话`);

    const signals: InferredSignal[] = [];
    for (const [, session] of sessions) {
      const signal = learner.inferQValue(session);
      signals.push(signal);
    }

    // 统计 Q 值分布
    const qBuckets = { high: 0, medium: 0, low: 0 };
    for (const s of signals) {
      if (s.pseudo_q >= 0.6) qBuckets.high++;
      else if (s.pseudo_q >= 0.4) qBuckets.medium++;
      else qBuckets.low++;
    }

    console.log(`\n推断 Q 值分布:`);
    console.log(`  高 (≥0.6): ${qBuckets.high} (${(qBuckets.high/signals.length*100).toFixed(1)}%)`);
    console.log(`  中 (0.4-0.6): ${qBuckets.medium} (${(qBuckets.medium/signals.length*100).toFixed(1)}%)`);
    console.log(`  低 (<0.4): ${qBuckets.low} (${(qBuckets.low/signals.length*100).toFixed(1)}%)`);

    // 写入数据库
    const written = learner.writeToDatabase(signals);
    console.log(`\n✅ 写入 ${written} 条 Q 值到数据库`);
  }

  learner.close();
}
