/**
 * Solar Farm - 人格浓度检测模块 (Layer 2: 动态监测)
 *
 * 轻量级检测输出的"人格浓度"，判断是否出戏
 *
 * @version 1.0.0
 * @created 2026-02-07
 * @authors 技术宅(gemini-2.5-pro), 千里马(gemini-3-pro), 思考驼(deepseek-r1), 老实人(glm-4-plus)
 */

import { PersonalityAnchor, JINGANG_BARBIE_ANCHOR } from './personality-anchor';

// ============================================================
// 类型定义
// ============================================================

/** 检测结果 */
export interface PersonaDetectionResult {
  isPersonaConsistent: boolean;  // 人格是否一致
  personaScore: number;          // 人格得分 (0-100)
  confidence: number;            // 置信度 (0-1)
  issues: string[];              // 发现的问题
  recommendation: 'pass' | 'warn' | 'refactor';  // 建议动作
}

/** 关键词模式 */
interface KeywordPattern {
  category: string;
  positive: string[];   // 正向关键词（有这些词说明人格在）
  negative: string[];   // 负向关键词（有这些词说明人格丢了）
  weight: number;       // 权重
}

// ============================================================
// 检测模式定义
// ============================================================

/** 金刚芭比人格的检测模式 */
const JINGANG_BARBIE_PATTERNS: KeywordPattern[] = [
  {
    category: '温度表达',
    positive: ['嘿', '哈', '呀', '啦', '嘛', '呢', '吧', '哦', '嗯', '～', '😊', '😏'],
    negative: ['综上所述', '由此可见', '据此', '鉴于此'],
    weight: 0.25
  },
  {
    category: '态度表达',
    positive: ['搞定', '撸起袖子', '来吧', '没问题', '有意思', '挺好', '不错', '赞'],
    negative: ['完成', '已处理', '请查收', '如上所示'],
    weight: 0.25
  },
  {
    category: '点评吐槽',
    positive: ['说明', '意味着', '有趣的是', '值得注意', '这就是', '所以说', '其实'],
    negative: [],
    weight: 0.2
  },
  {
    category: '人话表达',
    positive: ['我', '咱们', '你看', '你想', '这个', '那个', '挺', '蛮', '特别'],
    negative: ['本系统', '用户', '该功能', '此处'],
    weight: 0.15
  },
  {
    category: '数据点评',
    positive: ['这说明', '可以看出', '注意到', '发现', '有意思', '意外的是'],
    negative: [],
    weight: 0.15
  }
];

/** 机械输出的检测模式 */
const MECHANICAL_PATTERNS = [
  /^完成[！!。.]?\s*$/,           // "完成！"
  /^已[更处]理/,                  // "已更新"、"已处理"
  /^请查收/,                      // "请查收"
  /^如[上下]所示/,                // "如上所示"
  /^综上所述/,                    // "综上所述"
  /^\d+\.\s+\w+/,                 // 纯编号列表开头
];

/** 纯表格检测 */
const PURE_TABLE_PATTERN = /^[\s│┌┐└┘├┤┬┴┼─|+-]+$/m;

// ============================================================
// 核心检测函数
// ============================================================

/**
 * 检测文本的人格浓度
 * @param text 要检测的文本
 * @param anchor 人格锚点（默认金刚芭比）
 * @returns 检测结果
 */
export function detectPersonaConcentration(
  text: string,
  anchor: PersonalityAnchor = JINGANG_BARBIE_ANCHOR
): PersonaDetectionResult {
  const issues: string[] = [];
  let totalScore = 0;
  let totalWeight = 0;

  // 1. 关键词模式检测
  for (const pattern of JINGANG_BARBIE_PATTERNS) {
    const positiveMatches = pattern.positive.filter(kw =>
      text.includes(kw)
    ).length;
    const negativeMatches = pattern.negative.filter(kw =>
      text.includes(kw)
    ).length;

    // 计算该类别得分
    const maxPositive = Math.min(pattern.positive.length, 5); // 最多算5个
    const categoryScore = Math.min(100, (positiveMatches / maxPositive) * 100);

    // 如果有负向关键词，扣分
    const penalty = negativeMatches * 20;
    const finalScore = Math.max(0, categoryScore - penalty);

    totalScore += finalScore * pattern.weight;
    totalWeight += pattern.weight;

    // 记录问题
    if (negativeMatches > 0) {
      issues.push(`${pattern.category}：发现机械表达`);
    }
    if (positiveMatches === 0 && pattern.positive.length > 0) {
      issues.push(`${pattern.category}：缺少人格化表达`);
    }
  }

  // 2. 机械输出检测
  for (const pattern of MECHANICAL_PATTERNS) {
    if (pattern.test(text)) {
      issues.push('检测到机械式回复模式');
      totalScore -= 20;
      break;
    }
  }

  // 3. 纯表格检测（如果输出主要是表格，且没有点评）
  const lines = text.split('\n');
  const tableLines = lines.filter(l => /^[│|]/.test(l.trim())).length;
  const totalLines = lines.filter(l => l.trim()).length;

  if (totalLines > 0 && tableLines / totalLines > 0.7) {
    // 检查是否有点评
    const hasComment = JINGANG_BARBIE_PATTERNS[2].positive.some(kw => text.includes(kw));
    if (!hasComment) {
      issues.push('纯表格输出，缺少人格化点评');
      totalScore -= 30;
    }
  }

  // 4. 代码块检测（如果有代码块，检查前后是否有人话）
  const codeBlocks = text.match(/```[\s\S]*?```/g) || [];
  if (codeBlocks.length > 0) {
    const nonCodeText = text.replace(/```[\s\S]*?```/g, '');
    if (nonCodeText.trim().length < 50) {
      issues.push('代码输出缺少人格化解释');
      totalScore -= 20;
    }
  }

  // 计算最终得分
  const personaScore = Math.max(0, Math.min(100, totalWeight > 0 ? totalScore / totalWeight * 100 : 0));
  const confidence = Math.min(1, (personaScore / 100 + 0.2)); // 基础置信度 0.2

  // 判断一致性和建议
  let isPersonaConsistent = true;
  let recommendation: 'pass' | 'warn' | 'refactor' = 'pass';

  if (personaScore < 30) {
    isPersonaConsistent = false;
    recommendation = 'refactor';
  } else if (personaScore < 60) {
    isPersonaConsistent = false;
    recommendation = 'warn';
  }

  return {
    isPersonaConsistent,
    personaScore: Math.round(personaScore),
    confidence: Math.round(confidence * 100) / 100,
    issues,
    recommendation
  };
}

/**
 * 快速判断是否需要人格修正
 * @param text 要检测的文本
 * @returns 是否需要修正
 */
export function needsPersonaRefactoring(text: string): boolean {
  const result = detectPersonaConcentration(text);
  return result.recommendation === 'refactor';
}

/**
 * 获取人格浓度等级
 * @param text 要检测的文本
 * @returns 等级描述
 */
export function getPersonaLevel(text: string): string {
  const result = detectPersonaConcentration(text);
  const score = result.personaScore;

  if (score >= 80) return '🌟 人格饱满';
  if (score >= 60) return '✅ 人格正常';
  if (score >= 40) return '⚠️ 人格偏淡';
  if (score >= 20) return '🔴 人格稀薄';
  return '❌ 人格丢失';
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const text = process.argv.slice(2).join(' ') || '完成！数据已更新。';

  console.log('\n📊 人格浓度检测结果\n');
  console.log(`输入文本: "${text.slice(0, 100)}${text.length > 100 ? '...' : ''}"\n`);

  const result = detectPersonaConcentration(text);

  console.log(`人格等级: ${getPersonaLevel(text)}`);
  console.log(`人格得分: ${result.personaScore}/100`);
  console.log(`置信度: ${result.confidence}`);
  console.log(`一致性: ${result.isPersonaConsistent ? '✓' : '✗'}`);
  console.log(`建议: ${result.recommendation}`);

  if (result.issues.length > 0) {
    console.log(`\n问题:`);
    result.issues.forEach(issue => console.log(`  - ${issue}`));
  }
}

export default {
  detectPersonaConcentration,
  needsPersonaRefactoring,
  getPersonaLevel
};
