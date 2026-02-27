#!/usr/bin/env bun
/**
 * Execution Logger - 执行日志收集器
 *
 * 收集每次执行的详细信息，为 MemRL 训练准备数据
 *
 * @module execution-logger
 * @version 1.0.0
 * @created 2026-02-27
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';
import type { Plan, PlanStep } from './types';
import type { ExecutionReport, StepReport } from './plan-executor';

const DB_PATH = path.join(os.homedir(), '.solar', 'solar.db');

// ============ 类型定义 ============

export interface ExecutionLog {
  id: number;
  planId: string;
  sessionId: string;
  goal: string;
  constraints: string;
  planSteps: string;         // JSON
  executionSteps: string;    // JSON
  status: string;
  successRate: number;
  durationMs: number;
  replanCount: number;
  failurePatterns: string;   // JSON
  createdAt: number;
}

export interface TrainingSample {
  id: number;
  inputGoal: string;
  inputConstraints: string;
  outputPlan: string;        // JSON
  success: boolean;
  reward: number;            // 0-1，基于成功率
  createdAt: number;
}

export interface LogStats {
  totalLogs: number;
  successRate: number;
  avgDuration: number;
  avgSteps: number;
  samplesCollected: number;
}

// ============ 表结构 ============

const CREATE_LOGS_TABLE = `
CREATE TABLE IF NOT EXISTS plan_execution_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  goal TEXT NOT NULL,
  constraints TEXT DEFAULT '[]',
  plan_steps TEXT DEFAULT '[]',
  execution_steps TEXT DEFAULT '[]',
  status TEXT DEFAULT 'pending',
  success_rate REAL DEFAULT 0,
  duration_ms INTEGER DEFAULT 0,
  replan_count INTEGER DEFAULT 0,
  failure_patterns TEXT DEFAULT '[]',
  created_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_status ON plan_execution_logs(status);
CREATE INDEX IF NOT EXISTS idx_execution_logs_created ON plan_execution_logs(created_at);

CREATE TABLE IF NOT EXISTS memrl_training_samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  input_goal TEXT NOT NULL,
  input_constraints TEXT DEFAULT '[]',
  output_plan TEXT NOT NULL,
  success BOOLEAN DEFAULT false,
  reward REAL DEFAULT 0,
  created_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_training_samples_success ON memrl_training_samples(success);
CREATE INDEX IF NOT EXISTS idx_training_samples_reward ON memrl_training_samples(reward);
`;

// ============ 核心函数 ============

/**
 * 初始化日志表
 */
export function initExecutionLogger(): void {
  const db = new Database(DB_PATH);

  try {
    db.run(CREATE_LOGS_TABLE);
  } finally {
    db.close();
  }
}

/**
 * 记录执行日志
 *
 * @param plan - 计划对象
 * @param report - 执行报告
 * @param sessionId - 会话 ID
 */
export function logExecution(
  plan: Plan,
  report: ExecutionReport,
  sessionId: string
): number {
  const db = new Database(DB_PATH);

  try {
    // 提取失败模式
    const failurePatterns = extractFailurePatterns(report);

    const result = db.run(`
      INSERT INTO plan_execution_logs
      (plan_id, session_id, goal, constraints, plan_steps, execution_steps,
       status, success_rate, duration_ms, replan_count, failure_patterns)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
      plan.id,
      sessionId,
      plan.goal,
      JSON.stringify(plan.constraints),
      JSON.stringify(plan.steps.map(s => ({
        id: s.id,
        action: s.action,
        agent: s.agent,
        dependencies: s.dependencies
      }))),
      JSON.stringify(report.steps),
      report.status,
      report.totalSteps > 0 ? report.completedSteps / report.totalSteps : 0,
      report.durationMs,
      report.replanCount,
      JSON.stringify(failurePatterns)
    );

    const logId = result.lastInsertRowid;

    // 如果执行成功，创建训练样本
    if (report.status === 'success' || report.status === 'partial') {
      createTrainingSample(plan, report);
    }

    return logId as number;

  } finally {
    db.close();
  }
}

/**
 * 提取失败模式
 */
function extractFailurePatterns(report: ExecutionReport): string[] {
  const patterns: string[] = [];

  for (const step of report.steps) {
    if (step.status === 'failed' && step.error) {
      // 分类错误
      const error = step.error.toLowerCase();

      if (error.includes('permission') || error.includes('access denied')) {
        patterns.push('PERMISSION');
      } else if (error.includes('timeout') || error.includes('network')) {
        patterns.push('NETWORK');
      } else if (error.includes('type') || error.includes('undefined')) {
        patterns.push('LOGIC');
      } else {
        patterns.push('UNKNOWN');
      }
    }
  }

  return [...new Set(patterns)];
}

/**
 * 创建训练样本
 */
function createTrainingSample(plan: Plan, report: ExecutionReport): number {
  const db = new Database(DB_PATH);

  try {
    // 计算奖励（基于成功率）
    const reward = report.totalSteps > 0
      ? report.completedSteps / report.totalSteps
      : 0;

    const result = db.run(`
      INSERT INTO memrl_training_samples
      (input_goal, input_constraints, output_plan, success, reward)
      VALUES (?, ?, ?, ?, ?)
    `,
      plan.goal,
      JSON.stringify(plan.constraints),
      JSON.stringify({
        steps: plan.steps.map(s => ({
          action: s.action,
          agent: s.agent,
          dependencies: s.dependencies
        }))
      }),
      report.status === 'success',
      reward
    );

    return result.lastInsertRowid as number;

  } finally {
    db.close();
  }
}

/**
 * 获取训练样本
 *
 * @param limit - 返回数量
 * @param minReward - 最小奖励值
 * @returns 训练样本列表
 */
export function getTrainingSamples(
  limit: number = 100,
  minReward: number = 0.5
): TrainingSample[] {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT id, input_goal, input_constraints, output_plan, success, reward, created_at
      FROM memrl_training_samples
      WHERE reward >= ?
      ORDER BY reward DESC, created_at DESC
      LIMIT ?
    `);

    const results = stmt.all(minReward, limit) as TrainingSample[];
    stmt.finalize();

    return results;
  } finally {
    db.close();
  }
}

/**
 * 获取日志统计
 */
export function getLogStats(): LogStats {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    // 执行日志统计
    const logStmt = db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(success_rate) as avg_rate,
        AVG(duration_ms) as avg_duration
      FROM plan_execution_logs
    `);
    const logStats = logStmt.get() as {
      total: number;
      avg_rate: number;
      avg_duration: number;
    };
    logStmt.finalize();

    // 平均步骤数
    const stepsStmt = db.prepare(`
      SELECT AVG(json_array_length(plan_steps)) as avg_steps
      FROM plan_execution_logs
    `);
    const stepsStats = stepsStmt.get() as { avg_steps: number };
    stepsStmt.finalize();

    // 训练样本数
    const sampleStmt = db.prepare(`
      SELECT COUNT(*) as count FROM memrl_training_samples
    `);
    const sampleStats = sampleStmt.get() as { count: number };
    sampleStmt.finalize();

    return {
      totalLogs: logStats.total || 0,
      successRate: logStats.avg_rate || 0,
      avgDuration: Math.round(logStats.avg_duration || 0),
      avgSteps: Math.round(stepsStats.avg_steps || 0),
      samplesCollected: sampleStats.count || 0
    };

  } finally {
    db.close();
  }
}

/**
 * 导出训练数据
 *
 * @param format - 导出格式 ('json' | 'jsonl')
 * @returns 导出的数据
 */
export function exportTrainingData(format: 'json' | 'jsonl' = 'jsonl'): string {
  const samples = getTrainingSamples(1000, 0.3);

  if (format === 'json') {
    return JSON.stringify(samples, null, 2);
  }

  // JSONL 格式
  return samples.map(s => JSON.stringify({
    input: {
      goal: s.input_goal,
      constraints: JSON.parse(s.input_constraints)
    },
    output: JSON.parse(s.output_plan),
    reward: s.reward
  })).join('\n');
}

/**
 * 获取最近的执行日志
 */
export function getRecentLogs(limit: number = 20): ExecutionLog[] {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT id, plan_id, session_id, goal, constraints, plan_steps,
             execution_steps, status, success_rate, duration_ms,
             replan_count, failure_patterns, created_at
      FROM plan_execution_logs
      ORDER BY created_at DESC
      LIMIT ?
    `);

    const results = stmt.all(limit) as ExecutionLog[];
    stmt.finalize();

    return results;
  } finally {
    db.close();
  }
}

/**
 * 清理旧日志
 */
export function cleanupOldLogs(daysToKeep: number = 30): number {
  const db = new Database(DB_PATH);

  try {
    const cutoffSec = Math.floor(Date.now() / 1000) - daysToKeep * 24 * 60 * 60;

    // 只删除失败的日志，保留成功的作为训练数据
    const result = db.run(`
      DELETE FROM plan_execution_logs
      WHERE created_at < ? AND status = 'failed'
    `, cutoffSec);

    return result.changes;
  } finally {
    db.close();
  }
}

/**
 * 生成日志报告
 */
export function generateLogReport(): string {
  const stats = getLogStats();
  const recentLogs = getRecentLogs(5);

  const lines = [
    '╔═══════════════════════════════════════════════════════════════╗',
    '║              Plan-and-Act 执行日志统计                        ║',
    '╠═══════════════════════════════════════════════════════════════╣',
    `║  总执行次数: ${String(stats.totalLogs).padEnd(46)}║`,
    `║  平均成功率: ${(stats.successRate * 100).toFixed(1)}%`.padEnd(60) + '║',
    `║  平均耗时: ${(stats.avgDuration / 1000).toFixed(2)}s`.padEnd(57) + '║',
    `║  平均步骤: ${stats.avgSteps}`.padEnd(57) + '║',
    `║  训练样本: ${stats.samplesCollected}`.padEnd(57) + '║',
    '╚═══════════════════════════════════════════════════════════════╝',
    '',
    '最近 5 次执行:',
  ];

  for (const log of recentLogs) {
    const status = log.status === 'success' ? '✅' : log.status === 'partial' ? '⚠️' : '❌';
    lines.push(`  ${status} ${log.goal.slice(0, 40)} (${(log.success_rate * 100).toFixed(0)}%)`);
  }

  // MemRL 进度
  const memrlProgress = stats.samplesCollected / 100;
  const progressBar = '█'.repeat(Math.min(10, Math.floor(memrlProgress * 10))) +
                      '░'.repeat(10 - Math.min(10, Math.floor(memrlProgress * 10)));

  lines.push('');
  lines.push(`MemRL 训练数据进度: [${progressBar}] ${Math.min(100, memrlProgress * 100).toFixed(0)}%`);
  lines.push(`(目标: 100 样本，当前: ${stats.samplesCollected})`);

  return lines.join('\n');
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  // 初始化表
  initExecutionLogger();

  if (command === 'stats') {
    console.log('\n' + generateLogReport());

  } else if (command === 'export') {
    const format = (args[1] as 'json' | 'jsonl') || 'jsonl';
    const data = exportTrainingData(format);
    console.log(data);

  } else if (command === 'samples') {
    const limit = parseInt(args[1]) || 10;
    const samples = getTrainingSamples(limit);

    console.log(`\n=== 训练样本 (前 ${limit} 个) ===\n`);
    for (const s of samples) {
      console.log(`Reward: ${s.reward.toFixed(2)} | Goal: ${s.input_goal.slice(0, 40)}`);
    }

  } else if (command === 'cleanup') {
    const days = parseInt(args[1]) || 30;
    const deleted = cleanupOldLogs(days);
    console.log(`✅ 已清理 ${deleted} 条旧日志`);

  } else {
    console.log(`
Execution Logger CLI

Usage:
  bun execution-logger.ts stats           - 查看统计报告
  bun execution-logger.ts export [fmt]    - 导出训练数据
  bun execution-logger.ts samples [n]     - 查看训练样本
  bun execution-logger.ts cleanup [days]  - 清理旧日志
    `);
  }
}

export type { ExecutionLog, TrainingSample, LogStats };
