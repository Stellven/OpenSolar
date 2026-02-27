#!/usr/bin/env bun
/**
 * SMA L2 Plan Context - 计划状态存储
 *
 * 将计划状态持久化到 SMA L2 (session_log)
 *
 * @module plan-context
 * @version 1.0.0
 * @created 2026-02-27
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';
import type { Plan, PlanContext, PlanStep, PlanStepStatus } from './types';

const DB_PATH = path.join(os.homedir(), '.solar', 'solar.db');

// ============ Plan Context 操作 ============

/**
 * 保存计划上下文到 SMA L2
 *
 * @param sessionId - 会话 ID
 * @param context - 计划上下文
 */
export function savePlanContext(sessionId: string, context: PlanContext): void {
  const db = new Database(DB_PATH);

  try {
    const now = Math.floor(Date.now() / 1000);

    // 使用大的 turn_id 避免与正常对话冲突
    const turnId = 999900 + (context.replanCount || 0);

    db.run(`
      INSERT INTO session_log (session_id, turn_id, user_input, ai_output, timestamp)
      VALUES (?, ?, ?, ?, ?)
    `, sessionId, turnId, '[PLAN_CONTEXT]', JSON.stringify(context), now);
  } finally {
    db.close();
  }
}

/**
 * 从 SMA L2 加载计划上下文
 *
 * @param sessionId - 会话 ID
 * @returns 计划上下文，不存在则返回 null
 */
export function loadPlanContext(sessionId: string): PlanContext | null {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT ai_output
      FROM session_log
      WHERE session_id = ? AND user_input = '[PLAN_CONTEXT]'
      ORDER BY timestamp DESC
      LIMIT 1
    `);

    const result = stmt.get(sessionId) as { ai_output: string } | undefined;
    stmt.finalize();

    if (!result) return null;

    try {
      return JSON.parse(result.ai_output) as PlanContext;
    } catch {
      return null;
    }
  } finally {
    db.close();
  }
}

/**
 * 更新计划上下文
 *
 * @param sessionId - 会话 ID
 * @param updates - 要更新的字段
 */
export function updatePlanContext(
  sessionId: string,
  updates: Partial<PlanContext>
): void {
  const existing = loadPlanContext(sessionId);

  if (!existing) {
    throw new Error(`Plan context not found for session: ${sessionId}`);
  }

  const updated: PlanContext = {
    ...existing,
    ...updates,
    updatedAt: Date.now()
  };

  savePlanContext(sessionId, updated);
}

/**
 * 创建新的计划上下文
 *
 * @param sessionId - 会话 ID
 * @param planId - 计划 ID
 * @returns 新创建的计划上下文
 */
export function createPlanContext(sessionId: string, planId: string): PlanContext {
  const context: PlanContext = {
    currentPlanId: planId,
    activeSteps: [],
    completedSteps: [],
    failedSteps: [],
    replanCount: 0,
    sessionId,
    updatedAt: Date.now()
  };

  savePlanContext(sessionId, context);
  return context;
}

// ============ Plan 状态操作 ============

/**
 * 保存完整计划到 SMA L2
 *
 * @param sessionId - 会话 ID
 * @param plan - 计划对象
 */
export function savePlan(sessionId: string, plan: Plan): void {
  const db = new Database(DB_PATH);

  try {
    const now = Math.floor(Date.now() / 1000);

    // 使用大的 turn_id 避免与正常对话冲突
    const turnId = 999800 + Math.floor(Math.random() * 100);

    db.run(`
      INSERT INTO session_log (session_id, turn_id, user_input, ai_output, timestamp)
      VALUES (?, ?, ?, ?, ?)
    `, sessionId, turnId, `[PLAN:${plan.id}]`, JSON.stringify(plan), now);
  } finally {
    db.close();
  }
}

/**
 * 从 SMA L2 加载计划
 *
 * @param sessionId - 会话 ID
 * @param planId - 计划 ID
 * @returns 计划对象，不存在则返回 null
 */
export function loadPlan(sessionId: string, planId: string): Plan | null {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT ai_output
      FROM session_log
      WHERE session_id = ? AND user_input = ?
      ORDER BY timestamp DESC
      LIMIT 1
    `);

    const result = stmt.get(sessionId, `[PLAN:${planId}]`) as { ai_output: string } | undefined;
    stmt.finalize();

    if (!result) return null;

    try {
      return JSON.parse(result.ai_output) as Plan;
    } catch {
      return null;
    }
  } finally {
    db.close();
  }
}

/**
 * 更新计划中的步骤状态
 *
 * @param sessionId - 会话 ID
 * @param plan - 当前计划
 * @param stepId - 步骤 ID
 * @param status - 新状态
 * @param result - 可选的结果
 */
export function updateStepInStorage(
  sessionId: string,
  plan: Plan,
  stepId: string,
  status: PlanStepStatus,
  result?: unknown
): void {
  const now = Date.now();

  // 更新计划中的步骤
  const updatedSteps = plan.steps.map(step => {
    if (step.id !== stepId) return step;

    return {
      ...step,
      status,
      result: result !== undefined ? result : step.result,
      retryCount: status === 'failed' ? step.retryCount + 1 : step.retryCount,
      completedAt: status === 'completed' ? now : step.completedAt,
      startedAt: status === 'running' ? now : step.startedAt
    } as PlanStep;
  });

  const updatedPlan: Plan = {
    ...plan,
    steps: updatedSteps,
    updatedAt: now
  };

  // 保存更新后的计划
  savePlan(sessionId, updatedPlan);

  // 更新计划上下文
  const context = loadPlanContext(sessionId);
  if (context) {
    const contextUpdates: Partial<PlanContext> = {};

    if (status === 'completed') {
      contextUpdates.completedSteps = [...context.completedSteps, stepId];
      contextUpdates.activeSteps = context.activeSteps.filter(id => id !== stepId);
    } else if (status === 'failed') {
      contextUpdates.failedSteps = [...context.failedSteps, stepId];
      contextUpdates.activeSteps = context.activeSteps.filter(id => id !== stepId);
    } else if (status === 'running') {
      contextUpdates.activeSteps = [...context.activeSteps, stepId];
    }

    updatePlanContext(sessionId, contextUpdates);
  }
}

/**
 * 获取会话的所有计划历史
 *
 * @param sessionId - 会话 ID
 * @returns 计划 ID 列表
 */
export function listPlans(sessionId: string): string[] {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT DISTINCT user_input
      FROM session_log
      WHERE session_id = ? AND user_input LIKE '[PLAN:%'
      ORDER BY timestamp DESC
    `);

    const results = stmt.all(sessionId) as { user_input: string }[];
    stmt.finalize();

    return results.map(r => r.user_input.replace('[PLAN:', '').replace(']', ''));
  } finally {
    db.close();
  }
}

/**
 * 删除计划
 *
 * @param sessionId - 会话 ID
 * @param planId - 计划 ID
 */
export function deletePlan(sessionId: string, planId: string): void {
  const db = new Database(DB_PATH);

  try {
    db.run(`
      DELETE FROM session_log
      WHERE session_id = ? AND user_input = ?
    `, sessionId, `[PLAN:${planId}]`);
  } finally {
    db.close();
  }
}

// ============ 辅助函数 ============

/**
 * 获取步骤的执行历史
 *
 * @param sessionId - 会话 ID
 * @param stepId - 步骤 ID
 * @returns 执行记录列表
 */
export function getStepHistory(sessionId: string, stepId: string): Array<{
  timestamp: number;
  status: string;
  error?: string;
}> {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    const stmt = db.prepare(`
      SELECT timestamp, ai_output
      FROM session_log
      WHERE session_id = ? AND user_input LIKE '[STEP:${stepId}%'
      ORDER BY timestamp ASC
    `);

    const results = stmt.all(sessionId) as { timestamp: number; ai_output: string }[];
    stmt.finalize();

    return results.map(r => {
      try {
        const data = JSON.parse(r.ai_output);
        return {
          timestamp: r.timestamp,
          status: data.status,
          error: data.error
        };
      } catch {
        return { timestamp: r.timestamp, status: 'unknown' };
      }
    });
  } finally {
    db.close();
  }
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];
  const sessionId = args[1] || 'test-session';

  if (command === 'context') {
    console.log(`\n=== Plan Context: ${sessionId} ===\n`);
    const context = loadPlanContext(sessionId);

    if (context) {
      console.log(`Plan ID: ${context.currentPlanId}`);
      console.log(`Active: ${context.activeSteps.join(', ') || '无'}`);
      console.log(`Completed: ${context.completedSteps.join(', ') || '无'}`);
      console.log(`Failed: ${context.failedSteps.join(', ') || '无'}`);
      console.log(`Replan Count: ${context.replanCount}`);
    } else {
      console.log('No context found');
    }

  } else if (command === 'plans') {
    console.log(`\n=== Plans for: ${sessionId} ===\n`);
    const plans = listPlans(sessionId);

    if (plans.length > 0) {
      plans.forEach((id, i) => console.log(`${i + 1}. ${id}`));
    } else {
      console.log('No plans found');
    }

  } else if (command === 'show') {
    const planId = args[2];
    if (!planId) {
      console.error('Usage: bun plan-context.ts show <session_id> <plan_id>');
      process.exit(1);
    }

    console.log(`\n=== Plan: ${planId} ===\n`);
    const plan = loadPlan(sessionId, planId);

    if (plan) {
      console.log(`Goal: ${plan.goal}`);
      console.log(`Constraints: ${plan.constraints.join(', ') || '无'}`);
      console.log(`\nSteps (${plan.steps.length}):`);
      plan.steps.forEach((step, i) => {
        const statusIcon = {
          pending: '⏳',
          running: '🔄',
          completed: '✅',
          failed: '❌',
          skipped: '⏭️'
        }[step.status] || '❓';
        console.log(`  ${statusIcon} ${i + 1}. [${step.agent || '?'}] ${step.action}`);
      });
    } else {
      console.log('Plan not found');
    }

  } else {
    console.log(`
Plan Context CLI

Usage:
  bun plan-context.ts context <session_id>  - 查看计划上下文
  bun plan-context.ts plans <session_id>    - 列出所有计划
  bun plan-context.ts show <session_id> <plan_id>  - 查看计划详情
    `);
  }
}

export type { PlanContext, Plan };
