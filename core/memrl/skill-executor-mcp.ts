/**
 * MEMRL Skill Executor MCP Adapter
 *
 * P2 集成组件
 * 职责: 将 Skill Executor 接入 brain-router MCP
 *
 * 使用方式:
 * 1. 在 Claude Code 中: 使用 MCP 工具直接调用
 * 2. 独立运行: 通过 HTTP 调用 brain-router 服务
 */

import { SkillRetriever, RetrievedSkill } from './skill-retriever';
import { Database } from 'bun:sqlite';

// 执行结果
export interface SkillExecutionResult {
  success: boolean;
  skillId: string;
  skillName: string;
  output: string;
  executionTimeMs: number;
  modelUsed: string;
  error?: string;
}

// MCP 调用器类型 (由外部注入)
export type MCPCaller = (params: {
  model: string;
  system?: string;
  prompt: string;
  task_type?: string;
}) => Promise<{ content: string }>;

/**
 * Skill Executor MCP 适配器
 *
 * 优先使用 MCP 工具，回退到 HTTP
 */
export class SkillExecutorMCP {
  private retriever: SkillRetriever;
  private db: Database;
  private mcpCaller: MCPCaller | null = null;
  private httpEndpoint: string;
  private defaultModel: string;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    options?: {
      mcpCaller?: MCPCaller;
      httpEndpoint?: string;
      defaultModel?: string;
    }
  ) {
    this.db = new Database(dbPath);
    this.retriever = new SkillRetriever(dbPath);
    this.mcpCaller = options?.mcpCaller || null;
    this.httpEndpoint = options?.httpEndpoint || 'http://localhost:3000/api/brain-router/complete';
    this.defaultModel = options?.defaultModel || 'glm-5';
  }

  /**
   * 设置 MCP 调用器 (从 Claude Code 注入)
   */
  setMCPCaller(caller: MCPCaller): void {
    this.mcpCaller = caller;
  }

  /**
   * 根据用户输入自动选择并执行技能
   *
   * @param userInput 用户输入
   * @param context 可选上下文
   * @param preferredModel 可选的模型偏好
   */
  async autoExecute(
    userInput: string,
    context?: string,
    preferredModel?: string
  ): Promise<SkillExecutionResult | null> {
    const startTime = Date.now();

    // 1. 检索相关技能
    const skills = this.retriever.retrieve(userInput);

    if (skills.length === 0) {
      return null;
    }

    // 2. 选择最佳技能
    const bestSkill = skills[0];

    // 3. 构建 Prompt
    const prompt = this.buildPrompt(bestSkill, userInput, context);

    // 4. 调用 LLM
    const model = preferredModel || this.selectModel(bestSkill);

    try {
      const output = await this.callLLM(model, prompt, bestSkill.llm_prompt_template);

      // 5. 记录成功
      this.retriever.recordSuccess(bestSkill.skill_id, Date.now() - startTime);

      return {
        success: true,
        skillId: bestSkill.skill_id,
        skillName: bestSkill.name,
        output,
        executionTimeMs: Date.now() - startTime,
        modelUsed: model
      };
    } catch (error) {
      // 6. 记录失败
      this.retriever.recordFailure(bestSkill.skill_id);

      return {
        success: false,
        skillId: bestSkill.skill_id,
        skillName: bestSkill.name,
        output: '',
        executionTimeMs: Date.now() - startTime,
        modelUsed: model,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * 执行指定技能
   */
  async execute(
    skillId: string,
    params: Record<string, string>,
    context?: string,
    preferredModel?: string
  ): Promise<SkillExecutionResult> {
    const startTime = Date.now();

    // 1. 获取技能详情
    const skill = this.retriever.getSkillById(skillId);

    if (!skill) {
      return {
        success: false,
        skillId,
        skillName: skillId,
        output: '',
        executionTimeMs: 0,
        modelUsed: '',
        error: `技能不存在: ${skillId}`
      };
    }

    // 2. 构建 Prompt
    let prompt = skill.llm_prompt_template || '';

    // 替换参数
    for (const [key, value] of Object.entries(params)) {
      prompt = prompt.replace(new RegExp(`{{${key}}}`, 'g'), value);
    }

    if (context) {
      prompt += `\n\n上下文:\n${context}`;
    }

    // 3. 调用 LLM
    const model = preferredModel || this.selectModel(skill);

    try {
      const output = await this.callLLM(model, prompt, skill.llm_prompt_template);

      this.retriever.recordSuccess(skill.skill_id, Date.now() - startTime);

      return {
        success: true,
        skillId: skill.skill_id,
        skillName: skill.name,
        output,
        executionTimeMs: Date.now() - startTime,
        modelUsed: model
      };
    } catch (error) {
      this.retriever.recordFailure(skill.skill_id);

      return {
        success: false,
        skillId: skill.skill_id,
        skillName: skill.name,
        output: '',
        executionTimeMs: Date.now() - startTime,
        modelUsed: model,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * 构建 Prompt
   */
  private buildPrompt(
    skill: RetrievedSkill,
    userInput: string,
    context?: string
  ): string {
    let prompt = skill.llm_prompt_template || '';

    // 替换默认参数
    prompt = prompt.replace(/{{input}}/g, userInput);
    prompt = prompt.replace(/{{user_input}}/g, userInput);

    if (context) {
      prompt += `\n\n上下文:\n${context}`;
    }

    return prompt;
  }

  /**
   * 根据技能类型选择模型
   */
  private selectModel(skill: RetrievedSkill | any): string {
    // 根据技能类型选择合适的模型
    switch (skill.skill_type) {
      case 'workflow':
        return 'gemini-2.5-pro';  // 复杂工作流用强模型
      case 'api_call':
        return 'glm-4-flash';    // API 调用用快模型
      case 'template':
      default:
        // 根据复杂度选择
        if (skill.q_value >= 0.8) {
          return 'glm-5';   // 高成功率用标准模型
        }
        return 'glm-4-flash';   // 低成功率用快模型试错
    }
  }

  /**
   * 调用 LLM
   *
   * 优先使用 MCP，回退到 HTTP
   */
  private async callLLM(
    model: string,
    prompt: string,
    systemPrompt?: string
  ): Promise<string> {
    // 1. 尝试使用 MCP 调用器
    if (this.mcpCaller) {
      try {
        const result = await this.mcpCaller({
          model,
          system: systemPrompt,
          prompt,
          task_type: 'coding'
        });
        return result.content;
      } catch (error) {
        console.warn('[SkillExecutor] MCP 调用失败，回退到 HTTP:', error);
      }
    }

    // 2. 回退到 HTTP 调用
    const response = await fetch(this.httpEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model,
        system: systemPrompt,
        prompt,
        task_type: 'coding'
      })
    });

    if (!response.ok) {
      throw new Error(`LLM 调用失败: ${response.status}`);
    }

    const data = await response.json();
    return data.content || data.response || '';
  }

  /**
   * 搜索技能
   */
  searchSkills(query: string): RetrievedSkill[] {
    return this.retriever.retrieve(query);
  }

  /**
   * 获取统计
   */
  getStats(): {
    totalSkills: number;
    avgQValue: number;
    topSkills: RetrievedSkill[];
  } {
    const stats = this.retriever.getStats();
    const topSkills = this.retriever.retrieve('');  // 空查询返回按 Q 值排序的列表

    return {
      totalSkills: stats.totalSkills,
      avgQValue: stats.avgQValue,
      topSkills: topSkills.slice(0, 5)
    };
  }

  close(): void {
    this.retriever.close();
    this.db.close();
  }
}

// MCP 注入器 (在 Claude Code 中使用)
export function createMCPCaller(): MCPCaller | null {
  // 在 Claude Code 上下文中，这个函数会被替换为实际的 MCP 调用
  // 返回 null 表示需要使用 HTTP 回退
  return null;
}

// CLI 入口
if (import.meta.main) {
  const executor = new SkillExecutorMCP();

  const command = process.argv[2] || 'stats';
  const query = process.argv[3] || '';

  if (command === 'stats') {
    console.log('📊 Skill Executor MCP 统计\n');
    const stats = executor.getStats();
    console.log(`总技能数: ${stats.totalSkills}`);
    console.log(`平均 Q: ${stats.avgQValue.toFixed(3)}`);
    console.log('\nTop 5 技能:');
    for (const s of stats.topSkills) {
      console.log(`  [Q=${s.q_value.toFixed(2)}] ${s.name}`);
    }
  }

  if (command === 'search' && query) {
    console.log(`🔍 搜索技能: "${query}"\n`);
    const skills = executor.searchSkills(query);

    if (skills.length === 0) {
      console.log('无匹配技能');
    } else {
      console.log(`找到 ${skills.length} 个技能:\n`);
      for (const s of skills) {
        console.log(`[Q=${s.q_value.toFixed(2)}] ${s.name}`);
        console.log(`  描述: ${s.description}`);
        console.log(`  匹配关键词: ${s.matched_keywords.join(', ') || '(无)'}`);
        console.log();
      }
    }
  }

  if (command === 'execute' && query) {
    console.log(`🚀 执行技能: ${query}\n`);
    executor.execute(query, { input: '测试输入' }).then(result => {
      console.log(`结果: ${result.success ? '✅ 成功' : '❌ 失败'}`);
      console.log(`耗时: ${result.executionTimeMs}ms`);
      console.log(`模型: ${result.modelUsed}`);
      if (result.error) {
        console.log(`错误: ${result.error}`);
      }
      console.log(`\n输出:\n${result.output.slice(0, 500)}...`);
    });
  }

  if (command === 'auto' && query) {
    console.log(`🤖 自动执行: "${query}"\n`);
    executor.autoExecute(query).then(result => {
      if (!result) {
        console.log('无匹配技能');
      } else {
        console.log(`选中技能: ${result.skillName}`);
        console.log(`结果: ${result.success ? '✅ 成功' : '❌ 失败'}`);
        console.log(`耗时: ${result.executionTimeMs}ms`);
        console.log(`模型: ${result.modelUsed}`);
        console.log(`\n输出:\n${result.output.slice(0, 500)}...`);
      }
    });
  }

  // 不关闭，因为异步操作
}
