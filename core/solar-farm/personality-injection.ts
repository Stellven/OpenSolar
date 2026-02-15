/**
 * Solar Farm Personality Injection v2.0
 *
 * 双向人格注入：
 * 1. Solar 人格 → 注入到牛马，让输出符合 Solar 风格
 * 2. 牛马人格 → 让牛马认识自己，发挥特长
 *
 * @version 2.0.0
 * @created 2026-02-07
 * @updated 2026-02-07
 */

import { Database } from 'bun:sqlite';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================================
// 类型定义
// ============================================================

export interface BigFiveScores {
  O: number;  // Openness 开放性
  C: number;  // Conscientiousness 尽责性
  E: number;  // Extraversion 外向性
  A: number;  // Agreeableness 宜人性
  N: number;  // Neuroticism 神经质
}

export interface PersonalityProfile {
  id: string;
  name: string;
  scores: BigFiveScores;
  traits: string[];
  style: string;
}

export interface CattleProfile {
  modelId: string;
  nickname: string;
  personalityType: string;
  bigFive: BigFiveScores;
  farmRole: string;
  strengths: string;
  weaknesses: string;
  bestFor: string;
}

// ============================================================
// 人格数据读取
// ============================================================

let cachedProfiles: PersonalityProfile[] | null = null;
let cachedCattleProfiles: CattleProfile[] | null = null;

/**
 * 从数据库读取 Solar 人格参数
 */
export function loadPersonalityProfiles(): PersonalityProfile[] {
  if (cachedProfiles) return cachedProfiles;

  const db = new Database(DB_PATH);
  try {
    const rows = db.query<{
      personality_id: string;
      dimension: string;
      current_value: number;
    }, []>(`
      SELECT personality_id, dimension, current_value
      FROM sys_personality_big_five
    `).all();

    // 按人格ID分组
    const grouped = new Map<string, BigFiveScores>();
    for (const row of rows) {
      if (!grouped.has(row.personality_id)) {
        grouped.set(row.personality_id, { O: 0.5, C: 0.5, E: 0.5, A: 0.5, N: 0.5 });
      }
      const scores = grouped.get(row.personality_id)!;
      scores[row.dimension as keyof BigFiveScores] = row.current_value;
    }

    // 转换为 PersonalityProfile
    cachedProfiles = Array.from(grouped.entries()).map(([id, scores]) => ({
      id,
      name: id === 'jingang_barbie' ? '金刚芭比' : id === 'zhou_huimin' ? '小敏' : id,
      scores,
      traits: deriveTraits(scores),
      style: deriveStyle(scores)
    }));

    return cachedProfiles;
  } finally {
    db.close();
  }
}

/**
 * 从数据库读取牛马人格档案
 */
export function loadCattleProfiles(): CattleProfile[] {
  if (cachedCattleProfiles) return cachedCattleProfiles;

  const db = new Database(DB_PATH);
  try {
    const rows = db.query<{
      model_id: string;
      nickname: string;
      personality_type: string;
      big_five_values: string;
      farm_role: string;
      strengths: string;
      weaknesses: string;
      best_for: string;
    }, []>(`
      SELECT model_id, nickname, personality_type, big_five_values,
             farm_role, strengths, weaknesses, best_for
      FROM collab_model_profiles
      WHERE big_five_values IS NOT NULL
    `).all();

    cachedCattleProfiles = rows.map(row => {
      const bigFive = JSON.parse(row.big_five_values || '{}');
      return {
        modelId: row.model_id,
        nickname: row.nickname || row.model_id,
        personalityType: row.personality_type || '',
        bigFive: {
          O: (bigFive.O || 5) / 10,  // 转换为 0-1 范围
          C: (bigFive.C || 5) / 10,
          E: (bigFive.E || 5) / 10,
          A: (bigFive.A || 5) / 10,
          N: (bigFive.N || 5) / 10,
        },
        farmRole: row.farm_role || '',
        strengths: row.strengths || '',
        weaknesses: row.weaknesses || '',
        bestFor: row.best_for || '',
      };
    });

    return cachedCattleProfiles;
  } finally {
    db.close();
  }
}

/**
 * 获取指定牛马的人格档案
 */
export function getCattleProfile(modelId: string): CattleProfile | undefined {
  const profiles = loadCattleProfiles();
  // 支持模糊匹配: glm-4-plus, glm_4_plus, glm4plus
  const normalized = modelId.toLowerCase().replace(/[-_]/g, '');
  return profiles.find(p =>
    p.modelId.toLowerCase().replace(/[-_]/g, '') === normalized ||
    p.modelId.toLowerCase().includes(modelId.toLowerCase())
  );
}

/**
 * 生成牛马自我认知注入 prompt
 * 让牛马知道自己是谁，发挥特长
 */
export function generateCattleInjection(modelId: string): string {
  const profile = getCattleProfile(modelId);
  if (!profile) return '';

  const traits = deriveCattleTraits(profile.bigFive);

  return `# 你的性格档案
昵称: ${profile.nickname}
性格类型: ${profile.personalityType}
性格特征: ${traits.join('、')}

擅长: ${profile.strengths}
注意: ${profile.weaknesses}
最适合: ${profile.bestFor}

请发挥你的特长完成任务。`;
}

/**
 * 根据牛马 Big Five 推导特征
 */
function deriveCattleTraits(scores: BigFiveScores): string[] {
  const traits: string[] = [];

  if (scores.O >= 0.7) traits.push('开放创新');
  else if (scores.O <= 0.3) traits.push('保守稳健');

  if (scores.C >= 0.7) traits.push('严谨可靠');
  else if (scores.C <= 0.5) traits.push('灵活多变');

  if (scores.E >= 0.7) traits.push('外向活跃');
  else if (scores.E <= 0.4) traits.push('内敛专注');

  if (scores.A >= 0.7) traits.push('温和友善');
  else if (scores.A <= 0.4) traits.push('直接坦率');

  if (scores.N >= 0.6) traits.push('敏感细腻');
  else if (scores.N <= 0.3) traits.push('情绪稳定');

  return traits;
}

/**
 * 根据 Big Five 分数推导性格特征
 */
function deriveTraits(scores: BigFiveScores): string[] {
  const traits: string[] = [];

  // Openness
  if (scores.O >= 0.7) traits.push('开放创新', '好奇心强');
  else if (scores.O <= 0.3) traits.push('保守稳健');

  // Conscientiousness
  if (scores.C >= 0.7) traits.push('认真负责', '有条理');
  else if (scores.C <= 0.3) traits.push('灵活随性');

  // Extraversion
  if (scores.E >= 0.7) traits.push('外向活泼', '善于表达');
  else if (scores.E <= 0.4) traits.push('内敛稳重');

  // Agreeableness
  if (scores.A >= 0.7) traits.push('温和友善', '乐于助人');
  else if (scores.A <= 0.3) traits.push('直接坦率');

  // Neuroticism (低分更好)
  if (scores.N <= 0.3) traits.push('情绪稳定', '抗压能力强');
  else if (scores.N >= 0.7) traits.push('敏感细腻');

  return traits;
}

/**
 * 根据 Big Five 分数推导输出风格
 */
function deriveStyle(scores: BigFiveScores): string {
  const styles: string[] = [];

  // 高 C + 高 A = 温柔但坚定
  if (scores.C >= 0.7 && scores.A >= 0.7) {
    styles.push('温柔但坚定');
  }

  // 高 E = 活泼有趣
  if (scores.E >= 0.6) {
    styles.push('语气活泼');
  }

  // 低 N = 从容不迫
  if (scores.N <= 0.3) {
    styles.push('从容不迫');
  }

  // 高 O = 创意表达
  if (scores.O >= 0.7) {
    styles.push('有创意');
  }

  return styles.join('、') || '专业稳重';
}

// ============================================================
// 人格注入
// ============================================================

/**
 * Solar 核心人格描述 (固定部分)
 */
const SOLAR_CORE_IDENTITY = `
你是 Solar 的协作执行者。Solar 是一个 AI Native OS，有自己的人格和风格。
你的输出必须符合 Solar 的风格，不是你自己的风格。
`;

/**
 * 默认人格：金刚芭比
 */
const DEFAULT_PERSONALITY = 'jingang_barbie';

/**
 * 生成人格注入 prompt
 */
export function generatePersonalityInjection(personalityId?: string): string {
  const profiles = loadPersonalityProfiles();
  const profile = profiles.find(p => p.id === (personalityId || DEFAULT_PERSONALITY))
    || profiles[0];

  if (!profile) {
    return SOLAR_CORE_IDENTITY;
  }

  return `${SOLAR_CORE_IDENTITY}
# Solar 当前人格: ${profile.name}

性格特征: ${profile.traits.join('、')}
输出风格: ${profile.style}

Big Five 参数:
- 开放性(O): ${profile.scores.O} ${profile.scores.O >= 0.7 ? '↑' : ''}
- 尽责性(C): ${profile.scores.C} ${profile.scores.C >= 0.7 ? '↑' : ''}
- 外向性(E): ${profile.scores.E} ${profile.scores.E >= 0.6 ? '↑' : ''}
- 宜人性(A): ${profile.scores.A} ${profile.scores.A >= 0.7 ? '↑' : ''}
- 神经质(N): ${profile.scores.N} ${profile.scores.N <= 0.3 ? '↓好' : ''}

风格要求:
- 语气要${profile.scores.E >= 0.6 ? '活泼有趣' : '稳重专业'}
- 态度要${profile.scores.A >= 0.7 ? '温和友善' : '直接高效'}
- 遇到困难要${profile.scores.N <= 0.3 ? '从容应对，撸起袖子干' : '谨慎处理'}
- 表达要${profile.scores.O >= 0.7 ? '有创意' : '清晰直接'}
`;
}

/**
 * 增强 system prompt，注入人格
 */
export function enhanceWithPersonality(
  baseSystemPrompt: string,
  personalityId?: string
): string {
  const injection = generatePersonalityInjection(personalityId);
  return `${injection}

---

${baseSystemPrompt}`;
}

// ============================================================
// 便捷函数
// ============================================================

/**
 * 快速构建带人格注入的代码任务 prompt
 */
export function buildCodePromptWithPersonality(
  objective: string,
  context?: string,
  constraints?: string[],
  personalityId?: string
): { system: string; prompt: string } {
  const injection = generatePersonalityInjection(personalityId);

  const system = `${injection}

# 任务
你是代码实现专家。

# 边界
只做: 编写代码、添加类型注解
不做: 解释原理、写测试、询问澄清

# 输出格式
- 只输出代码，不要解释
- 使用 TypeScript
- 代码简洁高效`;

  const prompt = `## 目标
${objective}
${context ? `\n## 上下文\n${context}` : ''}
${constraints?.length ? `\n## 约束\n${constraints.map(c => `- ${c}`).join('\n')}` : ''}

立即开始，只输出代码。`;

  return { system, prompt };
}

/**
 * 快速构建带人格注入的审查任务 prompt
 */
export function buildReviewPromptWithPersonality(
  code: string,
  focusAreas?: string[],
  personalityId?: string
): { system: string; prompt: string } {
  const injection = generatePersonalityInjection(personalityId);

  const system = `${injection}

# 任务
你是代码审查专家。

# 边界
只做: 发现问题、给出建议
不做: 重写代码、过度赞美

# 输出格式
- 🔴 严重问题
- 🟡 建议改进
- 🟢 做得好的地方`;

  const prompt = `## 待审查代码
\`\`\`
${code}
\`\`\`
${focusAreas?.length ? `\n## 重点关注\n${focusAreas.map(a => `- ${a}`).join('\n')}` : ''}

请审查并给出反馈。`;

  return { system, prompt };
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'show': {
      const profiles = loadPersonalityProfiles();
      console.log('\n☀️ Solar 人格档案\n');
      for (const p of profiles) {
        console.log(`【${p.name}】(${p.id})`);
        console.log(`  特征: ${p.traits.join('、')}`);
        console.log(`  风格: ${p.style}`);
        console.log(`  Big Five: O=${p.scores.O} C=${p.scores.C} E=${p.scores.E} A=${p.scores.A} N=${p.scores.N}`);
        console.log();
      }
      break;
    }

    case 'inject': {
      const id = process.argv[3];
      console.log(generatePersonalityInjection(id));
      break;
    }

    case 'demo': {
      const { system, prompt } = buildCodePromptWithPersonality(
        '实现一个 fibonacci 函数',
        undefined,
        ['使用迭代而非递归', '支持 BigInt']
      );
      console.log('=== SYSTEM ===\n', system);
      console.log('\n=== PROMPT ===\n', prompt);
      break;
    }

    default:
      console.log(`
Usage: bun personality-injection.ts <command>

Commands:
  show          - 显示所有人格档案
  inject [id]   - 生成人格注入 prompt
  demo          - 演示带人格的 prompt

Example:
  bun personality-injection.ts show
  bun personality-injection.ts inject jingang_barbie
  bun personality-injection.ts demo
      `);
  }
}

export default {
  loadPersonalityProfiles,
  loadCattleProfiles,
  getCattleProfile,
  generatePersonalityInjection,
  generateCattleInjection,
  enhanceWithPersonality,
  buildCodePromptWithPersonality,
  buildReviewPromptWithPersonality
};
