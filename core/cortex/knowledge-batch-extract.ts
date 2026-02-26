#!/usr/bin/env bun
/**
 * Knowledge Batch Extractor - 批量知识抽取处理器
 *
 * 功能：
 * 1. 从 sys_favorites 批量抽取知识（按 importance 排序）
 * 2. 断点续传（进度记录到 JSON 文件）
 * 3. 速率控制（每条间隔 2 秒，避免 API 过载）
 * 4. 错误容忍（失败跳过，不阻塞全流程）
 * 5. 增量模式（只处理未同步的 favorites）
 *
 * 用法：
 *   bun knowledge-batch-extract.ts [--limit 10] [--min-importance 7] [--model glm-5] [--force] [--dry-run]
 *
 * @created 2026-02-22
 */

import { Database } from 'bun:sqlite';
import { readFileSync, writeFileSync, existsSync } from 'fs';

// ============================================================
// 导入 LLM 抽取器
// ============================================================

import { extractKnowledge, writeExtractionToDb } from './knowledge-llm-extractor';

// ============================================================
// 配置
// ============================================================

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const PROGRESS_FILE = `${process.env.HOME}/.solar/knowledge-batch-progress.json`;
const DEFAULT_MODEL = 'glm-5';
const RATE_LIMIT_MS = 2000; // 每条间隔 2 秒
const MAX_TEXT_LENGTH = 6000; // 单次抽取最大文本长度

// ============================================================
// 参数解析
// ============================================================

interface BatchOptions {
  limit: number;
  minImportance: number;
  model: string;
  force: boolean;   // 忽略已处理标记，强制重新抽取
  dryRun: boolean;  // 只显示将处理的条目，不实际抽取
}

function parseArgs(): BatchOptions {
  const args = process.argv.slice(2);
  const opts: BatchOptions = {
    limit: 10,
    minImportance: 7,
    model: DEFAULT_MODEL,
    force: false,
    dryRun: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--limit' && args[i + 1]) {
      opts.limit = parseInt(args[i + 1], 10);
      i++;
    } else if (arg === '--min-importance' && args[i + 1]) {
      opts.minImportance = parseInt(args[i + 1], 10);
      i++;
    } else if (arg === '--model' && args[i + 1]) {
      opts.model = args[i + 1];
      i++;
    } else if (arg === '--force') {
      opts.force = true;
    } else if (arg === '--dry-run') {
      opts.dryRun = true;
    } else if (arg === '--help' || arg === '-h') {
      console.log(`
Knowledge Batch Extractor - 批量知识抽取

用法:
  bun knowledge-batch-extract.ts [options]

选项:
  --limit N            每次处理条数 (默认: 10)
  --min-importance N   最低重要性 (默认: 7)
  --model MODEL        抽取模型 (默认: glm-5)
  --force              强制重新抽取（忽略 synced_to_graph）
  --dry-run            只显示将处理的条目，不实际抽取
  --help, -h           显示帮助
`);
      process.exit(0);
    }
  }

  return opts;
}

// ============================================================
// 进度管理（断点续传）
// ============================================================

interface BatchProgress {
  last_run: string;
  processed_ids: number[];
  failed_ids: number[];
  total_processed: number;
  total_entities: number;
  total_relations: number;
  total_claims: number;
  total_cortex_claims_upgraded: number;
  runs: Array<{
    timestamp: string;
    processed: number;
    failed: number;
    model: string;
    duration_ms: number;
  }>;
}

function loadProgress(): BatchProgress {
  if (existsSync(PROGRESS_FILE)) {
    try {
      return JSON.parse(readFileSync(PROGRESS_FILE, 'utf-8'));
    } catch {
      // corrupted file, start fresh
    }
  }
  return {
    last_run: '',
    processed_ids: [],
    failed_ids: [],
    total_processed: 0,
    total_entities: 0,
    total_relations: 0,
    total_claims: 0,
    total_cortex_claims_upgraded: 0,
    runs: [],
  };
}

function saveProgress(progress: BatchProgress): void {
  writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
}

// ============================================================
// 候选查询
// ============================================================

interface FavoriteCandidate {
  favorite_id: number;
  title: string;
  question: string;
  answer: string;
  tags: string;
  importance: number;
  synced_to_graph: number;
}

function getCandidates(db: Database, opts: BatchOptions, progress: BatchProgress): FavoriteCandidate[] {
  let sql = `
    SELECT favorite_id, title, question, answer, tags, importance, synced_to_graph
    FROM sys_favorites
    WHERE importance >= ?
  `;
  const params: any[] = [opts.minImportance];

  if (!opts.force) {
    // 增量模式：只处理未同步的
    sql += ` AND synced_to_graph = 0`;
  }

  // 跳过已经在 progress 中记录为已处理的（防止重复）
  if (!opts.force && progress.processed_ids.length > 0) {
    // SQLite 限制 IN 列表大小，分批处理
    const batchSize = 500;
    const chunks: number[][] = [];
    for (let i = 0; i < progress.processed_ids.length; i += batchSize) {
      chunks.push(progress.processed_ids.slice(i, i + batchSize));
    }
    for (const chunk of chunks) {
      sql += ` AND favorite_id NOT IN (${chunk.join(',')})`;
    }
  }

  sql += ` ORDER BY importance DESC, favorite_id ASC LIMIT ?`;
  params.push(opts.limit);

  return db.query(sql).all(...params) as FavoriteCandidate[];
}

// ============================================================
// 文本预处理
// ============================================================

function prepareExtractionText(fav: FavoriteCandidate): string {
  const parts: string[] = [];

  if (fav.title) {
    parts.push(`# ${fav.title}`);
  }

  if (fav.question) {
    parts.push(`## 问题\n${fav.question}`);
  }

  if (fav.answer) {
    parts.push(`## 回答\n${fav.answer}`);
  }

  // 解析 tags 添加上下文
  if (fav.tags) {
    try {
      const tags = JSON.parse(fav.tags);
      if (Array.isArray(tags) && tags.length > 0) {
        parts.push(`## 标签\n${tags.join(', ')}`);
      }
    } catch {
      // tags 不是 JSON 格式
    }
  }

  let text = parts.join('\n\n');

  // 截断过长文本
  if (text.length > MAX_TEXT_LENGTH) {
    text = text.substring(0, MAX_TEXT_LENGTH) + '\n\n[... 文本已截断 ...]';
  }

  return text;
}

// ============================================================
// 速率控制
// ============================================================

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
// 主流程
// ============================================================

async function main() {
  const opts = parseArgs();
  const db = new Database(DB_PATH);
  const progress = loadProgress();
  const startTime = Date.now();

  console.log('📦 Knowledge Batch Extractor - 批量知识抽取\n');
  console.log(`配置:`);
  console.log(`   模型: ${opts.model}`);
  console.log(`   限制: ${opts.limit} 条`);
  console.log(`   最低重要性: ${opts.minImportance}`);
  console.log(`   模式: ${opts.force ? '强制重抽' : '增量'}`);
  console.log(`   Dry Run: ${opts.dryRun}`);

  // 统计
  const totalFavorites = (db.query(`SELECT COUNT(*) as c FROM sys_favorites`).get() as any)?.c ?? 0;
  const unsyncedCount = (db.query(`SELECT COUNT(*) as c FROM sys_favorites WHERE synced_to_graph = 0`).get() as any)?.c ?? 0;
  const highImportance = (db.query(`SELECT COUNT(*) as c FROM sys_favorites WHERE importance >= ?`).get(opts.minImportance) as any)?.c ?? 0;

  console.log(`\n📊 数据源统计:`);
  console.log(`   sys_favorites 总数: ${totalFavorites}`);
  console.log(`   未同步到知识图谱: ${unsyncedCount}`);
  console.log(`   importance >= ${opts.minImportance}: ${highImportance}`);
  console.log(`   历史已处理: ${progress.total_processed}`);

  // 获取候选
  const candidates = getCandidates(db, opts, progress);

  if (candidates.length === 0) {
    console.log('\n✅ 没有需要处理的条目');
    if (!opts.force && unsyncedCount === 0) {
      console.log('   所有 favorites 已同步到知识图谱');
    }
    db.close();
    return;
  }

  console.log(`\n📝 本次将处理: ${candidates.length} 条\n`);

  // Dry Run 模式：只列出不执行
  if (opts.dryRun) {
    console.log('┌────┬──────────────────────────────────────────────────┬────────────┐');
    console.log('│ ID │ 标题                                             │ 重要性     │');
    console.log('├────┼──────────────────────────────────────────────────┼────────────┤');
    for (const fav of candidates) {
      const title = fav.title.substring(0, 48).padEnd(48);
      console.log(`│ ${String(fav.favorite_id).padStart(2)} │ ${title} │ ${String(fav.importance).padStart(10)} │`);
    }
    console.log('└────┴──────────────────────────────────────────────────┴────────────┘');
    console.log('\n💡 去掉 --dry-run 参数开始实际抽取');
    db.close();
    return;
  }

  // 实际抽取
  let processed = 0;
  let failed = 0;
  let totalEntities = 0;
  let totalRelations = 0;
  let totalClaims = 0;
  let totalCortexUpgraded = 0;

  const updateSynced = db.prepare(`UPDATE sys_favorites SET synced_to_graph = 1 WHERE favorite_id = ?`);

  for (let i = 0; i < candidates.length; i++) {
    const fav = candidates[i];
    const progressStr = `[${i + 1}/${candidates.length}]`;

    console.log(`${progressStr} 处理: #${fav.favorite_id} "${fav.title.substring(0, 40)}..." (importance=${fav.importance})`);

    try {
      // 1. 准备文本
      const text = prepareExtractionText(fav);

      if (text.trim().length < 50) {
        console.log(`   ⏭️  跳过: 文本太短 (${text.length} chars)`);
        continue;
      }

      // 2. 调用 LLM 抽取
      const result = await extractKnowledge(text, {
        model: opts.model,
        favoriteId: fav.favorite_id,
      });

      // 3. 写入数据库
      const writeResult = writeExtractionToDb(db, result, `favorite:${fav.favorite_id}`);

      // 4. 标记为已同步
      updateSynced.run(fav.favorite_id);

      // 5. 更新统计
      processed++;
      totalEntities += writeResult.entitiesWritten;
      totalRelations += writeResult.relationsWritten;
      totalClaims += writeResult.claimsWritten;
      totalCortexUpgraded += writeResult.cortexClaimsUpgraded;

      // 6. 记录到 progress
      progress.processed_ids.push(fav.favorite_id);

      console.log(`   ✅ 实体: ${writeResult.entitiesWritten}, 关系: ${writeResult.relationsWritten}, Claims: ${writeResult.claimsWritten}, Cortex升级: ${writeResult.cortexClaimsUpgraded} (${result.extraction_time_ms}ms)`);

    } catch (error: any) {
      failed++;
      progress.failed_ids.push(fav.favorite_id);
      console.log(`   ❌ 失败: ${error.message}`);
    }

    // 7. 速率控制（最后一条不等待）
    if (i < candidates.length - 1) {
      await sleep(RATE_LIMIT_MS);
    }

    // 8. 每 5 条保存一次进度（断点续传）
    if ((i + 1) % 5 === 0) {
      progress.total_processed += processed;
      progress.total_entities += totalEntities;
      progress.total_relations += totalRelations;
      progress.total_claims += totalClaims;
      progress.total_cortex_claims_upgraded += totalCortexUpgraded;
      saveProgress(progress);
    }
  }

  // 最终保存进度
  const duration = Date.now() - startTime;
  progress.last_run = new Date().toISOString();
  progress.total_processed += processed;
  progress.total_entities += totalEntities;
  progress.total_relations += totalRelations;
  progress.total_claims += totalClaims;
  progress.total_cortex_claims_upgraded += totalCortexUpgraded;
  progress.runs.push({
    timestamp: new Date().toISOString(),
    processed,
    failed,
    model: opts.model,
    duration_ms: duration,
  });
  saveProgress(progress);

  // 输出报告
  console.log('\n' + '═'.repeat(60));
  console.log('📊 批量抽取报告');
  console.log('═'.repeat(60));

  console.log(`\n本次处理:`);
  console.log(`   成功: ${processed} 条`);
  console.log(`   失败: ${failed} 条`);
  console.log(`   耗时: ${(duration / 1000).toFixed(1)} 秒`);

  console.log(`\n抽取成果:`);
  console.log(`   新增实体: ${totalEntities}`);
  console.log(`   新增关系: ${totalRelations}`);
  console.log(`   新增 Claims: ${totalClaims}`);
  console.log(`   升级到 cortex_claims: ${totalCortexUpgraded}`);

  // 清理后统计
  const afterEntities = (db.query(`SELECT COUNT(*) as c FROM knowledge_entities`).get() as any)?.c ?? 0;
  const afterRelations = (db.query(`SELECT COUNT(*) as c FROM knowledge_relations`).get() as any)?.c ?? 0;
  const afterClaims = (db.query(`SELECT COUNT(*) as c FROM knowledge_claims`).get() as any)?.c ?? 0;
  const afterCortex = (db.query(`SELECT COUNT(*) as c FROM cortex_claims`).get() as any)?.c ?? 0;
  const afterUnsynced = (db.query(`SELECT COUNT(*) as c FROM sys_favorites WHERE synced_to_graph = 0`).get() as any)?.c ?? 0;

  console.log(`\n知识库现状:`);
  console.log(`   knowledge_entities: ${afterEntities}`);
  console.log(`   knowledge_relations: ${afterRelations}`);
  console.log(`   knowledge_claims: ${afterClaims}`);
  console.log(`   cortex_claims: ${afterCortex}`);
  console.log(`   待处理 favorites: ${afterUnsynced}`);

  // 关系类型分布
  const relTypes = db.query(`
    SELECT relation_type, COUNT(*) as cnt
    FROM knowledge_relations
    GROUP BY relation_type
    ORDER BY cnt DESC
  `).all() as any[];

  if (relTypes.length > 0) {
    console.log(`\n关系类型分布:`);
    for (const r of relTypes) {
      console.log(`   ${r.relation_type}: ${r.cnt}`);
    }
  }

  // 累计统计
  console.log(`\n累计统计 (所有运行):`);
  console.log(`   总处理: ${progress.total_processed} 条`);
  console.log(`   总实体: ${progress.total_entities}`);
  console.log(`   总关系: ${progress.total_relations}`);
  console.log(`   总 Claims: ${progress.total_claims}`);
  console.log(`   总 Cortex 升级: ${progress.total_cortex_claims_upgraded}`);
  console.log(`   运行次数: ${progress.runs.length}`);

  if (afterUnsynced > 0) {
    console.log(`\n💡 还有 ${afterUnsynced} 条 favorites 待处理，再次运行即可继续`);
  }

  db.close();
  console.log('\n🎉 批量抽取完成!');
}

// ============================================================
// 入口
// ============================================================

main().catch(err => {
  console.error('❌ 批量抽取失败:', err);
  process.exit(1);
});
