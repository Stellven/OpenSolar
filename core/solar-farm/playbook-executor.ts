/**
 * Skill-RAG: Playbook Executor
 *
 * 完整的 Skill-RAG 运行时管道：
 *   1. matchPlaybooks()     — 意图匹配 (playbook-matcher)
 *   2. extractParams()      — 参数提取 (param-extractor)
 *   3. buildBrainRouterCall() — 构建调用参数 (call-niuma)
 *   4. updateQValue()       — 反馈更新 q_value
 *
 * 注意: 实际的 brain-router MCP 调用由 Solar 主脑发起，
 * 本模块只负责准备参数和后处理反馈。
 *
 * Part of Step 2: Skill-RAG Plan A
 * @version 1.0.0
 * @created 2026-02-24
 */

import Database from 'bun:sqlite';
import { homedir } from 'os';
import { join } from 'path';
import { matchPlaybooks, type PlaybookMatch, type MatchResult } from './playbook-matcher';
import { extractParams, type FilledTemplate } from './param-extractor';
import { buildNiumaCall } from './call-niuma';

const DB_PATH = join(homedir(), '.solar', 'solar.db');

// ============================================================
// 类型定义
// ============================================================

export interface ExecutionResult {
  // Match phase
  matchResult: MatchResult;
  selectedPlaybook: PlaybookMatch | null;

  // Extract phase
  filledTemplate: FilledTemplate | null;

  // Execution params
  model: string;
  callParams: { model: string; system: string; prompt: string } | null;

  // Status
  fallbackMode: boolean;       // true if no playbook matched
  elapsed_ms: number;
}

// ============================================================
// 模型选择 (方案B: 数据驱动 + Fallback)
// ============================================================

/**
 * 推断 playbook 的 task_type
 * 用于查询 model_task_performance
 *
 * 与 brain-router feature_extractor.py 的 TASK_TYPE_PATTERNS 对齐
 */
function inferTaskType(playbook: PlaybookMatch): string {
  const keywords = playbook.trigger_keywords.join(' ').toLowerCase();
  const name = playbook.name.toLowerCase();
  const desc = playbook.description.toLowerCase();
  const combined = `${keywords} ${name} ${desc}`;

  // 映射规则 (优先级从高到低，与 sroe_requests 的 task_type 对齐)

  // Architecture - 架构设计 (高权重)
  if (/架构|设计模式|重构|refactor|架构师|architect|design|schema|api.?design/.test(combined)) return 'architecture';

  // Optimization - 性能优化 (单独分类，区别于 analysis)
  if (/优化|性能|optim|performance|加速|speed|效率|efficiency|simd|向量化/.test(combined)) return 'optimization';

  // Math - 数学/计算
  if (/数学|计算|公式|math|calculate|算法|algorithm|证明|proof/.test(combined)) return 'math';

  // Review/审查 → analysis (需要深度分析)
  if (/review|审查|检查|code.?review|评审/.test(combined)) return 'analysis';

  // Debug/调试 → analysis (需要推理)
  if (/debug|调试|error|错误|排查|diagnos|bug|失败|报错/.test(combined)) return 'analysis';

  // Research/洞察 → analysis
  if (/分析|analy|洞察|研究|research|调研|探索|investigat/.test(combined)) return 'analysis';

  // Testing - 测试
  if (/测试|test|验证|verify|benchmark|基准|e2e|unit.?test/.test(combined)) return 'testing';

  // DevOps - 部署/运维
  if (/部署|deploy|构建|build|运维|ops|docker|k8s|ci|cd|pipeline/.test(combined)) return 'devops';

  // Documentation - 文档
  if (/文档|注释|doc|comment|说明|readme|文章|report/.test(combined)) return 'documentation';

  // Coding - 代码实现
  if (/代码|code|编程|实现|coding|开发|implement|function|class/.test(combined)) return 'coding';

  // Chinese - 中文写作
  if (/中文|写作|writing|文章|翻译|translate/.test(combined)) return 'chinese';

  // Reasoning - 推理
  if (/推理|reasoning|逻辑|思考|logic/.test(combined)) return 'reasoning';

  // Simple - 简单任务
  if (/简单|快速|simple|quick|小|minor|一行|改名|rename/.test(combined)) return 'simple';

  // Default
  return 'general';
}

/**
 * 从 model_task_performance 查询最佳模型
 * 返回 null 表示没有足够数据
 */
function getBestModelFromPerformance(taskType: string, minSamples: number = 3): string | null {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    const row = db.query(`
      SELECT model_id
      FROM model_task_performance
      WHERE task_type = ? AND sample_count >= ?
      ORDER BY avg_quality DESC, sample_count DESC
      LIMIT 1
    `).get(taskType, minSamples) as { model_id: string } | undefined;

    return row?.model_id ?? null;
  } finally {
    db.close();
  }
}

/**
 * 获取某任务类型的所有可用模型（用于探索）
 */
function getAvailableModelsForTask(taskType: string): string[] {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    const rows = db.query(`
      SELECT DISTINCT model_id
      FROM model_task_performance
      WHERE task_type = ?
      ORDER BY sample_count DESC
      LIMIT 5
    `).all(taskType) as { model_id: string }[];
    return rows.map(r => r.model_id);
  } finally {
    db.close();
  }
}

/**
 * Epsilon-Greedy 探索策略
 *
 * @param bestModel 当前最佳模型
 * @param taskType 任务类型
 * @param epsilon 探索概率 (0-1)，默认 0.1
 * @returns 最终选择的模型
 */
function epsilonGreedyExplore(
  bestModel: string,
  taskType: string,
  epsilon: number = 0.1
): string {
  // 随机数 > epsilon 时，使用最佳模型（开发）
  if (Math.random() > epsilon) {
    return bestModel;
  }

  // 探索：从该任务类型的可用模型中随机选择
  const availableModels = getAvailableModelsForTask(taskType);

  // 如果没有其他可用模型，返回最佳模型
  if (availableModels.length <= 1) {
    return bestModel;
  }

  // 过滤掉最佳模型，从其他模型中随机选择
  const otherModels = availableModels.filter(m => m !== bestModel);
  if (otherModels.length === 0) {
    return bestModel;
  }

  const randomIndex = Math.floor(Math.random() * otherModels.length);
  return otherModels[randomIndex];
}

/**
 * 获取当前探索率（可配置，支持动态调整）
 * 后期可以根据数据量自动降低探索率
 */
function getExplorationRate(taskType: string): number {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    // 查询该任务类型的总样本数
    const row = db.query(`
      SELECT SUM(sample_count) as total_samples
      FROM model_task_performance
      WHERE task_type = ?
    `).get(taskType) as { total_samples: number | null };

    const totalSamples = row?.total_samples || 0;

    // 动态调整：数据越多，探索率越低
    // 0-50 样本: 20% 探索
    // 50-200 样本: 10% 探索
    // 200+ 样本: 5% 探索
    if (totalSamples < 50) return 0.20;
    if (totalSamples < 200) return 0.10;
    return 0.05;
  } finally {
    db.close();
  }
}

/**
 * Select best model based on playbook task type
 *
 * 方案B: 数据驱动 + 硬编码 Fallback
 * 1. 先从 model_task_performance 查询历史最佳模型
 * 2. 如果没有足够数据，fallback 到硬编码规则
 *
 * Uses regex on combined text (keywords + name + desc) for task type inference.
 * This is the canonical selectModel — auto-dispatcher imports this.
 */
export function selectModel(playbook: PlaybookMatch): string {
  const keywords = playbook.trigger_keywords.join(' ').toLowerCase();
  const name = playbook.name.toLowerCase();
  const desc = playbook.description.toLowerCase();
  const combined = `${keywords} ${name} ${desc}`;

  // Step 1: 推断 task_type
  const taskType = inferTaskType(playbook);

  // Step 2: 尝试从历史表现中选择 (minSamples=3 确保统计显著性)
  const dataDrivenModel = getBestModelFromPerformance(taskType, 3);
  if (dataDrivenModel) {
    // Step 2a: 应用 Epsilon-Greedy 探索策略
    const epsilon = getExplorationRate(taskType);
    const finalModel = epsilonGreedyExplore(dataDrivenModel, taskType, epsilon);

    // 如果探索选择了不同模型，记录日志（可选）
    if (finalModel !== dataDrivenModel) {
      console.log(`🔍 [MemRL] 探索: ${taskType} -> ${finalModel} (最佳: ${dataDrivenModel}, ε=${epsilon})`);
    }

    return finalModel;
  }

  // Step 3: Fallback 到硬编码规则 (无足够数据时)
  // Architecture → 探索派 (creative exploration)
  if (/架构|设计模式|重构|refactor|architect|design|schema|api.?design/.test(combined)) return 'gemini-3-pro-preview';
  // Math → 审判官 (deep reasoning)
  if (/数学|计算|公式|math|calculate|算法|algorithm|证明|proof/.test(combined)) return 'deepseek-r1';
  // Review/code review → 稳健派 (high rigor)
  if (/review|审查|code.?review|检查|评审/.test(combined)) return 'gemini-2.5-pro';
  // Debug/error → 审判官 (deep reasoning)
  if (/debug|调试|error|错误|排查|diagnos|bug|失败|报错/.test(combined)) return 'deepseek-r1';
  // Performance/optimization → 创想家 (creative solutions)
  if (/perf|性能|optim|优化|加速|simd|向量化/.test(combined)) return 'deepseek-v3';
  // Testing → 稳健派 (quality focus)
  if (/测试|test|验证|verify|benchmark|基准|e2e|unit.?test/.test(combined)) return 'gemini-2.5-pro';
  // DevOps → 建设者 (routine tasks)
  if (/部署|deploy|构建|build|运维|ops|docker|k8s|ci|cd|pipeline/.test(combined)) return 'glm-5';
  // Documentation → 综合官 (clear communication)
  if (/文档|注释|doc|comment|说明|readme|report/.test(combined)) return 'gpt-4o';
  // Git/commit → 建设者
  if (/git|commit|提交/.test(combined)) return 'glm-5';
  // Creative/brainstorm → 创想家
  if (/创意|creative|brainstorm/.test(combined)) return 'deepseek-v3';
  // Research/insight → 探索派
  if (/研究|洞察|insight|research|调研|探索/.test(combined)) return 'gemini-3-pro-preview';
  // Analysis (general) → 稳健派 (after more specific matches)
  if (/分析|analy/.test(combined)) return 'gemini-2.5-pro';
  // Chinese writing → 智囊 (Chinese native)
  if (/中文|写作|文章|翻译/.test(combined)) return 'glm-5';
  // Simple tasks → 小快手 (fast, cheap)
  if (/简单|快速|simple|quick|小|minor|一行|改名/.test(combined)) return 'glm-4-flash';

  // Default → 建设者 (reliable, cost-effective)
  return 'glm-5';
}

// ============================================================
// Q-Value 更新
// ============================================================

/**
 * Update q_value after execution using simple Q-learning
 *
 * q_new = q_old + alpha * (reward - q_old)
 * alpha = 0.1 default (learning rate), can be overridden for decaying schedules
 *
 * success can be:
 *   - boolean: true → reward=1.0, false → reward=0.0
 *   - number [0-1]: continuous reward (e.g. 0.8 = good but not perfect)
 *     reward >= 0.5 counts as success for success_count/failure_count tracking
 */
export function updateQValue(skillId: string, success: boolean | number, alpha?: number): { oldQ: number; newQ: number; reward: number } | null {
  const db = new Database(DB_PATH);
  try {
    const effectiveAlpha = alpha ?? 0.1;
    const reward = typeof success === 'number'
      ? Math.max(0, Math.min(1, success))  // clamp to [0, 1]
      : (success ? 1.0 : 0.0);
    const isSuccess = reward >= 0.5;

    const row = db.query('SELECT q_value, success_count, failure_count FROM sys_skill_bank WHERE skill_id = ?')
      .get(skillId) as any;

    if (!row) return null;

    const oldQ = row.q_value;
    const newQ = parseFloat((oldQ + effectiveAlpha * (reward - oldQ)).toFixed(4));

    if (isSuccess) {
      db.query(`
        UPDATE sys_skill_bank
        SET q_value = ?, success_count = success_count + 1,
            last_used_at = datetime('now'), updated_at = datetime('now')
        WHERE skill_id = ?
      `).run(newQ, skillId);
    } else {
      db.query(`
        UPDATE sys_skill_bank
        SET q_value = ?, failure_count = failure_count + 1,
            last_used_at = datetime('now'), updated_at = datetime('now')
        WHERE skill_id = ?
      `).run(newQ, skillId);
    }

    return { oldQ, newQ, reward };
  } finally {
    db.close();
  }
}

// ============================================================
// 反馈闭环 (Step 3: MemRL)
// ============================================================

export interface FeedbackResult {
  qUpdate: { oldQ: number; newQ: number } | null;
  sroe_recorded: boolean;
  skill_id: string | null;
}

/**
 * Record execution feedback: update q_value + write to sroe_requests
 *
 * Call this AFTER brain-router execution completes.
 * Closes the Q-learning loop: execute → observe → update.
 */
export function recordFeedback(
  execution: ExecutionResult,
  success: boolean,
  meta?: {
    sessionId?: string;
    responseTokens?: number;
    latencyMs?: number;
    costUsd?: number;
    finishReason?: string;
    errorType?: string;
  }
): FeedbackResult {
  const skillId = execution.selectedPlaybook?.skill_id || null;
  let qUpdate: { oldQ: number; newQ: number } | null = null;
  let sroe_recorded = false;

  // Phase 1: Update q_value in skill_bank
  if (skillId) {
    qUpdate = updateQValue(skillId, success);
  }

  // Phase 2: Record to sroe_requests for routing intelligence
  const db = new Database(DB_PATH);
  try {
    const contextTags = execution.selectedPlaybook
      ? JSON.stringify(execution.selectedPlaybook.trigger_keywords.slice(0, 5))
      : null;

    db.query(`
      INSERT INTO sroe_requests (
        session_id, timestamp, task_type, task_complexity,
        selected_model, routing_reason, routing_confidence,
        response_tokens, latency_ms, cost_usd,
        finish_reason, error_type,
        skill_id, context_tags
      ) VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      meta?.sessionId || `srag-${Date.now()}`,
      // 使用 inferTaskType 推断真正的任务类型，而不是硬编码 'skill_rag'
      execution.selectedPlaybook ? inferTaskType(execution.selectedPlaybook) : 'general',
      execution.selectedPlaybook?.match_score || 0,
      execution.model,
      execution.fallbackMode
        ? 'fallback:no_match'
        : `skill-rag:${execution.selectedPlaybook?.name}`,
      execution.selectedPlaybook?.match_score || 0,
      meta?.responseTokens || null,
      meta?.latencyMs || execution.elapsed_ms,
      meta?.costUsd || null,
      meta?.finishReason || (success ? 'stop' : 'error'),
      meta?.errorType || null,
      skillId,
      contextTags
    );
    sroe_recorded = true;
  } catch (e) {
    // Non-fatal: sroe_requests recording failure shouldn't break the pipeline
  } finally {
    db.close();
  }

  return { qUpdate, sroe_recorded, skill_id: skillId };
}

/**
 * Get Q-learning statistics for observability
 */
export function getQLearningStats(): {
  total: number;
  used: number;
  avgQ: number;
  topImprovers: any[];
  recentFeedback: any[];
} {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    const total = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE length(llm_prompt_template) > 0').get() as any).c;
    const used = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE success_count > 0 OR failure_count > 0').get() as any).c;
    const avgQ = (db.query('SELECT AVG(q_value) as avg FROM sys_skill_bank WHERE length(llm_prompt_template) > 0').get() as any).avg || 0;

    const topImprovers = db.query(`
      SELECT skill_id, name, q_value, success_count, failure_count,
             (success_count + failure_count) as total_uses
      FROM sys_skill_bank
      WHERE (success_count + failure_count) > 0
      ORDER BY q_value DESC LIMIT 5
    `).all();

    const recentFeedback = db.query(`
      SELECT skill_id, selected_model, routing_reason, finish_reason, latency_ms,
             timestamp
      FROM sroe_requests
      WHERE skill_id IS NOT NULL
      ORDER BY timestamp DESC LIMIT 10
    `).all();

    return { total, used, avgQ, topImprovers, recentFeedback };
  } finally {
    db.close();
  }
}

// ============================================================
// 核心管道
// ============================================================

/**
 * Full Skill-RAG pipeline: match → extract → build call params
 *
 * Does NOT execute the brain-router call — that's Solar's job.
 * Returns everything needed for Solar to make the MCP call.
 */
export function prepareExecution(
  userIntent: string,
  userMessage: string,
  additionalContext?: string,
  modelOverride?: string
): ExecutionResult {
  const start = Date.now();

  // Phase 1: Match
  const matchResult = matchPlaybooks(userIntent);

  if (matchResult.matches.length === 0) {
    return {
      matchResult,
      selectedPlaybook: null,
      filledTemplate: null,
      model: modelOverride || 'glm-5',
      callParams: null,
      fallbackMode: true,
      elapsed_ms: Date.now() - start
    };
  }

  // Phase 2: Select best playbook
  const selectedPlaybook = matchResult.matches[0];

  // Phase 3: Extract params and fill template
  const filledTemplate = extractParams(
    selectedPlaybook.llm_prompt_template,
    userMessage,
    additionalContext
  );

  // Phase 4: Select model and build call params
  const model = modelOverride || selectModel(selectedPlaybook);

  const niumaResult = buildNiumaCall({
    model,
    task: filledTemplate.filled,
    context: `[Skill-RAG] playbook=${selectedPlaybook.name} q=${selectedPlaybook.q_value}`,
  });

  const callParams = {
    model: niumaResult.model,
    system: niumaResult.system,
    prompt: niumaResult.prompt
  };

  return {
    matchResult,
    selectedPlaybook,
    filledTemplate,
    model,
    callParams,
    fallbackMode: false,
    elapsed_ms: Date.now() - start
  };
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '--help') {
    console.log(`
Skill-RAG: Playbook Executor v1.0

用法:
  bun playbook-executor.ts match <intent>              # 只匹配，不执行
  bun playbook-executor.ts prepare <intent> <message>  # 匹配+填参，输出调用参数
  bun playbook-executor.ts execute <intent> <message> <0|1>  # 完整闭环: 匹配+反馈
  bun playbook-executor.ts feedback <skill_id> <0|1>   # 手动反馈 q_value
  bun playbook-executor.ts pipeline <intent> <message>  # JSON 输出 (供程序调用)
  bun playbook-executor.ts stats                        # skill_bank 统计
  bun playbook-executor.ts qstats                       # Q-learning 闭环可观测

示例:
  bun playbook-executor.ts match "代码需要review"
  bun playbook-executor.ts prepare "性能太慢了" "我的API接口响应时间从100ms涨到了2s"
  bun playbook-executor.ts execute "性能太慢" "API响应2秒" 1
  bun playbook-executor.ts feedback skill_perf_debug_001 1
  bun playbook-executor.ts qstats
`);
    process.exit(0);
  }

  // ---- match ----
  if (command === 'match') {
    const intent = args.slice(1).join(' ');
    if (!intent) { console.error('需要 <intent> 参数'); process.exit(1); }

    const result = matchPlaybooks(intent);
    console.log(`\n🔍 匹配结果: "${intent}"`);
    console.log(`   候选: ${result.total_candidates} | 命中: ${result.matches.length} | ${result.elapsed_ms}ms\n`);
    for (const m of result.matches) {
      console.log(`   ${m.match_method === 'keyword' ? '🎯' : '🔎'} [${m.match_score.toFixed(2)}] ${m.name}`);
      console.log(`      q=${m.q_value} 参数=${m.parameters.map(p => `{{${p}}}`).join(',') || '无'}`);
    }
    if (result.matches.length === 0) console.log('   ❌ 无匹配');
    console.log();
  }

  // ---- prepare ----
  else if (command === 'prepare') {
    const intent = args[1];
    const message = args.slice(2).join(' ');
    if (!intent || !message) {
      console.error('需要 <intent> 和 <message> 参数');
      process.exit(1);
    }

    const result = prepareExecution(intent, message);

    if (result.fallbackMode) {
      console.log('\n❌ 无匹配 playbook，走通用流程\n');
    } else {
      console.log('\n✅ Skill-RAG 准备就绪:\n');
      console.log(`  Playbook: ${result.selectedPlaybook?.name} (${result.selectedPlaybook?.skill_id})`);
      console.log(`  匹配分: ${result.selectedPlaybook?.match_score.toFixed(2)}`);
      console.log(`  模型: ${result.model}`);
      console.log(`  参数填充率: ${((result.filledTemplate?.confidence || 0) * 100).toFixed(0)}%`);
      console.log(`  未填充: ${result.filledTemplate?.unfilled.join(', ') || '无'}`);
      console.log(`  耗时: ${result.elapsed_ms}ms`);

      if (result.callParams) {
        console.log('\n  📤 brain-router 调用参数:');
        console.log(`  model: "${result.callParams.model}"`);
        console.log(`  system (前120字): "${result.callParams.system.substring(0, 120)}..."`);
        console.log(`  prompt (前120字): "${result.callParams.prompt.substring(0, 120)}..."`);
      }
      console.log();
    }
  }

  // ---- feedback ----
  else if (command === 'feedback') {
    const skillId = args[1];
    const successArg = args[2];
    if (!skillId || (successArg !== '0' && successArg !== '1')) {
      console.error('用法: feedback <skill_id> <0|1>');
      process.exit(1);
    }

    const success = successArg === '1';
    const qUpdate = updateQValue(skillId, success);

    if (qUpdate) {
      console.log(`\n✅ q_value 已更新: ${skillId}`);
      console.log(`   ${qUpdate.oldQ.toFixed(4)} → ${qUpdate.newQ.toFixed(4)} (${success ? '成功+1' : '失败+1'})\n`);
    } else {
      console.log(`\n❌ 未找到 skill: ${skillId}\n`);
    }
  }

  // ---- pipeline (JSON output) ----
  else if (command === 'pipeline') {
    const intent = args[1];
    const message = args.slice(2).join(' ');
    if (!intent || !message) {
      console.error('需要 <intent> 和 <message> 参数');
      process.exit(1);
    }

    const result = prepareExecution(intent, message);

    console.log(JSON.stringify({
      fallback: result.fallbackMode,
      playbook: result.selectedPlaybook ? {
        skill_id: result.selectedPlaybook.skill_id,
        name: result.selectedPlaybook.name,
        match_score: result.selectedPlaybook.match_score,
        match_method: result.selectedPlaybook.match_method,
        q_value: result.selectedPlaybook.q_value,
        parameters: result.selectedPlaybook.parameters
      } : null,
      params: result.filledTemplate ? {
        confidence: result.filledTemplate.confidence,
        unfilled: result.filledTemplate.unfilled
      } : null,
      call: result.callParams,
      model: result.model,
      elapsed_ms: result.elapsed_ms
    }, null, 2));
  }

  // ---- execute (full loop: prepare → record feedback) ----
  else if (command === 'execute') {
    const intent = args[1];
    const message = args[2];
    const successArg = args[3];
    if (!intent || !message || (successArg !== '0' && successArg !== '1')) {
      console.error('用法: execute <intent> <message> <0|1>');
      process.exit(1);
    }

    const success = successArg === '1';
    const execution = prepareExecution(intent, message);

    if (execution.fallbackMode) {
      console.log('\n❌ 无匹配 playbook，走通用流程 (无反馈可记录)\n');
    } else {
      const feedback = recordFeedback(execution, success, {
        sessionId: `cli-${Date.now()}`,
        latencyMs: execution.elapsed_ms
      });

      console.log('\n🔄 完整闭环执行:');
      console.log(`  Playbook: ${execution.selectedPlaybook?.name} (${execution.selectedPlaybook?.skill_id})`);
      console.log(`  模型: ${execution.model}`);
      console.log(`  匹配分: ${execution.selectedPlaybook?.match_score.toFixed(2)}`);
      console.log(`  反馈: ${success ? '✅ 成功' : '❌ 失败'}`);
      if (feedback.qUpdate) {
        console.log(`  q_value: ${feedback.qUpdate.oldQ.toFixed(4)} → ${feedback.qUpdate.newQ.toFixed(4)}`);
      }
      console.log(`  sroe_requests: ${feedback.sroe_recorded ? '✅ 已记录' : '❌ 记录失败'}`);
      console.log(`  耗时: ${execution.elapsed_ms}ms\n`);
    }
  }

  // ---- qstats (Q-learning observability) ----
  else if (command === 'qstats') {
    const stats = getQLearningStats();

    console.log('\n📈 Q-Learning 闭环状态:\n');
    console.log(`  Playbook 总数: ${stats.total}`);
    console.log(`  已被使用: ${stats.used}`);
    console.log(`  平均 q_value: ${stats.avgQ.toFixed(4)}`);

    if (stats.topImprovers.length > 0) {
      console.log('\n  🏆 Top-5 使用过的 Playbooks:');
      for (const s of stats.topImprovers as any[]) {
        const total = s.success_count + s.failure_count;
        const rate = total > 0 ? ((s.success_count / total) * 100).toFixed(0) : 'N/A';
        console.log(`    [q=${Number(s.q_value).toFixed(3)}] ${s.name} (成功=${s.success_count} 失败=${s.failure_count} 成功率=${rate}%)`);
      }
    }

    if (stats.recentFeedback.length > 0) {
      console.log('\n  📋 最近 Skill-RAG 路由记录 (sroe_requests):');
      for (const r of stats.recentFeedback as any[]) {
        console.log(`    ${r.timestamp} | ${r.skill_id} → ${r.selected_model} | ${r.finish_reason} | ${r.latency_ms}ms`);
      }
    } else {
      console.log('\n  📋 暂无 Skill-RAG 路由记录');
    }
    console.log();
  }

  // ---- stats ----
  else if (command === 'stats') {
    const db = new Database(DB_PATH, { readonly: true });
    const total = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank').get() as any).c;
    const withTemplate = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE length(llm_prompt_template) > 0').get() as any).c;
    const used = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE success_count > 0 OR failure_count > 0').get() as any).c;
    const avgQ = (db.query('SELECT AVG(q_value) as avg FROM sys_skill_bank').get() as any).avg;
    const topSkills = db.query(`
      SELECT skill_id, name, q_value, success_count, failure_count
      FROM sys_skill_bank
      WHERE length(llm_prompt_template) > 0
      ORDER BY q_value DESC LIMIT 5
    `).all() as any[];
    db.close();

    console.log(`\n📊 Skill-RAG 状态:\n`);
    console.log(`  skill_bank 总条目: ${total}`);
    console.log(`  有模板可用: ${withTemplate}`);
    console.log(`  被使用过: ${used}`);
    console.log(`  平均 q_value: ${avgQ?.toFixed(3) || 'N/A'}`);
    console.log(`\n  🏆 Top-5 Playbooks:`);
    for (const s of topSkills) {
      console.log(`    [q=${s.q_value}] ${s.name} (成功=${s.success_count} 失败=${s.failure_count})`);
    }
    console.log();
  }

  else {
    console.error(`未知命令: ${command}，用 --help 查看用法`);
    process.exit(1);
  }
}
