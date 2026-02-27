#!/usr/bin/env bun
/**
 * SMA RAG Retriever - P2 检索策略实现
 *
 * 设计来源: 审判官 + 探索派专家会审
 *
 * 核心机制:
 * 1. Entity Anchoring - 从用户 prompt 提取锚点实体
 * 2. FTS5 全文检索 - L2 session_log 高效检索
 * 3. 时间衰减排序 - 优先最近相关内容
 * 4. L3 1-hop 扩展 - 知识图谱邻居检索
 * 5. 冲突检测 - L2/L3 矛盾标记
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';

const DB_PATH = path.join(os.homedir(), '.solar', 'solar.db');

// ==================== Types ====================

export interface RAGResult {
  turns: TurnResult[];
  triples: TripleResult[];
  conflicts: ConflictInfo[];
  metadata: {
    queryTime: number;
    anchorsFound: number;
    l2Hits: number;
    l3Hits: number;
  };
}

export interface TurnResult {
  turn_id: number;
  session_id: string;
  user_input: string;
  ai_output: string;
  timestamp: number;
  score: number;
  // Aliases for compatibility
  turnId?: number;
  sessionId?: string;
  userInput?: string;
  aiOutput?: string;
}

export interface TripleResult {
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
  type: 'direct' | 'indirect';
}

export interface ConflictInfo {
  l2Fact: string;
  l3Fact: string;
  reason: string;
}

// ==================== Stop Words ====================

const STOP_WORDS = new Set([
  // 中文停用词
  '的', '是', '在', '有', '和', '了', '不', '这', '我', '你', '他', '她', '它',
  '就', '也', '都', '会', '说', '要', '对', '能', '到', '那', '个', '们', '着',
  '又', '为', '但', '可以', '这个', '那个', '什么', '怎么', '如何', '为什么',
  // 英文停用词
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
  'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'whose',
  'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where', 'why', 'how',
  'for', 'from', 'to', 'of', 'in', 'on', 'at', 'by', 'with', 'about', 'as'
]);

// ==================== Tokenizer ====================

/**
 * 简单分词器 - 中英文混合
 */
function tokenize(text: string): string[] {
  const tokens: string[] = [];

  // 英文单词
  const englishWords = text.match(/[a-zA-Z][a-zA-Z0-9_-]*/g) || [];
  tokens.push(...englishWords.map(w => w.toLowerCase()));

  // 中文词汇（简单按字切分，实际可用 jieba）
  const chineseChars = text.match(/[\u4e00-\u9fa5]+/g) || [];
  for (const phrase of chineseChars) {
    // 2-gram 切分
    for (let i = 0; i < phrase.length - 1; i++) {
      tokens.push(phrase.substring(i, i + 2));
    }
    // 也保留完整词
    if (phrase.length >= 2 && phrase.length <= 6) {
      tokens.push(phrase);
    }
  }

  // 过滤停用词和短词
  return tokens.filter(t => t.length >= 2 && !STOP_WORDS.has(t));
}

// ==================== Entity Anchoring ====================

/**
 * Step 1: Entity Anchoring - 从 prompt 提取锚点
 *
 * 逻辑:
 * 1. 对 prompt 分词
 * 2. 与 L3 的 subject 集合求交集
 * 3. 命中的词作为锚点
 */
function extractAnchors(prompt: string, knownSubjects: Set<string>): string[] {
  const tokens = tokenize(prompt);
  const anchors: string[] = [];

  for (const token of tokens) {
    // 精确匹配
    if (knownSubjects.has(token)) {
      anchors.push(token);
      continue;
    }

    // 模糊匹配（包含关系）
    for (const subject of knownSubjects) {
      if (subject.includes(token) || token.includes(subject)) {
        anchors.push(subject);
        break;
      }
    }
  }

  return [...new Set(anchors)]; // 去重
}

/**
 * 获取所有已知 subject（缓存）
 */
let subjectCache: Set<string> | null = null;
let subjectCacheTime = 0;

function getKnownSubjects(db: Database): Set<string> {
  const now = Date.now();

  // 缓存 5 分钟
  if (subjectCache && (now - subjectCacheTime) < 300000) {
    return subjectCache;
  }

  const stmt = db.prepare('SELECT DISTINCT subject FROM knowledge_triples');
  const results = stmt.all() as { subject: string }[];
  stmt.finalize();

  subjectCache = new Set(results.map(r => r.subject));
  subjectCacheTime = now;

  return subjectCache;
}

// ==================== Query Generation ====================

/**
 * Step 2: 生成 FTS5 查询
 *
 * 策略:
 * - 有锚点: anchor1 OR anchor2 OR 其他词
 * - 无锚点: 词1 OR 词2
 * 注意: FTS5 不支持 ^ boost 语法，改用重复锚点提升权重
 */
function generateFTSQuery(prompt: string, anchors: string[]): string {
  const tokens = tokenize(prompt);

  if (anchors.length === 0) {
    // 无锚点，使用简单 OR 查询
    if (tokens.length === 0) {
      return '';
    }
    return tokens.slice(0, 5).join(' OR ');
  }

  // 有锚点，boost 锚点
  const anchorQuery = anchors.map(a => `"${a}"`).join(' OR ');
  const otherTokens = tokens.filter(t => !anchors.includes(t)).slice(0, 3);

  if (otherTokens.length === 0) {
    // FTS5: 通过重复锚点提升权重
    return `${anchorQuery} ${anchorQuery}`;
  }

  const otherQuery = otherTokens.join(' OR ');
  // FTS5: 锚点放前面，其他词放后面
  return `${anchorQuery} OR (${otherQuery})`;
}

// ==================== L2 Retrieval ====================

/**
 * Step 3: L2 检索 - FTS5 + 时间衰减
 *
 * 排序公式: bm25() * (1 / (1 + (now - timestamp) / 3600))
 * 半衰期约 1 小时
 */
function retrieveL2(
  db: Database,
  ftsQuery: string,
  options: { limit?: number } = {}
): { turns: TurnResult[], time: number } {
  const start = performance.now();
  const limit = options.limit || 10;

  if (!ftsQuery) {
    // 空查询，返回最近的对话
    const stmt = db.prepare(`
      SELECT
        session_id, turn_id, user_input, ai_output, timestamp,
        0.5 as score
      FROM session_log
      ORDER BY timestamp DESC
      LIMIT ?
    `);
    const turns = stmt.all(limit) as TurnResult[];
    stmt.finalize();

    return { turns, time: performance.now() - start };
  }

  // 检查 FTS 表是否存在
  const tableCheck = db.prepare(`
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='session_log_fts'
  `).get();

  if (!tableCheck) {
    // FTS 表不存在，回退到 LIKE 查询
    console.warn('FTS table not found, falling back to LIKE query');
    return retrieveL2Fallback(db, ftsQuery, limit);
  }

  // FTS5 检索 + 时间衰减
  // 先从 FTS 获取 rowid，再 join 原表获取完整数据
  const stmt = db.prepare(`
    SELECT
      sl.session_id, sl.turn_id, sl.user_input, sl.ai_output, sl.timestamp,
      bm25(session_log_fts) * (1.0 / (1.0 + (strftime('%s', 'now') - sl.timestamp) / 3600.0)) as score
    FROM session_log_fts fts
    JOIN session_log sl ON fts.rowid = sl.log_id
    WHERE session_log_fts MATCH ?
    ORDER BY score DESC
    LIMIT ?
  `);

  const turns = stmt.all(ftsQuery, limit) as TurnResult[];
  stmt.finalize();

  return { turns, time: performance.now() - start };
}

/**
 * FTS 回退方案 - LIKE 查询
 */
function retrieveL2Fallback(db: Database, query: string, limit: number): { turns: TurnResult[], time: number } {
  const start = performance.now();

  // 提取关键词
  const keywords = query.replace(/["()^]/g, '').split(/\s+OR\s+/).filter(k => k.length > 0);

  if (keywords.length === 0) {
    return { turns: [], time: performance.now() - start };
  }

  const conditions = keywords.map(() => '(user_input LIKE ? OR ai_output LIKE ?)').join(' OR ');
  const params = keywords.flatMap(k => [`%${k}%`, `%${k}%`]);

  const stmt = db.prepare(`
    SELECT
      session_id, turn_id, user_input, ai_output, timestamp,
      (1.0 / (1.0 + (strftime('%s', 'now') - timestamp) / 3600.0)) as score
    FROM session_log
    WHERE ${conditions}
    ORDER BY score DESC
    LIMIT ?
  `);

  const turns = stmt.all(...params, limit) as TurnResult[];
  stmt.finalize();

  return { turns, time: performance.now() - start };
}

// ==================== L3 Retrieval ====================

/**
 * Step 4: L3 检索 - 直接匹配 + 1-hop 扩展
 */
function retrieveL3(
  db: Database,
  anchors: string[],
  options: { minConfidence?: number, limit?: number } = {}
): { triples: TripleResult[], time: number } {
  const start = performance.now();
  const minConfidence = options.minConfidence || 0.6;
  const limit = options.limit || 15;

  if (anchors.length === 0) {
    return { triples: [], time: performance.now() - start };
  }

  const placeholders = anchors.map(() => '?').join(',');

  // 直接匹配
  const directStmt = db.prepare(`
    SELECT subject, predicate, object, confidence, 'direct' as type
    FROM knowledge_triples
    WHERE subject IN (${placeholders}) AND confidence >= ?
    UNION
    SELECT subject, predicate, object, confidence, 'direct' as type
    FROM knowledge_triples
    WHERE object IN (${placeholders}) AND confidence >= ?
    ORDER BY confidence DESC
    LIMIT ?
  `);

  const triples = directStmt.all(
    ...anchors, minConfidence,
    ...anchors, minConfidence,
    limit
  ) as TripleResult[];
  directStmt.finalize();

  // 1-hop 扩展（仅对高置信度锚点）
  const highConfAnchors = anchors.slice(0, 3);

  if (highConfAnchors.length > 0 && triples.length < limit) {
    const hopPlaceholders = highConfAnchors.map(() => '?').join(',');

    const hopStmt = db.prepare(`
      SELECT t2.subject, t2.predicate, t2.object, t2.confidence, 'indirect' as type
      FROM knowledge_triples t1
      JOIN knowledge_triples t2 ON t1.object = t2.subject
      WHERE t1.subject IN (${hopPlaceholders})
        AND t1.confidence > 0.8
        AND t2.confidence > 0.7
      LIMIT ?
    `);

    const hopTriples = hopStmt.all(...highConfAnchors, limit - triples.length) as TripleResult[];
    hopStmt.finalize();

    triples.push(...hopTriples);
  }

  return { triples, time: performance.now() - start };
}

// ==================== Conflict Detection ====================

/**
 * Step 5: 冲突检测 - L2/L3 矛盾
 *
 * 简单启发式:
 * - L3 说 X 是 A，但 L2（更新）提到 X 和 B
 */
function detectConflicts(
  turns: TurnResult[],
  triples: TripleResult[]
): ConflictInfo[] {
  const conflicts: ConflictInfo[] = [];

  // 简单实现：检测同主题但不同描述
  const tripleSubjects = new Map<string, TripleResult[]>();
  for (const t of triples) {
    if (!tripleSubjects.has(t.subject)) {
      tripleSubjects.set(t.subject, []);
    }
    tripleSubjects.get(t.subject)!.push(t);
  }

  for (const turn of turns) {
    for (const [subject, relatedTriples] of tripleSubjects) {
      // 检查 turn 是否提到了 subject 但内容与 L3 不同
      const aiOutput = (turn as any).ai_output || turn.aiOutput || '';
      if (aiOutput.includes(subject)) {
        // 检查是否有时间上的矛盾（L2 比 L3 新）
        // 这里简化处理，实际需要更复杂的 NLU
        for (const triple of relatedTriples) {
          if (!turn.aiOutput.includes(triple.object)) {
            // L2 提到 subject 但没提到 L3 记录的 object
            // 可能是状态变化
            conflicts.push({
              l2Fact: `[Turn ${turn.turnId}] 提到 ${subject}`,
              l3Fact: `${triple.subject} ${triple.predicate} ${triple.object}`,
              reason: 'L2 可能包含更新信息'
            });
            break; // 每个 subject 只报一个冲突
          }
        }
      }
    }
  }

  return conflicts.slice(0, 5); // 最多返回 5 个
}

// ==================== Main Entry ====================

/**
 * RAG 检索主入口
 *
 * @param prompt 用户输入
 * @param options 检索选项
 * @returns RAG 结果
 */
export function retrieveWithRAG(
  prompt: string,
  options: {
    l2Limit?: number;
    l3Limit?: number;
    minConfidence?: number;
  } = {}
): RAGResult {
  const totalStart = performance.now();
  const db = new Database(DB_PATH, { readonly: true });

  try {
    // Step 1: Entity Anchoring
    const knownSubjects = getKnownSubjects(db);
    const anchors = extractAnchors(prompt, knownSubjects);

    // Step 2: Query Generation
    const ftsQuery = generateFTSQuery(prompt, anchors);

    // Step 3: L2 Retrieval
    const { turns, time: l2Time } = retrieveL2(db, ftsQuery, { limit: options.l2Limit || 10 });

    // Step 4: L3 Retrieval
    const { triples, time: l3Time } = retrieveL3(db, anchors, {
      minConfidence: options.minConfidence || 0.6,
      limit: options.l3Limit || 15
    });

    // Step 5: Conflict Detection
    const conflicts = detectConflicts(turns, triples);

    const totalTime = performance.now() - totalStart;

    return {
      turns,
      triples,
      conflicts,
      metadata: {
        queryTime: Math.round(totalTime * 100) / 100,
        anchorsFound: anchors.length,
        l2Hits: turns.length,
        l3Hits: triples.length
      }
    };
  } finally {
    db.close();
  }
}

/**
 * 格式化 RAG 结果为 L1 上下文
 */
export function formatRAGContext(result: RAGResult): string {
  const parts: string[] = [];

  // L3 知识（高置信度）
  if (result.triples.length > 0) {
    parts.push('[FACTS]');
    for (const t of result.triples.filter(t => t.confidence >= 0.8).slice(0, 5)) {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object} (Conf: ${t.confidence.toFixed(2)})`);
    }
    parts.push('');
  }

  // L2 会话记忆
  if (result.turns.length > 0) {
    parts.push('[MEMORY]');
    for (const turn of result.turns.slice(0, 5)) {
      const date = new Date(turn.timestamp * 1000).toLocaleDateString('zh-CN');
      const input = (turn as any).user_input || turn.userInput || '';
      parts.push(`- [${date}] User: "${input.slice(0, 50)}..."`);
    }
    parts.push('');
  }

  // 冲突警告
  if (result.conflicts.length > 0) {
    parts.push('[CONFLICT WARNINGS]');
    for (const c of result.conflicts) {
      parts.push(`- L2: ${c.l2Fact} vs L3: ${c.l3Fact}`);
    }
    parts.push('');
  }

  // 元数据
  parts.push(`[META] Query: ${result.metadata.queryTime}ms | Anchors: ${result.metadata.anchorsFound} | L2: ${result.metadata.l2Hits} | L3: ${result.metadata.l3Hits}`);

  return parts.join('\n');
}

// ==================== FTS Table Setup ====================

/**
 * 创建 FTS5 虚拟表（首次使用时调用）
 */
export function setupFTSTables(): void {
  const db = new Database(DB_PATH);

  try {
    // 检查是否已存在
    const exists = db.prepare(`
      SELECT name FROM sqlite_master
      WHERE type='table' AND name='session_log_fts'
    `).get();

    if (exists) {
      console.log('FTS tables already exist');
      return;
    }

    // 创建 FTS5 虚拟表
    db.run(`
      CREATE VIRTUAL TABLE IF NOT EXISTS session_log_fts USING fts5(
        session_id,
        user_input,
        ai_output,
        content='session_log',
        content_rowid='log_id'
      )
    `);

    // 填充初始数据
    db.run(`
      INSERT INTO session_log_fts (rowid, session_id, user_input, ai_output)
      SELECT log_id, session_id, user_input, ai_output FROM session_log
    `);

    // 创建触发器保持同步
    db.run(`
      CREATE TRIGGER IF NOT EXISTS session_log_ai AFTER INSERT ON session_log BEGIN
        INSERT INTO session_log_fts (rowid, session_id, user_input, ai_output)
        VALUES (new.log_id, new.session_id, new.user_input, new.ai_output);
      END
    `);

    db.run(`
      CREATE TRIGGER IF NOT EXISTS session_log_ad AFTER DELETE ON session_log BEGIN
        INSERT INTO session_log_fts (session_log_fts, rowid, session_id, user_input, ai_output)
        VALUES ('delete', old.log_id, old.session_id, old.user_input, old.ai_output);
      END
    `);

    db.run(`
      CREATE TRIGGER IF NOT EXISTS session_log_au AFTER UPDATE ON session_log BEGIN
        INSERT INTO session_log_fts (session_log_fts, rowid, session_id, user_input, ai_output)
        VALUES ('delete', old.log_id, old.session_id, old.user_input, old.ai_output);
        INSERT INTO session_log_fts (rowid, session_id, user_input, ai_output)
        VALUES (new.log_id, new.session_id, new.user_input, new.ai_output);
      END
    `);

    console.log('FTS tables created successfully');
  } finally {
    db.close();
  }
}

// ==================== CLI ====================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'setup') {
    setupFTSTables();
  } else if (command === 'search') {
    const query = args.slice(1).join(' ');
    if (!query) {
      console.error('Usage: bun rag-retriever.ts search <query>');
      process.exit(1);
    }

    const result = retrieveWithRAG(query);
    console.log(formatRAGContext(result));
    console.log('\n--- Raw Result ---');
    console.log(JSON.stringify(result.metadata, null, 2));
  } else {
    console.log(`
Usage:
  bun rag-retriever.ts setup      - Create FTS tables
  bun rag-retriever.ts search <q> - Search with RAG
    `);
  }
}
