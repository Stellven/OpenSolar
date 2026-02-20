/**
 * MEMRL Skill Retriever - 技能检索器
 *
 * Phase 1 核心组件
 * 职责: 从 sys_skill_bank 检索相关技能
 *
 * 检索策略:
 * 1. 关键词匹配 (trigger_keywords)
 * 2. Intent Hash 匹配
 * 3. 上下文过滤 (applicable_contexts)
 * 4. Q 值排序
 */

import { Database } from 'bun:sqlite';
import { QUpdater } from './q-updater';

// 技能数据结构
export interface Skill {
  skill_id: string;
  name: string;
  description: string;
  skill_type: 'template' | 'workflow' | 'api_call';
  intent_hash: string;
  q_value: number;
  llm_prompt_template: string;
  parameters: string;  // JSON
  trigger_keywords: string;  // JSON
  applicable_contexts: string;  // JSON
  tags: string;  // JSON
  success_count: number;
  failure_count: number;
  avg_execution_time_ms: number | null;
  source: string;
  validated: number;
  created_at: string;
  updated_at: string;
}

// 检索结果（带匹配分数）
export interface RetrievedSkill extends Skill {
  keyword_match_score: number;   // 关键词匹配分数
  intent_match_score: number;     // Intent 匹配分数
  context_match_score: number;    // 上下文匹配分数
  combined_score: number;         // 综合分数
  matched_keywords: string[];     // 匹配到的关键词
}

// 检索配置
interface SkillRetrievalConfig {
  maxResults: number;           // 最大返回数量
  minQValue: number;            // 最低 Q 值阈值
  keywordWeight: number;        // 关键词权重
  intentWeight: number;         // Intent 权重
  qValueWeight: number;         // Q 值权重
  contextWeight: number;        // 上下文权重
  requireValidated: boolean;    // 是否只返回已验证的
}

const DEFAULT_CONFIG: SkillRetrievalConfig = {
  maxResults: 5,
  minQValue: 0.5,
  keywordWeight: 0.4,
  intentWeight: 0.3,
  qValueWeight: 0.2,
  contextWeight: 0.1,
  requireValidated: false
};

export class SkillRetriever {
  private db: Database;
  private qUpdater: QUpdater;
  private config: SkillRetrievalConfig;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    config: Partial<SkillRetrievalConfig> = {}
  ) {
    this.db = new Database(dbPath);
    this.qUpdater = new QUpdater(dbPath);
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 主检索入口
   *
   * @param userInput 用户输入文本
   * @param intentHash 可选的 Intent Hash
   * @param context 可选的上下文（如 'coding', 'review'）
   */
  retrieve(
    userInput: string,
    intentHash?: string,
    context?: string
  ): RetrievedSkill[] {
    // 1. 获取所有候选技能
    const candidates = this.getCandidates();

    if (candidates.length === 0) {
      return [];
    }

    // 2. 计算每个技能的匹配分数
    const scored = candidates.map(skill => this.scoreSkill(
      skill,
      userInput,
      intentHash,
      context
    ));

    // 3. 过滤低分技能
    const filtered = scored.filter(s => s.combined_score > 0.1);

    // 4. 按综合分数排序
    filtered.sort((a, b) => b.combined_score - a.combined_score);

    // 5. 返回 Top-K
    return filtered.slice(0, this.config.maxResults);
  }

  /**
   * 获取候选技能列表
   */
  private getCandidates(): Skill[] {
    let query = `
      SELECT *
      FROM sys_skill_bank
      WHERE q_value >= ?
    `;

    const params: any[] = [this.config.minQValue];

    if (this.config.requireValidated) {
      query += ` AND validated = 1`;
    }

    query += ` ORDER BY q_value DESC`;

    return this.db.prepare(query).all(...params) as Skill[];
  }

  /**
   * 计算技能匹配分数
   *
   * v3 更新: 使用融合 Q 值（结合隐式负面信号）
   */
  private scoreSkill(
    skill: Skill,
    userInput: string,
    intentHash?: string,
    context?: string
  ): RetrievedSkill {
    // 1. 关键词匹配
    const { score: keywordScore, matchedKeywords } = this.matchKeywords(
      userInput,
      skill.trigger_keywords
    );

    // 2. Intent Hash 匹配
    const intentScore = intentHash
      ? this.matchIntentHash(intentHash, skill.intent_hash)
      : 0;

    // 3. 上下文匹配
    const contextScore = context
      ? this.matchContext(context, skill.applicable_contexts)
      : 0.5; // 无上下文时给中性分数

    // 4. 获取融合 Q 值（从 memrl_utility_store 查询）
    const fusedQ = this.qUpdater.getFusedQ(skill.intent_hash);

    // 5. 综合分数
    const combinedScore =
      this.config.keywordWeight * keywordScore +
      this.config.intentWeight * intentScore +
      this.config.qValueWeight * fusedQ +  // 使用融合 Q 而非原始 q_value
      this.config.contextWeight * contextScore;

    return {
      ...skill,
      keyword_match_score: keywordScore,
      intent_match_score: intentScore,
      context_match_score: contextScore,
      combined_score: combinedScore,
      matched_keywords: matchedKeywords
    };
  }

  /**
   * 关键词匹配
   *
   * @returns 匹配分数 (0-1) 和匹配到的关键词列表
   */
  private matchKeywords(
    userInput: string,
    keywordsJson: string
  ): { score: number; matchedKeywords: string[] } {
    const keywords: string[] = JSON.parse(keywordsJson || '[]');
    const inputLower = userInput.toLowerCase();

    const matchedKeywords: string[] = [];

    for (const keyword of keywords) {
      if (inputLower.includes(keyword.toLowerCase())) {
        matchedKeywords.push(keyword);
      }
    }

    // 分数 = 匹配数 / 总关键词数，但至少匹配 1 个才有分
    if (matchedKeywords.length === 0) {
      return { score: 0, matchedKeywords: [] };
    }

    // 匹配比例，但上限为 1
    const score = Math.min(matchedKeywords.length / Math.max(keywords.length, 1), 1);

    return { score, matchedKeywords };
  }

  /**
   * Intent Hash 匹配
   *
   * 精确匹配 = 1.0
   * 前缀匹配 = 0.7
   * 无匹配 = 0
   */
  private matchIntentHash(
    queryHash: string,
    skillHash: string
  ): number {
    if (queryHash === skillHash) {
      return 1.0;
    }

    // 前缀匹配（前 8 个字符）
    if (queryHash.substring(0, 8) === skillHash.substring(0, 8)) {
      return 0.7;
    }

    return 0;
  }

  /**
   * 上下文匹配
   */
  private matchContext(
    context: string,
    contextsJson: string
  ): number {
    const contexts: string[] = JSON.parse(contextsJson || '[]');

    if (contexts.length === 0) {
      return 0.5; // 无上下文约束时给中性分数
    }

    return contexts.includes(context) ? 1.0 : 0;
  }

  /**
   * 根据技能 ID 获取技能详情
   */
  getSkillById(skillId: string): Skill | null {
    return this.db.prepare(`
      SELECT * FROM sys_skill_bank WHERE skill_id = ?
    `).get(skillId) as Skill | null;
  }

  /**
   * 记录技能使用（成功）
   */
  recordSuccess(skillId: string, executionTimeMs: number): void {
    this.db.prepare(`
      UPDATE sys_skill_bank
      SET
        success_count = success_count + 1,
        avg_execution_time_ms = CASE
          WHEN avg_execution_time_ms IS NULL THEN ?
          ELSE (avg_execution_time_ms * (success_count + failure_count) + ?) / (success_count + failure_count + 1)
        END,
        last_used_at = CURRENT_TIMESTAMP
      WHERE skill_id = ?
    `).run(executionTimeMs, executionTimeMs, skillId);
  }

  /**
   * 记录技能使用（失败）
   */
  recordFailure(skillId: string): void {
    this.db.prepare(`
      UPDATE sys_skill_bank
      SET
        failure_count = failure_count + 1,
        last_used_at = CURRENT_TIMESTAMP
      WHERE skill_id = ?
    `).run(skillId);
  }

  /**
   * 更新技能 Q 值
   */
  updateQValue(skillId: string, newQValue: number): void {
    this.db.prepare(`
      UPDATE sys_skill_bank
      SET q_value = ?
      WHERE skill_id = ?
    `).run(newQValue, skillId);
  }

  /**
   * 获取统计信息
   */
  getStats(): {
    totalSkills: number;
    avgQValue: number;
    avgSuccessRate: number;
    byType: Record<string, number>;
  } {
    const result = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(q_value) as avg_q,
        SUM(CASE WHEN success_count + failure_count > 0
          THEN CAST(success_count AS REAL) / (success_count + failure_count)
          ELSE 0.5 END) as avg_success_rate
      FROM sys_skill_bank
    `).get() as any;

    const byType = this.db.prepare(`
      SELECT skill_type, COUNT(*) as count
      FROM sys_skill_bank
      GROUP BY skill_type
    `).all() as any[];

    const typeCounts: Record<string, number> = {};
    for (const row of byType) {
      typeCounts[row.skill_type] = row.count;
    }

    return {
      totalSkills: result?.total || 0,
      avgQValue: result?.avg_q || 0,
      avgSuccessRate: result?.avg_success_rate || 0,
      byType: typeCounts
    };
  }

  /**
   * 更新配置
   */
  updateConfig(config: Partial<SkillRetrievalConfig>): void {
    this.config = { ...this.config, ...config };
  }

  close(): void {
    this.db.close();
    this.qUpdater.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const retriever = new SkillRetriever();

  const command = process.argv[2] || 'stats';
  const query = process.argv.slice(3).join(' ') || '性能优化';

  if (command === 'stats') {
    console.log('📊 Skill Retriever 统计\n');
    const stats = retriever.getStats();
    console.log(`总技能数: ${stats.totalSkills}`);
    console.log(`平均 Q 值: ${stats.avgQValue.toFixed(3)}`);
    console.log(`平均成功率: ${(stats.avgSuccessRate * 100).toFixed(1)}%`);
    console.log(`按类型: ${JSON.stringify(stats.byType)}`);
  }

  if (command === 'search' || command === 'retrieve') {
    console.log(`🔍 搜索技能: "${query}"\n`);

    const results = retriever.retrieve(query);

    if (results.length === 0) {
      console.log('❌ 无匹配技能');
    } else {
      console.log(`找到 ${results.length} 个相关技能:\n`);
      for (let i = 0; i < results.length; i++) {
        const s = results[i];
        const fusedQ = retriever['qUpdater'].getFusedQ(s.intent_hash);
        console.log(`${i + 1}. [Q=${s.q_value.toFixed(2)}→${fusedQ.toFixed(2)}] ${s.name}`);
        console.log(`   描述: ${s.description}`);
        console.log(`   匹配关键词: ${s.matched_keywords.join(', ') || '(无)'}`);
        console.log(`   分数: 关键词=${s.keyword_match_score.toFixed(2)} Q融合=${fusedQ.toFixed(2)} 综合=${s.combined_score.toFixed(3)}`);
        console.log();
      }
    }
  }

  if (command === 'get') {
    const skill = retriever.getSkillById(query);
    if (skill) {
      console.log(`📝 技能详情: ${skill.name}\n`);
      console.log(`ID: ${skill.skill_id}`);
      console.log(`类型: ${skill.skill_type}`);
      console.log(`Q 值: ${skill.q_value}`);
      console.log(`描述: ${skill.description}`);
      console.log(`\n触发关键词: ${skill.trigger_keywords}`);
      console.log(`\n提示词模板:\n${skill.llm_prompt_template?.substring(0, 200)}...`);
    } else {
      console.log(`❌ 未找到技能: ${query}`);
    }
  }

  retriever.close();
}
