#!/usr/bin/env bun
/**
 * Claude Code JSONL 轨迹数据提取器
 * 从 ~/.claude/projects/-Users-lisihao/*.jsonl 提取数据到 SQLite 数据库
 * 支持增量更新和统计输出
 */

import { Database } from 'bun:sqlite';
import fs from 'fs';
import path from 'path';
import { classifyIntent } from './intent-classifier';

// 类型定义
interface JsonlLine {
  type: 'user' | 'assistant' | 'tool_use' | 'tool_result' | 'error' | 'file-history-snapshot';
  sessionId?: string;
  message?: {
    content: string | any[];
    id?: string;
    role?: string;
    model?: string;
    usage?: {
      input_tokens: number;
      output_tokens: number;
    };
  };
  timestamp: string;
  uuid?: string;
  name?: string;
  args?: any;
  result?: any;
}

interface TraceData {
  trace_id: string;
  session_id: string;
  user_query: string;
  intent: string;
  started_at: string;
  ended_at: string | null;
  latency_ms: number | null;
  status: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  response_summary: string;
}

interface SessionData {
  session_id: string;
  started_at: string;
  ended_at: string | null;
  total_turns: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

interface ProcessingStats {
  filesProcessed: number;
  sessionsProcessed: number;
  tracesProcessed: number;
  sessionsSkipped: number;
  errors: string[];
}

class TrajectoryExtractor {
  private db: Database;
  private jsonlDir: string;
  private dbPath: string;
  private processedSessions: Set<string> = new Set();

  constructor() {
    this.jsonlDir = path.join(process.env.HOME || '', '.claude/projects/-Users-lisihao');
    this.dbPath = path.join(process.env.HOME || '', '.solar/solar.db');
    this.db = new Database(this.dbPath);
    this.loadProcessedSessions();
  }

  private loadProcessedSessions(): void {
    try {
      const stmt = this.db.prepare('SELECT DISTINCT session_id FROM evo_traces WHERE session_id IS NOT NULL');
      const rows = stmt.all() as { session_id: string }[];
      this.processedSessions = new Set(rows.map(row => row.session_id));
      console.log(`📋 已处理会话数: ${this.processedSessions.size}`);
    } catch (error) {
      console.warn('加载已处理会话失败:', error);
    }
  }

  private parseJsonlLine(line: string): JsonlLine | null {
    try {
      return JSON.parse(line.trim());
    } catch {
      return null;
    }
  }

  private extractUserQuery(messages: JsonlLine[]): string {
    const userMessage = messages.find(m => m.type === 'user');
    if (!userMessage?.message?.content) return '';

    if (typeof userMessage.message.content === 'string') {
      return userMessage.message.content.substring(0, 500);
    } else if (Array.isArray(userMessage.message.content)) {
      return userMessage.message.content
        .filter((item: any) => item.type === 'text')
        .map((item: any) => item.text)
        .join('\n')
        .substring(0, 500);
    }
    return '';
  }

  private extractResponseSummary(messages: JsonlLine[]): string {
    const assistantMessages = messages.filter(m => m.type === 'assistant');
    if (assistantMessages.length === 0) return '';

    const lastAssistant = assistantMessages[assistantMessages.length - 1];
    if (!lastAssistant.message?.content) return '';

    if (typeof lastAssistant.message.content === 'string') {
      return lastAssistant.message.content.substring(0, 200);
    } else if (Array.isArray(lastAssistant.message.content)) {
      const textContent = lastAssistant.message.content
        .filter((item: any) => item.type === 'text')
        .map((item: any) => item.text)
        .join(' ');
      return textContent.substring(0, 200);
    }
    return '';
  }

  private calculateTokens(messages: JsonlLine[]): { input: number; output: number } {
    let totalInput = 0;
    let totalOutput = 0;

    for (const msg of messages) {
      if (msg.type === 'assistant' && msg.message?.usage) {
        totalInput += msg.message.usage.input_tokens || 0;
        totalOutput += msg.message.usage.output_tokens || 0;
      }
    }

    return { input: totalInput, output: totalOutput };
  }

  private calculateCost(inputTokens: number, outputTokens: number, model?: string): number {
    // 不同模型定价 (每1K tokens)
    const pricing: Record<string, { input: number; output: number }> = {
      'glm-5': { input: 0.001, output: 0.002 },
      'glm-5': { input: 0.0005, output: 0.0005 },
      'gemini-2.5-pro': { input: 0.00125, output: 0.005 },
      'deepseek-v3': { input: 0.0014, output: 0.0028 },
      'claude-sonnet': { input: 0.003, output: 0.015 },
      'claude-opus': { input: 0.015, output: 0.075 },
    };

    const price = pricing[model || 'glm-5'] || pricing['glm-5'];
    const inputCost = (inputTokens / 1000) * price.input;
    const outputCost = (outputTokens / 1000) * price.output;
    return parseFloat((inputCost + outputCost).toFixed(6));
  }

  private processSession(sessionId: string, messages: JsonlLine[]): {
    traces: TraceData[];
    session: SessionData | null;
  } {
    if (messages.length === 0) return { traces: [], session: null };

    const traces: TraceData[] = [];
    const userMessages = messages.filter(m => m.type === 'user');

    // 按 user message 分组形成 trace
    for (let i = 0; i < userMessages.length; i++) {
      const userMsg = userMessages[i];
      const userTime = new Date(userMsg.timestamp).getTime();

      // 找到下一个 user message 之前的所有消息
      const nextUserTime = i < userMessages.length - 1
        ? new Date(userMessages[i + 1].timestamp).getTime()
        : Infinity;

      const traceMessages = messages.filter(m => {
        const t = new Date(m.timestamp).getTime();
        return t >= userTime && t < nextUserTime;
      });

      const responseSummary = this.extractResponseSummary(traceMessages);
      const { input: totalInputTokens, output: totalOutputTokens } = this.calculateTokens(traceMessages);

      // 获取模型名
      const assistantMsg = traceMessages.find(m => m.type === 'assistant');
      const model = assistantMsg?.message?.model;

      const userQuery = this.extractUserQuery([userMsg]);
      const intentResult = classifyIntent(userQuery);

      const trace: TraceData = {
        trace_id: userMsg.uuid || `trace_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        session_id: sessionId,
        user_query: userQuery,
        intent: JSON.stringify(intentResult),
        started_at: userMsg.timestamp,
        ended_at: traceMessages.length > 1 ? traceMessages[traceMessages.length - 1].timestamp : null,
        latency_ms: traceMessages.length > 1
          ? new Date(traceMessages[traceMessages.length - 1].timestamp).getTime() - userTime
          : null,
        status: assistantMsg ? 'completed' : 'in_progress',
        total_input_tokens: totalInputTokens,
        total_output_tokens: totalOutputTokens,
        total_cost_usd: this.calculateCost(totalInputTokens, totalOutputTokens, model),
        response_summary: responseSummary
      };

      traces.push(trace);
    }

    // 汇总 session 数据
    const timestamps = messages.map(m => new Date(m.timestamp).getTime());
    const { input, output } = this.calculateTokens(messages);

    const session: SessionData = {
      session_id: sessionId,
      started_at: new Date(Math.min(...timestamps)).toISOString(),
      ended_at: new Date(Math.max(...timestamps)).toISOString(),
      total_turns: userMessages.length,
      total_input_tokens: input,
      total_output_tokens: output,
      total_cost_usd: traces.reduce((sum, t) => sum + t.total_cost_usd, 0)
    };

    return { traces, session };
  }

  private insertTrace(trace: TraceData): void {
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO evo_traces
      (trace_id, session_id, user_query, intent, started_at, ended_at, latency_ms, status,
       total_input_tokens, total_output_tokens, total_cost_usd, response_summary)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      trace.trace_id,
      trace.session_id,
      trace.user_query,
      trace.intent,
      trace.started_at,
      trace.ended_at,
      trace.latency_ms,
      trace.status,
      trace.total_input_tokens,
      trace.total_output_tokens,
      trace.total_cost_usd,
      trace.response_summary
    );
  }

  private insertSession(session: SessionData): void {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO evo_sessions
      (session_id, started_at, ended_at, total_turns, total_input_tokens, total_output_tokens, total_cost_usd)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      session.session_id,
      session.started_at,
      session.ended_at,
      session.total_turns,
      session.total_input_tokens,
      session.total_output_tokens,
      session.total_cost_usd
    );
  }

  private processFile(filePath: string): ProcessingStats {
    const stats: ProcessingStats = {
      filesProcessed: 0,
      sessionsProcessed: 0,
      tracesProcessed: 0,
      sessionsSkipped: 0,
      errors: []
    };

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const lines = content.split('\n').filter(line => line.trim());

      // 按 sessionId 分组消息
      const sessions = new Map<string, JsonlLine[]>();

      for (const line of lines) {
        const data = this.parseJsonlLine(line);
        if (!data || !data.sessionId) continue;

        if (!sessions.has(data.sessionId)) {
          sessions.set(data.sessionId, []);
        }
        sessions.get(data.sessionId)!.push(data);
      }

      // 处理每个会话
      for (const [sessionId, messages] of sessions) {
        if (this.processedSessions.has(sessionId)) {
          stats.sessionsSkipped++;
          continue;
        }

        try {
          const { traces, session } = this.processSession(sessionId, messages);

          if (session && traces.length > 0) {
            this.db.run('BEGIN TRANSACTION');

            try {
              this.insertSession(session);
              for (const trace of traces) {
                this.insertTrace(trace);
              }

              this.db.run('COMMIT');
              this.processedSessions.add(sessionId);
              stats.sessionsProcessed++;
              stats.tracesProcessed += traces.length;
            } catch (error) {
              this.db.run('ROLLBACK');
              throw error;
            }
          }
        } catch (error) {
          stats.errors.push(`Session ${sessionId}: ${error}`);
        }
      }

      stats.filesProcessed = 1;
    } catch (error) {
      stats.errors.push(`File ${filePath}: ${error}`);
    }

    return stats;
  }

  public async run(): Promise<void> {
    console.log('🚀 开始提取轨迹数据...');
    console.log(`📁 JSONL 目录: ${this.jsonlDir}`);
    console.log(`🗄️  数据库: ${this.dbPath}`);

    // 查找所有 JSONL 文件
    const files = fs.readdirSync(this.jsonlDir)
      .filter(f => f.endsWith('.jsonl'))
      .map(f => path.join(this.jsonlDir, f));

    console.log(`📄 找到 ${files.length} 个 JSONL 文件`);

    if (files.length === 0) {
      console.log('⚠️  未找到 JSONL 文件');
      return;
    }

    const totalStats: ProcessingStats = {
      filesProcessed: 0,
      sessionsProcessed: 0,
      tracesProcessed: 0,
      sessionsSkipped: 0,
      errors: []
    };

    // 处理每个文件
    for (const file of files) {
      console.log(`\n🔍 处理文件: ${path.basename(file)}`);
      const stats = this.processFile(file);

      totalStats.filesProcessed += stats.filesProcessed;
      totalStats.sessionsProcessed += stats.sessionsProcessed;
      totalStats.tracesProcessed += stats.tracesProcessed;
      totalStats.sessionsSkipped += stats.sessionsSkipped;
      totalStats.errors.push(...stats.errors);

      if (stats.sessionsProcessed > 0) {
        console.log(`   ✅ 会话: +${stats.sessionsProcessed}, 轨迹: +${stats.tracesProcessed}`);
      }
    }

    // 输出统计
    console.log('\n📊 处理统计:');
    console.log(`   文件处理: ${totalStats.filesProcessed}/${files.length}`);
    console.log(`   会话处理: ${totalStats.sessionsProcessed}`);
    console.log(`   轨迹处理: ${totalStats.tracesProcessed}`);
    console.log(`   会话跳过: ${totalStats.sessionsSkipped}`);
    console.log(`   错误数量: ${totalStats.errors.length}`);

    if (totalStats.errors.length > 0 && totalStats.errors.length <= 10) {
      console.log('\n❌ 错误详情:');
      totalStats.errors.forEach((error, i) => {
        console.log(`   ${i + 1}. ${error}`);
      });
    }

    // 验证数据
    this.verifyData();

    console.log('\n🎉 轨迹数据提取完成!');
  }

  private verifyData(): void {
    console.log('\n🔍 数据验证:');

    try {
      const sessionCount = this.db.prepare('SELECT COUNT(*) as count FROM evo_sessions').get() as { count: number };
      const traceCount = this.db.prepare('SELECT COUNT(*) as count FROM evo_traces').get() as { count: number };

      console.log(`   会话表记录: ${sessionCount.count}`);
      console.log(`   轨迹表记录: ${traceCount.count}`);

      // 检查最近的数据
      const recentSessions = this.db.prepare(`
        SELECT session_id, started_at, total_turns
        FROM evo_sessions
        ORDER BY started_at DESC
        LIMIT 5
      `).all() as SessionData[];

      console.log('\n📅 最近会话:');
      recentSessions.forEach((session: any) => {
        console.log(`   ${session.session_id?.substring(0, 8)}: ${session.started_at?.substring(0, 10)} (${session.total_turns} 轮)`);
      });

    } catch (error) {
      console.log(`   验证失败: ${error}`);
    }
  }

  public close(): void {
    this.db.close();
  }
}

// 主函数
async function main() {
  const extractor = new TrajectoryExtractor();

  try {
    await extractor.run();
  } catch (error) {
    console.error('❌ 处理失败:', error);
    process.exit(1);
  } finally {
    extractor.close();
  }
}

// 运行脚本
if (import.meta.main) {
  main().catch(console.error);
}

export { TrajectoryExtractor };
