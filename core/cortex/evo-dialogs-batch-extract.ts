#!/usr/bin/env bun
/**
 * Evo Dialogs Batch Extractor - L2→L3 知识提取处理器
 *
 * 功能：
 * 1. 从 evo_dialogs 批量抽取知识（60,807条对话记录）
 * 2. 预处理：计算 clean_token_count 并写入 knowledge_records
 * 3. First Fit Decreasing 批量规划（避免 token 超限）
 * 4. 断点续传（进度记录到 JSON 文件）
 * 5. 速率控制（每条间隔 2 秒，避免 API 过载）
 * 6. 错误容忍（失败跳过，不阻塞全流程）
 * 7. Auto-upgrade（confidence >= 0.7 自动提升到 cortex_claims）
 *
 * 用法：
 *   bun evo-dialogs-batch-extract.ts [--limit 10] [--model glm-5] [--force] [--dry-run]
 *
 * @created 2026-02-24
 * @adapted_from knowledge-batch-extract.ts
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
const PROGRESS_FILE = `${process.env.HOME}/.solar/evo-dialogs-batch-progress.json`;
const DEFAULT_MODEL = 'glm-5';
const RATE_LIMIT_MS = 2000; // 每条间隔 2 秒
const MAX_TEXT_LENGTH = 6000; // 单次抽取最大文本长度

// ============================================================
// 参数解析
// ============================================================

interface BatchOptions {
  limit: number;
  model: string;
  force: boolean;   // 忽略已处理标记，强制重新抽取
  dryRun: boolean;  // 只显示将处理的条目，不实际抽取
}

function parseArgs(): BatchOptions {
  const args = process.argv.slice(2);
  const opts: BatchOptions = {
    limit: 10,
    model: DEFAULT_MODEL,
    force: false,
    dryRun: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--limit' && args[i + 1]) {
      opts.limit = parseInt(args[i + 1], 10);
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
Evo Dialogs Batch Extractor - L2→L3 知识提取

用法:
  bun evo-dialogs-batch-extract.ts [options]

选项:
  --limit N            每次处理条数 (默认: 10)
  --model MODEL        抽取模型 (默认: glm-5)
  --force              强制重新抽取（忽略 extraction_status）
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
  processed_ids: string[];
  failed_ids: string[];
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
// 候选查询（从 evo_dialogs 获取）
// ============================================================

interface DialogCandidate {
  dialog_id: string;
  session_id: string;
  role: string;
  content: string;
  timestamp: string;
  model: string;
  record_id: number | null;
  extraction_status: string | null;
}

function getCandidates(db: Database, opts: BatchOptions, progress: BatchProgress): DialogCandidate[] {
  // 查询 evo_dialogs，左连接 knowledge_records 获取提取状态
  let sql = `
    SELECT
      d.dialog_id,
      d.session_id,
      d.role,
      d.content,
      d.timestamp,
      d.model,
      kr.record_id,
      kr.extraction_status
    FROM evo_dialogs d
    LEFT JOIN knowledge_records kr ON d.dialog_id = kr.dialog_id
  `;

  const conditions: string[] = [];
  const params: any[] = [];

  // 过滤空内容记录
  conditions.push(`d.content IS NOT NULL AND length(d.content) > 10`);

  if (!opts.force) {
    // 增量模式：只处理未提取的（extraction_status IS NULL 或 = 'pending'）
    conditions.push(`(kr.extraction_status IS NULL OR kr.extraction_status = 'pending')`);
  }

  // 跳过已经在 progress 中记录为已处理的（防止重复）
  if (!opts.force && progress.processed_ids.length > 0) {
    const batchSize = 500;
    const chunks: string[][] = [];
    for (let i = 0; i < progress.processed_ids.length; i += batchSize) {
      chunks.push(progress.processed_ids.slice(i, i + batchSize));
    }
    for (const chunk of chunks) {
      const placeholders = chunk.map(() => '?').join(',');
      conditions.push(`d.dialog_id NOT IN (${placeholders})`);
      params.push(...chunk);
    }
  }

  if (conditions.length > 0) {
    sql += ` WHERE ` + conditions.join(' AND ');
  }

  // 按时间戳排序，限制数量
  sql += ` ORDER BY d.timestamp DESC LIMIT ?`;
  params.push(opts.limit);

  return db.query(sql).all(...params) as DialogCandidate[];
}

// ============================================================
// 文本预处理
// ============================================================

function prepareExtractionText(dialog: DialogCandidate): string {
  const parts: string[] = [];

  // 对话角色和内容
  if (dialog.role && dialog.content) {
    parts.push(`## ${dialog.role}`);
    parts.push(dialog.content);
  }

  // 会话上下文
  if (dialog.session_id) {
    parts.push(`\n_Session: ${dialog.session_id}_`);
  }

  // 时间戳
  if (dialog.timestamp) {
    parts.push(`_Timestamp: ${dialog.timestamp}_`);
  }

  // 模型信息
  if (dialog.model) {
    parts.push(`_Model: ${dialog.model}_`);
  }

  let text = parts.join('\n\n');

  // 截断过长文本
  if (text.length > MAX_TEXT_LENGTH) {
    text = text.substring(0, MAX_TEXT_LENGTH) + '\n\n[... 文本已截断 ...]';
  }

  return text;
}

// ============================================================
// 预处理：计算 token 数并写入 knowledge_records
// ============================================================

function preprocessDialog(db: Database, dialog: DialogCandidate, preprocessConfig: any): number {
  // 获取预处理配置
  const removePatterns = JSON.parse(preprocessConfig.remove_patterns || '[]');
  const minLength = preprocessConfig.min_content_length || 10;
  const maxLength = preprocessConfig.max_content_length || 10000;

  // 清理内容
  let cleaned = dialog.content || '';
  for (const pattern of removePatterns) {
    const regex = new RegExp(pattern, 'g');
    cleaned = cleaned.replace(regex, '');
  }
  cleaned = cleaned.trim();

  // 长度检查
  if (cleaned.length < minLength) {
    return 0; // 内容太短，跳过
  }
  if (cleaned.length > maxLength) {
    cleaned = cleaned.substring(0, maxLength);
  }

  // 估算 token 数（简单估算：英文 1 token ~= 4 chars，中文 1 token ~= 2 chars）
  // 更精确的方法需要实际 tokenizer，这里用启发式估算
  const chineseChars = (cleaned.match(/[\u4e00-\u9fa5]/g) || []).length;
  const englishChars = cleaned.length - chineseChars;
  const estimatedTokens = Math.ceil(chineseChars / 2 + englishChars / 4);

  // 写入 knowledge_records
  const insertStmt = db.prepare(`
    INSERT OR REPLACE INTO knowledge_records
    (dialog_id, session_id, original_content, cleaned_content, clean_token_count, extraction_status)
    VALUES (?, ?, ?, ?, ?, 'pending')
  `);

  insertStmt.run(
    dialog.dialog_id,
    dialog.session_id,
    dialog.content,
    cleaned,
    estimatedTokens
  );

  return estimatedTokens;
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

  console.log('📦 Evo Dialogs Batch Extractor - L2→L3 知识提取\n');
  console.log(`配置:`);
  console.log(`   模型: ${opts.model}`);
  console.log(`   限制: ${opts.limit} 条`);
  console.log(`   模式: ${opts.force ? '强制重抽' : '增量'}`);
  console.log(`   Dry Run: ${opts.dryRun}`);

  // 统计
  const totalDialogs = (db.query(`SELECT COUNT(*) as c FROM evo_dialogs`).get() as any)?.c ?? 0;
  const totalRecords = (db.query(`SELECT COUNT(*) as c FROM knowledge_records`).get() as any)?.c ?? 0;
  const pendingRecords = (db.query(`SELECT COUNT(*) as c FROM knowledge_records WHERE extraction_status = 'pending'`).get() as any)?.c ?? 0;

  console.log(`\n📊 数据源统计:`);
  console.log(`   evo_dialogs 总数: ${totalDialogs}`);
  console.log(`   knowledge_records 总数: ${totalRecords}`);
  console.log(`   待提取记录: ${pendingRecords}`);
  console.log(`   历史已处理: ${progress.total_processed}`);

  // 获取预处理配置
  const preprocessConfig = db.query(`
    SELECT * FROM preprocessor_config WHERE is_active = 1 LIMIT 1
  `).get() as any;

  if (!preprocessConfig) {
    console.error('❌ 错误: 未找到活跃的 preprocessor_config');
    db.close();
    return;
  }

  // 获取候选
  const candidates = getCandidates(db, opts, progress);

  if (candidates.length === 0) {
    console.log('\n✅ 没有需要处理的条目');
    if (!opts.force && pendingRecords === 0) {
      console.log('   所有对话已提取到知识图谱');
    }
    db.close();
    return;
  }

  console.log(`\n📝 本次将处理: ${candidates.length} 条\n`);

  // Dry Run 模式：只列出不执行
  if (opts.dryRun) {
    console.log('┌────────────────────────┬──────────┬────────────────────────────────────────┐');
    console.log('│ Dialog ID              │ Role     │ Content Preview                        │');
    console.log('├────────────────────────┼──────────┼────────────────────────────────────────┤');
    for (const dialog of candidates) {
      const preview = (dialog.content || '').substring(0, 38).padEnd(38);
      const dialogId = dialog.dialog_id.substring(0, 22).padEnd(22);
      const role = (dialog.role || '').substring(0, 8).padEnd(8);
      console.log(`│ ${dialogId} │ ${role} │ ${preview} │`);
    }
    console.log('└────────────────────────┴──────────┴────────────────────────────────────────┘');
    console.log('\n💡 去掉 --dry-run 参数开始实际抽取');
    db.close();
    return;
  }

  // 实际抽取
  let processed = 0;
  let failed = 0;
  let skipped = 0;
  let totalEntities = 0;
  let totalRelations = 0;
  let totalClaims = 0;
  let totalCortexUpgraded = 0;

  const updateStatus = db.prepare(`
    UPDATE knowledge_records
    SET extraction_status = ?, extracted_at = datetime('now')
    WHERE dialog_id = ?
  `);

  for (let i = 0; i < candidates.length; i++) {
    const dialog = candidates[i];
    const progressStr = `[${i + 1}/${candidates.length}]`;

    console.log(`${progressStr} 处理: ${dialog.dialog_id} (${dialog.role})`);

    try {
      // 1. 预处理（计算 token 并写入 knowledge_records）
      const tokenCount = preprocessDialog(db, dialog, preprocessConfig);

      if (tokenCount === 0) {
        console.log(`   ⏭️  跳过: 内容太短或不符合条件`);
        skipped++;
        continue;
      }

      console.log(`   📊 预处理完成: ${tokenCount} tokens`);

      // 2. 准备文本
      const text = prepareExtractionText(dialog);

      // 3. 调用 LLM 抽取
      const result = await extractKnowledge(text, {
        model: opts.model,
        favoriteId: parseInt(dialog.dialog_id.split('-')[0] || '0', 10), // 兼容性参数
      });

      // 4. 写入数据库
      const writeResult = writeExtractionToDb(db, result, `dialog:${dialog.dialog_id}`);

      // 5. 标记为已提取
      updateStatus.run('completed', dialog.dialog_id);

      // 6. 更新统计
      processed++;
      totalEntities += writeResult.entitiesWritten;
      totalRelations += writeResult.relationsWritten;
      totalClaims += writeResult.claimsWritten;
      totalCortexUpgraded += writeResult.cortexClaimsUpgraded;

      // 7. 记录到 progress
      progress.processed_ids.push(dialog.dialog_id);

      console.log(`   ✅ 实体: ${writeResult.entitiesWritten}, 关系: ${writeResult.relationsWritten}, Claims: ${writeResult.claimsWritten}, Cortex升级: ${writeResult.cortexClaimsUpgraded} (${result.extraction_time_ms}ms)`);

    } catch (error: any) {
      failed++;
      progress.failed_ids.push(dialog.dialog_id);
      updateStatus.run('failed', dialog.dialog_id);
      console.log(`   ❌ 失败: ${error.message}`);
    }

    // 8. 速率控制（最后一条不等待）
    if (i < candidates.length - 1) {
      await sleep(RATE_LIMIT_MS);
    }

    // 9. 每 5 条保存一次进度（断点续传）
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
  console.log(`   跳过: ${skipped} 条`);
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
  const afterPending = (db.query(`SELECT COUNT(*) as c FROM knowledge_records WHERE extraction_status = 'pending'`).get() as any)?.c ?? 0;

  console.log(`\n知识库现状:`);
  console.log(`   knowledge_entities: ${afterEntities}`);
  console.log(`   knowledge_relations: ${afterRelations}`);
  console.log(`   knowledge_claims: ${afterClaims}`);
  console.log(`   cortex_claims: ${afterCortex}`);
  console.log(`   待处理记录: ${afterPending}`);

  // 关系类型分布
  const relTypes = db.query(`
    SELECT relation_type, COUNT(*) as cnt
    FROM knowledge_relations
    GROUP BY relation_type
    ORDER BY cnt DESC
    LIMIT 10
  `).all() as any[];

  if (relTypes.length > 0) {
    console.log(`\n关系类型分布 (Top 10):`);
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

  if (afterPending > 0) {
    console.log(`\n💡 还有 ${afterPending} 条记录待处理，再次运行即可继续`);
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
