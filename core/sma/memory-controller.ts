import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';

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
      return 0;
    }

    // 获取会话内容
    const contentStmt = db.prepare(`
      SELECT user_input, ai_output
      FROM session_log
      WHERE session_id = ?
      ORDER BY turn_id
    `);
    const contents = contentStmt.all(sessionId) as Array<{
      user_input: string;
      ai_output: string;
    }>;
    contentStmt.finalize();

    // 提取三元组
    const triples: Array<[string, string, string]> = [];

    for (const content of contents) {
      // 简单规则提取
      const text = `${content.user_input} ${content.ai_output}`;

      // 规则1: "X 是 Y" 模式
      const isPattern = text.match(/([^。，！？]+?)是([^。，！？]+?)(?=[。，！？]|$)/g);
      if (isPattern) {
        isPattern.forEach(match => {
          const parts = match.split('是');
          if (parts.length === 2) {
            const subject = parts[0].trim();
            const object = parts[1].trim();
            if (subject && object) {
              triples.push([subject, '是', object]);
            }
          }
        });
      }

      // 规则2: "X 可以 Y" 模式
      const canPattern = text.match(/([^。，！？]+?)可以([^。，！？]+?)(?=[。，！？]|$)/g);
      if (canPattern) {
        canPattern.forEach(match => {
          const parts = match.split('可以');
          if (parts.length === 2) {
            const subject = parts[0].trim();
            const object = parts[1].trim();
            if (subject && object) {
              triples.push([subject, '可以', object]);
            }
          }
        });
      }

      // 规则3: "X 有 Y" 模式
      const havePattern = text.match(/([^。，！？]+?)有([^。，！？]+?)(?=[。，！？]|$)/g);
      if (havePattern) {
        havePattern.forEach(match => {
          const parts = match.split('有');
          if (parts.length === 2) {
            const subject = parts[0].trim();
            const object = parts[1].trim();
            if (subject && object) {
              triples.push([subject, '有', object]);
            }
          }
        });
      }
    }

    // 去重并写入数据库
    const uniqueTriples = Array.from(
      new Set(triples.map(t => JSON.stringify(t)))
    ).map(str => JSON.parse(str) as [string, string, string]);

    if (uniqueTriples.length > 0) {
      const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO knowledge_triples
        (subject, predicate, object, confidence, created_at)
        VALUES (?, ?, ?, 0.5, unixepoch())
      `);

      db.transaction(() => {
        for (const [subject, predicate, object] of uniqueTriples) {
          insertStmt.run(subject, predicate, object);
        }
      })();

      insertStmt.finalize();
    }

    return uniqueTriples.length;
  } catch (error) {
    console.error('Failed to trigger consolidation:', error);
    throw new Error(`Consolidation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
