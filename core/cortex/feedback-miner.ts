#!/usr/bin/env bun
/**
 * 用户反馈信号挖掘器
 * 从轨迹数据中提取显式和隐式的用户反馈信号
 */

import { Database } from 'bun:sqlite';
import path from 'path';

// 信号类型定义
type SignalType =
  | 'explicit_positive'    // 显式正向
  | 'implicit_positive'    // 隐式正向
  | 'explicit_negative'    // 显式负向
  | 'implicit_negative'    // 隐式负向
  | 'task_success'         // 任务成功
  | 'task_failure';        // 任务失败

interface TraceRecord {
  trace_id: string;
  session_id: string;
  user_query: string;
  response_summary: string;
  status?: string;
  started_at: string;
}

interface FeedbackSignal {
  feedback_id: string;
  session_id: string;
  turn_id: number;
  signal_type: SignalType;
  feedback_value: number;
  trigger_text: string;
  related_model: string;
  task_type: string;
}

class FeedbackMiner {
  private db: Database;

  // 信号检测模式
  private readonly patterns = {
    explicit_positive: [
      /^(好|OK|可以|谢谢|棒|厉害|搞定|完美|不错|对|是|正确|好的|行)$/i,
      /好[！!。.]|谢谢[！!。.]|棒[！!。.]|厉害[！!。.]/i,
      /^ok$|^yes$|^good$|^great$|^perfect$/i
    ],
    implicit_positive: [
      /^(继续|嗯|懂了|明白|了解|知道了|行|好的|继续吧|ok|可以)$/i,
      /^继续/
    ],
    explicit_negative: [
      /不对|错了|重来|不好|问题|bug|失败|错误|不行|no|wrong|bad|fail|error/i
    ],
    implicit_negative: [
      /你没想到|漏了|应该是|其实是|补充|还有|另外|还要|别忘了|注意/i
    ]
  };

  constructor() {
    const homeDir = process.env.HOME || '.';
    const dbPath = path.join(homeDir, '.solar', 'solar.db');
    this.db = new Database(dbPath);
    this.ensureTables();
  }

  private ensureTables(): void {
    // 创建已处理记录表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS processed_feedback_traces (
        trace_id TEXT PRIMARY KEY,
        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  private getUnprocessedTraces(): TraceRecord[] {
    const query = this.db.query(`
      SELECT
        t.trace_id,
        t.session_id,
        t.user_query,
        t.response_summary,
        t.status,
        t.started_at
      FROM evo_traces t
      LEFT JOIN processed_feedback_traces p ON t.trace_id = p.trace_id
      WHERE p.trace_id IS NULL
        AND t.user_query IS NOT NULL
        AND t.user_query != ''
      ORDER BY t.started_at ASC
    `);

    return query.all() as TraceRecord[];
  }

  private detectSignals(text: string): Array<{
    type: SignalType;
    value: number;
    trigger: string;
  }> {
    const signals: Array<{
      type: SignalType;
      value: number;
      trigger: string;
    }> = [];

    const cleanText = text.trim();

    // 检测显式正向信号
    for (const pattern of this.patterns.explicit_positive) {
      if (pattern.test(cleanText)) {
        signals.push({
          type: 'explicit_positive',
          value: 0.85 + Math.random() * 0.15,
          trigger: cleanText.substring(0, 50)
        });
        break;
      }
    }

    // 检测隐式正向信号
    if (signals.length === 0) {
      for (const pattern of this.patterns.implicit_positive) {
        if (pattern.test(cleanText)) {
          signals.push({
            type: 'implicit_positive',
            value: 0.5 + Math.random() * 0.2,
            trigger: cleanText.substring(0, 50)
          });
          break;
        }
      }
    }

    // 检测显式负向信号
    for (const pattern of this.patterns.explicit_negative) {
      if (pattern.test(cleanText)) {
        signals.push({
          type: 'explicit_negative',
          value: -0.8 - Math.random() * 0.2,
          trigger: cleanText.substring(0, 50)
        });
        break;
      }
    }

    // 检测隐式负向信号
    for (const pattern of this.patterns.implicit_negative) {
      if (pattern.test(cleanText)) {
        signals.push({
          type: 'implicit_negative',
          value: -0.3 - Math.random() * 0.3,
          trigger: cleanText.substring(0, 50)
        });
        break;
      }
    }

    return signals;
  }

  private processTrace(trace: TraceRecord, turnId: number): FeedbackSignal[] {
    const feedbacks: FeedbackSignal[] = [];

    // 检测文本信号
    const textSignals = this.detectSignals(trace.user_query);

    // 检测任务状态信号
    const hasNegative = textSignals.some(s => s.type.includes('negative'));

    if (trace.status === 'completed' && !hasNegative && textSignals.length === 0) {
      textSignals.push({
        type: 'task_success',
        value: 0.7,
        trigger: 'status=completed'
      });
    } else if (trace.status === 'failed') {
      textSignals.push({
        type: 'task_failure',
        value: -0.5,
        trigger: 'status=failed'
      });
    }

    // 转换为反馈记录
    for (const signal of textSignals) {
      feedbacks.push({
        feedback_id: `${trace.trace_id}_${signal.type}`,
        session_id: trace.session_id,
        turn_id: turnId,
        signal_type: signal.type,
        feedback_value: signal.value,
        trigger_text: signal.trigger,
        related_model: 'unknown',
        task_type: 'general'
      });
    }

    return feedbacks;
  }

  private saveFeedbacks(feedbacks: FeedbackSignal[]): void {
    const insert = this.db.prepare(`
      INSERT OR REPLACE INTO evo_feedback_v2
      (feedback_id, session_id, turn_id, signal_type, feedback_value,
       trigger_text, related_model, task_type)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const transaction = this.db.transaction((items: FeedbackSignal[]) => {
      for (const feedback of items) {
        insert.run(
          feedback.feedback_id,
          feedback.session_id,
          feedback.turn_id,
          feedback.signal_type,
          feedback.feedback_value,
          feedback.trigger_text,
          feedback.related_model,
          feedback.task_type
        );
      }
    });

    transaction(feedbacks);
  }

  private markAsProcessed(traceIds: string[]): void {
    const insert = this.db.prepare(`
      INSERT OR IGNORE INTO processed_feedback_traces (trace_id)
      VALUES (?)
    `);

    const transaction = this.db.transaction((ids: string[]) => {
      for (const id of ids) {
        insert.run(id);
      }
    });

    transaction(traceIds);
  }

  public async mine(): Promise<void> {
    console.log('🚀 开始挖掘用户反馈信号...');

    // 获取未处理数据
    const unprocessed = this.getUnprocessedTraces();
    console.log(`📊 发现 ${unprocessed.length} 条未处理轨迹`);

    if (unprocessed.length === 0) {
      console.log('✅ 没有需要处理的数据');
      return;
    }

    // 按 session 分组计算 turn_id
    const sessionTurns = new Map<string, number>();

    // 处理每条轨迹
    const allFeedbacks: FeedbackSignal[] = [];
    const processedIds: string[] = [];
    const statsByType: Record<string, number> = {};

    for (const trace of unprocessed) {
      // 计算该 session 的 turn_id
      const currentTurn = sessionTurns.get(trace.session_id) || 0;
      const turnId = currentTurn + 1;
      sessionTurns.set(trace.session_id, turnId);

      try {
        const feedbacks = this.processTrace(trace, turnId);

        if (feedbacks.length > 0) {
          allFeedbacks.push(...feedbacks);
          processedIds.push(trace.trace_id);

          for (const fb of feedbacks) {
            statsByType[fb.signal_type] = (statsByType[fb.signal_type] || 0) + 1;
          }
        } else {
          // 即使没有反馈也标记为已处理
          processedIds.push(trace.trace_id);
        }
      } catch (error) {
        console.error(`  ↳ ${trace.trace_id}: 处理失败`, error);
      }
    }

    // 保存结果
    if (allFeedbacks.length > 0) {
      this.saveFeedbacks(allFeedbacks);
      console.log(`💾 保存 ${allFeedbacks.length} 个反馈信号`);
    }

    // 标记已处理
    this.markAsProcessed(processedIds);
    console.log(`🏷️  标记 ${processedIds.length} 条轨迹为已处理`);

    // 输出统计
    console.log('\n📈 信号类型分布:');
    Object.entries(statsByType).forEach(([type, count]) => {
      console.log(`   ${type}: ${count}`);
    });

    // 查询总统计
    const totalCount = this.db.query('SELECT COUNT(*) as count FROM evo_feedback_v2').get() as { count: number };
    console.log(`\n📊 总反馈记录: ${totalCount.count}`);

    console.log('\n✅ 反馈信号挖掘完成！');
  }

  public close(): void {
    this.db.close();
  }
}

// 运行脚本
async function main() {
  const miner = new FeedbackMiner();

  try {
    await miner.mine();
  } catch (error) {
    console.error('❌ 挖掘过程出错:', error);
    process.exit(1);
  } finally {
    miner.close();
  }
}

if (import.meta.main) {
  main();
}

export { FeedbackMiner };
