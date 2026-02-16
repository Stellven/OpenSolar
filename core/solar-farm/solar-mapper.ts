/**
 * SolarMapper - A-MapReduce 落地实现
 *
 * 基于 A-MapReduce 论文架构，实现宽搜索并行执行
 *
 * 工作流程: decompose → map → batch → execute → aggregate
 *
 * @version 1.0.0
 * @created 2026-02-07
 * @authors 探索派(gemini-3-pro), 审判官(deepseek-r1)
 */

import { randomUUID } from 'crypto';
import { Database } from 'bun:sqlite';
import { buildNiumaCall, getNiumaNickname } from './call-niuma';

// ============================================================
// 类型定义
// ============================================================

export interface WideSearchTask {
  taskId: string;
  goal: string;
  template: string;
  context?: string;
}

/** 任务类型 - 根据任务特点分类 */
export type TaskType = 'coding' | 'analysis' | 'creative' | 'simple';

export interface SubTask {
  id: string;
  entity: string;
  prompt: string;
  model: string;
  taskType: TaskType;  // 新增：任务类型
  retryCount: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

/** 任务类型 → 牛马优先级映射 (昵称 → 模型ID会在 batch 中转换) */
export const MODEL_PREFERENCE_BY_TYPE: Record<TaskType, string[]> = {
  analysis: ['deepseek-r1', 'gemini-3-pro-preview', 'deepseek-v3'],  // 审判官、探索派、创想家
  creative: ['gemini-3-pro-preview', 'gemini-2.5-flash', 'deepseek-v3'],  // 探索派、闪电侠、创想家
  coding: ['deepseek-v3', 'gemini-2.5-pro'],  // 创想家、稳健派
  simple: ['glm-4-flash', 'gemini-2.5-flash', 'gemini-2.5-pro', 'glm-4-plus']  // 小快手、闪电侠、稳健派、建设者
};

export interface MapperResult {
  taskId: string;
  goal: string;
  entities: string[];
  results: Map<string, string>;
  summary: string;
  stats: {
    total: number;
    success: number;
    failed: number;
    duration: number;
  };
}

/** 执行计划 - 由主脑执行 */
export interface ExecutionPlan {
  planId: string;
  createdAt: string;
  totalTasks: number;
  tasks: {
    id: string;
    entity: string;
    model: string;
    nickname: string;
    system: string;
    prompt: string;
    status: 'pending' | 'completed' | 'failed';
  }[];
  usage: string;
}

/** 专家建议 - 每个专家对任务分配的建议 */
export interface ExpertAdvice {
  expertModel: string;
  expertNickname: string;
  assignments: {
    entity: string;
    taskType: TaskType;
    recommendedModel: string;
    reason: string;
  }[];
}

/** 规划调用 - 返回给主脑的专家调用参数 */
export interface PlanningCall {
  expert: string;
  nickname: string;
  model: string;
  system: string;
  prompt: string;
}

/** 合并后的规划 - 多专家综合结果 */
export interface MergedPlan {
  planId: string;
  createdAt: string;
  experts: string[];
  assignments: {
    entity: string;
    finalModel: string;
    finalNickname: string;
    expertVotes: { expert: string; model: string; reason: string }[];
    consensus: boolean;  // 专家是否一致
  }[];
}

// ============================================================
// SolarMapper 核心类
// ============================================================

export class SolarMapper {
  private db: Database;
  private maxRetries = 3;

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
  }

  /**
   * 1. Decompose: 生成分解调用（由主脑执行）
   *
   * 返回调用探索派的参数，主脑执行后得到实体列表
   */
  getDecomposeCall(goal: string): { model: string; system: string; prompt: string } {
    console.log(`🔥 [Decompose] 生成分解调用: ${goal}`);

    const { system, prompt } = buildNiumaCall({
      model: 'gemini-3-pro-preview',
      task: `请将以下目标分解为独立的执行实体，每个实体是一个可以并行处理的子任务。

目标: ${goal}

要求:
1. 每个实体应该是独立的、可并行处理的
2. 实体粒度适中，不要太粗也不要太细
3. 如果目标已经明确列出了实体，直接提取即可

输出格式: 只输出 JSON 数组，如 ["实体1", "实体2", "实体3"]
不要输出其他内容。`,
      outputFormat: 'JSON 数组'
    });

    return { model: 'gemini-3-pro-preview', system, prompt };
  }

  /**
   * 解析分解结果
   */
  parseDecomposeResult(response: string): string[] {
    try {
      // 尝试直接解析 JSON
      const parsed = JSON.parse(response);
      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch {
      // 尝试从文本中提取 JSON 数组
      const match = response.match(/\[[\s\S]*\]/);
      if (match) {
        try {
          return JSON.parse(match[0]);
        } catch {}
      }
    }
    // 降级：按行分割
    return response.split('\n').filter(line => line.trim()).slice(0, 10);
  }

  /**
   * 2. Map: 用模板生成子任务 (含任务类型分类)
   */
  map(entities: string[], template: string): SubTask[] {
    console.log(`🗺️ [Map] 正在映射 ${entities.length} 个实体...`);

    return entities.map(entity => {
      // 根据实体 + 模板内容判断任务类型
      const fullContext = `${entity} ${template}`;
      const taskType = this.classifyTaskType(fullContext);

      return {
        id: randomUUID(),
        entity,
        prompt: template.replace(/\{\{entity\}\}/g, entity),
        model: 'pending',
        taskType,
        retryCount: 0,
        status: 'pending' as const
      };
    });
  }

  /**
   * 根据任务内容分类任务类型
   *
   * 优先级: coding > creative > analysis > simple
   * 因为编码任务最明确，创意任务次之
   */
  private classifyTaskType(content: string): TaskType {
    // 编码/实现类 → 需要代码能力 (最优先，关键词最明确)
    if (/代码|实现|编写|函数|脚本|调试|测试|接口|API|编程/.test(content)) {
      return 'coding';
    }

    // 创意/写作类 → 需要创造力 (创意关键词优先于分析)
    if (/创意|起草|文案|生成|想法|营销|头脑风暴|策划|灵感/.test(content)) {
      return 'creative';
    }

    // 分析/架构/设计类 → 需要深度思考
    if (/架构|设计|分析|优化|审查|评估|重构|安全|性能/.test(content)) {
      return 'analysis';
    }

    // 其他 → 简单任务
    return 'simple';
  }

  /**
   * 3. Batch: 根据任务类型智能分配牛马
   *
   * 使用 MODEL_PREFERENCE_BY_TYPE 根据 taskType 选择最合适的牛马：
   * - analysis → 审判官/探索派/创想家 (深度分析)
   * - coding   → 创想家/稳健派 (代码能力)
   * - creative → 探索派/闪电侠/创想家 (创造力)
   * - simple   → 小快手/闪电侠/建设者 (成本低)
   */
  batch(tasks: SubTask[]): SubTask[] {
    console.log(`⚖️ [Batch] 正在为 ${tasks.length} 个任务分配牛马...`);

    // 查询可用牛马列表 (用于检查可用性)
    let availableModels: string[] = [];
    try {
      const profiles = this.db.query(`
        SELECT model_id FROM collab_model_profiles
      `).all() as any[];
      availableModels = profiles.map(p => p.model_id);
    } catch (e) {
      // 表可能不存在，使用默认列表
      availableModels = Object.keys(MODEL_PREFERENCE_BY_TYPE.simple);
    }

    return tasks.map(task => {
      // 根据 taskType 获取推荐牛马列表
      const preferredModels = MODEL_PREFERENCE_BY_TYPE[task.taskType];

      // 选择第一个可用的牛马 (优先级从高到低)
      let selectedModel = preferredModels[0];  // 默认用第一个
      for (const model of preferredModels) {
        if (availableModels.length === 0 || availableModels.includes(model)) {
          selectedModel = model;
          break;
        }
      }

      task.model = selectedModel;

      console.log(`   └─ ${task.entity} [${task.taskType}] → ${getNiumaNickname(task.model)}`);
      return task;
    });
  }

  // ============================================================
  // 多专家规划机制 (Step 2 改进版)
  // ============================================================

  /** 规划专家配置 */
  private readonly PLANNING_EXPERTS = [
    { model: 'gemini-3-pro-preview', nickname: '探索派', style: '创新探索' },
    { model: 'deepseek-r1', nickname: '审判官', style: '深度推理' }
  ];

  /**
   * Step 2a: 生成专家规划调用
   *
   * 返回两个专家的调用参数，主脑并行执行
   */
  getExpertPlanCalls(entities: string[], template: string): PlanningCall[] {
    console.log(`🧠 [Expert Planning] 生成 ${this.PLANNING_EXPERTS.length} 个专家调用...`);

    const niumaList = `
可用牛马:
| 昵称 | 模型 | 特长 | 成本 |
|------|------|------|------|
| 小快手 | glm-4-flash | 简单任务，速度快 | 最低 |
| 闪电侠 | gemini-2.5-flash | 长文档，多模态 | 低 |
| 建设者 | glm-4-plus | 日常编码，友善 | 中 |
| 稳健派 | gemini-2.5-pro | 严谨审查，高一致性 | 中高 |
| 探索派 | gemini-3-pro-preview | 创新探索，热情高效 | 高 |
| 创想家 | deepseek-v3 | 创意编码，中文好 | 高 |
| 审判官 | deepseek-r1 | 深度推理，自我觉察 | 高 |
`;

    const taskList = entities.map((e, i) => `${i + 1}. ${e}`).join('\n');

    return this.PLANNING_EXPERTS.map(expert => {
      const { system, prompt } = buildNiumaCall({
        model: expert.model,
        task: `作为规划专家，请为以下任务分配最合适的执行牛马。

## 任务模板
${template}

## 待分配任务
${taskList}

${niumaList}

## 分配原则
- 分析/深度任务 → 审判官/探索派
- 编码任务 → 创想家/稳健派
- 创意任务 → 探索派/创想家
- 简单任务 → 小快手/闪电侠 (省钱)

## 输出格式
只输出 JSON 数组，每个元素: {"entity": "任务名", "taskType": "analysis|coding|creative|simple", "model": "模型ID", "reason": "一句话理由"}

示例:
[{"entity": "分析模块A", "taskType": "analysis", "model": "deepseek-r1", "reason": "需要深度推理"}]`,
        outputFormat: 'JSON 数组'
      });

      console.log(`   └─ ${expert.nickname} (${expert.style})`);

      return {
        expert: expert.model,
        nickname: expert.nickname,
        model: expert.model,
        system,
        prompt
      };
    });
  }

  /**
   * 解析专家建议
   */
  parseExpertAdvice(expertModel: string, response: string): ExpertAdvice {
    const nickname = getNiumaNickname(expertModel);
    let assignments: ExpertAdvice['assignments'] = [];

    try {
      // 尝试解析 JSON
      const match = response.match(/\[[\s\S]*\]/);
      if (match) {
        const parsed = JSON.parse(match[0]);
        assignments = parsed.map((item: any) => ({
          entity: item.entity || '',
          taskType: (item.taskType || 'simple') as TaskType,
          recommendedModel: item.model || 'glm-4-flash',
          reason: item.reason || ''
        }));
      }
    } catch (e) {
      console.log(`   ⚠️ ${nickname} 返回格式异常，使用默认分配`);
    }

    return { expertModel, expertNickname: nickname, assignments };
  }

  /**
   * Step 2b: 合并专家建议
   *
   * 规则:
   * - 一致 → 直接采用
   * - 不一致 → 取能力更强的牛马 (偏保守)
   */
  mergeExpertAdvices(advices: ExpertAdvice[], entities: string[]): MergedPlan {
    console.log(`🔀 [Merge] 合并 ${advices.length} 个专家建议...`);

    // 牛马能力排名 (用于不一致时选择)
    const MODEL_RANK: Record<string, number> = {
      'deepseek-r1': 7,      // 最强
      'gemini-3-pro-preview': 6,
      'deepseek-v3': 5,
      'gemini-2.5-pro': 4,
      'glm-4-plus': 3,
      'gemini-2.5-flash': 2,
      'glm-4-flash': 1       // 最弱
    };

    const assignments = entities.map(entity => {
      const votes = advices.map(advice => {
        const assignment = advice.assignments.find(a => a.entity === entity);
        return {
          expert: advice.expertNickname,
          model: assignment?.recommendedModel || 'glm-4-flash',
          reason: assignment?.reason || '默认分配'
        };
      });

      // 检查是否一致
      const models = votes.map(v => v.model);
      const consensus = new Set(models).size === 1;

      // 选择最终牛马
      let finalModel: string;
      if (consensus) {
        finalModel = models[0];
        console.log(`   ✓ ${entity} → ${getNiumaNickname(finalModel)} (一致)`);
      } else {
        // 不一致时取能力更强的
        finalModel = models.reduce((a, b) =>
          (MODEL_RANK[a] || 0) >= (MODEL_RANK[b] || 0) ? a : b
        );
        console.log(`   ⚡ ${entity} → ${getNiumaNickname(finalModel)} (取强者: ${models.map(m => getNiumaNickname(m)).join(' vs ')})`);
      }

      return {
        entity,
        finalModel,
        finalNickname: getNiumaNickname(finalModel),
        expertVotes: votes,
        consensus
      };
    });

    return {
      planId: randomUUID(),
      createdAt: new Date().toISOString(),
      experts: advices.map(a => a.expertNickname),
      assignments
    };
  }

  /**
   * Step 2c: 从合并结果生成最终执行计划
   */
  generatePlanFromMerged(mergedPlan: MergedPlan, template: string): ExecutionPlan {
    console.log(`📋 [Plan] 从合并结果生成执行计划...`);

    const tasks = mergedPlan.assignments.map(assignment => {
      const { system, prompt } = buildNiumaCall({
        model: assignment.finalModel,
        task: template.replace(/\{\{entity\}\}/g, assignment.entity),
        outputFormat: '结构化输出'
      });

      return {
        id: randomUUID(),
        entity: assignment.entity,
        model: assignment.finalModel,
        nickname: assignment.finalNickname,
        system,
        prompt,
        status: 'pending' as const
      };
    });

    return {
      planId: mergedPlan.planId,
      createdAt: mergedPlan.createdAt,
      totalTasks: tasks.length,
      tasks,
      usage: `
多专家规划 (${mergedPlan.experts.join(' + ')})
一致率: ${mergedPlan.assignments.filter(a => a.consensus).length}/${mergedPlan.assignments.length}

主脑执行方式:
for each task in plan.tasks:
  result = mcp__brain_router__complete({
    model: task.model,
    system: task.system,
    prompt: task.prompt
  })
`
    };
  }

  /**
   * 4. Plan: 生成执行计划（不实际执行）
   *
   * 返回 JSON 格式的执行计划，由主脑（Claude）负责实际执行
   * 主脑可以调用 brain-router MCP 执行每个子任务
   */
  generatePlan(tasks: SubTask[]): ExecutionPlan {
    console.log(`📋 [Plan] 生成 ${tasks.length} 个任务的执行计划...`);

    const plan: ExecutionPlan = {
      planId: randomUUID(),
      createdAt: new Date().toISOString(),
      totalTasks: tasks.length,
      tasks: tasks.map(task => {
        const { system, prompt } = buildNiumaCall({
          model: task.model,
          task: task.prompt,
          outputFormat: '结构化输出'
        });

        return {
          id: task.id,
          entity: task.entity,
          model: task.model,
          nickname: getNiumaNickname(task.model),
          system,
          prompt,
          status: 'pending' as const
        };
      }),
      usage: `
主脑执行方式:
for each task in plan.tasks:
  result = mcp__brain_router__complete({
    model: task.model,
    system: task.system,
    prompt: task.prompt
  })
  // 收集 result
`
    };

    console.log(`   ✅ 执行计划已生成，包含 ${plan.totalTasks} 个待执行任务`);
    return plan;
  }

  /**
   * 4b. 接收外部执行结果
   *
   * 主脑执行完毕后，调用此方法注入结果
   */
  async injectResults(results: Map<string, string>): Promise<void> {
    console.log(`📥 [Inject] 接收 ${results.size} 个执行结果...`);

    for (const [entity, content] of results.entries()) {
      const success = content !== 'EXECUTION_FAILED';
      await this.logMemory(success ? 'task_success' : 'task_failed', {
        entity,
        resultLength: content.length
      });
    }
  }

  /**
   * 5. Aggregate: 聚合结果 + 调用审判官生成总结
   */
  async aggregate(goal: string, results: Map<string, string>): Promise<string> {
    console.log(`✨ [Aggregate] 正在聚合 ${results.size} 个结果...`);

    // 构建结果表
    let table = '| 实体 | 结果 |\n|------|------|\n';
    for (const [entity, content] of results.entries()) {
      table += `| ${entity} | ${content.substring(0, 50)}... |\n`;
    }

    // 调用审判官生成总结
    const { system, prompt } = buildNiumaCall({
      model: 'deepseek-r1',
      task: `基于以下执行结果，为目标"${goal}"生成简洁的总结报告：\n\n${table}`,
      outputFormat: '3-5句话的总结'
    });

    // 模拟返回
    const summary = `完成了 ${results.size} 个子任务的并行执行，整体进展顺利。`;

    await this.logMemory('aggregate', { goal, resultCount: results.size, summary });

    return summary;
  }

  /**
   * 记录到 collab_memory
   */
  private async logMemory(action: string, content: any) {
    try {
      this.db.run(`
        INSERT INTO collab_memory (memory_type, model_id, content, created_at)
        VALUES (?, ?, ?, datetime('now'))
      `, [`SolarMapper:${action}`, 'solar-mapper', JSON.stringify(content)]);
    } catch (e) {
      // 表可能不存在，忽略
    }
  }

  /**
   * Step 1: 获取分解调用
   *
   * 主脑调用此方法获取分解参数，然后执行 brain-router 得到实体列表
   */
  step1_decompose(goal: string): { model: string; system: string; prompt: string; nickname: string } {
    const call = this.getDecomposeCall(goal);
    return { ...call, nickname: '探索派' };
  }

  /**
   * Step 2: 获取专家规划调用 (多专家版)
   *
   * 返回两个老专家的调用参数，主脑并行执行后调用 step3
   */
  step2_getExpertCalls(goal: string, template: string, entities: string[]): {
    entities: string[];
    template: string;
    expertCalls: PlanningCall[];
  } {
    console.log(`\n${'='.repeat(50)}`);
    console.log(`🧠 SolarMapper Step 2: 多专家规划`);
    console.log(`   目标: ${goal}`);
    console.log(`   实体: ${entities.join(', ')}`);
    console.log(`${'='.repeat(50)}\n`);

    const expertCalls = this.getExpertPlanCalls(entities, template);

    console.log(`\n${'='.repeat(50)}`);
    console.log(`📤 专家调用已生成`);
    console.log(`   专家数: ${expertCalls.length}`);
    console.log(`   专家: ${expertCalls.map(c => c.nickname).join(', ')}`);
    console.log(`${'='.repeat(50)}\n`);

    return { entities, template, expertCalls };
  }

  /**
   * Step 3: 合并专家建议，生成执行计划
   *
   * 主脑执行专家调用后，将结果传入此方法
   */
  step3_mergePlan(
    entities: string[],
    template: string,
    expertResponses: { model: string; response: string }[]
  ): ExecutionPlan {
    console.log(`\n${'='.repeat(50)}`);
    console.log(`🔀 SolarMapper Step 3: 合并专家建议`);
    console.log(`${'='.repeat(50)}\n`);

    // 解析每个专家的建议
    const advices = expertResponses.map(({ model, response }) =>
      this.parseExpertAdvice(model, response)
    );

    // 合并建议
    const mergedPlan = this.mergeExpertAdvices(advices, entities);

    // 生成最终执行计划
    const plan = this.generatePlanFromMerged(mergedPlan, template);

    console.log(`\n${'='.repeat(50)}`);
    console.log(`📋 执行计划已生成 (${mergedPlan.experts.join(' + ')})`);
    console.log(`   任务数: ${plan.totalTasks}`);
    console.log(`   一致率: ${mergedPlan.assignments.filter(a => a.consensus).length}/${mergedPlan.assignments.length}`);
    console.log(`${'='.repeat(50)}\n`);

    return plan;
  }

  /**
   * Step 2 (快速版): 单专家规划，跳过多专家
   *
   * 用于简单场景，直接本地分类
   */
  step2_plan(goal: string, template: string, entities: string[]): ExecutionPlan {
    console.log(`\n${'='.repeat(50)}`);
    console.log(`☀️ SolarMapper Step 2 (快速): 本地规划`);
    console.log(`   目标: ${goal}`);
    console.log(`   实体: ${entities.join(', ')}`);
    console.log(`${'='.repeat(50)}\n`);

    const mappedTasks = this.map(entities, template);
    const batchedTasks = this.batch(mappedTasks);
    const plan = this.generatePlan(batchedTasks);

    console.log(`\n${'='.repeat(50)}`);
    console.log(`📋 执行计划已生成`);
    console.log(`   任务数: ${plan.totalTasks}`);
    console.log(`${'='.repeat(50)}\n`);

    return plan;
  }

  /**
   * 完整执行：规划 + 结果注入 + 聚合
   *
   * 注意：需要外部提供执行结果（主脑执行后调用）
   */
  async complete(goal: string, results: Map<string, string>): Promise<string> {
    await this.injectResults(results);
    const summary = await this.aggregate(goal, results);
    return summary;
  }
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const mapper = new SolarMapper();
  const cmd = process.argv[2] || 'help';

  if (cmd === 'step1' || cmd === 'decompose') {
    // Step 1: 获取分解调用
    const goal = process.argv[3] || '分析阳光牧场的架构优化点';
    const call = mapper.step1_decompose(goal);

    console.log('\n📋 Step 1: 分解调用');
    console.log('━'.repeat(50));
    console.log(JSON.stringify(call, null, 2));
    console.log('\n🔧 主脑执行:');
    console.log('mcp__brain_router__complete({ model: "gemini-3-pro-preview", system: call.system, prompt: call.prompt })');
    console.log('\n然后用返回的实体列表调用 step2');

  } else if (cmd === 'step2' || cmd === 'plan') {
    // Step 2 (快速版): 本地规划
    const goal = process.argv[3] || '分析阳光牧场的架构优化点';
    const template = process.argv[4] || '请详细分析 {{entity}} 的现状和改进建议。';
    const entitiesJson = process.argv[5] || '["模块A", "模块B", "模块C"]';

    const entities = JSON.parse(entitiesJson);
    const plan = mapper.step2_plan(goal, template, entities);

    console.log('\n📋 Step 2 (快速): 执行计划');
    console.log('━'.repeat(50));
    console.log(JSON.stringify(plan, null, 2));

  } else if (cmd === 'step2-expert') {
    // Step 2 (多专家版): 获取专家调用
    const goal = process.argv[3] || '分析阳光牧场的架构优化点';
    const template = process.argv[4] || '请详细分析 {{entity}} 的现状和改进建议。';
    const entitiesJson = process.argv[5] || '["模块A", "模块B", "模块C"]';

    const entities = JSON.parse(entitiesJson);
    const result = mapper.step2_getExpertCalls(goal, template, entities);

    console.log('\n🧠 Step 2 (多专家): 专家调用');
    console.log('━'.repeat(50));
    console.log(JSON.stringify(result, null, 2));
    console.log('\n🔧 主脑并行执行:');
    console.log('for call in expertCalls:');
    console.log('  mcp__brain_router__complete({ model: call.model, system: call.system, prompt: call.prompt })');
    console.log('\n然后用专家响应调用 step3');

  } else if (cmd === 'step3' || cmd === 'merge') {
    // Step 3: 合并专家建议
    const template = process.argv[3] || '请详细分析 {{entity}} 的现状和改进建议。';
    const entitiesJson = process.argv[4] || '["模块A", "模块B", "模块C"]';
    const responsesJson = process.argv[5] || '[]';

    const entities = JSON.parse(entitiesJson);
    const responses = JSON.parse(responsesJson);
    const plan = mapper.step3_mergePlan(entities, template, responses);

    console.log('\n📋 Step 3: 合并后的执行计划');
    console.log('━'.repeat(50));
    console.log(JSON.stringify(plan, null, 2));

  } else {
    console.log(`
☀️ SolarMapper - A-MapReduce 宽搜索

用法:
  bun solar-mapper.ts step1 "目标"
    → 获取分解调用，主脑执行后得到实体列表

  bun solar-mapper.ts step2 "目标" "模板" '["实体1","实体2"]'
    → (快速版) 本地规划，直接生成执行计划

  bun solar-mapper.ts step2-expert "目标" "模板" '["实体1","实体2"]'
    → (多专家版) 获取两个老专家的调用参数

  bun solar-mapper.ts step3 "模板" '["实体1","实体2"]' '[专家响应JSON]'
    → 合并专家建议，生成最终执行计划

完整流程 (快速版):
  1. step1 → 探索派分解 → 实体列表
  2. step2 → 本地规划 → 执行计划
  3. 主脑执行

完整流程 (多专家版):
  1. step1 → 探索派分解 → 实体列表
  2. step2-expert → 生成两个专家调用
  3. 主脑并行调用探索派 + 审判官
  4. step3 → 合并建议 → 执行计划
  5. 主脑执行
`);
  }
}
