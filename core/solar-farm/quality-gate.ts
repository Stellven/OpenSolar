/**
 * Quality Gate System v1.0 - 质量门禁 + 分赛道OKR + 成本账本
 *
 * 工程化管理:
 * 1. 质量门禁 (Quality Gate) - CI风格，没过不能进下一阶段
 * 2. 分赛道 OKR - 研究/架构/实现/评审各有KPI
 * 3. SRE 错误预算 - 高风险赛道 RiskPenalty 权重高
 * 4. 赛季制 - 每周/月结算，避免剧烈波动
 * 5. 成本账本 - 实时记账，价格表可热更新
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// Schema: 质量门禁
// ============================================================

// 质量门禁配置
db.run(`
  CREATE TABLE IF NOT EXISTS quality_gates (
    gate_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    stage TEXT NOT NULL,              -- 'design' | 'implement' | 'review' | 'deploy'

    -- 阈值配置
    min_correctness REAL DEFAULT 0.7,
    min_rigor REAL DEFAULT 0.6,
    min_completeness REAL DEFAULT 0.6,
    max_risk_score REAL DEFAULT 0.3,

    -- 必须条件
    required_evidence TEXT,           -- JSON: ['unit_test', 'integration_test', ...]
    required_reviewers INTEGER DEFAULT 1,

    -- 赛道风险等级
    risk_level TEXT DEFAULT 'medium', -- 'low' | 'medium' | 'high' | 'critical'

    enabled BOOLEAN DEFAULT true,

    UNIQUE(task_type, stage)
  )
`);

// 门禁检查记录
db.run(`
  CREATE TABLE IF NOT EXISTS quality_gate_checks (
    check_id TEXT PRIMARY KEY,
    gate_id TEXT NOT NULL,
    run_id TEXT NOT NULL,

    -- 检查结果
    passed BOOLEAN NOT NULL,
    scores TEXT NOT NULL,             -- JSON: {correctness, rigor, ...}
    failed_criteria TEXT,             -- JSON: ['min_correctness', ...]
    missing_evidence TEXT,            -- JSON: ['unit_test', ...]

    -- 决策
    action TEXT NOT NULL,             -- 'pass' | 'block' | 'warn' | 'override'
    override_reason TEXT,
    override_by TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// 分赛道 OKR
db.run(`
  CREATE TABLE IF NOT EXISTS track_okrs (
    okr_id TEXT PRIMARY KEY,
    track TEXT NOT NULL,              -- 'research' | 'architecture' | 'implementation' | 'review'
    season TEXT NOT NULL,             -- '2026-Q1', '2026-W07', ...

    -- KPI 权重
    kpi_weights TEXT NOT NULL,        -- JSON: {quality: 0.4, speed: 0.2, cost: 0.2, innovation: 0.2}

    -- 目标
    target_quality REAL DEFAULT 0.8,
    target_speed REAL,                -- median latency
    target_cost REAL,                 -- dollar per task
    target_innovation REAL,           -- 0-1

    -- 实际
    actual_quality REAL,
    actual_speed REAL,
    actual_cost REAL,
    actual_innovation REAL,

    -- 评分
    okr_score REAL,

    status TEXT DEFAULT 'active',     -- 'active' | 'closed'

    UNIQUE(track, season)
  )
`);

// 赛季结算
db.run(`
  CREATE TABLE IF NOT EXISTS season_settlements (
    settlement_id TEXT PRIMARY KEY,
    season TEXT NOT NULL,
    settled_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- 结算数据
    leaderboard_snapshot TEXT,        -- JSON: 排名快照
    promotion_decisions TEXT,         -- JSON: 晋升决定
    demotion_decisions TEXT,          -- JSON: 降级决定
    route_weight_updates TEXT,        -- JSON: 路由权重更新

    UNIQUE(season)
  )
`);

// 成本账本 (实时记账)
db.run(`
  CREATE TABLE IF NOT EXISTS cost_ledger (
    ledger_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_variant TEXT NOT NULL,

    -- Token 消耗
    input_tokens INTEGER,
    output_tokens INTEGER,
    cached_input_tokens INTEGER,

    -- 工具调用
    tool_calls TEXT,                  -- JSON: [{tool, count, unit_cost}]

    -- 成本计算
    input_cost_usd REAL,
    output_cost_usd REAL,
    cache_savings_usd REAL,
    tool_cost_usd REAL,
    total_cost_usd REAL,

    -- 时间
    latency_ms INTEGER,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// 模型价格表 (可热更新)
db.run(`
  CREATE TABLE IF NOT EXISTS model_pricing (
    pricing_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    provider TEXT NOT NULL,

    -- 输入价格 ($/1M tokens)
    input_price REAL NOT NULL,
    cached_input_price REAL,
    cache_hit_price REAL,

    -- 输出价格 ($/1M tokens)
    output_price REAL NOT NULL,

    -- 缓存存储 ($/1M tokens/hour)
    cache_storage_price REAL,

    -- 生效时间
    effective_from DATETIME DEFAULT CURRENT_TIMESTAMP,
    effective_until DATETIME,

    is_current BOOLEAN DEFAULT true,

    UNIQUE(model_id, effective_from)
  )
`);

// ============================================================
// 成本计算 (价格表 2026-02)
// ============================================================

export const MODEL_PRICING_2026_02 = {
  // OpenAI
  'gpt-4o': { provider: 'openai', input: 1.75, cachedInput: 0.175, output: 14 },

  // Google Gemini
  'gemini-2.5-pro': { provider: 'google', input: 1.25, output: 10 },
  'gemini-2.5-flash': { provider: 'google', input: 0.30, output: 2.50 },
  'gemini-3-pro-preview': { provider: 'google', input: 1.25, output: 10 },
  'gemini-3-flash-preview': { provider: 'google', input: 0.30, output: 2.50 },

  // DeepSeek
  'deepseek-v3': { provider: 'deepseek', input: 0.55, cacheHit: 0.14, output: 2.19 },
  'deepseek-r1': { provider: 'deepseek', input: 0.55, cacheHit: 0.14, output: 2.19 },

  // 智谱 GLM
  'glm-4-plus': { provider: 'zhipu', input: 0.6, cachedInput: 0.11, output: 2.2 },
  'glm-4-flash': { provider: 'zhipu', input: 0.07, cachedInput: 0.01, output: 0.4 },
  'glm-4-flashx': { provider: 'zhipu', input: 0.07, cachedInput: 0.01, output: 0.4 },
  'glm-5': { provider: 'zhipu', input: 0.6, cachedInput: 0.11, output: 2.2 },

  // Anthropic
  'claude-opus-4-5': { provider: 'anthropic', input: 5, output: 25 },
  'claude-sonnet-4-5': { provider: 'anthropic', input: 1.5, output: 7.5 },
};

/**
 * 计算成本
 */
export function calculateCost(
  modelId: string,
  inputTokens: number,
  outputTokens: number,
  cachedInputTokens: number = 0
): {
  inputCost: number;
  outputCost: number;
  cacheSavings: number;
  totalCost: number;
} {
  const pricing = MODEL_PRICING_2026_02[modelId as keyof typeof MODEL_PRICING_2026_02];

  if (!pricing) {
    console.warn(`Unknown model: ${modelId}, using default pricing`);
    return {
      inputCost: (inputTokens / 1_000_000) * 1,
      outputCost: (outputTokens / 1_000_000) * 2,
      cacheSavings: 0,
      totalCost: (inputTokens / 1_000_000) * 1 + (outputTokens / 1_000_000) * 2
    };
  }

  // 输入成本 (考虑缓存)
  const regularInputTokens = inputTokens - cachedInputTokens;
  const inputCost = (regularInputTokens / 1_000_000) * pricing.input;

  // 缓存节省
  let cacheSavings = 0;
  if (cachedInputTokens > 0 && pricing.cachedInput) {
    const cachedCost = (cachedInputTokens / 1_000_000) * pricing.cachedInput;
    const regularCost = (cachedInputTokens / 1_000_000) * pricing.input;
    cacheSavings = regularCost - cachedCost;
  }

  // 输出成本
  const outputCost = (outputTokens / 1_000_000) * pricing.output;

  const totalCost = inputCost + outputCost - cacheSavings;

  return {
    inputCost,
    outputCost,
    cacheSavings,
    totalCost
  };
}

// ============================================================
// 质量门禁检查
// ============================================================

export interface QualityGateConfig {
  minCorrectness: number;
  minRigor: number;
  minCompleteness: number;
  maxRiskScore: number;
  requiredEvidence: string[];
  requiredReviewers: number;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

export const DEFAULT_GATE_CONFIGS: Record<string, QualityGateConfig> = {
  // 代码实现 - 标准
  'implementation:standard': {
    minCorrectness: 0.7,
    minRigor: 0.6,
    minCompleteness: 0.7,
    maxRiskScore: 0.3,
    requiredEvidence: ['unit_test'],
    requiredReviewers: 1,
    riskLevel: 'medium'
  },

  // 代码实现 - 高风险 (金融/安全)
  'implementation:critical': {
    minCorrectness: 0.9,
    minRigor: 0.85,
    minCompleteness: 0.9,
    maxRiskScore: 0.1,
    requiredEvidence: ['unit_test', 'integration_test', 'security_review'],
    requiredReviewers: 2,
    riskLevel: 'critical'
  },

  // 架构设计
  'architecture:standard': {
    minCorrectness: 0.8,
    minRigor: 0.8,
    minCompleteness: 0.75,
    maxRiskScore: 0.2,
    requiredEvidence: ['design_doc', 'tradeoff_analysis'],
    requiredReviewers: 2,
    riskLevel: 'high'
  },

  // 研究分析
  'research:standard': {
    minCorrectness: 0.75,
    minRigor: 0.8,
    minCompleteness: 0.7,
    maxRiskScore: 0.3,
    requiredEvidence: ['citations', 'reproduction_steps'],
    requiredReviewers: 1,
    riskLevel: 'medium'
  },

  // 快速原型
  'prototype:fast': {
    minCorrectness: 0.6,
    minRigor: 0.5,
    minCompleteness: 0.5,
    maxRiskScore: 0.5,
    requiredEvidence: [],
    requiredReviewers: 0,
    riskLevel: 'low'
  }
};

/**
 * 检查质量门禁
 */
export function checkQualityGate(
  scores: {
    correctness: number;
    rigor: number;
    completeness: number;
    usefulness: number;
    efficiency: number;
    safety: number;
  },
  evidence: string[],
  reviewerCount: number,
  config: QualityGateConfig
): {
  passed: boolean;
  failedCriteria: string[];
  missingEvidence: string[];
  action: 'pass' | 'block' | 'warn';
} {
  const failedCriteria: string[] = [];
  const missingEvidence: string[] = [];

  // 检查各项阈值
  if (scores.correctness < config.minCorrectness) {
    failedCriteria.push(`correctness: ${scores.correctness.toFixed(2)} < ${config.minCorrectness}`);
  }
  if (scores.rigor < config.minRigor) {
    failedCriteria.push(`rigor: ${scores.rigor.toFixed(2)} < ${config.minRigor}`);
  }
  if (scores.completeness < config.minCompleteness) {
    failedCriteria.push(`completeness: ${scores.completeness.toFixed(2)} < ${config.minCompleteness}`);
  }
  if (scores.safety > config.maxRiskScore) {
    failedCriteria.push(`risk: ${scores.safety.toFixed(2)} > ${config.maxRiskScore}`);
  }

  // 检查证据
  for (const req of config.requiredEvidence) {
    if (!evidence.includes(req)) {
      missingEvidence.push(req);
    }
  }

  // 检查评审人数
  if (reviewerCount < config.requiredReviewers) {
    failedCriteria.push(`reviewers: ${reviewerCount} < ${config.requiredReviewers}`);
  }

  const passed = failedCriteria.length === 0 && missingEvidence.length === 0;

  let action: 'pass' | 'block' | 'warn';
  if (passed) {
    action = 'pass';
  } else if (config.riskLevel === 'critical' || config.riskLevel === 'high') {
    action = 'block';
  } else {
    action = 'warn';
  }

  return { passed, failedCriteria, missingEvidence, action };
}

// ============================================================
// 分赛道 OKR
// ============================================================

export interface TrackKPI {
  quality: number;      // 权重
  speed: number;        // 权重
  cost: number;         // 权重
  innovation: number;   // 权重
}

export const TRACK_KPI_WEIGHTS: Record<string, TrackKPI> = {
  research: { quality: 0.4, speed: 0.1, cost: 0.2, innovation: 0.3 },
  architecture: { quality: 0.5, speed: 0.1, cost: 0.15, innovation: 0.25 },
  implementation: { quality: 0.45, speed: 0.25, cost: 0.2, innovation: 0.1 },
  review: { quality: 0.6, speed: 0.2, cost: 0.15, innovation: 0.05 }
};

/**
 * 计算 OKR 分数
 */
export function calculateOKRScore(
  track: string,
  actual: {
    quality: number;
    speed: number;      // inverse (lower is better)
    cost: number;       // inverse (lower is better)
    innovation: number;
  },
  targets: {
    quality: number;
    speed: number;
    cost: number;
    innovation: number;
  }
): number {
  const weights = TRACK_KPI_WEIGHTS[track] || { quality: 0.4, speed: 0.2, cost: 0.2, innovation: 0.2 };

  // 质量得分 (实际/目标，上限1.2)
  const qualityScore = Math.min(1.2, actual.quality / targets.quality);

  // 速度得分 (目标/实际，越快越好)
  const speedScore = targets.speed > 0 ? Math.min(1.2, targets.speed / actual.speed) : 1;

  // 成本得分 (目标/实际，越便宜越好)
  const costScore = targets.cost > 0 ? Math.min(1.2, targets.cost / actual.cost) : 1;

  // 创新得分
  const innovationScore = Math.min(1.2, actual.innovation / targets.innovation);

  // 加权平均
  return (
    qualityScore * weights.quality +
    speedScore * weights.speed +
    costScore * weights.cost +
    innovationScore * weights.innovation
  );
}

// ============================================================
// 赛季制
// ============================================================

export function getCurrentSeason(): string {
  const now = new Date();
  const year = now.getFullYear();
  const week = getWeekNumber(now);
  return `${year}-W${week.toString().padStart(2, '0')}`;
}

export function getWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

/**
 * 赛季结算
 * 避免剧烈波动，只更新变化超过阈值的
 */
export function settleSeason(
  season: string,
  currentRankings: Array<{ variant: string; mu: number; sigma: number }>,
  previousRankings: Array<{ variant: string; mu: number; sigma: number; routeWeight: number }>,
  volatilityThreshold: number = 0.2  // 20% 变化才更新权重
): Array<{ variant: string; newWeight: number; change: number }> {
  const updates: Array<{ variant: string; newWeight: number; change: number }> = [];

  for (const current of currentRankings) {
    const previous = previousRankings.find(p => p.variant === current.variant);
    const currentConservative = current.mu - 2 * current.sigma;

    if (!previous) {
      // 新选手，给中等权重
      updates.push({ variant: current.variant, newWeight: 0.5, change: 0.5 });
      continue;
    }

    const previousConservative = previous.mu - 2 * previous.sigma;
    const change = (currentConservative - previousConservative) / Math.max(previousConservative, 1);

    // 只有变化超过阈值才更新
    if (Math.abs(change) >= volatilityThreshold) {
      // 平滑更新
      const newWeight = previous.routeWeight * (1 + change * 0.5);  // 50% 响应
      const clampedWeight = Math.max(0.1, Math.min(1.0, newWeight));

      updates.push({
        variant: current.variant,
        newWeight: clampedWeight,
        change: clampedWeight - previous.routeWeight
      });
    } else {
      // 保持不变
      updates.push({
        variant: current.variant,
        newWeight: previous.routeWeight,
        change: 0
      });
    }
  }

  return updates;
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'cost': {
      const model = process.argv[3] || 'gemini-2.5-pro';
      const inputTokens = parseInt(process.argv[4] || '1000');
      const outputTokens = parseInt(process.argv[5] || '500');
      const cachedTokens = parseInt(process.argv[6] || '0');

      const cost = calculateCost(model, inputTokens, outputTokens, cachedTokens);

      console.log(`\n💰 成本计算 (${model}):\n`);
      console.log(`输入: ${inputTokens} tokens = $${cost.inputCost.toFixed(6)}`);
      if (cachedTokens > 0) {
        console.log(`缓存命中: ${cachedTokens} tokens, 节省 $${cost.cacheSavings.toFixed(6)}`);
      }
      console.log(`输出: ${outputTokens} tokens = $${cost.outputCost.toFixed(6)}`);
      console.log(`─────────────────────────────`);
      console.log(`总成本: $${cost.totalCost.toFixed(6)}`);
      break;
    }

    case 'gate': {
      const taskType = process.argv[3] || 'implementation:standard';
      const config = DEFAULT_GATE_CONFIGS[taskType];

      if (!config) {
        console.log(`❌ 未找到门禁配置: ${taskType}`);
        break;
      }

      // 模拟评分
      const scores = {
        correctness: 0.8,
        rigor: 0.7,
        completeness: 0.75,
        usefulness: 0.8,
        efficiency: 0.6,
        safety: 0.2
      };

      const result = checkQualityGate(scores, ['unit_test'], 1, config);

      console.log(`\n🚪 质量门禁检查 (${taskType}):\n`);
      console.log(`评分: correctness=${scores.correctness}, rigor=${scores.rigor}, completeness=${scores.completeness}`);
      console.log(`结果: ${result.passed ? '✅ 通过' : '❌ 未通过'}`);
      console.log(`动作: ${result.action}`);
      if (result.failedCriteria.length > 0) {
        console.log(`失败项: ${result.failedCriteria.join(', ')}`);
      }
      if (result.missingEvidence.length > 0) {
        console.log(`缺失证据: ${result.missingEvidence.join(', ')}`);
      }
      break;
    }

    case 'okr': {
      const track = process.argv[3] || 'implementation';
      const weights = TRACK_KPI_WEIGHTS[track];

      const actual = { quality: 0.82, speed: 1500, cost: 0.02, innovation: 0.6 };
      const targets = { quality: 0.8, speed: 2000, cost: 0.03, innovation: 0.5 };

      const score = calculateOKRScore(track, actual, targets);

      console.log(`\n🎯 OKR 评分 (${track}):\n`);
      console.log(`权重: quality=${weights.quality}, speed=${weights.speed}, cost=${weights.cost}, innovation=${weights.innovation}`);
      console.log(`实际: Q=${actual.quality}, 速度=${actual.speed}ms, 成本=$${actual.cost}, 创新=${actual.innovation}`);
      console.log(`目标: Q=${targets.quality}, 速度=${targets.speed}ms, 成本=$${targets.cost}, 创新=${targets.innovation}`);
      console.log(`─────────────────────────────`);
      console.log(`OKR 分数: ${(score * 100).toFixed(1)}%`);
      break;
    }

    case 'season': {
      const season = getCurrentSeason();
      console.log(`\n📅 当前赛季: ${season}\n`);
      break;
    }

    case 'pricing': {
      console.log('\n📋 模型价格表 (2026-02):\n');
      console.log('| 模型 | 输入 ($/1M) | 缓存输入 | 输出 ($/1M) |');
      console.log('|------|------------|---------|------------|');
      for (const [model, p] of Object.entries(MODEL_PRICING_2026_02)) {
        const cached = p.cachedInput || p.cacheHit || '-';
        console.log(`| ${model.padEnd(20)} | ${p.input.toString().padStart(5)} | ${cached.toString().padStart(5)} | ${p.output.toString().padStart(5)} |`);
      }
      break;
    }

    default:
      console.log(`
🚪 Quality Gate System - 质量门禁 + 分赛道OKR + 成本账本

用法:
  bun quality-gate.ts cost <model> <input_tokens> <output_tokens> [cached_tokens]
  bun quality-gate.ts gate <task_type>
  bun quality-gate.ts okr <track>
  bun quality-gate.ts season
  bun quality-gate.ts pricing

门禁类型:
  implementation:standard  - 代码实现标准
  implementation:critical  - 代码实现高风险
  architecture:standard    - 架构设计
  research:standard        - 研究分析
  prototype:fast           - 快速原型

赛道 OKR:
  research       - 质量40%, 速度10%, 成本20%, 创新30%
  architecture   - 质量50%, 速度10%, 成本15%, 创新25%
  implementation - 质量45%, 速度25%, 成本20%, 创新10%
  review         - 质量60%, 速度20%, 成本15%, 创新5%

原型期推荐顺序:
  1. 评测协议标准化 (rubric + pairwise + 证据要求)
  2. TrueSkill 上线 (按 agent_variant, task_type 更新 μ/σ)
  3. 评委治理 (交换顺序 + 多评委 + 评委可信度)
  4. XP/等级展示层 (决策靠 μ - kσ)
  5. 2-4周后上 bandit 路由
`);
  }
}

export default {
  // 成本计算
  calculateCost,
  MODEL_PRICING_2026_02,

  // 质量门禁
  checkQualityGate,
  DEFAULT_GATE_CONFIGS,

  // 分赛道 OKR
  calculateOKRScore,
  TRACK_KPI_WEIGHTS,

  // 赛季制
  getCurrentSeason,
  settleSeason
};
