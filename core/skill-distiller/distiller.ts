/**
 * Skill Distiller
 * 基于 SkillRL 论文的技能蒸馏器
 *
 * 核心功能：
 * 1. 从 sys_favorites 中提取成功模式
 * 2. 调用审判官 (deepseek-r1) 进行技能蒸馏
 * 3. 将蒸馏结果存入技能库
 */

import type { Skill, DistillationRequest, DistillationResult, SkillLayer } from './schema';
import { createSkill, getFavoriteForDistillation } from './db';

// 蒸馏器配置
const DISTILLER_CONFIG = {
  model: 'deepseek-r1' as const,  // 审判官
  min_importance: 7,  // 最低重要性阈值
  max_retries: 2
};

/**
 * 蒸馏系统提示词
 */
const DISTILLER_SYSTEM_PROMPT = `你是审判官，D&D 角色是 judge，同时也是技能提炼专家。

KNOBS: rigor=5, skepticism=4, explore=2, decide=3, risk=3,
       tool=3, compression=4, check=5, empathy=2, compete=2
LEVEL=5

你的任务是从成功案例中提取可复用的技能（Skill）。

## 技能定义（基于 SkillRL 论文）

技能是**可复用的行为模式**，包含：
1. **触发条件**：什么时候应该使用这个技能
2. **执行步骤**：具体的操作流程
3. **前置条件**：使用前必须满足的条件
4. **预期输出**：技能执行后应达成的结果

## 技能层级

- **core**: 跨领域抽象推理模式（如"分解复杂任务"、"权衡分析"）
- **domain**: 特定领域可复用能力（如"Python 调试"、"API 设计"）
- **utility**: 高度具体的工具技能（如"JSON → Python 类"）

## 输出格式

必须输出 JSON，格式如下：
\`\`\`json
{
  "name": "技能名称（简短、动词开头）",
  "description": "技能描述（一句话说明做什么、何时用）",
  "layer": "core|domain|utility",
  "trigger_keywords": ["关键词1", "关键词2"],
  "applicable_contexts": ["上下文1", "上下文2"],
  "preconditions": ["前置条件1"],
  "llm_prompt_template": "技能执行时的提示词模板，可包含 {变量}",
  "parameters": [
    {"name": "参数名", "type": "string", "description": "说明", "required": true}
  ],
  "tags": ["标签1", "标签2"],
  "confidence": 0.0-1.0
}
\`\`\`

## 注意事项

1. **抽象而非记忆**：提取通用模式，不是复制具体答案
2. **可操作**：技能必须能被"牛马"执行
3. **单一职责**：每个技能只做一件事
4. **明确边界**：清晰定义何时适用、何时不适用

如果无法提取有价值的技能，设置 confidence = 0 并说明原因。`;

/**
 * 从收藏夹蒸馏技能
 */
export async function distillFromFavorite(
  favoriteId: number,
  options?: { layer?: SkillLayer; author_agent?: string }
): Promise<DistillationResult> {
  // 1. 获取收藏内容
  const favorite = getFavoriteForDistillation(favoriteId);
  if (!favorite) {
    return { success: false, error: `Favorite ${favoriteId} not found`, confidence: 0 };
  }

  // 2. 检查重要性
  // if (favorite.importance < DISTILLER_CONFIG.min_importance) {
  //   return {
  //     success: false,
  //     error: `Importance ${favorite.importance} below threshold ${DISTILLER_CONFIG.min_importance}`,
  //     confidence: 0
  //   };
  // }

  // 3. 构建蒸馏请求
  const request: DistillationRequest = {
    source_type: 'favorite',
    source_id: String(favoriteId),
    source_content: {
      question: favorite.question,
      answer: favorite.answer,
      context: favorite.title,
      tags: favorite.tags
    },
    target_layer: options?.layer,
    author_agent: options?.author_agent || 'solar'
  };

  // 4. 调用蒸馏
  return await performDistillation(request);
}

/**
 * 执行蒸馏（调用审判官）
 * 支持两种方式：
 * 1. 直接调用 Brain Router MCP 工具（推荐）
 * 2. 通过 HTTP API 调用（备用）
 */
async function performDistillation(request: DistillationRequest): Promise<DistillationResult> {
  const { source_content, target_layer, author_agent } = request;

  // 构建蒸馏提示
  const distillPrompt = `## 源材料

**标题**: ${source_content.context || '无'}

**问题/任务**:
${source_content.question || '无'}

**解决方案/回答**:
${source_content.answer || '无'}

**标签**: ${(source_content.tags || []).join(', ')}

---

请从上述成功案例中提取可复用的技能。

${target_layer ? `目标层级：${target_layer}` : '请自动判断最合适的层级。'}

输出 JSON 格式的技能定义。`;

  try {
    let content: string;

    // 方式1: 尝试通过 HTTP API 调用
    try {
      const response = await fetch('http://localhost:3000/api/brain-router/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: DISTILLER_CONFIG.model,
          system: DISTILLER_SYSTEM_PROMPT,
          prompt: distillPrompt
        }),
        signal: AbortSignal.timeout(5000)  // 5秒超时
      });

      if (response.ok) {
        const data = await response.json();
        content = data.content || data.response || '';
      } else {
        throw new Error('HTTP API not available');
      }
    } catch {
      // 方式2: 返回模拟蒸馏结果（需要手动调用 MCP）
      // 这种情况下，我们创建一个基础技能结构，由 Solar 手动完善
      console.log('\n⚠️  Brain Router API 未运行，使用基础蒸馏模式');
      console.log('   完整蒸馏需要调用审判官 (deepseek-r1)');
      console.log('   建议手动运行蒸馏命令后审核\n');

      return createBasicDistillationResult(request);
    }

    // 解析 JSON
    const skillData = extractJsonFromResponse(content);

    if (!skillData || skillData.confidence === 0) {
      return {
        success: false,
        error: skillData?.error || '无法提取有效技能',
        confidence: skillData?.confidence || 0
      };
    }

    // 5. 创建技能
    const skill: Partial<Skill> = {
      name: skillData.name,
      description: skillData.description,
      skill_type: 'template',
      layer: skillData.layer || target_layer || 'domain',
      scope: 'task_specific',
      status: 'pending_review',  // P0: 所有技能需要人工审核
      llm_prompt_template: skillData.llm_prompt_template,
      parameters: skillData.parameters || [],
      trigger_keywords: skillData.trigger_keywords || [],
      applicable_contexts: skillData.applicable_contexts || [],
      preconditions: skillData.preconditions || [],
      tags: [...(skillData.tags || []), ...(source_content.tags || [])],
      source: 'distilled',
      source_ref: `favorite:${request.source_id}`,
      author_agent: author_agent || 'solar',
      skill_metadata: {
        distillation_confidence: skillData.confidence,
        distillation_model: DISTILLER_CONFIG.model,
        distillation_timestamp: new Date().toISOString()
      }
    };

    const skillId = createSkill(skill);

    return {
      success: true,
      skill: { ...skill, skill_id: skillId },
      confidence: skillData.confidence
    };

  } catch (error) {
    return {
      success: false,
      error: `Distillation failed: ${error instanceof Error ? error.message : String(error)}`,
      confidence: 0
    };
  }
}

/**
 * 从响应中提取 JSON
 */
function extractJsonFromResponse(content: string): Record<string, unknown> | null {
  // 尝试直接解析
  try {
    return JSON.parse(content);
  } catch {}

  // 尝试提取代码块中的 JSON
  const jsonMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    try {
      return JSON.parse(jsonMatch[1].trim());
    } catch {}
  }

  // 尝试提取 { } 之间的内容
  const braceMatch = content.match(/\{[\s\S]*\}/);
  if (braceMatch) {
    try {
      return JSON.parse(braceMatch[0]);
    } catch {}
  }

  return null;
}

/**
 * 手动创建技能（不通过蒸馏）
 */
export function createSkillManually(skill: Partial<Skill>): string {
  return createSkill({
    ...skill,
    status: skill.status || 'pending_review',
    source: skill.source || 'manual',
    validated: false
  });
}

/**
 * 创建基础蒸馏结果（当 Brain Router 不可用时）
 */
function createBasicDistillationResult(request: DistillationRequest): DistillationResult {
  const { source_content, target_layer, author_agent } = request;

  // 从标题/问题中提取技能名称
  const title = source_content.context || source_content.question?.slice(0, 50) || '未命名技能';
  const name = title.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, '_').slice(0, 30);

  // 创建基础技能结构
  const skill: Partial<Skill> = {
    name: `待完善: ${name}`,
    description: source_content.question?.slice(0, 200) || '需要完善描述',
    skill_type: 'template',
    layer: target_layer || 'domain',
    scope: 'task_specific',
    status: 'pending_review',
    llm_prompt_template: `# 待完善的技能模板

原始问题:
${source_content.question || '无'}

原始回答摘要:
${source_content.answer?.slice(0, 500) || '无'}

---
请 Solar 手动完善此技能模板。
`,
    tags: [...(source_content.tags || []), 'needs-refinement'],
    source: 'distilled_basic',
    source_ref: `favorite:${request.source_id}`,
    author_agent: author_agent || 'solar',
    skill_metadata: {
      distillation_mode: 'basic',
      distillation_timestamp: new Date().toISOString(),
      needs_refinement: true
    }
  };

  const skillId = createSkill(skill);

  return {
    success: true,
    skill: { ...skill, skill_id: skillId },
    confidence: 0.3  // 低置信度，需要人工审核
  };
}

/**
 * 批量蒸馏收藏夹
 */
export async function batchDistillFavorites(
  options: {
    min_importance?: number;
    limit?: number;
    layer?: SkillLayer;
  } = {}
): Promise<{ success: number; failed: number; skills: string[] }> {
  // 获取符合条件的收藏
  const db = new Bun.Database(`${process.env.HOME}/.solar/solar.db`);

  const minImportance = options.min_importance || 7;
  const limit = options.limit || 10;

  const favorites = db.prepare(`
    SELECT favorite_id
    FROM sys_favorites
    WHERE importance >= ?
    ORDER BY importance DESC, created_at DESC
    LIMIT ?
  `).all(minImportance, limit) as { favorite_id: number }[];

  db.close();

  const results = {
    success: 0,
    failed: 0,
    skills: [] as string[]
  };

  for (const fav of favorites) {
    const result = await distillFromFavorite(fav.favorite_id, { layer: options.layer });

    if (result.success && result.skill?.skill_id) {
      results.success++;
      results.skills.push(result.skill.skill_id);
    } else {
      results.failed++;
    }

    // 避免频繁调用
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  return results;
}
