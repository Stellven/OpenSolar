/**
 * ARE Parallel Executor
 *
 * Parallel execution with work stealing scheduling
 */

import { PlanIR, PlanTask, TaskResult, PlanResult, ExecutionState } from '../types';
import { DAG } from '../compiler/dag';
import { TieredExecutor } from './executor';
import { Database } from 'bun:sqlite';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Worker Pool
// ============================================

interface WorkerState {
  id: number;
  busy: boolean;
  currentTask: string | null;
  completedTasks: number;
  totalTime: number;
}

interface WorkQueue {
  tasks: PlanTask[];
  mutex: boolean;
}

// ============================================
// Parallel Scheduler
// ============================================

export class ParallelScheduler {
  private db: Database;
  private executor: TieredExecutor;
  private maxWorkers: number;
  private workers: WorkerState[];
  private workQueue: WorkQueue;
  private completedTasks: Set<string>;
  private taskResults: Map<string, TaskResult>;
  private vars: Record<string, any>;

  constructor(maxWorkers: number = 4) {
    this.db = new Database(DB_PATH);
    this.executor = new TieredExecutor();
    this.maxWorkers = maxWorkers;
    this.workers = [];
    this.workQueue = { tasks: [], mutex: false };
    this.completedTasks = new Set();
    this.taskResults = new Map();
    this.vars = {};

    // Initialize workers
    for (let i = 0; i < maxWorkers; i++) {
      this.workers.push({
        id: i,
        busy: false,
        currentTask: null,
        completedTasks: 0,
        totalTime: 0,
      });
    }
  }

  /**
   * Execute plan with parallel scheduling
   */
  async execute(plan: PlanIR): Promise<PlanResult> {
    const startTime = Date.now();
    const dag = new DAG(plan);
    const executionId = `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    // Initialize vars from plan
    this.vars = {};
    for (const [name, varDef] of Object.entries(plan.vars)) {
      if (varDef.value !== undefined) {
        this.vars[name] = varDef.value;
      }
    }

    // Reset state
    this.completedTasks.clear();
    this.taskResults.clear();
    this.workQueue.tasks = [];

    // Log execution start
    this.logExecutionStart(executionId, plan);

    try {
      // Execute using work stealing
      await this.executeWithWorkStealing(dag, plan);

      // Collect results
      const taskResults = Array.from(this.taskResults.values());
      const failedTasks = taskResults.filter(r => r.status === 'failed');
      const cachedTasks = taskResults.filter(r => r.cached);

      const endTime = Date.now();
      const status = failedTasks.length === 0 ? 'success' : 'partial';

      // Build outputs
      const outputs: Record<string, any> = {};
      for (const task of plan.tasks) {
        const result = this.taskResults.get(task.task_id);
        if (result?.status === 'success' || result?.status === 'cached') {
          outputs[task.output.var_name] = result.output;
        }
      }

      const result: PlanResult = {
        plan_id: plan.meta.plan_id,
        status,
        outputs,
        task_results: taskResults,
        metrics: {
          total_tasks: plan.tasks.length,
          completed_tasks: this.completedTasks.size,
          failed_tasks: failedTasks.length,
          cached_tasks: cachedTasks.length,
          total_duration_ms: endTime - startTime,
          parallel_efficiency: this.calculateEfficiency(dag, taskResults),
        },
      };

      // Log execution end
      this.logExecutionEnd(executionId, result);

      return result;
    } catch (error: any) {
      const endTime = Date.now();
      return {
        plan_id: plan.meta.plan_id,
        status: 'failed',
        outputs: {},
        task_results: Array.from(this.taskResults.values()),
        metrics: {
          total_tasks: plan.tasks.length,
          completed_tasks: this.completedTasks.size,
          failed_tasks: plan.tasks.length - this.completedTasks.size,
          cached_tasks: 0,
          total_duration_ms: endTime - startTime,
          parallel_efficiency: 0,
        },
      };
    }
  }

  /**
   * Work stealing execution
   */
  private async executeWithWorkStealing(dag: DAG, plan: PlanIR): Promise<void> {
    const maxParallel = plan.constraints?.max_parallel || this.maxWorkers;
    const activeWorkers = Math.min(maxParallel, this.maxWorkers);

    while (this.completedTasks.size < plan.tasks.length) {
      // Get ready tasks
      const readyTasks = dag.getReadyTasks(this.completedTasks);

      if (readyTasks.length === 0 && this.hasActiveWorkers()) {
        // Wait for workers to complete
        await this.sleep(10);
        continue;
      }

      if (readyTasks.length === 0 && !this.hasActiveWorkers()) {
        // Deadlock or all done
        break;
      }

      // Add ready tasks to work queue
      for (const task of readyTasks) {
        if (!this.isTaskQueued(task.task_id) && !this.completedTasks.has(task.task_id)) {
          this.workQueue.tasks.push(task);
        }
      }

      // Dispatch tasks to idle workers
      const idleWorkers = this.workers.filter(w => !w.busy).slice(0, activeWorkers);
      const tasksToDispatch = this.workQueue.tasks.splice(0, idleWorkers.length);

      // Execute in parallel
      const promises = tasksToDispatch.map((task, i) =>
        this.executeTaskOnWorker(idleWorkers[i], task)
      );

      if (promises.length > 0) {
        // Wait for at least one to complete (work stealing opportunity)
        await Promise.race(promises);
      } else {
        await this.sleep(10);
      }
    }
  }

  /**
   * Execute task on specific worker
   */
  private async executeTaskOnWorker(worker: WorkerState, task: PlanTask): Promise<void> {
    worker.busy = true;
    worker.currentTask = task.task_id;
    const startTime = Date.now();

    try {
      const result = await this.executor.execute(task, this.vars);

      // Store result
      this.taskResults.set(task.task_id, result);

      // Update vars if successful
      if (result.status === 'success' || result.status === 'cached') {
        this.vars[task.output.var_name] = result.output;
      }

      this.completedTasks.add(task.task_id);
      worker.completedTasks++;
      worker.totalTime += Date.now() - startTime;
    } catch (error: any) {
      this.taskResults.set(task.task_id, {
        task_id: task.task_id,
        status: 'failed',
        error: { code: 'WORKER_ERROR', message: error.message, retryable: false },
        metrics: {
          start_time: startTime,
          end_time: Date.now(),
          duration_ms: Date.now() - startTime,
          input_bytes: 0,
          output_bytes: 0,
          tier: 'unknown',
        },
        cached: false,
      });
      this.completedTasks.add(task.task_id);
    } finally {
      worker.busy = false;
      worker.currentTask = null;
    }
  }

  /**
   * Check if task is already queued
   */
  private isTaskQueued(taskId: string): boolean {
    return this.workQueue.tasks.some(t => t.task_id === taskId) ||
           this.workers.some(w => w.currentTask === taskId);
  }

  /**
   * Check if any worker is active
   */
  private hasActiveWorkers(): boolean {
    return this.workers.some(w => w.busy);
  }

  /**
   * Calculate parallel efficiency
   */
  private calculateEfficiency(dag: DAG, results: TaskResult[]): number {
    if (results.length === 0) return 0;

    const totalTaskTime = results.reduce((sum, r) => sum + (r.metrics?.duration_ms || 0), 0);
    const wallClockTime = Math.max(...results.map(r => r.metrics?.end_time || 0)) -
                          Math.min(...results.map(r => r.metrics?.start_time || 0));

    if (wallClockTime === 0) return 1;

    // Efficiency = total work / (workers * wall clock time)
    // But we simplify to: total work / wall clock time / max parallelism
    const maxPar = dag.getMaxParallelism();
    return Math.min(1, totalTaskTime / wallClockTime / maxPar);
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Log execution start
   */
  private logExecutionStart(executionId: string, plan: PlanIR): void {
    try {
      this.db.run(
        `INSERT INTO are_execution_log (execution_id, plan_id, status, start_time, total_tasks)
         VALUES (?, ?, 'running', datetime('now'), ?)`,
        [executionId, plan.meta.plan_id, plan.tasks.length]
      );
    } catch (e) {
      // Ignore logging errors
    }
  }

  /**
   * Log execution end
   */
  private logExecutionEnd(executionId: string, result: PlanResult): void {
    try {
      this.db.run(
        `UPDATE are_execution_log SET
           status = ?,
           end_time = datetime('now'),
           duration_ms = ?,
           completed_tasks = ?,
           failed_tasks = ?,
           cached_tasks = ?,
           parallel_efficiency = ?,
           task_results = ?,
           final_outputs = ?
         WHERE execution_id = ?`,
        [
          result.status,
          result.metrics.total_duration_ms,
          result.metrics.completed_tasks,
          result.metrics.failed_tasks,
          result.metrics.cached_tasks,
          result.metrics.parallel_efficiency,
          JSON.stringify(result.task_results),
          JSON.stringify(result.outputs),
          executionId,
        ]
      );
    } catch (e) {
      // Ignore logging errors
    }
  }

  /**
   * Get worker statistics
   */
  getWorkerStats(): WorkerState[] {
    return this.workers.map(w => ({ ...w }));
  }
}

// ============================================
// Export
// ============================================

export const parallelScheduler = new ParallelScheduler();
