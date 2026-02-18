/**
 * MEMRL Unified Retriever - Solar 主流程集成
 *
 * P2 集成组件
 * 职责: 将 Unified Retriever 接入 Solar 主流程
 *
 * 使用场景:
 * 1. 用户输入 → 自动检索相关记忆和技能
 * 2. 为 LLM 提供上下文增强
 * 3. 记忆+技能的统一 RAG
 */

import { Database } from 'bun:sqlite';
import { UnifiedRetriever, UnifiedRetrievalResult } from './unified-retriever';

// 集成配置
interface IntegrationConfig {
  autoRetrieve: boolean;        // 自动检索
  minScore: number;             // 最低分数阈值
  maxResults: number;           // 最大结果数
  includeMemory: boolean;       // 包含记忆
  includeSkill: boolean;        // 包含技能
  logRetrieval: boolean;        // 记录检索日志
}

const DEFAULT_CONFIG: IntegrationConfig = {
  autoRetrieve: true,
  minScore: 0.2,
  maxResults: 5,
  includeMemory: true,
  includeSkill: true,
  logRetrieval: true
};

/**
 * Solar 主流程集成器
 *
 * 在每个用户输入后自动:
 * 1. 检索相关记忆和技能
 * 2. 格式化为可注入的上下文
 * 3. 记录检索历史
 */
export class UnifiedRetrieverIntegration {
  private retriever: UnifiedRetriever;
  private db: Database;
  private config: IntegrationConfig;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    config: Partial<IntegrationConfig> = {}
  ) {
    this.db = new Database(dbPath);
    this.retriever = new UnifiedRetriever(dbPath);
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 主入口: 处理用户输入
   *
   * @param userInput 用户输入
   * @param sessionId 会话 ID
   * @returns 检索结果 + 格式化上下文
   */
  process(
    userInput: string,
    sessionId: string
  ): {
    result: UnifiedRetrievalResult;
    contextBlock: string;
    hasRelevantContext: boolean;
  } {
    // 1. 生成 Intent Hash
    const intentHash = this.generateIntentHash(userInput);

    // 2. 检索
    const result = this.retriever.retrieve(userInput, intentHash);

    // 3. 过滤低分结果
    const filteredAll = result.all.filter(item => {
      if ('skill_id' in item) {
        return (item as any).combined_score >= this.config.minScore;
      }
      return (item as any).combined_score >= this.config.minScore;
    });

    // 4. 格式化上下文块
    const contextBlock = this.formatContextBlock(filteredAll.slice(0, this.config.maxResults));

    // 5. 记录检索日志
    if (this.config.logRetrieval) {
      this.logRetrieval(sessionId, userInput, intentHash, result);
    }

    return {
      result,
      contextBlock,
      hasRelevantContext: filteredAll.length > 0
    };
  }

  /**
   * 格式化为可注入的上下文块
   *
   * 用于在 LLM Prompt 中注入
   */
  private formatContextBlock(items: any[]): string {
    if (items.length === 0) {
      return '';
    }

    const lines: string[] = [
      '---',
      '## 📚 相关上下文 (自动检索)',
      ''
    ];

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const isSkill = 'skill_id' in item;

      if (isSkill) {
        const skill = item;
        lines.push(`### ${i + 1}. [技能] ${skill.name}`);
        lines.push(`Q值: ${skill.q_value.toFixed(2)} | 匹配分数: ${skill.combined_score.toFixed(3)}`);
        lines.push(`描述: ${skill.description}`);
        if (skill.matched_keywords?.length > 0) {
          lines.push(`匹配关键词: ${skill.matched_keywords.join(', ')}`);
        }
      } else {
        const mem = item;
        lines.push(`### ${i + 1}. [记忆] ${mem.experience_id?.slice(0, 20)}...`);
        lines.push(`Q值: ${mem.q_value?.toFixed(2)} | 匹配分数: ${mem.combined_score?.toFixed(3)}`);
      }
      lines.push('');
    }

    lines.push('---');
    lines.push('');

    return lines.join('\n');
  }

  /**
   * 生成 Intent Hash
   */
  private generateIntentHash(input: string): string {
    let hash = 0;
    const content = input.toLowerCase();
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return `intent_${Math.abs(hash).toString(16).padStart(8, '0')}`;
  }

  /**
   * 记录检索日志
   */
  private logRetrieval(
    sessionId: string,
    query: string,
    intentHash: string,
    result: UnifiedRetrievalResult
  ): void {
    try {
      this.db.run(`
        INSERT INTO memrl_retrieval_log
        (session_id, query, intent_hash, memory_count, skill_count, total_count, retrieval_time_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `, [
        sessionId,
        query.slice(0, 200),
        intentHash,
        result.memories.length,
        result.skills.length,
        result.all.length,
        result.retrievalTimeMs
      ]);
    } catch (e) {
      // 表可能不存在，忽略
    }
  }

  /**
   * 获取检索统计
   */
  getStats(): {
    retriever: ReturnType<UnifiedRetriever['getStats']>;
    recentQueries: { query: string; memoryCount: number; skillCount: number }[];
  } {
    const retrieverStats = this.retriever.getStats();

    // 获取最近查询
    let recentQueries: any[] = [];
    try {
      recentQueries = this.db.query(`
        SELECT query, memory_count, skill_count, created_at
        FROM memrl_retrieval_log
        ORDER BY created_at DESC
        LIMIT 10
      `).all() as any[];
    } catch (e) {
      // 表不存在
    }

    return {
      retriever: retrieverStats,
      recentQueries
    };
  }

  /**
   * 快速检查是否有相关技能
   */
  hasRelevantSkill(userInput: string): { has: boolean; topSkill?: string; score?: number } {
    const skills = this.retriever['skillRetriever'].retrieve(userInput);

    if (skills.length === 0) {
      return { has: false };
    }

    const top = skills[0];
    return {
      has: top.combined_score >= this.config.minScore,
      topSkill: top.name,
      score: top.combined_score
    };
  }

  /**
   * 创建检索日志表
   */
  initLogTable(): void {
    this.db.run(`
      CREATE TABLE IF NOT EXISTS memrl_retrieval_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        query TEXT,
        intent_hash TEXT,
        memory_count INTEGER,
        skill_count INTEGER,
        total_count INTEGER,
        retrieval_time_ms INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  close(): void {
    this.retriever.close();
    this.db.close();
  }
}

// 便捷函数: 快速检索
export function quickRetrieve(
  userInput: string,
  sessionId: string = 'default'
): { contextBlock: string; hasRelevantContext: boolean } {
  const integration = new UnifiedRetrieverIntegration();
  const result = integration.process(userInput, sessionId);
  integration.close();
  return {
    contextBlock: result.contextBlock,
    hasRelevantContext: result.hasRelevantContext
  };
}

// CLI 入口
if (import.meta.main) {
  const integration = new UnifiedRetrieverIntegration();
  integration.initLogTable();

  const command = process.argv[2] || 'stats';
  const query = process.argv.slice(3).join(' ') || '性能优化';

  if (command === 'stats') {
    console.log('📊 Unified Retriever 集成统计\n');
    const stats = integration.getStats();

    console.log('Memory Retriever:');
    console.log(`  总经验: ${stats.retriever.memories.totalExperiences}`);
    console.log(`  平均 Q: ${stats.retriever.memories.avgQValue.toFixed(3)}`);

    console.log('\nSkill Retriever:');
    console.log(`  总技能: ${stats.retriever.skills.totalSkills}`);
    console.log(`  平均 Q: ${stats.retriever.skills.avgQValue.toFixed(3)}`);

    if (stats.recentQueries.length > 0) {
      console.log('\n最近查询:');
      for (const q of stats.recentQueries.slice(0, 5)) {
        console.log(`  "${q.query.slice(0, 30)}..." - 记忆:${q.memory_count} 技能:${q.skill_count}`);
      }
    }
  }

  if (command === 'retrieve' || command === 'search') {
    console.log(`🔍 检索: "${query}"\n`);
    const result = integration.process(query, 'cli_test');

    console.log(`找到 ${result.result.all.length} 个相关项`);
    console.log(`有相关上下文: ${result.hasRelevantContext ? '是' : '否'}`);
    console.log(`\n${result.contextBlock}`);
  }

  if (command === 'context') {
    console.log(`📝 生成上下文块: "${query}"\n`);
    const result = integration.process(query, 'cli_test');
    console.log(result.contextBlock);
  }

  if (command === 'check') {
    const check = integration.hasRelevantSkill(query);
    console.log(`有相关技能: ${check.has}`);
    if (check.topSkill) {
      console.log(`最佳匹配: ${check.topSkill} (分数: ${check.score?.toFixed(3)})`);
    }
  }

  integration.close();
}
