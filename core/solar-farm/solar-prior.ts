#!/usr/bin/env bun
/**
 * Solar Prior - 存储 Solar 的主观知识到 Cortex
 *
 * 用途：人类先验路由
 * - Solar 的主观经验/观点不直接注入 prompt
 * - 先存入 Cortex 作为资料
 * - 需要时显式引用
 *
 * 示例：
 *   bun solar-prior.ts save "记忆系统架构" "三层架构：Episodic/Semantic/Procedural"
 *   bun solar-prior.ts query "记忆系统"
 */

import { Cortex } from '../cortex/index';

const cortex = new Cortex();

async function savePrior(topic: string, knowledge: string): Promise<void> {
  // 创建任务（会返回生成的 taskId）
  const taskId = cortex.createTask('prior', topic, 'solar', {
    source: 'solar_subjective',
    type: 'human_prior'
  });

  // 存储为 source
  const sourceId = await cortex.addSource(taskId, {
    citation_key: `solar_${topic.toLowerCase().replace(/\s+/g, '_')}`,
    title: `Solar 先验: ${topic}`,
    url: undefined,
    finding: knowledge,
    credibility: 0.9  // Solar 的主观知识，高可信度
  }, 'solar');

  console.log(`✅ 已存储 Solar 先验知识到 Cortex`);
  console.log(`   Task ID: ${taskId}`);
  console.log(`   Source ID: ${sourceId}`);
  console.log(`   Topic: ${topic}`);
  console.log(`   Knowledge: ${knowledge.substring(0, 100)}...`);
}

async function queryPrior(keyword: string): Promise<void> {
  // 使用参数化查询防止 SQL 注入
  const searchPattern = `%${keyword}%`;

  // 直接使用 Database 实例进行参数化查询
  const { Database } = await import('bun:sqlite');
  const { homedir } = await import('os');
  const db = new Database(`${homedir()}/.solar/solar.db`);

  const results = db.query(`
    SELECT
      s.citation_key,
      s.title,
      s.finding,
      t.topic,
      t.created_at
    FROM cortex_sources s
    JOIN cortex_tasks t ON s.task_id = t.task_id
    WHERE t.task_type = 'prior'
      AND (s.title LIKE ? OR s.finding LIKE ?)
    ORDER BY t.created_at DESC
    LIMIT 10
  `).all(searchPattern, searchPattern);

  if (results.length === 0) {
    console.log(`未找到关于 "${keyword}" 的 Solar 先验知识`);
    return;
  }

  console.log(`\n📚 找到 ${results.length} 条 Solar 先验知识:\n`);
  for (const r of results as any[]) {
    console.log(`┌─ ${r.citation_key}`);
    console.log(`│  Topic: ${r.topic}`);
    console.log(`│  Finding: ${r.finding}`);
    console.log(`│  Created: ${r.created_at}`);
    console.log(`└─`);
  }
}

// CLI
const command = process.argv[2];

if (command === 'save') {
  const topic = process.argv[3];
  const knowledge = process.argv[4];

  if (!topic || !knowledge) {
    console.error('用法: bun solar-prior.ts save <topic> <knowledge>');
    process.exit(1);
  }

  await savePrior(topic, knowledge);
} else if (command === 'query') {
  const keyword = process.argv[3];

  if (!keyword) {
    console.error('用法: bun solar-prior.ts query <keyword>');
    process.exit(1);
  }

  await queryPrior(keyword);
} else {
  console.log(`
Solar Prior - 存储 Solar 的主观知识到 Cortex

用法:
  bun solar-prior.ts save <topic> <knowledge>   存储先验知识
  bun solar-prior.ts query <keyword>            查询先验知识

示例:
  bun solar-prior.ts save "记忆系统架构" "三层架构：Episodic/Semantic/Procedural"
  bun solar-prior.ts query "记忆系统"
`);
}
