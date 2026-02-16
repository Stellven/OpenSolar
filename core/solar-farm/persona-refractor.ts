/**
 * Solar Farm - 人格修正模块 (Layer 3: 按需修正)
 *
 * 当检测到严重出戏时，触发两步式重写机制
 *
 * @version 1.0.0
 * @created 2026-02-07
 * @authors 稳健派(gemini-2.5-pro), 探索派(gemini-3-pro), 审判官(deepseek-r1), 建设者(glm-4-plus)
 */

import { PersonalityAnchor, JINGANG_BARBIE_ANCHOR, generatePersonalityAnchorText } from './personality-anchor';
import { PersonaDetectionResult, detectPersonaConcentration } from './persona-detector';
import { refineTone, recordToneRefinement } from './tone-refiner';

// ============================================================
// 类型定义
// ============================================================

/** 修正结果 */
export interface PersonaRefactoringResult {
  originalText: string;
  refactoredText: string;
  beforeScore: number;
  afterScore: number;
  success: boolean;
  method: 'micro-inject' | 'full-rewrite' | 'styled-cot';
}

/** 修正配置 */
export interface RefactoringConfig {
  anchor: PersonalityAnchor;
  preferredMethod: 'auto' | 'micro-inject' | 'full-rewrite' | 'styled-cot';
  maxRetries: number;
}

// ============================================================
// 微注入模式 (Micro-Inject)
// ============================================================

/**
 * 微注入修正 - 在关键位置插入人格化表达
 * 适用于轻度出戏的情况
 */
function microInject(text: string, anchor: PersonalityAnchor): string {
  let result = text;

  // 1. 如果是纯表格，在前后加人格化表达
  if (/^[│┌]/.test(text.trim())) {
    result = `来看看这个数据～\n\n${text}\n\n这个结果还挺有意思的，说明...`;
  }

  // 2. 如果是代码块开头，加人格化解释
  if (text.trim().startsWith('```')) {
    result = `让我写个代码搞定这个～\n\n${text}`;
  }

  // 3. 如果是机械回复，替换为人格化版本
  const mechanicalReplaces: [RegExp, string][] = [
    [/^完成[！!。.]?\s*$/, '搞定啦！'],
    [/^已更新[。.]?\s*$/, '更新好了～'],
    [/^已处理[。.]?\s*$/, '处理好了！'],
    [/^请查收[。.]?\s*$/, '来，看看这个～'],
  ];

  for (const [pattern, replacement] of mechanicalReplaces) {
    if (pattern.test(result.trim())) {
      result = replacement;
      break;
    }
  }

  // 4. 如果以"综上所述"等开头，替换为人格化表达
  result = result.replace(/^综上所述[，,]?/, '总结一下呢，');
  result = result.replace(/^由此可见[，,]?/, '这说明啊，');
  result = result.replace(/^据此[，,]?/, '根据这个来看，');

  // 5. 在末尾没有语气词时，加一个
  if (result.length > 20 && !/[～~！!？?哈嘿呀啦。]$/.test(result.trim())) {
    const endings = ['～', '！', '哈哈', ''];
    result = result.trimEnd() + endings[Math.floor(Math.random() * endings.length)];
  }

  return result;
}

// ============================================================
// 风格化思维链 (Styled Chain-of-Thought)
// ============================================================

/**
 * 生成风格化思维链的提示
 * 用于数据分析等高认知负载场景
 */
export function generateStyledCoTPrompt(
  task: string,
  anchor: PersonalityAnchor = JINGANG_BARBIE_ANCHOR
): string {
  return `
${generatePersonalityAnchorText(anchor)}

## 任务
${task}

## 执行方式：风格化思维链

<THINKING style="${anchor.name}">
先用 ${anchor.name} 的口吻进行思考，比如：
"让我看看这个问题...嗯，首先要搞清楚..."
"这个数据有点意思哦，说明..."
</THINKING>

<ANALYSIS>
然后进行专业准确的分析/代码/计算
</ANALYSIS>

<COMMENT style="${anchor.name}">
最后用 ${anchor.name} 的口吻做总结点评，比如：
"搞定！总结一下就是..."
"这个结果还挺有意思的，核心发现是..."
</COMMENT>

现在开始执行任务，记住保持 ${anchor.name} 的人格！
`.trim();
}

// ============================================================
// 完整重写 (Full Rewrite)
// ============================================================

/**
 * 生成完整重写的提示
 * 用于严重出戏的情况
 */
export function generateRewritePrompt(
  originalText: string,
  anchor: PersonalityAnchor = JINGANG_BARBIE_ANCHOR
): string {
  return `
# 人格重写任务

你需要将以下"冷冰冰"的输出重写为 ${anchor.name} 的风格。

## ${anchor.name} 的人格特点
${generatePersonalityAnchorText(anchor)}

## 原始输出（冷冰冰版本）
${originalText}

## 重写要求
1. **保持核心内容不变** - 数据、代码、事实必须 100% 保留
2. **调整语气** - 用 ${anchor.name} 的口吻表达
3. **添加点评** - 对数据/代码加入个人看法
4. **使用人话** - 避免机械式表达

## 重写后的输出（${anchor.name}版本）
`.trim();
}

// ============================================================
// 核心修正函数
// ============================================================

/**
 * 执行人格修正
 * @param text 原始文本
 * @param config 修正配置
 * @returns 修正结果
 */
export function executePersonaRefactoring(
  text: string,
  config: Partial<RefactoringConfig> = {}
): PersonaRefactoringResult {
  const anchor = config.anchor || JINGANG_BARBIE_ANCHOR;
  const preferredMethod = config.preferredMethod || 'auto';

  // 检测原始文本的人格浓度
  const beforeResult = detectPersonaConcentration(text, anchor);
  const beforeScore = beforeResult.personaScore;

  // 根据分数选择修正方法
  let method: 'micro-inject' | 'full-rewrite' | 'styled-cot';
  let refactoredText: string;

  if (preferredMethod !== 'auto') {
    method = preferredMethod;
  } else if (beforeScore >= 40) {
    // 轻度出戏，用微注入
    method = 'micro-inject';
  } else if (beforeScore >= 20) {
    // 中度出戏，用风格化思维链（需要外部调用 LLM）
    method = 'styled-cot';
  } else {
    // 严重出戏，用完整重写（需要外部调用 LLM）
    method = 'full-rewrite';
  }

  // 执行修正
  switch (method) {
    case 'micro-inject':
      refactoredText = microInject(text, anchor);
      break;
    case 'styled-cot':
      // 返回提示词，需要外部调用 LLM
      refactoredText = `[需要 LLM 重新生成]\n\n${generateStyledCoTPrompt(text, anchor)}`;
      break;
    case 'full-rewrite':
      // 返回提示词，需要外部调用 LLM
      refactoredText = `[需要 LLM 重写]\n\n${generateRewritePrompt(text, anchor)}`;
      break;
  }

  // 检测修正后的人格浓度（如果是微注入）
  let afterScore = beforeScore;
  if (method === 'micro-inject') {
    const afterResult = detectPersonaConcentration(refactoredText, anchor);
    afterScore = afterResult.personaScore;
  }

  return {
    originalText: text,
    refactoredText,
    beforeScore,
    afterScore,
    success: method === 'micro-inject' ? afterScore > beforeScore : true,
    method
  };
}

/**
 * 快速修正 - 只做微注入
 * @param text 原始文本
 * @returns 修正后的文本
 */
export function quickFix(text: string): string {
  return microInject(text, JINGANG_BARBIE_ANCHOR);
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const text = process.argv.slice(2).join(' ') || '完成！数据已更新。';

  console.log('\n🔧 人格修正测试\n');
  console.log(`原始文本: "${text}"\n`);

  const result = executePersonaRefactoring(text);

  console.log(`修正方法: ${result.method}`);
  console.log(`修正前得分: ${result.beforeScore}`);
  console.log(`修正后得分: ${result.afterScore}`);
  console.log(`修正成功: ${result.success ? '✓' : '✗'}`);
  console.log(`\n修正结果:\n${result.refactoredText}`);
}

export default {
  executePersonaRefactoring,
  generateStyledCoTPrompt,
  generateRewritePrompt,
  quickFix
};
