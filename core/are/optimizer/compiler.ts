/**
 * ARE JIT/AOT Compiler
 *
 * Compile Plan IR to optimized execution format
 * - JIT: Just-in-time compilation for cold plans
 * - AOT: Ahead-of-time compilation for hot plans
 */

import { Database } from 'bun:sqlite';
import { PlanIR, PlanTask, PRIMITIVES } from '../types';
import { DAG } from '../compiler/dag';
import { createHash } from 'crypto';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Compiled Plan Format
// ============================================

export interface CompiledPlan {
  plan_id: string;
  version: string;
  compile_mode: 'jit' | 'aot';
  compiled_at: string;

  // Execution schedule
  schedule: CompiledStage[];

  // Optimizations applied
  optimizations: string[];

  // Pre-resolved data
  static_params: Record<string, any>;

  // Metrics
  estimated_latency_ms: number;
  estimated_cost: number;
}

export interface CompiledStage {
  stage_id: number;
  tasks: CompiledTask[];
  parallel: boolean;
  dependencies: number[];  // Stage IDs this depends on
}

export interface CompiledTask {
  task_id: string;
  action_type: string;
  target: string;
  params_template: string;  // JSON template with ${var} references
  cache_key_template: string;
  timeout_ms: number;
  retry_count: number;
  tier: 'cache' | 'primitive' | 'script' | 'sandbox';
}

// ============================================
// Plan Compiler
// ============================================

export class PlanCompiler {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
  }

  /**
   * Compile a Plan IR (JIT mode)
   */
  compileJIT(plan: PlanIR): CompiledPlan {
    const dag = new DAG(plan);
    const schedule = this.buildSchedule(dag, plan);
    const optimizations = this.applyOptimizations(plan, schedule);

    return {
      plan_id: plan.meta.plan_id,
      version: '1.0',
      compile_mode: 'jit',
      compiled_at: new Date().toISOString(),
      schedule,
      optimizations,
      static_params: this.extractStaticParams(plan),
      estimated_latency_ms: this.estimateLatency(schedule),
      estimated_cost: this.estimateCost(schedule),
    };
  }

  /**
   * Compile a Plan IR (AOT mode) - more aggressive optimizations
   */
  compileAOT(plan: PlanIR): CompiledPlan {
    const dag = new DAG(plan);
    const schedule = this.buildSchedule(dag, plan);

    // Apply AOT-specific optimizations
    const optimizations = [
      ...this.applyOptimizations(plan, schedule),
      ...this.applyAOTOptimizations(plan, schedule),
    ];

    // Pre-compute cache keys for static tasks
    this.precomputeCacheKeys(schedule, plan);

    return {
      plan_id: plan.meta.plan_id,
      version: '1.0',
      compile_mode: 'aot',
      compiled_at: new Date().toISOString(),
      schedule,
      optimizations,
      static_params: this.extractStaticParams(plan),
      estimated_latency_ms: this.estimateLatency(schedule) * 0.8, // AOT is faster
      estimated_cost: this.estimateCost(schedule) * 0.9, // AOT is cheaper
    };
  }

  /**
   * Build execution schedule from DAG
   */
  private buildSchedule(dag: DAG, plan: PlanIR): CompiledStage[] {
    const parallelSchedule = dag.getParallelSchedule();
    const stages: CompiledStage[] = [];

    for (let i = 0; i < parallelSchedule.length; i++) {
      const tasks = parallelSchedule[i];
      const stage: CompiledStage = {
        stage_id: i,
        tasks: tasks.map(t => this.compileTask(t, plan)),
        parallel: tasks.length > 1,
        dependencies: i > 0 ? [i - 1] : [],
      };
      stages.push(stage);
    }

    return stages;
  }

  /**
   * Compile a single task
   */
  private compileTask(task: PlanTask, plan: PlanIR): CompiledTask {
    const tier = this.determineTier(task);

    return {
      task_id: task.task_id,
      action_type: task.action.type,
      target: task.action.target,
      params_template: JSON.stringify(task.action.params),
      cache_key_template: this.buildCacheKeyTemplate(task),
      timeout_ms: task.constraints?.timeout_ms || plan.constraints?.timeout_ms || 30000,
      retry_count: task.constraints?.retry || plan.constraints?.retry_policy?.max_attempts || 2,
      tier,
    };
  }

  /**
   * Determine execution tier for task
   */
  private determineTier(task: PlanTask): CompiledTask['tier'] {
    switch (task.action.type) {
      case 'primitive':
        return PRIMITIVES[task.action.target] ? 'primitive' : 'script';
      case 'script':
        return 'script';
      case 'code':
        return 'sandbox';
      default:
        return 'script';
    }
  }

  /**
   * Build cache key template
   */
  private buildCacheKeyTemplate(task: PlanTask): string {
    return `${task.action.type}:${task.action.target}:${JSON.stringify(task.action.params)}`;
  }

  /**
   * Apply general optimizations
   */
  private applyOptimizations(plan: PlanIR, schedule: CompiledStage[]): string[] {
    const optimizations: string[] = [];

    // 1. Merge small sequential stages
    if (this.canMergeStages(schedule)) {
      optimizations.push('stage_merge');
    }

    // 2. Cache promotion for idempotent tasks
    const idempotentTasks = plan.tasks.filter(t => t.constraints?.idempotent);
    if (idempotentTasks.length > 0) {
      optimizations.push(`cache_promotion:${idempotentTasks.length}`);
    }

    // 3. Parallel degree optimization
    const maxParallel = Math.max(...schedule.map(s => s.tasks.length));
    if (maxParallel > 1) {
      optimizations.push(`parallel:${maxParallel}`);
    }

    return optimizations;
  }

  /**
   * Apply AOT-specific optimizations
   */
  private applyAOTOptimizations(plan: PlanIR, schedule: CompiledStage[]): string[] {
    const optimizations: string[] = [];

    // 1. Inline static params
    const staticParams = this.extractStaticParams(plan);
    if (Object.keys(staticParams).length > 0) {
      optimizations.push(`inline_static:${Object.keys(staticParams).length}`);
    }

    // 2. Pre-resolve script paths
    const scriptTasks = plan.tasks.filter(t => t.action.type === 'script');
    if (scriptTasks.length > 0) {
      optimizations.push(`preresolve_scripts:${scriptTasks.length}`);
    }

    // 3. Speculative execution hints
    const speculativeTasks = this.findSpeculativeTasks(plan);
    if (speculativeTasks.length > 0) {
      optimizations.push(`speculative:${speculativeTasks.length}`);
    }

    return optimizations;
  }

  /**
   * Check if stages can be merged
   */
  private canMergeStages(schedule: CompiledStage[]): boolean {
    for (let i = 0; i < schedule.length - 1; i++) {
      if (schedule[i].tasks.length === 1 && schedule[i + 1].tasks.length === 1) {
        return true;
      }
    }
    return false;
  }

  /**
   * Extract static (non-variable) params
   */
  private extractStaticParams(plan: PlanIR): Record<string, any> {
    const staticParams: Record<string, any> = {};

    for (const [name, varDef] of Object.entries(plan.vars)) {
      if (varDef.type === 'input' && varDef.value !== undefined) {
        staticParams[name] = varDef.value;
      }
    }

    return staticParams;
  }

  /**
   * Find tasks that can be executed speculatively
   */
  private findSpeculativeTasks(plan: PlanIR): PlanTask[] {
    return plan.tasks.filter(t =>
      t.constraints?.idempotent &&
      t.depends_on.length === 0 &&
      t.action.type === 'primitive'
    );
  }

  /**
   * Pre-compute cache keys for static tasks
   */
  private precomputeCacheKeys(schedule: CompiledStage[], plan: PlanIR): void {
    const staticParams = this.extractStaticParams(plan);

    for (const stage of schedule) {
      for (const task of stage.tasks) {
        // Check if all params are static
        const hasVarRefs = task.params_template.includes('${');
        if (!hasVarRefs) {
          // Pre-compute cache key
          const content = `${task.action_type}:${task.target}:${task.params_template}`;
          task.cache_key_template = createHash('sha256').update(content).digest('hex').slice(0, 32);
        }
      }
    }
  }

  /**
   * Estimate total latency
   */
  private estimateLatency(schedule: CompiledStage[]): number {
    let total = 0;
    const tierLatency: Record<string, number> = {
      cache: 5,
      primitive: 20,
      script: 100,
      sandbox: 500,
    };

    for (const stage of schedule) {
      // Parallel stage: max of task latencies
      const stageLatency = Math.max(
        ...stage.tasks.map(t => tierLatency[t.tier] || 100)
      );
      total += stageLatency;
    }

    return total;
  }

  /**
   * Estimate total cost (in arbitrary units)
   */
  private estimateCost(schedule: CompiledStage[]): number {
    let total = 0;
    const tierCost: Record<string, number> = {
      cache: 0.01,
      primitive: 0.1,
      script: 1,
      sandbox: 5,
    };

    for (const stage of schedule) {
      for (const task of stage.tasks) {
        total += tierCost[task.tier] || 1;
      }
    }

    return total;
  }

  /**
   * Save compiled plan to database
   */
  async saveCompiled(compiled: CompiledPlan): Promise<void> {
    try {
      this.db.run(
        `UPDATE are_plan_cache SET
           compile_mode = ?,
           compiled_artifact = ?
         WHERE plan_id = ?`,
        [
          compiled.compile_mode,
          JSON.stringify(compiled),
          compiled.plan_id,
        ]
      );
    } catch (e) {
      // Ignore save errors
    }
  }

  /**
   * Load compiled plan from database
   */
  async loadCompiled(planId: string): Promise<CompiledPlan | null> {
    try {
      const row = this.db.query<{ compiled_artifact: string }, [string]>(
        `SELECT compiled_artifact FROM are_plan_cache WHERE plan_id = ? AND compiled_artifact IS NOT NULL`
      ).get(planId);

      if (row?.compiled_artifact) {
        return JSON.parse(row.compiled_artifact);
      }
    } catch (e) {
      // Ignore load errors
    }
    return null;
  }
}

// ============================================
// Export
// ============================================

export const planCompiler = new PlanCompiler();
