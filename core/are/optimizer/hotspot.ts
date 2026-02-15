/**
 * ARE Hotspot Detector
 *
 * Detect frequently executed plans and promote to AOT
 */

import { Database } from 'bun:sqlite';
import { PlanIR } from '../types';
import { PlanCompiler, planCompiler } from './compiler';
import { createHash } from 'crypto';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Hotspot Configuration
// ============================================

export interface HotspotConfig {
  // Minimum executions to consider for AOT
  min_executions: number;

  // Minimum success rate for AOT promotion
  min_success_rate: number;

  // Maximum latency improvement expected (for prioritization)
  target_latency_improvement: number;

  // Cooldown period after promotion (hours)
  promotion_cooldown_hours: number;
}

export const DEFAULT_HOTSPOT_CONFIG: HotspotConfig = {
  min_executions: 10,
  min_success_rate: 0.8,
  target_latency_improvement: 0.2, // 20% improvement
  promotion_cooldown_hours: 24,
};

// ============================================
// Hotspot Candidate
// ============================================

export interface HotspotCandidate {
  plan_id: string;
  intent_hash: string;
  pattern: string;
  execution_count: number;
  success_rate: number;
  avg_latency_ms: number;
  last_executed: string;
  current_mode: 'jit' | 'aot';
  recommendation: 'promote' | 'demote' | 'keep';
  expected_improvement: number;
}

// ============================================
// Hotspot Detector
// ============================================

export class HotspotDetector {
  private db: Database;
  private config: HotspotConfig;
  private compiler: PlanCompiler;

  constructor(config?: Partial<HotspotConfig>) {
    this.db = new Database(DB_PATH);
    this.config = { ...DEFAULT_HOTSPOT_CONFIG, ...config };
    this.compiler = planCompiler;
  }

  /**
   * Detect hotspot candidates
   */
  async detectHotspots(): Promise<HotspotCandidate[]> {
    const candidates: HotspotCandidate[] = [];

    // Query execution statistics
    const stats = this.db.query(`
      SELECT
        p.plan_id,
        p.intent_hash,
        COALESCE(p.intent_text, 'unknown') as pattern,
        p.success_count + p.fail_count as execution_count,
        CASE
          WHEN (p.success_count + p.fail_count) > 0
          THEN CAST(p.success_count AS REAL) / (p.success_count + p.fail_count)
          ELSE 0
        END as success_rate,
        COALESCE(p.avg_latency_ms, 0) as avg_latency_ms,
        p.last_used_at,
        COALESCE(p.compile_mode, 'jit') as compile_mode
      FROM are_plan_cache p
      WHERE (p.success_count + p.fail_count) >= ?
      ORDER BY execution_count DESC
      LIMIT 50
    `).all(this.config.min_executions) as any[];

    for (const stat of stats) {
      const candidate = this.analyzeCandidate(stat);
      candidates.push(candidate);
    }

    return candidates;
  }

  /**
   * Analyze a candidate for promotion/demotion
   */
  private analyzeCandidate(stat: any): HotspotCandidate {
    const isHot = stat.execution_count >= this.config.min_executions;
    const isReliable = stat.success_rate >= this.config.min_success_rate;
    const isJIT = stat.compile_mode === 'jit';
    const isAOT = stat.compile_mode === 'aot';

    let recommendation: HotspotCandidate['recommendation'] = 'keep';
    let expectedImprovement = 0;

    if (isHot && isReliable && isJIT) {
      // Promote to AOT
      recommendation = 'promote';
      expectedImprovement = this.config.target_latency_improvement;
    } else if (isAOT && !isReliable) {
      // Demote if unreliable
      recommendation = 'demote';
      expectedImprovement = -0.1; // Slight penalty for switching back
    } else if (isAOT && stat.execution_count < this.config.min_executions / 2) {
      // Demote if no longer hot
      recommendation = 'demote';
      expectedImprovement = 0;
    }

    return {
      plan_id: stat.plan_id,
      intent_hash: stat.intent_hash,
      pattern: stat.pattern,
      execution_count: stat.execution_count,
      success_rate: stat.success_rate,
      avg_latency_ms: stat.avg_latency_ms,
      last_executed: stat.last_used_at || 'unknown',
      current_mode: stat.compile_mode,
      recommendation,
      expected_improvement: expectedImprovement,
    };
  }

  /**
   * Promote a plan to AOT
   */
  async promote(planId: string): Promise<boolean> {
    try {
      // Load plan IR
      const row = this.db.query<{ plan_ir: string }, [string]>(
        `SELECT plan_ir FROM are_plan_cache WHERE plan_id = ?`
      ).get(planId);

      if (!row) return false;

      const plan: PlanIR = JSON.parse(row.plan_ir);

      // Compile AOT
      const compiled = this.compiler.compileAOT(plan);

      // Save compiled plan
      await this.compiler.saveCompiled(compiled);

      // Log promotion
      this.logPromotion(planId, 'jit', 'aot', compiled.optimizations);

      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * Demote a plan back to JIT
   */
  async demote(planId: string): Promise<boolean> {
    try {
      this.db.run(
        `UPDATE are_plan_cache SET compile_mode = 'jit', compiled_artifact = NULL WHERE plan_id = ?`,
        [planId]
      );

      // Log demotion
      this.logPromotion(planId, 'aot', 'jit', ['demoted']);

      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * Auto-promote all eligible candidates
   */
  async autoPromote(): Promise<{ promoted: number; demoted: number }> {
    const candidates = await this.detectHotspots();
    let promoted = 0;
    let demoted = 0;

    for (const candidate of candidates) {
      if (candidate.recommendation === 'promote') {
        if (await this.promote(candidate.plan_id)) {
          promoted++;
        }
      } else if (candidate.recommendation === 'demote') {
        if (await this.demote(candidate.plan_id)) {
          demoted++;
        }
      }
    }

    return { promoted, demoted };
  }

  /**
   * Log promotion/demotion
   */
  private logPromotion(planId: string, from: string, to: string, optimizations: string[]): void {
    try {
      this.db.run(
        `INSERT INTO are_optimization_log (
           optimization_type, target, old_value, new_value, evidence, applied, applied_at
         ) VALUES (?, ?, ?, ?, ?, true, datetime('now'))`,
        [
          to === 'aot' ? 'jit_to_aot' : 'aot_to_jit',
          planId,
          from,
          to,
          JSON.stringify({ optimizations }),
        ]
      );
    } catch (e) {
      // Ignore logging errors
    }
  }

  /**
   * Record task execution for hotspot tracking
   */
  recordExecution(pattern: string, latencyMs: number, success: boolean): void {
    const patternHash = createHash('sha256').update(pattern).digest('hex').slice(0, 16);

    try {
      // Upsert hotspot record
      this.db.run(`
        INSERT INTO are_hotspots (pattern_hash, task_pattern, execution_count, last_executed, avg_latency_ms)
        VALUES (?, ?, 1, datetime('now'), ?)
        ON CONFLICT(pattern_hash) DO UPDATE SET
          execution_count = execution_count + 1,
          last_executed = datetime('now'),
          avg_latency_ms = (avg_latency_ms * execution_count + ?) / (execution_count + 1),
          updated_at = datetime('now')
      `, [patternHash, pattern, latencyMs, latencyMs]);
    } catch (e) {
      // Ignore tracking errors
    }
  }

  /**
   * Get hotspot statistics
   */
  getStats(): any {
    const totalPlans = this.db.query(`SELECT COUNT(*) as count FROM are_plan_cache`).get() as any;
    const aotPlans = this.db.query(`SELECT COUNT(*) as count FROM are_plan_cache WHERE compile_mode = 'aot'`).get() as any;
    const hotspots = this.db.query(`SELECT COUNT(*) as count FROM are_hotspots WHERE execution_count >= ?`).get(this.config.min_executions) as any;

    const recentPromotions = this.db.query(`
      SELECT COUNT(*) as count FROM are_optimization_log
      WHERE optimization_type = 'jit_to_aot' AND applied_at > datetime('now', '-24 hours')
    `).get() as any;

    return {
      total_plans: totalPlans?.count || 0,
      aot_plans: aotPlans?.count || 0,
      jit_plans: (totalPlans?.count || 0) - (aotPlans?.count || 0),
      hot_patterns: hotspots?.count || 0,
      recent_promotions_24h: recentPromotions?.count || 0,
      config: this.config,
    };
  }
}

// ============================================
// Export
// ============================================

export const hotspotDetector = new HotspotDetector();
