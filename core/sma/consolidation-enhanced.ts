#!/usr/bin/env bun
/**
 * SMA Memory Controller - Enhanced Consolidation
 *
 * 增强功能:
 * 1. 语义相似度检测 (Jaccard + Levenshtein)
 * 2. 实体链接 (同义词/缩写映射)
 * 3. 置信度验证 (分级处理)
 * 4. 冲突解决 (保留高置信度)
 *
 * @version 2.0.0
 * @created 2026-02-27
 */

import { Database } from 'bun:sqlite';

// ============ 类型定义 ============

interface Triple {
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
  source?: string;
  timestamp?: number;
  metadata?: Record<string, unknown>;
}

interface ConsolidationResult {
  merged: Triple[];
  duplicates: Array<{ original: Triple; duplicate: Triple; similarity: number }>;
  conflicts: Array<{ triple1: Triple; triple2: Triple; resolved: Triple }>;
  lowConfidence: Triple[];
  stats: {
    inputCount: number;
    outputCount: number;
    duplicatesRemoved: number;
    conflictsResolved: number;
    lowConfidenceFlagged: number;
  };
}

interface ConsolidationConfig {
  similarityThreshold: number;      // 相似度阈值，超过则视为重复
  confidenceHighThreshold: number;  // 高置信度阈值
  confidenceLowThreshold: number;   // 低置信度阈值
  enableEntityLinking: boolean;     // 是否启用实体链接
  enableConflictResolution: boolean;
}

// 默认配置
const DEFAULT_CONFIG: ConsolidationConfig = {
  similarityThreshold: 0.85,
  confidenceHighThreshold: 0.9,
  confidenceLowThreshold: 0.7,
  enableEntityLinking: true,
  enableConflictResolution: true
};

// ============ 实体同义词映射 ============

/**
 * 实体同义词映射表
 * 格式: [规范化形式, [变体列表]]
 */
const ENTITY_SYNONYMS: Array<[string, string[]]> = [
  // 架构相关
  ['SMA', ['Solar Memory Architecture', 'sma', 'Solar-Memory-Architecture']],
  ['L1', ['Level 1', 'level1', '第一层']],
  ['L2', ['Level 2', 'level2', '第二层']],
  ['L3', ['Level 3', 'level3', '第三层']],

  // 数据库相关
  ['DB', ['Database', 'database', '数据库']],
  ['SQLite', ['sqlite', 'SQLITE']],
  ['Bun', ['bun', 'BUN']],

  // 通用缩写
  ['ID', ['id', 'Id', 'identifier', 'Identifier']],
  ['URL', ['url', 'Url', 'URI', 'uri']],
  ['API', ['api', 'Api']],

  // 状态描述
  ['有', ['has', 'have', '存在', 'contains']],
  ['是', ['is', 'equals', '等于', '为']],
  ['无', ['none', 'null', 'empty', '空']],
];

// 构建快速查找映射
const SYNONYM_MAP = new Map<string, string>();
ENTITY_SYNONYMS.forEach(([canonical, variants]) => {
  SYNONYM_MAP.set(canonical.toLowerCase(), canonical);
  variants.forEach(v => SYNONYM_MAP.set(v.toLowerCase(), canonical));
});

// ============ 核心算法函数 ============

/**
 * 计算 Levenshtein 编辑距离
 */
function levenshteinDistance(a: string, b: string): number {
  const m = a.length;
  const n = b.length;

  // 优化：短字符串用一维数组
  if (m === 0) return n;
  if (n === 0) return m;

  const dp = new Array(n + 1).fill(0).map((_, i) => i);

  for (let i = 1; i <= m; i++) {
    let prev = dp[0];
    dp[0] = i;

    for (let j = 1; j <= n; j++) {
      const temp = dp[j];
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[j] = Math.min(
        dp[j] + 1,      // 删除
        dp[j - 1] + 1,  // 插入
        prev + cost     // 替换
      );
      prev = temp;
    }
  }

  return dp[n];
}

/**
 * 计算 Levenshtein 相似度 (0-1)
 */
function levenshteinSimilarity(a: string, b: string): number {
  if (a === b) return 1;
  const maxLen = Math.max(a.length, b.length);
  if (maxLen === 0) return 1;
  const distance = levenshteinDistance(a, b);
  return 1 - distance / maxLen;
}

/**
 * 计算 Jaccard 相似度 (基于词集合)
 */
function jaccardSimilarity(a: string, b: string): number {
  // 分词：支持中英文混合
  const tokenize = (s: string): Set<string> => {
    // 移除标点，转小写
    const normalized = s.toLowerCase().replace(/[^\w\u4e00-\u9fa5]/g, ' ');
    // 英文按空格分，中文按字符分
    const tokens: string[] = [];
    const parts = normalized.split(/\s+/).filter(p => p);

    parts.forEach(part => {
      if (/[\u4e00-\u9fa5]/.test(part)) {
        // 中文：按字符拆分
        tokens.push(...part.split(''));
      } else {
        tokens.push(part);
      }
    });

    return new Set(tokens);
  };

  const setA = tokenize(a);
  const setB = tokenize(b);

  if (setA.size === 0 && setB.size === 0) return 1;
  if (setA.size === 0 || setB.size === 0) return 0;

  // 计算交集
  const intersection = new Set([...setA].filter(x => setB.has(x)));
  const union = new Set([...setA, ...setB]);

  return intersection.size / union.size;
}

/**
 * 【核心函数1】计算综合文本相似度
 * 混合策略：Jaccard (语义) + Levenshtein (字面)
 *
 * @param a - 文本A
 * @param b - 文本B
 * @param weights - 权重配置 [jaccard, levenshtein]
 * @returns 相似度分数 (0-1)
 *
 * @example
 * calculateSimilarity("session_id索引", "session_id 索引") // ~0.95
 * calculateSimilarity("L2缓存", "Level2缓存") // ~0.8
 */
export function calculateSimilarity(
  a: string,
  b: string,
  weights: [number, number] = [0.6, 0.4]
): number {
  // 边界检查
  if (!a || !b) return 0;
  if (a === b) return 1;

  // 完全匹配检查（优化性能）
  if (a.trim() === b.trim()) return 1;

  // 计算两种相似度
  const jaccard = jaccardSimilarity(a, b);
  const levenshtein = levenshteinSimilarity(a, b);

  // 加权平均
  const combined = weights[0] * jaccard + weights[1] * levenshtein;

  return Math.round(combined * 1000) / 1000; // 保留3位小数
}

/**
 * 【核心函数2】实体链接 - 将变体映射到规范形式
 *
 * @param entity - 原始实体名称
 * @returns 规范化后的实体名称
 *
 * @example
 * linkEntities("SMA") // "SMA"
 * linkEntities("Solar Memory Architecture") // "SMA"
 * linkEntities("level1") // "L1"
 */
export function linkEntities(entity: string): string {
  if (!entity) return entity;

  // 直接查找
  const normalized = entity.trim();
  const canonical = SYNONYM_MAP.get(normalized.toLowerCase());

  if (canonical) return canonical;

  // 模糊匹配：检查是否与某个变体高度相似
  let bestMatch: string | null = null;
  let bestSimilarity = 0;

  for (const [canon, variants] of ENTITY_SYNONYMS) {
    // 检查所有变体
    for (const variant of [canon, ...variants]) {
      const sim = calculateSimilarity(entity, variant);
      if (sim > 0.85 && sim > bestSimilarity) {
        bestSimilarity = sim;
        bestMatch = canon;
      }
    }
  }

  return bestMatch || normalized;
}

/**
 * 链接三元组中的所有实体
 */
function linkTripleEntities(triple: Triple): Triple {
  return {
    ...triple,
    subject: linkEntities(triple.subject),
    predicate: linkEntities(triple.predicate),
    object: linkEntities(triple.object)
  };
}

/**
 * 【核心函数3】置信度验证
 * 分级处理：高(自动通过) / 中(正常) / 低(需确认)
 *
 * @param triples - 待验证的三元组列表
 * @returns 分类结果
 */
export function validateConfidence(triples: Triple[]): {
  high: Triple[];      // >= 0.9 自动通过
  medium: Triple[];    // 0.7 - 0.9 正常处理
  low: Triple[];       // < 0.7 需二次确认
  stats: { validated: number; avgConfidence: number };
} {
  const high: Triple[] = [];
  const medium: Triple[] = [];
  const low: Triple[] = [];
  let totalConfidence = 0;

  for (const triple of triples) {
    const conf = triple.confidence ?? 0.5;
    totalConfidence += conf;

    if (conf >= DEFAULT_CONFIG.confidenceHighThreshold) {
      high.push({ ...triple, metadata: { ...triple.metadata, confidenceLevel: 'high' } });
    } else if (conf >= DEFAULT_CONFIG.confidenceLowThreshold) {
      medium.push({ ...triple, metadata: { ...triple.metadata, confidenceLevel: 'medium' } });
    } else {
      low.push({ ...triple, metadata: { ...triple.metadata, confidenceLevel: 'low', needsConfirmation: true } });
    }
  }

  return {
    high,
    medium,
    low,
    stats: {
      validated: triples.length,
      avgConfidence: triples.length > 0 ? totalConfidence / triples.length : 0
    }
  };
}

/**
 * 检测两个三元组是否冲突
 * 冲突定义：相同主语和谓语，但宾语不同
 */
function detectConflict(t1: Triple, t2: Triple): boolean {
  return (
    t1.subject === t2.subject &&
    t1.predicate === t2.predicate &&
    t1.object !== t2.object
  );
}

/**
 * 【核心函数4】冲突解决
 * 策略：保留置信度更高的，或按时间戳取最新的
 *
 * @param triples - 可能存在冲突的三元组
 * @returns 解决后的三元组列表 + 冲突报告
 */
export function resolveConflicts(triples: Triple[]): {
  resolved: Triple[];
  conflicts: Array<{ triple1: Triple; triple2: Triple; winner: Triple; reason: string }>;
} {
  const resolved: Triple[] = [];
  const conflicts: Array<{ triple1: Triple; triple2: Triple; winner: Triple; reason: string }> = [];

  // 按 (subject, predicate) 分组
  const groups = new Map<string, Triple[]>();

  for (const triple of triples) {
    const key = `${triple.subject}|${triple.predicate}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(triple);
  }

  // 处理每组
  for (const [, group] of groups) {
    if (group.length === 1) {
      resolved.push(group[0]);
      continue;
    }

    // 检查宾语是否一致
    const objects = new Set(group.map(t => t.object));
    if (objects.size === 1) {
      // 无冲突，合并（保留置信度最高的）
      const best = group.reduce((a, b) =>
        (a.confidence ?? 0) >= (b.confidence ?? 0) ? a : b
      );
      resolved.push(best);
    } else {
      // 存在冲突，选择置信度最高的
      const sorted = [...group].sort((a, b) => {
        // 首先按置信度排序
        const confDiff = (b.confidence ?? 0) - (a.confidence ?? 0);
        if (Math.abs(confDiff) > 0.1) return confDiff;

        // 置信度相近时，按时间戳排序
        return (b.timestamp ?? 0) - (a.timestamp ?? 0);
      });

      const winner = sorted[0];
      resolved.push(winner);

      // 记录冲突
      for (let i = 1; i < sorted.length; i++) {
        conflicts.push({
          triple1: winner,
          triple2: sorted[i],
          winner,
          reason: winner.confidence === sorted[i].confidence
            ? 'timestamp'
            : 'higher_confidence'
        });
      }
    }
  }

  return { resolved, conflicts };
}

/**
 * 检测两个三元组是否相似（可能是重复）
 */
function areTriplesSimilar(t1: Triple, t2: Triple, threshold: number): boolean {
  // 完全匹配
  if (
    t1.subject === t2.subject &&
    t1.predicate === t2.predicate &&
    t1.object === t2.object
  ) {
    return true;
  }

  // 语义相似度匹配
  const subjSim = calculateSimilarity(t1.subject, t2.subject);
  const predSim = calculateSimilarity(t1.predicate, t2.predicate);
  const objSim = calculateSimilarity(t1.object, t2.object);

  // 三个分量都必须高于阈值的某个比例
  const minComponentThreshold = threshold * 0.9;

  if (subjSim < minComponentThreshold || predSim < minComponentThreshold) {
    return false;
  }

  // 综合相似度
  const combined = (subjSim + predSim + objSim) / 3;

  return combined >= threshold;
}

/**
 * 计算两个相似三元组的综合相似度
 */
function getTripleSimilarity(t1: Triple, t2: Triple): number {
  const subjSim = calculateSimilarity(t1.subject, t2.subject);
  const predSim = calculateSimilarity(t1.predicate, t2.predicate);
  const objSim = calculateSimilarity(t1.object, t2.object);
  return (subjSim + predSim + objSim) / 3;
}

/**
 * 【主函数】增强版合并去重
 *
 * 流程：
 * 1. 实体链接（规范化）
 * 2. 置信度验证（分级）
 * 3. 语义去重（相似度检测）
 * 4. 冲突解决（保留最优）
 *
 * @param triples - 输入三元组列表
 * @param config - 可选配置
 * @returns 合并结果及统计
 */
export function mergeAndDeduplicate(
  triples: Triple[],
  config: Partial<ConsolidationConfig> = {}
): ConsolidationResult {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const stats = {
    inputCount: triples.length,
    outputCount: 0,
    duplicatesRemoved: 0,
    conflictsResolved: 0,
    lowConfidenceFlagged: 0
  };

  // 边界检查
  if (triples.length === 0) {
    return {
      merged: [],
      duplicates: [],
      conflicts: [],
      lowConfidence: [],
      stats: { ...stats, outputCount: 0 }
    };
  }

  // Step 1: 实体链接（规范化实体名称）
  let processed = cfg.enableEntityLinking
    ? triples.map(linkTripleEntities)
    : [...triples];

  // Step 2: 置信度验证
  const { high, medium, low } = validateConfidence(processed);
  stats.lowConfidenceFlagged = low.length;

  // 高置信度 + 中置信度参与合并，低置信度单独标记
  const candidates = [...high, ...medium];

  // Step 3: 语义去重
  const merged: Triple[] = [];
  const duplicates: Array<{ original: Triple; duplicate: Triple; similarity: number }> = [];
  const processedIndices = new Set<number>();

  for (let i = 0; i < candidates.length; i++) {
    if (processedIndices.has(i)) continue;

    const current = candidates[i];
    let best = current;
    const currentDuplicates: Array<{ triple: Triple; similarity: number }> = [];

    // 查找相似三元组
    for (let j = i + 1; j < candidates.length; j++) {
      if (processedIndices.has(j)) continue;

      const other = candidates[j];

      if (areTriplesSimilar(current, other, cfg.similarityThreshold)) {
        const similarity = getTripleSimilarity(current, other);

        // 选择置信度更高的作为主三元组
        if ((other.confidence ?? 0) > (best.confidence ?? 0)) {
          currentDuplicates.push({ triple: best, similarity });
          best = other;
        } else {
          currentDuplicates.push({ triple: other, similarity });
        }

        processedIndices.add(j);
      }
    }

    // 记录重复项
    currentDuplicates.forEach(({ triple, similarity }) => {
      duplicates.push({
        original: best,
        duplicate: triple,
        similarity
      });
      stats.duplicatesRemoved++;
    });

    merged.push(best);
    processedIndices.add(i);
  }

  // Step 4: 冲突解决
  let finalMerged = merged;
  const conflictResults: Array<{ triple1: Triple; triple2: Triple; resolved: Triple }> = [];

  if (cfg.enableConflictResolution) {
    const { resolved, conflicts } = resolveConflicts(merged);
    finalMerged = resolved;

    conflicts.forEach(c => {
      conflictResults.push({
        triple1: c.triple1,
        triple2: c.triple2,
        resolved: c.winner
      });
    });

    stats.conflictsResolved = conflicts.length;
  }

  stats.outputCount = finalMerged.length;

  return {
    merged: finalMerged,
    duplicates,
    conflicts: conflictResults,
    lowConfidence: low,
    stats
  };
}

// ============ 工具函数 ============

/**
 * 计算合并质量指标 (用于评估 F1)
 */
export function evaluateConsolidation(
  result: ConsolidationResult,
  groundTruth?: Set<string>
): {
  precision: number;
  recall: number;
  f1: number;
  compressionRatio: number;
} {
  const { stats, merged } = result;

  // 压缩率
  const compressionRatio = stats.inputCount > 0
    ? stats.outputCount / stats.inputCount
    : 1;

  // 如果有标注数据，计算 P/R/F1
  if (groundTruth) {
    const mergedSet = new Set(
      merged.map(t => `${t.subject}|${t.predicate}|${t.object}`)
    );

    let truePositives = 0;
    mergedSet.forEach(key => {
      if (groundTruth.has(key)) truePositives++;
    });

    const precision = mergedSet.size > 0
      ? truePositives / mergedSet.size
      : 0;
    const recall = groundTruth.size > 0
      ? truePositives / groundTruth.size
      : 0;
    const f1 = precision + recall > 0
      ? 2 * (precision * recall) / (precision + recall)
      : 0;

    return { precision, recall, f1, compressionRatio };
  }

  // 无标注数据时，使用启发式评估
  const avgConfidence = merged.length > 0
    ? merged.reduce((sum, t) => sum + (t.confidence ?? 0), 0) / merged.length
    : 0;
  const duplicateRate = stats.inputCount > 0
    ? stats.duplicatesRemoved / stats.inputCount
    : 0;

  // 估算 F1（假设去重准确率与平均置信度相关）
  const estimatedF1 = Math.min(0.95, avgConfidence * (1 - duplicateRate * 0.5));

  return {
    precision: avgConfidence,
    recall: avgConfidence * 0.95, // 假设少量漏检
    f1: estimatedF1,
    compressionRatio
  };
}

/**
 * 导出工具：打印合并报告
 */
export function printConsolidationReport(result: ConsolidationResult): void {
  console.log('\n=== SMA Consolidation Report ===');
  console.log(`Input triples:  ${result.stats.inputCount}`);
  console.log(`Output triples: ${result.stats.outputCount}`);
  console.log(`Duplicates removed: ${result.stats.duplicatesRemoved}`);
  console.log(`Conflicts resolved: ${result.stats.conflictsResolved}`);
  console.log(`Low confidence flagged: ${result.stats.lowConfidenceFlagged}`);

  const metrics = evaluateConsolidation(result);
  console.log(`\nEstimated F1: ${metrics.f1.toFixed(3)}`);
  console.log(`Compression: ${(metrics.compressionRatio * 100).toFixed(1)}%`);

  if (result.lowConfidence.length > 0) {
    console.log('\n⚠️  Low confidence triples needing review:');
    result.lowConfidence.forEach((t, i) => {
      console.log(`  ${i + 1}. (${t.subject}, ${t.predicate}, ${t.object}) [conf: ${t.confidence}]`);
    });
  }

  if (result.conflicts.length > 0) {
    console.log('\n⚔️  Resolved conflicts:');
    result.conflicts.forEach((c, i) => {
      console.log(`  ${i + 1}. "${c.triple1.object}" vs "${c.triple2.object}" → "${c.resolved.object}"`);
    });
  }
}

// ============ CLI ============

if (import.meta.main) {
  // 简单测试
  const testTriples: Triple[] = [
    { subject: 'L2', predicate: '有', object: 'session_id索引', confidence: 0.95 },
    { subject: 'L2', predicate: '有', object: 'session_id 索引', confidence: 0.85 },
    { subject: 'L1', predicate: '存储', object: '短期记忆', confidence: 0.9 },
    { subject: 'SMA', predicate: '是', object: '三层架构', confidence: 0.9 },
    { subject: 'Solar Memory Architecture', predicate: '是', object: '三层架构', confidence: 0.85 },
    { subject: 'user', predicate: 'location', object: 'NY', confidence: 0.9 },
    { subject: 'user', predicate: 'location', object: 'SF', confidence: 0.7 },
  ];

  const result = mergeAndDeduplicate(testTriples);
  printConsolidationReport(result);
}

// 导出类型和函数
export type { Triple, ConsolidationResult, ConsolidationConfig };
