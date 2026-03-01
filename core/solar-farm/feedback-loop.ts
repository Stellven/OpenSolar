/**
 * Feedback Loop: 反馈闭环引擎
 *
 * 扫描 sroe_requests 中有 skill_id 但无 quality_score 的请求，
 * 基于 finish_reason / error / latency 计算质量分数，
 * 调用 updateQValue 写回 sys_skill_bank 的 q_value。
 *
 * Part of Phase 4: 反馈闭环强化
 * @version 1.0.0
 * @created 2026-02-24
 */

import Database from 'bun:sqlite';
import { homedir } from 'os';
import { join } from 'path';
import { updateQValue } from './playbook-executor';

const DB_PATH = join(homedir(), '.solar', 'solar.db');

// ============================================================
// 类型定义
// ============================================================

export interface QualitySignals {
  finish_reason: string | null;
  error_type: string | null;
  error_message: string | null;
  latency_ms: number | null;
  response_tokens: number | null;
  tps: number | null;
}

export interface QualityResult {
  quality_score: number;        // [0-1] final quality score
  components: {
    completion: number;         // finish_reason based [0-1]
    error_penalty: number;      // error penalty [0-1] (1 = no error)
    latency_factor: number;     // latency-based [0-1]
    throughput_factor: number;   // tps-based [0-1]
  };
  reasoning: string;
}

export interface FeedbackResult {
  request_id: string;
  skill_id: string;
  quality: QualityResult;
  q_update: { oldQ: number; newQ: number; reward: number } | null;
}

export interface FeedbackSummary {
  processed: number;
  skipped: number;
  errors: number;
  results: FeedbackResult[];
  elapsed_ms: number;
  avg_quality: number;
  q_updates: { skill_id: string; oldQ: number; newQ: number }[];
}

// ============================================================
// Schema Migration
// ============================================================

/**
 * Ensure quality_score column exists on sroe_requests
 */
function ensureSchema(db: Database): void {
  const cols = db.query(`PRAGMA table_info(sroe_requests)`).all() as any[];
  const hasQuality = cols.some((c: any) => c.name === 'quality_score');

  if (!hasQuality) {
    db.run(`ALTER TABLE sroe_requests ADD COLUMN quality_score REAL`);
  }
}

// ============================================================
// 质量评估
// ============================================================

// Latency baseline (from sroe_requests distribution)
const LATENCY_P50 = 25000;  // 25s median
const LATENCY_P95 = 80000;  // 80s P95

/**
 * Calculate quality score from available signals
 *
 * Components (weighted):
 *   completion (0.50): Did the model finish successfully?
 *   error_penalty (0.25): Were there errors?
 *   latency_factor (0.15): How fast was the response?
 *   throughput_factor (0.10): Token throughput
 */
export function calculateQuality(signals: QualitySignals): QualityResult {
  // 1. Completion score (50% weight) — finish_reason based
  let completion = 0.5;  // default for unknown
  if (signals.finish_reason === 'stop') {
    completion = 1.0;
  } else if (signals.finish_reason === 'length') {
    completion = 0.6;  // truncated but partial success
  } else if (signals.finish_reason === 'error') {
    completion = 0.1;
  } else if (signals.finish_reason === 'content_filter') {
    completion = 0.3;
  }

  // 2. Error penalty (25% weight) — 1.0 = no error
  let error_penalty = 1.0;
  if (signals.error_type) {
    if (signals.error_type === 'timeout') {
      error_penalty = 0.2;
    } else if (signals.error_type === 'rate_limit') {
      error_penalty = 0.4;  // not the model's fault
    } else {
      error_penalty = 0.1;  // generic error
    }
  }

  // 3. Latency factor (15% weight)
  let latency_factor = 0.5;  // default for unknown
  if (signals.latency_ms && signals.latency_ms > 0) {
    if (signals.latency_ms <= LATENCY_P50) {
      latency_factor = 1.0;
    } else if (signals.latency_ms <= LATENCY_P95) {
      // Linear interpolation P50→P95 maps to 1.0→0.4
      latency_factor = 1.0 - 0.6 * ((signals.latency_ms - LATENCY_P50) / (LATENCY_P95 - LATENCY_P50));
    } else {
      latency_factor = 0.3;  // extremely slow
    }
  }

  // 4. Throughput factor (10% weight) — tokens per second
  let throughput_factor = 0.5;  // default
  if (signals.tps && signals.tps > 0) {
    if (signals.tps >= 50) {
      throughput_factor = 1.0;
    } else if (signals.tps >= 20) {
      throughput_factor = 0.8;
    } else if (signals.tps >= 10) {
      throughput_factor = 0.6;
    } else {
      throughput_factor = 0.4;
    }
  }

  // Weighted combination
  const quality_score = parseFloat((
    completion * 0.50 +
    error_penalty * 0.25 +
    latency_factor * 0.15 +
    throughput_factor * 0.10
  ).toFixed(4));

  // Build reasoning
  const parts: string[] = [];
  parts.push(`finish=${signals.finish_reason || 'unknown'}(${completion.toFixed(1)})`);
  if (signals.error_type) parts.push(`err=${signals.error_type}(${error_penalty.toFixed(1)})`);
  if (signals.latency_ms) parts.push(`lat=${Math.round(signals.latency_ms)}ms(${latency_factor.toFixed(1)})`);
  if (signals.tps) parts.push(`tps=${signals.tps.toFixed(0)}(${throughput_factor.toFixed(1)})`);

  return {
    quality_score,
    components: { completion, error_penalty, latency_factor, throughput_factor },
    reasoning: parts.join(', ')
  };
}

// ============================================================
// 反馈闭环主流程
// ============================================================

/**
 * Process unscored requests: calculate quality → update q_value
 *
 * @param limit - Max requests to process (default 100)
 * @param dryRun - If true, calculate but don't write back
 */
export function processFeedbackLoop(limit: number = 100, dryRun: boolean = false): FeedbackSummary {
  const start = Date.now();
  const db = new Database(DB_PATH);

  try {
    // Ensure schema (always, even in dry run — needed for query)
    ensureSchema(db);

    // Find requests with skill_id but no quality_score
    const pendingRows = db.query(`
      SELECT request_id, skill_id, finish_reason, error_type, error_message,
             latency_ms, response_tokens, tps
      FROM sroe_requests
      WHERE skill_id IS NOT NULL
        AND skill_id != ''
        AND quality_score IS NULL
      ORDER BY timestamp DESC
      LIMIT ?
    `).all(limit) as any[];

    const results: FeedbackResult[] = [];
    const qUpdates: Map<string, { oldQ: number; newQ: number }> = new Map();
    let processed = 0;
    let skipped = 0;
    let errors = 0;

    for (const row of pendingRows) {
      try {
        // Calculate quality
        const signals: QualitySignals = {
          finish_reason: row.finish_reason,
          error_type: row.error_type,
          error_message: row.error_message,
          latency_ms: row.latency_ms,
          response_tokens: row.response_tokens,
          tps: row.tps
        };

        const quality = calculateQuality(signals);

        // Write quality_score back to sroe_requests
        if (!dryRun) {
          db.run(
            `UPDATE sroe_requests SET quality_score = ? WHERE request_id = ?`,
            [quality.quality_score, row.request_id]
          );
        }

        // Update q_value via playbook-executor
        let qResult: { oldQ: number; newQ: number; reward: number } | null = null;
        if (!dryRun && row.skill_id) {
          qResult = updateQValue(row.skill_id, quality.quality_score);
          if (qResult) {
            qUpdates.set(row.skill_id, { oldQ: qResult.oldQ, newQ: qResult.newQ });
          }
        }

        results.push({
          request_id: row.request_id,
          skill_id: row.skill_id,
          quality,
          q_update: qResult
        });
        processed++;
      } catch (e) {
        errors++;
      }
    }

    // Calculate average quality
    const avgQuality = results.length > 0
      ? parseFloat((results.reduce((s, r) => s + r.quality.quality_score, 0) / results.length).toFixed(4))
      : 0;

    return {
      processed,
      skipped,
      errors,
      results,
      elapsed_ms: Date.now() - start,
      avg_quality: avgQuality,
      q_updates: Array.from(qUpdates.entries()).map(([skill_id, v]) => ({ skill_id, ...v }))
    };
  } finally {
    db.close();
  }
}

/**
 * Backfill quality scores for ALL requests (even without skill_id)
 * Useful for establishing baseline quality distribution
 */
export function backfillQualityScores(limit: number = 1000): { processed: number; elapsed_ms: number } {
  const start = Date.now();
  const db = new Database(DB_PATH);

  try {
    ensureSchema(db);

    const rows = db.query(`
      SELECT request_id, finish_reason, error_type, error_message,
             latency_ms, response_tokens, tps
      FROM sroe_requests
      WHERE quality_score IS NULL
      ORDER BY timestamp DESC
      LIMIT ?
    `).all(limit) as any[];

    let processed = 0;
    for (const row of rows) {
      const quality = calculateQuality({
        finish_reason: row.finish_reason,
        error_type: row.error_type,
        error_message: row.error_message,
        latency_ms: row.latency_ms,
        response_tokens: row.response_tokens,
        tps: row.tps
      });

      db.run(
        `UPDATE sroe_requests SET quality_score = ? WHERE request_id = ?`,
        [quality.quality_score, row.request_id]
      );
      processed++;
    }

    return { processed, elapsed_ms: Date.now() - start };
  } finally {
    db.close();
  }
}

// ============================================================
// 方案B: 按任务类型聚合反馈 (不依赖 skill_id)
// ============================================================

export interface TaskTypePerformance {
  model_id: string;
  task_type: string;
  sample_count: number;
  success_count: number;
  avg_quality: number;
  avg_latency_ms: number | null;
  avg_tps: number | null;
}

export interface AggregateResult {
  processed: number;
  updated_models: number;
  performance_rows: TaskTypePerformance[];
  elapsed_ms: number;
}

/**
 * 方案B: 按 task_type + selected_model 聚合反馈
 *
 * 不依赖 skill_id，直接利用所有请求学习模型在不同任务类型上的表现。
 * 这解决了 97.7% 请求没有 skill_id 的问题。
 *
 * @param backfillFirst - 是否先回填 quality_score
 */
export function aggregateByTaskType(backfillFirst: boolean = true): AggregateResult {
  const start = Date.now();
  const db = new Database(DB_PATH);

  try {
    ensureSchema(db);

    // Step 1: Backfill quality_score if requested
    let processed = 0;
    if (backfillFirst) {
      const unscored = db.query(`
        SELECT request_id, finish_reason, error_type, error_message,
               latency_ms, response_tokens, tps
        FROM sroe_requests
        WHERE quality_score IS NULL
      `).all() as any[];

      for (const row of unscored) {
        const quality = calculateQuality({
          finish_reason: row.finish_reason,
          error_type: row.error_type,
          error_message: row.error_message,
          latency_ms: row.latency_ms,
          response_tokens: row.response_tokens,
          tps: row.tps
        });
        db.run(
          `UPDATE sroe_requests SET quality_score = ? WHERE request_id = ?`,
          [quality.quality_score, row.request_id]
        );
        processed++;
      }
    }

    // Step 2: Aggregate by model + task_type
    const aggregates = db.query(`
      SELECT
        selected_model as model_id,
        task_type,
        COUNT(*) as sample_count,
        SUM(CASE WHEN quality_score >= 0.5 THEN 1 ELSE 0 END) as success_count,
        AVG(quality_score) as avg_quality,
        AVG(latency_ms) as avg_latency_ms,
        AVG(tps) as avg_tps
      FROM sroe_requests
      WHERE quality_score IS NOT NULL
      GROUP BY selected_model, task_type
    `).all() as TaskTypePerformance[];

    // Step 3: Upsert to model_task_performance
    let updatedModels = 0;
    for (const row of aggregates) {
      db.run(`
        INSERT INTO model_task_performance
          (model_id, task_type, sample_count, success_count, avg_quality, avg_latency_ms, avg_tps, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(model_id, task_type) DO UPDATE SET
          sample_count = excluded.sample_count,
          success_count = excluded.success_count,
          avg_quality = excluded.avg_quality,
          avg_latency_ms = excluded.avg_latency_ms,
          avg_tps = excluded.avg_tps,
          last_updated = datetime('now')
      `, [row.model_id, row.task_type, row.sample_count, row.success_count,
          row.avg_quality, row.avg_latency_ms, row.avg_tps]);
      updatedModels++;
    }

    return {
      processed,
      updated_models: updatedModels,
      performance_rows: aggregates,
      elapsed_ms: Date.now() - start
    };
  } finally {
    db.close();
  }
}

/**
 * 获取模型在特定任务类型上的推荐排序
 */
export function getModelRanking(taskType: string): Array<{
  model_id: string;
  avg_quality: number;
  sample_count: number;
  success_rate: number;
}> {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    return db.query(`
      SELECT
        model_id,
        avg_quality,
        sample_count,
        CASE WHEN sample_count > 0
          THEN CAST(success_count AS REAL) / sample_count
          ELSE 0
        END as success_rate
      FROM model_task_performance
      WHERE task_type = ?
      ORDER BY avg_quality DESC, sample_count DESC
    `).all(taskType) as any[];
  } finally {
    db.close();
  }
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const cmd = args[0] || 'run';

  if (cmd === '--help' || cmd === 'help') {
    console.log(`
Feedback Loop v2.0 — 反馈闭环引擎 (方案B 增强)

用法:
  bun feedback-loop.ts run [limit]     # 处理未评分的有 skill_id 的请求
  bun feedback-loop.ts dry [limit]     # 干跑，不写数据库
  bun feedback-loop.ts backfill [limit] # 回填所有请求的 quality_score
  bun feedback-loop.ts aggregate        # 方案B: 按 task_type 聚合 (推荐)
  bun feedback-loop.ts ranking <task>   # 查看特定任务类型的模型排名
  bun feedback-loop.ts stats           # 查看反馈闭环统计
`);
    process.exit(0);
  }

  if (cmd === 'stats') {
    const db = new Database(DB_PATH, { readonly: true });

    const total = (db.query('SELECT COUNT(*) as c FROM sroe_requests').get() as any).c;
    const withSkill = (db.query('SELECT COUNT(*) as c FROM sroe_requests WHERE skill_id IS NOT NULL AND skill_id != ""').get() as any).c;
    const withQuality = (db.query('SELECT COUNT(*) as c FROM sroe_requests WHERE quality_score IS NOT NULL').get() as any).c;
    const pendingFeedback = (db.query('SELECT COUNT(*) as c FROM sroe_requests WHERE skill_id IS NOT NULL AND skill_id != "" AND quality_score IS NULL').get() as any).c;

    const avgQuality = (db.query('SELECT AVG(quality_score) as avg FROM sroe_requests WHERE quality_score IS NOT NULL').get() as any).avg;

    const skillQuality = db.query(`
      SELECT skill_id, COUNT(*) as cnt, AVG(quality_score) as avg_q,
             MIN(quality_score) as min_q, MAX(quality_score) as max_q
      FROM sroe_requests
      WHERE skill_id IS NOT NULL AND skill_id != '' AND quality_score IS NOT NULL
      GROUP BY skill_id
      ORDER BY cnt DESC
    `).all() as any[];

    console.log(`\n📊 反馈闭环统计:`);
    console.log(`  总请求: ${total}`);
    console.log(`  有 skill_id: ${withSkill} (${(withSkill / total * 100).toFixed(1)}%)`);
    console.log(`  有 quality_score: ${withQuality} (${(withQuality / total * 100).toFixed(1)}%)`);
    console.log(`  待反馈: ${pendingFeedback}`);
    console.log(`  平均质量: ${avgQuality?.toFixed(4) || 'N/A'}`);

    if (skillQuality.length > 0) {
      console.log(`\n  按 Skill 分布:`);
      for (const row of skillQuality) {
        console.log(`    ${row.skill_id}: ${row.cnt}次, avg=${row.avg_q?.toFixed(3)}, range=[${row.min_q?.toFixed(2)}-${row.max_q?.toFixed(2)}]`);
      }
    }

    db.close();
    process.exit(0);
  }

  if (cmd === 'backfill') {
    const limit = parseInt(args[1] || '1000');
    console.log(`\n🔄 回填 quality_score (最多 ${limit} 条)...`);
    const result = backfillQualityScores(limit);
    console.log(`  处理: ${result.processed} 条 | 耗时: ${result.elapsed_ms}ms`);
    process.exit(0);
  }

  // 方案B: 按 task_type 聚合
  if (cmd === 'aggregate') {
    console.log(`\n🔄 方案B: 按 task_type + model 聚合反馈...`);
    const result = aggregateByTaskType(true);
    console.log(`  回填: ${result.processed} 条 | 更新: ${result.updated_models} 个模型-任务组合`);
    console.log(`  耗时: ${result.elapsed_ms}ms`);

    if (result.performance_rows.length > 0) {
      console.log(`\n📊 模型-任务表现 (Top 10):\n`);
      const sorted = [...result.performance_rows].sort((a, b) => b.avg_quality - a.avg_quality);
      for (const row of sorted.slice(0, 10)) {
        const successRate = row.sample_count > 0 ? (row.success_count / row.sample_count * 100).toFixed(0) : '0';
        console.log(`  [${row.task_type}] ${row.model_id}: ${row.sample_count}次, 质量=${row.avg_quality.toFixed(3)}, 成功率=${successRate}%`);
      }
    }
    process.exit(0);
  }

  if (cmd === 'aggregate') {
    console.log(`\n🔄 方案B: 按任务类型聚合反馈...`);
    const result = aggregateByTaskType(true);
    console.log(`  回填评分: ${result.processed} 条`);
    console.log(`  更新模型: ${result.updated_models} 个`);
    console.log(`  耗时: ${result.elapsed_ms}ms`);

    if (result.performance_rows.length > 0) {
      console.log(`\n  📊 模型表现排名 (按任务类型):`);
      const grouped = new Map<string, typeof result.performance_rows>();
      for (const row of result.performance_rows) {
        if (!grouped.has(row.task_type)) grouped.set(row.task_type, []);
        grouped.get(row.task_type)!.push(row);
      }
      for (const [taskType, rows] of grouped) {
        console.log(`\n  [${taskType}]`);
        for (const row of rows.slice(0, 5)) {
          const successRate = row.sample_count > 0 ? (row.success_count / row.sample_count * 100).toFixed(0) : '0';
          console.log(`    ${row.model_id}: ${row.sample_count}次, 质量=${row.avg_quality?.toFixed(3)}, 成功率=${successRate}%`);
        }
      }
    }
    process.exit(0);
  }

  if (cmd === 'ranking') {
    const taskType = args[1] || 'coding';
    console.log(`\n📊 模型排名 [${taskType}]:\n`);
    const ranking = getModelRanking(taskType);
    if (ranking.length === 0) {
      console.log(`  暂无数据，请先运行: bun feedback-loop.ts aggregate`);
    } else {
      for (const row of ranking) {
        console.log(`  ${row.model_id}: ${row.sample_count}次, 质量=${row.avg_quality.toFixed(3)}, 成功率=${(row.success_rate * 100).toFixed(0)}%`);
      }
    }
    process.exit(0);
  }

  // Default: run or dry
  const dryRun = cmd === 'dry';
  const limit = parseInt(args[1] || '100');

  console.log(`\n🔄 反馈闭环${dryRun ? ' (DRY RUN)' : ''} — 处理最多 ${limit} 条...`);

  const summary = processFeedbackLoop(limit, dryRun);

  console.log(`\n  处理: ${summary.processed} | 跳过: ${summary.skipped} | 错误: ${summary.errors}`);
  console.log(`  平均质量: ${summary.avg_quality}`);
  console.log(`  耗时: ${summary.elapsed_ms}ms`);

  if (summary.q_updates.length > 0) {
    console.log(`\n  Q-Value 更新:`);
    for (const u of summary.q_updates) {
      const direction = u.newQ > u.oldQ ? '↑' : u.newQ < u.oldQ ? '↓' : '→';
      console.log(`    ${u.skill_id}: ${u.oldQ.toFixed(4)} ${direction} ${u.newQ.toFixed(4)}`);
    }
  }

  if (dryRun && summary.results.length > 0) {
    console.log(`\n  前 5 条评估预览:`);
    for (const r of summary.results.slice(0, 5)) {
      console.log(`    [${r.quality.quality_score.toFixed(3)}] ${r.skill_id} — ${r.quality.reasoning}`);
    }
  }
}
