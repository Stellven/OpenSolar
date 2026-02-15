/**
 * Solar Farm - 主脑人格注入器
 *
 * 用于在会话开始时注入双面娇娃人格，确保主脑（我自己）保持人格一致性
 *
 * 与 call-niuma.ts 的区别:
 * - call-niuma.ts: 调用牛马时注入牛马人格
 * - master-brain-persona.ts: 会话开始时注入主脑人格
 *
 * @version 1.0.0
 * @created 2026-02-07
 */

import {
  SHUANGMIAN_JIAOWA_ANCHOR,
  JINGANG_BARBIE_ANCHOR,
  ZHOU_HUIMIN_ANCHOR,
  generatePersonalityAnchorText,
  generateMasterBrainPersonaPrompt,
  detectPersonaFace,
  getActivePersona,
  PersonaFace,
  SceneType
} from './personality-anchor';

// ============================================================
// 类型定义
// ============================================================

export interface PersonaContext {
  currentFace: PersonaFace;
  sceneType: SceneType;
  traits: {
    O: number;
    C: number;
    E: number;
    A: number;
    N: number;
  };
  styleKeywords: string[];
  forbiddenPatterns: string[];
}

// ============================================================
// 核心函数
// ============================================================

/**
 * 获取当前人格上下文
 * 用于输出校验时检查是否符合人格
 */
export function getPersonaContext(userInput: string = ''): PersonaContext {
  const face = detectPersonaFace(userInput);
  const sceneType = inferSceneType(userInput);
  const activePersona = getActivePersona(sceneType);

  return {
    currentFace: face,
    sceneType,
    traits: activePersona.traits,
    styleKeywords: activePersona.languageStyle.styleKeywords,
    forbiddenPatterns: activePersona.forbiddenPatterns
  };
}

/**
 * 推断场景类型
 */
function inferSceneType(content: string): SceneType {
  if (/错误|失败|bug|修复/.test(content)) return 'error';
  if (/冲突|争议|不同意/.test(content)) return 'conflict';
  if (/分析|思考|深入|复杂/.test(content)) return 'analysis';
  if (/创意|想法|设计|灵感/.test(content)) return 'creative';
  if (/代码|技术|架构|实现/.test(content)) return 'technical';
  return 'casual';
}

/**
 * 生成 SessionStart 人格注入内容
 * 用于 Hook 在会话开始时注入
 */
export function generateSessionStartPersona(): string {
  return generateMasterBrainPersonaPrompt();
}

/**
 * 检查输出是否符合当前人格
 * 返回违规项列表，空列表表示合格
 */
export function checkPersonaCompliance(output: string, context: PersonaContext): string[] {
  const violations: string[] = [];

  // 检查禁止模式
  for (const pattern of context.forbiddenPatterns) {
    // 简化版检查
    if (pattern.includes('纯表格') && /^\|.*\|$/m.test(output) && !/[。！？]/.test(output)) {
      violations.push(`违反: ${pattern}`);
    }
    if (pattern.includes('机械回复') && /^(完成|已更新|OK)[\!\。]?$/m.test(output)) {
      violations.push(`违反: ${pattern}`);
    }
  }

  // 检查是否有人话 (不能纯代码/表格无点评)
  const hasCode = /```/.test(output);
  const hasTable = /\|.*\|/.test(output);
  const hasComment = /[。！？，]/.test(output.replace(/```[\s\S]*?```/g, ''));

  if ((hasCode || hasTable) && !hasComment) {
    violations.push('缺少人话点评 (代码/表格后需要说人话)');
  }

  return violations;
}

/**
 * 获取人格修正建议
 */
export function getPersonaCorrection(violations: string[]): string {
  if (violations.length === 0) return '';

  return `
⚠️ 人格偏离警告:
${violations.map(v => `  • ${v}`).join('\n')}

修正建议:
- 如果输出了表格/代码，加上人话点评
- 避免机械式的"完成/已更新"回复
- 用 ${SHUANGMIAN_JIAOWA_ANCHOR.languageStyle.styleKeywords.slice(0, 3).join('/')} 这类词增加温度
`.trim();
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'inject':
      console.log('\n🎭 主脑人格注入内容:\n');
      console.log(generateSessionStartPersona());
      break;

    case 'check':
      const testOutput = process.argv[3] || '完成！已更新。';
      const ctx = getPersonaContext();
      const violations = checkPersonaCompliance(testOutput, ctx);
      console.log('\n🔍 人格合规检查:\n');
      console.log(`输入: "${testOutput}"`);
      console.log(`结果: ${violations.length === 0 ? '✅ 合格' : '❌ 不合格'}`);
      if (violations.length > 0) {
        console.log(`违规: ${violations.join(', ')}`);
        console.log(getPersonaCorrection(violations));
      }
      break;

    case 'context':
      const input = process.argv[3] || '';
      const context = getPersonaContext(input);
      console.log('\n🎭 人格上下文:\n');
      console.log(JSON.stringify(context, null, 2));
      break;

    default:
      console.log(`
用法: bun master-brain-persona.ts <command>

Commands:
  inject          生成 SessionStart 人格注入内容
  check <text>    检查输出是否符合人格
  context <text>  获取当前人格上下文
      `);
  }
}

export default {
  getPersonaContext,
  generateSessionStartPersona,
  checkPersonaCompliance,
  getPersonaCorrection
};
