/**
 * MEMRL Unified Retriever - 统一检索器
 *
 * Phase 1 核心组件
 * 职责: 同时从 Memory DB 和 Skill Bank 检索，用 Q 值统一排序
 *
 * 架构:
 * 用户请求 → MultiSourceRetriever → Q-Ranker → Top-K 结果
 *                │
 *                ├── Memory Retriever (TwoPhaseRetriever)
 *                └── Skill Retriever (SkillRetriever)
 */

import { Database } from 'bun:sqlite';
import { TwoPhaseRetriever, RetrievedExperience } from './two-phase-retriever';
import { SkillRetriever, RetrievedSkill } from './skill-retriever';
import { QUpdater } from './q-updater';

// 统一检索结果类型
export type UnifiedItem = RetrievedExperience | RetrievedSkill;

// 检索结果
export interface UnifiedRetrievalResult {
  memories: RetrievedExperience[];
  skills: RetrievedSkill[];
  all: UnifiedItem[];  // 按 combined_score 统一排序
  query: string;
  intentHash: string;
  retrievalTimeMs: number;
}

// 检索配置
interface UnifiedRetrieverConfig {
  maxMemories: number;      // 最大记忆返回数
  maxSkills: number;        // 最大技能返回数
  maxTotal: number;         // 总最大返回数
  memoryWeight: number;     // 记忆权重（在统一排序中）
  skillWeight: number;      // 技能权重
  minQValue: number;        // 最低 Q 值阈值
}

const DEFAULT_CONFIG: UnifiedRetrieverConfig = {
  maxMemories: 5,
  maxSkills: 3,
  maxTotal: 5,
  memoryWeight: 1.0,
  skillWeight: 1.0,
  minQValue: 0.5
};

export class UnifiedRetriever {
  private db: Database;
  private memoryRetriever: TwoPhaseRetriever;
  private skillRetriever: SkillRetriever;
  private qUpdater: QUpdater;
  private config: UnifiedRetrieverConfig;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    config: Partial<UnifiedRetrieverConfig> = {}
  ) {
    this.db = new Database(dbPath);
    this.memoryRetriever = new TwoPhaseRetriever(dbPath);
    this.skillRetriever = new SkillRetriever(dbPath, {
      maxResults: config.maxSkills || 3,
      minQValue: config.minQValue || 0.5
    });
    this.qUpdater = new QUpdater(dbPath);
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 统一检索主入口
   *
   * @param userInput 用户输入
   * @param intentHash 意图哈希
   * @param context 可选上下文
   */
  retrieve(
    userInput: string,
    intentHash: string,
    context?: string
  ): UnifiedRetrievalResult {
    const startTime = Date.now();

    // 1. 并行检索 Memory 和 Skill
    const [memories, skills] = this.parallelRetrieve(userInput, intentHash, context);

    // 2. 统一排序
    const all = this.unifiedRank(memories, skills);

    // 3. 返回结果
    const retrievalTimeMs = Date.now() - startTime;

    return {
      memories: memories.slice(0, this.config.maxMemories),
      skills: skills.slice(0, this.config.maxSkills),
      all: all.slice(0, this.config.maxTotal),
      query: userInput,
      intentHash,
      retrievalTimeMs
    };
  }

  /**
   * 并行检索 Memory 和 Skill
   */
  private parallelRetrieve(
    userInput: string,
    intentHash: string,
    context?: string
  ): [RetrievedExperience[], RetrievedSkill[]] {
    // 这里用同步模拟并行（Bun 是单线程的）
    // 如果需要真正的并行，可以用 Worker

    const memories = this.memoryRetriever.retrieve(intentHash);
    const skills = this.skillRetriever.retrieve(userInput, intentHash, context);

    return [memories, skills];
  }

  /**
   * 统一排序
   *
   * 策略:
   * 1. 关键词匹配度高的 Skill 优先（直接解决问题）
   * 2. 高 Q 值的 Memory 作为补充（提供历史经验）
   *
   * 综合分数 = 类型权重 × (关键词匹配加成 + Q值 × 时间衰减)
   */
  private unifiedRank(
    memories: RetrievedExperience[],
    skills: RetrievedSkill[]
  ): UnifiedItem[] {
    interface ScoredItem {
      item: UnifiedItem;
      type: 'memory' | 'skill';
      unifiedScore: number;
    }

    const scored: ScoredItem[] = [];

    // 评分 Memory
    for (const mem of memories) {
      // Memory 主要基于 Q 值和时间衰减
      const unifiedScore =
        this.config.memoryWeight * mem.combined_score;
      scored.push({
        item: mem,
        type: 'memory',
        unifiedScore
      });
    }

    // 评分 Skill
    for (const skill of skills) {
      // Skill 有关键词匹配加成
      // 如果匹配了关键词，分数应该更高
      const keywordBonus = skill.keyword_match_score > 0 ? 0.3 : 0;

      // 基础分数 = 融合 Q 值（v3 更新）
      const fusedQ = this.qUpdater.getFusedQ(skill.intent_hash);
      const baseScore = fusedQ * 0.5;

      // 综合分数
      const unifiedScore =
        this.config.skillWeight * (baseScore + keywordBonus + skill.keyword_match_score * 0.5);

      scored.push({
        item: skill,
        type: 'skill',
        unifiedScore
      });
    }

    // 按统一分数排序
    scored.sort((a, b) => b.unifiedScore - a.unifiedScore);

    return scored.map(s => s.item);
  }

  /**
   * 格式化输出检索结果
   */
  formatResult(result: UnifiedRetrievalResult): string {
    const lines: string[] = [
      `🔍 统一检索结果 (耗时: ${result.retrievalTimeMs}ms)`,
      `   查询: "${result.query}"`,
      `   Intent: ${result.intentHash}`,
      '',
    ];

    if (result.all.length === 0) {
      lines.push('❌ 无匹配结果');
      return lines.join('\n');
    }

    lines.push(`📊 检索到 ${result.memories.length} 条记忆, ${result.skills.length} 个技能`);
    lines.push('');
    lines.push('📚 统一排序结果:');
    lines.push('');

    for (let i = 0; i < result.all.length; i++) {
      const item = result.all[i];
      const isSkill = 'skill_id' in item;

      if (isSkill) {
        const skill = item as RetrievedSkill;
        lines.push(`${i + 1}. [SKILL] ${skill.name}`);
        lines.push(`   Q=${skill.q_value.toFixed(2)} | 匹配: ${skill.matched_keywords.join(', ') || '(无)'}`);
        lines.push(`   综合分数: ${skill.combined_score.toFixed(3)}`);
      } else {
        const mem = item as RetrievedExperience;
        lines.push(`${i + 1}. [MEMORY] ${mem.experience_id}`);
        lines.push(`   Q=${mem.q_value.toFixed(2)} | Intent: ${mem.intent_hash.substring(0, 15)}...`);
        lines.push(`   综合分数: ${mem.combined_score.toFixed(3)}`);
      }
      lines.push('');
    }

    return lines.join('\n');
  }

  /**
   * 获取统计信息
   */
  getStats(): {
    memories: ReturnType<TwoPhaseRetriever['getStats']>;
    skills: ReturnType<SkillRetriever['getStats']>;
  } {
    return {
      memories: this.memoryRetriever.getStats(),
      skills: this.skillRetriever.getStats()
    };
  }

  /**
   * 更新配置
   */
  updateConfig(config: Partial<UnifiedRetrieverConfig>): void {
    this.config = { ...this.config, ...config };
    this.skillRetriever.updateConfig({
      maxResults: this.config.maxSkills,
      minQValue: this.config.minQValue
    });
  }

  close(): void {
    this.memoryRetriever.close();
    this.skillRetriever.close();
    this.qUpdater.close();
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const retriever = new UnifiedRetriever();

  const command = process.argv[2] || 'stats';
  const query = process.argv.slice(3).join(' ') || '性能优化';
  const intentHash = `intent_${Buffer.from(query).toString('base64').slice(0, 16)}`;

  if (command === 'stats') {
    console.log('📊 Unified Retriever 统计\n');
    const stats = retriever.getStats();
    console.log('Memory:');
    console.log(`  总经验: ${stats.memories.totalExperiences}`);
    console.log(`  平均 Q: ${stats.memories.avgQValue.toFixed(3)}`);
    console.log('');
    console.log('Skills:');
    console.log(`  总技能: ${stats.skills.totalSkills}`);
    console.log(`  平均 Q: ${stats.skills.avgQValue.toFixed(3)}`);
  }

  if (command === 'search' || command === 'retrieve') {
    const result = retriever.retrieve(query, intentHash);
    console.log(retriever.formatResult(result));
  }

  retriever.close();
}
