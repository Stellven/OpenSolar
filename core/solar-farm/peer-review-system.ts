/**
 * Peer Review System v1.0 - 互评系统 + 内控机制
 *
 * 核心问题：LLM 评委有系统性偏差，必须治理
 *
 * 内控机制:
 * 1. 盲审 - 隐藏作者/模型/人格
 * 2. 交换顺序 - 抵消 position bias
 * 3. 多评委 + 少数否决 - 高风险结论
 * 4. 评委可信度 - 与最终裁决一致性
 *
 * 双层指标:
 * - 竞技能力 (Skill Rating): TrueSkill μ/σ
 * - 绩效积分 (XP): OKR/季度绩效
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// Schema: 评审系统
// ============================================================

// 评审会话 (一次完整的互评)
db.run(`
  CREATE TABLE IF NOT EXISTS review_sessions (
    session_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,

    -- 被评对象 (盲审)
    submission_a_id TEXT NOT NULL,    -- 匿名ID
    submission_b_id TEXT NOT NULL,    -- 匿名ID
    real_a_variant TEXT,              -- 解盲后填入
    real_b_variant TEXT,              -- 解盲后填入

    -- 顺序随机化
    original_order TEXT NOT NULL,     -- 'a_b' | 'b_a' (随机)
    swapped_count INTEGER DEFAULT 0,  -- 交换次数

    -- 状态
    status TEXT DEFAULT 'pending',    -- 'pending' | 'reviewing' | 'resolved'
    resolved_at DATETIME,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// 评委评分 (盲审)
db.run(`
  CREATE TABLE IF NOT EXISTS review_scores (
    score_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,

    -- 评委 (也盲审)
    reviewer_anon_id TEXT NOT NULL,   -- 评委匿名ID
    reviewer_real_variant TEXT,       -- 解盲后填入

    -- 多维评分
    scores_a TEXT NOT NULL,           -- JSON: {correctness, rigor, ...}
    scores_b TEXT NOT NULL,           -- JSON: {correctness, rigor, ...}

    -- 偏好
    preferred TEXT,                   -- 'a' | 'b' | 'tie'
    confidence REAL,                  -- 0-1

    -- 校准
    self_calibration REAL,            -- 评委自信度

    -- 计算出的奖励
    xp_awarded REAL DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// 评委可信度
db.run(`
  CREATE TABLE IF NOT EXISTS reviewer_credibility (
    credibility_id TEXT PRIMARY KEY,
    reviewer_variant TEXT NOT NULL,
    task_type TEXT NOT NULL,

    -- 可信度指标
    credibility_score REAL DEFAULT 0.5,   -- 0-1
    total_reviews INTEGER DEFAULT 0,
    agreed_with_consensus INTEGER DEFAULT 0,
    disagreed_with_consensus INTEGER DEFAULT 0,

    -- 偏差检测
    position_bias_score REAL DEFAULT 0,   -- 位置偏差 (正=偏好第一)
    verbosity_bias_score REAL DEFAULT 0,  -- 啰嗦偏差
    self_enhancement_bias REAL DEFAULT 0, -- 自增强偏差

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(reviewer_variant, task_type)
  )
`);

// 双层指标: 竞技能力 + 绩效积分
db.run(`
  CREATE TABLE IF NOT EXISTS agent_dual_metrics (
    metric_id TEXT PRIMARY KEY,
    agent_variant TEXT NOT NULL,
    task_type TEXT NOT NULL,

    -- A层: 竞技能力 (TrueSkill)
    skill_mu REAL DEFAULT 25.0,
    skill_sigma REAL DEFAULT 8.333,
    conservative_skill REAL,         -- μ - kσ (路由用)

    -- B层: 绩效积分 (XP)
    total_xp REAL DEFAULT 0,
    current_level INTEGER DEFAULT 1,
    xp_to_next_level REAL,

    -- 统计
    total_tasks INTEGER DEFAULT 0,
    avg_quality REAL DEFAULT 0,
    avg_efficiency REAL DEFAULT 0,   -- Q/Cost
    avg_calibration REAL DEFAULT 0,

    -- 晋升状态
    promotion_status TEXT DEFAULT 'normal', -- 'candidate' | 'promoted' | 'demoted' | 'probation'

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(agent_variant, task_type)
  )
`);

// XP 历史 (便于审计)
db.run(`
  CREATE TABLE IF NOT EXISTS xp_history (
    history_id TEXT PRIMARY KEY,
    agent_variant TEXT NOT NULL,
    task_type TEXT NOT NULL,

    -- XP 计算明细
    quality_component REAL,          -- A·Q
    efficiency_component REAL,       -- B·log(1 + Eff/E0)
    calibration_component REAL,      -- C·Cal
    violation_penalty REAL,          -- -D·PolicyViolations
    total_xp_gain REAL,

    task_id TEXT,
    session_id TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// ============================================================
// XP 计算公式
// ============================================================

export interface XPConfig {
  A: number;      // 质量权重
  B: number;      // 效率权重
  C: number;      // 校准权重
  D: number;      // 违规惩罚
  E0: number;     // 效率基准
  g: number;      // 等级增长因子
  XP0: number;    // 初始 XP 阈值
}

export const DEFAULT_XP_CONFIG: XPConfig = {
  A: 100,         // 质量权重
  B: 50,          // 效率权重
  C: 30,          // 校准权重
  D: 200,         // 违规惩罚
  E0: 10,         // 效率基准 (Q=0.8, Cost=$0.08 → Eff=10)
  g: 1.3,         // 等级增长因子
  XP0: 100        // 初始 XP 阈值
};

/**
 * 计算 XP 增益
 * XP_gain = A·Q + B·log(1 + Eff/E0) + C·Cal − D·PolicyViolations
 */
export function calculateXPGain(
  quality: number,           // Q: 0-1
  cost: number,              // Cost: dollars
  calibration: number,       // Cal: -1 to 1 (Brier score transformed)
  policyViolations: number,  // 违规次数
  config: XPConfig = DEFAULT_XP_CONFIG
): {
  totalXPGain: number;
  components: {
    quality: number;
    efficiency: number;
    calibration: number;
    penalty: number;
  };
  efficiency: number;
} {
  // 效率 = Q / Cost (性价比)
  const efficiency = cost > 0 ? quality / cost : 0;

  const qualityComponent = config.A * quality;
  const efficiencyComponent = config.B * Math.log(1 + efficiency / config.E0);
  const calibrationComponent = config.C * calibration;
  const penalty = config.D * policyViolations;

  const totalXPGain = qualityComponent + efficiencyComponent + calibrationComponent - penalty;

  return {
    totalXPGain,
    components: {
      quality: qualityComponent,
      efficiency: efficiencyComponent,
      calibration: calibrationComponent,
      penalty
    },
    efficiency
  };
}

/**
 * 计算升级所需 XP
 * XP_needed(L) = XP0 · g^L
 */
export function xpNeededForLevel(level: number, config: XPConfig = DEFAULT_XP_CONFIG): number {
  return config.XP0 * Math.pow(config.g, level);
}

/**
 * 检查是否升级
 */
export function checkLevelUp(
  currentLevel: number,
  totalXP: number,
  config: XPConfig = DEFAULT_XP_CONFIG
): { leveledUp: boolean; newLevel: number; xpToNext: number } {
  const threshold = xpNeededForLevel(currentLevel, config);

  if (totalXP >= threshold && currentLevel < 20) {
    return {
      leveledUp: true,
      newLevel: currentLevel + 1,
      xpToNext: xpNeededForLevel(currentLevel + 1, config) - totalXP
    };
  }

  return {
    leveledUp: false,
    newLevel: currentLevel,
    xpToNext: threshold - totalXP
  };
}

// ============================================================
// 晋升/降级逻辑
// ============================================================

export interface PromotionThresholds {
  T_high: number;      // 晋升门槛 (保守估计)
  T_low: number;       // 降级门槛
  k: number;           // 保守系数 (默认2)
  N_stable: number;    // 稳定性检查窗口
  variance_threshold: number;  // 方差阈值
}

export const DEFAULT_PROMOTION_THRESHOLDS: PromotionThresholds = {
  T_high: 30,          // μ - 2σ > 30 → 晋升候选
  T_low: 15,           // μ + 2σ < 15 → 降级
  k: 2,
  N_stable: 10,
  variance_threshold: 5
};

/**
 * 检查晋升条件
 * 条件: μ - kσ > T_high 且最近 N 次任务稳定
 */
export function checkPromotion(
  mu: number,
  sigma: number,
  recentScores: number[],
  thresholds: PromotionThresholds = DEFAULT_PROMOTION_THRESHOLDS
): { canPromote: boolean; reason: string; confidence: number } {
  const conservative = mu - thresholds.k * sigma;

  // 条件1: 保守估计超过门槛
  if (conservative <= thresholds.T_high) {
    return {
      canPromote: false,
      reason: `Conservative rating (${conservative.toFixed(1)}) below threshold (${thresholds.T_high})`,
      confidence: 0
    };
  }

  // 条件2: 最近 N 次任务稳定
  if (recentScores.length >= thresholds.N_stable) {
    const recentN = recentScores.slice(-thresholds.N_stable);
    const variance = calculateVariance(recentN);

    if (variance > thresholds.variance_threshold) {
      return {
        canPromote: false,
        reason: `Recent performance unstable (variance: ${variance.toFixed(2)})`,
        confidence: conservative / thresholds.T_high
      };
    }
  }

  return {
    canPromote: true,
    reason: 'Meets promotion criteria',
    confidence: conservative / thresholds.T_high
  };
}

/**
 * 检查降级条件
 * 条件: μ + kσ < T_low 或违规/高风险错误超阈值
 */
export function checkDemotion(
  mu: number,
  sigma: number,
  policyViolations: number,
  highRiskErrors: number,
  thresholds: PromotionThresholds = DEFAULT_PROMOTION_THRESHOLDS
): { shouldDemote: boolean; reason: string } {
  const upperBound = mu + thresholds.k * sigma;

  if (upperBound < thresholds.T_low) {
    return {
      shouldDemote: true,
      reason: `Upper bound (${upperBound.toFixed(1)}) below threshold (${thresholds.T_low})`
    };
  }

  if (policyViolations > 3 || highRiskErrors > 2) {
    return {
      shouldDemote: true,
      reason: `Too many violations (${policyViolations}) or high-risk errors (${highRiskErrors})`
    };
  }

  return { shouldDemote: false, reason: '' };
}

function calculateVariance(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length;
}

// ============================================================
// 内控: 盲审 + 交换顺序 + 少数否决
// ============================================================

export interface ReviewSubmission {
  sessionId: string;
  submissionA: string;
  submissionB: string;
  variantA: string;
  variantB: string;
}

/**
 * 创建盲审会话
 */
export function createBlindReviewSession(
  submissionA: string,
  submissionB: string,
  variantA: string,
  variantB: string
): ReviewSubmission {
  const sessionId = generateId();

  // 随机交换顺序 (抵消 position bias)
  const shouldSwap = Math.random() > 0.5;

  return {
    sessionId,
    submissionA: shouldSwap ? submissionB : submissionA,
    submissionB: shouldSwap ? submissionA : submissionB,
    variantA: shouldSwap ? variantB : variantA,
    variantB: shouldSwap ? variantA : variantB
  };
}

/**
 * 生成匿名ID
 */
export function generateAnonId(): string {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < 8; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return `anon_${result}`;
}

/**
 * 少数否决决策
 * 对于高风险结论，即使多数同意，少数反对也能触发仲裁
 */
export function minorityVetoDecision(
  votes: Array<{ reviewer: string; preference: 'a' | 'b' | 'tie'; confidence: number }>,
  highRisk: boolean = false,
  vetoThreshold: number = 0.3  // 少数比例超过此值触发仲裁
): {
  decision: 'a' | 'b' | 'tie' | 'arbitrate';
  confidence: number;
  minorityRatio: number;
} {
  const counts = { a: 0, b: 0, tie: 0 };
  let totalConfidence = 0;

  for (const vote of votes) {
    counts[vote.preference]++;
    totalConfidence += vote.confidence;
  }

  const total = votes.length;
  const maxCount = Math.max(counts.a, counts.b, counts.tie);
  const minorityRatio = 1 - maxCount / total;

  // 高风险任务 + 少数比例高 → 触发仲裁
  if (highRisk && minorityRatio >= vetoThreshold) {
    return {
      decision: 'arbitrate',
      confidence: totalConfidence / total,
      minorityRatio
    };
  }

  // 正常决策
  const decision = counts.a >= counts.b && counts.a >= counts.tie ? 'a' :
                   counts.b >= counts.tie ? 'b' : 'tie';

  return {
    decision,
    confidence: totalConfidence / total,
    minorityRatio
  };
}

/**
 * 更新评委可信度
 * 可信度 = 与最终裁决/客观指标的一致性
 */
export function updateReviewerCredibilityScore(
  currentCredibility: number,
  reviewerVote: 'a' | 'b' | 'tie',
  finalDecision: 'a' | 'b' | 'tie',
  objectiveResult: 'a' | 'b' | 'tie' | null,
  decayFactor: number = 0.95
): number {
  // 衰减旧信誉
  const decayed = currentCredibility * decayFactor;

  // 检查与最终决策是否一致
  const agreedWithDecision = reviewerVote === finalDecision;

  // 如果有客观结果，额外检查
  const agreedWithObjective = objectiveResult === null || reviewerVote === objectiveResult;

  // 更新
  const update = (agreedWithDecision ? 0.05 : -0.1) +
                 (objectiveResult ? (agreedWithObjective ? 0.05 : -0.15) : 0);

  return Math.max(0.1, Math.min(1.0, decayed + update));
}

/**
 * 检测位置偏差
 */
export function detectPositionBias(
  reviews: Array<{ preferredFirst: boolean; swapped: boolean }>
): number {
  // 正值 = 偏好第一个位置
  // 负值 = 偏好第二个位置
  if (reviews.length < 10) return 0;

  let firstPreferenceCount = 0;
  let totalCount = 0;

  for (const r of reviews) {
    // 只统计有明确偏好的
    firstPreferenceCount += r.preferredFirst ? 1 : 0;
    totalCount++;
  }

  return totalCount > 0 ? (firstPreferenceCount / totalCount - 0.5) * 2 : 0;
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'xp': {
      const quality = parseFloat(process.argv[3] || '0.8');
      const cost = parseFloat(process.argv[4] || '0.01');
      const calibration = parseFloat(process.argv[5] || '0.5');
      const violations = parseInt(process.argv[6] || '0');

      const result = calculateXPGain(quality, cost, calibration, violations);

      console.log('\n📈 XP 计算:\n');
      console.log(`质量 (A·Q):        +${result.components.quality.toFixed(1)}`);
      console.log(`效率 (B·log):      +${result.components.efficiency.toFixed(1)}`);
      console.log(`校准 (C·Cal):      +${result.components.calibration.toFixed(1)}`);
      console.log(`违规惩罚:          -${result.components.penalty.toFixed(1)}`);
      console.log(`─────────────────────────────`);
      console.log(`总 XP 增益:        +${result.totalXPGain.toFixed(1)}`);
      console.log(`效率值 (Eff):      ${result.efficiency.toFixed(2)}`);
      break;
    }

    case 'level': {
      const level = parseInt(process.argv[3] || '1');
      const totalXP = parseFloat(process.argv[4] || '0');

      const threshold = xpNeededForLevel(level);
      const result = checkLevelUp(level, totalXP);

      console.log('\n🎯 等级检查:\n');
      console.log(`当前等级: ${level}`);
      console.log(`升级所需: ${threshold.toFixed(0)} XP`);
      console.log(`当前 XP: ${totalXP.toFixed(0)}`);
      console.log(`结果: ${result.leveledUp ? '✅ 升级到 ' + result.newLevel : '❌ 未达标'}`);
      if (!result.leveledUp) {
        console.log(`还需: ${result.xpToNext.toFixed(0)} XP`);
      }
      break;
    }

    case 'promote': {
      const mu = parseFloat(process.argv[3] || '35');
      const sigma = parseFloat(process.argv[4] || '3');

      const result = checkPromotion(mu, sigma, [0.8, 0.85, 0.82, 0.88, 0.84, 0.86, 0.83, 0.87, 0.85, 0.84]);

      console.log('\n⬆️ 晋升检查:\n');
      console.log(`μ = ${mu}, σ = ${sigma}`);
      console.log(`保守估计: ${(mu - 2 * sigma).toFixed(1)} (μ - 2σ)`);
      console.log(`结果: ${result.canPromote ? '✅ 可晋升' : '❌ 不可晋升'}`);
      console.log(`原因: ${result.reason}`);
      break;
    }

    case 'veto': {
      // 模拟投票
      const votes = [
        { reviewer: 'r1', preference: 'a' as const, confidence: 0.9 },
        { reviewer: 'r2', preference: 'a' as const, confidence: 0.8 },
        { reviewer: 'r3', preference: 'b' as const, confidence: 0.7 },
        { reviewer: 'r4', preference: 'a' as const, confidence: 0.6 },
        { reviewer: 'r5', preference: 'b' as const, confidence: 0.85 },
      ];

      const normalResult = minorityVetoDecision(votes, false);
      const highRiskResult = minorityVetoDecision(votes, true);

      console.log('\n⚖️ 少数否决决策:\n');
      console.log(`投票: A=3, B=2, 少数比例=${(normalResult.minorityRatio * 100).toFixed(0)}%`);
      console.log(`普通任务: ${normalResult.decision}`);
      console.log(`高风险任务: ${highRiskResult.decision}`);
      break;
    }

    default:
      console.log(`
⚖️ Peer Review System - 互评系统 + 内控机制

用法:
  bun peer-review-system.ts xp <quality> <cost> <calibration> <violations>
  bun peer-review-system.ts level <level> <totalXP>
  bun peer-review-system.ts promote <mu> <sigma>
  bun peer-review-system.ts veto

XP 公式:
  XP_gain = A·Q + B·log(1 + Eff/E0) + C·Cal − D·Violations

内控机制:
  1. 盲审 - 隐藏作者/模型/人格
  2. 交换顺序 - 抵消 position bias
  3. 多评委 + 少数否决 - 高风险结论
  4. 评委可信度 - 与最终裁决一致性

晋升/降级:
  晋升: μ - 2σ > T_high 且最近 N 次稳定
  降级: μ + 2σ < T_low 或违规过多
`);
  }
}

function generateId(): string {
  return `id_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

export default {
  // XP 计算
  calculateXPGain,
  xpNeededForLevel,
  checkLevelUp,
  DEFAULT_XP_CONFIG,

  // 晋升/降级
  checkPromotion,
  checkDemotion,
  DEFAULT_PROMOTION_THRESHOLDS,

  // 内控
  createBlindReviewSession,
  generateAnonId,
  minorityVetoDecision,
  updateReviewerCredibilityScore,
  detectPositionBias
};
