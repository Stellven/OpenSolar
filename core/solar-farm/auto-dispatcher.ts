/**
 * Skill-RAG: Auto-Dispatcher (接水管)
 *
 * 统一入口：Solar 调 brain-router 前自动过 Skill-RAG
 * 修复断头 1/2/4/5:
 *   断头1: 主脑不会自动调 matchPlaybooks → 本模块就是自动调用者
 *   断头2: sroe_requests 不带 skill_id → recordDispatch 写回
 *   断头4: 模块间零导入 → 本模块串联 matcher/extractor/call-niuma/executor
 *   断头5: 冷启动死循环 → UCB1 + epsilon-greedy 探索机制
 *
 * 算法参数 (基于研究报告 skill-rag-research-2026-02-24.md):
 *   UCB1 C = 1.41 (sqrt(2))
 *   Epsilon = 0.15 初始, 衰减到 0.05
 *   Alpha = 0.15 初始, 衰减到 0.05
 *   Optimistic init q = 0.7 (已设)
 *
 * @version 1.0.0
 * @created 2026-02-24
 */

import Database from 'bun:sqlite';
import { homedir } from 'os';
import { join } from 'path';
import { matchPlaybooks, type PlaybookMatch, type MatchResult } from './playbook-matcher';
import { extractParams, type FilledTemplate } from './param-extractor';
import { buildNiumaCall, type NiumaCallResult } from './call-niuma';
import { selectModel, updateQValue } from './playbook-executor';

const DB_PATH = join(homedir(), '.solar', 'solar.db');

// ============================================================
// 配置
// ============================================================

export interface DispatchConfig {
  /** UCB1 探索系数 C, 默认 sqrt(2) ≈ 1.41 */
  ucbC: number;
  /** Epsilon-greedy 探索概率, 默认 0.15 */
  epsilon: number;
  /** 最小 epsilon (衰减下限) */
  epsilonMin: number;
  /** 每 N 次调用 epsilon 衰减一次 */
  epsilonDecayEvery: number;
  /** epsilon 衰减因子 */
  epsilonDecayFactor: number;
  /** Q-learning alpha */
  alpha: number;
  /** 最小 alpha */
  alphaMin: number;
  /** 置信度阈值：低于此值则透传 (不用 playbook) */
  confidenceThreshold: number;
  /** 匹配 topK */
  topK: number;
  /** 探索策略: 'ucb' | 'epsilon' | 'hybrid' */
  explorationStrategy: 'ucb' | 'epsilon' | 'hybrid';
}

const DEFAULT_CONFIG: DispatchConfig = {
  ucbC: 1.41,
  epsilon: 0.30,           // 研究推荐: 冷启动阶段高探索率 (0.30→0.15→0.05)
  epsilonMin: 0.05,
  epsilonDecayEvery: 50,
  epsilonDecayFactor: 0.9,
  alpha: 0.15,             // 研究推荐: 0.15(1-100次)→0.10(100-500)→0.05(500+)
  alphaMin: 0.05,
  confidenceThreshold: 0.5,
  topK: 10,
  explorationStrategy: 'hybrid',
};

// ============================================================
// 类型定义
// ============================================================

export interface DispatchResult {
  /** 用户原始意图 */
  intent: string;
  /** 匹配结果 */
  matchResult: MatchResult;
  /** 选中的 playbook (null = 透传模式) */
  selectedPlaybook: PlaybookMatch | null;
  /** 选择方法 */
  selectionMethod: 'ucb' | 'epsilon_explore' | 'greedy' | 'none';
  /** 填充后的模板 */
  filledTemplate: FilledTemplate | null;
  /** 模型调用参数 */
  callParams: NiumaCallResult | null;
  /** 是否透传 (无匹配或置信度不够) */
  fallbackMode: boolean;
  /** 总耗时 ms */
  elapsed_ms: number;
  /** 探索信息 */
  exploration: {
    totalDispatches: number;
    currentEpsilon: number;
    wasExploration: boolean;
    ucbScores?: { skill_id: string; ucb: number }[];
  };
}

export interface FeedbackResult {
  skill_id: string;
  old_q: number;
  new_q: number;
  alpha_used: number;
  sroe_updated: boolean;
}

// ============================================================
// 全局调度计数 (内存缓存, 用于 epsilon 衰减)
// ============================================================

let totalDispatches = 0;

function loadTotalDispatches(): number {
  try {
    const db = new Database(DB_PATH, { readonly: true });
    const row = db.query(`
      SELECT COUNT(*) as c FROM sroe_requests WHERE skill_id IS NOT NULL AND skill_id != ''
    `).get() as any;
    db.close();
    return row?.c || 0;
  } catch {
    return 0;
  }
}

// ============================================================
// UCB1 选择
// ============================================================

/**
 * UCB1 选择: score = q_value + C * sqrt(ln(N) / n_i)
 *
 * N = 总调度次数
 * n_i = 该 playbook 被使用次数 (success + failure)
 *
 * 关键修复: n_i=0 时 UCB 为 Infinity，保证未尝试的 playbook 被优先探索
 * (研究推荐: 冷启动阶段未尝试应得到最高优先级)
 *
 * @returns 按 UCB score 排序后的 candidates, 以及 UCB 分数
 */
function ucbSelect(
  candidates: PlaybookMatch[],
  totalN: number,
  C: number
): { selected: PlaybookMatch; scores: { skill_id: string; ucb: number }[] } {
  const N = Math.max(totalN, 1);

  const scores = candidates.map(pb => {
    const ni = (pb.success_count || 0) + (pb.failure_count || 0);
    // n=0 → Infinity: 未尝试过的 playbook 获得最高探索优先级
    const exploration = ni === 0 ? Infinity : C * Math.sqrt(Math.log(N) / ni);
    const ucb = ni === 0 ? Infinity : pb.q_value + exploration;
    return { skill_id: pb.skill_id, ucb, playbook: pb };
  });

  // 未尝试的 playbook 随机化顺序（避免总是选第一个未尝试的）
  const untried = scores.filter(s => s.ucb === Infinity);
  const tried = scores.filter(s => s.ucb !== Infinity);
  // shuffle untried
  for (let i = untried.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [untried[i], untried[j]] = [untried[j], untried[i]];
  }
  tried.sort((a, b) => b.ucb - a.ucb);
  const sorted = [...untried, ...tried];

  return {
    selected: sorted[0].playbook,
    scores: sorted.map(s => ({
      skill_id: s.skill_id,
      ucb: s.ucb === Infinity ? 999.99 : parseFloat(s.ucb.toFixed(4))
    })),
  };
}

// ============================================================
// Epsilon-greedy 选择
// ============================================================

/**
 * Epsilon-greedy: 以 epsilon 概率随机选一个 (探索), 否则选 q_value 最高的 (利用)
 */
function epsilonGreedySelect(
  candidates: PlaybookMatch[],
  epsilon: number
): { selected: PlaybookMatch; wasExploration: boolean } {
  if (Math.random() < epsilon && candidates.length > 1) {
    // 探索: 随机选一个 (偏好使用次数少的)
    const unused = candidates.filter(
      pb => (pb.success_count || 0) + (pb.failure_count || 0) === 0
    );
    const pool = unused.length > 0 ? unused : candidates;
    const idx = Math.floor(Math.random() * pool.length);
    return { selected: pool[idx], wasExploration: true };
  }

  // 利用: 选 q_value 最高的 (match_score 已经包含 q_value 权重)
  return { selected: candidates[0], wasExploration: false };
}

// ============================================================
// 计算当前 epsilon (衰减)
// ============================================================

function currentEpsilon(config: DispatchConfig, totalN: number): number {
  if (totalN === 0) return config.epsilon;
  const decays = Math.floor(totalN / config.epsilonDecayEvery);
  const eps = config.epsilon * Math.pow(config.epsilonDecayFactor, decays);
  return Math.max(eps, config.epsilonMin);
}

// ============================================================
// 模型选择 — 已迁移到 playbook-executor.ts (import { selectModel })
// ============================================================

// ============================================================
// 核心: dispatch()
// ============================================================

/**
 * 统一调度入口
 *
 * 流程:
 *   1. matchPlaybooks(intent) — 检索匹配 playbook
 *   2. UCB/epsilon 选择 — 智能探索-利用平衡
 *   3. extractParams — 填充模板参数
 *   4. buildNiumaCall — 构建带人格的模型调用
 *   5. 返回 DispatchResult (调用者决定是否执行)
 *
 * @param intent - 用户意图/消息
 * @param message - 用户原始消息 (用于参数提取)
 * @param context - 附加上下文 (代码、文件内容等)
 * @param config - 调度配置
 */
export function dispatch(
  intent: string,
  message?: string,
  context?: string,
  config?: Partial<DispatchConfig>
): DispatchResult {
  const start = Date.now();
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const userMessage = message || intent;

  // 初始化总调度数 (懒加载)
  if (totalDispatches === 0) {
    totalDispatches = loadTotalDispatches();
  }

  // Step 1: 匹配 playbooks (扩大 topK 给探索留空间)
  const matchResult = matchPlaybooks(intent, cfg.topK);

  // 无匹配 → 透传
  if (matchResult.matches.length === 0) {
    return {
      intent,
      matchResult,
      selectedPlaybook: null,
      selectionMethod: 'none',
      filledTemplate: null,
      callParams: null,
      fallbackMode: true,
      elapsed_ms: Date.now() - start,
      exploration: {
        totalDispatches,
        currentEpsilon: currentEpsilon(cfg, totalDispatches),
        wasExploration: false,
      },
    };
  }

  // Step 2: 智能选择 (UCB + epsilon-greedy)
  let selected: PlaybookMatch;
  let selectionMethod: DispatchResult['selectionMethod'];
  let wasExploration = false;
  let ucbScores: { skill_id: string; ucb: number }[] | undefined;
  const eps = currentEpsilon(cfg, totalDispatches);

  if (cfg.explorationStrategy === 'ucb') {
    const ucbResult = ucbSelect(matchResult.matches, totalDispatches, cfg.ucbC);
    selected = ucbResult.selected;
    selectionMethod = 'ucb';
    ucbScores = ucbResult.scores;
    wasExploration = selected.skill_id !== matchResult.matches[0].skill_id;
  } else if (cfg.explorationStrategy === 'epsilon') {
    const epsResult = epsilonGreedySelect(matchResult.matches, eps);
    selected = epsResult.selected;
    selectionMethod = epsResult.wasExploration ? 'epsilon_explore' : 'greedy';
    wasExploration = epsResult.wasExploration;
  } else {
    // hybrid: 先 UCB 排序, 再 epsilon-greedy 在 UCB 排序后的列表上选
    const ucbResult = ucbSelect(matchResult.matches, totalDispatches, cfg.ucbC);
    ucbScores = ucbResult.scores;

    // 用 UCB 排序后的列表做 epsilon-greedy
    const ucbSorted = ucbResult.scores.map(s =>
      matchResult.matches.find(m => m.skill_id === s.skill_id)!
    );
    const epsResult = epsilonGreedySelect(ucbSorted, eps);
    selected = epsResult.selected;
    wasExploration = epsResult.wasExploration;
    selectionMethod = epsResult.wasExploration ? 'epsilon_explore' : 'ucb';
  }

  // Step 3: 提取参数, 填充模板
  const filledTemplate = extractParams(
    selected.llm_prompt_template,
    userMessage,
    context
  );

  // 置信度检查: 如果参数填充率太低, 降级透传
  if (filledTemplate.confidence < cfg.confidenceThreshold) {
    return {
      intent,
      matchResult,
      selectedPlaybook: selected,
      selectionMethod,
      filledTemplate,
      callParams: null,
      fallbackMode: true,
      elapsed_ms: Date.now() - start,
      exploration: {
        totalDispatches,
        currentEpsilon: eps,
        wasExploration,
        ucbScores,
      },
    };
  }

  // Step 4: 构建模型调用 (带人格)
  const model = selectModel(selected);
  const callParams = buildNiumaCall({
    model,
    task: filledTemplate.filled,
    context: context || undefined,
    outputFormat: 'markdown',
  });

  totalDispatches++;

  // Step 5: 写入 pending skill context (供 brain-router tracker 消费)
  try {
    const pendingDb = new Database(DB_PATH);
    pendingDb.run(
      `INSERT INTO sroe_pending_skill_context (skill_id, skill_name, context_tags)
       VALUES (?, ?, ?)`,
      [
        selected.skill_id,
        selected.name,
        JSON.stringify([
          ...selected.trigger_keywords.slice(0, 5),
          selectionMethod,
        ]),
      ]
    );
    pendingDb.close();
  } catch { /* non-critical, tracker fallback handles missing context */ }

  return {
    intent,
    matchResult,
    selectedPlaybook: selected,
    selectionMethod,
    filledTemplate,
    callParams,
    fallbackMode: false,
    elapsed_ms: Date.now() - start,
    exploration: {
      totalDispatches,
      currentEpsilon: eps,
      wasExploration,
      ucbScores,
    },
  };
}

// ============================================================
// 反馈: recordDispatch()
// ============================================================

/**
 * 记录调度结果, 闭环更新:
 *   1. updateQValue — Q-learning 更新
 *   2. sroe_requests 写入 skill_id — 修复断头2
 *
 * @param result - dispatch() 的返回值
 * @param success - 调用是否成功
 * @param meta - 额外元数据 (latency, tokens 等)
 */
export function recordDispatch(
  result: DispatchResult,
  success: boolean,
  meta?: {
    latency_ms?: number;
    tokens_in?: number;
    tokens_out?: number;
    quality_score?: number;
    request_id?: string;
  }
): FeedbackResult | null {
  if (!result.selectedPlaybook || result.fallbackMode) {
    return null;
  }

  const skillId = result.selectedPlaybook.skill_id;

  // 1. Q-learning 更新 — 委托给 playbook-executor 的统一实现
  //    计算衰减 alpha 后传入
  const config = { ...DEFAULT_CONFIG };
  const decays = Math.floor(totalDispatches / config.epsilonDecayEvery);
  const alpha = Math.max(
    config.alpha * Math.pow(config.epsilonDecayFactor, decays),
    config.alphaMin
  );

  const qResult = updateQValue(skillId, success, alpha);
  if (!qResult) return null;

  // 2. 写回 skill_id 到 sroe_requests (修复断头2)
  let sroeUpdated = false;
  const db = new Database(DB_PATH);
  try {
    if (meta?.request_id) {
      // 如果有 request_id, 更新特定记录
      db.run(`
        UPDATE sroe_requests
        SET skill_id = ?, context_tags = ?
        WHERE id = ?
      `, [
        skillId,
        JSON.stringify([
          result.selectedPlaybook.name,
          result.selectionMethod,
          result.exploration.wasExploration ? 'explored' : 'exploited',
        ]),
        meta.request_id,
      ]);
      sroeUpdated = true;
    } else {
      // 否则更新最近一条无 skill_id 的记录
      db.run(`
        UPDATE sroe_requests
        SET skill_id = ?, context_tags = ?
        WHERE id = (
          SELECT id FROM sroe_requests
          WHERE (skill_id IS NULL OR skill_id = '')
          ORDER BY timestamp DESC LIMIT 1
        )
      `, [
        skillId,
        JSON.stringify([
          result.selectedPlaybook.name,
          result.selectionMethod,
        ]),
      ]);
      sroeUpdated = true;
    }
  } catch {
    // sroe_requests 写入失败不影响主流程
    sroeUpdated = false;
  } finally {
    db.close();
  }

  return {
    skill_id: skillId,
    old_q: qResult.oldQ,
    new_q: qResult.newQ,
    alpha_used: parseFloat(alpha.toFixed(4)),
    sroe_updated: sroeUpdated,
  };
}

// ============================================================
// 统计: getStats()
// ============================================================

export function getStats(): {
  totalPlaybooks: number;
  usedPlaybooks: number;
  unusedPlaybooks: number;
  avgQValue: number;
  totalDispatches: number;
  sroeWithSkillId: number;
  sroeTotal: number;
  coveragePercent: number;
} {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    const total = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE length(llm_prompt_template) > 0').get() as any).c;
    const used = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE success_count > 0 OR failure_count > 0').get() as any).c;
    const avgQ = (db.query('SELECT AVG(q_value) as avg FROM sys_skill_bank').get() as any).avg || 0.7;
    const sroeTotal = (db.query('SELECT COUNT(*) as c FROM sroe_requests').get() as any).c;
    const sroeWithSkill = (db.query("SELECT COUNT(*) as c FROM sroe_requests WHERE skill_id IS NOT NULL AND skill_id != ''").get() as any).c;

    return {
      totalPlaybooks: total,
      usedPlaybooks: used,
      unusedPlaybooks: total - used,
      avgQValue: parseFloat(avgQ.toFixed(3)),
      totalDispatches: loadTotalDispatches(),
      sroeWithSkillId: sroeWithSkill,
      sroeTotal: sroeTotal,
      coveragePercent: sroeTotal > 0 ? parseFloat(((sroeWithSkill / sroeTotal) * 100).toFixed(1)) : 0,
    };
  } finally {
    db.close();
  }
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help') {
    console.log(`
Skill-RAG: Auto-Dispatcher v1.0 (接水管)

用法:
  bun auto-dispatcher.ts dispatch <intent> [context]   # 调度 (匹配+选择+填充)
  bun auto-dispatcher.ts feedback <skill_id> <success>  # 反馈 (Q-learning 更新)
  bun auto-dispatcher.ts stats                          # 统计
  bun auto-dispatcher.ts explore <intent>               # 仅探索 (不执行, 展示选择过程)

示例:
  bun auto-dispatcher.ts dispatch "代码有bug，报错TypeError"
  bun auto-dispatcher.ts dispatch "帮我review这段代码" "function foo() { ... }"
  bun auto-dispatcher.ts feedback perf_debug_001 true
  bun auto-dispatcher.ts stats
  bun auto-dispatcher.ts explore "性能很慢需要优化"

修复的断头:
  断头1: 本模块就是自动调用者 ✅
  断头2: recordDispatch 写 skill_id 到 sroe_requests ✅
  断头4: 串联 matcher/extractor/call-niuma/executor ✅
  断头5: UCB1 + epsilon-greedy 探索机制 ✅
`);
    process.exit(0);
  }

  const command = args[0];

  if (command === 'dispatch' || command === 'explore') {
    const intent = args[1];
    if (!intent) {
      console.error('❌ 缺少 intent 参数');
      process.exit(1);
    }
    const context = args[2] || undefined;

    const result = dispatch(intent, intent, context);

    console.log(`\n🔀 Auto-Dispatcher: "${intent}"`);
    console.log(`   候选池: ${result.matchResult.total_candidates} | 匹配: ${result.matchResult.matches.length} | 耗时: ${result.elapsed_ms}ms`);
    console.log(`   探索策略: hybrid | epsilon: ${result.exploration.currentEpsilon.toFixed(3)} | 总调度: ${result.exploration.totalDispatches}`);

    if (result.fallbackMode) {
      console.log(`\n   ⚡ 透传模式 (${result.matchResult.matches.length === 0 ? '无匹配' : '置信度不足'})`);
      if (result.selectedPlaybook) {
        console.log(`      尝试匹配: ${result.selectedPlaybook.name} (${result.selectedPlaybook.skill_id})`);
        console.log(`      置信度: ${result.filledTemplate?.confidence?.toFixed(2) || 'N/A'}`);
      }
    } else {
      console.log(`\n   🎯 选中: ${result.selectedPlaybook!.name} (${result.selectedPlaybook!.skill_id})`);
      console.log(`      方法: ${result.selectionMethod} | q=${result.selectedPlaybook!.q_value} | 探索=${result.exploration.wasExploration ? '是' : '否'}`);
      console.log(`      成功=${result.selectedPlaybook!.success_count} 失败=${result.selectedPlaybook!.failure_count}`);
      console.log(`      模板置信度: ${result.filledTemplate!.confidence.toFixed(2)}`);
      console.log(`      未填参数: ${result.filledTemplate!.unfilled.length > 0 ? result.filledTemplate!.unfilled.map(p => `{{${p}}}`).join(', ') : '无'}`);
      console.log(`      模型: ${result.callParams!.model}`);
      console.log(`      人格注入: ${result.callParams!.personalityInjected ? '✅' : '❌'}`);

      if (result.callParams!.ddRole) {
        console.log(`      D&D角色: ${result.callParams!.ddRole}`);
      }
    }

    // 展示 UCB 分数
    if (result.exploration.ucbScores && result.exploration.ucbScores.length > 0) {
      console.log(`\n   📊 UCB 分数 (C=${DEFAULT_CONFIG.ucbC}):`);
      for (const s of result.exploration.ucbScores.slice(0, 5)) {
        const pb = result.matchResult.matches.find(m => m.skill_id === s.skill_id);
        const marker = result.selectedPlaybook?.skill_id === s.skill_id ? '→' : ' ';
        console.log(`   ${marker} [UCB ${s.ucb.toFixed(3)}] ${pb?.name || s.skill_id} (q=${pb?.q_value?.toFixed(2)} n=${(pb?.success_count || 0) + (pb?.failure_count || 0)})`);
      }
    }

    if (command === 'explore') {
      console.log(`\n   (explore 模式: 仅展示选择过程, 不执行)`);
    }

    if (command === 'dispatch' && !result.fallbackMode) {
      console.log(`\n   📝 填充后 prompt (前200字):`);
      console.log(`   ${result.filledTemplate!.filled.substring(0, 200)}${result.filledTemplate!.filled.length > 200 ? '...' : ''}`);
    }
    console.log();

  } else if (command === 'feedback') {
    const skillId = args[1];
    const success = args[2] === 'true' || args[2] === '1';

    if (!skillId) {
      console.error('❌ 缺少 skill_id 参数');
      process.exit(1);
    }

    // 构造一个最小 DispatchResult 来调 recordDispatch
    const minResult: DispatchResult = {
      intent: 'manual-feedback',
      matchResult: { query: '', matches: [], total_candidates: 0, elapsed_ms: 0 },
      selectedPlaybook: {
        skill_id: skillId,
        name: skillId,
        description: '',
        llm_prompt_template: '',
        parameters: [],
        trigger_keywords: [],
        q_value: 0,
        match_score: 0,
        match_method: 'keyword',
        success_count: 0,
        failure_count: 0,
      },
      selectionMethod: 'greedy',
      filledTemplate: null,
      callParams: null,
      fallbackMode: false,
      elapsed_ms: 0,
      exploration: { totalDispatches: 0, currentEpsilon: 0, wasExploration: false },
    };

    const fb = recordDispatch(minResult, success);
    if (fb) {
      console.log(`\n✅ 反馈已记录:`);
      console.log(`   skill_id: ${fb.skill_id}`);
      console.log(`   q_value: ${fb.old_q} → ${fb.new_q} (alpha=${fb.alpha_used})`);
      console.log(`   success: ${success}`);
      console.log(`   sroe_updated: ${fb.sroe_updated}`);
    } else {
      console.log(`\n❌ 反馈记录失败 (skill_id "${skillId}" 未找到)`);
    }
    console.log();

  } else if (command === 'stats') {
    const stats = getStats();
    console.log(`\n📊 Auto-Dispatcher 统计:`);
    console.log(`   Playbooks: ${stats.totalPlaybooks} 总 | ${stats.usedPlaybooks} 已用 | ${stats.unusedPlaybooks} 未用`);
    console.log(`   平均 q_value: ${stats.avgQValue}`);
    console.log(`   SROE 覆盖: ${stats.sroeWithSkillId}/${stats.sroeTotal} (${stats.coveragePercent}%)`);
    console.log(`   总调度: ${stats.totalDispatches}`);

    // 展示 playbook 使用排行
    const db = new Database(DB_PATH, { readonly: true });
    const top = db.query(`
      SELECT skill_id, name, q_value, success_count, failure_count
      FROM sys_skill_bank
      WHERE (success_count > 0 OR failure_count > 0) AND length(llm_prompt_template) > 0
      ORDER BY (success_count + failure_count) DESC
      LIMIT 10
    `).all() as any[];

    if (top.length > 0) {
      console.log(`\n   🏆 使用排行 (Top ${top.length}):`);
      for (const t of top) {
        console.log(`      ${t.name} (${t.skill_id}): q=${t.q_value} s=${t.success_count} f=${t.failure_count}`);
      }
    }

    // 展示未使用的 playbook 数量分布
    const unused = db.query(`
      SELECT COUNT(*) as c, ROUND(q_value, 1) as q_bucket
      FROM sys_skill_bank
      WHERE success_count = 0 AND failure_count = 0 AND length(llm_prompt_template) > 0
      GROUP BY q_bucket
      ORDER BY q_bucket DESC
    `).all() as any[];

    if (unused.length > 0) {
      console.log(`\n   🧊 未使用 playbook 分布 (q_value → 数量):`);
      for (const u of unused) {
        console.log(`      q=${u.q_bucket}: ${u.c} 个`);
      }
    }

    db.close();
    console.log();

  } else if (command === 'hook') {
    // Hook 模式: 简洁输出，供 UserPromptSubmit hook 注入上下文
    const intent = args[1];
    if (!intent) { process.exit(0); }

    try {
      const result = dispatch(intent, intent);

      if (!result.selectedPlaybook) {
        // 完全无匹配 → 不输出
        process.exit(0);
      }

      const pb = result.selectedPlaybook;
      // hook 是 advisory 模式: 即使 fallbackMode (置信度低) 也输出提示
      // callParams 在 fallbackMode 时为 null, 从 playbook 本身推断模型
      const model = result.callParams?.model || pb.preferred_model || 'auto';
      const ddRole = result.callParams?.ddRole || '';
      const templatePreview = result.filledTemplate?.filled?.substring(0, 120) || pb.llm_prompt_template.substring(0, 120);
      const confidence = result.filledTemplate?.confidence?.toFixed(2) || 'N/A';
      const isFallback = result.fallbackMode;

      // 输出简洁的上下文提示
      console.log(`<skill-rag-hint>`);
      console.log(`匹配 Playbook: ${pb.name} (${pb.skill_id})${isFallback ? ' [参数待补充]' : ''}`);
      console.log(`  模型: ${model} | D&D: ${ddRole} | 选择: ${result.selectionMethod} | 置信度: ${confidence}`);
      console.log(`  q=${pb.q_value} 成功=${pb.success_count} 失败=${pb.failure_count} | 探索=${result.exploration.wasExploration ? '是' : '否'}`);
      if (result.filledTemplate && result.filledTemplate.unfilled.length > 0) {
        console.log(`  未填参数: ${result.filledTemplate.unfilled.map(p => '{{' + p + '}}').join(', ')}`);
      }
      console.log(`  模板: ${templatePreview}...`);
      if (isFallback) {
        console.log(`建议: 此 playbook 可作为回复参考框架，用户可能需要提供更多上下文 (如代码片段)`);
      } else {
        console.log(`建议: 使用此 playbook 模板引导回复，可通过 brain-router 调用 ${model} 执行`);
      }
      console.log(`</skill-rag-hint>`);
    } catch {
      // hook 模式静默失败，不影响用户体验
      process.exit(0);
    }

  } else {
    console.error(`❌ 未知命令: ${command}`);
    console.log('使用 --help 查看用法');
    process.exit(1);
  }
}
