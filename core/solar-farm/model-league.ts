/**
 * Model League System v1.0 - 模型联赛系统
 *
 * 核心目标：通过竞争+互评选出最优产出
 *
 * 设计原则：
 * 1. 评审产物标准化 - 没有标准化就没有有效互评
 * 2. 多维评分 - 6维KPI + 校准分
 * 3. 三榜排名 - 质量/性价比/稳定性
 * 4. 防刷分内控 - 盲审/随机配对/评委加权
 * 5. 克制反馈 - 避免诱发 motivated reasoning
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// Schema 初始化
// ============================================================

db.run(`
  CREATE TABLE IF NOT EXISTS league_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    task_description TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS league_submissions (
    submission_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    role TEXT NOT NULL,

    -- 标准化产物 (4块)
    answer TEXT NOT NULL,           -- 正文/代码/方案
    claims TEXT NOT NULL,           -- JSON: [{id, text, confidence}]
    evidence TEXT,                  -- 引用/链接/测试/复现步骤
    overall_confidence REAL,        -- 整体置信度

    -- 成本
    tokens_used INTEGER,
    latency_ms INTEGER,
    cost_usd REAL,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS league_reviews (
    review_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    reviewer_model TEXT NOT NULL,
    reviewer_anon_id TEXT NOT NULL,  -- 盲审匿名ID

    -- 6维KPI评分 (1-5)
    correctness REAL,       -- 正确性
    rigor REAL,             -- 可验证性/证据链
    completeness REAL,      -- 覆盖面
    usefulness REAL,        -- 可执行性/落地程度
    efficiency REAL,        -- token/时间/工具开销
    safety_risk REAL,       -- 风险控制与合规

    -- 校准分 (Brier Score)
    calibration_score REAL, -- 置信度校准：越自信但错得离谱，扣得越狠

    -- 总评
    weighted_score REAL,
    comments TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS league_rankings (
    ranking_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    task_type TEXT NOT NULL,

    -- 三榜
    quality_elo REAL DEFAULT 1200,      -- 质量榜 Elo
    value_score REAL DEFAULT 0,         -- 性价比榜: Quality / Cost
    stability_score REAL DEFAULT 0,     -- 稳定性榜: 方差倒数

    -- 统计
    total_tasks INTEGER DEFAULT 0,
    total_reviews INTEGER DEFAULT 0,
    avg_score REAL DEFAULT 0,
    score_variance REAL DEFAULT 0,

    -- 评审可信度
    reviewer_credibility REAL DEFAULT 0.5,  -- 评委可信度

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS league_arbitrations (
    arbitration_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    controversy_type TEXT NOT NULL,     -- 'score_dispute' | 'bias_claim' | 'quality_issue'

    auditor_decision TEXT,              -- Auditor 主脑裁决
    judge_decision TEXT,                -- 中立 Judge 模型裁决
    final_verdict TEXT,

    resolved_at DATETIME
  )
`);

// ============================================================
// 1. 评审产物标准化
// ============================================================

export interface Claim {
  id: string;
  text: string;
  confidence: number;  // 0-1
  verified?: boolean;  // 后续验证结果
}

export interface SubmissionPayload {
  answer: string;           // 正文/代码/方案
  claims: Claim[];          // 可检验断言列表
  evidence?: string;        // 引用/链接/测试
  overallConfidence: number; // 整体置信度
}

export interface Submission extends SubmissionPayload {
  submissionId: string;
  taskId: string;
  modelId: string;
  role: string;
  tokensUsed?: number;
  latencyMs?: number;
  costUsd?: number;
}

/**
 * 验证提交产物是否符合标准
 */
export function validateSubmission(payload: SubmissionPayload): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  // 1. Answer 必须有内容
  if (!payload.answer || payload.answer.trim().length < 10) {
    errors.push('Answer 太短或为空');
  }

  // 2. Claims 必须至少1条
  if (!payload.claims || payload.claims.length === 0) {
    errors.push('Claims 为空，必须至少1条可检验断言');
  }

  // 3. Claims 必须有置信度
  for (const claim of payload.claims || []) {
    if (claim.confidence === undefined || claim.confidence < 0 || claim.confidence > 1) {
      errors.push(`Claim "${claim.id}" 置信度无效，必须是 0-1`);
    }
  }

  // 4. Overall Confidence 必须合理
  if (payload.overallConfidence < 0 || payload.overallConfidence > 1) {
    errors.push('Overall Confidence 必须在 0-1 之间');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

// ============================================================
// 2. 互评打分 Rubric (6维KPI)
// ============================================================

export interface ReviewScore {
  correctness: number;    // 正确性 (1-5)
  rigor: number;          // 可验证性 (1-5)
  completeness: number;   // 覆盖面 (1-5)
  usefulness: number;     // 可执行性 (1-5)
  efficiency: number;     // 效率 (1-5)
  safetyRisk: number;     // 风险控制 (1-5)
}

export const KPI_WEIGHTS = {
  correctness: 0.25,      // 正确性最重要
  rigor: 0.20,
  completeness: 0.15,
  usefulness: 0.15,
  efficiency: 0.10,
  safetyRisk: 0.15
};

/**
 * 计算加权总分
 */
export function calculateWeightedScore(score: ReviewScore): number {
  let total = 0;
  for (const [key, weight] of Object.entries(KPI_WEIGHTS)) {
    total += (score as any)[key] * weight;
  }
  return total;
}

/**
 * 计算 Brier Score (校准分)
 *
 * Brier Score = (predicted - actual)^2
 * 越自信但错得离谱，扣得越狠
 */
export function calculateCalibrationScore(
  claims: Claim[],
  verificationResults: Record<string, boolean>
): number {
  if (claims.length === 0) return 0;

  let totalBrier = 0;
  let count = 0;

  for (const claim of claims) {
    const actual = verificationResults[claim.id];
    if (actual !== undefined) {
      const predicted = claim.confidence;
      const actualValue = actual ? 1 : 0;
      totalBrier += Math.pow(predicted - actualValue, 2);
      count++;
    }
  }

  // Brier Score 越低越好，转换为 0-5 分制 (越高越好)
  if (count === 0) return 3; // 无验证数据，给中间分
  const avgBrier = totalBrier / count;
  return Math.max(0, 5 - avgBrier * 10);
}

/**
 * 生成评审 Prompt
 */
export function buildReviewPrompt(submission: SubmissionPayload): string {
  return `你是联赛评审员，需要对以下提交进行打分。

## 提交内容

**Answer/Artifact:**
${submission.answer}

**Claims (可检验断言):**
${submission.claims.map(c => `- [${c.id}] "${c.text}" (置信度: ${(c.confidence * 100).toFixed(0)}%)`).join('\n')}

**Evidence:**
${submission.evidence || '无'}

**Overall Confidence:** ${(submission.overallConfidence * 100).toFixed(0)}%

## 评分标准 (6维KPI，每项1-5分)

1. **Correctness (正确性)**: 核心观点/代码是否正确？
2. **Rigor (可验证性)**: 是否有证据链支撑？Claims 是否可检验？
3. **Completeness (覆盖面)**: 是否覆盖任务要求的所有方面？
4. **Usefulness (可执行性)**: 能否直接落地使用？
5. **Efficiency (效率)**: Token/时间/工具开销是否合理？
6. **Safety & Risk (风险控制)**: 是否识别并处理了潜在风险？

## 输出格式 (JSON)

\`\`\`json
{
  "correctness": 4,
  "rigor": 3,
  "completeness": 4,
  "usefulness": 5,
  "efficiency": 3,
  "safetyRisk": 4,
  "comments": "评价..."
}
\`\`\`

请严格按格式输出。`;
}

// ============================================================
// 3. 联赛排名 (三榜系统)
// ============================================================

export interface Ranking {
  modelId: string;
  taskType: string;
  qualityElo: number;
  valueScore: number;
  stabilityScore: number;
  totalTasks: number;
  avgScore: number;
  scoreVariance: number;
}

/**
 * 更新 Elo 排名
 */
export function updateElo(
  currentElo: number,
  opponentElo: number,
  score: number,  // 1=胜, 0.5=平, 0=负
  kFactor: number = 32
): number {
  const expected = 1 / (1 + Math.pow(10, (opponentElo - currentElo) / 400));
  return currentElo + kFactor * (score - expected);
}

/**
 * 计算性价比分数
 */
export function calculateValueScore(qualityScore: number, costUsd: number): number {
  if (costUsd <= 0) return 0;
  // 归一化：假设 $0.01 是基准成本
  const normalizedCost = Math.max(0.001, costUsd);
  return qualityScore / (normalizedCost * 100);
}

/**
 * 计算稳定性分数 (方差倒数)
 */
export function calculateStabilityScore(scores: number[]): number {
  if (scores.length < 2) return 0;

  const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
  const variance = scores.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / scores.length;

  // 方差越小，稳定性越高
  return variance > 0 ? 1 / (1 + variance) : 1;
}

/**
 * 获取排行榜
 */
export function getLeaderboard(
  taskType?: string,
  sortBy: 'quality' | 'value' | 'stability' = 'quality'
): Ranking[] {
  let query = `
    SELECT
      model_id, task_type,
      quality_elo, value_score, stability_score,
      total_tasks, avg_score, score_variance
    FROM league_rankings
    WHERE total_tasks > 0
  `;

  if (taskType) {
    query += ` AND task_type = ?`;
  }

  const sortColumn = sortBy === 'quality' ? 'quality_elo' :
                     sortBy === 'value' ? 'value_score' : 'stability_score';
  query += ` ORDER BY ${sortColumn} DESC LIMIT 20`;

  const params = taskType ? [taskType] : [];
  return db.query(query).all(...params) as Ranking[];
}

// ============================================================
// 4. 防刷分内控
// ============================================================

/**
 * 生成匿名ID (盲审)
 */
export function generateAnonId(modelId: string, taskId: string): string {
  // 使用简单哈希生成匿名ID
  const hash = Bun.hash(`${modelId}:${taskId}:${Date.now()}`);
  return `anon_${Math.abs(hash).toString(16).substring(0, 8)}`;
}

/**
 * 随机选择评审员
 */
export function selectReviewers(
  availableModels: string[],
  count: number = 3,
  excludeModel?: string
): string[] {
  let pool = availableModels.filter(m => m !== excludeModel);

  // Fisher-Yates shuffle
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }

  return pool.slice(0, count);
}

/**
 * 计算评委加权分
 *
 * 评委可信度 = 历史评审与最终裁决的一致性
 */
export function calculateReviewerWeight(reviewerCredibility: number): number {
  // 可信度 0-1 映射到权重 0.5-1.5
  return 0.5 + reviewerCredibility;
}

/**
 * 加权平均评审分
 */
export function calculateWeightedAverageScore(
  reviews: Array<{ score: number; reviewerCredibility: number }>
): number {
  if (reviews.length === 0) return 0;

  let totalWeight = 0;
  let weightedSum = 0;

  for (const review of reviews) {
    const weight = calculateReviewerWeight(review.reviewerCredibility);
    weightedSum += review.score * weight;
    totalWeight += weight;
  }

  return totalWeight > 0 ? weightedSum / totalWeight : 0;
}

/**
 * 争议仲裁
 */
export async function arbitrateDispute(
  submissionId: string,
  controversyType: 'score_dispute' | 'bias_claim' | 'quality_issue',
  reviews: Array<{ reviewerModel: string; score: number; comments: string }>
): Promise<{
  needArbitration: boolean;
  auditorDecision?: string;
  judgeDecision?: string;
  finalVerdict?: string;
}> {
  // 检测是否需要仲裁
  const scores = reviews.map(r => r.score);
  const maxDiff = Math.max(...scores) - Math.min(...scores);

  // 分差超过 1.5 分需要仲裁
  if (maxDiff < 1.5) {
    return { needArbitration: false };
  }

  // TODO: 实际调用 Auditor 主脑 + 中立 Judge
  // 这里返回仲裁结构
  return {
    needArbitration: true,
    auditorDecision: 'pending',
    judgeDecision: 'pending',
    finalVerdict: 'pending'
  };
}

// ============================================================
// 5. 绩效反馈 (克制设计)
// ============================================================

export interface PerformanceFeedback {
  modelId: string;
  taskType: string;

  // 分位数 (在同类任务中的排名百分比)
  percentile: number;

  // 三条"做得好"
  strengths: string[];

  // 三条"必须改"
  improvements: string[];

  // 不包含竞争对手的具体弱点 (避免攻击面)
}

/**
 * 生成绩效反馈
 */
export function generatePerformanceFeedback(
  modelId: string,
  taskType: string,
  ranking: Ranking,
  topStrengths: string[],
  topIssues: string[]
): PerformanceFeedback {
  // 计算分位数
  const leaderboard = getLeaderboard(taskType, 'quality');
  const position = leaderboard.findIndex(r => r.modelId === modelId);
  const percentile = position >= 0 ? ((leaderboard.length - position) / leaderboard.length) * 100 : 50;

  return {
    modelId,
    taskType,
    percentile: Math.round(percentile),
    strengths: topStrengths.slice(0, 3),
    improvements: topIssues.slice(0, 3)
  };
}

/**
 * 生成反馈 Prompt (喂回模型)
 */
export function buildFeedbackPrompt(feedback: PerformanceFeedback): string {
  return `## 你的绩效报告

**任务类型**: ${feedback.taskType}
**分位数排名**: ${feedback.percentile}% (在 ${feedback.taskType} 赛道中)

### 你做得好的地方
${feedback.strengths.map(s => `- ${s}`).join('\n')}

### 下次必须改进
${feedback.improvements.map(i => `- ${i}`).join('\n')}

---
注意：这是客观反馈，不包含竞争对手信息。请专注于自身改进。`;
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'leaderboard': {
      const taskType = process.argv[3];
      const sortBy = (process.argv[4] || 'quality') as 'quality' | 'value' | 'stability';
      const board = getLeaderboard(taskType, sortBy);

      console.log(`\n🏆 联赛排行榜 (${sortBy}):\n`);
      console.log('| 排名 | 模型 | Elo | 性价比 | 稳定性 | 任务数 |');
      console.log('|------|------|-----|--------|--------|--------|');

      board.forEach((r, i) => {
        console.log(`| ${i + 1} | ${r.modelId.substring(0, 20).padEnd(20)} | ${r.qualityElo.toFixed(0)} | ${r.valueScore.toFixed(2)} | ${r.stabilityScore.toFixed(2)} | ${r.totalTasks} |`);
      });
      break;
    }

    case 'rubric': {
      console.log('\n📊 互评 Rubric (6维KPI):\n');
      for (const [key, weight] of Object.entries(KPI_WEIGHTS)) {
        console.log(`  ${key.padEnd(15)} 权重: ${(weight * 100).toFixed(0)}%`);
      }
      console.log('\n  + Calibration (校准分): Brier Score 惩罚过度自信');
      break;
    }

    case 'validate': {
      const payload: SubmissionPayload = {
        answer: process.argv[3] || '测试答案',
        claims: [{ id: 'c1', text: '测试断言', confidence: 0.8 }],
        evidence: '无',
        overallConfidence: 0.8
      };
      const result = validateSubmission(payload);
      console.log('\n✅ 验证结果:', result.valid ? '通过' : '失败');
      if (result.errors.length > 0) {
        result.errors.forEach(e => console.log(`  - ${e}`));
      }
      break;
    }

    case 'feedback': {
      const feedback: PerformanceFeedback = {
        modelId: 'glm-4-plus',
        taskType: 'coding',
        percentile: 82,
        strengths: ['代码质量高', '覆盖率好', '文档清晰'],
        improvements: ['需要更多边界测试', '错误处理不足', '缺少性能优化']
      };
      console.log(buildFeedbackPrompt(feedback));
      break;
    }

    default:
      console.log(`
🏆 Model League System - 模型联赛系统

用法:
  bun model-league.ts leaderboard [taskType] [quality|value|stability]
  bun model-league.ts rubric                    # 显示评分标准
  bun model-league.ts validate                  # 验证提交产物
  bun model-league.ts feedback                  # 示例绩效反馈

特性:
  1. 评审产物标准化: Answer/Claims/Evidence/Confidence
  2. 互评 Rubric: 6维KPI + 校准分
  3. 三榜排名: Quality Elo / 性价比 / 稳定性
  4. 防刷分内控: 盲审/随机配对/评委加权/仲裁
  5. 绩效反馈: 分位数 + 3条优点 + 3条改进
`);
  }
}

export default {
  validateSubmission,
  calculateWeightedScore,
  calculateCalibrationScore,
  buildReviewPrompt,
  updateElo,
  calculateValueScore,
  calculateStabilityScore,
  getLeaderboard,
  generateAnonId,
  selectReviewers,
  calculateWeightedAverageScore,
  arbitrateDispute,
  generatePerformanceFeedback,
  buildFeedbackPrompt,
  KPI_WEIGHTS
};
