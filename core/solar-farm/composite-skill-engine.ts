/**
 * Composite Skill Engine
 *
 * 多步工作流封装为高阶技能，支持三种执行模式:
 * - sequential: 顺序管道 (如 InsightAgent: plan→write→review→synthesis)
 * - parallel:   MapReduce 并行 (如 多专家会审: 分发→并行分析→汇总)
 * - gated:      门控流程 (如 代码审查: 分析→检查→质量门→报告)
 *
 * 注意: 实际的 brain-router MCP 调用由 Solar 主脑发起，
 * 本模块只负责: 计划编排、阶段准备、检查点管理、Q-learning 反馈。
 *
 * Part of Step 4: Composite Skills
 * @version 1.0.0
 * @created 2026-02-24
 */

import Database from 'bun:sqlite';
import { homedir } from 'os';
import { join } from 'path';
import { buildNiumaCall } from './call-niuma';
import { matchPlaybooks, extractParamNames } from './playbook-matcher';

const DB_PATH = join(homedir(), '.solar', 'solar.db');

// ============================================================
// 类型定义
// ============================================================

export type WorkflowType = 'sequential' | 'parallel' | 'gated';
export type StageStatus = 'pending' | 'ready' | 'running' | 'done' | 'failed' | 'skipped';
export type ExecutionStatus = 'planned' | 'running' | 'paused' | 'completed' | 'failed';

export interface CompositeStage {
  stage_id: string;
  name: string;
  description: string;
  skill_id?: string;           // Optional link to sys_skill_bank playbook
  model_hint?: string;         // Preferred model (e.g. 'deepseek-r1')
  prompt_template: string;     // Template with {{params}} + {{prev_output}}
  input_from?: string[];       // stage_ids whose output feeds into this stage
  gate_condition?: string;     // For gated: 'quality>0.7' or 'all_done'
  timeout_ms?: number;
  max_retries?: number;
  parallel_group?: string;     // Stages in same group run concurrently
}

export interface CompositeSkill {
  composite_id: string;
  name: string;
  description: string;
  workflow_type: WorkflowType;
  stages: CompositeStage[];
  trigger_keywords: string[];
  q_value: number;
  success_count: number;
  failure_count: number;
  avg_total_time_ms: number;
  version: string;
}

export interface StageResult {
  stage_id: string;
  status: StageStatus;
  output: string;
  model_used: string;
  tokens_used: number;
  latency_ms: number;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

export interface CompositeExecution {
  execution_id: string;
  composite_id: string;
  status: ExecutionStatus;
  current_stage_id: string;
  stage_results: Record<string, StageResult>;
  input_params: Record<string, string>;
  started_at: string;
  updated_at: string;
  completed_at?: string;
  total_tokens: number;
  total_cost_usd: number;
}

/** What Solar gets back to know what to do next */
export interface NextStageAction {
  execution_id: string;
  composite_name: string;
  action: 'execute_stage' | 'execute_parallel' | 'check_gate' | 'complete' | 'failed';
  stage?: CompositeStage;
  parallel_stages?: CompositeStage[];
  call_params?: { model: string; system: string; prompt: string };
  parallel_call_params?: { model: string; system: string; prompt: string }[];
  progress: string;             // e.g. "3/5 stages done"
  is_complete: boolean;
}

// ============================================================
// Schema 初始化
// ============================================================

function ensureSchema(db: Database): void {
  db.run(`
    CREATE TABLE IF NOT EXISTS sys_composite_skills (
      composite_id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      workflow_type TEXT NOT NULL DEFAULT 'sequential',
      stages TEXT NOT NULL,           -- JSON array of CompositeStage
      trigger_keywords TEXT,          -- JSON array of strings
      q_value REAL DEFAULT 0.5,
      success_count INTEGER DEFAULT 0,
      failure_count INTEGER DEFAULT 0,
      avg_total_time_ms INTEGER DEFAULT 0,
      version TEXT DEFAULT '1.0.0',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS sys_composite_executions (
      execution_id TEXT PRIMARY KEY,
      composite_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'planned',
      current_stage_id TEXT,
      stage_results TEXT NOT NULL DEFAULT '{}',  -- JSON: Record<stage_id, StageResult>
      input_params TEXT NOT NULL DEFAULT '{}',   -- JSON: user-provided params
      started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      completed_at DATETIME,
      total_tokens INTEGER DEFAULT 0,
      total_cost_usd REAL DEFAULT 0,
      FOREIGN KEY (composite_id) REFERENCES sys_composite_skills(composite_id)
    )
  `);
}

// ============================================================
// 核心: 列出所有 Composite Skills
// ============================================================

export function listCompositeSkills(): CompositeSkill[] {
  const db = new Database(DB_PATH, { readonly: true });
  ensureSchema(db);
  try {
    const rows = db.query(`
      SELECT * FROM sys_composite_skills ORDER BY q_value DESC
    `).all() as any[];

    return rows.map(r => ({
      composite_id: r.composite_id,
      name: r.name,
      description: r.description,
      workflow_type: r.workflow_type as WorkflowType,
      stages: JSON.parse(r.stages || '[]'),
      trigger_keywords: JSON.parse(r.trigger_keywords || '[]'),
      q_value: r.q_value,
      success_count: r.success_count,
      failure_count: r.failure_count,
      avg_total_time_ms: r.avg_total_time_ms,
      version: r.version,
    }));
  } finally {
    db.close();
  }
}

// ============================================================
// 核心: 匹配意图到 Composite Skill
// ============================================================

export function matchComposite(intent: string): CompositeSkill | null {
  const db = new Database(DB_PATH, { readonly: true });
  ensureSchema(db);
  try {
    const skills = db.query(`
      SELECT * FROM sys_composite_skills
      ORDER BY q_value DESC
    `).all() as any[];

    let bestMatch: any = null;
    let bestScore = 0;

    // Phase 1: keyword matching (existing logic)
    for (const skill of skills) {
      let keywords: string[] = [];
      try { keywords = JSON.parse(skill.trigger_keywords || '[]'); } catch {}

      const intentLower = intent.toLowerCase();
      let matchCount = 0;
      for (const kw of keywords) {
        if (intentLower.includes(kw.toLowerCase())) matchCount++;
      }

      if (keywords.length > 0 && matchCount > 0) {
        const score = (matchCount / keywords.length) * 0.6 + (skill.q_value || 0.5) * 0.4;
        if (score > bestScore) {
          bestScore = score;
          bestMatch = skill;
        }
      }
    }

    // Phase 2: FTS5 fallback for composite matching
    if (!bestMatch) {
      try {
        const ftsRows = db.query(`
          SELECT doc_id, rank
          FROM fts_unified_search
          WHERE fts_unified_search MATCH ?
            AND doc_type = 'composite_skill'
          ORDER BY rank
          LIMIT 3
        `).all(intent) as any[];

        if (ftsRows.length > 0) {
          const matchedId = ftsRows[0].doc_id as string;
          bestMatch = skills.find(s => s.composite_id === matchedId);
        }
      } catch {
        // FTS5 might not have composite entries, that's ok
      }
    }

    if (!bestMatch) return null;

    let stages: CompositeStage[] = [];
    try { stages = JSON.parse(bestMatch.stages || '[]'); } catch {}
    let keywords: string[] = [];
    try { keywords = JSON.parse(bestMatch.trigger_keywords || '[]'); } catch {}

    return {
      composite_id: bestMatch.composite_id,
      name: bestMatch.name,
      description: bestMatch.description,
      workflow_type: bestMatch.workflow_type as WorkflowType,
      stages,
      trigger_keywords: keywords,
      q_value: bestMatch.q_value || 0.5,
      success_count: bestMatch.success_count || 0,
      failure_count: bestMatch.failure_count || 0,
      avg_total_time_ms: bestMatch.avg_total_time_ms || 0,
      version: bestMatch.version || '1.0.0',
    };
  } finally {
    db.close();
  }
}

// ============================================================
// 核心: 创建执行计划
// ============================================================

export function createExecution(
  compositeId: string,
  inputParams: Record<string, string>
): CompositeExecution {
  const db = new Database(DB_PATH);
  ensureSchema(db);
  try {
    const skill = db.query(`SELECT * FROM sys_composite_skills WHERE composite_id = ?`)
      .get(compositeId) as any;
    if (!skill) throw new Error(`Composite skill not found: ${compositeId}`);

    const stages: CompositeStage[] = JSON.parse(skill.stages || '[]');
    if (stages.length === 0) throw new Error(`No stages defined for: ${compositeId}`);

    const executionId = `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const firstStageId = stages[0].stage_id;

    // Initialize all stage results as pending
    const stageResults: Record<string, StageResult> = {};
    for (const s of stages) {
      stageResults[s.stage_id] = {
        stage_id: s.stage_id,
        status: 'pending',
        output: '',
        model_used: '',
        tokens_used: 0,
        latency_ms: 0,
      };
    }

    const now = new Date().toISOString();
    db.run(`
      INSERT INTO sys_composite_executions
      (execution_id, composite_id, status, current_stage_id, stage_results, input_params, started_at, updated_at)
      VALUES (?, ?, 'planned', ?, ?, ?, ?, ?)
    `, executionId, compositeId, firstStageId,
      JSON.stringify(stageResults), JSON.stringify(inputParams), now, now);

    return {
      execution_id: executionId,
      composite_id: compositeId,
      status: 'planned',
      current_stage_id: firstStageId,
      stage_results: stageResults,
      input_params: inputParams,
      started_at: now,
      updated_at: now,
      total_tokens: 0,
      total_cost_usd: 0,
    };
  } finally {
    db.close();
  }
}

// ============================================================
// 核心: 准备下一个阶段的调用参数
// ============================================================

export function prepareNextStage(executionId: string): NextStageAction {
  const db = new Database(DB_PATH);
  ensureSchema(db);
  try {
    const exec = db.query(`SELECT * FROM sys_composite_executions WHERE execution_id = ?`)
      .get(executionId) as any;
    if (!exec) throw new Error(`Execution not found: ${executionId}`);

    const skill = db.query(`SELECT * FROM sys_composite_skills WHERE composite_id = ?`)
      .get(exec.composite_id) as any;
    if (!skill) throw new Error(`Composite skill not found: ${exec.composite_id}`);

    const stages: CompositeStage[] = JSON.parse(skill.stages || '[]');
    const stageResults: Record<string, StageResult> = JSON.parse(exec.stage_results || '{}');
    const inputParams: Record<string, string> = JSON.parse(exec.input_params || '{}');
    const workflowType = skill.workflow_type as WorkflowType;

    const doneCount = Object.values(stageResults).filter(r => r.status === 'done').length;
    const progress = `${doneCount}/${stages.length} stages done`;

    // Find next actionable stage(s)
    const pendingStages = stages.filter(s => stageResults[s.stage_id]?.status === 'pending');

    if (pendingStages.length === 0) {
      // All stages done or failed
      const anyFailed = Object.values(stageResults).some(r => r.status === 'failed');
      return {
        execution_id: executionId,
        composite_name: skill.name,
        action: anyFailed ? 'failed' : 'complete',
        progress,
        is_complete: true,
      };
    }

    // ---- Sequential: take first pending stage ----
    if (workflowType === 'sequential') {
      const nextStage = pendingStages[0];

      // Check if dependencies are met
      if (nextStage.input_from && nextStage.input_from.length > 0) {
        const allDepsReady = nextStage.input_from.every(
          depId => stageResults[depId]?.status === 'done'
        );
        if (!allDepsReady) {
          return {
            execution_id: executionId,
            composite_name: skill.name,
            action: 'failed',
            progress,
            is_complete: true,
          };
        }
      }

      const prompt = buildStagePrompt(nextStage, stageResults, inputParams);
      const model = nextStage.model_hint || 'glm-5';
      const niumaResult = buildNiumaCall({
        model,
        task: prompt,
        context: `[Composite] ${skill.name} stage=${nextStage.name}`,
      });

      return {
        execution_id: executionId,
        composite_name: skill.name,
        action: 'execute_stage',
        stage: nextStage,
        call_params: { model: niumaResult.model, system: niumaResult.system, prompt: niumaResult.prompt },
        progress,
        is_complete: false,
      };
    }

    // ---- Parallel: group by parallel_group, execute group together ----
    if (workflowType === 'parallel') {
      // Find the first parallel_group that has all pending stages
      const groups = new Map<string, CompositeStage[]>();
      for (const s of pendingStages) {
        const group = s.parallel_group || s.stage_id;
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group)!.push(s);
      }

      const [, groupStages] = [...groups.entries()][0];

      // Check if all dependencies met for this group
      const allDepsReady = groupStages.every(s =>
        !s.input_from || s.input_from.every(depId => stageResults[depId]?.status === 'done')
      );
      if (!allDepsReady) {
        return {
          execution_id: executionId,
          composite_name: skill.name,
          action: 'failed',
          progress,
          is_complete: true,
        };
      }

      if (groupStages.length === 1) {
        const stage = groupStages[0];
        const prompt = buildStagePrompt(stage, stageResults, inputParams);
        const model = stage.model_hint || 'glm-5';
        const niumaResult = buildNiumaCall({ model, task: prompt, context: `[Composite] ${skill.name} stage=${stage.name}` });
        return {
          execution_id: executionId,
          composite_name: skill.name,
          action: 'execute_stage',
          stage,
          call_params: { model: niumaResult.model, system: niumaResult.system, prompt: niumaResult.prompt },
          progress,
          is_complete: false,
        };
      }

      // Multiple stages in parallel
      const parallelParams = groupStages.map(stage => {
        const prompt = buildStagePrompt(stage, stageResults, inputParams);
        const model = stage.model_hint || 'glm-5';
        const r = buildNiumaCall({ model, task: prompt, context: `[Composite] ${skill.name} stage=${stage.name}` });
        return { model: r.model, system: r.system, prompt: r.prompt };
      });

      return {
        execution_id: executionId,
        composite_name: skill.name,
        action: 'execute_parallel',
        parallel_stages: groupStages,
        parallel_call_params: parallelParams,
        progress,
        is_complete: false,
      };
    }

    // ---- Gated: check gate condition before proceeding ----
    if (workflowType === 'gated') {
      const nextStage = pendingStages[0];

      // Check gate condition if it exists
      if (nextStage.gate_condition) {
        const gateResult = evaluateGate(nextStage.gate_condition, stageResults);
        if (!gateResult.passed) {
          return {
            execution_id: executionId,
            composite_name: skill.name,
            action: 'check_gate',
            stage: nextStage,
            progress: `${progress} | GATE BLOCKED: ${gateResult.reason}`,
            is_complete: false,
          };
        }
      }

      const prompt = buildStagePrompt(nextStage, stageResults, inputParams);
      const model = nextStage.model_hint || 'glm-5';
      const niumaResult = buildNiumaCall({ model, task: prompt, context: `[Composite] ${skill.name} stage=${nextStage.name}` });

      return {
        execution_id: executionId,
        composite_name: skill.name,
        action: 'execute_stage',
        stage: nextStage,
        call_params: { model: niumaResult.model, system: niumaResult.system, prompt: niumaResult.prompt },
        progress,
        is_complete: false,
      };
    }

    // Fallback
    return {
      execution_id: executionId,
      composite_name: skill.name,
      action: 'complete',
      progress,
      is_complete: true,
    };
  } finally {
    db.close();
  }
}

// ============================================================
// 核心: 记录阶段结果并推进
// ============================================================

export function advanceStage(
  executionId: string,
  stageId: string,
  output: string,
  success: boolean,
  meta?: { model?: string; tokens?: number; latencyMs?: number; costUsd?: number }
): void {
  const db = new Database(DB_PATH);
  ensureSchema(db);
  try {
    const exec = db.query(`SELECT * FROM sys_composite_executions WHERE execution_id = ?`)
      .get(executionId) as any;
    if (!exec) throw new Error(`Execution not found: ${executionId}`);

    // Validate stage_id exists in composite definition
    const skillDef = db.query(`SELECT stages FROM sys_composite_skills WHERE composite_id = ?`)
      .get(exec.composite_id) as any;
    const definedStages: CompositeStage[] = JSON.parse(skillDef?.stages || '[]');
    const validStageIds = definedStages.map(s => s.stage_id);
    if (!validStageIds.includes(stageId)) {
      throw new Error(`Invalid stage_id "${stageId}". Valid: ${validStageIds.join(', ')}`);
    }

    const stageResults: Record<string, StageResult> = JSON.parse(exec.stage_results || '{}');
    const now = new Date().toISOString();

    stageResults[stageId] = {
      stage_id: stageId,
      status: success ? 'done' : 'failed',
      output: output,
      model_used: meta?.model || '',
      tokens_used: meta?.tokens || 0,
      latency_ms: meta?.latencyMs || 0,
      error: success ? undefined : output,
      started_at: stageResults[stageId]?.started_at || now,
      completed_at: now,
    };

    // Calculate totals
    let totalTokens = 0;
    let totalCost = 0;
    for (const r of Object.values(stageResults)) {
      totalTokens += r.tokens_used;
    }
    totalCost = (meta?.costUsd || 0) + (exec.total_cost_usd || 0);

    // Find next pending stage
    const skill = db.query(`SELECT stages FROM sys_composite_skills WHERE composite_id = ?`)
      .get(exec.composite_id) as any;
    const stages: CompositeStage[] = JSON.parse(skill?.stages || '[]');
    const nextPending = stages.find(s => stageResults[s.stage_id]?.status === 'pending');

    const allDone = !nextPending;
    const anyFailed = Object.values(stageResults).some(r => r.status === 'failed');
    const newStatus = allDone ? (anyFailed ? 'failed' : 'completed') : 'running';

    db.run(`
      UPDATE sys_composite_executions
      SET stage_results = ?, current_stage_id = ?, status = ?,
          total_tokens = ?, total_cost_usd = ?, updated_at = ?,
          completed_at = ?
      WHERE execution_id = ?
    `,
      JSON.stringify(stageResults),
      nextPending?.stage_id || stageId,
      newStatus,
      totalTokens,
      totalCost,
      now,
      allDone ? now : null,
      executionId
    );

    // Phase 3: Write skill_id to sroe_requests for traceability
    const stage = stages.find(s => s.stage_id === stageId);
    if (stage?.skill_id) {
      try {
        db.run(`
          INSERT INTO sroe_requests (request_id, task_type, skill_id, context_tags, selected_model, finish_reason, created_at)
          VALUES (?, 'composite_stage', ?, ?, ?, ?, datetime('now'))
        `,
          `comp_${executionId}_${stageId}`,
          stage.skill_id,
          JSON.stringify([exec.composite_id, stageId]),
          stageResults[stageId]?.model_used || 'unknown',
          success ? 'stop' : 'error'
        );
      } catch { /* sroe_requests write is best-effort */ }
    }

    // If completed, update q_value on the composite skill
    if (allDone) {
      const allSuccess = !anyFailed;
      updateCompositeQValue(exec.composite_id, allSuccess, db);
    }
  } finally {
    db.close();
  }
}

// ============================================================
// Q-learning 反馈
// ============================================================

function updateCompositeQValue(compositeId: string, success: boolean, db: Database): void {
  const skill = db.query(`SELECT q_value, success_count, failure_count FROM sys_composite_skills WHERE composite_id = ?`)
    .get(compositeId) as any;
  if (!skill) return;

  const alpha = 0.1;
  const reward = success ? 1.0 : 0.0;
  const oldQ = skill.q_value || 0.5;
  const newQ = oldQ + alpha * (reward - oldQ);

  db.run(`
    UPDATE sys_composite_skills
    SET q_value = ?, success_count = success_count + ?, failure_count = failure_count + ?,
        updated_at = datetime('now')
    WHERE composite_id = ?
  `, newQ, success ? 1 : 0, success ? 0 : 1, compositeId);
}

// ============================================================
// 辅助函数
// ============================================================

function buildStagePrompt(
  stage: CompositeStage,
  stageResults: Record<string, StageResult>,
  inputParams: Record<string, string>
): string {
  let prompt = stage.prompt_template;

  // --- Playbook enrichment (Phase 3 串联) ---
  // If stage has a skill_id, look up its playbook template as supplementary context
  if (stage.skill_id) {
    try {
      const pbMatches = matchPlaybooks(stage.skill_id, 1);
      if (pbMatches.matches.length > 0) {
        const pb = pbMatches.matches[0];
        // Append playbook guidance as supplementary instructions
        prompt += `\n\n[Playbook 参考 - ${pb.name}]\n${pb.llm_prompt_template}`;
      }
    } catch { /* playbook lookup optional */ }
  }
  // If no skill_id but stage description is rich enough, try auto-matching
  else if (stage.description && stage.description.length > 10) {
    try {
      const pbMatches = matchPlaybooks(stage.description, 1);
      if (pbMatches.matches.length > 0 && pbMatches.matches[0].match_score > 0.4) {
        const pb = pbMatches.matches[0];
        prompt += `\n\n[Playbook 参考 - ${pb.name}]\n${pb.llm_prompt_template}`;
      }
    } catch { /* auto-match optional */ }
  }

  // Fill {{param}} from inputParams
  for (const [key, value] of Object.entries(inputParams)) {
    prompt = prompt.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value);
  }

  // Fill {{prev_output}} from previous stage results
  if (stage.input_from && stage.input_from.length > 0) {
    const prevOutputs = stage.input_from
      .map(depId => stageResults[depId]?.output || '')
      .filter(o => o.length > 0)
      .join('\n\n---\n\n');
    prompt = prompt.replace(/\{\{prev_output\}\}/g, prevOutputs);
  }

  // Fill {{all_outputs}} with all completed stage outputs
  const allOutputs = Object.values(stageResults)
    .filter(r => r.status === 'done' && r.output)
    .map(r => `[${r.stage_id}]\n${r.output}`)
    .join('\n\n---\n\n');
  prompt = prompt.replace(/\{\{all_outputs\}\}/g, allOutputs);

  return prompt;
}

function evaluateGate(
  condition: string,
  stageResults: Record<string, StageResult>
): { passed: boolean; reason: string } {
  // Simple gate evaluation: 'all_done', 'any_done', 'no_failures'
  if (condition === 'all_done') {
    const allDone = Object.values(stageResults).every(
      r => r.status === 'done' || r.status === 'pending'
    );
    return { passed: allDone, reason: allDone ? '' : 'Not all prerequisite stages are done' };
  }
  if (condition === 'no_failures') {
    const noFail = !Object.values(stageResults).some(r => r.status === 'failed');
    return { passed: noFail, reason: noFail ? '' : 'One or more stages failed' };
  }
  // Default: pass through
  return { passed: true, reason: '' };
}

// ============================================================
// 查询执行状态
// ============================================================

export function getExecutionStatus(executionId: string): CompositeExecution | null {
  const db = new Database(DB_PATH, { readonly: true });
  ensureSchema(db);
  try {
    const exec = db.query(`SELECT * FROM sys_composite_executions WHERE execution_id = ?`)
      .get(executionId) as any;
    if (!exec) return null;

    return {
      execution_id: exec.execution_id,
      composite_id: exec.composite_id,
      status: exec.status as ExecutionStatus,
      current_stage_id: exec.current_stage_id,
      stage_results: JSON.parse(exec.stage_results || '{}'),
      input_params: JSON.parse(exec.input_params || '{}'),
      started_at: exec.started_at,
      updated_at: exec.updated_at,
      completed_at: exec.completed_at,
      total_tokens: exec.total_tokens,
      total_cost_usd: exec.total_cost_usd,
    };
  } finally {
    db.close();
  }
}

// ============================================================
// Seed: 预置 5 个高频 Composite Skills
// ============================================================

export function seedCompositeSkills(): number {
  const db = new Database(DB_PATH);
  ensureSchema(db);
  try {
    const seeds: Array<{
      composite_id: string; name: string; description: string;
      workflow_type: WorkflowType; stages: CompositeStage[];
      trigger_keywords: string[];
    }> = [
      // ---- 1. 深度洞察分析 (Sequential) ----
      {
        composite_id: 'comp_deep_insight',
        name: '深度洞察分析',
        description: '多阶段深度研究：规划→多专家分析→综合→精炼',
        workflow_type: 'sequential',
        trigger_keywords: ['深度洞察', '洞察分析', '深入分析', '研究报告', 'insight'],
        stages: [
          {
            stage_id: 'plan',
            name: '研究规划',
            description: '制定研究大纲和章节分配',
            model_hint: 'gemini-3-pro-preview',
            prompt_template: '你是研究规划专家。针对主题"{{topic}}"，制定一个3-5章的研究大纲。\n每章包含：标题、核心问题、建议研究角度。\n输出JSON格式：{chapters: [{title, question, angle}]}',
          },
          {
            stage_id: 'research',
            name: '多角度分析',
            description: '基于大纲进行深度分析',
            model_hint: 'deepseek-r1',
            input_from: ['plan'],
            prompt_template: '基于以下研究大纲，对"{{topic}}"进行深度分析。\n\n研究大纲:\n{{prev_output}}\n\n要求：逐章分析，每章800-1200字，引用具体论据。',
          },
          {
            stage_id: 'synthesis',
            name: '综合结论',
            description: '汇总分析形成结论',
            model_hint: 'gemini-2.5-pro',
            input_from: ['research'],
            prompt_template: '基于以下多角度分析结果，生成综合结论报告。\n\n分析内容:\n{{prev_output}}\n\n要求：提炼核心发现(3-5条)、行动建议(2-3条)、风险提示(1-2条)。',
          },
        ],
      },

      // ---- 2. 专家会审 (Parallel) ----
      {
        composite_id: 'comp_expert_review',
        name: '专家会审',
        description: '多专家并行分析→综合意见',
        workflow_type: 'parallel',
        trigger_keywords: ['专家会审', '多专家', '会审', '集思广益', '多角度审查'],
        stages: [
          {
            stage_id: 'expert_1',
            name: '稳健派分析',
            description: '严谨架构审查视角',
            model_hint: 'gemini-2.5-pro',
            parallel_group: 'experts',
            prompt_template: '作为严谨的架构审查专家，分析以下内容：\n\n{{content}}\n\n重点关注：可靠性、一致性、潜在风险。输出结构化评审意见。',
          },
          {
            stage_id: 'expert_2',
            name: '审判官分析',
            description: '深度推理和质疑视角',
            model_hint: 'deepseek-r1',
            parallel_group: 'experts',
            prompt_template: '作为深度推理专家，分析以下内容：\n\n{{content}}\n\n重点关注：逻辑漏洞、隐含假设、反例。输出结构化评审意见。',
          },
          {
            stage_id: 'expert_3',
            name: '探索派分析',
            description: '创新方案和替代视角',
            model_hint: 'gemini-3-pro-preview',
            parallel_group: 'experts',
            prompt_template: '作为创新探索专家，分析以下内容：\n\n{{content}}\n\n重点关注：替代方案、创新机会、行业前沿对比。输出结构化评审意见。',
          },
          {
            stage_id: 'synthesize',
            name: '综合意见',
            description: '汇总三位专家意见',
            model_hint: 'gemini-2.5-pro',
            input_from: ['expert_1', 'expert_2', 'expert_3'],
            prompt_template: '三位专家的分析意见如下，请综合汇总：\n\n{{prev_output}}\n\n要求：\n1. 共识点(所有专家一致)\n2. 分歧点(专家间不同)\n3. 行动建议(综合最优)\n4. 风险清单',
          },
        ],
      },

      // ---- 3. 代码审查流程 (Gated) ----
      {
        composite_id: 'comp_code_review',
        name: '代码审查流程',
        description: '静态分析→安全检查→质量门→改进建议',
        workflow_type: 'gated',
        trigger_keywords: ['代码审查', 'code review', '审查代码', '代码检查'],
        stages: [
          {
            stage_id: 'static_analysis',
            name: '静态分析',
            description: '代码结构、风格、潜在bug',
            model_hint: 'gemini-2.5-pro',
            prompt_template: '对以下代码进行静态分析：\n\n```\n{{code}}\n```\n\n检查点：命名规范、代码结构、潜在bug、类型安全。\n输出JSON：{issues: [{severity, line, message}], score: 0-100}',
          },
          {
            stage_id: 'security_check',
            name: '安全检查',
            description: 'OWASP安全审查',
            model_hint: 'deepseek-r1',
            prompt_template: '对以下代码进行安全审查(OWASP Top 10)：\n\n```\n{{code}}\n```\n\n检查：注入、XSS、敏感数据泄露、认证绕过等。\n输出JSON：{vulnerabilities: [{severity, type, location, fix}], secure_score: 0-100}',
          },
          {
            stage_id: 'quality_gate',
            name: '质量门',
            description: '基于前两阶段结果决定是否通过',
            model_hint: 'glm-5',
            gate_condition: 'no_failures',
            input_from: ['static_analysis', 'security_check'],
            prompt_template: '基于静态分析和安全检查结果，判断代码是否通过质量门：\n\n{{prev_output}}\n\n输出：PASS/FAIL + 理由 + 必须修复的问题清单',
          },
          {
            stage_id: 'improvement',
            name: '改进建议',
            description: '生成具体改进代码',
            model_hint: 'deepseek-v3',
            input_from: ['static_analysis', 'security_check', 'quality_gate'],
            prompt_template: '基于以下审查结果，生成具体的代码改进建议：\n\n{{prev_output}}\n\n要求：给出具体的修改diff，优先修复严重问题。',
          },
        ],
      },

      // ---- 4. 架构设计 (Sequential) ----
      {
        composite_id: 'comp_arch_design',
        name: '架构设计',
        description: '需求分析→方案设计→专家评审→最终方案',
        workflow_type: 'sequential',
        trigger_keywords: ['架构设计', '系统设计', '方案设计', 'architecture'],
        stages: [
          {
            stage_id: 'requirements',
            name: '需求分析',
            description: '梳理功能和非功能需求',
            model_hint: 'gemini-3-pro-preview',
            prompt_template: '分析以下需求，输出结构化需求文档：\n\n{{requirement}}\n\n包含：功能需求(FR)、非功能需求(NFR)、约束条件、假设、风险。',
          },
          {
            stage_id: 'design',
            name: '方案设计',
            description: '设计2-3个候选方案',
            model_hint: 'deepseek-v3',
            input_from: ['requirements'],
            prompt_template: '基于以下需求，设计2-3个候选架构方案：\n\n{{prev_output}}\n\n每个方案包含：架构图(ASCII)、技术栈、优缺点、ROI评估。',
          },
          {
            stage_id: 'review',
            name: '方案评审',
            description: '审判官评审方案风险',
            model_hint: 'deepseek-r1',
            input_from: ['design'],
            prompt_template: '作为技术评审专家，审查以下架构方案：\n\n{{prev_output}}\n\n重点评估：可扩展性、可维护性、安全性、成本。\n推荐最优方案并说明理由。',
          },
          {
            stage_id: 'final',
            name: '最终方案',
            description: '综合评审意见出最终设计',
            model_hint: 'gemini-2.5-pro',
            input_from: ['design', 'review'],
            prompt_template: '基于方案设计和评审意见，输出最终架构设计文档：\n\n{{prev_output}}\n\n包含：最终方案、实施路线图、风险缓解措施、验收标准。',
          },
        ],
      },

      // ---- 5. 系统诊断 (Sequential) ----
      {
        composite_id: 'comp_diagnosis',
        name: '系统诊断',
        description: '症状收集→根因分析→修复方案→验证计划',
        workflow_type: 'sequential',
        trigger_keywords: ['诊断', '系统诊断', '排查', 'diagnosis', '故障分析'],
        stages: [
          {
            stage_id: 'symptom',
            name: '症状收集',
            description: '结构化收集问题症状',
            model_hint: 'glm-5',
            prompt_template: '分析以下问题描述，结构化提取症状：\n\n{{problem}}\n\n输出：症状列表、触发条件、影响范围、严重程度。',
          },
          {
            stage_id: 'root_cause',
            name: '根因分析',
            description: '深度推理找根因',
            model_hint: 'deepseek-r1',
            input_from: ['symptom'],
            prompt_template: '基于以下症状分析，进行根因推理：\n\n{{prev_output}}\n\n使用5-Why方法，找出根本原因。输出：根因假设(至少2个)、证据链、排除项。',
          },
          {
            stage_id: 'fix_plan',
            name: '修复方案',
            description: '针对根因设计修复方案',
            model_hint: 'deepseek-v3',
            input_from: ['root_cause'],
            prompt_template: '基于根因分析，设计修复方案：\n\n{{prev_output}}\n\n每个根因假设对应一个修复方案。包含：修改点、风险评估、回滚方案。',
          },
          {
            stage_id: 'verify',
            name: '验证计划',
            description: '设计验证测试',
            model_hint: 'gemini-2.5-pro',
            input_from: ['fix_plan'],
            prompt_template: '设计验证计划确认修复有效：\n\n{{prev_output}}\n\n包含：测试用例、预期结果、回归检查项。',
          },
        ],
      },
    ];

    let inserted = 0;
    for (const s of seeds) {
      const existing = db.query(`SELECT composite_id FROM sys_composite_skills WHERE composite_id = ?`)
        .get(s.composite_id);
      if (!existing) {
        db.run(`
          INSERT INTO sys_composite_skills
          (composite_id, name, description, workflow_type, stages, trigger_keywords, q_value)
          VALUES (?, ?, ?, ?, ?, ?, 0.5)
        `, s.composite_id, s.name, s.description, s.workflow_type,
          JSON.stringify(s.stages), JSON.stringify(s.trigger_keywords));
        inserted++;
      }
    }
    return inserted;
  } finally {
    db.close();
  }
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '--help') {
    console.log(`
Composite Skill Engine v1.0

用法:
  bun composite-skill-engine.ts list                         # 列出所有 composite skills
  bun composite-skill-engine.ts match <intent>               # 意图匹配
  bun composite-skill-engine.ts plan <composite_id> [params]  # 创建执行计划
  bun composite-skill-engine.ts next <execution_id>           # 准备下一阶段
  bun composite-skill-engine.ts advance <exec_id> <stage_id> <0|1> [output]  # 推进阶段
  bun composite-skill-engine.ts status <execution_id>         # 查看执行状态
  bun composite-skill-engine.ts seed                          # 预置 5 个高频 workflow
  bun composite-skill-engine.ts stats                         # 统计信息

示例:
  bun composite-skill-engine.ts seed
  bun composite-skill-engine.ts match "帮我做个深度洞察分析"
  bun composite-skill-engine.ts plan comp_deep_insight '{"topic":"AI Agent记忆机制"}'
  bun composite-skill-engine.ts next exec_1234_abc
  bun composite-skill-engine.ts advance exec_1234_abc plan 1 "研究大纲..."
`);
    process.exit(0);
  }

  // ---- list ----
  if (command === 'list') {
    const skills = listCompositeSkills();
    console.log(`\n📦 Composite Skills (${skills.length} 个):\n`);
    for (const s of skills) {
      const stageNames = s.stages.map(st => st.name).join(' → ');
      console.log(`  [${s.workflow_type}] ${s.name} (${s.composite_id})`);
      console.log(`    q=${s.q_value.toFixed(3)} | 成功=${s.success_count} 失败=${s.failure_count}`);
      console.log(`    阶段: ${stageNames}`);
      console.log(`    关键词: ${s.trigger_keywords.join(', ')}`);
      console.log();
    }
    process.exit(0);
  }

  // ---- match ----
  if (command === 'match') {
    const intent = args.slice(1).join(' ');
    if (!intent) { console.error('需要 <intent> 参数'); process.exit(1); }
    const match = matchComposite(intent);
    if (match) {
      console.log(`\n🎯 匹配: ${match.name} (${match.composite_id})`);
      console.log(`   类型: ${match.workflow_type} | q=${match.q_value.toFixed(3)}`);
      console.log(`   阶段: ${match.stages.map(s => s.name).join(' → ')}`);
    } else {
      console.log(`\n❌ 无匹配 composite skill`);
    }
    process.exit(0);
  }

  // ---- seed ----
  if (command === 'seed') {
    const count = seedCompositeSkills();
    console.log(`\n🌱 预置完成: 新增 ${count} 个 composite skills`);
    const skills = listCompositeSkills();
    console.log(`   总计: ${skills.length} 个\n`);
    for (const s of skills) {
      console.log(`   ✅ ${s.name} (${s.workflow_type}, ${s.stages.length} stages)`);
    }
    console.log();
    process.exit(0);
  }

  // ---- plan ----
  if (command === 'plan') {
    const compositeId = args[1];
    const paramsJson = args[2] || '{}';
    if (!compositeId) { console.error('需要 <composite_id>'); process.exit(1); }
    let params: Record<string, string>;
    try { params = JSON.parse(paramsJson); } catch { params = {}; }

    const exec = createExecution(compositeId, params);
    console.log(`\n📋 执行计划已创建:`);
    console.log(`   execution_id: ${exec.execution_id}`);
    console.log(`   composite_id: ${exec.composite_id}`);
    console.log(`   状态: ${exec.status}`);
    console.log(`   首阶段: ${exec.current_stage_id}`);
    console.log(`\n   下一步: bun composite-skill-engine.ts next ${exec.execution_id}\n`);
    process.exit(0);
  }

  // ---- next ----
  if (command === 'next') {
    const executionId = args[1];
    if (!executionId) { console.error('需要 <execution_id>'); process.exit(1); }

    const action = prepareNextStage(executionId);
    console.log(`\n🔄 下一步 [${action.composite_name}]:`);
    console.log(`   进度: ${action.progress}`);
    console.log(`   动作: ${action.action}`);

    if (action.action === 'execute_stage' && action.call_params) {
      console.log(`   阶段: ${action.stage?.name}`);
      console.log(`   模型: ${action.call_params.model}`);
      console.log(`   System (前100): ${action.call_params.system.substring(0, 100)}...`);
      console.log(`   Prompt (前200): ${action.call_params.prompt.substring(0, 200)}...`);
    } else if (action.action === 'execute_parallel' && action.parallel_call_params) {
      console.log(`   并行阶段: ${action.parallel_stages?.map(s => s.name).join(', ')}`);
      for (let i = 0; i < action.parallel_call_params.length; i++) {
        console.log(`   [${i}] 模型: ${action.parallel_call_params[i].model}`);
      }
    } else if (action.action === 'complete') {
      console.log(`   ✅ 所有阶段完成！`);
    } else if (action.action === 'failed') {
      console.log(`   ❌ 执行失败`);
    }
    console.log();
    process.exit(0);
  }

  // ---- advance ----
  if (command === 'advance') {
    const executionId = args[1];
    const stageId = args[2];
    const success = args[3] === '1';
    const output = args.slice(4).join(' ') || '(no output)';

    if (!executionId || !stageId || !args[3]) {
      console.error('用法: advance <exec_id> <stage_id> <0|1> [output]');
      process.exit(1);
    }

    advanceStage(executionId, stageId, output, success);
    console.log(`\n📝 阶段 ${stageId} 已记录: ${success ? '✅ 成功' : '❌ 失败'}`);

    // Show next action
    const nextAction = prepareNextStage(executionId);
    console.log(`   下一步: ${nextAction.action} (${nextAction.progress})\n`);
    process.exit(0);
  }

  // ---- status ----
  if (command === 'status') {
    const executionId = args[1];
    if (!executionId) { console.error('需要 <execution_id>'); process.exit(1); }

    const exec = getExecutionStatus(executionId);
    if (!exec) { console.error('找不到执行记录'); process.exit(1); }

    console.log(`\n📊 执行状态: ${exec.execution_id}`);
    console.log(`   Composite: ${exec.composite_id}`);
    console.log(`   状态: ${exec.status}`);
    console.log(`   当前阶段: ${exec.current_stage_id}`);
    console.log(`   总Token: ${exec.total_tokens}`);
    console.log(`   总成本: $${exec.total_cost_usd.toFixed(4)}`);
    console.log(`\n   阶段详情:`);
    for (const [id, result] of Object.entries(exec.stage_results)) {
      const icon = result.status === 'done' ? '✅' : result.status === 'failed' ? '❌' : '⏳';
      console.log(`   ${icon} ${id}: ${result.status} ${result.model_used ? `(${result.model_used})` : ''}`);
      if (result.output) {
        console.log(`      输出: ${result.output.substring(0, 80)}...`);
      }
    }
    console.log();
    process.exit(0);
  }

  // ---- stats ----
  if (command === 'stats') {
    const db = new Database(DB_PATH, { readonly: true });
    ensureSchema(db);
    try {
      const total = (db.query('SELECT COUNT(*) as c FROM sys_composite_skills').get() as any).c;
      const byType = db.query(`
        SELECT workflow_type, COUNT(*) as c, AVG(q_value) as avg_q
        FROM sys_composite_skills GROUP BY workflow_type
      `).all() as any[];
      const execCount = (db.query('SELECT COUNT(*) as c FROM sys_composite_executions').get() as any).c;
      const completed = (db.query(`SELECT COUNT(*) as c FROM sys_composite_executions WHERE status='completed'`).get() as any).c;

      console.log(`\n📊 Composite Skills 统计:`);
      console.log(`   总数: ${total}`);
      for (const t of byType) {
        console.log(`   ${t.workflow_type}: ${t.c} 个, 平均q=${t.avg_q?.toFixed(3) || 'N/A'}`);
      }
      console.log(`\n   执行记录: ${execCount} (完成: ${completed})`);
      console.log();
    } finally {
      db.close();
    }
    process.exit(0);
  }

  console.error(`未知命令: ${command}. 使用 --help 查看帮助.`);
  process.exit(1);
}
