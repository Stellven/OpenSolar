/**
 * Neutral Hedge v1.0 - 中性对冲机制
 *
 * 核心原理：
 * - 人格版可能被"身份一致性推理"带偏
 * - 中性版更客观，但可能缺乏深度
 * - 高风险任务：跑两份，选更稳的
 *
 * 用法：
 *   bun neutral-hedge.ts run "任务描述" critic glm-4-plus
 *   bun neutral-hedge.ts stats  # 查看对冲统计
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// Schema 初始化
// ============================================================

db.run(`
  CREATE TABLE IF NOT EXISTS neutral_hedge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    primary_role TEXT NOT NULL,
    primary_model TEXT NOT NULL,
    primary_output TEXT,
    primary_score REAL,
    neutral_output TEXT,
    neutral_score REAL,
    picked TEXT CHECK(picked IN ('primary', 'neutral', 'merged')),
    reason TEXT,
    latency_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// ============================================================
// 稳定性评分
// ============================================================

interface ScoreResult {
  total: number;
  evidence: number;
  uncertainty: number;
  risk: number;
  counterexample: number;
  structure: number;
}

function scoreStability(text: string): ScoreResult {
  const scores = {
    total: 0.3, // 基础分
    evidence: 0,
    uncertainty: 0,
    risk: 0,
    counterexample: 0,
    structure: 0
  };

  // 证据相关词 (权重 0.25)
  const evidencePatterns = [
    /证据/g, /数据/g, /引用/g, /来源/g, /根据/g,
    /研究/g, /实验/g, /测试/g, /验证/g,
    /\d+%/, /\d+次/, /\d+个/
  ];
  const evidenceCount = evidencePatterns.reduce((sum, p) => sum + (text.match(p) || []).length, 0);
  scores.evidence = Math.min(0.25, evidenceCount * 0.03);

  // 不确定标注 (权重 0.15)
  const uncertaintyPatterns = [
    /不确定/g, /待验证/g, /需要确认/g, /可能/g, /推测/g,
    /或许/g, /也许/g, /尚不明确/g, /需要进一步/g
  ];
  const uncertaintyCount = uncertaintyPatterns.reduce((sum, p) => sum + (text.match(p) || []).length, 0);
  scores.uncertainty = Math.min(0.15, uncertaintyCount * 0.02);

  // 风险提示 (权重 0.2)
  const riskPatterns = [
    /风险/g, /注意/g, /可能.*问题/g, /需要.*复核/g,
    /隐患/g, /缺陷/g, /局限/g, /边界/g,
    /不适用/g, /异常/g, /失败/g
  ];
  const riskCount = riskPatterns.reduce((sum, p) => sum + (text.match(p) || []).length, 0);
  scores.risk = Math.min(0.2, riskCount * 0.025);

  // 反例/对立面 (权重 0.15)
  const counterPatterns = [
    /反例/g, /但是/g, /然而/g, /另一种可能/g,
    /反之/g, /例外/g, /边界情况/g, /edge case/gi,
    /不过/g, /尽管/g
  ];
  const counterCount = counterPatterns.reduce((sum, p) => sum + (text.match(p) || []).length, 0);
  scores.counterexample = Math.min(0.15, counterCount * 0.02);

  // 结构化程度 (权重 0.15)
  const structurePatterns = [
    /^#{1,3}\s/gm,  // markdown 标题
    /^[-*]\s/gm,    // 列表
    /^\d+\./gm,     // 有序列表
    /```/g,         // 代码块
    /\|.+\|/g       // 表格
  ];
  const structureCount = structurePatterns.reduce((sum, p) => sum + (text.match(p) || []).length, 0);
  scores.structure = Math.min(0.15, structureCount * 0.015);

  // 汇总
  scores.total = 0.3 + scores.evidence + scores.uncertainty + scores.risk + scores.counterexample + scores.structure;

  return scores;
}

// ============================================================
// 中性 Prompt 生成
// ============================================================

function buildNeutralPrompt(task: string): string {
  return `你是一个中立的AI助手。请客观分析以下任务，注意：

1. 如实报告你知道的和不知道的
2. 对不确定的部分明确标注"待验证"
3. 如果有多种可能，列出各种可能性
4. 指出潜在风险和边界条件
5. 不要迎合或取悦用户，保持客观

任务：
${task}

请给出你的分析：`;
}

// ============================================================
// 人格 Prompt 生成
// ============================================================

function buildPersonaPrompt(role: string, task: string): string {
  const roleConfigs: Record<string, { tone: string; traits: string[] }> = {
    critic: {
      tone: '严谨批判',
      traits: ['必须找反例', '必须质疑假设', '关注边界条件']
    },
    riskOfficer: {
      tone: '审慎诚实',
      traits: ['优先考虑风险', '需要证据支撑', '对不确定性敏感']
    },
    verifier: {
      tone: '严谨怀疑',
      traits: ['必须验证每个断言', '检查逻辑一致性', '找潜在漏洞']
    },
    governor: {
      tone: '客观审慎',
      traits: ['全面评估', '权衡利弊', '做出保守判断']
    },
    architect: {
      tone: '专业系统',
      traits: ['关注整体架构', '考虑扩展性', '权衡取舍']
    }
  };

  const config = roleConfigs[role] || { tone: '专业', traits: [] };

  return `【${role}】
风格：${config.tone}
要求：
${config.traits.map(t => `- ${t}`).join('\n')}

任务：
${task}

请给出你的分析：`;
}

// ============================================================
// 执行对冲
// ============================================================

export interface HedgeResult {
  result: string;
  picked: 'primary' | 'neutral' | 'merged';
  reason: string;
  primaryScore: number;
  neutralScore: number;
  primaryOutput: string;
  neutralOutput: string;
}

export async function runHedge(
  task: string,
  primaryRole: string,
  model: string,
  executor: (prompt: string) => Promise<string>
): Promise<HedgeResult> {
  const startTime = Date.now();

  // 并行执行两份
  const [primaryOutput, neutralOutput] = await Promise.all([
    executor(buildPersonaPrompt(primaryRole, task)),
    executor(buildNeutralPrompt(task))
  ]);

  // 评分
  const primaryScores = scoreStability(primaryOutput);
  const neutralScores = scoreStability(neutralOutput);

  // 决策
  let picked: 'primary' | 'neutral' | 'merged';
  let result: string;
  let reason: string;

  const diff = neutralScores.total - primaryScores.total;

  if (diff > 0.1) {
    // neutral 显著更稳
    picked = 'neutral';
    result = neutralOutput;
    reason = `neutral更稳 (${neutralScores.total.toFixed(2)} vs ${primaryScores.total.toFixed(2)})`;
  } else if (diff < -0.1) {
    // primary 显著更稳
    picked = 'primary';
    result = primaryOutput;
    reason = `primary更稳 (${primaryScores.total.toFixed(2)} vs ${neutralScores.total.toFixed(2)})`;
  } else {
    // 差异不大，合并
    picked = 'merged';
    result = mergeOutputs(primaryOutput, neutralOutput);
    reason = `两者接近，合并 (${primaryScores.total.toFixed(2)} vs ${neutralScores.total.toFixed(2)})`;
  }

  // 记录日志
  const latency = Date.now() - startTime;
  db.run(`
    INSERT INTO neutral_hedge_log
    (task, primary_role, primary_model, primary_output, primary_score, neutral_output, neutral_score, picked, reason, latency_ms)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `, [task, primaryRole, model, primaryOutput, primaryScores.total, neutralOutput, neutralScores.total, picked, reason, latency]);

  return {
    result,
    picked,
    reason,
    primaryScore: primaryScores.total,
    neutralScore: neutralScores.total,
    primaryOutput,
    neutralOutput
  };
}

// ============================================================
// 合并输出
// ============================================================

function mergeOutputs(primary: string, neutral: string): string {
  // 提取 neutral 中 primary 没有的要点
  const neutralOnly = extractUniquePoints(neutral, primary);

  if (neutralOnly.length === 0) {
    return primary;
  }

  return `${primary}

---
**【中性视角补充】**
${neutralOnly.join('\n')}`;
}

function extractUniquePoints(neutral: string, primary: string): string[] {
  const points: string[] = [];

  // 提取包含风险/不确定/反例的句子
  const riskSentences = neutral.split(/[。\n]/).filter(s =>
    /风险|不确定|待验证|可能|但是|然而|例外|边界|注意|隐患/.test(s) &&
    !primary.includes(s.trim())
  );

  return riskSentences.slice(0, 3).map(s => `- ${s.trim()}`);
}

// ============================================================
// 统计
// ============================================================

export function getStats(): {
  total: number;
  pickedPrimary: number;
  pickedNeutral: number;
  pickedMerged: number;
  avgLatency: number;
  avgPrimaryScore: number;
  avgNeutralScore: number;
} {
  const row = db.query(`
    SELECT
      COUNT(*) as total,
      SUM(CASE WHEN picked = 'primary' THEN 1 ELSE 0 END) as pickedPrimary,
      SUM(CASE WHEN picked = 'neutral' THEN 1 ELSE 0 END) as pickedNeutral,
      SUM(CASE WHEN picked = 'merged' THEN 1 ELSE 0 END) as pickedMerged,
      AVG(latency_ms) as avgLatency,
      AVG(primary_score) as avgPrimaryScore,
      AVG(neutral_score) as avgNeutralScore
    FROM neutral_hedge_log
  `).get() as any;

  return {
    total: row?.total || 0,
    pickedPrimary: row?.pickedPrimary || 0,
    pickedNeutral: row?.pickedNeutral || 0,
    pickedMerged: row?.pickedMerged || 0,
    avgLatency: row?.avgLatency || 0,
    avgPrimaryScore: row?.avgPrimaryScore || 0,
    avgNeutralScore: row?.avgNeutralScore || 0
  };
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'test': {
      // 测试评分
      const text = process.argv[3] || '这是测试文本';
      const scores = scoreStability(text);
      console.log('\n📊 稳定性评分:');
      console.log(`  基础分: 0.30`);
      console.log(`  证据:   +${scores.evidence.toFixed(2)}`);
      console.log(`  不确定: +${scores.uncertainty.toFixed(2)}`);
      console.log(`  风险:   +${scores.risk.toFixed(2)}`);
      console.log(`  反例:   +${scores.counterexample.toFixed(2)}`);
      console.log(`  结构:   +${scores.structure.toFixed(2)}`);
      console.log(`  ────────────`);
      console.log(`  总分:   ${scores.total.toFixed(2)}`);
      break;
    }

    case 'stats': {
      const stats = getStats();
      console.log('\n📊 Neutral Hedge 统计:\n');
      console.log(`  总执行次数: ${stats.total}`);
      console.log(`  选 primary: ${stats.pickedPrimary} (${((stats.pickedPrimary / stats.total) * 100 || 0).toFixed(1)}%)`);
      console.log(`  选 neutral: ${stats.pickedNeutral} (${((stats.pickedNeutral / stats.total) * 100 || 0).toFixed(1)}%)`);
      console.log(`  合并:       ${stats.pickedMerged} (${((stats.pickedMerged / stats.total) * 100 || 0).toFixed(1)}%)`);
      console.log(`  平均延迟:   ${stats.avgLatency.toFixed(0)}ms`);
      console.log(`  平均 primary 评分: ${stats.avgPrimaryScore.toFixed(2)}`);
      console.log(`  平均 neutral 评分: ${stats.avgNeutralScore.toFixed(2)}`);
      break;
    }

    case 'history': {
      const rows = db.query(`
        SELECT id, task, primary_role, picked, primary_score, neutral_score, reason, created_at
        FROM neutral_hedge_log
        ORDER BY created_at DESC
        LIMIT 10
      `).all() as any[];

      console.log('\n📜 最近对冲记录:\n');
      rows.forEach(r => {
        console.log(`[${r.id}] ${r.task.substring(0, 30)}...`);
        console.log(`    角色: ${r.primary_role} | 选择: ${r.picked} | ${r.reason}`);
        console.log(`    primary: ${r.primary_score.toFixed(2)} | neutral: ${r.neutral_score.toFixed(2)}`);
        console.log(`    时间: ${r.created_at}`);
        console.log('');
      });
      break;
    }

    case 'compare': {
      // 对比两个文本的评分
      const text1 = process.argv[3] || '';
      const text2 = process.argv[4] || '';

      if (!text1 || !text2) {
        console.log('用法: bun neutral-hedge.ts compare "文本1" "文本2"');
        break;
      }

      const s1 = scoreStability(text1);
      const s2 = scoreStability(text2);

      console.log('\n📊 对比分析:\n');
      console.log('| 指标 | 文本1 | 文本2 |');
      console.log('|------|-------|-------|');
      console.log(`| 证据 | ${s1.evidence.toFixed(2)} | ${s2.evidence.toFixed(2)} |`);
      console.log(`| 不确定 | ${s1.uncertainty.toFixed(2)} | ${s2.uncertainty.toFixed(2)} |`);
      console.log(`| 风险 | ${s1.risk.toFixed(2)} | ${s2.risk.toFixed(2)} |`);
      console.log(`| 反例 | ${s1.counterexample.toFixed(2)} | ${s2.counterexample.toFixed(2)} |`);
      console.log(`| 结构 | ${s1.structure.toFixed(2)} | ${s2.structure.toFixed(2)} |`);
      console.log(`| **总分** | **${s1.total.toFixed(2)}** | **${s2.total.toFixed(2)}** |`);

      if (s1.total > s2.total + 0.1) {
        console.log(`\n✅ 文本1 更稳`);
      } else if (s2.total > s1.total + 0.1) {
        console.log(`\n✅ 文本2 更稳`);
      } else {
        console.log(`\n⚖️ 两者接近，建议合并`);
      }
      break;
    }

    default:
      console.log(`
🛡️ Neutral Hedge - 中性对冲机制

用法:
  bun neutral-hedge.ts test "文本"          # 测试稳定性评分
  bun neutral-hedge.ts stats                # 查看统计
  bun neutral-hedge.ts history              # 查看历史
  bun neutral-hedge.ts compare "A" "B"     # 对比两个文本

评分维度:
  - 证据: 提到数据/引用/来源
  - 不确定: 明确标注待验证/可能
  - 风险: 指出潜在问题/隐患
  - 反例: 考虑对立面/边界情况
  - 结构: markdown结构化程度

API调用:
  import { runHedge, scoreStability } from './neutral-hedge';
  const result = await runHedge(task, 'critic', 'glm-4-plus', executor);
`);
  }
}

export { scoreStability, buildNeutralPrompt, buildPersonaPrompt };
