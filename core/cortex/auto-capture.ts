#!/usr/bin/env bun
/**
 * Auto-Capture System - 自动知识捕获核心模块
 *
 * 功能：
 * 1. 捕获所有搜索结果（Grep/Glob/WebSearch/WebFetch/Read）
 * 2. 捕获专家输出（brain-router 调用）
 * 3. 捕获开发产物（代码/设计/分析/决策）
 *
 * 原则：不要问我，都存下来（自动保存，无需确认）
 */

import Database from 'bun:sqlite';
import { randomBytes } from 'crypto';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const SESSION_ID = process.env.CLAUDE_SESSION_ID?.substring(0, 8) || 'unknown';

interface SearchCapture {
  search_type: 'grep' | 'glob' | 'websearch' | 'webfetch' | 'read';
  query: string;
  context?: string;
  results: any;
  result_count?: number;
  tool_params?: any;
}

interface ExpertCapture {
  model: string;
  expert_role?: string;
  system_prompt?: string;
  user_prompt: string;
  output: string;
  task_type?: string;
  context?: string;
  tokens_input?: number;
  tokens_output?: number;
  latency_ms?: number;
}

interface ArtifactCapture {
  artifact_type: 'code' | 'design' | 'analysis' | 'decision' | 'test' | 'refactor' | 'architecture';
  title: string;
  content: string;
  file_path?: string;
  tags?: string[];
  context?: string;
  related_task?: string;
  importance?: number;
}

/**
 * 生成唯一 ID
 */
function generateId(prefix: string): string {
  const timestamp = Date.now().toString(36);
  const random = randomBytes(4).toString('hex');
  return `${prefix}_${timestamp}_${random}`;
}

/**
 * 捕获搜索结果
 */
export async function captureSearch(data: SearchCapture): Promise<string> {
  const db = new Database(DB_PATH);

  try {
    const search_id = generateId('search');

    db.run(`
      INSERT INTO sys_search_cache (
        search_id, search_type, query, context, results,
        result_count, tool_params, session_id, synced_to_graph
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    `, [
      search_id,
      data.search_type,
      data.query,
      data.context || null,
      JSON.stringify(data.results),
      data.result_count || null,
      data.tool_params ? JSON.stringify(data.tool_params) : null,
      SESSION_ID
    ]);

    return search_id;
  } finally {
    db.close();
  }
}

/**
 * 捕获专家输出
 */
export async function captureExpertOutput(data: ExpertCapture): Promise<string> {
  const db = new Database(DB_PATH);

  try {
    const output_id = generateId('expert');

    db.run(`
      INSERT INTO sys_expert_outputs (
        output_id, model, expert_role, system_prompt, user_prompt,
        output, task_type, context, tokens_input, tokens_output,
        latency_ms, session_id, synced_to_graph
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    `, [
      output_id,
      data.model,
      data.expert_role || null,
      data.system_prompt || null,
      data.user_prompt,
      data.output,
      data.task_type || null,
      data.context || null,
      data.tokens_input || null,
      data.tokens_output || null,
      data.latency_ms || null,
      SESSION_ID
    ]);

    return output_id;
  } finally {
    db.close();
  }
}

/**
 * 捕获开发产物
 */
export async function captureArtifact(data: ArtifactCapture): Promise<string> {
  const db = new Database(DB_PATH);

  try {
    const artifact_id = generateId('artifact');

    db.run(`
      INSERT INTO sys_dev_artifacts (
        artifact_id, artifact_type, title, content, file_path,
        tags, context, related_task, importance, session_id, synced_to_graph
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    `, [
      artifact_id,
      data.artifact_type,
      data.title,
      data.content,
      data.file_path || null,
      data.tags ? JSON.stringify(data.tags) : null,
      data.context || null,
      data.related_task || null,
      data.importance || 5,
      SESSION_ID
    ]);

    return artifact_id;
  } finally {
    db.close();
  }
}

/**
 * 获取待抽取统计
 */
export function getPendingStats(): any {
  const db = new Database(DB_PATH);

  try {
    const stats = db.query(`SELECT * FROM v_capture_stats`).all();
    return stats;
  } finally {
    db.close();
  }
}

/**
 * 获取待抽取条目
 */
export function getPendingEntries(limit: number = 100): any[] {
  const db = new Database(DB_PATH);

  try {
    const entries = db.query(`
      SELECT * FROM v_pending_extraction
      ORDER BY created_at DESC
      LIMIT ?
    `).all(limit);
    return entries;
  } finally {
    db.close();
  }
}

// CLI 接口
if (import.meta.main) {
  const command = process.argv[2];

  switch (command) {
    case 'stats':
      const stats = getPendingStats();
      console.log('📊 自动捕获统计:\n');
      console.table(stats);
      break;

    case 'pending':
      const limit = parseInt(process.argv[3] || '10');
      const entries = getPendingEntries(limit);
      console.log(`\n📋 待抽取条目 (前 ${limit} 条):\n`);
      entries.forEach((entry: any, i: number) => {
        console.log(`${i + 1}. [${entry.source_type}] ${entry.title}`);
        console.log(`   时间: ${entry.created_at}`);
        console.log(`   内容预览: ${entry.content?.substring(0, 100)}...`);
        console.log('');
      });
      break;

    case 'test-search':
      const search_id = await captureSearch({
        search_type: 'grep',
        query: 'test query',
        context: 'testing auto-capture',
        results: { matches: ['result1', 'result2'] },
        result_count: 2,
        tool_params: { pattern: 'test', path: '/test' }
      });
      console.log(`✅ 搜索捕获成功: ${search_id}`);
      break;

    case 'test-expert':
      const output_id = await captureExpertOutput({
        model: 'glm-5',
        expert_role: '测试专家',
        system_prompt: 'You are a test expert',
        user_prompt: 'Test this',
        output: 'Test output from expert',
        task_type: 'test',
        tokens_input: 100,
        tokens_output: 50,
        latency_ms: 1500
      });
      console.log(`✅ 专家输出捕获成功: ${output_id}`);
      break;

    case 'test-artifact':
      const artifact_id = await captureArtifact({
        artifact_type: 'code',
        title: '测试代码片段',
        content: 'function test() { return "hello"; }',
        tags: ['test', 'javascript'],
        importance: 7
      });
      console.log(`✅ 产物捕获成功: ${artifact_id}`);
      break;

    default:
      console.log(`
Usage:
  bun auto-capture.ts stats              # 查看捕获统计
  bun auto-capture.ts pending [limit]    # 查看待抽取条目
  bun auto-capture.ts test-search        # 测试搜索捕获
  bun auto-capture.ts test-expert        # 测试专家捕获
  bun auto-capture.ts test-artifact      # 测试产物捕获
      `);
  }
}
