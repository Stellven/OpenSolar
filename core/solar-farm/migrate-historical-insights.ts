#!/usr/bin/env bun
/**
 * 历史 Insight 数据迁移到 Cortex
 *
 * 用途：将 v2.3 之前生成的 Insight 分析数据批量导入到 Cortex 知识库
 *
 * 数据源：
 * - insight_sessions 表（会话元数据）
 * - artifacts/*_phase1_research_sources_*.json（参考资料）
 * - insight_evaluations 表（专家互评）
 *
 * 目标：
 * - cortex_tasks（任务记录）
 * - cortex_sources（参考资料）
 * - cortex_evals（专家互评）
 */

import { Cortex } from '../cortex/index';
import { Database } from 'bun:sqlite';
import { homedir } from 'os';
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const ARTIFACTS_DIR = `${homedir()}/.solar/cortex/artifacts`;

interface InsightSession {
  session_id: string;
  topic: string;
  status: string;
  started_at: string;
}

interface ResearchSource {
  key: string;
  title: string;
  url: string;
  snippet: string;
  query: string;
}

interface Evaluation {
  task_id: string;
  phase: string;
  evaluator: string;
  evaluated: string;
  target_id: string;
  scores: string;
  avg_score: number;
  comments: string;
}

async function migrate() {
  const db = new Database(DB_PATH);
  const cortex = new Cortex();

  console.log('🔄 开始迁移历史 Insight 数据到 Cortex...\n');

  // 1. 查询所有已完成的 insight 会话
  const sessions = db.query(`
    SELECT session_id, topic, status, started_at
    FROM insight_sessions
    WHERE status = 'done'
    ORDER BY started_at ASC
  `).all() as InsightSession[];

  console.log(`📊 找到 ${sessions.length} 个已完成的会话\n`);

  let migratedCount = 0;
  let skippedCount = 0;
  let errorCount = 0;

  for (const session of sessions) {
    console.log(`\n🔍 处理: ${session.topic} (${session.session_id})`);

    try {
      // 检查是否已经导入过
      const existingTask = cortex.getTask(session.session_id);
      if (existingTask) {
        console.log(`  ⏭️  已存在，跳过`);
        skippedCount++;
        continue;
      }

      // 2. 查找 research_sources 文件
      const sourcesPattern = `${session.session_id}_phase1_research_sources_`;
      const files = Bun.spawn(['ls', ARTIFACTS_DIR], { stdout: 'pipe' });
      const filesOutput = await new Response(files.stdout).text();
      const sourcesFile = filesOutput.split('\n').find(f => f.includes(sourcesPattern));

      let sourcesCount = 0;
      if (sourcesFile) {
        const sourcesPath = join(ARTIFACTS_DIR, sourcesFile);
        if (existsSync(sourcesPath)) {
          const data = JSON.parse(readFileSync(sourcesPath, 'utf-8'));
          const sources: ResearchSource[] = data.sources || [];

          // 创建任务（使用原 session_id 作为 task_id）
          db.run(`
            INSERT INTO cortex_tasks (task_id, task_type, topic, requester, config, phase_status, status, created_at)
            VALUES (?, 'insight', ?, 'insight-agent-v2', '{}', '{}', 'completed', ?)
          `, [session.session_id, session.topic, session.started_at]);

          // 导入 sources（只导入前 20 个，避免数据过多）
          const topSources = sources.slice(0, 20);
          for (const src of topSources) {
            await cortex.addSource(session.session_id, {
              citation_key: src.key || `src_${sourcesCount}`,
              title: src.title || 'Untitled',
              url: src.url,
              finding: src.snippet || '',
              credibility: 0.7  // 默认可信度
            }, 'web-search');
            sourcesCount++;
          }

          console.log(`  ✅ 导入 ${sourcesCount} 条 sources`);
        }
      }

      // 3. 导入 evaluations
      const evaluations = db.query(`
        SELECT task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments
        FROM insight_evaluations
        WHERE task_id = ?
      `).all(session.session_id) as Evaluation[];

      let evalsCount = 0;
      for (const ev of evaluations) {
        const rubric = JSON.parse(ev.scores);
        const suggestions = ev.comments ? [ev.comments] : [];

        await cortex.addEval(
          session.session_id,
          5,  // phase (reviewing 阶段)
          0,  // artifact_id (暂不关联)
          ev.evaluator,
          ev.evaluated,
          rubric,
          ev.avg_score,
          ev.comments || '',
          suggestions
        );
        evalsCount++;
      }

      if (evalsCount > 0) {
        console.log(`  ✅ 导入 ${evalsCount} 条 evaluations`);
      }

      migratedCount++;

    } catch (error) {
      console.error(`  ❌ 错误:`, error);
      errorCount++;
    }
  }

  console.log(`\n📊 迁移完成:`);
  console.log(`  ✅ 成功: ${migratedCount}`);
  console.log(`  ⏭️  跳过: ${skippedCount}`);
  console.log(`  ❌ 失败: ${errorCount}`);

  // 4. 显示最终统计
  const totalSources = db.query(`SELECT COUNT(*) as cnt FROM cortex_sources`).get() as { cnt: number };
  const totalEvals = db.query(`SELECT COUNT(*) as cnt FROM cortex_evals`).get() as { cnt: number };
  const totalTasks = db.query(`SELECT COUNT(*) as cnt FROM cortex_tasks`).get() as { cnt: number };

  console.log(`\n📚 Cortex 知识库统计:`);
  console.log(`  Tasks: ${totalTasks.cnt}`);
  console.log(`  Sources: ${totalSources.cnt}`);
  console.log(`  Evaluations: ${totalEvals.cnt}`);
}

// 执行迁移
migrate().catch(console.error);
