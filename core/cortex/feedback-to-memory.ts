#!/usr/bin/env bun
/**
 * Feedback to Memory - 反馈写记忆
 *
 * 功能:
 * 1. 提取高价值反馈（负面反馈作为教训）
 * 2. 写入 evo_memory_semantic
 * 3. 更新 evo_memory_procedural 的熟练度
 *
 * 解决断点 #3: 反馈不写入记忆
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface FeedbackRecord {
  feedback_id: string;
  trigger_text: string;
  signal_type: string;
  related_model?: string;
  session_id?: string;
  turn_id?: number;
}

interface MemoryStats {
  lessons: number;
  experiences: number;
  total: number;
}

export class FeedbackToMemory {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
  }

  /**
   * 将负面反馈写入语义记忆（作为教训）
   */
  writeLessonsToMemory(): number {
    console.log('  📝 提取负面反馈作为教训...');

    // 提取负面反馈
    const negativeFeedback = this.db.query<FeedbackRecord>(`
      SELECT
        feedback_id,
        trigger_text,
        signal_type,
        related_model,
        session_id,
        turn_id
      FROM evo_feedback_v2
      WHERE signal_type IN ('explicit_negative', 'task_failure')
        AND feedback_id NOT IN (
          SELECT json_extract(value, '$.source')
          FROM evo_memory_semantic
          WHERE namespace = 'lessons'
            AND json_extract(value, '$.source') IS NOT NULL
        )
      ORDER BY created_at DESC
      LIMIT 50
    `).all();

    if (negativeFeedback.length === 0) {
      console.log('    ℹ️  没有新的负面反馈需要处理');
      return 0;
    }

    // 写入记忆
    const insert = this.db.prepare(`
      INSERT INTO evo_memory_semantic (namespace, key, value, confidence)
      VALUES ('lessons', ?, ?, 0.7)
    `);

    let count = 0;
    for (const fb of negativeFeedback) {
      const key = `lesson_${fb.feedback_id}`;
      const value = JSON.stringify({
        source: fb.feedback_id,
        context: fb.trigger_text,
        type: fb.signal_type,
        model: fb.related_model || 'unknown',
        session: fb.session_id || 'unknown',
        turn: fb.turn_id || 0,
        lesson: '待人工分析提取',  // 后续可用 LLM 自动提取
        timestamp: new Date().toISOString()
      });

      try {
        insert.run(key, value);
        count++;
      } catch (error: any) {
        // 忽略重复键错误
        if (!error.message.includes('UNIQUE constraint failed')) {
          console.error(`    ⚠️  插入失败 [${key}]:`, error.message);
        }
      }
    }

    console.log(`    ✅ 写入 ${count} 条教训`);
    return count;
  }

  /**
   * 将正面反馈写入语义记忆（作为成功经验）
   */
  writeExperiencesToMemory(): number {
    console.log('  📝 提取正面反馈作为经验...');

    // 提取正面反馈
    const positiveFeedback = this.db.query<FeedbackRecord>(`
      SELECT
        feedback_id,
        trigger_text,
        signal_type,
        related_model,
        session_id,
        turn_id
      FROM evo_feedback_v2
      WHERE signal_type IN ('explicit_positive', 'task_success')
        AND feedback_id NOT IN (
          SELECT json_extract(value, '$.source')
          FROM evo_memory_semantic
          WHERE namespace = 'experiences'
            AND json_extract(value, '$.source') IS NOT NULL
        )
      ORDER BY created_at DESC
      LIMIT 50
    `).all();

    if (positiveFeedback.length === 0) {
      console.log('    ℹ️  没有新的正面反馈需要处理');
      return 0;
    }

    // 写入记忆
    const insert = this.db.prepare(`
      INSERT INTO evo_memory_semantic (namespace, key, value, confidence)
      VALUES ('experiences', ?, ?, 0.8)
    `);

    let count = 0;
    for (const fb of positiveFeedback) {
      const key = `experience_${fb.feedback_id}`;
      const value = JSON.stringify({
        source: fb.feedback_id,
        context: fb.trigger_text,
        type: fb.signal_type,
        model: fb.related_model || 'unknown',
        session: fb.session_id || 'unknown',
        turn: fb.turn_id || 0,
        insight: '待人工分析提取',
        timestamp: new Date().toISOString()
      });

      try {
        insert.run(key, value);
        count++;
      } catch (error: any) {
        if (!error.message.includes('UNIQUE constraint failed')) {
          console.error(`    ⚠️  插入失败 [${key}]:`, error.message);
        }
      }
    }

    console.log(`    ✅ 写入 ${count} 条经验`);
    return count;
  }

  /**
   * 获取记忆统计
   */
  getMemoryStats(): MemoryStats {
    const stats = this.db.query<{
      namespace: string;
      count: number;
    }>(`
      SELECT namespace, COUNT(*) as count
      FROM evo_memory_semantic
      WHERE namespace IN ('lessons', 'experiences')
      GROUP BY namespace
    `).all();

    const result: MemoryStats = {
      lessons: 0,
      experiences: 0,
      total: 0
    };

    for (const row of stats) {
      if (row.namespace === 'lessons') result.lessons = row.count;
      if (row.namespace === 'experiences') result.experiences = row.count;
      result.total += row.count;
    }

    return result;
  }

  /**
   * 显示记忆统计
   */
  displayStats(): void {
    const stats = this.getMemoryStats();

    console.log('\n📊 记忆统计:');
    console.log(`  教训 (lessons): ${stats.lessons}`);
    console.log(`  经验 (experiences): ${stats.experiences}`);
    console.log(`  总计: ${stats.total}`);

    // 显示最近的教训
    if (stats.lessons > 0) {
      console.log('\n🔍 最近 3 条教训:');
      const recentLessons = this.db.query<{
        key: string;
        context: string;
        model: string;
      }>(`
        SELECT
          key,
          json_extract(value, '$.context') as context,
          json_extract(value, '$.model') as model
        FROM evo_memory_semantic
        WHERE namespace = 'lessons'
        ORDER BY created_at DESC
        LIMIT 3
      `).all();

      for (const lesson of recentLessons) {
        const contextShort = lesson.context.length > 60
          ? lesson.context.substring(0, 60) + '...'
          : lesson.context;
        console.log(`  • [${lesson.model}] ${contextShort}`);
      }
    }
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 Feedback to Memory 启动\n');

    try {
      // 1. 检查反馈数据
      const feedbackCount = this.db.query<{ count: number }>(`
        SELECT COUNT(*) as count FROM evo_feedback_v2
      `).get()?.count || 0;

      if (feedbackCount === 0) {
        console.log('⚠️  警告: evo_feedback_v2 表为空');
        console.log('   请先运行 feedback-miner.ts 提取反馈');
        return;
      }

      console.log(`📋 已有 ${feedbackCount} 条反馈\n`);

      // 2. 写入教训
      const lessons = this.writeLessonsToMemory();

      // 3. 写入经验
      const experiences = this.writeExperiencesToMemory();

      console.log(`\n✅ 写入完成: 教训=${lessons}, 经验=${experiences}`);

      // 4. 显示统计
      this.displayStats();

    } catch (error) {
      console.error('❌ 执行失败:', error);
      throw error;
    } finally {
      this.db.close();
    }
  }
}

// CLI 入口
if (import.meta.main) {
  const converter = new FeedbackToMemory();
  await converter.run();
}
