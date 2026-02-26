/**
 * MEMRL Skill Executor - 技能执行器
 *
 * Phase 1 核心组件
 * 职责: 执行 Skill，调用 LLM，处理结果和错误
 *
 * 执行流程:
 * 1. 获取 Skill 详情
 * 2. 验证参数
 * 3. 构建 Prompt
 * 4. 调用 LLM (brain-router)
 * 5. 解析响应
 * 6. 记录执行结果
 */

import { Database } from 'bun:sqlite';
import { SkillRetriever, RetrievedSkill } from './skill-retriever';

// 执行参数
export interface ExecutionParams {
  [key: string]: string | number | boolean;
}

// 执行结果
export interface ExecutionResult {
  success: boolean;
  skillId: string;
  skillName: string;
  output: string;
  executionTimeMs: number;
  error?: {
    type: 'validation' | 'timeout' | 'llm' | 'parse' | 'unknown';
    message: string;
  };
  metadata: {
    modelUsed: string;
    retryCount: number;
    fallbackUsed: boolean;
  };
}

// 执行配置
interface ExecutorConfig {
  defaultTimeout: number;      // 默认超时 (ms)
  maxRetries: number;          // 最大重试次数
  defaultModel: string;        // 默认 LLM 模型
  temperature: number;         // LLM 温度
  enableFallback: boolean;     // 启用降级
}

const DEFAULT_CONFIG: ExecutorConfig = {
  defaultTimeout: 30000,
  maxRetries: 2,
  defaultModel: 'glm-5',
  temperature: 0.3,
  enableFallback: true
};

// MCP brain-router 类型声明
declare function mcp__brain_router__complete(params: {
  model: string;
  system?: string;
  prompt: string;
}): Promise<{ content: string }>;

export class SkillExecutor {
  private db: Database;
  private retriever: SkillRetriever;
  private config: ExecutorConfig;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    config: Partial<ExecutorConfig> = {}
  ) {
    this.db = new Database(dbPath);
    this.retriever = new SkillRetriever(dbPath);
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 执行技能
   *
   * @param skill 技能对象或技能 ID
   * @param params 执行参数
   * @param context 额外上下文
   */
  async execute(
    skill: RetrievedSkill | string,
    params: ExecutionParams = {},
    context: string = ''
  ): Promise<ExecutionResult> {
    const startTime = Date.now();
    let retryCount = 0;

    // 1. 获取技能详情
    let skillObj: RetrievedSkill | null;
    if (typeof skill === 'string') {
      const s = this.retriever.getSkillById(skill);
      if (!s) {
        return this.createErrorResult(
          skill,
          'validation',
          `技能不存在: ${skill}`,
          0,
          0
        );
      }
      skillObj = { ...s, keyword_match_score: 0, intent_match_score: 0, context_match_score: 0, combined_score: 0, matched_keywords: [] };
    } else {
      skillObj = skill;
    }

    // 2. 参数验证
    const validationError = this.validateParams(skillObj, params);
    if (validationError) {
      return this.createErrorResult(
        skillObj.skill_id,
        'validation',
        validationError,
        0,
        0
      );
    }

    // 3. 构建 Prompt
    const prompt = this.buildPrompt(skillObj, params, context);

    // 4. 调用 LLM (带重试)
    let output = '';
    let lastError: string | null = null;

    for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
      try {
        output = await this.callLLM(prompt);
        break; // 成功则退出循环
      } catch (error) {
        lastError = error instanceof Error ? error.message : String(error);
        retryCount = attempt + 1;

        if (attempt < this.config.maxRetries) {
          // 指数退避
          await this.sleep(Math.pow(2, attempt) * 1000);
        }
      }
    }

    // 5. 检查是否需要降级
    if (!output && this.config.enableFallback) {
      output = this.fallbackResponse(skillObj, params);
      const executionTimeMs = Date.now() - startTime;

      this.retriever.recordFailure(skillObj.skill_id);

      return {
        success: false,
        skillId: skillObj.skill_id,
        skillName: skillObj.name,
        output,
        executionTimeMs,
        error: {
          type: 'llm',
          message: lastError || 'LLM 调用失败'
        },
        metadata: {
          modelUsed: this.config.defaultModel,
          retryCount,
          fallbackUsed: true
        }
      };
    }

    if (!output) {
      const executionTimeMs = Date.now() - startTime;
      this.retriever.recordFailure(skillObj.skill_id);

      return {
        success: false,
        skillId: skillObj.skill_id,
        skillName: skillObj.name,
        output: '',
        executionTimeMs,
        error: {
          type: 'llm',
          message: lastError || 'LLM 调用失败'
        },
        metadata: {
          modelUsed: this.config.defaultModel,
          retryCount,
          fallbackUsed: false
        }
      };
    }

    // 6. 成功
    const executionTimeMs = Date.now() - startTime;
    this.retriever.recordSuccess(skillObj.skill_id, executionTimeMs);

    return {
      success: true,
      skillId: skillObj.skill_id,
      skillName: skillObj.name,
      output,
      executionTimeMs,
      metadata: {
        modelUsed: this.config.defaultModel,
        retryCount,
        fallbackUsed: false
      }
    };
  }

  /**
   * 根据用户输入自动选择并执行技能
   */
  async autoExecute(
    userInput: string,
    context: string = ''
  ): Promise<ExecutionResult | null> {
    // 1. 检索最相关的技能
    const skills = this.retriever.retrieve(userInput);

    if (skills.length === 0) {
      return null;
    }

    // 2. 选择最佳技能 (Top-1)
    const bestSkill = skills[0];

    // 3. 提取参数
    const params = this.extractParams(userInput, bestSkill);

    // 4. 执行
    return this.execute(bestSkill, params, context);
  }

  /**
   * 验证参数
   */
  private validateParams(skill: Skill, params: ExecutionParams): string | null {
    const paramDefs = JSON.parse(skill.parameters || '[]');

    for (const paramDef of paramDefs) {
      if (paramDef.required && !(paramDef.name in params)) {
        return `缺少必需参数: ${paramDef.name}`;
      }

      if (paramDef.name in params) {
        const value = params[paramDef.name];
        const type = typeof value;

        if (paramDef.type === 'number' && type !== 'number') {
          return `参数 ${paramDef.name} 应为数字类型`;
        }

        if (paramDef.type === 'boolean' && type !== 'boolean') {
          return `参数 ${paramDef.name} 应为布尔类型`;
        }
      }
    }

    return null;
  }

  /**
   * 构建 Prompt
   */
  private buildPrompt(
    skill: Skill,
    params: ExecutionParams,
    context: string
  ): string {
    let prompt = skill.llm_prompt_template || '';

    // 替换参数占位符 {{param_name}}
    for (const [key, value] of Object.entries(params)) {
      const placeholder = `{{${key}}}`;
      prompt = prompt.replace(new RegExp(placeholder, 'g'), String(value));
    }

    // 添加上下文
    if (context) {
      prompt += `\n\n上下文信息:\n${context}`;
    }

    return prompt;
  }

  /**
   * 调用 LLM
   *
   * 支持多种后端:
   * 1. MCP brain-router (默认: http://localhost:3000)
   * 2. OpenAI API (设置 OPENAI_API_KEY)
   * 3. GLM API (设置 GLM_API_KEY)
   * 4. 自定义端点 (设置 LLM_ENDPOINT)
   */
  private async callLLM(prompt: string): Promise<string> {
    const endpoint = process.env.LLM_ENDPOINT || 'http://localhost:3000/api/brain-router/complete';
    const apiKey = process.env.LLM_API_KEY || process.env.OPENAI_API_KEY || process.env.GLM_API_KEY;

    // 判断使用哪种 API 格式
    if (endpoint.includes('openai.com') || process.env.OPENAI_API_KEY) {
      return this.callOpenAI(prompt);
    }

    if (endpoint.includes('bigmodel.cn') || process.env.GLM_API_KEY) {
      return this.callGLM(prompt);
    }

    // 默认: brain-router 或自定义端点
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {})
      },
      body: JSON.stringify({
        model: this.config.defaultModel,
        prompt,
        temperature: this.config.temperature
      })
    });

    if (!response.ok) {
      throw new Error(`LLM 调用失败: ${response.status}`);
    }

    const data = await response.json();
    return data.content || data.response || data.choices?.[0]?.message?.content || '';
  }

  /**
   * 调用 OpenAI API
   */
  private async callOpenAI(prompt: string): Promise<string> {
    const apiKey = process.env.OPENAI_API_KEY!;
    const model = process.env.OPENAI_MODEL || 'gpt-4o-mini';

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: '你是一个专业的技术助手，帮助用户解决问题。' },
          { role: 'user', content: prompt }
        ],
        temperature: this.config.temperature
      })
    });

    if (!response.ok) {
      throw new Error(`OpenAI 调用失败: ${response.status}`);
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content || '';
  }

  /**
   * 调用 GLM API
   */
  private async callGLM(prompt: string): Promise<string> {
    const apiKey = process.env.GLM_API_KEY!;
    const model = process.env.GLM_MODEL || 'glm-4-flash';

    const response = await fetch('https://open.bigmodel.cn/api/paas/v4/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: '你是一个专业的技术助手，帮助用户解决问题。' },
          { role: 'user', content: prompt }
        ],
        temperature: this.config.temperature
      })
    });

    if (!response.ok) {
      throw new Error(`GLM 调用失败: ${response.status}`);
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content || '';
  }

  /**
   * 降级响应
   */
  private fallbackResponse(skill: Skill, params: ExecutionParams): string {
    return `⚠️ 技能 "${skill.name}" 执行失败，以下是降级响应：

${skill.description}

请尝试以下步骤：
1. 检查输入参数是否正确
2. 稍后重试
3. 如问题持续，联系管理员

参数: ${JSON.stringify(params)}`;
  }

  /**
   * 从用户输入提取参数
   */
  private extractParams(userInput: string, skill: RetrievedSkill): ExecutionParams {
    const params: ExecutionParams = {};
    const paramDefs = JSON.parse(skill.parameters || '[]');

    // 简单提取：把整个用户输入作为第一个参数
    // 更复杂的提取可以用 NER 或 LLM
    if (paramDefs.length > 0) {
      const firstParam = paramDefs[0];
      if (firstParam.type === 'string') {
        params[firstParam.name] = userInput;
      }
    }

    return params;
  }

  /**
   * 创建错误结果
   */
  private createErrorResult(
    skillId: string,
    errorType: ExecutionResult['error'] extends { type: infer T } ? T : never,
    message: string,
    executionTimeMs: number,
    retryCount: number
  ): ExecutionResult {
    return {
      success: false,
      skillId,
      skillName: skillId,
      output: '',
      executionTimeMs,
      error: {
        type: errorType,
        message
      },
      metadata: {
        modelUsed: this.config.defaultModel,
        retryCount,
        fallbackUsed: false
      }
    };
  }

  /**
   * Sleep 工具
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 获取执行统计
   */
  getStats(): {
    totalSkills: number;
    totalExecutions: number;
    successRate: number;
    avgExecutionTime: number;
  } {
    const result = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        SUM(success_count + failure_count) as executions,
        SUM(success_count) as successes,
        AVG(avg_execution_time_ms) as avg_time
      FROM sys_skill_bank
    `).get() as any;

    const executions = result?.executions || 0;
    const successes = result?.successes || 0;

    return {
      totalSkills: result?.total || 0,
      totalExecutions: executions,
      successRate: executions > 0 ? successes / executions : 0,
      avgExecutionTime: result?.avg_time || 0
    };
  }

  close(): void {
    this.retriever.close();
    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const executor = new SkillExecutor();

  const command = process.argv[2] || 'stats';
  const skillId = process.argv[3] || 'skill_perf_debug_001';
  const paramValue = process.argv.slice(4).join(' ') || '程序启动很慢，需要分析';

  if (command === 'stats') {
    console.log('📊 Skill Executor 统计\n');
    const stats = executor.getStats();
    console.log(`总技能数: ${stats.totalSkills}`);
    console.log(`总执行次数: ${stats.totalExecutions}`);
    console.log(`成功率: ${(stats.successRate * 100).toFixed(1)}%`);
    console.log(`平均执行时间: ${stats.avgExecutionTime.toFixed(0)}ms`);
  }

  if (command === 'execute') {
    console.log(`🚀 执行技能: ${skillId}\n`);
    console.log(`参数: "${paramValue}"\n`);

    const result = await executor.execute(skillId, {
      problem_description: paramValue
    });

    console.log(`执行结果: ${result.success ? '✅ 成功' : '❌ 失败'}`);
    console.log(`耗时: ${result.executionTimeMs}ms`);
    console.log(`重试次数: ${result.metadata.retryCount}`);
    console.log(`\n输出:\n${result.output}`);
  }

  if (command === 'auto') {
    console.log(`🤖 自动执行技能\n`);
    console.log(`输入: "${skillId}"\n`);

    const result = await executor.autoExecute(skillId);

    if (result) {
      console.log(`选中技能: ${result.skillName}`);
      console.log(`执行结果: ${result.success ? '✅ 成功' : '❌ 失败'}`);
      console.log(`耗时: ${result.executionTimeMs}ms`);
      console.log(`\n输出:\n${result.output}`);
    } else {
      console.log('❌ 未找到匹配的技能');
    }
  }

  executor.close();
}
