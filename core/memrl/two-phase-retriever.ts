/**
 * MEMRL Two-Phase Retriever - 两阶段检索器
 *
 * Phase 1 核心组件
 * 职责: 语义召回 + 价值感知排序
 *
 * 参考: MEMRL 论文 Section 3.2
 * Phase A: Recall by similarity (语义相似度)
 * Phase B: Select by Q-value (价值感知)
 */

import { Database } from 'bun:sqlite';

interface Experience {
  id: number;
  intent_hash: string;
  experience_id: string;
  experience_type: string;
  q_value: number;
  utility_total: number;
  update_count: number;
  evidence_json: string | null;
  created_at: string;
  updated_at: string;
}

interface RetrievedExperience extends Experience {
  similarity_score: number;
  recency_score: number;
  combined_score: number;
}

interface RetrievalConfig {
  recallTopK: number;       // Phase A 召回数量
  finalTopK: number;        // Phase B 返回数量
  similarityWeight: number; // 相似度权重
  qValueWeight: number;     // Q 值权重
  recencyDecay: number;     // 时间衰减系数 (λ)
}

const DEFAULT_CONFIG: RetrievalConfig = {
  recallTopK: 20,
  finalTopK: 5,
  similarityWeight: 0.3,
  qValueWeight: 0.5,
  recencyDecay: 0.05  // e^(-0.05 * days)
};

export class TwoPhaseRetriever {
  private db: Database;
  private config: RetrievalConfig;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    config: Partial<RetrievalConfig> = {}
  ) {
    this.db = new Database(dbPath);
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Phase A: 语义召回
   *
   * 从 memrl_utility_store 中召回相似的 Experience
   * 相似度基于: intent_hash 匹配 + 时间衰减
   */
  phaseA_recall(intentHash: string): Experience[] {
    // 1. 精确匹配 intent_hash
    const exactMatches = this.db.prepare(`
      SELECT
        id, intent_hash, experience_id, experience_type,
        q_value, utility_total, update_count, evidence_json,
        created_at, updated_at
      FROM memrl_utility_store
      WHERE intent_hash = ?
      ORDER BY q_value DESC
      LIMIT ?
    `).all(intentHash, this.config.recallTopK) as Experience[];

    if (exactMatches.length >= this.config.recallTopK) {
      return exactMatches;
    }

    // 2. 模糊匹配 (intent_hash 前缀匹配)
    const prefixMatches = this.db.prepare(`
      SELECT
        id, intent_hash, experience_id, experience_type,
        q_value, utility_total, update_count, evidence_json,
        created_at, updated_at
      FROM memrl_utility_store
      WHERE intent_hash LIKE ? || '%'
        AND intent_hash != ?
      ORDER BY q_value DESC
      LIMIT ?
    `).all(intentHash.substring(0, 8), intentHash, this.config.recallTopK - exactMatches.length) as Experience[];

    return [...exactMatches, ...prefixMatches];
  }

  /**
   * 计算时间衰减分数
   *
   * recency_score = e^(-λ × days_since_update)
   */
  calculateRecencyScore(updatedAt: string): number {
    const updated = new Date(updatedAt).getTime();
    const now = Date.now();
    const daysSince = (now - updated) / (1000 * 60 * 60 * 24);

    return Math.exp(-this.config.recencyDecay * daysSince);
  }

  /**
   * Phase B: 价值感知排序
   *
   * combined_score = w_sim × similarity + w_q × q_value × recency
   */
  phaseB_rank(experiences: Experience[], intentHash: string): RetrievedExperience[] {
    const scored: RetrievedExperience[] = experiences.map(exp => {
      // 相似度分数 (精确匹配=1, 前缀匹配=0.7)
      const similarityScore = exp.intent_hash === intentHash ? 1.0 : 0.7;

      // 时间衰减分数
      const recencyScore = this.calculateRecencyScore(exp.updated_at);

      // 综合分数
      const combinedScore =
        this.config.similarityWeight * similarityScore +
        this.config.qValueWeight * exp.q_value * recencyScore;

      return {
        ...exp,
        similarity_score: similarityScore,
        recency_score: recencyScore,
        combined_score: combinedScore
      };
    });

    // 按综合分数降序排序
    scored.sort((a, b) => b.combined_score - a.combined_score);

    return scored.slice(0, this.config.finalTopK);
  }

  /**
   * 两阶段检索主入口
   */
  retrieve(intentHash: string): RetrievedExperience[] {
    // Phase A: 召回
    const candidates = this.phaseA_recall(intentHash);

    if (candidates.length === 0) {
      // 无匹配时，返回全局 Top-K 高 Q 值经验
      return this.getGlobalTopK();
    }

    // Phase B: 排序
    return this.phaseB_rank(candidates, intentHash);
  }

  /**
   * 获取全局 Top-K (当无精确匹配时)
   */
  getGlobalTopK(): RetrievedExperience[] {
    const experiences = this.db.prepare(`
      SELECT
        id, intent_hash, experience_id, experience_type,
        q_value, utility_total, update_count, evidence_json,
        created_at, updated_at
      FROM memrl_utility_store
      WHERE q_value > 0.5
      ORDER BY q_value DESC, update_count DESC
      LIMIT ?
    `).all(this.config.finalTopK) as Experience[];

    return experiences.map(exp => ({
      ...exp,
      similarity_score: 0,
      recency_score: this.calculateRecencyScore(exp.updated_at),
      combined_score: exp.q_value * this.calculateRecencyScore(exp.updated_at)
    }));
  }

  /**
   * 获取推荐的 Experience ID 列表
   */
  getRecommendedExperienceIds(intentHash: string): string[] {
    const results = this.retrieve(intentHash);
    return results.map(r => r.experience_id);
  }

  /**
   * 更新配置
   */
  updateConfig(config: Partial<RetrievalConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * 获取检索统计
   */
  getStats(): {
    totalExperiences: number;
    uniqueIntents: number;
    avgQValue: number;
    highQCount: number;
  } {
    const result = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        COUNT(DISTINCT intent_hash) as unique_intents,
        AVG(q_value) as avg_q,
        SUM(CASE WHEN q_value >= 0.6 THEN 1 ELSE 0 END) as high_q
      FROM memrl_utility_store
    `).get() as any;

    return {
      totalExperiences: result?.total || 0,
      uniqueIntents: result?.unique_intents || 0,
      avgQValue: result?.avg_q || 0,
      highQCount: result?.high_q || 0
    };
  }

  close(): void {
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const retriever = new TwoPhaseRetriever();

  const command = process.argv[2] || 'stats';
  const intentHash = process.argv[3] || 'intent_test';

  if (command === 'stats') {
    console.log('📊 检索器统计\n');
    const stats = retriever.getStats();
    console.log(`总经验数: ${stats.totalExperiences}`);
    console.log(`唯一意图数: ${stats.uniqueIntents}`);
    console.log(`平均 Q 值: ${stats.avgQValue.toFixed(3)}`);
    console.log(`高 Q 经验数: ${stats.highQCount}`);
  }

  if (command === 'retrieve') {
    console.log(`🔍 检索意图: ${intentHash}\n`);

    const results = retriever.retrieve(intentHash);

    if (results.length === 0) {
      console.log('❌ 无匹配经验');
    } else {
      console.log(`找到 ${results.length} 个相关经验:\n`);
      for (let i = 0; i < results.length; i++) {
        const r = results[i];
        console.log(`${i + 1}. [${r.experience_id}]`);
        console.log(`   Intent: ${r.intent_hash}`);
        console.log(`   Q=${r.q_value.toFixed(2)} Sim=${r.similarity_score.toFixed(2)} Rec=${r.recency_score.toFixed(2)}`);
        console.log(`   Combined=${r.combined_score.toFixed(3)}`);
        console.log();
      }
    }
  }

  if (command === 'ids') {
    const ids = retriever.getRecommendedExperienceIds(intentHash);
    console.log(`推荐 Experience IDs: ${ids.join(', ')}`);
  }

  retriever.close();
}
