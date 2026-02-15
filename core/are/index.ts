/**
 * Agentic Runtime Engine (ARE)
 *
 * The efficient execution engine for AI agents
 * Transforms LLM from "script writer" to "API scheduler"
 *
 * Features:
 * - Plan IR: Structured DAG instead of ad-hoc scripts
 * - Tiered Execution: Cache → Primitive → Script → Sandbox
 * - Telemetry Integration: Optimization based on tel_operations data
 * - REE Integration: Reuse existing scripts and resources
 */

import { Database } from 'bun:sqlite';
import { PlanIR, PlanResult, PlanCacheEntry } from './types';
import { PlanParser, parser } from './compiler/parser';
import { DAG, dagBuilder } from './compiler/dag';
import { Scheduler, scheduler } from './scheduler/executor';
import { ParallelScheduler, parallelScheduler } from './scheduler/parallel';
import { codeExecutor } from './sandbox/executor';
import { planCompiler } from './optimizer/compiler';
import { hotspotDetector } from './optimizer/hotspot';
import { dashboard } from './monitor/dashboard';
import { healthChecker } from './monitor/health';
import { createHash } from 'crypto';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// ARE Main Class
// ============================================

export class ARE {
  private db: Database;
  private parser: PlanParser;
  private parallelMode: boolean = false;

  constructor() {
    this.db = new Database(DB_PATH);
    this.parser = parser;
  }

  /**
   * Execute a plan from JSON Plan IR
   */
  async executeJSON(planJson: string | object): Promise<PlanResult> {
    const plan = this.parser.parseJSON(planJson);
    return this.execute(plan);
  }

  /**
   * Execute a plan from simple text format
   */
  async executeSimple(text: string, intentText?: string): Promise<PlanResult> {
    const plan = this.parser.parseSimple(text, intentText);
    return this.execute(plan);
  }

  /**
   * Enable or disable parallel execution
   */
  setParallelMode(enabled: boolean): void {
    this.parallelMode = enabled;
  }

  /**
   * Execute a Plan IR (with execution history tracking)
   */
  async execute(plan: PlanIR): Promise<PlanResult> {
    const startTime = Date.now();
    const executionId = `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    // Validate plan
    const validation = this.parser.validate(plan);
    if (!validation.valid) {
      const result: PlanResult = {
        plan_id: plan.meta.plan_id,
        status: 'failed',
        outputs: {},
        task_results: [],
        metrics: {
          total_tasks: plan.tasks.length,
          completed_tasks: 0,
          failed_tasks: plan.tasks.length,
          cached_tasks: 0,
          total_duration_ms: 0,
          parallel_efficiency: 0,
        },
      };
      this.logExecution(executionId, plan, result, startTime);
      return result;
    }

    // Check plan cache
    const cachedPlan = await this.lookupPlanCache(plan.meta.intent_hash);
    if (cachedPlan && this.shouldUseCachedPlan(cachedPlan)) {
      // Use cached plan IR (might have optimizations)
      plan = cachedPlan.plan_ir;
    } else {
      // Save new plan to cache
      await this.savePlanToCache(plan);
    }

    // Execute with appropriate scheduler
    let result: PlanResult;
    if (this.parallelMode || (plan.constraints?.max_parallel && plan.constraints.max_parallel > 1)) {
      result = await parallelScheduler.execute(plan);
    } else {
      result = await scheduler.execute(plan);
    }

    // 🔧 记录执行历史
    this.logExecution(executionId, plan, result, startTime);

    return result;
  }

  /**
   * Log execution to are_execution_log
   */
  private logExecution(executionId: string, plan: PlanIR, result: PlanResult, startTime: number): void {
    try {
      const duration = Date.now() - startTime;
      this.db.run(`
        INSERT INTO are_execution_log (
          execution_id, plan_id, intent_hash, status,
          total_tasks, completed_tasks, failed_tasks, cached_tasks,
          duration_ms, parallel_efficiency, start_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
      `, [
        executionId,
        plan.meta.plan_id,
        plan.meta.intent_hash,
        result.status,
        result.metrics.total_tasks,
        result.metrics.completed_tasks,
        result.metrics.failed_tasks,
        result.metrics.cached_tasks,
        duration,
        result.metrics.parallel_efficiency,
      ]);

      // Update plan cache stats
      if (result.status === 'success') {
        this.db.run(`
          UPDATE are_plan_cache
          SET success_count = success_count + 1,
              avg_latency_ms = (avg_latency_ms * success_count + ?) / (success_count + 1),
              last_used_at = datetime('now')
          WHERE intent_hash = ?
        `, [duration, plan.meta.intent_hash]);
      } else {
        this.db.run(`
          UPDATE are_plan_cache
          SET fail_count = fail_count + 1, last_used_at = datetime('now')
          WHERE intent_hash = ?
        `, [plan.meta.intent_hash]);
      }
    } catch (e) {
      // Logging failure should not affect execution
    }
  }

  /**
   * Execute from user intent (compile + execute)
   * This is the high-level API for agent integration
   */
  async executeIntent(intentText: string, context?: Record<string, any>): Promise<PlanResult> {
    // Check plan cache by intent hash
    const intentHash = this.parser.hashIntent(intentText);
    const cachedPlan = await this.lookupPlanCache(intentHash);

    if (cachedPlan && this.shouldUseCachedPlan(cachedPlan)) {
      // Adapt cached plan with new context
      const plan = this.adaptPlan(cachedPlan.plan_ir, context);
      return this.execute(plan);
    }

    // No cached plan - return null to signal LLM should compile
    // (In future: could use LLM to compile here)
    throw new Error('Plan compilation not yet implemented. Please provide Plan IR.');
  }

  /**
   * Look up plan in cache
   */
  private async lookupPlanCache(intentHash: string): Promise<PlanCacheEntry | null> {
    try {
      const row = this.db.query<any, [string]>(
        `SELECT * FROM are_plan_cache WHERE intent_hash = ?`
      ).get(intentHash);

      if (row) {
        return {
          plan_id: row.plan_id,
          intent_hash: row.intent_hash,
          plan_ir: JSON.parse(row.plan_ir),
          success_count: row.success_count,
          fail_count: row.fail_count,
          avg_latency_ms: row.avg_latency_ms,
          created_at: new Date(row.created_at),
          last_used_at: new Date(row.last_used_at),
        };
      }
    } catch (e) {
      // Cache miss
    }
    return null;
  }

  /**
   * Save plan to cache
   */
  private async savePlanToCache(plan: PlanIR): Promise<void> {
    try {
      this.db.run(
        `INSERT OR REPLACE INTO are_plan_cache (plan_id, intent_hash, intent_text, plan_ir, version)
         VALUES (?, ?, ?, ?, ?)`,
        [
          plan.meta.plan_id,
          plan.meta.intent_hash,
          plan.meta.intent_text || '',
          JSON.stringify(plan),
          plan.meta.version,
        ]
      );
    } catch (e) {
      // Ignore cache errors
    }
  }

  /**
   * Decide if cached plan should be used
   */
  private shouldUseCachedPlan(cached: PlanCacheEntry): boolean {
    // Use if success rate > 80%
    const totalExecutions = cached.success_count + cached.fail_count;
    if (totalExecutions < 3) return true; // Not enough data, try it
    const successRate = cached.success_count / totalExecutions;
    return successRate >= 0.8;
  }

  /**
   * Adapt cached plan with new context/params
   */
  private adaptPlan(plan: PlanIR, context?: Record<string, any>): PlanIR {
    if (!context) return plan;

    // Update input vars with context
    const adapted = { ...plan };
    adapted.vars = { ...plan.vars };

    for (const [key, value] of Object.entries(context)) {
      if (adapted.vars[key]) {
        adapted.vars[key] = { ...adapted.vars[key], value };
      } else {
        adapted.vars[key] = { type: 'input', value };
      }
    }

    return adapted;
  }

  /**
   * Build DAG for visualization/analysis
   */
  buildDAG(plan: PlanIR): DAG {
    return dagBuilder.build(plan);
  }

  /**
   * Get telemetry-based optimization suggestions
   */
  async getOptimizationSuggestions(): Promise<any[]> {
    const suggestions: any[] = [];

    // Query hotspots from existing telemetry
    const hotspots = this.db.query(`
      SELECT
        category || ':' || operation as pattern,
        COUNT(*) as frequency,
        AVG(duration_ms) as avg_latency,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
      FROM tel_operations
      WHERE timestamp > datetime('now', '-7 days')
      GROUP BY category, operation
      HAVING COUNT(*) > 10
      ORDER BY frequency DESC
      LIMIT 20
    `).all() as any[];

    for (const hotspot of hotspots) {
      if (hotspot.avg_latency > 100 && hotspot.frequency > 50) {
        suggestions.push({
          type: 'cache_optimization',
          pattern: hotspot.pattern,
          reason: `High frequency (${hotspot.frequency}) with slow latency (${hotspot.avg_latency.toFixed(0)}ms)`,
          suggestion: 'Consider adding result caching or promoting to AOT',
        });
      }

      if (hotspot.success_rate < 0.9) {
        suggestions.push({
          type: 'reliability',
          pattern: hotspot.pattern,
          reason: `Low success rate (${(hotspot.success_rate * 100).toFixed(1)}%)`,
          suggestion: 'Investigate failures and add retry logic',
        });
      }
    }

    return suggestions;
  }

  /**
   * Get execution statistics
   */
  async getStats(): Promise<any> {
    const planCount = this.db.query(`SELECT COUNT(*) as count FROM are_plan_cache`).get() as any;
    const execCount = this.db.query(`SELECT COUNT(*) as count FROM are_execution_log`).get() as any;
    const cacheStats = this.db.query(`
      SELECT
        COUNT(*) as entries,
        SUM(hit_count) as total_hits,
        SUM(size_bytes) as total_bytes
      FROM are_result_cache
    `).get() as any;

    const recentSuccess = this.db.query(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
      FROM are_execution_log
      WHERE start_time > datetime('now', '-1 day')
    `).get() as any;

    return {
      plans_cached: planCount?.count || 0,
      total_executions: execCount?.count || 0,
      result_cache: {
        entries: cacheStats?.entries || 0,
        total_hits: cacheStats?.total_hits || 0,
        total_bytes: cacheStats?.total_bytes || 0,
      },
      recent_24h: {
        executions: recentSuccess?.total || 0,
        success_rate: recentSuccess?.total > 0
          ? ((recentSuccess.success / recentSuccess.total) * 100).toFixed(1) + '%'
          : 'N/A',
      },
    };
  }
}

// ============================================
// CLI Interface
// ============================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const cmd = args[0];

  const are = new ARE();

  switch (cmd) {
    case 'execute':
    case 'exec': {
      // Execute from stdin or file
      // Options: --parallel, --serial
      const parallel = args.includes('--parallel') || args.includes('-p');
      const input = args.filter(a => !a.startsWith('-'))[1] || await Bun.stdin.text();
      try {
        const plan = parser.parseJSON(input);
        const dag = are.buildDAG(plan);
        console.log(dag.toAscii());
        console.log(`\nExecuting (${parallel ? 'parallel' : 'serial'})...\n`);

        are.setParallelMode(parallel);
        const result = await are.execute(plan);
        console.log('Result:', JSON.stringify(result, null, 2));
      } catch (e: any) {
        console.error('Error:', e.message);
        process.exit(1);
      }
      break;
    }

    case 'sandbox':
    case 'code': {
      // Execute code in sandbox
      const language = args[1] as 'python' | 'javascript' | 'typescript' | 'bash' || 'python';
      const code = args[2] || await Bun.stdin.text();
      try {
        console.log(`Executing ${language} code in sandbox...\n`);
        const result = await codeExecutor.execute({
          code,
          language,
        });
        console.log('Status:', result.status);
        console.log('Exit Code:', result.exit_code);
        console.log('Duration:', result.metrics.duration_ms, 'ms');
        if (result.stdout) console.log('\nStdout:\n', result.stdout);
        if (result.stderr) console.log('\nStderr:\n', result.stderr);
      } catch (e: any) {
        console.error('Error:', e.message);
        process.exit(1);
      }
      break;
    }

    case 'parse': {
      // Parse and show DAG
      const input = args.slice(1).join(' ') || await Bun.stdin.text();
      try {
        const plan = input.trim().startsWith('{')
          ? parser.parseJSON(input)
          : parser.parseSimple(input);
        console.log('Plan IR:', JSON.stringify(plan, null, 2));
        console.log('\n' + are.buildDAG(plan).toAscii());
      } catch (e: any) {
        console.error('Parse error:', e.message);
        process.exit(1);
      }
      break;
    }

    case 'stats': {
      const stats = await are.getStats();
      console.log('ARE Statistics:');
      console.log(JSON.stringify(stats, null, 2));
      break;
    }

    case 'optimize': {
      const suggestions = await are.getOptimizationSuggestions();
      console.log('Optimization Suggestions:');
      for (const s of suggestions) {
        console.log(`\n[${s.type}] ${s.pattern}`);
        console.log(`  Reason: ${s.reason}`);
        console.log(`  Suggestion: ${s.suggestion}`);
      }
      if (suggestions.length === 0) {
        console.log('No optimization suggestions at this time.');
      }
      break;
    }

    // Phase 4: JIT/AOT Compilation
    case 'compile': {
      const mode = args[1] as 'jit' | 'aot' || 'jit';
      const input = args[2] || await Bun.stdin.text();
      try {
        const plan = parser.parseJSON(input);
        const compiled = mode === 'aot'
          ? planCompiler.compileAOT(plan)
          : planCompiler.compileJIT(plan);
        console.log(`Compiled Plan (${mode.toUpperCase()}):`);
        console.log(JSON.stringify(compiled, null, 2));
      } catch (e: any) {
        console.error('Compile error:', e.message);
        process.exit(1);
      }
      break;
    }

    case 'hotspots': {
      const action = args[1] || 'list';
      if (action === 'list') {
        const candidates = await hotspotDetector.detectHotspots();
        console.log('Hotspot Candidates:');
        console.log('─'.repeat(80));
        for (const c of candidates) {
          const statusIcon = c.recommendation === 'promote' ? '🔥' : c.recommendation === 'demote' ? '❄️' : '•';
          console.log(`${statusIcon} ${c.pattern.slice(0, 40).padEnd(40)} ${c.current_mode.padEnd(4)} exec:${String(c.execution_count).padStart(4)} success:${(c.success_rate * 100).toFixed(0)}%`);
        }
        if (candidates.length === 0) {
          console.log('No hotspot candidates found (need more execution data).');
        }
      } else if (action === 'auto') {
        const result = await hotspotDetector.autoPromote();
        console.log(`Auto-promotion complete: ${result.promoted} promoted, ${result.demoted} demoted`);
      } else if (action === 'stats') {
        const stats = hotspotDetector.getStats();
        console.log('Hotspot Statistics:');
        console.log(JSON.stringify(stats, null, 2));
      }
      break;
    }

    // Phase 5: Production Monitoring
    case 'dashboard': {
      const period = (args[1] || '24h') as '1h' | '24h' | '7d';
      const metrics = dashboard.getMetrics(period);
      console.log(dashboard.formatAscii(metrics));
      break;
    }

    case 'health': {
      const status = await healthChecker.check();
      console.log(healthChecker.formatAscii(status));

      // Also check alerts
      const alerts = await healthChecker.evaluateAlerts();
      if (alerts.length > 0) {
        console.log('\n⚠️  Active Alerts:');
        for (const alert of alerts) {
          const icon = alert.severity === 'critical' ? '🔴' : alert.severity === 'warning' ? '🟡' : '🔵';
          console.log(`  ${icon} [${alert.severity}] ${alert.message}`);
        }
      }
      break;
    }

    case 'realtime': {
      const stats = dashboard.getRealtimeStats();
      console.log('Real-time Stats:');
      console.log(`  Executions/min: ${stats.executions_per_minute}`);
      console.log(`  Current latency: ${stats.current_latency_ms.toFixed(0)}ms`);
      console.log(`  Error rate: ${(stats.error_rate * 100).toFixed(1)}%`);
      console.log(`  Active plans: ${stats.active_plans}`);
      break;
    }

    default:
      console.log(`
Agentic Runtime Engine (ARE) v2.0

Usage:
  bun are/index.ts exec [options] <plan.json>   Execute a Plan IR
  bun are/index.ts parse <text>                 Parse and show DAG
  bun are/index.ts sandbox <lang> <code>        Execute code in sandbox
  bun are/index.ts stats                        Show statistics
  bun are/index.ts optimize                     Get optimization suggestions

Compilation (Phase 4):
  bun are/index.ts compile [jit|aot] <plan>     Compile plan to optimized IR
  bun are/index.ts hotspots [list|auto|stats]   Hotspot detection & promotion

Monitoring (Phase 5):
  bun are/index.ts dashboard [1h|24h|7d]        Production dashboard
  bun are/index.ts health                       Health check & alerts
  bun are/index.ts realtime                     Real-time stats

Options:
  -p, --parallel    Enable parallel execution

Supported Languages (sandbox):
  python, javascript, typescript, bash

Example Plan IR:
{
  "meta": { "intent_text": "Get weather for Beijing" },
  "vars": { "city": { "type": "input", "value": "Beijing" } },
  "tasks": [
    {
      "task_id": "t1",
      "name": "Fetch weather",
      "action": { "type": "script", "target": "weather-fetch", "params": { "city": "\${city}" } },
      "depends_on": [],
      "output": { "var_name": "weather" }
    }
  ],
  "constraints": { "timeout_ms": 30000, "max_parallel": 4 }
}

Action Types:
  primitive  - Built-in operations (fs.read, db.query, etc.)
  script     - REE cached scripts (sys_scripts)
  mcp        - MCP tools
  shortcut   - Apple Shortcuts
  code       - Sandboxed code execution
`);
  }
}

// Export
export { parser, dagBuilder, scheduler, parallelScheduler, codeExecutor };
export { planCompiler, hotspotDetector };
export { dashboard, healthChecker };
export * from './types';
export * from './sandbox/types';
export * from './optimizer/compiler';
export * from './optimizer/hotspot';
export * from './monitor/dashboard';
export * from './monitor/health';
