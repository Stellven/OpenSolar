/**
 * MEMRL Integration Orchestrator
 *
 * Phase 2 核心组件
 * 职责: 协调 Intent Engine + Retriever + Injector
 *
 * 完整流程:
 * 用户输入 → Intent Hash → Two-Phase Retrieve → Context Inject → Execute
 */

import { IntentHashGenerator } from './intent-hash';
import { MEMRLContextInjector } from './context-injector';
import { TwoPhaseRetriever, RetrievedExperience } from './two-phase-retriever';
import { QUpdater } from './q-updater';
import { UtilityCollector } from './utility-collector';
import { Database } from 'bun:sqlite';

interface IntegrationResult {
  // 意图解析
  userInput: string;
  intentHash: string;
  keywords: string[];

  // 检索结果
  retrievedExperiences: RetrievedExperience[];
  retrievalSummary: string;

  // 上下文注入
  formattedContext: string;
  llmContext: string;

  // 元信息
  processingTimeMs: number;
  sessionId: string;
}

interface ExecutionFeedback {
  intentHash: string;
  experienceId: string;
  success: boolean;
  userFeedback?: string;
}

export class MEMRLIntegrationOrchestrator {
  private db: Database;
  private hashGenerator: IntentHashGenerator;
  private injector: MEMRLContextInjector;
  private retriever: TwoPhaseRetriever;
  private updater: QUpdater;
  private collector: UtilityCollector;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`
  ) {
    this.db = new Database(dbPath);
    this.hashGenerator = new IntentHashGenerator();
    this.injector = new MEMRLContextInjector(dbPath);
    this.retriever = new TwoPhaseRetriever(dbPath);
    this.updater = new QUpdater(dbPath);
    this.collector = new UtilityCollector(dbPath);
  }

  /**
   * 完整集成流程
   *
   * @param userInput 用户输入
   * @param sessionId 会话 ID
   */
  process(userInput: string, sessionId?: string): IntegrationResult {
    const startTime = Date.now();
    const sid = sessionId || `session_${Date.now()}`;

    // 1. 解析意图
    const intentHash = this.hashGenerator.generate(userInput);
    const keywords = this.hashGenerator.extractKeywords(userInput);

    // 2. 检索相关经验
    const retrievedExperiences = this.retriever.retrieve(intentHash);
    const retrievalSummary = this.injector.summarize(retrievedExperiences);

    // 3. 生成上下文
    const formattedContext = this.injector.formatContext(retrievedExperiences, userInput);
    const llmContext = this.generateLLMContext(retrievedExperiences);

    // 4. 记录检索日志
    this.logRetrieval(userInput, intentHash, retrievedExperiences, sid);

    const processingTimeMs = Date.now() - startTime;

    return {
      userInput,
      intentHash,
      keywords,
      retrievedExperiences,
      retrievalSummary,
      formattedContext,
      llmContext,
      processingTimeMs,
      sessionId: sid
    };
  }

  /**
   * 执行后反馈
   *
   * 在任务执行完成后调用，更新 Q 值
   */
  feedback(feedback: ExecutionFeedback): number {
    const reward = feedback.success ? 1 : 0;
    const qValue = this.updater.update(
      feedback.intentHash,
      feedback.experienceId,
      reward
    );

    // 记录反馈
    this.logFeedback(feedback, qValue);

    return qValue;
  }

  /**
   * 生成 LLM 上下文
   */
  private generateLLMContext(experiences: RetrievedExperience[]): string {
    if (experiences.length === 0) {
      return '';
    }

    // 只使用高 Q 值经验
    const highQ = experiences
      .filter(e => e.q_value >= 0.6)
      .slice(0, 3);

    if (highQ.length === 0) {
      return '';
    }

    const lines = ['\n📚 参考历史成功经验:'];
    for (const exp of highQ) {
      lines.push(`- [Q=${exp.q_value.toFixed(2)}] ${exp.experience_id}`);
    }
    lines.push('');

    return lines.join('\n');
  }

  /**
   * 记录检索日志
   */
  private logRetrieval(
    userInput: string,
    intentHash: string,
    experiences: RetrievedExperience[],
    sessionId: string
  ): void {
    this.db.prepare(`
      INSERT INTO memrl_retrieval_logs
      (user_input, intent_hash, experience_count, top_q_value, session_id, created_at)
      VALUES (?, ?, ?, ?, ?, datetime('now'))
    `).run(
      userInput.substring(0, 200),
      intentHash,
      experiences.length,
      experiences.length > 0 ? experiences[0].q_value : 0,
      sessionId
    );
  }

  /**
   * 记录反馈日志
   */
  private logFeedback(feedback: ExecutionFeedback, qValue: number): void {
    this.db.prepare(`
      INSERT INTO memrl_feedback_logs
      (intent_hash, experience_id, success, user_feedback, new_q_value, created_at)
      VALUES (?, ?, ?, ?, ?, datetime('now'))
    `).run(
      feedback.intentHash,
      feedback.experienceId,
      feedback.success ? 1 : 0,
      feedback.userFeedback || '',
      qValue
    );
  }

  /**
   * 获取集成统计
   */
  getStats(): {
    retrievals: { total: number; avgExperiences: number; avgTopQ: number };
    feedbacks: { total: number; successRate: number };
    storage: ReturnType<TwoPhaseRetriever['getStats']>;
  } {
    const retrievalStats = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(experience_count) as avg_exp,
        AVG(top_q_value) as avg_q
      FROM memrl_retrieval_logs
    `).get() as any;

    const feedbackStats = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(success) as success_rate
      FROM memrl_feedback_logs
    `).get() as any;

    return {
      retrievals: {
        total: retrievalStats?.total || 0,
        avgExperiences: retrievalStats?.avg_exp || 0,
        avgTopQ: retrievalStats?.avg_q || 0
      },
      feedbacks: {
        total: feedbackStats?.total || 0,
        successRate: feedbackStats?.success_rate || 0
      },
      storage: this.retriever.getStats()
    };
  }

  /**
   * 获取推荐的 Experience IDs
   */
  getRecommendedExperiences(userInput: string): string[] {
    const result = this.process(userInput);
    return result.retrievedExperiences.map(e => e.experience_id);
  }

  close(): void {
    this.db.close();
    this.injector.close();
    this.retriever.close();
    this.updater.close();
    this.collector.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const orchestrator = new MEMRLIntegrationOrchestrator();

  const command = process.argv[2] || 'process';
  const input = process.argv.slice(3).join(' ') || '构建项目';

  if (command === 'process') {
    console.log('🔄 完整集成流程测试\n');
    console.log(`输入: "${input}"\n`);

    const result = orchestrator.process(input);

    console.log('═══════════════════════════════════════════════════════════════');
    console.log(`Intent Hash: ${result.intentHash}`);
    console.log(`关键词: ${result.keywords.join(', ')}`);
    console.log(`检索摘要: ${result.retrievalSummary}`);
    console.log(`处理时间: ${result.processingTimeMs}ms`);
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log(result.formattedContext);

    if (result.llmContext) {
      console.log();
      console.log('🤖 LLM 上下文:');
      console.log(result.llmContext);
    }
  }

  if (command === 'stats') {
    console.log('📊 集成统计\n');
    const stats = orchestrator.getStats();

    console.log('检索统计:');
    console.log(`  总检索: ${stats.retrievals.total}`);
    console.log(`  平均经验数: ${stats.retrievals.avgExperiences.toFixed(1)}`);
    console.log(`  平均 Top Q: ${stats.retrievals.avgTopQ.toFixed(3)}`);

    console.log('\n反馈统计:');
    console.log(`  总反馈: ${stats.feedbacks.total}`);
    console.log(`  成功率: ${(stats.feedbacks.successRate * 100).toFixed(1)}%`);

    console.log('\n存储统计:');
    console.log(`  总经验: ${stats.storage.totalExperiences}`);
    console.log(`  平均 Q: ${stats.storage.avgQValue.toFixed(3)}`);
  }

  if (command === 'recommend') {
    const ids = orchestrator.getRecommendedExperiences(input);
    console.log(`推荐 Experience IDs: ${ids.join(', ')}`);
  }

  orchestrator.close();
}
