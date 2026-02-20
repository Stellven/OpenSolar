#!/usr/bin/env bun
/**
 * Memory-Driven Decision - 记忆驱动决策
 *
 * 功能:
 * 1. 决策前查询相关教训
 * 2. 决策前查询成功经验
 * 3. 生成决策建议
 * 4. 避免重复错误
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface Memory {
  key: string;
  value: any;
  context: string;
  confidence: number;
}

interface DecisionAdvice {
  related_lessons: Memory[];
  related_experiences: Memory[];
  warnings: string[];
  recommendations: string[];
  best_practices: string[];
}

export class MemoryDrivenDecision {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
  }

  /**
   * 根据任务描述查询相关记忆
   */
  queryRelevantMemories(taskDescription: string): DecisionAdvice {
    // 提取关键词
    const keywords = this.extractKeywords(taskDescription);

    // 查询相关教训
    const lessons = this.queryLessons(keywords);

    // 查询相关经验
    const experiences = this.queryExperiences(keywords);

    // 生成建议
    const warnings = this.extractWarnings(lessons);
    const recommendations = this.extractRecommendations(experiences);
    const bestPractices = this.extractBestPractices(experiences);

    return {
      related_lessons: lessons,
      related_experiences: experiences,
      warnings,
      recommendations,
      best_practices: bestPractices
    };
  }

  /**
   * 提取关键词
   */
  private extractKeywords(text: string): string[] {
    // 简单的关键词提取（可以后续用 NLP 改进）
    const stopWords = new Set(['的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这']);

    const words = text.toLowerCase()
      .replace(/[^\u4e00-\u9fa5a-zA-Z0-9\s]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 1 && !stopWords.has(w));

    return [...new Set(words)].slice(0, 10);
  }

  /**
   * 查询相关教训
   */
  private queryLessons(keywords: string[]): Memory[] {
    const memories: Memory[] = [];

    for (const keyword of keywords) {
      const results = this.db.query<{
        key: string;
        value: string;
        confidence: number;
      }>(`
        SELECT key, value, confidence
        FROM evo_memory_semantic
        WHERE namespace = 'lessons'
          AND (
            json_extract(value, '$.context') LIKE ?
            OR json_extract(value, '$.lesson') LIKE ?
          )
        ORDER BY confidence DESC
        LIMIT 3
      `).all(`%${keyword}%`, `%${keyword}%`);

      for (const r of results) {
        try {
          const value = JSON.parse(r.value);
          memories.push({
            key: r.key,
            value,
            context: value.context || '',
            confidence: r.confidence
          });
        } catch (e) {
          // 忽略解析错误
        }
      }
    }

    // 去重
    const uniqueMap = new Map(memories.map(m => [m.key, m]));
    return Array.from(uniqueMap.values()).slice(0, 5);
  }

  /**
   * 查询相关经验
   */
  private queryExperiences(keywords: string[]): Memory[] {
    const memories: Memory[] = [];

    for (const keyword of keywords) {
      const results = this.db.query<{
        key: string;
        value: string;
        confidence: number;
      }>(`
        SELECT key, value, confidence
        FROM evo_memory_semantic
        WHERE namespace = 'experiences'
          AND (
            json_extract(value, '$.context') LIKE ?
            OR json_extract(value, '$.insight') LIKE ?
          )
        ORDER BY confidence DESC
        LIMIT 3
      `).all(`%${keyword}%`, `%${keyword}%`);

      for (const r of results) {
        try {
          const value = JSON.parse(r.value);
          memories.push({
            key: r.key,
            value,
            context: value.context || '',
            confidence: r.confidence
          });
        } catch (e) {
          // 忽略解析错误
        }
      }
    }

    // 去重
    const uniqueMap = new Map(memories.map(m => [m.key, m]));
    return Array.from(uniqueMap.values()).slice(0, 5);
  }

  /**
   * 提取警告
   */
  private extractWarnings(lessons: Memory[]): string[] {
    // 从教训中提取关键警告
    const warnings: string[] = [];

    for (const lesson of lessons) {
      if (lesson.value.type === 'explicit_negative') {
        warnings.push(`⚠️ 避免重复错误: ${lesson.context.substring(0, 100)}...`);
      } else if (lesson.value.type === 'task_failure') {
        warnings.push(`❌ 曾失败: ${lesson.context.substring(0, 100)}...`);
      }
    }

    return warnings;
  }

  /**
   * 提取建议
   */
  private extractRecommendations(experiences: Memory[]): string[] {
    const recommendations: string[] = [];

    for (const exp of experiences) {
      if (exp.value.model) {
        recommendations.push(`✅ 推荐使用模型: ${exp.value.model}`);
      }
    }

    return [...new Set(recommendations)];
  }

  /**
   * 提取最佳实践
   */
  private extractBestPractices(experiences: Memory[]): string[] {
    // 生成最佳实践建议
    const practices: string[] = [];

    const topModels = this.db.query<{ model: string }>(`
      SELECT entity_id as model
      FROM sys_quality_scores
      WHERE entity_type = 'model'
      ORDER BY satisfaction DESC
      LIMIT 3
    `).all();

    if (topModels.length > 0) {
      practices.push(`📋 推荐模型: ${topModels.map(m => m.model).join(', ')}`);
    }

    return practices;
  }

  /**
   * 生成决策报告
   */
  generateDecisionReport(taskDescription: string): void {
    console.log('🎯 Memory-Driven Decision Report\n');
    console.log('═'.repeat(60) + '\n');

    const advice = this.queryRelevantMemories(taskDescription);

    console.log(`📝 任务: ${taskDescription.substring(0, 100)}...\n`);

    // 1. 警告
    if (advice.warnings.length > 0) {
      console.log('⚠️  历史教训 (避免重复错误):');
      for (const w of advice.warnings) {
        console.log(`  ${w}`);
      }
      console.log();
    }

    // 2. 建议
    if (advice.recommendations.length > 0) {
      console.log('💡 成功经验 (可复用):');
      for (const r of advice.recommendations) {
        console.log(`  ${r}`);
      }
      console.log();
    }

    // 3. 最佳实践
    if (advice.best_practices.length > 0) {
      console.log('📋 当前最佳实践:');
      for (const p of advice.best_practices) {
        console.log(`  ${p}`);
      }
      console.log();
    }

    // 4. 相关记忆数量
    console.log('📊 记忆支撑:');
    console.log(`  相关教训: ${advice.related_lessons.length} 条`);
    console.log(`  相关经验: ${advice.related_experiences.length} 条`);
    console.log();

    console.log('═'.repeat(60));
  }

  /**
   * 主执行流程
   */
  async run(taskDescription?: string): Promise<void> {
    const task = taskDescription || '优化系统性能';

    this.generateDecisionReport(task);
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const task = process.argv[2] || '编码任务';
  const decision = new MemoryDrivenDecision();
  await decision.run(task);
}
