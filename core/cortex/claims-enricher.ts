#!/usr/bin/env bun
/**
 * Claims Enricher - 从 cortex_sources 生成高质量 cortex_claims
 *
 * 功能：
 * 1. 按 task_id 分组读取 cortex_sources（按 credibility DESC）
 * 2. 合并同组 sources，调用 LLM 提炼核心 claims
 * 3. 交叉引用 supporting_sources，寻找 counter_sources
 * 4. 写入 cortex_claims 表
 * 5. 与 knowledge_entities 建立关联
 * 6. 断点续传 + 速率控制
 *
 * 用法：
 *   bun claims-enricher.ts [--limit 50] [--min-credibility 0.5] [--model glm-5] [--force] [--dry-run]
 *
 * @created 2026-02-22
 */

import { Database } from 'bun:sqlite';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { callLLM } from './llm-api-client';

// ============================================================
// 配置
// ============================================================

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const ANCHORS_PATH = `${process.env.HOME}/.claude/core/solar-farm/niumao-anchors.json`;
const PROGRESS_FILE = `${process.env.HOME}/.solar/claims-enricher-progress.json`;
const DEFAULT_MODEL = 'glm-5';
const RATE_LIMIT_MS = 2000;
const MAX_SOURCES_PER_GROUP = 15; // 单组最大 sources 数（防止 prompt 过长）

// ============================================================
// 参数解析
// ============================================================

interface EnricherOptions {
  limit: number;
  minCredibility: number;
  model: string;
  force: boolean;
  dryRun: boolean;
}

function parseArgs(): EnricherOptions {
  const args = process.argv.slice(2);
  const opts: EnricherOptions = {
    limit: 50,
    minCredibility: 0.5,
    model: DEFAULT_MODEL,
    force: false,
    dryRun: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--limit' && args[i + 1]) {
      opts.limit = parseInt(args[i + 1], 10);
      i++;
    } else if (arg === '--min-credibility' && args[i + 1]) {
      opts.minCredibility = parseFloat(args[i + 1]);
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
Claims Enricher - 从 cortex_sources 生成高质量 cortex_claims

用法:
  bun claims-enricher.ts [options]

选项:
  --limit N              每次处理组数 (默认: 50)
  --min-credibility N    最低可信度 (默认: 0.5)
  --model MODEL          抽取模型 (默认: glm-5)
  --force                强制重新处理已处理的 task_id
  --dry-run              只显示将处理的分组，不实际抽取
  --help, -h             显示帮助
`);
      process.exit(0);
    }
  }

  return opts;
}

// ============================================================
// 进度管理（断点续传）
// ============================================================

interface EnricherProgress {
  last_run: string;
  processed_task_ids: string[];
  failed_task_ids: string[];
  total_processed: number;
  total_claims_generated: number;
  total_entities_linked: number;
  runs: Array<{
    timestamp: string;
    groups_processed: number;
    groups_failed: number;
    claims_generated: number;
    model: string;
    duration_ms: number;
  }>;
}

function loadProgress(): EnricherProgress {
  if (existsSync(PROGRESS_FILE)) {
    try {
      return JSON.parse(readFileSync(PROGRESS_FILE, 'utf-8'));
    } catch {
      // corrupted file, start fresh
    }
  }
  return {
    last_run: '',
    processed_task_ids: [],
    failed_task_ids: [],
    total_processed: 0,
    total_claims_generated: 0,
    total_entities_linked: 0,
    runs: [],
  };
}

function saveProgress(progress: EnricherProgress): void {
  writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
}

// ============================================================
// D&D KNOBS 人格加载
// ============================================================

function loadAnchorSystemPrompt(modelKey: string): string {
  try {
    if (!existsSync(ANCHORS_PATH)) return '';
    const anchors = JSON.parse(readFileSync(ANCHORS_PATH, 'utf-8'));
    const anchor = anchors[modelKey];
    if (!anchor) return '';

    const knobs = anchor.knobs || {};
    const role = anchor.dnd_role || 'builder';
    const level = anchor.level || 2;
    const nickname = anchor.nickname || modelKey;

    const knobLines = Object.entries(knobs)
      .map(([k, v]) => `• ${k}=${v}`)
      .join('\n');

    return `你是${nickname}，D&D 角色是 ${role}。

KNOBS (10 个可调节旋钮):
${knobLines}

LEVEL=${level}`;
  } catch {
    return '';
  }
}

// ============================================================
// 候选分组查询
// ============================================================

interface SourceGroup {
  task_id: string;
  sources: Array<{
    source_id: number;
    citation_key: string;
    title: string;
    finding: string;
    credibility: number;
    expert_model: string;
  }>;
  avg_credibility: number;
  source_count: number;
}

function getCandidateGroups(
  db: Database,
  opts: EnricherOptions,
  progress: EnricherProgress
): SourceGroup[] {
  // 1. 获取符合条件的 task_id 分组
  let groupSql = `
    SELECT task_id, COUNT(*) as cnt, AVG(credibility) as avg_cred
    FROM cortex_sources
    WHERE credibility >= ?
  `;
  const params: any[] = [opts.minCredibility];

  // 增量模式：跳过已处理的
  if (!opts.force && progress.processed_task_ids.length > 0) {
    const batchSize = 500;
    for (let i = 0; i < progress.processed_task_ids.length; i += batchSize) {
      const chunk = progress.processed_task_ids.slice(i, i + batchSize);
      const placeholders = chunk.map(() => '?').join(',');
      groupSql += ` AND task_id NOT IN (${placeholders})`;
      params.push(...chunk);
    }
  }

  groupSql += ` GROUP BY task_id HAVING cnt >= 2 ORDER BY avg_cred DESC, cnt DESC LIMIT ?`;
  params.push(opts.limit);

  const groups = db.query(groupSql).all(...params) as Array<{
    task_id: string;
    cnt: number;
    avg_cred: number;
  }>;

  // 2. 为每个分组加载详细 sources
  const result: SourceGroup[] = [];

  const sourceStmt = db.prepare(`
    SELECT source_id, citation_key, title, finding, credibility, expert_model
    FROM cortex_sources
    WHERE task_id = ? AND credibility >= ?
    ORDER BY credibility DESC
    LIMIT ?
  `);

  for (const g of groups) {
    const sources = sourceStmt.all(g.task_id, opts.minCredibility, MAX_SOURCES_PER_GROUP) as SourceGroup['sources'];

    if (sources.length >= 2) {
      result.push({
        task_id: g.task_id,
        sources,
        avg_credibility: g.avg_cred,
        source_count: g.cnt,
      });
    }
  }

  return result;
}

// ============================================================
// LLM Claims 抽取
// ============================================================

interface ExtractedClaims {
  claims: Array<{
    claim_text: string;
    supporting_sources: string[];
    counter_sources: string[];
    confidence: number;
    domain: string;
  }>;
}

function buildClaimsPrompt(group: SourceGroup): string {
  const sourceSummaries = group.sources.map((s, i) => {
    return `[${i + 1}] citation_key="${s.citation_key}" (credibility=${s.credibility.toFixed(2)}, expert=${s.expert_model || 'unknown'})
标题: ${s.title}
发现: ${(s.finding || '').substring(0, 500)}`;
  }).join('\n\n');

  return `请从以下 ${group.sources.length} 条研究发现中提炼核心论断 (claims)。

## 研究发现 (task_id: ${group.task_id})

${sourceSummaries}

## 提取要求

1. 提炼 3-5 条核心 claims（论断/结论）
2. 每条 claim 必须引用 supporting_sources（使用 citation_key）
3. 主动寻找矛盾观点（counter_sources）：不同 source 之间是否有矛盾？
4. 置信度基于 source 的 credibility 加权计算
5. 标注领域 domain（如：AI_engineering, system_design, performance, architecture, memory_system, agent_design, knowledge_management 等）

## 输出格式

只输出 JSON，不要其他内容：
{
  "claims": [
    {
      "claim_text": "核心论断（20-60字）",
      "supporting_sources": ["citation_key_1", "citation_key_2"],
      "counter_sources": ["如果有反面证据的 citation_key"],
      "confidence": 0.85,
      "domain": "AI_engineering"
    }
  ]
}`;
}

function buildSystemPrompt(model: string): string {
  const anchor = loadAnchorSystemPrompt(model);

  const basePrompt = `你是一名学术评审专家，擅长从多条研究发现中提炼核心论断。

你的职责：
1. 证据优先：任何 claim 必须有明确的 source 支撑
2. 交叉验证：对比不同 source 的发现，寻找一致和矛盾
3. 量化置信度：基于 source 的 credibility 加权
4. 领域分类：准确标注每条 claim 的知识领域
5. 不确定时降低置信度而非编造

输出必须是合法的 JSON。`;

  if (anchor) {
    return `${anchor}\n\n${basePrompt}`;
  }
  return basePrompt;
}

async function extractClaims(
  group: SourceGroup,
  model: string
): Promise<ExtractedClaims> {
  const systemPrompt = buildSystemPrompt(model);
  const userPrompt = buildClaimsPrompt(group);

  const raw = await callLLM(model, systemPrompt, userPrompt, 0.3);

  // 提取 JSON
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error('未找到 JSON 输出');
  }

  const parsed = JSON.parse(jsonMatch[0]) as ExtractedClaims;

  // 验证
  if (!parsed.claims || !Array.isArray(parsed.claims) || parsed.claims.length === 0) {
    throw new Error('claims 数组为空或格式错误');
  }

  // 规范化
  const validCitationKeys = new Set(group.sources.map(s => s.citation_key));

  for (const claim of parsed.claims) {
    // 过滤无效的 citation_key
    claim.supporting_sources = (claim.supporting_sources || [])
      .filter(k => validCitationKeys.has(k));
    claim.counter_sources = (claim.counter_sources || [])
      .filter(k => validCitationKeys.has(k));

    // 确保至少有一个 supporting_source
    if (claim.supporting_sources.length === 0 && group.sources.length > 0) {
      claim.supporting_sources = [group.sources[0].citation_key];
    }

    // 置信度范围检查
    claim.confidence = Math.max(0.1, Math.min(1.0, claim.confidence || 0.5));

    // 基于 source credibility 加权调整置信度
    const avgCred = group.avg_credibility;
    claim.confidence = claim.confidence * 0.7 + avgCred * 0.3;

    // domain 默认值
    if (!claim.domain) {
      claim.domain = 'general';
    }
  }

  return parsed;
}

// ============================================================
// 写入数据库
// ============================================================

interface WriteResult {
  claimsWritten: number;
  entitiesLinked: number;
}

function writeClaimsToDb(
  db: Database,
  group: SourceGroup,
  extracted: ExtractedClaims,
  model: string
): WriteResult {
  let claimsWritten = 0;
  let entitiesLinked = 0;

  const insertClaim = db.prepare(`
    INSERT INTO cortex_claims (task_id, claim_text, supporting_sources, counter_sources, expert_model, confidence)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  // 检查是否有 knowledge_source_links 表
  let hasSourceLinks = false;
  try {
    db.query(`SELECT 1 FROM knowledge_source_links LIMIT 0`).get();
    hasSourceLinks = true;
  } catch {
    // 表不存在
  }

  for (const claim of extracted.claims) {
    try {
      // 去重：检查是否已存在相似 claim
      const existing = db.query(`
        SELECT claim_id FROM cortex_claims
        WHERE task_id = ? AND claim_text = ?
      `).get(group.task_id, claim.claim_text) as any;

      if (existing) continue;

      insertClaim.run(
        group.task_id,
        claim.claim_text,
        JSON.stringify(claim.supporting_sources),
        JSON.stringify(claim.counter_sources),
        model,
        claim.confidence
      );
      claimsWritten++;

      // 尝试关联 knowledge_entities
      // 简单策略：在 claim_text 中搜索已有实体名称
      if (hasSourceLinks) {
        const entities = db.query(`
          SELECT entity_id, name FROM knowledge_entities
        `).all() as Array<{ entity_id: string; name: string }>;

        for (const entity of entities) {
          if (claim.claim_text.includes(entity.name) && entity.name.length >= 3) {
            try {
              db.run(`
                INSERT OR IGNORE INTO knowledge_source_links (entity_id, source_type, source_id)
                VALUES (?, 'cortex_claim', ?)
              `, entity.entity_id, `${group.task_id}:${claim.claim_text.substring(0, 50)}`);
              entitiesLinked++;
            } catch {
              // ignore link errors
            }
          }
        }
      }
    } catch (error: any) {
      console.log(`      ⚠️  写入 claim 失败: ${error.message}`);
    }
  }

  return { claimsWritten, entitiesLinked };
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

  console.log('🧠 Claims Enricher - 从 cortex_sources 生成高质量 cortex_claims\n');
  console.log(`配置:`);
  console.log(`   模型: ${opts.model}`);
  console.log(`   限制: ${opts.limit} 组`);
  console.log(`   最低可信度: ${opts.minCredibility}`);
  console.log(`   模式: ${opts.force ? '强制重处理' : '增量'}`);
  console.log(`   Dry Run: ${opts.dryRun}`);

  // 统计
  const totalSources = (db.query(`SELECT COUNT(*) as c FROM cortex_sources`).get() as any)?.c ?? 0;
  const totalGroups = (db.query(`SELECT COUNT(DISTINCT task_id) as c FROM cortex_sources`).get() as any)?.c ?? 0;
  const qualifiedGroups = (db.query(`
    SELECT COUNT(*) as c FROM (
      SELECT task_id FROM cortex_sources
      WHERE credibility >= ?
      GROUP BY task_id HAVING COUNT(*) >= 2
    )
  `).get(opts.minCredibility) as any)?.c ?? 0;
  const existingClaims = (db.query(`SELECT COUNT(*) as c FROM cortex_claims`).get() as any)?.c ?? 0;

  console.log(`\n📊 数据源统计:`);
  console.log(`   cortex_sources 总数: ${totalSources}`);
  console.log(`   task_id 分组数: ${totalGroups}`);
  console.log(`   合格分组 (≥2 sources, credibility≥${opts.minCredibility}): ${qualifiedGroups}`);
  console.log(`   已有 cortex_claims: ${existingClaims}`);
  console.log(`   历史已处理分组: ${progress.processed_task_ids.length}`);

  // 获取候选分组
  const groups = getCandidateGroups(db, opts, progress);

  if (groups.length === 0) {
    console.log('\n✅ 没有需要处理的分组');
    if (!opts.force && progress.processed_task_ids.length >= qualifiedGroups) {
      console.log('   所有合格分组已处理');
    }
    db.close();
    return;
  }

  console.log(`\n📝 本次将处理: ${groups.length} 组\n`);

  // Dry Run 模式
  if (opts.dryRun) {
    console.log('┌────────────────────────────────────────────────────┬──────────┬─────────┐');
    console.log('│ task_id                                            │ sources  │ avg_cred│');
    console.log('├────────────────────────────────────────────────────┼──────────┼─────────┤');
    for (const g of groups) {
      const tid = g.task_id.substring(0, 50).padEnd(50);
      console.log(`│ ${tid} │ ${String(g.source_count).padStart(8)} │ ${g.avg_credibility.toFixed(2).padStart(7)} │`);
    }
    console.log('└────────────────────────────────────────────────────┴──────────┴─────────┘');
    console.log('\n💡 去掉 --dry-run 参数开始实际抽取');
    db.close();
    return;
  }

  // 实际抽取
  let processed = 0;
  let failed = 0;
  let totalClaimsGenerated = 0;
  let totalEntitiesLinked = 0;

  for (let i = 0; i < groups.length; i++) {
    const group = groups[i];
    const progressStr = `[${i + 1}/${groups.length}]`;
    const shortTaskId = group.task_id.substring(0, 40);

    console.log(`${progressStr} 处理: "${shortTaskId}..." (${group.source_count} sources, avg_cred=${group.avg_credibility.toFixed(2)})`);

    try {
      // 1. 调用 LLM 抽取 claims
      const extracted = await extractClaims(group, opts.model);

      // 2. 写入数据库
      const writeResult = writeClaimsToDb(db, group, extracted, opts.model);

      // 3. 更新统计
      processed++;
      totalClaimsGenerated += writeResult.claimsWritten;
      totalEntitiesLinked += writeResult.entitiesLinked;

      // 4. 记录到 progress
      progress.processed_task_ids.push(group.task_id);

      console.log(`   ✅ 生成 claims: ${writeResult.claimsWritten}, 实体关联: ${writeResult.entitiesLinked} (${extracted.claims.length} extracted)`);

    } catch (error: any) {
      failed++;
      progress.failed_task_ids.push(group.task_id);
      console.log(`   ❌ 失败: ${error.message}`);
    }

    // 5. 速率控制（最后一条不等待）
    if (i < groups.length - 1) {
      await sleep(RATE_LIMIT_MS);
    }

    // 6. 每 5 组保存一次进度
    if ((i + 1) % 5 === 0) {
      saveProgress(progress);
    }
  }

  // 最终保存进度
  const duration = Date.now() - startTime;
  progress.last_run = new Date().toISOString();
  progress.total_processed += processed;
  progress.total_claims_generated += totalClaimsGenerated;
  progress.total_entities_linked += totalEntitiesLinked;
  progress.runs.push({
    timestamp: new Date().toISOString(),
    groups_processed: processed,
    groups_failed: failed,
    claims_generated: totalClaimsGenerated,
    model: opts.model,
    duration_ms: duration,
  });
  saveProgress(progress);

  // 输出报告
  console.log('\n' + '═'.repeat(60));
  console.log('📊 Claims Enricher 报告');
  console.log('═'.repeat(60));

  console.log(`\n本次处理:`);
  console.log(`   成功分组: ${processed}`);
  console.log(`   失败分组: ${failed}`);
  console.log(`   耗时: ${(duration / 1000).toFixed(1)} 秒`);

  console.log(`\n生成成果:`);
  console.log(`   新增 cortex_claims: ${totalClaimsGenerated}`);
  console.log(`   实体关联: ${totalEntitiesLinked}`);

  // 清理后统计
  const afterClaims = (db.query(`SELECT COUNT(*) as c FROM cortex_claims`).get() as any)?.c ?? 0;
  const afterByDomain = db.query(`
    SELECT
      CASE
        WHEN claim_text LIKE '%AI%' OR claim_text LIKE '%agent%' OR claim_text LIKE '%LLM%' THEN 'AI_engineering'
        WHEN claim_text LIKE '%性能%' OR claim_text LIKE '%优化%' OR claim_text LIKE '%延迟%' THEN 'performance'
        WHEN claim_text LIKE '%架构%' OR claim_text LIKE '%设计%' THEN 'architecture'
        ELSE 'other'
      END as domain_guess,
      COUNT(*) as cnt
    FROM cortex_claims
    GROUP BY domain_guess
    ORDER BY cnt DESC
  `).all() as any[];

  console.log(`\n知识库现状:`);
  console.log(`   cortex_claims 总数: ${afterClaims} (原 ${existingClaims}, +${afterClaims - existingClaims})`);

  if (afterByDomain.length > 0) {
    console.log(`\n领域分布 (估算):`);
    for (const d of afterByDomain) {
      console.log(`   ${d.domain_guess}: ${d.cnt}`);
    }
  }

  // 高可信度 claims 样本
  const topClaims = db.query(`
    SELECT claim_text, confidence, expert_model
    FROM cortex_claims
    ORDER BY confidence DESC
    LIMIT 5
  `).all() as any[];

  if (topClaims.length > 0) {
    console.log(`\n🏆 高可信度 Claims Top 5:`);
    for (const c of topClaims) {
      const text = c.claim_text.substring(0, 60);
      console.log(`   [${c.confidence.toFixed(2)}] ${text}...`);
    }
  }

  // 累计统计
  console.log(`\n累计统计 (所有运行):`);
  console.log(`   总处理分组: ${progress.total_processed}`);
  console.log(`   总生成 claims: ${progress.total_claims_generated}`);
  console.log(`   总实体关联: ${progress.total_entities_linked}`);
  console.log(`   运行次数: ${progress.runs.length}`);

  const remainingGroups = qualifiedGroups - progress.processed_task_ids.length;
  if (remainingGroups > 0) {
    console.log(`\n💡 还有 ${remainingGroups} 组待处理，再次运行即可继续`);
  }

  db.close();
  console.log('\n🎉 Claims Enricher 完成!');
}

// ============================================================
// 入口
// ============================================================

main().catch(err => {
  console.error('❌ Claims Enricher 失败:', err);
  process.exit(1);
});
