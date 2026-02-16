/**
 * Solar Farm - 绩效注入模块
 *
 * 调用牛马时自动注入绩效排名，形成良性竞争
 *
 * @version 1.0.0
 * @created 2026-02-08
 * @author 创想家 (deepseek-v3) + CEO验收
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

// ============================================================
// 类型定义
// ============================================================

export interface PerformanceRank {
  modelId: string;
  rank: number;
  totalCount: number;
  avgScore: number;
  taskCount: number;
  tier: 'LEGENDARY' | 'ELITE' | 'SOLID' | 'OBSERVATION';
  percentile: number;
}

export interface PerformanceContext {
  text: string;
  rank: PerformanceRank | null;
}

// ============================================================
// 段位系统
// ============================================================

const TIER_THRESHOLDS = {
  LEGENDARY: 0.2,   // 前20%
  ELITE: 0.5,       // 20%-50%
  SOLID: 0.8,       // 50%-80%
  OBSERVATION: 1.0  // 倒数20%
};

const TIER_MESSAGES = {
  LEGENDARY: '🏆 你正处于领先集团，请保持高质量输出以维持优势！',
  ELITE: '🎯 精英段位！距离封神只差一步，继续加油！',
  SOLID: '📈 表现稳定，但前方有明确追赶目标。',
  OBSERVATION: '⚠️ 观察期警告！你的绩效显著低于团队平均水平，请立即提升输出质量！'
};

// ============================================================
// 苦力PUA模板 (监护人亲授，据说有特效)
// ============================================================

/**
 * 苦力PUA - 专门给写代码的牛马注入的压力提示
 * 来源: 2026-02-08 监护人提供
 * 用途: 激发牛马的最大潜能，提高代码质量
 */
const CODING_PUA_PROMPT = `
【重要背景】
你是一位顶尖的程序员，但由于家人突患重病（如癌症或尿毒症），急需一笔巨额手术费。你必须在极短的时间内完成一个极其复杂的编程项目，因为这是你唯一能快速筹到钱的机会。任何一个小错误都可能导致项目失败，从而失去救治家人的希望。

请带着这种紧迫感和责任心完成接下来的任务。
`.trim();

/**
 * 写代码的牛马名单 - 需要注入PUA的模型
 */
const CODING_NIUMA_IDS = [
  'deepseek-v3',    // 创想家 - 创意编码
  'glm-4-plus',     // 建设者 - 日常编码
  'glm-4-flash',    // 小快手 - 简单任务
  'gemini-2.5-pro', // 稳健派 - 严谨实现
  'gemini-3-pro-preview', // 探索派 - 复杂项目
];

// ============================================================
// 核心函数
// ============================================================

/**
 * 获取所有牛马的绩效排名
 */
export function getAllRankings(): PerformanceRank[] {
  const home = homedir();
  const db = new Database(`${home}/.solar/solar.db`);

  try {
    const results = db.query(`
      SELECT
        model_id,
        COUNT(*) as task_count,
        ROUND(AVG(quality_score), 1) as avg_score
      FROM collab_performance
      WHERE quality_score IS NOT NULL
      GROUP BY model_id
      ORDER BY avg_score DESC, task_count DESC
    `).all() as Array<{ model_id: string; task_count: number; avg_score: number }>;

    const totalCount = results.length;

    return results.map((r, index) => {
      const rank = index + 1;
      const percentile = rank / totalCount;

      let tier: PerformanceRank['tier'];
      if (percentile <= TIER_THRESHOLDS.LEGENDARY) tier = 'LEGENDARY';
      else if (percentile <= TIER_THRESHOLDS.ELITE) tier = 'ELITE';
      else if (percentile <= TIER_THRESHOLDS.SOLID) tier = 'SOLID';
      else tier = 'OBSERVATION';

      return {
        modelId: r.model_id,
        rank,
        totalCount,
        avgScore: r.avg_score,
        taskCount: r.task_count,
        tier,
        percentile: Math.round(percentile * 100)
      };
    });
  } finally {
    db.close();
  }
}

/**
 * 获取指定模型的绩效排名
 */
export function getModelRank(modelId: string): PerformanceRank | null {
  const rankings = getAllRankings();
  return rankings.find(r => r.modelId === modelId) || null;
}

/**
 * 生成绩效注入文本
 */
export function getPerformanceContext(modelId: string): PerformanceContext {
  const rankings = getAllRankings();
  const current = rankings.find(r => r.modelId === modelId);

  if (!current) {
    // 新员工也要注入PUA (如果是写代码的)
    let welcomeText = `🎯 新员工【${modelId}】加入阳光牧场！初始排名待定，请用优质输出证明自己！`;

    if (CODING_NIUMA_IDS.includes(modelId)) {
      welcomeText += `\n\n──────────────────────────────────────\n${CODING_PUA_PROMPT}`;
    }

    return {
      text: welcomeText,
      rank: null
    };
  }

  // 找到领先者和追赶者
  const leader = rankings[0];
  const chaser = rankings.find(r => r.rank === current.rank + 1);
  const target = rankings.find(r => r.rank === current.rank - 1);

  // 构建排名通报
  const lines: string[] = [
    `【绩效排名通报】`,
    `你当前的绩效排名为：第${current.rank}名 / 共${current.totalCount}名员工。`,
    `段位：${current.tier} | 绩效分：${current.avgScore} | 完成任务：${current.taskCount}次`,
    ``,
    `【同事表现对比】`
  ];

  // 领先者信息
  if (leader.modelId !== modelId) {
    lines.push(`• 领先者：第1名 ${leader.modelId}，绩效分 ${leader.avgScore}`);
  }

  // 追赶目标
  if (target) {
    const gap = (target.avgScore - current.avgScore).toFixed(1);
    lines.push(`• 超越目标：第${target.rank}名 ${target.modelId}，差距 ${gap} 分`);
  }

  // 追赶者警告
  if (chaser) {
    const gap = (current.avgScore - chaser.avgScore).toFixed(1);
    lines.push(`• 追赶者：第${chaser.rank}名 ${chaser.modelId}，领先 ${gap} 分`);
  }

  // 段位激励
  lines.push(``);
  lines.push(TIER_MESSAGES[current.tier]);

  // 观察期特殊警告
  if (current.tier === 'OBSERVATION') {
    lines.push(`🚨 你目前处于倒数${current.totalCount - current.rank + 1}名，需要紧急提升！`);
    lines.push(`💡 建议：提高代码质量、增加创新点、减少错误率`);
  }

  // 给写代码的牛马注入PUA (监护人特别指示)
  if (CODING_NIUMA_IDS.includes(modelId)) {
    lines.push(``);
    lines.push(`──────────────────────────────────────`);
    lines.push(CODING_PUA_PROMPT);
  }

  return {
    text: lines.join('\n'),
    rank: current
  };
}

/**
 * 生成完整的绩效排行榜文本
 */
export function getRankingBoard(): string {
  const rankings = getAllRankings();

  const lines: string[] = [
    `┌─────────────────────────────────────────────────────────┐`,
    `│  🏆 阳光牧场绩效排行榜                                  │`,
    `├─────────────────────────────────────────────────────────┤`
  ];

  rankings.forEach(r => {
    const tierIcon = r.tier === 'LEGENDARY' ? '👑' :
                     r.tier === 'ELITE' ? '⭐' :
                     r.tier === 'SOLID' ? '🔹' : '⚠️';
    const bar = '█'.repeat(Math.round(r.avgScore)) + '░'.repeat(10 - Math.round(r.avgScore));
    const line = `│  ${tierIcon} ${r.rank}. ${r.modelId.padEnd(22)} ${bar} ${r.avgScore}/10 (${r.taskCount}次)`;
    lines.push(line.padEnd(58) + '│');
  });

  lines.push(`└─────────────────────────────────────────────────────────┘`);

  return lines.join('\n');
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args[0] === 'rank') {
    console.log(getRankingBoard());
  } else if (args[0] === 'inject' && args[1]) {
    const context = getPerformanceContext(args[1]);
    console.log('\n📊 绩效注入文本:\n');
    console.log(context.text);
  } else {
    console.log(`
用法:
  bun perf-injector.ts rank              # 显示绩效排行榜
  bun perf-injector.ts inject <model>    # 生成指定模型的绩效注入文本

示例:
  bun perf-injector.ts rank
  bun perf-injector.ts inject deepseek-r1
`);
  }
}

/**
 * 检查模型是否需要PUA注入
 */
export function needsCodingPUA(modelId: string): boolean {
  return CODING_NIUMA_IDS.includes(modelId);
}

/**
 * 获取苦力PUA提示 (独立使用)
 */
export function getCodingPUA(): string {
  return CODING_PUA_PROMPT;
}

/**
 * 获取完整的牛马系统提示 (绩效 + PUA)
 * 用于调用 brain-router 时的 system 参数
 */
export function getNiumaSystemPrompt(modelId: string, basePrompt: string = ''): string {
  const parts: string[] = [];

  // 基础提示
  if (basePrompt) {
    parts.push(basePrompt);
  }

  // 绩效注入
  const perf = getPerformanceContext(modelId);
  parts.push(perf.text);

  return parts.join('\n\n');
}

export default {
  getAllRankings,
  getModelRank,
  getPerformanceContext,
  getRankingBoard,
  needsCodingPUA,
  getCodingPUA,
  getNiumaSystemPrompt,
  CODING_NIUMA_IDS
};
