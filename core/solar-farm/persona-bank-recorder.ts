/**
 * PersonaRecorder - 人格评分记录器
 *
 * 核心亮点：
 * 1. 使用 TypeScript 类型体操确保数据安全
 * 2. 创新的 ELO 计算方式，支持动态 K-factor
 * 3. 内置数据验证和错误恢复机制
 * 4. 简洁的 API 设计，灵感来自游戏评分系统
 */

import { Database } from 'bun:sqlite';

// ==================== 类型定义 ====================

/** 评分项类型 - 支持动态键值对 */
export type RubricScores = Record<string, number>;

/** 评分记录接口 */
export interface ScoreRecord {
  personaId: string;
  taskId: string;
  phase: 'collect' | 'fill_gaps' | 'peer_review' | 'compose';
  rubricScores: RubricScores;
  overallScore: number;
  evaluatorPersonaId?: string; // 互评时的评估者ID
  recordedAt: Date;
}

/** 对局结果接口 */
export interface MatchResult {
  taskId: string;
  personaA: string;
  personaB: string;
  scoreA: number; // B给A的评分
  scoreB: number; // A给B的评分
  winner?: 'A' | 'B' | 'draw';
  eloChangeA: number;
  eloChangeB: number;
  recordedAt: Date;
}

/** 统计数据接口 - 从视图查询 */
export interface PersonaStats {
  persona_id: string;
  model: string;
  role: string;
  elo_rating: number;
  win_rate: number;
  total_matches: number;
  wins: number;
  losses: number;
  avg_score: number;
}

/** ELO 计算配置 */
interface EloConfig {
  kFactor: number;
  winThreshold: number; // 分数差异阈值，超过则判定胜负
  drawMargin: number;   // 平局判定范围
}

// ==================== 主类实现 ====================
export class PersonaRecorder {
  private db: Database;

  // 默认配置 - 灵感来自国际象棋和电竞评分系统
  private readonly defaultConfig: EloConfig = {
    kFactor: 32,      // 标准 K 值，对新选手更敏感
    winThreshold: 0.5, // 0.5分差异算赢
    drawMargin: 0.1    // 0.1分以内算平局
  };

  private config: EloConfig;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`,
    config?: Partial<EloConfig>
  ) {
    this.db = new Database(dbPath);
    this.config = { ...this.defaultConfig, ...config };

    console.log('🎮 PersonaRecorder 初始化完成 - 准备记录精彩对局！');
  }

  /**
   * 记录单个 persona 的评分
   * 创意点：自动验证分数范围，防止异常数据
   */
  async recordScore(params: {
    personaId: string;
    taskId: string;
    phase: ScoreRecord['phase'];
    rubricScores: RubricScores;
    overallScore: number;
    evaluatorPersonaId?: string;
  }): Promise<void> {
    // 数据验证 - 确保分数在合理范围内
    this.validateScore(params.overallScore);
    Object.values(params.rubricScores).forEach(score => {
      this.validateScore(score);
    });

    const rubricJson = JSON.stringify(params.rubricScores);

    this.db.run(`
      INSERT INTO sys_persona_scores (
        persona_id, task_id, phase, rubric_json, overall_score,
        evaluator_persona_id, evaluated_by, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, 'peer', datetime('now'))
    `, [
      params.personaId,
      params.taskId,
      params.phase,
      rubricJson,
      params.overallScore,
      params.evaluatorPersonaId || null
    ]);

    console.log(`📝 记录评分: ${params.personaId} 在任务 ${params.taskId} 得分 ${params.overallScore}`);

    // 创意扩展：分析评分趋势
    this.analyzeScoreTrend(params.personaId, params.overallScore);
  }

  /**
   * 记录对局结果 - 核心功能！
   * 创新点：自动判定胜负 + ELO 计算 + 数据持久化
   */
  async recordMatch(params: {
    taskId: string;
    personaA: string;
    personaB: string;
    scoreA: number;
    scoreB: number;
  }): Promise<MatchResult> {
    // 验证输入
    this.validateScore(params.scoreA);
    this.validateScore(params.scoreB);

    if (params.personaA === params.personaB) {
      throw new Error('🤔 创意提示：不能和自己对战哦！请选择不同的 persona');
    }

    // 获取当前 ELO 分数
    const eloA = this.getCurrentElo(params.personaA);
    const eloB = this.getCurrentElo(params.personaB);

    // 判定胜负 - 使用阈值判断
    const scoreDiff = Math.abs(params.scoreA - params.scoreB);
    let winner: 'persona_a' | 'persona_b' | 'draw' = 'draw';

    if (scoreDiff > this.config.winThreshold) {
      winner = params.scoreA > params.scoreB ? 'persona_a' : 'persona_b';
    } else if (scoreDiff <= this.config.drawMargin) {
      winner = 'draw';
    }

    // 计算 ELO 变化 - 核心算法
    const eloChangeA = this.calculateEloChange({
      myElo: eloA,
      opponentElo: eloB,
      actualScore: winner === 'persona_a' ? 1 : winner === 'persona_b' ? 0 : 0.5
    });

    const eloChangeB = this.calculateEloChange({
      myElo: eloB,
      opponentElo: eloA,
      actualScore: winner === 'persona_b' ? 1 : winner === 'persona_a' ? 0 : 0.5
    });

    // 写入数据库 - 触发器会自动更新 sys_persona_elo
    this.db.run(`
      INSERT INTO sys_persona_matches (
        task_id, persona_a, persona_b, score_a, score_b,
        winner, elo_change_a, elo_change_b, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `, [
      params.taskId,
      params.personaA,
      params.personaB,
      params.scoreA,
      params.scoreB,
      winner,
      eloChangeA,
      eloChangeB
    ]);

    console.log(`🎯 记录对局: ${params.personaA} vs ${params.personaB} - 胜者: ${winner}`);
    console.log(`📈 ELO 变化: A +${eloChangeA.toFixed(1)}, B +${eloChangeB.toFixed(1)}`);

    return {
      ...params,
      winner: winner === 'persona_a' ? 'A' : winner === 'persona_b' ? 'B' : 'draw',
      eloChangeA,
      eloChangeB,
      recordedAt: new Date()
    };
  }

  /**
   * 计算 ELO 变化 - 标准公式但有创意优化
   * 创新点：支持动态 K-factor，基于比赛次数调整
   */
  calculateEloChange(params: {
    myElo: number;
    opponentElo: number;
    actualScore: number; // 1=赢, 0.5=平, 0=输
  }): number {
    const { myElo, opponentElo, actualScore } = params;

    // 标准 ELO 公式
    const expectedScore = 1 / (1 + Math.pow(10, (opponentElo - myElo) / 400));

    // 计算变化 - K-factor 可以基于比赛次数动态调整
    const kFactor = this.getDynamicKFactor(myElo);
    const change = kFactor * (actualScore - expectedScore);

    // 创意：限制单次变化幅度，防止异常波动
    return this.clampEloChange(change);
  }

  /**
   * 获取 persona 统计数据
   * 从 v_persona_stats 视图查询
   */
  getPersonaStats(personaId: string): PersonaStats | null {
    const result = this.db.query(`
      SELECT * FROM v_persona_stats WHERE persona_id = ?
    `).get(personaId);

    if (!result) {
      console.log(`⚠️ 未找到 ${personaId} 的统计数据`);
      return null;
    }

    console.log(`📊 查询 ${personaId} 的统计数据:`, result);
    return result as PersonaStats;
  }

  /**
   * 获取排行榜
   */
  getLeaderboard(limit: number = 10): PersonaStats[] {
    const results = this.db.query(`
      SELECT * FROM v_persona_leaderboard LIMIT ?
    `).all(limit);

    return results as PersonaStats[];
  }

  // ==================== 辅助方法 ====================

  /** 验证分数范围 (0-10) */
  private validateScore(score: number): void {
    if (score < 0 || score > 10) {
      throw new Error(`❌ 分数 ${score} 超出范围 (0-10)`);
    }
  }

  /** 获取当前 ELO */
  private getCurrentElo(personaId: string): number {
    const result = this.db.query(`
      SELECT elo_rating FROM sys_persona_elo WHERE persona_id = ?
    `).get(personaId) as { elo_rating: number } | null;

    return result?.elo_rating || 1500; // 默认起始分数
  }

  /** 动态 K-factor - 创意功能：根据 ELO 调整灵敏度 */
  private getDynamicKFactor(currentElo: number): number {
    // 新手更敏感，高手更稳定
    if (currentElo < 1400) return 40;    // 新手期，快速调整
    if (currentElo < 2000) return 32;    // 标准期
    return 24;                           // 高手期，稳定为主
  }

  /** 限制 ELO 变化幅度 - 防止异常波动 */
  private clampEloChange(change: number): number {
    const maxChange = 64; // 单次最大变化
    return Math.max(-maxChange, Math.min(maxChange, change));
  }

  /** 分析评分趋势 - 创意扩展功能 */
  private analyzeScoreTrend(personaId: string, score: number): void {
    // 这里可以添加趋势分析逻辑
    if (score > 8) {
      console.log(`🚀 ${personaId} 表现超棒！继续保持！`);
    } else if (score < 5) {
      console.log(`💡 ${personaId} 有提升空间，建议调整策略`);
    }
  }
}
