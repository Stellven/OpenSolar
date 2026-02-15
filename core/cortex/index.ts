/**
 * Cortex v0.1 - 统一记忆与状态系统
 * 唯一真相源，解决失忆 + 支撑 AI 管 AI
 *
 * 入口命令:
 *   cortex query <sql>     - 执行查询
 *   cortex upsert <table> <json> - 插入/更新
 *   cortex recent          - 最近任务
 *   cortex task <id>       - 查看任务详情
 *   cortex phase <task_id> <phase> - 更新任务阶段
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';
import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'fs';
import { join } from 'path';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const ARTIFACTS_DIR = `${homedir()}/.solar/cortex/artifacts`;

// 确保目录存在
if (!existsSync(ARTIFACTS_DIR)) {
  mkdirSync(ARTIFACTS_DIR, { recursive: true });
}

const db = new Database(DB_PATH);

// ============================================================
// 结构化输出类型定义
// ============================================================
export interface Source {
  citation_key: string;
  title: string;
  url?: string;
  finding: string;
  credibility: number;
}

export interface Claim {
  claim_id: string;
  text: string;
  supporting_sources: string[];
  counter_sources: string[];
}

export interface OutlineSection {
  section_id: string;
  goal: string;
  required_claims: string[];
}

export interface EvalEntry {
  reviewer_model: string;
  target_model: string;
  rubric: Record<string, number>;
  score: number;
  verdict: string;
}

export interface DraftSection {
  section_id: string;
  expert_model: string;
  content: string;
  word_count: number;
}

export interface CostEntry {
  expert_model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface StructuredOutput {
  sources: Source[];
  claims: Claim[];
  outline: OutlineSection[];
  eval_matrix: EvalEntry[];
  draft_sections: DraftSection[];
  cost: CostEntry[];
}

// ============================================================
// Cortex 核心类
// ============================================================
export class Cortex {
  private db: Database;
  private artifactsDir: string;

  constructor() {
    this.db = db;
    this.artifactsDir = ARTIFACTS_DIR;
  }

  // ============================================================
  // 任务管理
  // ============================================================

  createTask(taskType: string, topic: string, requester?: string, config?: object): string {
    const taskId = `${taskType}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    this.db.run(`
      INSERT INTO cortex_tasks (task_id, task_type, topic, requester, config, phase_status)
      VALUES (?, ?, ?, ?, ?, ?)
    `, [
      taskId,
      taskType,
      topic,
      requester || 'unknown',
      JSON.stringify(config || {}),
      JSON.stringify({})
    ]);

    return taskId;
  }

  getTask(taskId: string): any {
    return this.db.query(`SELECT * FROM cortex_tasks WHERE task_id = ?`).get(taskId);
  }

  updateTaskPhase(taskId: string, phase: number, status: string = 'in_progress'): void {
    const task = this.getTask(taskId);
    const phaseStatus = JSON.parse(task.phase_status || '{}');
    phaseStatus[`phase${phase}`] = status;

    this.db.run(`
      UPDATE cortex_tasks
      SET current_phase = ?, phase_status = ?, status = ?
      WHERE task_id = ?
    `, [phase, JSON.stringify(phaseStatus), status === 'completed' ? 'completed' : 'in_progress', taskId]);
  }

  completeTask(taskId: string): void {
    this.db.run(`
      UPDATE cortex_tasks
      SET status = 'completed', completed_at = datetime('now')
      WHERE task_id = ?
    `, [taskId]);
  }

  getRecentTasks(limit: number = 20): any[] {
    return this.db.query(`SELECT * FROM v_cortex_recent LIMIT ?`).all(limit) as any[];
  }

  // ============================================================
  // 产物管理
  // ============================================================

  saveArtifact(
    taskId: string,
    phase: number,
    artifactType: string,
    contentJson: object,
    expertModel?: string,
    tokens?: number,
    latency?: number
  ): number {
    // 持久化到文件系统
    const fileName = `${taskId}_phase${phase}_${artifactType}_${Date.now()}.json`;
    const filePath = join(this.artifactsDir, fileName);
    writeFileSync(filePath, JSON.stringify(contentJson, null, 2));

    // 保存到数据库
    const result = this.db.run(`
      INSERT INTO cortex_artifacts (task_id, phase, artifact_type, expert_model, content_json, file_path, token_count, latency_ms)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `, [taskId, phase, artifactType, expertModel, JSON.stringify(contentJson), filePath, tokens, latency]);

    return Number(result.lastInsertRowid);
  }

  getArtifacts(taskId: string, phase?: number, artifactType?: string): any[] {
    let query = `SELECT * FROM cortex_artifacts WHERE task_id = ?`;
    const params: any[] = [taskId];

    if (phase !== undefined) {
      query += ` AND phase = ?`;
      params.push(phase);
    }
    if (artifactType) {
      query += ` AND artifact_type = ?`;
      params.push(artifactType);
    }

    query += ` ORDER BY created_at`;
    return this.db.query(query).all(...params) as any[];
  }

  // ============================================================
  // 引用源管理
  // ============================================================

  addSource(taskId: string, source: Source, expertModel?: string): number {
    const result = this.db.run(`
      INSERT INTO cortex_sources (task_id, citation_key, title, url, finding, credibility, expert_model)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `, [taskId, source.citation_key, source.title, source.url, source.finding, source.credibility, expertModel]);

    return Number(result.lastInsertRowid);
  }

  getSources(taskId: string): Source[] {
    return this.db.query(`SELECT * FROM cortex_sources WHERE task_id = ?`).all(taskId) as Source[];
  }

  // ============================================================
  // 论点管理
  // ============================================================

  addClaim(taskId: string, claim: Claim, expertModel?: string): number {
    const result = this.db.run(`
      INSERT INTO cortex_claims (task_id, claim_text, supporting_sources, counter_sources, expert_model)
      VALUES (?, ?, ?, ?, ?)
    `, [
      taskId,
      claim.text,
      JSON.stringify(claim.supporting_sources),
      JSON.stringify(claim.counter_sources),
      expertModel
    ]);

    return Number(result.lastInsertRowid);
  }

  getClaims(taskId: string): Claim[] {
    return this.db.query(`SELECT * FROM cortex_claims WHERE task_id = ?`).all(taskId) as any[];
  }

  // ============================================================
  // 互评管理
  // ============================================================

  addEval(
    taskId: string,
    phase: number,
    artifactId: number,
    reviewerModel: string,
    targetModel: string,
    rubric: Record<string, number>,
    score: number,
    verdict: string,
    suggestions?: string[]
  ): number {
    const result = this.db.run(`
      INSERT INTO cortex_evals (task_id, phase, artifact_id, reviewer_model, target_model, rubric, score, verdict, suggestions)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `, [
      taskId, phase, artifactId, reviewerModel, targetModel,
      JSON.stringify(rubric), score, verdict, JSON.stringify(suggestions || [])
    ]);

    return Number(result.lastInsertRowid);
  }

  getEvals(taskId: string, phase?: number): EvalEntry[] {
    let query = `SELECT * FROM cortex_evals WHERE task_id = ?`;
    const params: any[] = [taskId];

    if (phase !== undefined) {
      query += ` AND phase = ?`;
      params.push(phase);
    }

    return this.db.query(query).all(...params) as any[];
  }

  // ============================================================
  // 大纲管理
  // ============================================================

  setOutline(taskId: string, sections: OutlineSection[]): void {
    // 清除旧大纲
    this.db.run(`DELETE FROM cortex_outline WHERE task_id = ?`, [taskId]);

    // 插入新大纲
    sections.forEach((section, index) => {
      this.db.run(`
        INSERT INTO cortex_outline (task_id, section_order, section_title, goal, required_claims)
        VALUES (?, ?, ?, ?, ?)
      `, [taskId, index + 1, section.section_id, section.goal, JSON.stringify(section.required_claims)]);
    });
  }

  getOutline(taskId: string): OutlineSection[] {
    return this.db.query(`
      SELECT * FROM cortex_outline WHERE task_id = ? ORDER BY section_order
    `).all(taskId) as any[];
  }

  updateSectionPrompt(taskId: string, sectionOrder: number, prompt: string): void {
    this.db.run(`
      UPDATE cortex_outline SET prompt = ? WHERE task_id = ? AND section_order = ?
    `, [prompt, taskId, sectionOrder]);
  }

  // ============================================================
  // 草稿管理
  // ============================================================

  saveDraft(taskId: string, sectionId: number, expertModel: string, content: string, version: number = 1): number {
    const wordCount = content.split(/\s+/).length;

    const result = this.db.run(`
      INSERT INTO cortex_draft_sections (task_id, section_id, expert_model, version, content, word_count)
      VALUES (?, ?, ?, ?, ?, ?)
    `, [taskId, sectionId, expertModel, version, content, wordCount]);

    return Number(result.lastInsertRowid);
  }

  getDrafts(taskId: string, sectionId?: number): DraftSection[] {
    let query = `SELECT * FROM cortex_draft_sections WHERE task_id = ?`;
    const params: any[] = [taskId];

    if (sectionId !== undefined) {
      query += ` AND section_id = ?`;
      params.push(sectionId);
    }

    query += ` ORDER BY section_id, version`;
    return this.db.query(query).all(...params) as any[];
  }

  setFinalDraft(draftId: number): void {
    this.db.run(`UPDATE cortex_draft_sections SET is_final = TRUE WHERE draft_id = ?`, [draftId]);
  }

  // ============================================================
  // 成本追踪
  // ============================================================

  recordCost(taskId: string, phase: number, expertModel: string, inputTokens: number, outputTokens: number, costUsd: number): void {
    this.db.run(`
      INSERT INTO cortex_cost (task_id, phase, expert_model, input_tokens, output_tokens, cost_usd)
      VALUES (?, ?, ?, ?, ?, ?)
    `, [taskId, phase, expertModel, inputTokens, outputTokens, costUsd]);
  }

  getCost(taskId: string): CostEntry[] {
    return this.db.query(`SELECT * FROM cortex_cost WHERE task_id = ?`).all(taskId) as any[];
  }

  getTotalCost(taskId: string): number {
    const result = this.db.query(`SELECT SUM(cost_usd) as total FROM cortex_cost WHERE task_id = ?`).get(taskId) as any;
    return result?.total || 0;
  }

  // ============================================================
  // 结构化输出
  // ============================================================

  getStructuredOutput(taskId: string): StructuredOutput {
    return {
      sources: this.getSources(taskId),
      claims: this.getClaims(taskId),
      outline: this.getOutline(taskId),
      eval_matrix: this.getEvals(taskId),
      draft_sections: this.getDrafts(taskId),
      cost: this.getCost(taskId)
    };
  }

  // ============================================================
  // 通用查询
  // ============================================================

  query(sql: string): any[] {
    return this.db.query(sql).all() as any[];
  }

  upsert(table: string, data: object): void {
    const keys = Object.keys(data);
    const values = Object.values(data);
    const placeholders = keys.map(() => '?').join(', ');
    const updates = keys.map(k => `${k} = excluded.${k}`).join(', ');

    this.db.run(`
      INSERT INTO ${table} (${keys.join(', ')})
      VALUES (${placeholders})
      ON CONFLICT DO UPDATE SET ${updates}
    `, values);
  }
}

// ============================================================
// CLI 入口
// ============================================================

// 只在直接执行时运行 CLI，不在 import 时运行
if (import.meta.main) {
  const cortex = new Cortex();

  const command = process.argv[2];

  switch (command) {
  case 'query': {
    const sql = process.argv.slice(3).join(' ');
    const results = cortex.query(sql);
    console.log(JSON.stringify(results, null, 2));
    break;
  }

  case 'recent': {
    const limit = parseInt(process.argv[3]) || 20;
    const tasks = cortex.getRecentTasks(limit);
    console.log('\n📋 最近任务:\n');
    tasks.forEach(t => {
      console.log(`  ${t.task_id}`);
      console.log(`    主题: ${t.topic}`);
      console.log(`    状态: ${t.status} (Phase ${t.current_phase})`);
      console.log(`    时间: ${t.created_at}\n`);
    });
    break;
  }

  case 'task': {
    const taskId = process.argv[3];
    if (!taskId) {
      console.error('用法: cortex task <task_id>');
      process.exit(1);
    }
    const task = cortex.getTask(taskId);
    const output = cortex.getStructuredOutput(taskId);
    console.log('\n📦 任务详情:\n');
    console.log(JSON.stringify({ task, ...output }, null, 2));
    break;
  }

  case 'phase': {
    const taskId = process.argv[3];
    const phase = parseInt(process.argv[4]);
    const status = process.argv[5] || 'in_progress';
    if (!taskId || isNaN(phase)) {
      console.error('用法: cortex phase <task_id> <phase> [status]');
      process.exit(1);
    }
    cortex.updateTaskPhase(taskId, phase, status);
    console.log(`✅ 任务 ${taskId} 已更新到 Phase ${phase} (${status})`);
    break;
  }

  case 'init': {
    // 初始化 schema
    const schemaPath = join(import.meta.dir, 'schema.sql');
    const schema = readFileSync(schemaPath, 'utf-8');
    db.exec(schema);
    console.log('✅ Cortex schema 初始化完成');
    break;
  }

  default:
    console.log(`
Cortex v0.1 - 统一记忆与状态系统

用法:
  bun cortex.ts init                    - 初始化数据库
  bun cortex.ts query <sql>             - 执行查询
  bun cortex.ts recent [limit]          - 最近任务
  bun cortex.ts task <task_id>          - 任务详情 (含结构化输出)
  bun cortex.ts phase <task_id> <n> [s] - 更新任务阶段
`);
  }
}  // if (import.meta.main)

export default Cortex;
