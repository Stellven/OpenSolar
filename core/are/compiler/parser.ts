/**
 * ARE Plan Parser
 *
 * Parse LLM output or structured input into Plan IR
 */

import { PlanIR, PlanTask, PlanMeta, PlanVariable, PlanConstraints, PRIMITIVES } from '../types';
import { createHash } from 'crypto';

// ============================================
// Plan Parser
// ============================================

export class PlanParser {
  /**
   * Parse JSON Plan IR (from LLM structured output)
   */
  parseJSON(json: string | object): PlanIR {
    const raw = typeof json === 'string' ? JSON.parse(json) : json;
    return this.validateAndNormalize(raw);
  }

  /**
   * Parse simple task list format (for quick plans)
   * Format: Each line is "task_name: action_type target params"
   */
  parseSimple(text: string, intentText?: string): PlanIR {
    const lines = text.trim().split('\n').filter(l => l.trim() && !l.startsWith('#'));
    const tasks: PlanTask[] = [];
    const vars: Record<string, PlanVariable> = {};

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      const task = this.parseTaskLine(line, i);
      if (task) {
        tasks.push(task);
        vars[task.output.var_name] = {
          type: 'computed',
          source_task: task.task_id,
        };
      }
    }

    // Auto-detect dependencies based on variable references
    this.inferDependencies(tasks, vars);

    return {
      meta: this.createMeta(intentText || text),
      vars,
      tasks,
      constraints: this.defaultConstraints(),
    };
  }

  /**
   * Parse a single task line
   * Format: "name: primitive.op param1=value1 param2=value2"
   * Or: "name: script:script_id param1=value1"
   * Or: "name: mcp:tool_name param1=value1"
   */
  private parseTaskLine(line: string, index: number): PlanTask | null {
    const colonIdx = line.indexOf(':');
    if (colonIdx === -1) return null;

    const name = line.substring(0, colonIdx).trim();
    const rest = line.substring(colonIdx + 1).trim();

    // Parse action and params
    const parts = rest.split(/\s+/);
    const actionSpec = parts[0];
    const paramParts = parts.slice(1);

    // Parse action type
    let actionType: 'primitive' | 'script' | 'mcp' | 'agent' | 'shortcut' | 'code' = 'primitive';
    let target = actionSpec;

    if (actionSpec.startsWith('script:')) {
      actionType = 'script';
      target = actionSpec.substring(7);
    } else if (actionSpec.startsWith('mcp:')) {
      actionType = 'mcp';
      target = actionSpec.substring(4);
    } else if (actionSpec.startsWith('agent:')) {
      actionType = 'agent';
      target = actionSpec.substring(6);
    } else if (actionSpec.startsWith('shortcut:')) {
      actionType = 'shortcut';
      target = actionSpec.substring(9);
    } else if (actionSpec.startsWith('code:')) {
      actionType = 'code';
      target = actionSpec.substring(5);
    }

    // Parse params (key=value or key="value with spaces")
    const params = this.parseParams(paramParts.join(' '));

    const taskId = `t${index + 1}`;
    return {
      task_id: taskId,
      name,
      action: { type: actionType, target, params },
      depends_on: [],
      output: { var_name: `result_${taskId}`, type: 'any' },
    };
  }

  /**
   * Parse params string into object
   */
  private parseParams(paramStr: string): Record<string, any> {
    const params: Record<string, any> = {};
    // Match key=value or key="quoted value"
    const regex = /(\w+)=(?:"([^"]*)"|'([^']*)'|(\S+))/g;
    let match;
    while ((match = regex.exec(paramStr)) !== null) {
      const key = match[1];
      const value = match[2] ?? match[3] ?? match[4];
      // Try to parse as JSON for complex values
      try {
        params[key] = JSON.parse(value);
      } catch {
        params[key] = value;
      }
    }
    return params;
  }

  /**
   * Infer dependencies based on variable references in params
   */
  private inferDependencies(tasks: PlanTask[], vars: Record<string, PlanVariable>): void {
    for (const task of tasks) {
      const paramStr = JSON.stringify(task.action.params);
      // Find ${var_name} references
      const refs = paramStr.match(/\$\{(\w+)(?:\.\w+)*\}/g) || [];
      for (const ref of refs) {
        const varName = ref.slice(2, -1).split('.')[0]; // ${result_t1.field} -> result_t1
        const sourceVar = vars[varName];
        if (sourceVar?.source_task && !task.depends_on.includes(sourceVar.source_task)) {
          task.depends_on.push(sourceVar.source_task);
        }
      }
    }
  }

  /**
   * Validate and normalize Plan IR
   */
  private validateAndNormalize(raw: any): PlanIR {
    // Ensure required fields
    if (!raw.tasks || !Array.isArray(raw.tasks)) {
      throw new Error('Plan IR must have tasks array');
    }

    // Normalize meta
    const meta: PlanMeta = {
      plan_id: raw.meta?.plan_id || `plan_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      version: raw.meta?.version || '1.0',
      created_at: raw.meta?.created_at || new Date().toISOString(),
      intent_hash: raw.meta?.intent_hash || this.hashIntent(raw.meta?.intent_text || ''),
      intent_text: raw.meta?.intent_text,
      estimated_cost: raw.meta?.estimated_cost,
      estimated_latency_ms: raw.meta?.estimated_latency_ms,
    };

    // Normalize vars
    const vars: Record<string, PlanVariable> = {};
    if (raw.vars) {
      for (const [name, v] of Object.entries(raw.vars)) {
        const varDef = v as any;
        vars[name] = {
          type: varDef.type || 'computed',
          value: varDef.value,
          source_task: varDef.source_task,
          schema: varDef.schema,
        };
      }
    }

    // Normalize tasks
    const tasks: PlanTask[] = raw.tasks.map((t: any, i: number) => this.normalizeTask(t, i));

    // Add output vars for tasks without explicit vars
    for (const task of tasks) {
      if (!vars[task.output.var_name]) {
        vars[task.output.var_name] = {
          type: 'computed',
          source_task: task.task_id,
        };
      }
    }

    // Normalize constraints
    const constraints: PlanConstraints = {
      timeout_ms: raw.constraints?.timeout_ms ?? 60000,
      max_parallel: raw.constraints?.max_parallel ?? 4,
      retry_policy: raw.constraints?.retry_policy ?? {
        max_attempts: 2,
        backoff_ms: 1000,
        backoff_multiplier: 2,
      },
      rollback_on_failure: raw.constraints?.rollback_on_failure ?? false,
    };

    return { meta, vars, tasks, constraints };
  }

  /**
   * Normalize a single task
   */
  private normalizeTask(raw: any, index: number): PlanTask {
    const taskId = raw.task_id || `t${index + 1}`;

    return {
      task_id: taskId,
      name: raw.name || `Task ${index + 1}`,
      description: raw.description,
      action: {
        type: raw.action?.type || 'primitive',
        target: raw.action?.target || '',
        params: raw.action?.params || {},
      },
      depends_on: raw.depends_on || [],
      output: {
        var_name: raw.output?.var_name || `result_${taskId}`,
        type: raw.output?.type,
      },
      constraints: raw.constraints ? {
        timeout_ms: raw.constraints.timeout_ms,
        retry: raw.constraints.retry,
        cache_ttl_s: raw.constraints.cache_ttl_s,
        idempotent: raw.constraints.idempotent,
        sandbox: raw.constraints.sandbox,
      } : undefined,
    };
  }

  /**
   * Create plan metadata
   */
  private createMeta(intentText: string): PlanMeta {
    return {
      plan_id: `plan_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      version: '1.0',
      created_at: new Date().toISOString(),
      intent_hash: this.hashIntent(intentText),
      intent_text: intentText,
    };
  }

  /**
   * Hash intent text for cache lookup
   */
  hashIntent(text: string): string {
    // Normalize: lowercase, remove extra spaces, sort words for permutation invariance
    const normalized = text.toLowerCase().trim().replace(/\s+/g, ' ');
    return createHash('sha256').update(normalized).digest('hex').slice(0, 16);
  }

  /**
   * Default plan constraints
   */
  private defaultConstraints(): PlanConstraints {
    return {
      timeout_ms: 60000,
      max_parallel: 4,
      retry_policy: {
        max_attempts: 2,
        backoff_ms: 1000,
        backoff_multiplier: 2,
      },
      rollback_on_failure: false,
    };
  }

  /**
   * Validate task action against known primitives
   */
  validateAction(task: PlanTask): string[] {
    const errors: string[] = [];

    if (task.action.type === 'primitive') {
      const primitive = PRIMITIVES[task.action.target];
      if (!primitive) {
        errors.push(`Unknown primitive: ${task.action.target}`);
      } else {
        // Check required params
        for (const [name, def] of Object.entries(primitive.params)) {
          if (def.required && !(name in task.action.params)) {
            errors.push(`Missing required param '${name}' for ${task.action.target}`);
          }
        }
      }
    }

    return errors;
  }

  /**
   * Validate entire plan
   */
  validate(plan: PlanIR): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check for duplicate task IDs
    const taskIds = new Set<string>();
    for (const task of plan.tasks) {
      if (taskIds.has(task.task_id)) {
        errors.push(`Duplicate task ID: ${task.task_id}`);
      }
      taskIds.add(task.task_id);
    }

    // Check dependencies exist
    for (const task of plan.tasks) {
      for (const dep of task.depends_on) {
        if (!taskIds.has(dep)) {
          errors.push(`Task ${task.task_id} depends on unknown task: ${dep}`);
        }
      }
    }

    // Check for cycles
    const cycleError = this.detectCycle(plan.tasks);
    if (cycleError) {
      errors.push(cycleError);
    }

    // Validate actions
    for (const task of plan.tasks) {
      errors.push(...this.validateAction(task));
    }

    return { valid: errors.length === 0, errors };
  }

  /**
   * Detect cycles in task dependencies
   */
  private detectCycle(tasks: PlanTask[]): string | null {
    const visited = new Set<string>();
    const inStack = new Set<string>();
    const taskMap = new Map(tasks.map(t => [t.task_id, t]));

    const dfs = (taskId: string, path: string[]): string | null => {
      if (inStack.has(taskId)) {
        return `Cycle detected: ${[...path, taskId].join(' -> ')}`;
      }
      if (visited.has(taskId)) return null;

      visited.add(taskId);
      inStack.add(taskId);

      const task = taskMap.get(taskId);
      if (task) {
        for (const dep of task.depends_on) {
          const result = dfs(dep, [...path, taskId]);
          if (result) return result;
        }
      }

      inStack.delete(taskId);
      return null;
    };

    for (const task of tasks) {
      const result = dfs(task.task_id, []);
      if (result) return result;
    }

    return null;
  }
}

// ============================================
// Export singleton
// ============================================

export const parser = new PlanParser();
