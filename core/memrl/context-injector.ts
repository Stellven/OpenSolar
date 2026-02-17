/**
 * MEMRL Context Injector
 *
 * Phase 2 核心组件
 * 职责: 将检索结果注入执行上下文
 */

import { TwoPhaseRetriever, RetrievedExperience } from './two-phase-retriever';
import { IntentHashGenerator } from './intent-hash';

interface InjectedContext {
  intentHash: string;
  experiences: RetrievedExperience[];
  formattedContext: string;
  summary: string;
}

export class MEMRLContextInjector {
  private retriever: TwoPhaseRetriever;
  private hashGenerator: IntentHashGenerator;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`
  ) {
    this.retriever = new TwoPhaseRetriever(dbPath);
    this.hashGenerator = new IntentHashGenerator();
  }

  /**
   * 检索并注入上下文
   *
   * @param userInput 用户输入
   * @param intentHash 可选的预设 hash
   */
  inject(userInput: string, intentHash?: string): InjectedContext {
    // 1. 生成 intent hash
    const hash = intentHash || this.hashGenerator.generate(userInput);

    // 2. 检索相关经验
    const experiences = this.retriever.retrieve(hash);

    // 3. 格式化上下文
    const formattedContext = this.formatContext(experiences, userInput);

    // 4. 生成摘要
    const summary = this.summarize(experiences);

    return {
      intentHash: hash,
      experiences,
      formattedContext,
      summary
    };
  }

  /**
   * 从 intent hash 直接检索
   */
  injectByHash(intentHash: string): InjectedContext {
    const experiences = this.retriever.retrieve(intentHash);
    const formattedContext = this.formatContext(experiences, intentHash);
    const summary = this.summarize(experiences);

    return {
      intentHash,
      experiences,
      formattedContext,
      summary
    };
  }

  /**
   * 格式化上下文输出
   */
  private formatContext(
    experiences: RetrievedExperience[],
    context: string
  ): string {
    if (experiences.length === 0) {
      return `📚 未找到相关历史经验 (context: "${context.substring(0, 30)}...")`;
    }

    const lines: string[] = [
      `📚 相关历史经验 (Top-${experiences.length}):`,
      ''
    ];

    for (let i = 0; i < experiences.length; i++) {
      const exp = experiences[i];
      lines.push(this.formatExperience(exp, i + 1));
    }

    return lines.join('\n');
  }

  /**
   * 格式化单个 Experience
   */
  formatExperience(exp: RetrievedExperience, index?: number): string {
    const idx = index ? `${index}. ` : '• ';
    const qStr = exp.q_value.toFixed(2);
    const simStr = exp.similarity_score.toFixed(2);

    // 尝试从 evidence_json 提取摘要
    let evidenceSummary = '';
    if (exp.evidence_json) {
      try {
        const evidence = JSON.parse(exp.evidence_json);
        if (evidence.evidence && Array.isArray(evidence.evidence)) {
          evidenceSummary = evidence.evidence.slice(0, 2).join('; ');
        }
      } catch {
        // ignore
      }
    }

    const lines = [
      `${idx}[Q=${qStr}] ${exp.experience_id}`,
      `   Intent: ${exp.intent_hash.substring(0, 20)}...`,
      `   Score: Combined=${exp.combined_score.toFixed(3)} | Sim=${simStr} | Rec=${exp.recency_score.toFixed(2)}`
    ];

    if (evidenceSummary) {
      lines.push(`   Evidence: ${evidenceSummary.substring(0, 60)}...`);
    }

    return lines.join('\n');
  }

  /**
   * 生成摘要
   */
  summarize(experiences: RetrievedExperience[]): string {
    if (experiences.length === 0) {
      return '无相关经验';
    }

    const avgQ = experiences.reduce((s, e) => s + e.q_value, 0) / experiences.length;
    const highQ = experiences.filter(e => e.q_value >= 0.7).length;

    return `${experiences.length} 条经验 | 平均 Q=${avgQ.toFixed(2)} | 高 Q=${highQ}`;
  }

  /**
   * 生成用于 LLM 的简洁上下文
   */
  generateLLMContext(userInput: string): string {
    const result = this.inject(userInput);

    if (result.experiences.length === 0) {
      return '';
    }

    // 只返回高 Q 值经验的摘要
    const highQExperiences = result.experiences
      .filter(e => e.q_value >= 0.6)
      .slice(0, 3);

    if (highQExperiences.length === 0) {
      return '';
    }

    const lines = ['参考以下历史成功经验:'];
    for (const exp of highQExperiences) {
      lines.push(`- [Q=${exp.q_value.toFixed(2)}] ${exp.experience_id}`);
    }

    return lines.join('\n');
  }

  /**
   * 获取检索器统计
   */
  getStats(): ReturnType<TwoPhaseRetriever['getStats']> {
    return this.retriever.getStats();
  }

  /**
   * 更新检索器配置
   */
  updateConfig(config: Parameters<TwoPhaseRetriever['updateConfig']>[0]): void {
    this.retriever.updateConfig(config);
  }

  close(): void {
    this.retriever.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const injector = new MEMRLContextInjector();

  const command = process.argv[2] || 'inject';
  const input = process.argv.slice(3).join(' ') || '构建项目';

  if (command === 'inject') {
    console.log(`🔍 检索并注入上下文\n`);
    console.log(`输入: "${input}"\n`);

    const result = injector.inject(input);

    console.log(`Intent Hash: ${result.intentHash}`);
    console.log(`摘要: ${result.summary}`);
    console.log();
    console.log(result.formattedContext);
  }

  if (command === 'llm') {
    console.log(`🤖 生成 LLM 上下文\n`);
    const llmContext = injector.generateLLMContext(input);
    console.log(llmContext || '(无相关经验)');
  }

  if (command === 'stats') {
    console.log('📊 Context Injector 统计\n');
    const stats = injector.getStats();
    console.log(`总经验数: ${stats.totalExperiences}`);
    console.log(`唯一意图: ${stats.uniqueIntents}`);
    console.log(`平均 Q: ${stats.avgQValue.toFixed(3)}`);
    console.log(`高 Q 经验: ${stats.highQCount}`);
  }

  injector.close();
}
