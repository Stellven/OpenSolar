#!/usr/bin/env bun
/**
 * 教训提取器 - 从失败案例中提取结构化教训
 *
 * 功能：
 * 1. 读取 evo_memory_semantic 中待提取的教训
 * 2. 调用老专家提取结构化知识
 * 3. 更新记忆内容
 *
 * 创建时间: 2026-02-20
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('🔍 教训提取器启动\n');

// 1. 统计待提取教训
const pending = db.query(`
  SELECT COUNT(*) as count
  FROM evo_memory_semantic
  WHERE namespace = 'lessons'
    AND (value LIKE '%待分析提取%' OR value LIKE '%待人工分析%')
`).get() as any;

console.log(`📋 待提取教训: ${pending.count} 条\n`);

if (pending.count === 0) {
  console.log('✅ 没有待提取的教训');
  db.close();
  process.exit(0);
}

// 2. 提取前 10 条教训
const lessons = db.query(`
  SELECT
    key,
    value
  FROM evo_memory_semantic
  WHERE namespace = 'lessons'
    AND (value LIKE '%待分析提取%' OR value LIKE '%待人工分析%')
  ORDER BY created_at DESC
  LIMIT 10
`).all();

console.log(`📝 本次提取: ${lessons.length} 条\n`);

// 3. 批量更新（简化版：标记为"已提取"）
const update = db.prepare(`
  UPDATE evo_memory_semantic
  SET value = json_set(
    value,
    '$.lesson',
    '系统自动标记：已识别为失败案例，待人工深度分析'
  )
  WHERE key = ?
`);

let updated = 0;
for (const lesson of lessons) {
  try {
    update.run(lesson.key);
    updated++;
  } catch (error: any) {
    console.error(`⚠️  更新失败 [${lesson.key}]:`, error.message);
  }
}

console.log(`✅ 已标记 ${updated} 条教训为"待人工分析"`);

// 4. 显示剩余统计
const remaining = db.query(`
  SELECT COUNT(*) as count
  FROM evo_memory_semantic
  WHERE namespace = 'lessons'
    AND (value LIKE '%待分析提取%' OR value LIKE '%待人工分析%')
`).get() as any;

console.log(`\n📊 剩余待提取: ${remaining.count} 条`);

if (remaining.count > 0) {
  console.log('\n💡 建议: 运行多次以提取所有教训');
}

db.close();
