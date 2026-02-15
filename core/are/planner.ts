/**
 * ARE Planner - 生成执行计划供 LLM 执行
 *
 * 不执行任务，只生成结构化的执行计划
 * 让 Claude/Gemini/GLM 按计划逐步执行
 */

import { Database } from 'bun:sqlite';
import { PlanIR, TaskIR } from './types';
import { DAG } from './compiler/dag';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

interface PlanStep {
  step: number;
  task_id: string;
  name: string;
  action: string;
  target: string;
  params: Record<string, any>;
  depends_on: string[];
  can_parallel_with: string[];
  estimated_duration: string;
  tool_hint: string;  // Claude 工具提示
}

interface ExecutionPlan {
  plan_id: string;
  intent: string;
  total_steps: number;
  parallel_waves: number;
  steps: PlanStep[];
  execution_order: string[][];  // 按 wave 分组
  claude_instructions: string;  // 给 Claude 的执行指令
}

export class Planner {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
  }

  /**
   * 从意图生成执行计划
   */
  async plan(intent: string): Promise<ExecutionPlan> {
    // 1. 分析意图，匹配资源
    const resources = await this.matchResources(intent);

    // 2. 生成 PlanIR
    const planIR = this.generatePlanIR(intent, resources);

    // 3. 构建 DAG 获取并行调度
    const dag = new DAG(planIR);
    const schedule = dag.getParallelSchedule();

    // 4. 转换为执行计划
    return this.toPlan(planIR, schedule, intent);
  }

  /**
   * 从 PlanIR 生成执行计划
   */
  fromPlanIR(planIR: PlanIR): ExecutionPlan {
    const dag = new DAG(planIR);
    const schedule = dag.getParallelSchedule();
    return this.toPlan(planIR, schedule, planIR.meta.intent_text || '');
  }

  /**
   * 匹配资源 - 双向匹配策略
   * 1. 检查意图是否包含资源的关键词
   * 2. 支持中文（无空格分词）
   */
  private async matchResources(intent: string): Promise<Array<{
    type: string;
    id: string;
    name: string;
    target: string;
  }>> {
    const intentLower = intent.toLowerCase();
    const resources: Array<{ type: string; id: string; name: string; target: string; score: number }> = [];

    // 查询脚本
    const scripts = this.db.query(`
      SELECT script_id, name, description, intent_keywords, runtime
      FROM sys_scripts WHERE status = 'active'
    `).all() as any[];

    for (const s of scripts) {
      let score = 0;

      // 策略1: 解析 intent_keywords，检查意图是否包含这些关键词
      if (s.intent_keywords) {
        try {
          const keywords = JSON.parse(s.intent_keywords) as string[];
          const matchCount = keywords.filter(k => intentLower.includes(k.toLowerCase())).length;
          score = matchCount / keywords.length;
        } catch {
          // JSON 解析失败，回退到字符串匹配
        }
      }

      // 策略2: 检查是否包含脚本名称
      if (intentLower.includes(s.name.toLowerCase())) {
        score = Math.max(score, 0.5);
      }

      // 策略3: 描述关键词匹配
      if (s.description) {
        const descWords = s.description.split(/[\s,，、]+/).filter((w: string) => w.length > 1);
        const descMatch = descWords.filter((w: string) => intentLower.includes(w.toLowerCase())).length;
        if (descWords.length > 0) {
          score = Math.max(score, descMatch / descWords.length * 0.8);
        }
      }

      if (score > 0.2) {
        resources.push({
          type: s.runtime === 'primitive' ? 'primitive' : 'script',
          id: s.script_id,
          name: s.name,
          target: s.name,
          score
        });
      }
    }

    return resources.sort((a, b) => b.score - a.score).slice(0, 5);
  }

  /**
   * 生成 PlanIR
   */
  private generatePlanIR(intent: string, resources: any[]): PlanIR {
    const tasks: TaskIR[] = resources.map((r, i) => ({
      task_id: `t${i + 1}`,
      name: r.name,
      action: {
        type: r.type as any,
        target: r.target,
        params: {}
      },
      depends_on: i === 0 ? [] : [`t${i}`],  // 默认串行
      output: { var_name: `output_${i + 1}` }
    }));

    return {
      meta: {
        plan_id: `plan_${Date.now()}`,
        version: '1.0',
        created_at: new Date().toISOString(),
        intent_hash: this.hash(intent),
        intent_text: intent
      },
      vars: {},
      tasks,
      constraints: {
        timeout_ms: 30000,
        max_parallel: 2,
        retry_policy: { max_attempts: 2, backoff_ms: 1000, backoff_multiplier: 2 },
        rollback_on_failure: false
      }
    };
  }

  /**
   * 转换为执行计划
   */
  private toPlan(planIR: PlanIR, schedule: any[][], intent: string): ExecutionPlan {
    const steps: PlanStep[] = [];
    let stepNum = 1;

    for (let wave = 0; wave < schedule.length; wave++) {
      const waveTasks = schedule[wave];
      for (const task of waveTasks) {
        const canParallelWith = waveTasks
          .filter((t: any) => t.task_id !== task.task_id)
          .map((t: any) => t.task_id);

        steps.push({
          step: stepNum++,
          task_id: task.task_id,
          name: task.name,
          action: task.action.type,
          target: task.action.target,
          params: task.action.params,
          depends_on: task.depends_on,
          can_parallel_with: canParallelWith,
          estimated_duration: this.estimateDuration(task.action.type),
          tool_hint: this.getToolHint(task.action)
        });
      }
    }

    const executionOrder = schedule.map(wave =>
      wave.map((t: any) => t.task_id)
    );

    return {
      plan_id: planIR.meta.plan_id,
      intent,
      total_steps: steps.length,
      parallel_waves: schedule.length,
      steps,
      execution_order: executionOrder,
      claude_instructions: this.generateClaudeInstructions(steps, executionOrder)
    };
  }

  /**
   * 生成 Claude 执行指令
   */
  private generateClaudeInstructions(steps: PlanStep[], executionOrder: string[][]): string {
    let instructions = `## 执行计划\n\n`;
    instructions += `共 ${steps.length} 步，分 ${executionOrder.length} 波执行：\n\n`;

    for (let wave = 0; wave < executionOrder.length; wave++) {
      const waveTaskIds = executionOrder[wave];
      const waveTasks = steps.filter(s => waveTaskIds.includes(s.task_id));

      instructions += `### Wave ${wave + 1}`;
      if (waveTasks.length > 1) {
        instructions += ` (可并行)\n`;
      } else {
        instructions += `\n`;
      }

      for (const step of waveTasks) {
        instructions += `\n**Step ${step.step}: ${step.name}**\n`;
        instructions += `- 动作: ${step.action} → ${step.target}\n`;
        instructions += `- 工具: ${step.tool_hint}\n`;
        if (Object.keys(step.params).length > 0) {
          instructions += `- 参数: ${JSON.stringify(step.params)}\n`;
        }
        if (step.depends_on.length > 0) {
          instructions += `- 依赖: ${step.depends_on.join(', ')}\n`;
        }
      }
      instructions += `\n`;
    }

    instructions += `---\n请按上述顺序执行。Wave 内的步骤可以并行调用。\n`;

    return instructions;
  }

  private estimateDuration(actionType: string): string {
    const estimates: Record<string, string> = {
      primitive: '~10ms',
      script: '~500ms',
      shortcut: '~1s',
      mcp: '~2s',
      code: '~5s'
    };
    return estimates[actionType] || '未知';
  }

  private getToolHint(action: { type: string; target: string }): string {
    if (action.type === 'primitive') {
      const hints: Record<string, string> = {
        'fs.read': 'Read tool',
        'fs.write': 'Write tool',
        'fs.list': 'Glob tool',
        'db.query': 'mcp__are__query_db',
        'shell.run': 'Bash tool',
        'http.get': 'WebFetch tool',
        'http.post': 'WebFetch tool',
        'notify.log': 'console output',
        'text.template': 'string manipulation'
      };
      return hints[action.target] || `primitive: ${action.target}`;
    }
    if (action.type === 'script') {
      return `Bash: bun ~/.claude/core/ree/scripts/${action.target}`;
    }
    if (action.type === 'shortcut') {
      return `Bash: shortcuts run ${action.target}`;
    }
    return action.target;
  }

  private hash(text: string): string {
    const { createHash } = require('crypto');
    return createHash('sha256').update(text).digest('hex').slice(0, 16);
  }
}

// CLI
if (import.meta.main) {
  const intent = process.argv[2] || '读取配置文件然后查询数据库';
  const planner = new Planner();

  console.log(`\n🎯 意图: ${intent}\n`);

  const plan = await planner.plan(intent);

  console.log(`📋 计划 ID: ${plan.plan_id}`);
  console.log(`📊 步骤数: ${plan.total_steps}, 波次: ${plan.parallel_waves}\n`);

  console.log(plan.claude_instructions);
}

export const planner = new Planner();
