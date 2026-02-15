/**
 * ARE Scheduler & Executor
 *
 * Execute Plan IR with tiered execution and caching
 */

import { Database } from 'bun:sqlite';
import { PlanIR, PlanTask, TaskResult, PlanResult, ExecutionState, TaskMetrics, PRIMITIVES } from '../types';
import { DAG, dagBuilder } from '../compiler/dag';
import { codeExecutor } from '../sandbox/executor';
import { createHash } from 'crypto';
import { getBus, getNetwork, getHeartbeat } from '../../agent/bus';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Tiered Executor
// ============================================

export class TieredExecutor {
  private db: Database;
  private executionCount: number = 0;
  private successCount: number = 0;
  private heartbeatInitialized: boolean = false;

  constructor() {
    this.db = new Database(DB_PATH);
    this.db.run('PRAGMA busy_timeout = 5000'); // Avoid lock conflicts
    // Heartbeat 延迟初始化，避免阻塞简单测试
  }

  private initHeartbeat() {
    if (this.heartbeatInitialized) return;
    try {
      const heartbeat = getHeartbeat();
      heartbeat.register('are-executor', { type: 'executor' });
      setInterval(() => {
        heartbeat.beat('are-executor', {
          executions: this.executionCount,
          successes: this.successCount,
          successRate: this.executionCount > 0 ? this.successCount / this.executionCount : 0,
        });
      }, 5000);
      this.heartbeatInitialized = true;
    } catch (e) {
      // Heartbeat optional
    }
  }

  /**
   * Track result and update metrics
   */
  private trackResult(result: TaskResult): TaskResult {
    if (result.status === 'success' || result.status === 'cached') {
      this.successCount++;
    }
    return result;
  }

  /**
   * Execute a single task with tiered strategy (wrapper with tracking)
   */
  async execute(task: PlanTask, vars: Record<string, any>): Promise<TaskResult> {
    this.executionCount++;
    const result = await this._executeInternal(task, vars);
    return this.trackResult(result);
  }

  /**
   * Internal execute implementation
   */
  private async _executeInternal(task: PlanTask, vars: Record<string, any>): Promise<TaskResult> {
    const startTime = Date.now();
    const resolvedParams = this.resolveParams(task.action.params, vars);
    const cacheKey = this.computeCacheKey(task, resolvedParams);

    // Tier 0: Hot Cache (Result Cache)
    const cached = this.checkCache(cacheKey);
    if (cached !== null) {
      return {
        task_id: task.task_id,
        status: 'cached',
        output: cached,
        metrics: this.createMetrics(startTime, 'cache', 0, JSON.stringify(cached).length),
        cached: true,
        cache_key: cacheKey,
      };
    }

    // Tier 1: Native Primitives
    if (task.action.type === 'primitive') {
      const primitive = PRIMITIVES[task.action.target];
      if (primitive) {
        try {
          const result = await this.executePrimitive(task.action.target, resolvedParams);
          this.saveToCache(cacheKey, result, task.constraints?.cache_ttl_s);
          return {
            task_id: task.task_id,
            status: 'success',
            output: result,
            metrics: this.createMetrics(startTime, 'primitive', JSON.stringify(resolvedParams).length, JSON.stringify(result).length),
            cached: false,
          };
        } catch (error: any) {
          return {
            task_id: task.task_id,
            status: 'failed',
            error: { code: 'PRIMITIVE_ERROR', message: error.message, retryable: true },
            metrics: this.createMetrics(startTime, 'primitive', 0, 0),
            cached: false,
          };
        }
      }
    }

    // Tier 2: Script Cache (REE integration)
    if (task.action.type === 'script') {
      try {
        const result = await this.executeScript(task.action.target, resolvedParams);
        this.saveToCache(cacheKey, result, task.constraints?.cache_ttl_s);
        return {
          task_id: task.task_id,
          status: 'success',
          output: result,
          metrics: this.createMetrics(startTime, 'script', JSON.stringify(resolvedParams).length, JSON.stringify(result).length),
          cached: false,
        };
      } catch (error: any) {
        return {
          task_id: task.task_id,
          status: 'failed',
          error: { code: 'SCRIPT_ERROR', message: error.message, retryable: true },
          metrics: this.createMetrics(startTime, 'script', 0, 0),
          cached: false,
        };
      }
    }

    // Tier 3: MCP Tools
    if (task.action.type === 'mcp') {
      try {
        const result = await this.executeMCP(task.action.target, resolvedParams);
        return {
          task_id: task.task_id,
          status: 'success',
          output: result,
          metrics: this.createMetrics(startTime, 'script', JSON.stringify(resolvedParams).length, JSON.stringify(result).length),
          cached: false,
        };
      } catch (error: any) {
        return {
          task_id: task.task_id,
          status: 'failed',
          error: { code: 'MCP_ERROR', message: error.message, retryable: true },
          metrics: this.createMetrics(startTime, 'script', 0, 0),
          cached: false,
        };
      }
    }

    // Tier 4: Shortcut
    if (task.action.type === 'shortcut') {
      try {
        const result = await this.executeShortcut(task.action.target, resolvedParams);
        return {
          task_id: task.task_id,
          status: 'success',
          output: result,
          metrics: this.createMetrics(startTime, 'shortcut', JSON.stringify(resolvedParams).length, JSON.stringify(result).length),
          cached: false,
        };
      } catch (error: any) {
        return {
          task_id: task.task_id,
          status: 'failed',
          error: { code: 'SHORTCUT_ERROR', message: error.message, retryable: false },
          metrics: this.createMetrics(startTime, 'shortcut', 0, 0),
          cached: false,
        };
      }
    }

    // Tier 5: Code (Sandbox)
    if (task.action.type === 'code') {
      try {
        const language = task.action.target as 'python' | 'javascript' | 'typescript' | 'bash';
        const code = resolvedParams.code || resolvedParams.source || '';
        const execResult = await codeExecutor.execute({
          code,
          language,
          stdin: resolvedParams.stdin,
          args: resolvedParams.args,
          config: {
            timeout_ms: task.constraints?.timeout_ms,
            memory_mb: resolvedParams.memory_mb,
            network: resolvedParams.network,
          },
        });

        if (execResult.status === 'success') {
          // Try to parse stdout as JSON
          let output: any = execResult.stdout;
          try {
            output = JSON.parse(execResult.stdout.trim());
          } catch {}

          this.saveToCache(cacheKey, output, task.constraints?.cache_ttl_s);
          return {
            task_id: task.task_id,
            status: 'success',
            output,
            metrics: this.createMetrics(startTime, 'sandbox', code.length, execResult.stdout.length),
            cached: false,
          };
        } else {
          return {
            task_id: task.task_id,
            status: 'failed',
            error: {
              code: execResult.status === 'timeout' ? 'TIMEOUT' : execResult.status === 'oom' ? 'OOM' : 'CODE_ERROR',
              message: execResult.stderr || `Code execution ${execResult.status}`,
              retryable: execResult.status === 'timeout',
            },
            metrics: this.createMetrics(startTime, 'sandbox', code.length, 0),
            cached: false,
          };
        }
      } catch (error: any) {
        return {
          task_id: task.task_id,
          status: 'failed',
          error: { code: 'SANDBOX_ERROR', message: error.message, retryable: true },
          metrics: this.createMetrics(startTime, 'sandbox', 0, 0),
          cached: false,
        };
      }
    }

    // Unknown action type
    return {
      task_id: task.task_id,
      status: 'failed',
      error: { code: 'UNKNOWN_ACTION', message: `Unknown action type: ${task.action.type}`, retryable: false },
      metrics: this.createMetrics(startTime, 'sandbox', 0, 0),
      cached: false,
    };
  }

  /**
   * Resolve variable references in params
   */
  private resolveParams(params: Record<string, any>, vars: Record<string, any>): Record<string, any> {
    const resolved: Record<string, any> = {};

    for (const [key, value] of Object.entries(params)) {
      if (typeof value === 'string') {
        // Replace ${var} references
        resolved[key] = value.replace(/\$\{([^}]+)\}/g, (_, path) => {
          const parts = path.split('.');
          let result = vars[parts[0]];
          for (let i = 1; i < parts.length && result !== undefined; i++) {
            result = result[parts[i]];
          }
          return result !== undefined ? (typeof result === 'object' ? JSON.stringify(result) : String(result)) : '';
        });
      } else {
        resolved[key] = value;
      }
    }

    return resolved;
  }

  /**
   * Compute cache key for task + params
   */
  private computeCacheKey(task: PlanTask, params: Record<string, any>): string {
    const content = `${task.action.type}:${task.action.target}:${JSON.stringify(params)}`;
    return createHash('sha256').update(content).digest('hex').slice(0, 32);
  }

  /**
   * Check result cache
   */
  private checkCache(key: string): any | null {
    try {
      const row = this.db.query<{ result: string }, [string]>(
        `SELECT result FROM are_result_cache
         WHERE cache_key = ? AND (expires_at IS NULL OR expires_at > datetime('now'))`
      ).get(key);

      if (row) {
        // Update hit count
        this.db.run(
          `UPDATE are_result_cache SET hit_count = hit_count + 1, last_hit = datetime('now') WHERE cache_key = ?`,
          [key]
        );
        return JSON.parse(row.result);
      }
    } catch (e) {
      // Cache miss
    }
    return null;
  }

  /**
   * Save to result cache
   */
  private saveToCache(key: string, result: any, ttlSeconds?: number): void {
    try {
      const resultJson = JSON.stringify(result);
      const expiresAt = ttlSeconds ? `datetime('now', '+${ttlSeconds} seconds')` : 'NULL';

      this.db.run(
        `INSERT OR REPLACE INTO are_result_cache (cache_key, result, size_bytes, expires_at)
         VALUES (?, ?, ?, ${expiresAt})`,
        [key, resultJson, resultJson.length]
      );
    } catch (e) {
      // Ignore cache errors
    }
  }

  /**
   * Execute primitive operation
   */
  private async executePrimitive(name: string, params: Record<string, any>): Promise<any> {
    switch (name) {
      case 'fs.read': {
        const file = Bun.file(params.path);
        return await file.text();
      }
      case 'fs.write': {
        await Bun.write(params.path, params.content);
        return { success: true };
      }
      case 'fs.exists': {
        const file = Bun.file(params.path);
        return await file.exists();
      }
      case 'fs.list': {
        const { Glob } = await import('bun');
        const glob = new Glob(params.pattern || '*');
        const files: string[] = [];
        for await (const file of glob.scan({ cwd: params.path, absolute: true })) {
          files.push(file);
        }
        return files;
      }
      case 'db.query': {
        const stmt = this.db.query(params.sql);
        return params.params ? stmt.all(...params.params) : stmt.all();
      }
      case 'db.exec': {
        this.db.run(params.sql, params.params || []);
        return { success: true };
      }
      case 'json.parse': {
        return JSON.parse(params.text);
      }
      case 'json.stringify': {
        return JSON.stringify(params.value, null, params.pretty ? 2 : 0);
      }
      case 'json.path': {
        const parts = params.path.split('.');
        let result = params.obj;
        for (const part of parts) {
          if (result === undefined) break;
          result = result[part];
        }
        return result;
      }
      case 'text.regex': {
        const regex = new RegExp(params.pattern, params.flags || 'g');
        return params.text.match(regex) || [];
      }
      case 'text.template': {
        let result = params.template;
        for (const [key, value] of Object.entries(params.vars)) {
          result = result.replace(new RegExp(`\\$\\{${key}\\}`, 'g'), String(value));
        }
        return result;
      }
      case 'sys.exec': {
        const proc = Bun.spawn(params.args ? [params.cmd, ...params.args] : params.cmd.split(' '), {
          cwd: params.cwd,
          stdout: 'pipe',
          stderr: 'pipe',
        });
        const stdout = await new Response(proc.stdout).text();
        const stderr = await new Response(proc.stderr).text();
        const code = await proc.exited;
        return { stdout, stderr, code };
      }
      case 'sys.env': {
        return process.env[params.name] || '';
      }
      case 'net.fetch': {
        // Use Message Bus Network Adapter for:
        // - Caching
        // - Rate limiting
        // - Retry logic
        // - Centralized monitoring
        const bus = getBus();
        const network = getNetwork();

        // Start bus if not running
        if (!bus.getStats().running) {
          bus.start();
        }

        const method = params.options?.method || 'GET';
        const cacheTtl = params.options?.cache_ttl_ms || 60000;  // Default 1 minute cache

        let response;
        if (method === 'GET') {
          response = await network.get(params.url, {
            headers: params.options?.headers,
            timeout_ms: params.options?.timeout || 30000,
            cache_ttl_ms: cacheTtl,
          });
        } else {
          response = await network.post(params.url, params.options?.body, {
            headers: params.options?.headers,
            timeout_ms: params.options?.timeout || 30000,
          });
        }

        return {
          status: response.status,
          headers: response.headers,
          body: response.body,
          cached: response.cached,
          latency_ms: response.latency_ms,
        };
      }
      // === 新增原语 ===
      case 'shell.run': {
        // Alias for sys.exec
        const proc = Bun.spawn(params.args ? [params.cmd, ...params.args] : params.cmd.split(' '), {
          cwd: params.cwd,
          stdout: 'pipe',
          stderr: 'pipe',
        });
        const stdout = await new Response(proc.stdout).text();
        const stderr = await new Response(proc.stderr).text();
        const code = await proc.exited;
        return { stdout, stderr, code, success: code === 0 };
      }
      case 'http.get': {
        // Alias for net.fetch GET
        const response = await fetch(params.url, { headers: params.headers });
        return { status: response.status, body: await response.text() };
      }
      case 'http.post': {
        const response = await fetch(params.url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...params.headers },
          body: JSON.stringify(params.body),
        });
        return { status: response.status, body: await response.text() };
      }
      case 'db.insert': {
        this.db.run(params.sql, params.params || []);
        return { success: true, lastInsertRowid: this.db.query('SELECT last_insert_rowid()').get() };
      }
      case 'data.merge': {
        return { ...params.a, ...params.b };
      }
      case 'data.filter': {
        const arr = Array.isArray(params.data) ? params.data : [];
        if (params.key && params.value !== undefined) {
          return arr.filter((item: any) => item[params.key] === params.value);
        }
        return arr;
      }
      case 'notify.log': {
        console.log(`[ARE] ${params.message}`);
        return { logged: true, message: params.message };
      }
      case 'notify.alert': {
        // Use osascript for macOS notification
        const proc = Bun.spawn(['osascript', '-e', `display notification "${params.message}" with title "${params.title || 'Solar'}"`]);
        await proc.exited;
        return { notified: true };
      }
      case 'text.extract': {
        const regex = new RegExp(params.pattern, params.flags || 'g');
        const matches = params.text.match(regex);
        return matches || [];
      }
      default:
        throw new Error(`Unknown primitive: ${name}`);
    }
  }

  /**
   * Execute cached script via REE
   */
  private async executeScript(scriptId: string, params: Record<string, any>): Promise<any> {
    // Query script from sys_scripts
    const script = this.db.query<{ file_path: string; runtime: string }, [string]>(
      `SELECT file_path, runtime FROM sys_scripts WHERE script_id = ? OR name = ?`
    ).get(scriptId, scriptId);

    if (!script) {
      throw new Error(`Script not found: ${scriptId}`);
    }

    // Expand ~ to home directory
    const filePath = script.file_path.replace(/^~/, process.env.HOME || '');

    // Execute based on runtime
    const args = Object.entries(params).map(([k, v]) => `--${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`);
    const proc = Bun.spawn(['bun', filePath, ...args], {
      stdout: 'pipe',
      stderr: 'pipe',
    });

    const stdout = await new Response(proc.stdout).text();
    const code = await proc.exited;

    if (code !== 0) {
      const stderr = await new Response(proc.stderr).text();
      throw new Error(`Script failed: ${stderr}`);
    }

    // Try to parse as JSON
    try {
      return JSON.parse(stdout.trim());
    } catch {
      return stdout.trim();
    }
  }

  /**
   * Execute MCP tool
   */
  private async executeMCP(tool: string, params: Record<string, any>): Promise<any> {
    // TODO: Integrate with MCP client
    throw new Error(`MCP execution not yet implemented: ${tool}`);
  }

  /**
   * Execute Apple Shortcut
   */
  private async executeShortcut(name: string, params: Record<string, any>): Promise<any> {
    const input = JSON.stringify(params);
    const proc = Bun.spawn(['shortcuts', 'run', name, '-i', input], {
      stdout: 'pipe',
      stderr: 'pipe',
    });

    const stdout = await new Response(proc.stdout).text();
    const code = await proc.exited;

    if (code !== 0) {
      const stderr = await new Response(proc.stderr).text();
      throw new Error(`Shortcut failed: ${stderr}`);
    }

    return stdout.trim();
  }

  /**
   * Create task metrics
   */
  private createMetrics(startTime: number, tier: string, inputBytes: number, outputBytes: number): TaskMetrics {
    const endTime = Date.now();
    return {
      start_time: startTime,
      end_time: endTime,
      duration_ms: endTime - startTime,
      input_bytes: inputBytes,
      output_bytes: outputBytes,
      tier: tier as any,
    };
  }
}

// ============================================
// Scheduler
// ============================================

export class Scheduler {
  private executor: TieredExecutor;
  private db: Database;

  constructor() {
    this.executor = new TieredExecutor();
    this.db = new Database(DB_PATH);
    this.db.run('PRAGMA busy_timeout = 5000');
  }

  /**
   * Execute plan (currently serial, Phase 3 will add parallel)
   */
  async execute(plan: PlanIR): Promise<PlanResult> {
    const dag = dagBuilder.build(plan);
    const executionId = `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const state: ExecutionState = {
      status: 'running',
      completed: new Set(),
      failed: new Set(),
      running: new Set(),
      vars: { ...this.extractInputVars(plan) },
      checkpoints: [],
      start_time: Date.now(),
    };

    const taskResults: TaskResult[] = [];

    // Log execution start
    this.logExecutionStart(executionId, plan.meta.plan_id);

    try {
      // Get topological order for serial execution
      const orderedTasks = dag.getTopologicalOrder();

      for (const task of orderedTasks) {
        state.running.add(task.task_id);

        // Execute with retry
        let result = await this.executeWithRetry(task, state.vars, plan.constraints.retry_policy);

        state.running.delete(task.task_id);

        if (result.status === 'success' || result.status === 'cached') {
          state.completed.add(task.task_id);
          state.vars[task.output.var_name] = result.output;
        } else {
          state.failed.add(task.task_id);

          // Check if we should abort
          if (plan.constraints.rollback_on_failure) {
            state.status = 'failed';
            break;
          }
        }

        taskResults.push(result);

        // Log task execution to telemetry
        this.logTaskExecution(executionId, result);
      }

      state.status = state.failed.size > 0 ? (state.completed.size > 0 ? 'partial' : 'failed') : 'completed';
      state.end_time = Date.now();

    } catch (error: any) {
      state.status = 'failed';
      state.end_time = Date.now();
    }

    // Build result
    const planResult: PlanResult = {
      plan_id: plan.meta.plan_id,
      status: state.status === 'completed' ? 'success' : (state.status === 'partial' ? 'partial' : 'failed'),
      outputs: this.extractOutputs(plan, state.vars),
      task_results: taskResults,
      metrics: {
        total_tasks: plan.tasks.length,
        completed_tasks: state.completed.size,
        failed_tasks: state.failed.size,
        cached_tasks: taskResults.filter(r => r.cached).length,
        total_duration_ms: (state.end_time || Date.now()) - (state.start_time || Date.now()),
        parallel_efficiency: dag.getParallelEfficiency(),
      },
    };

    // Log execution end
    this.logExecutionEnd(executionId, planResult);

    // Update plan cache statistics
    this.updatePlanStats(plan.meta.plan_id, planResult);

    return planResult;
  }

  /**
   * Execute task with retry policy
   */
  private async executeWithRetry(
    task: PlanTask,
    vars: Record<string, any>,
    defaultRetry: { max_attempts: number; backoff_ms: number; backoff_multiplier: number }
  ): Promise<TaskResult> {
    const retry = task.constraints?.retry || defaultRetry;
    let lastResult: TaskResult | null = null;

    for (let attempt = 0; attempt < retry.max_attempts; attempt++) {
      if (attempt > 0) {
        const delay = retry.backoff_ms * Math.pow(retry.backoff_multiplier, attempt - 1);
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      lastResult = await this.executor.execute(task, vars);

      if (lastResult.status === 'success' || lastResult.status === 'cached') {
        return lastResult;
      }

      // Check if error is retryable
      if (lastResult.error && !lastResult.error.retryable) {
        return lastResult;
      }
    }

    return lastResult!;
  }

  /**
   * Extract input variables from plan
   */
  private extractInputVars(plan: PlanIR): Record<string, any> {
    const inputs: Record<string, any> = {};
    for (const [name, varDef] of Object.entries(plan.vars)) {
      if (varDef.type === 'input' || varDef.type === 'constant') {
        inputs[name] = varDef.value;
      }
    }
    return inputs;
  }

  /**
   * Extract final outputs from vars
   */
  private extractOutputs(plan: PlanIR, vars: Record<string, any>): Record<string, any> {
    const outputs: Record<string, any> = {};
    // Get outputs from leaf tasks
    for (const task of plan.tasks) {
      outputs[task.output.var_name] = vars[task.output.var_name];
    }
    return outputs;
  }

  /**
   * Log execution start
   */
  private logExecutionStart(executionId: string, planId: string): void {
    try {
      this.db.run(
        `INSERT INTO are_execution_log (execution_id, plan_id, status, start_time)
         VALUES (?, ?, 'running', datetime('now'))`,
        [executionId, planId]
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
           task_results = ?,
           final_outputs = ?,
           total_tasks = ?,
           completed_tasks = ?,
           failed_tasks = ?,
           cached_tasks = ?,
           parallel_efficiency = ?
         WHERE execution_id = ?`,
        [
          result.status,
          result.metrics.total_duration_ms,
          JSON.stringify(result.task_results),
          JSON.stringify(result.outputs),
          result.metrics.total_tasks,
          result.metrics.completed_tasks,
          result.metrics.failed_tasks,
          result.metrics.cached_tasks,
          result.metrics.parallel_efficiency,
          executionId,
        ]
      );
    } catch (e) {
      // Ignore logging errors
    }
  }

  /**
   * Log individual task execution
   */
  private logTaskExecution(executionId: string, result: TaskResult): void {
    try {
      const startTime = result.metrics?.start_time
        ? new Date(result.metrics.start_time).toISOString()
        : new Date().toISOString();
      const endTime = result.metrics?.end_time
        ? new Date(result.metrics.end_time).toISOString()
        : new Date().toISOString();

      this.db.run(
        `INSERT INTO are_task_execution (
           execution_id, task_id, status, tier,
           start_time, end_time, duration_ms, queue_time_ms,
           input_bytes, output_bytes, cached, cache_key,
           error_code, error_message, retry_count
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          executionId,
          result.task_id,
          result.status,
          result.metrics?.tier || 'unknown',
          startTime,
          endTime,
          result.metrics?.duration_ms || 0,
          0, // queue_time_ms - not tracked yet
          result.metrics?.input_bytes || 0,
          result.metrics?.output_bytes || 0,
          result.cached ? 1 : 0,
          result.cache_key || null,
          result.error?.code || null,
          result.error?.message || null,
          0, // retry_count - could be tracked in executeWithRetry
        ]
      );
    } catch (e: any) {
      // Log errors for debugging
      console.error('[ARE] Task logging error:', e?.message || e);
    }
  }

  /**
   * Update plan cache statistics
   */
  private updatePlanStats(planId: string, result: PlanResult): void {
    try {
      const success = result.status === 'success' ? 1 : 0;
      this.db.run(
        `UPDATE are_plan_cache SET
           total_executions = total_executions + 1,
           success_count = success_count + ?,
           fail_count = fail_count + ?,
           avg_latency_ms = (COALESCE(avg_latency_ms, 0) * total_executions + ?) / (total_executions + 1),
           last_used_at = datetime('now')
         WHERE plan_id = ?`,
        [success, 1 - success, result.metrics.total_duration_ms, planId]
      );
    } catch (e) {
      // Ignore
    }
  }
}

export const scheduler = new Scheduler();
