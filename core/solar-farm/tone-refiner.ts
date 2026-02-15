/**
 * Solar Farm - 语气修复器 (Tone Refiner)
 *
 * 基于 Intent Engine 的数据资产，学习并修复输出语气
 * 从 sys_training_samples 正样本中提取"有温度"的表达模式
 *
 * @version 1.0.0
 * @created 2026-02-07
 * @authors Solar + 监护人智慧
 */

import { Database } from 'bun:sqlite';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================================
// 类型定义
// ============================================================

/** 语气模式 */
interface TonePattern {
  pattern: string;
  replacement: string;
  category: 'opening' | 'closing' | 'connector' | 'expression';
  frequency: number;
}

/** 语气库 */
interface ToneLibrary {
  warmOpenings: string[];      // 温暖的开头
  warmClosings: string[];      // 有温度的结尾
  expressiveWords: string[];   // 表达性词汇
  connectors: string[];        // 连接词
}

// ============================================================
// 从数据资产学习的语气模式
// ============================================================

/**
 * 从 sys_training_samples 提取语气模式
 */
export function extractTonePatternsFromData(): ToneLibrary {
  const db = new Database(DB_PATH);

  try {
    // 获取高质量正样本
    const samples = db.query(`
      SELECT assistant_output
      FROM sys_training_samples
      WHERE sample_type = 'positive' AND quality_score >= 0.8
      ORDER BY created_at DESC
      LIMIT 500
    `).all() as { assistant_output: string }[];

    const openings = new Map<string, number>();
    const closings = new Map<string, number>();
    const expressions = new Map<string, number>();

    for (const sample of samples) {
      const text = sample.assistant_output || '';

      // 提取开头模式（前 50 字符）
      const opening = text.slice(0, 50).split(/[。！？\n]/)[0];
      if (opening && opening.length > 2) {
        openings.set(opening.trim(), (openings.get(opening.trim()) || 0) + 1);
      }

      // 提取表达性词汇
      const expressivePatterns = text.match(/[嘿哈呀啦嘛呢吧哦嗯～！]+/g);
      if (expressivePatterns) {
        for (const expr of expressivePatterns) {
          expressions.set(expr, (expressions.get(expr) || 0) + 1);
        }
      }
    }

    // 过滤高频模式
    const warmOpenings = Array.from(openings.entries())
      .filter(([_, count]) => count >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([pattern]) => pattern);

    const expressiveWords = Array.from(expressions.entries())
      .filter(([_, count]) => count >= 3)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 30)
      .map(([pattern]) => pattern);

    return {
      warmOpenings: warmOpenings.length > 0 ? warmOpenings : DEFAULT_TONE_LIBRARY.warmOpenings,
      warmClosings: DEFAULT_TONE_LIBRARY.warmClosings,
      expressiveWords: expressiveWords.length > 0 ? expressiveWords : DEFAULT_TONE_LIBRARY.expressiveWords,
      connectors: DEFAULT_TONE_LIBRARY.connectors
    };

  } finally {
    db.close();
  }
}

/** 默认语气库（基于金刚芭比人格） */
const DEFAULT_TONE_LIBRARY: ToneLibrary = {
  warmOpenings: [
    '搞定啦！',
    '来看看这个～',
    '好嘞！',
    '没问题！',
    '让我看看...',
    '有意思！',
    '这个思路很对！',
    '找到了！'
  ],
  warmClosings: [
    '～',
    '！',
    '哈哈',
    '呢',
    '哦',
    '嘿嘿'
  ],
  expressiveWords: [
    '嘿', '哈', '呀', '啦', '嘛', '呢', '吧', '哦', '嗯', '～'
  ],
  connectors: [
    '这说明',
    '值得注意的是',
    '有意思的是',
    '其实',
    '说白了',
    '简单来说'
  ]
};

// ============================================================
// 语气修复器
// ============================================================

/**
 * 修复冷冰冰的输出语气
 */
export function refineTone(text: string, options?: {
  intensity?: 'light' | 'medium' | 'strong';
  useDataDriven?: boolean;
}): string {
  const intensity = options?.intensity || 'medium';
  const library = options?.useDataDriven
    ? extractTonePatternsFromData()
    : DEFAULT_TONE_LIBRARY;

  let result = text;

  // 1. 修复机械开头
  result = refineOpening(result, library);

  // 2. 修复机械结尾
  result = refineClosing(result, library, intensity);

  // 3. 修复机械连接词
  result = refineConnectors(result, library);

  // 4. 添加表达性词汇（强度相关）
  if (intensity === 'strong') {
    result = addExpressiveness(result, library);
  }

  return result;
}

function refineOpening(text: string, library: ToneLibrary): string {
  // 机械开头替换表
  const mechanicalOpenings: [RegExp, string][] = [
    [/^完成[！!。.]?\s*/, '搞定啦！'],
    [/^已完成[。.]?\s*/, '搞定了～ '],
    [/^已处理[。.]?\s*/, '处理好了！'],
    [/^已更新[。.]?\s*/, '更新好了～ '],
    [/^请查收[。.]?\s*/, '来看看～ '],
    [/^如下[：:]\s*/, '是这样的：'],
    [/^统计结果[如如]下[：:]\s*/, '来看看这组数据～\n\n'],
    [/^分析结果[如如]下[：:]\s*/, '分析了一下，发现：\n\n']
  ];

  for (const [pattern, replacement] of mechanicalOpenings) {
    if (pattern.test(text)) {
      return text.replace(pattern, replacement);
    }
  }

  return text;
}

function refineClosing(text: string, library: ToneLibrary, intensity: string): string {
  // 如果结尾太干，加点语气
  const lastChar = text.trim().slice(-1);

  if (intensity !== 'light' && /[a-zA-Z0-9\u4e00-\u9fa5]/.test(lastChar)) {
    // 结尾是普通字符，加语气
    const closings = ['～', '！', ''];
    const randomClosing = closings[Math.floor(Math.random() * closings.length)];
    return text.trimEnd() + randomClosing;
  }

  return text;
}

function refineConnectors(text: string, library: ToneLibrary): string {
  // 机械连接词替换
  const mechanicalConnectors: [RegExp, string][] = [
    [/综上所述[，,]?/g, '总结一下，'],
    [/由此可见[，,]?/g, '这说明，'],
    [/据此[，,]?/g, '根据这个，'],
    [/因此[，,]?/g, '所以呢，'],
    [/鉴于此[，,]?/g, '考虑到这些，'],
    [/基于上述分析[，,]?/g, '分析下来，']
  ];

  let result = text;
  for (const [pattern, replacement] of mechanicalConnectors) {
    result = result.replace(pattern, replacement);
  }

  return result;
}

function addExpressiveness(text: string, library: ToneLibrary): string {
  // 在适当位置添加语气词
  let result = text;

  // 在标点后偶尔加语气词
  result = result.replace(/。/g, () => {
    return Math.random() > 0.7 ? '～' : '。';
  });

  return result;
}

// ============================================================
// 与 Intent Engine 集成
// ============================================================

/**
 * 记录语气修复效果（供 Intent Engine 学习）
 */
export function recordToneRefinement(
  original: string,
  refined: string,
  userFeedback?: 'positive' | 'negative' | 'neutral'
): void {
  const db = new Database(DB_PATH);

  try {
    // 记录到 sys_intent_patterns（如果表存在）
    const tableExists = db.query(`
      SELECT name FROM sqlite_master
      WHERE type='table' AND name='sys_intent_tone_patterns'
    `).get();

    if (!tableExists) {
      // 创建语气模式表
      db.run(`
        CREATE TABLE IF NOT EXISTS sys_intent_tone_patterns (
          pattern_id TEXT PRIMARY KEY,
          original_pattern TEXT,
          refined_pattern TEXT,
          feedback TEXT,
          usage_count INTEGER DEFAULT 1,
          success_rate REAL DEFAULT 0.5,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
      `);
    }

    const patternId = `tone_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    db.run(`
      INSERT INTO sys_intent_tone_patterns (pattern_id, original_pattern, refined_pattern, feedback)
      VALUES (?, ?, ?, ?)
    `, [patternId, original.slice(0, 100), refined.slice(0, 100), userFeedback || 'neutral']);

  } finally {
    db.close();
  }
}

/**
 * 从 Intent Engine 获取学习到的语气偏好
 */
export function getLearnedTonePreferences(): TonePattern[] {
  const db = new Database(DB_PATH);

  try {
    const patterns = db.query(`
      SELECT original_pattern, refined_pattern, usage_count,
             success_rate
      FROM sys_intent_tone_patterns
      WHERE success_rate > 0.6
      ORDER BY usage_count DESC
      LIMIT 20
    `).all() as any[];

    return patterns.map(p => ({
      pattern: p.original_pattern,
      replacement: p.refined_pattern,
      category: 'expression' as const,
      frequency: p.usage_count
    }));

  } catch {
    return [];
  } finally {
    db.close();
  }
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const text = process.argv.slice(2).join(' ') || '完成！数据已更新。';
  const useData = process.argv.includes('--data');

  console.log('\n🎨 语气修复测试\n');
  console.log(`原始文本: "${text}"\n`);

  const refined = refineTone(text, {
    intensity: 'medium',
    useDataDriven: useData
  });

  console.log(`修复后: "${refined}"\n`);

  if (useData) {
    console.log('(使用数据驱动模式，从 sys_training_samples 学习)\n');
  }
}

export default {
  refineTone,
  extractTonePatternsFromData,
  recordToneRefinement,
  getLearnedTonePreferences
};
