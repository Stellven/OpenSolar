/**
 * Performance Rating System v1.0 - 绩效考核闭环
 *
 * 核心目标：可对比的评测协议 + 可更新的评分/排名模型 + 可控的激励与反作弊
 *
 * 三套计算模型组合：
 * A) TrueSkill - 联赛式排名（原型期噪声大，需要 σ 驱动探索/淘汰）
 * B) Rasch/IRT - 难度校正（有客观正确性的赛道）
 * C) Contextual Bandit - 路由最优化（质量-成本权衡）
 *
 * 数据面 MVP: Run → Review → Rating → Cost
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// Schema: 数据面 MVP
// ============================================================

// Run: 一次产出
db.run(`
  CREATE TABLE IF NOT EXISTS perf_runs (
    run_id TEXT PRIMARY KEY,

    -- 可复现性
    input_hash TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    persona_hash TEXT NOT NULL,

    -- 产出标识
    agent_variant TEXT NOT NULL,     -- 模型 × persona × 工具策略 × prompt版本
    task_type TEXT NOT NULL,

    -- 消耗
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    tool_calls TEXT,                 -- JSON array

    -- 产出
    artifact_hash TEXT,
    output_snapshot TEXT,            -- 截断的输出

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// Review: 一次评审
db.run(`
  CREATE TABLE IF NOT EXISTS perf_reviews (
    review_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,

    -- 评审者
    reviewer_id TEXT NOT NULL,       -- 可以是人或模型评委
    reviewer_type TEXT NOT NULL,     -- 'human' | 'model' | 'automated'

    -- 多维评分
    rubric_scores TEXT NOT NULL,     -- JSON: {correctness, rigor, completeness, usefulness, efficiency, safety}
    overall_score REAL,

    -- 对战结果
    opponent_run_id TEXT,            -- 对手 run_id (pairwise)
    pairwise_result TEXT,            -- 'win' | 'lose' | 'tie'

    -- 评论
    comments TEXT,

    -- 盲审标记
    is_blind BOOLEAN DEFAULT true,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// Rating: 长期绩效 (TrueSkill)
db.run(`
  CREATE TABLE IF NOT EXISTS perf_ratings (
    rating_id TEXT PRIMARY KEY,
    agent_variant TEXT NOT NULL,
    task_type TEXT NOT NULL,

    -- TrueSkill 参数
    mu REAL DEFAULT 25.0,            -- 能力均值
    sigma REAL DEFAULT 8.333,        -- 不确定性 (初始 25/3)

    -- 统计
    total_runs INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    total_losses INTEGER DEFAULT 0,
    total_ties INTEGER DEFAULT 0,

    -- 保守估计 (用于排名)
    conservative_rating REAL,        -- mu - k*sigma (k=2 时约95%置信)

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(agent_variant, task_type)
  )
`);

// ItemDifficulty: IRT 任务难度
db.run(`
  CREATE TABLE IF NOT EXISTS perf_item_difficulty (
    item_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,

    -- Rasch/IRT 参数
    difficulty REAL DEFAULT 0,       -- β (任务难度)
    discrimination REAL DEFAULT 1,   -- α (区分度)

    -- 统计
    total_attempts INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// Cost: 成本账本
db.run(`
  CREATE TABLE IF NOT EXISTS perf_costs (
    cost_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,

    -- 成本明细
    input_cost_usd REAL,
    output_cost_usd REAL,
    tool_cost_usd REAL,
    total_cost_usd REAL,

    -- 缓存
    cache_hit BOOLEAN,
    cache_storage_bytes INTEGER,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// AgentVariant: 模型 × persona × 工具策略 × prompt版本
db.run(`
  CREATE TABLE IF NOT EXISTS perf_agent_variants (
    variant_id TEXT PRIMARY KEY,

    -- 组成部分
    model_id TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    tool_strategy TEXT,              -- JSON: {tool_first, compression, ...}
    prompt_version TEXT,

    -- 元数据
    description TEXT,
    status TEXT DEFAULT 'active',    -- 'active' | 'deprecated' | 'testing'

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// ============================================================
// A) TrueSkill 实现
// ============================================================

const TRUE_SKILL_CONFIG = {
  mu: 25.0,              // 初始均值
  sigma: 8.333,          // 初始标准差 (mu/3)
  beta: 4.166,           // 技能波动 (sigma/2)
  tau: 0.0833,           // 动态因子 (sigma/100)
  draw_probability: 0.1, // 平局概率
  k: 2                   // 保守估计系数 (95%置信)
};

/**
 * TrueSkill 更新 (两方对战)
 */
export function updateTrueSkill(
  winner: { mu: number; sigma: number },
  loser: { mu: number; sigma: number },
  result: 'win' | 'lose' | 'tie' = 'win'
): { winnerNew: { mu: number; sigma: number }; loserNew: { mu: number; sigma: number } } {
  const { beta, tau, draw_probability } = TRUE_SKILL_CONFIG;

  // 简化版 TrueSkill 更新
  // 完整实现需要因子图，这里用近似

  const winnerMu = winner.mu;
  const winnerSigma = winner.sigma;
  const loserMu = loser.mu;
  const loserSigma = loser.sigma;

  // 计算预期胜率
  const c = Math.sqrt(
    2 * beta * beta +
    winnerSigma * winnerSigma +
    loserSigma * loserSigma
  );

  const expectedWin = 1 / (1 + Math.exp((loserMu - winnerMu) / c));

  // 根据结果调整
  let score: number;
  if (result === 'win') score = 1;
  else if (result === 'lose') score = 0;
  else score = 0.5;

  const delta = score - expectedWin;

  // 更新均值
  const winnerMuNew = winnerMu + delta * (winnerSigma * winnerSigma) / c;
  const loserMuNew = loserMu - delta * (loserSigma * loserSigma) / c;

  // 更新标准差 (减小不确定性)
  const winnerSigmaNew = Math.max(
    1.0,
    winnerSigma * Math.sqrt(1 - (winnerSigma * winnerSigma) / (c * c))
  ) + tau;
  const loserSigmaNew = Math.max(
    1.0,
    loserSigma * Math.sqrt(1 - (loserSigma * loserSigma) / (c * c))
  ) + tau;

  return {
    winnerNew: { mu: winnerMuNew, sigma: winnerSigmaNew },
    loserNew: { mu: loserMuNew, sigma: loserSigmaNew }
  };
}

/**
 * 计算保守估计排名 (μ - k·σ)
 */
export function conservativeRating(mu: number, sigma: number, k: number = 2): number {
  return mu - k * sigma;
}

/**
 * 检查是否达到晋升门槛
 * 条件: μ - 2σ > threshold (约95%置信)
 */
export function canPromote(
  mu: number,
  sigma: number,
  threshold: number,
  k: number = 2
): { canPromote: boolean; confidence: number } {
  const conservative = mu - k * sigma;
  const confidence = 1 - 0.5 * (1 + erf((mu - threshold) / (sigma * Math.sqrt(2))));

  return {
    canPromote: conservative > threshold,
    confidence
  };
}

// 误差函数近似
function erf(x: number): number {
  const a1 =  0.254829592;
  const a2 = -0.284496736;
  const a3 =  1.421413741;
  const a4 = -1.453152027;
  const a5 =  1.061405429;
  const p  =  0.3275911;

  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);

  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

  return sign * y;
}

// ============================================================
// B) Rasch/IRT 实现
// ============================================================

/**
 * Rasch 模型: P(correct) = sigmoid(θ_agent - β_item)
 */
export function raschProbability(agentAbility: number, itemDifficulty: number): number {
  return 1 / (1 + Math.exp(-(agentAbility - itemDifficulty)));
}

/**
 * 更新 Rasch 参数 (简化版 EM)
 */
export function updateRasch(
  agentAbility: number,
  itemDifficulty: number,
  correct: boolean,
  learningRate: number = 0.1
): { newAbility: number; newDifficulty: number } {
  const predicted = raschProbability(agentAbility, itemDifficulty);
  const actual = correct ? 1 : 0;
  const error = actual - predicted;

  // 梯度下降
  const newAbility = agentAbility + learningRate * error;
  const newDifficulty = itemDifficulty - learningRate * error;

  return { newAbility, newDifficulty };
}

/**
 * 校正后的能力估计 (考虑任务难度)
 */
export function calibratedAbility(
  rawScore: number,
  avgItemDifficulty: number,
  totalItems: number
): number {
  // θ = logit(rawScore) + avgDifficulty
  const clampedScore = Math.max(0.01, Math.min(0.99, rawScore));
  const logit = Math.log(clampedScore / (1 - clampedScore));
  return logit + avgItemDifficulty;
}

// ============================================================
// C) Contextual Bandit 实现
// ============================================================

export interface BanditContext {
  taskType: string;
  complexity: number;      // 0-1
  budgetRemaining: number; // dollars
  timeBudget: number;      // seconds
  riskTolerance: number;   // 0-1
}

export interface BanditArm {
  variantId: string;
  mu: number;              // 预期质量
  sigma: number;           // 不确定性
  cost: number;            // 平均成本
  latency: number;         // 平均延迟
  trials: number;          // 尝试次数
}

/**
 * 计算奖励函数
 * R = Q - λ·Cost - μ·Latency - ν·RiskPenalty
 */
export function calculateReward(
  quality: number,
  cost: number,
  latency: number,
  riskPenalty: number,
  lambda: number = 1.0,    // 成本权重
  mu: number = 0.001,      // 延迟权重 ($/ms)
  nu: number = 0.5         // 风险权重
): number {
  return quality - lambda * cost - mu * latency - nu * riskPenalty;
}

/**
 * Thompson Sampling 选择臂
 */
export function thompsonSelectArm(
  arms: BanditArm[],
  context: BanditContext
): BanditArm {
  let bestArm = arms[0];
  let bestSample = -Infinity;

  for (const arm of arms) {
    // 从正态分布采样
    const sample = gaussianRandom(arm.mu, arm.sigma);

    // 成本惩罚
    const costPenalty = arm.cost / context.budgetRemaining;
    const adjustedSample = sample - costPenalty;

    if (adjustedSample > bestSample) {
      bestSample = adjustedSample;
      bestArm = arm;
    }
  }

  return bestArm;
}

/**
 * UCB (Upper Confidence Bound) 选择臂
 */
export function ucbSelectArm(
  arms: BanditArm[],
  totalTrials: number,
  c: number = 2.0
): BanditArm {
  let bestArm = arms[0];
  let bestScore = -Infinity;

  for (const arm of arms) {
    if (arm.trials === 0) return arm; // 未探索的优先

    const exploitation = arm.mu;
    const exploration = c * Math.sqrt(Math.log(totalTrials) / arm.trials);
    const score = exploitation + exploration;

    if (score > bestScore) {
      bestScore = score;
      bestArm = arm;
    }
  }

  return bestArm;
}

// 高斯随机数生成 (Box-Muller)
function gaussianRandom(mean: number, std: number): number {
  const u1 = Math.random();
  const u2 = Math.random();
  const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  return z0 * std + mean;
}

// ============================================================
// 反作弊机制
// ============================================================

/**
 * 检测异常模式
 */
export function detectAnomalies(
  reviews: Array<{ reviewerId: string; runId: string; score: number; timestamp: Date }>
): { anomalyType: string; evidence: string }[] {
  const anomalies: { anomalyType: string; evidence: string }[] = [];

  // 1. 检测评审者偏差 (总是给高分/低分)
  const reviewerScores: Record<string, number[]> = {};
  for (const r of reviews) {
    if (!reviewerScores[r.reviewerId]) reviewerScores[r.reviewerId] = [];
    reviewerScores[r.reviewerId].push(r.score);
  }

  for (const [reviewerId, scores] of Object.entries(reviewerScores)) {
    if (scores.length >= 10) {
      const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
      const variance = scores.reduce((a, b) => a + (b - avg) ** 2, 0) / scores.length;

      // 极端一致性 (可能刷分)
      if (variance < 0.1) {
        anomalies.push({
          anomalyType: 'reviewer_bias_low_variance',
          evidence: `Reviewer ${reviewerId} has suspiciously consistent scores (variance: ${variance.toFixed(3)})`
        });
      }

      // 极端偏好
      if (avg > 4.5 || avg < 1.5) {
        anomalies.push({
          anomalyType: 'reviewer_bias_extreme',
          evidence: `Reviewer ${reviewerId} has extreme average score (${avg.toFixed(2)})`
        });
      }
    }
  }

  // 2. 检测时间聚集 (短时间内大量评审)
  // 3. 检测自评 (评审者和被评者关联)
  // ... 可扩展

  return anomalies;
}

/**
 * 评委可信度更新
 */
export function updateReviewerCredibility(
  currentCredibility: number,
  agreedWithConsensus: boolean,
  decayFactor: number = 0.95
): number {
  // 衰减旧信誉
  const decayed = currentCredibility * decayFactor;

  // 根据与共识一致性更新
  const update = agreedWithConsensus ? 0.1 : -0.2;

  return Math.max(0.1, Math.min(1.0, decayed + update));
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'trueskill': {
      const mu1 = parseFloat(process.argv[3] || '25');
      const sigma1 = parseFloat(process.argv[4] || '8.333');
      const mu2 = parseFloat(process.argv[5] || '25');
      const sigma2 = parseFloat(process.argv[6] || '8.333');
      const result = (process.argv[7] || 'win') as 'win' | 'lose' | 'tie';

      const updated = updateTrueSkill(
        { mu: mu1, sigma: sigma1 },
        { mu: mu2, sigma: sigma2 },
        result
      );

      console.log('\n📊 TrueSkill 更新结果:\n');
      console.log(`胜者: μ=${updated.winnerNew.mu.toFixed(2)}, σ=${updated.winnerNew.sigma.toFixed(2)}, 保守=${conservativeRating(updated.winnerNew.mu, updated.winnerNew.sigma).toFixed(2)}`);
      console.log(`败者: μ=${updated.loserNew.mu.toFixed(2)}, σ=${updated.loserNew.sigma.toFixed(2)}, 保守=${conservativeRating(updated.loserNew.mu, updated.loserNew.sigma).toFixed(2)}`);
      break;
    }

    case 'rasch': {
      const ability = parseFloat(process.argv[3] || '0');
      const difficulty = parseFloat(process.argv[4] || '0');

      const prob = raschProbability(ability, difficulty);
      console.log(`\n📈 Rasch 模型:\n`);
      console.log(`P(correct) = ${prob.toFixed(3)} (能力=${ability}, 难度=${difficulty})`);
      break;
    }

    case 'bandit': {
      const arms: BanditArm[] = [
        { variantId: 'glm-5_builder', mu: 0.7, sigma: 0.1, cost: 0.001, latency: 1000, trials: 100 },
        { variantId: 'gemini-pro_judge', mu: 0.8, sigma: 0.15, cost: 0.005, latency: 2000, trials: 50 },
        { variantId: 'deepseek-r1_advisor', mu: 0.85, sigma: 0.2, cost: 0.01, latency: 3000, trials: 20 },
      ];

      const context: BanditContext = {
        taskType: 'coding',
        complexity: 0.6,
        budgetRemaining: 1.0,
        timeBudget: 60,
        riskTolerance: 0.3
      };

      const tsArm = thompsonSelectArm(arms, context);
      const ucbArm = ucbSelectArm(arms, 170);

      console.log('\n🎲 Bandit 选择:\n');
      console.log(`Thompson Sampling: ${tsArm.variantId}`);
      console.log(`UCB: ${ucbArm.variantId}`);
      break;
    }

    case 'reward': {
      const quality = parseFloat(process.argv[3] || '0.8');
      const cost = parseFloat(process.argv[4] || '0.01');
      const latency = parseFloat(process.argv[5] || '2000');

      const reward = calculateReward(quality, cost, latency, 0);
      console.log(`\n💰 奖励函数:\n`);
      console.log(`R = ${reward.toFixed(4)} (Q=${quality}, Cost=$${cost}, Latency=${latency}ms)`);
      break;
    }

    default:
      console.log(`
📊 Performance Rating System - 绩效考核闭环

用法:
  bun performance-rating.ts trueskill <mu1> <sigma1> <mu2> <sigma2> [win|lose|tie]
  bun performance-rating.ts rasch <ability> <difficulty>
  bun performance-rating.ts bandit
  bun performance-rating.ts reward <quality> <cost> <latency>

模型:
  A) TrueSkill - 联赛式排名 (μ, σ, 保守估计)
  B) Rasch/IRT - 难度校正 (θ_agent, β_item)
  C) Bandit - 路由最优化 (R = Q - λ·Cost - μ·Latency)

数据表:
  perf_runs        - 一次产出 (input_hash, tokens, latency)
  perf_reviews     - 一次评审 (rubric_scores, pairwise)
  perf_ratings     - 长期绩效 (TrueSkill μ/σ)
  perf_costs       - 成本账本
  perf_agent_variants - 模型×人格组合
`);
  }
}

export default {
  // TrueSkill
  updateTrueSkill,
  conservativeRating,
  canPromote,

  // Rasch/IRT
  raschProbability,
  updateRasch,
  calibratedAbility,

  // Bandit
  calculateReward,
  thompsonSelectArm,
  ucbSelectArm,

  // 反作弊
  detectAnomalies,
  updateReviewerCredibility,

  // 配置
  TRUE_SKILL_CONFIG
};
