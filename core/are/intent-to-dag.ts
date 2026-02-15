/**
 * Intent to DAG - 将用户意图转换为可执行的 PlanIR
 *
 * 这是 ARE 与实际执行的集成层:
 * 用户意图 → 资源匹配 → PlanIR 生成 → ARE 执行
 */

import { Database } from 'bun:sqlite';
import { PlanIR, TaskIR } from './types';
import { ARE } from './index';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

interface MatchedResource {
  type: 'script' | 'shortcut' | 'skill' | 'primitive';
  id: string;
  name: string;
  confidence: number;
}

interface IntentAnalysis {
  intent: string;
  complexity: 'simple' | 'multi_step' | 'parallel';
  resources: MatchedResource[];
  suggestedPlan?: PlanIR;
}

export class IntentToDAG {
  private db: Database;
  private are: ARE;

  constructor() {
    this.db = new Database(DB_PATH);
    this.are = new ARE();
  }

  /**
   * 分析用户意图，判断是否需要 ARE 编排
   */
  async analyze(intent: string): Promise<IntentAnalysis> {
    // 1. 提取动作关键词
    const actions = this.extractActions(intent);

    // 2. 匹配资源
    const resources = await this.matchResources(intent, actions);

    // 3. 判断复杂度
    const complexity = this.determineComplexity(intent, resources);

    // 4. 如果是多步骤，生成 PlanIR
    let suggestedPlan: PlanIR | undefined;
    if (complexity !== 'simple' && resources.length > 0) {
      suggestedPlan = this.generatePlan(intent, resources, complexity);
    }

    return { intent, complexity, resources, suggestedPlan };
  }

  /**
   * 执行意图 - 自动选择 ARE 或直接执行
   */
  async execute(intent: string): Promise<{
    mode: 'are' | 'direct';
    result: any;
  }> {
    const analysis = await this.analyze(intent);

    if (analysis.complexity === 'simple' || !analysis.suggestedPlan) {
      // 简单任务：直接执行第一个匹配的资源
      return {
        mode: 'direct',
        result: { message: '简单任务，建议直接执行', resources: analysis.resources }
      };
    }

    // 复杂任务：通过 ARE 编排执行
    this.are.setParallelMode(analysis.complexity === 'parallel');
    const result = await this.are.execute(analysis.suggestedPlan);

    return { mode: 'are', result };
  }

  /**
   * 提取动作关键词
   */
  private extractActions(intent: string): string[] {
    const actionPatterns = [
      /查询|获取|读取|抓取|fetch|get|read/gi,
      /发送|写入|创建|生成|send|write|create/gi,
      /分析|处理|转换|合并|analyze|process|transform|merge/gi,
      /保存|存储|缓存|save|store|cache/gi,
      /通知|提醒|发邮件|notify|remind|email/gi,
    ];

    const actions: string[] = [];
    for (const pattern of actionPatterns) {
      const matches = intent.match(pattern);
      if (matches) actions.push(...matches);
    }
    return [...new Set(actions)];
  }

  /**
   * 匹配可用资源
   */
  private async matchResources(intent: string, actions: string[]): Promise<MatchedResource[]> {
    const resources: MatchedResource[] = [];
    const keywords = intent.toLowerCase().split(/\s+/);

    // 1. 匹配脚本
    const scripts = this.db.query(`
      SELECT script_id, name, description, intent_keywords
      FROM sys_scripts
      WHERE status = 'active'
    `).all() as any[];

    for (const script of scripts) {
      const score = this.calculateMatchScore(keywords, script.description, script.intent_keywords);
      if (score > 0.3) {
        resources.push({
          type: 'script',
          id: script.script_id,
          name: script.name,
          confidence: score
        });
      }
    }

    // 2. 匹配 Shortcuts
    const shortcuts = this.db.query(`
      SELECT shortcut_id, category, trigger_phrases, siri_phrase
      FROM sys_shortcuts
    `).all() as any[];

    for (const shortcut of shortcuts) {
      const triggerText = shortcut.trigger_phrases || '';
      const score = this.calculateMatchScore(keywords, triggerText, shortcut.siri_phrase || '', shortcut.category || '');
      if (score > 0.3) {
        resources.push({
          type: 'shortcut',
          id: shortcut.shortcut_id,
          name: shortcut.shortcut_id,
          confidence: score
        });
      }
    }

    // 3. 匹配 Skills
    const skills = this.db.query(`
      SELECT skill_id, command, category
      FROM sys_skills
      WHERE user_invocable = 1
    `).all() as any[];

    for (const skill of skills) {
      const score = this.calculateMatchScore(keywords, skill.command, skill.category || '');
      if (score > 0.3) {
        resources.push({
          type: 'skill',
          id: skill.skill_id,
          name: skill.command,
          confidence: score
        });
      }
    }

    // 按置信度排序
    return resources.sort((a, b) => b.confidence - a.confidence);
  }

  /**
   * 计算匹配分数
   */
  private calculateMatchScore(keywords: string[], ...texts: string[]): number {
    const combined = texts.join(' ').toLowerCase();
    let matches = 0;
    for (const kw of keywords) {
      if (combined.includes(kw)) matches++;
    }
    return keywords.length > 0 ? matches / keywords.length : 0;
  }

  /**
   * 判断复杂度
   */
  private determineComplexity(intent: string, resources: MatchedResource[]): 'simple' | 'multi_step' | 'parallel' {
    // 并行关键词
    const parallelKeywords = /同时|并行|一起|parallel|concurrently/i;
    if (parallelKeywords.test(intent)) return 'parallel';

    // 多步骤关键词
    const multiStepKeywords = /然后|接着|之后|再|and then|after that|next/i;
    if (multiStepKeywords.test(intent)) return 'multi_step';

    // 多个资源也可能需要编排
    if (resources.length > 1) return 'multi_step';

    return 'simple';
  }

  /**
   * 生成 PlanIR
   */
  private generatePlan(intent: string, resources: MatchedResource[], complexity: string): PlanIR {
    const planId = `plan_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const intentHash = this.hashIntent(intent);

    const tasks: TaskIR[] = resources.slice(0, 5).map((resource, index) => ({
      task_id: `t${index + 1}`,
      name: resource.name,
      action: {
        type: resource.type === 'script' ? 'script' :
              resource.type === 'shortcut' ? 'primitive' : 'skill',
        target: resource.id,
        params: {}
      },
      depends_on: complexity === 'parallel' ? [] :
                  index === 0 ? [] : [`t${index}`],
      output: { var_name: `output_${index + 1}` }
    }));

    return {
      meta: {
        plan_id: planId,
        version: '1.0',
        created_at: new Date().toISOString(),
        intent_hash: intentHash,
        intent_text: intent
      },
      vars: {},
      tasks,
      constraints: {
        timeout_ms: 30000,
        max_parallel: complexity === 'parallel' ? 4 : 1,
        retry_policy: { max_attempts: 2, backoff_ms: 1000, backoff_multiplier: 2 },
        rollback_on_failure: false
      }
    };
  }

  private hashIntent(intent: string): string {
    const { createHash } = require('crypto');
    return createHash('sha256').update(intent).digest('hex').slice(0, 16);
  }
}

// CLI
if (import.meta.main) {
  const intent = process.argv[2] || '获取天气并发送邮件通知';
  const itd = new IntentToDAG();

  console.log(`\n🎯 意图: ${intent}\n`);

  const analysis = await itd.analyze(intent);

  console.log(`📊 复杂度: ${analysis.complexity}`);
  console.log(`🔧 匹配资源: ${analysis.resources.length} 个`);

  for (const r of analysis.resources.slice(0, 5)) {
    console.log(`   - [${r.type}] ${r.name} (${(r.confidence * 100).toFixed(0)}%)`);
  }

  if (analysis.suggestedPlan) {
    console.log(`\n📋 生成计划: ${analysis.suggestedPlan.meta.plan_id}`);
    console.log(`   任务数: ${analysis.suggestedPlan.tasks.length}`);
    console.log(`   并行度: ${analysis.suggestedPlan.constraints?.max_parallel || 1}`);

    // 执行
    const execArg = process.argv[3];
    if (execArg === '--exec') {
      console.log('\n🚀 执行中...');
      const result = await itd.execute(intent);
      console.log(`   模式: ${result.mode}`);
      console.log(`   结果:`, JSON.stringify(result.result, null, 2));
    }
  }
}

export const intentToDAG = new IntentToDAG();
