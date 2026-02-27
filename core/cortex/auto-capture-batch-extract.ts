#!/usr/bin/env bun
/**
 * Auto-Capture Batch Knowledge Extraction
 *
 * 处理三个自动捕获数据源的批量知识抽取：
 * 1. sys_search_cache - 搜索结果
 * 2. sys_expert_outputs - 专家输出
 * 3. sys_dev_artifacts - 开发产物
 *
 * Usage:
 *   bun auto-capture-batch-extract.ts [options]
 *
 * Options:
 *   --limit N          处理条目数上限 (default: 50)
 *   --model MODEL      使用的模型 (default: gemini-2.5-flash)
 *   --source TYPE      只处理指定来源 (search|expert|artifact, default: all)
 *   --force            重新处理已同步的条目
 *   --dry-run          模拟运行，不实际抽取
 */

import Database from 'bun:sqlite';
import { extractKnowledge, writeExtractionToDb } from './knowledge-llm-extractor';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const PROGRESS_FILE = `${process.env.HOME}/.solar/auto-capture-batch-progress.json`;
const RATE_LIMIT_MS = 2000; // 2秒间隔，避免API限流
const MAX_TEXT_LENGTH = 6000; // 文本截断长度

interface BatchOptions {
  limit: number;
  model: string;
  source?: 'search' | 'expert' | 'artifact';
  force: boolean;
  dryRun: boolean;
}

interface BatchProgress {
  last_run: string;
  processed_ids: string[];
  failed_ids: string[];
  total_processed: number;
  total_entities: number;
  total_relations: number;
  total_claims: number;
  total_cortex_claims_upgraded: number;
  runs: number;
}

interface CaptureCandidate {
  source_type: string;
  source_id: string;
  title: string;
  content: string;
  created_at: string;
}

/**
 * 加载进度
 */
async function loadProgress(): Promise<BatchProgress> {
  try {
    const file = Bun.file(PROGRESS_FILE);
    if (file.size > 0) {
      return JSON.parse(await file.text());
    }
  } catch (e) {
    // 文件不存在或损坏，返回默认值
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
    runs: 0
  };
}

/**
 * 保存进度
 */
function saveProgress(progress: BatchProgress) {
  Bun.write(PROGRESS_FILE, JSON.stringify(progress, null, 2));
}

/**
 * 获取待处理候选项
 */
function getCandidates(db: Database, opts: BatchOptions, progress: BatchProgress): CaptureCandidate[] {
  let sql = `SELECT source_type, source_id, title, content, created_at FROM (`;

  const unions: string[] = [];

  // Search results
  if (!opts.source || opts.source === 'search') {
    let searchSql = `
      SELECT 'search' as source_type, search_id as source_id,
             query as title, results as content, created_at
      FROM sys_search_cache
      WHERE 1=1
    `;
    if (!opts.force) {
      searchSql += ` AND synced_to_graph = 0`;
    }
    unions.push(searchSql);
  }

  // Expert outputs
  if (!opts.source || opts.source === 'expert') {
    let expertSql = `
      SELECT 'expert' as source_type, output_id as source_id,
             COALESCE(expert_role, model) as title, output as content, created_at
      FROM sys_expert_outputs
      WHERE 1=1
    `;
    if (!opts.force) {
      expertSql += ` AND synced_to_graph = 0`;
    }
    unions.push(expertSql);
  }

  // Development artifacts
  if (!opts.source || opts.source === 'artifact') {
    let artifactSql = `
      SELECT 'artifact' as source_type, artifact_id as source_id,
             title, content, created_at
      FROM sys_dev_artifacts
      WHERE 1=1
    `;
    if (!opts.force) {
      artifactSql += ` AND synced_to_graph = 0`;
    }
    unions.push(artifactSql);
  }

  sql += unions.join(' UNION ALL ');
  sql += `) ORDER BY created_at DESC LIMIT ?`;

  return db.query(sql).all(opts.limit) as CaptureCandidate[];
}

/**
 * 准备抽取文本
 */
function prepareExtractionText(candidate: CaptureCandidate): string {
  let text = `# ${candidate.title}\n\n`;

  // 根据source_type添加元数据
  text += `**来源类型**: ${candidate.source_type}\n`;
  text += `**创建时间**: ${candidate.created_at}\n\n`;

  // 添加内容
  text += `## 内容\n\n`;

  // 处理JSON内容（搜索结果）
  if (candidate.source_type === 'search' && candidate.content) {
    try {
      const results = JSON.parse(candidate.content);
      text += JSON.stringify(results, null, 2);
    } catch (e) {
      text += candidate.content;
    }
  } else {
    text += candidate.content;
  }

  // 截断过长文本
  if (text.length > MAX_TEXT_LENGTH) {
    text = text.substring(0, MAX_TEXT_LENGTH) + '\n\n... (内容已截断)';
  }

  return text;
}

/**
 * 标记已同步
 */
function markSynced(db: Database, candidate: CaptureCandidate) {
  const tableMap = {
    search: 'sys_search_cache',
    expert: 'sys_expert_outputs',
    artifact: 'sys_dev_artifacts'
  };

  const idMap = {
    search: 'search_id',
    expert: 'output_id',
    artifact: 'artifact_id'
  };

  const table = tableMap[candidate.source_type as keyof typeof tableMap];
  const idCol = idMap[candidate.source_type as keyof typeof idMap];

  db.run(
    `UPDATE ${table} SET synced_to_graph = 1 WHERE ${idCol} = ?`,
    [candidate.source_id]
  );
}

/**
 * 延迟函数
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 主批处理函数
 */
async function batchExtract(opts: BatchOptions) {
  const db = new Database(DB_PATH);
  const progress = await loadProgress();

  console.log('\n🔍 Auto-Capture 批量知识抽取');
  console.log('─────────────────────────────────────');
  console.log(`模型: ${opts.model}`);
  console.log(`来源: ${opts.source || 'all'}`);
  console.log(`上限: ${opts.limit}`);
  console.log(`模式: ${opts.force ? 'force' : 'incremental'}${opts.dryRun ? ' (dry-run)' : ''}`);
  console.log('');

  // 查询候选项
  const candidates = getCandidates(db, opts, progress);
  console.log(`✓ 找到 ${candidates.length} 个待处理条目\n`);

  if (candidates.length === 0) {
    console.log('✅ 没有待处理条目');
    db.close();
    return;
  }

  // 统计
  let processed = 0;
  let failed = 0;
  let totalEntities = 0;
  let totalRelations = 0;
  let totalClaims = 0;
  let totalCortexClaimsUpgraded = 0;

  // 处理每个候选项
  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i];
    const displayTitle = candidate.title.substring(0, 60) + (candidate.title.length > 60 ? '...' : '');

    console.log(`[${i + 1}/${candidates.length}] ${candidate.source_type}: ${displayTitle}`);

    if (opts.dryRun) {
      console.log('  (dry-run, 跳过实际抽取)\n');
      continue;
    }

    try {
      // 准备文本
      const text = prepareExtractionText(candidate);

      // LLM抽取
      const result = await extractKnowledge(text, {
        model: opts.model,
        sourceId: `${candidate.source_type}:${candidate.source_id}`
      });

      // 写入数据库
      const writeResult = writeExtractionToDb(
        db,
        result,
        `${candidate.source_type}:${candidate.source_id}`
      );

      // 标记已同步
      markSynced(db, candidate);

      // 累计统计
      processed++;
      totalEntities += writeResult.entitiesCreated;
      totalRelations += writeResult.relationsCreated;
      totalClaims += writeResult.claimsCreated;
      totalCortexClaimsUpgraded += writeResult.cortexClaimsUpgraded || 0;

      // 更新进度
      progress.processed_ids.push(candidate.source_id);

      console.log(`  ✓ 实体:${writeResult.entitiesCreated} 关系:${writeResult.relationsCreated} 结论:${writeResult.claimsCreated}`);
      if (writeResult.cortexClaimsUpgraded && writeResult.cortexClaimsUpgraded > 0) {
        console.log(`  ✓ Cortex结论升级: ${writeResult.cortexClaimsUpgraded}`);
      }
      console.log('');

    } catch (error: any) {
      failed++;
      progress.failed_ids.push(candidate.source_id);
      console.error(`  ✗ 失败: ${error.message}\n`);
    }

    // Rate limiting
    if (i < candidates.length - 1) {
      await sleep(RATE_LIMIT_MS);
    }

    // 每5个保存进度
    if ((i + 1) % 5 === 0) {
      saveProgress(progress);
    }
  }

  // 更新总进度
  progress.last_run = new Date().toISOString();
  progress.total_processed += processed;
  progress.total_entities += totalEntities;
  progress.total_relations += totalRelations;
  progress.total_claims += totalClaims;
  progress.total_cortex_claims_upgraded += totalCortexClaimsUpgraded;
  progress.runs += 1;
  saveProgress(progress);

  // 输出统计
  console.log('\n📊 批处理统计');
  console.log('─────────────────────────────────────');
  console.log(`本次处理: ${processed}/${candidates.length}`);
  console.log(`失败: ${failed}`);
  console.log(`新增实体: ${totalEntities}`);
  console.log(`新增关系: ${totalRelations}`);
  console.log(`新增结论: ${totalClaims}`);
  if (totalCortexClaimsUpgraded > 0) {
    console.log(`Cortex结论升级: ${totalCortexClaimsUpgraded}`);
  }
  console.log('');
  console.log('📈 累计统计 (所有批次)');
  console.log('─────────────────────────────────────');
  console.log(`总批次: ${progress.runs}`);
  console.log(`总处理: ${progress.total_processed}`);
  console.log(`总实体: ${progress.total_entities}`);
  console.log(`总关系: ${progress.total_relations}`);
  console.log(`总结论: ${progress.total_claims}`);
  console.log(`总Cortex升级: ${progress.total_cortex_claims_upgraded}`);
  console.log('');

  db.close();
}

// CLI 执行
if (import.meta.main) {
  const args = process.argv.slice(2);

  const opts: BatchOptions = {
    limit: 50,
    model: 'gemini-2.5-flash',
    force: false,
    dryRun: false
  };

  // 解析参数
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === '--limit' && i + 1 < args.length) {
      opts.limit = parseInt(args[++i]);
    } else if (arg === '--model' && i + 1 < args.length) {
      opts.model = args[++i];
    } else if (arg === '--source' && i + 1 < args.length) {
      const source = args[++i];
      if (source === 'search' || source === 'expert' || source === 'artifact') {
        opts.source = source;
      }
    } else if (arg === '--force') {
      opts.force = true;
    } else if (arg === '--dry-run') {
      opts.dryRun = true;
    } else if (arg === '--help' || arg === '-h') {
      console.log(`
Auto-Capture Batch Knowledge Extraction

Usage:
  bun auto-capture-batch-extract.ts [options]

Options:
  --limit N          处理条目数上限 (default: 50)
  --model MODEL      使用的模型 (default: gemini-2.5-flash)
  --source TYPE      只处理指定来源 (search|expert|artifact, default: all)
  --force            重新处理已同步的条目
  --dry-run          模拟运行，不实际抽取
  --help, -h         显示帮助信息

Examples:
  bun auto-capture-batch-extract.ts
  bun auto-capture-batch-extract.ts --limit 100
  bun auto-capture-batch-extract.ts --source expert
  bun auto-capture-batch-extract.ts --model gemini-2.5-pro --limit 20
      `);
      process.exit(0);
    }
  }

  batchExtract(opts).catch(console.error);
}
