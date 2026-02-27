#!/usr/bin/env bun
import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';
import { callLLM } from '../cortex/llm-api-client';

// 数据库路径配置
const DB_PATH = path.join(os.homedir(), '.solar', 'solar.db');

// 类型定义
interface LogTurnParams {
  sessionId: string;
  turnId: number;
  userInput: string;
  aiOutput: string;
  metadata?: Record<string, any>;
}

interface RetrieveOptions {
  limit?: number;
  sessionId?: string;
  startTime?: number;
  endTime?: number;
}

interface ContextResult {
  turns: Array<{
    turnId: number;
    userInput: string;
    aiOutput: string;
    timestamp: number;
  }>;
  triples: Array<{
    subject: string;
    predicate: string;
    object: string;
    confidence: number;
  }>;
}

interface ConsolidationOptions {
  minTurns?: number;
}

// 数据库连接管理
class DatabaseManager {
  private static instance: Database | null = null;

  static getConnection(): Database {
    if (!this.instance) {
      this.instance = new Database(DB_PATH, { create: true });
      this.initializeSchema();
    }
    return this.instance;
  }

  private static initializeSchema(): void {
    const db = this.instance!;

    // 创建会话日志表
    db.run(`
      CREATE TABLE IF NOT EXISTS session_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        turn_id INTEGER NOT NULL,
        user_input TEXT NOT NULL,
        ai_output TEXT NOT NULL,
        metadata TEXT,
        timestamp INTEGER DEFAULT (unixepoch()),
        UNIQUE(session_id, turn_id)
      )
    `);

    // 创建知识三元组表
    db.run(`
      CREATE TABLE IF NOT EXISTS knowledge_triples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        predicate TEXT NOT NULL,
        object TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        created_at INTEGER DEFAULT (unixepoch()),
        UNIQUE(subject, predicate, object)
      )
    `);

    // 创建索引优化查询性能
    db.run('CREATE INDEX IF NOT EXISTS idx_session_log_session ON session_log(session_id)');
    db.run('CREATE INDEX IF NOT EXISTS idx_session_log_timestamp ON session_log(timestamp)');
    db.run('CREATE INDEX IF NOT EXISTS idx_triples_subject ON knowledge_triples(subject)');
    db.run('CREATE INDEX IF NOT EXISTS idx_triples_predicate ON knowledge_triples(predicate)');
  }
}

// 核心函数实现
export async function logTurn(params: LogTurnParams): Promise<void> {
  const db = DatabaseManager.getConnection();

  try {
    const metadataJson = params.metadata ? JSON.stringify(params.metadata) : null;

    const stmt = db.prepare(`
      INSERT OR REPLACE INTO session_log
      (session_id, turn_id, user_input, ai_output, metadata, timestamp)
      VALUES (?, ?, ?, ?, ?, unixepoch())
    `);

    stmt.run(
      params.sessionId,
      params.turnId,
      params.userInput,
      params.aiOutput,
      metadataJson
    );

    stmt.finalize();
  } catch (error) {
    console.error('Failed to log turn:', error);
    throw new Error(`Log turn failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

export async function retrieveContext(
  query: string,
  options: RetrieveOptions = {}
): Promise<ContextResult> {
  const db = DatabaseManager.getConnection();
  const limit = options.limit || 10;

  try {
    // L2: 检索会话日志
    let turnsQuery = `
      SELECT turn_id, user_input, ai_output, timestamp
      FROM session_log
      WHERE (user_input LIKE ? OR ai_output LIKE ?)
    `;

    const queryParams: any[] = [`%${query}%`, `%${query}%`];

    if (options.sessionId) {
      turnsQuery += ' AND session_id = ?';
      queryParams.push(options.sessionId);
    }

    if (options.startTime) {
      turnsQuery += ' AND timestamp >= ?';
      queryParams.push(options.startTime);
    }

    if (options.endTime) {
      turnsQuery += ' AND timestamp <= ?';
      queryParams.push(options.endTime);
    }

    turnsQuery += ' ORDER BY timestamp DESC LIMIT ?';
    queryParams.push(limit);

    const turnsStmt = db.prepare(turnsQuery);
    const turns = turnsStmt.all(...queryParams) as Array<{
      turn_id: number;
      user_input: string;
      ai_output: string;
      timestamp: number;
    }>;
    turnsStmt.finalize();

    // L3: 检索知识三元组
    const triplesQuery = `
      SELECT subject, predicate, object, confidence
      FROM knowledge_triples
      WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ?
      LIMIT ?
    `;

    const triplesStmt = db.prepare(triplesQuery);
    const triples = triplesStmt.all(
      `%${query}%`,
      `%${query}%`,
      `%${query}%`,
      limit
    ) as Array<{
      subject: string;
      predicate: string;
      object: string;
      confidence: number;
    }>;
    triplesStmt.finalize();

    return {
      turns: turns.map(t => ({
        turnId: t.turn_id,
        userInput: t.user_input,
        aiOutput: t.ai_output,
        timestamp: t.timestamp
      })),
      triples: triples.map(t => ({
        subject: t.subject,
        predicate: t.predicate,
        object: t.object,
        confidence: t.confidence
      }))
    };
  } catch (error) {
    console.error('Failed to retrieve context:', error);
    throw new Error(`Retrieve context failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ==================== Phase 1: Rule Enhancement Helpers ====================

/**
 * 判断文本是否为问句
 */
function isQuestion(text: string): boolean {
  // 检测问号
  if (text.includes('？') || text.includes('?')) return true;

  // 检测疑问词
  const questionWords = ['什么', '为什么', '怎么', '如何', '哪', '谁', '多少', '几', '吗', '呢'];
  return questionWords.some(word => text.includes(word));
}

/**
 * 检查实体是否包含代词
 */
function hasPronouns(entity: string): boolean {
  const pronouns = ['它', '这', '那', '其', '他', '她', '这个', '那个', '这些', '那些'];
  return pronouns.some(pronoun => entity === pronoun || entity.startsWith(pronoun + ' ') || entity.endsWith(' ' + pronoun));
}

/**
 * 验证实体是否有效
 */
function isValidEntity(entity: string): boolean {
  // 长度检查 (2-30 字符)
  if (entity.length < 2 || entity.length > 30) return false;

  // 必须包含中文/字母/数字
  if (!/[\u4e00-\u9fa5a-zA-Z0-9]/.test(entity)) return false;

  // 不能是纯标点
  if (/^[^\u4e00-\u9fa5a-zA-Z0-9]+$/.test(entity)) return false;

  return true;
}

/**
 * 计算三元组置信度
 */
function calculateConfidence(subject: string, predicate: string, object: string, text: string): number {
  let confidence = 0.5; // 基础分

  // 主语质量 (+0.1)
  if (subject.length >= 2 && subject.length <= 10 && /^[\u4e00-\u9fa5a-zA-Z0-9]+$/.test(subject)) {
    confidence += 0.1;
  }

  // 谓语类型 (+0.05)
  const strongPredicates = ['是', '包括', '定义为', '等于'];
  if (strongPredicates.includes(predicate)) {
    confidence += 0.05;
  }

  // 宾语有效性 (+0.1)
  if (object.length >= 3 && !hasPronouns(object)) {
    confidence += 0.1;
  }

  // 上下文支持 (+0.05)
  if (text.length > 50) { // 长文本更可信
    confidence += 0.05;
  }

  return Math.min(confidence, 0.9); // 规则提取最高0.9
}

// ==================== End Phase 1 Helpers ====================

// ==================== Phase 2.5+: Enhanced LLM-based Triple Extraction ====================

/**
 * 清理 LLM 返回的 JSON 字符串（去除 markdown 代码块标记）
 */
function cleanJsonOutput(text: string): string {
  return text.replace(/```json\n?|```/g, "").trim();
}

/**
 * 使用 LLM 从会话内容中提取知识三元组
 *
 * Phase 2.5+ 优化 (DeepSeek-R1 测试):
 * 1. 模型: 使用 deepseek-r1 测试最大潜力 (CoT reasoning)
 * 2. Prompt 调优: 约束使用标准动词 (是、有、可以、使用)
 * 3. Few-shot learning: 添加 2 个标准示例
 *
 * @param contents 会话内容数组
 * @returns 提取的三元组数组
 */
export async function extractTriplesWithLLM(
  contents: Array<{ai_output: string}>
): Promise<Array<{subject: string, predicate: string, object: string, confidence: number}>> {
  const texts = contents.map(c => c.ai_output).join("\n---\n");

  const systemPrompt = `你是一个专业的知识图谱构建专家。你的任务是从给定的技术文本中提取"三元组"（实体-关系-实体）。

提取规则：
1. 实体：具体技术名词、工具、参数。
2. 关系：必须使用标准动词: 是、有、可以、使用。不要使用同义词替换。
3. 保持宾语完整性：如果原文有修饰词（如"索引"、"函数"、"表"），必须保留在宾语中。
4. 严格输出 JSON 数组，无 Markdown。
5. 为每个三元组标注置信度(confidence, 0.0-1.0)。

置信度标准：
- 0.9-1.0: 原文明确陈述，无歧义（如"A 是 B"）
- 0.8-0.89: 原文清楚，稍有推断（如"A 使用 B 存储"）
- 0.7-0.79: 需要一定推断，但合理（如"A 有 B 和 C"）
- 0.6以下: 不确定，避免提取

Few-shot 示例（标准格式）：
示例1 - 基础定义：
输入: "SMA 是 Solar Memory Architecture，三层记忆系统。L1 是上下文窗口，L2 是无损会话记录。"
输出: [
  {"subject": "SMA", "predicate": "是", "object": "Solar Memory Architecture", "confidence": 0.95},
  {"subject": "SMA", "predicate": "是", "object": "三层记忆系统", "confidence": 0.95},
  {"subject": "L1", "predicate": "是", "object": "上下文窗口", "confidence": 0.95},
  {"subject": "L2", "predicate": "是", "object": "无损会话记录", "confidence": 0.95}
]

示例2 - 保持宾语完整性（关键！）：
输入: "L2 有 session_id 和 turn_id 两个索引"
输出: [
  {"subject": "L2", "predicate": "有", "object": "session_id 索引", "confidence": 0.85},
  {"subject": "L2", "predicate": "有", "object": "turn_id 索引", "confidence": 0.85}
]
注意：保留"索引"修饰词，不要只提取"session_id"。

示例3 - 能力动词：
输入: "L2 可以无损记录所有会话轨迹，使用 session_log 表存储。"
输出: [
  {"subject": "L2", "predicate": "可以", "object": "无损记录所有会话轨迹", "confidence": 0.90},
  {"subject": "L2", "predicate": "使用", "object": "session_log 表", "confidence": 0.85}
]

示例4 - 函数能力：
输入: "memory-controller.ts 有三个核心函数: logTurn 写入 L2，retrieveContext 检索记忆，triggerConsolidation 固化知识。"
输出: [
  {"subject": "memory-controller.ts", "predicate": "有", "object": "三个核心函数", "confidence": 0.90},
  {"subject": "logTurn", "predicate": "可以", "object": "写入 L2", "confidence": 0.85},
  {"subject": "retrieveContext", "predicate": "可以", "object": "检索记忆", "confidence": 0.85},
  {"subject": "triggerConsolidation", "predicate": "可以", "object": "固化知识", "confidence": 0.85}
]

禁止事项：
- ❌ 不要过度分割复合名词（错误：turn_id → 正确：turn_id 索引）
- ❌ 不要提取推测性三元组（只提取原文明确的信息）
- ❌ 不要改变谓语类型（原文是"可以"就用"可以"，不要改成"是"）

格式要求：
[{"subject": "实体1", "predicate": "标准动词", "object": "实体2", "confidence": 0.0-1.0}]`;

  try {
    const response = await callLLM(
      'gemini-2-flash',  // Phase 2.5+: 改用 Gemini 2 Flash (快速信息提取，无限流问题)
      systemPrompt,
      `分析内容:\n${texts}`,
      0.1  // 低温度以保证确定性输出
    );

    const jsonStr = cleanJsonOutput(response);
    const triples = JSON.parse(jsonStr);

    // 过滤掉缺失字段的三元组
    return triples.filter((t: any) => t.subject && t.predicate && t.object);
  } catch (error) {
    console.error('LLM extraction failed:', error);
    throw new Error(`LLM extraction failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// ==================== End Phase 2.5+ ====================

// ==================== Phase 4: Auto Knowledge Consolidation ====================

/**
 * Phase 4: 自动触发知识固化（使用 LLM 提取）
 *
 * 改进点：
 * 1. 使用 Phase 3 验证通过的 LLM 方案替代 NLP
 * 2. 添加智能去重与合并逻辑
 * 3. 支持增量固化（只处理新增会话）
 */
export async function triggerConsolidation(
  sessionId: string,
  options: ConsolidationOptions = {}
): Promise<number> {
  const db = DatabaseManager.getConnection();
  const minTurns = options.minTurns || 5;

  try {
    // 检查是否有足够轮次
    const countStmt = db.prepare(`
      SELECT COUNT(*) as count FROM session_log WHERE session_id = ?
    `);
    const countResult = countStmt.get(sessionId) as { count: number };
    countStmt.finalize();

    if (countResult.count < minTurns) {
      console.log(`Session ${sessionId} has only ${countResult.count} turns, skipping consolidation (min ${minTurns})`);
      return 0;
    }

    // 获取会话内容（限制批次大小防止超限）
    const BATCH_SIZE = 10;  // 每次最多处理 10 条对话（从50降低，避免token超限）
    const contentStmt = db.prepare(`
      SELECT user_input, ai_output
      FROM session_log
      WHERE session_id = ?
      ORDER BY turn_id DESC
      LIMIT ?
    `);
    const contents = contentStmt.all(sessionId, BATCH_SIZE) as Array<{
      user_input: string;
      ai_output: string;
    }>;
    contentStmt.finalize();

    console.log(`Consolidating ${contents.length} turns from session ${sessionId} (batch size: ${BATCH_SIZE})...`);

    // Phase 4: 使用 LLM 提取三元组（替代 NLP）
    const extractedTriples = await extractTriplesWithLLM(contents);

    console.log(`LLM extracted ${extractedTriples.length} triples`);

    // Phase 4: 智能去重与合并
    const mergedTriples = await mergeAndDeduplicateTriples(db, extractedTriples);

    console.log(`After deduplication: ${mergedTriples.length} unique triples`);

    // 写入数据库
    if (mergedTriples.length > 0) {
      const insertStmt = db.prepare(`
        INSERT OR REPLACE INTO knowledge_triples
        (subject, predicate, object, confidence, created_at)
        VALUES (?, ?, ?, ?, unixepoch())
      `);

      db.transaction(() => {
        for (const triple of mergedTriples) {
          insertStmt.run(triple.subject, triple.predicate, triple.object, triple.confidence);
        }
      })();

      insertStmt.finalize();
    }

    return mergedTriples.length;
  } catch (error) {
    console.error('Failed to trigger consolidation:', error);
    throw new Error(`Consolidation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Phase 4: 智能去重与合并三元组
 *
 * 逻辑：
 * 1. 完全相同的三元组：保留置信度最高的
 * 2. 主谓相同但宾语不同：合并为多个三元组（如 L2 有 A，L2 有 B）
 * 3. 与已有知识冲突：根据置信度决定保留或更新
 */
async function mergeAndDeduplicateTriples(
  db: Database,
  newTriples: Array<{subject: string, predicate: string, object: string, confidence: number}>
): Promise<Array<{subject: string, predicate: string, object: string, confidence: number}>> {
  // 按 (subject, predicate, object) 去重，保留置信度最高的
  const tripleMap = new Map<string, {subject: string, predicate: string, object: string, confidence: number}>();

  for (const triple of newTriples) {
    const key = `${triple.subject}|${triple.predicate}|${triple.object}`;
    const existing = tripleMap.get(key);

    if (!existing || triple.confidence > existing.confidence) {
      tripleMap.set(key, triple);
    }
  }

  // 检查与数据库中已有知识的冲突
  const mergedTriples: Array<{subject: string, predicate: string, object: string, confidence: number}> = [];

  for (const triple of tripleMap.values()) {
    // 查询是否已存在相同的三元组
    const existingStmt = db.prepare(`
      SELECT confidence FROM knowledge_triples
      WHERE subject = ? AND predicate = ? AND object = ?
    `);
    const existingTriple = existingStmt.get(triple.subject, triple.predicate, triple.object) as { confidence: number } | undefined;
    existingStmt.finalize();

    if (existingTriple) {
      // 已存在相同三元组，取置信度最大值
      mergedTriples.push({
        ...triple,
        confidence: Math.max(triple.confidence, existingTriple.confidence)
      });
    } else {
      // 新三元组，直接添加
      mergedTriples.push(triple);
    }
  }

  return mergedTriples;
}

/**
 * Phase 4: 清理过期的低置信度知识
 *
 * 清理策略：
 * 1. 删除创建时间超过阈值且置信度低于阈值的三元组
 * 2. 默认保留期：90天（7776000秒）
 * 3. 默认置信度阈值：0.7
 *
 * @param maxAgeSeconds 最大保留时间（秒），默认90天
 * @param minConfidence 最小置信度阈值，低于此值的将被清理
 * @returns 清理的三元组数量
 */
export async function cleanupExpiredTriples(
  maxAgeSeconds: number = 7776000,  // 90天
  minConfidence: number = 0.7
): Promise<number> {
  const db = DatabaseManager.getConnection();

  try {
    const cutoffTime = Math.floor(Date.now() / 1000) - maxAgeSeconds;

    const deleteStmt = db.prepare(`
      DELETE FROM knowledge_triples
      WHERE created_at < ? AND confidence < ?
    `);

    const result = deleteStmt.run(cutoffTime, minConfidence);
    deleteStmt.finalize();

    const deletedCount = result.changes || 0;

    if (deletedCount > 0) {
      console.log(`Cleaned up ${deletedCount} expired triples (older than ${maxAgeSeconds}s with confidence < ${minConfidence})`);
    }

    return deletedCount;
  } catch (error) {
    console.error('Failed to cleanup expired triples:', error);
    throw new Error(`Cleanup failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Phase 4: 知识图谱查询接口
 *
 * 支持的查询类型：
 * 1. 基于主语查询所有相关三元组
 * 2. 基于主语+谓语查询对象
 * 3. 路径查询（找两个实体之间的连接，最多2跳）
 * 4. 置信度过滤
 */
export interface KnowledgeQueryOptions {
  subject?: string;
  predicate?: string;
  object?: string;
  minConfidence?: number;
  limit?: number;
}

export interface KnowledgeTriple {
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
}

export interface KnowledgePath {
  path: KnowledgeTriple[];
  confidence: number;  // 路径最小置信度
}

/**
 * 查询知识图谱
 *
 * @param options 查询选项
 * @returns 匹配的三元组数组
 */
export async function queryKnowledgeGraph(
  options: KnowledgeQueryOptions
): Promise<KnowledgeTriple[]> {
  const db = DatabaseManager.getConnection();
  const { subject, predicate, object, minConfidence = 0.0, limit = 100 } = options;

  try {
    let query = 'SELECT subject, predicate, object, confidence FROM knowledge_triples WHERE 1=1';
    const params: any[] = [];

    if (subject) {
      query += ' AND subject LIKE ?';
      params.push(`%${subject}%`);
    }

    if (predicate) {
      query += ' AND predicate = ?';
      params.push(predicate);
    }

    if (object) {
      query += ' AND object LIKE ?';
      params.push(`%${object}%`);
    }

    if (minConfidence > 0) {
      query += ' AND confidence >= ?';
      params.push(minConfidence);
    }

    query += ' ORDER BY confidence DESC LIMIT ?';
    params.push(limit);

    const stmt = db.prepare(query);
    const results = stmt.all(...params) as Array<{
      subject: string;
      predicate: string;
      object: string;
      confidence: number;
    }>;
    stmt.finalize();

    return results.map(r => ({
      subject: r.subject,
      predicate: r.predicate,
      object: r.object,
      confidence: r.confidence
    }));
  } catch (error) {
    console.error('Failed to query knowledge graph:', error);
    throw new Error(`Query failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * 查找两个实体之间的路径（最多2跳）
 *
 * @param startEntity 起始实体
 * @param endEntity 目标实体
 * @param maxHops 最大跳数，默认2
 * @returns 找到的路径数组
 */
export async function findKnowledgePaths(
  startEntity: string,
  endEntity: string,
  maxHops: number = 2
): Promise<KnowledgePath[]> {
  const db = DatabaseManager.getConnection();
  const paths: KnowledgePath[] = [];

  try {
    // 1跳：直接连接
    const direct = db.prepare(`
      SELECT subject, predicate, object, confidence
      FROM knowledge_triples
      WHERE subject LIKE ? AND object LIKE ?
    `).all(`%${startEntity}%`, `%${endEntity}%`) as KnowledgeTriple[];

    for (const triple of direct) {
      paths.push({
        path: [triple],
        confidence: triple.confidence
      });
    }

    // 2跳：通过中间实体
    if (maxHops >= 2) {
      const firstHop = db.prepare(`
        SELECT subject, predicate, object, confidence
        FROM knowledge_triples
        WHERE subject LIKE ?
      `).all(`%${startEntity}%`) as KnowledgeTriple[];

      for (const first of firstHop) {
        const secondHop = db.prepare(`
          SELECT subject, predicate, object, confidence
          FROM knowledge_triples
          WHERE subject LIKE ? AND object LIKE ?
        `).all(`%${first.object}%`, `%${endEntity}%`) as KnowledgeTriple[];

        for (const second of secondHop) {
          paths.push({
            path: [first, second],
            confidence: Math.min(first.confidence, second.confidence)
          });
        }
      }
    }

    // 按置信度排序
    paths.sort((a, b) => b.confidence - a.confidence);

    return paths;
  } catch (error) {
    console.error('Failed to find knowledge paths:', error);
    throw new Error(`Path finding failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 性能监控装饰器（可选）
function measurePerformance<T extends (...args: any[]) => Promise<any>>(
  target: T,
  context: ClassMethodDecoratorContext
) {
  return function (this: any, ...args: Parameters<T>): ReturnType<T> {
    const start = performance.now();
    const result = target.call(this, ...args);

    if (result instanceof Promise) {
      return result.then(res => {
        const duration = performance.now() - start;
        if (duration > 100) { // 超过100ms记录警告
          console.warn(`Performance warning: ${String(context.name)} took ${duration.toFixed(2)}ms`);
        }
        return res;
      }) as ReturnType<T>;
    }

    return result;
  };
}

// 导出类型
export type { LogTurnParams, RetrieveOptions, ContextResult, ConsolidationOptions };
