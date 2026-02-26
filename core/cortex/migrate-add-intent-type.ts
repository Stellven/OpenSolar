#!/usr/bin/env bun
/**
 * 迁移：sys_quality_scores 表添加 'intent' entity_type
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('🔧 开始迁移：添加 intent entity_type...\n');

try {
  // SQLite 不支持直接修改 CHECK 约束，需要重建表
  db.run('BEGIN TRANSACTION');

  // 1. 创建新表
  db.run(`
    CREATE TABLE sys_quality_scores_new (
      score_id TEXT PRIMARY KEY,
      entity_type TEXT CHECK(entity_type IN ('agent', 'skill', 'model', 'task_type', 'intent')),
      entity_id TEXT,
      completion_rate REAL,
      first_try_rate REAL,
      satisfaction REAL,
      efficiency REAL,
      sample_size INTEGER,
      confidence_lower REAL,
      confidence_upper REAL,
      period TEXT CHECK(period IN ('daily', 'weekly', 'monthly', 'all_time')),
      period_start DATE,
      period_end DATE,
      calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(entity_type, entity_id, period, period_start)
    )
  `);
  console.log('✅ 创建新表');

  // 2. 复制数据
  db.run(`
    INSERT INTO sys_quality_scores_new
    SELECT * FROM sys_quality_scores
  `);
  console.log('✅ 复制数据');

  // 3. 删除旧表
  db.run('DROP TABLE sys_quality_scores');
  console.log('✅ 删除旧表');

  // 4. 重命名新表
  db.run('ALTER TABLE sys_quality_scores_new RENAME TO sys_quality_scores');
  console.log('✅ 重命名新表');

  db.run('COMMIT');

  console.log('\n🎉 迁移成功！');

} catch (error) {
  db.run('ROLLBACK');
  console.error('❌ 迁移失败:', error);
  throw error;
}

db.close();
