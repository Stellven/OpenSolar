#!/usr/bin/env bun
/**
 * SMA Trigger Manager - P3 触发逻辑改进
 *
 * 功能:
 * 1. 微批处理触发 - 每10轮或15分钟空闲
 * 2. 知识显著度评分 - 区分核心事实 vs 临时信息
 * 3. 智能清理策略 - 结合 permanence + access_frequency
 *
 * @version 1.0.0
 * @created 2026-02-27
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import os from 'os';

const DB_PATH = path.join(os.homedir(), '.solar', 'solar.db');

// ============ 类型定义 ============

export interface TriggerState {
  lastConsolidation: number;      // 上次固化时间戳
  turnsSinceLastConsolidation: number;  // 上次固化后的对话轮数
  lastActivity: number;           // 上次活动时间戳
  sessionId: string;
}

export interface SalienceConfig {
  // 核心事实关键词（永久保留）
  coreKeywords: string[];
  // 临时信息关键词
  tempKeywords: string[];
  // 动态信息关键词
  dynamicKeywords: string[];
}

export interface SalienceResult {
  permanence: number;     // 0-1，越高越永久
  category: 'core' | 'temp' | 'dynamic';
  reason: string;
}

// ============ 默认配置 ============

const DEFAULT_SALIENCE_CONFIG: SalienceConfig = {
  coreKeywords: [
    // 个人信息
    '名字', '姓名', 'name', '叫什么', '我是', '我的名字',
    '生日', '出生', '年龄', 'age',
    '邮箱', 'email', '电话', '手机', 'phone',
    '家', '住址', '城市', 'city', 'address',
    // 偏好
    '喜欢', '偏好', '最爱', 'favorite', 'prefer',
    '习惯', '惯例',
    // 角色/身份
    '工作', '职业', '公司', '职位', 'job', 'company',
    '项目', '负责', 'project',
    // 重要关系
    '老婆', '老公', '妻子', '丈夫', '孩子', '女儿', '儿子', '父母', 'wife', 'husband', 'child',
  ],
  tempKeywords: [
    '现在', '当前', '目前', '今天', '昨天', '明天',
    '正在', '要做', '计划', '待办', 'task',
    '问题', 'bug', '错误', '修复',
    '测试', 'debug',
  ],
  dynamicKeywords: [
    '位置', '地点', '在哪', '地方',
    '状态', '心情', '感觉',
    '进度', '完成', '百分比',
  ],
};

const TRIGGER_CONFIG = {
  minTurns: 10,           // 最少对话轮数
  maxIdleMinutes: 15,     // 最大空闲分钟数
  maxBatchSize: 50,       // 最大批次大小
};

// ============ 触发条件检测 ============

/**
 * 检查是否应该触发固化
 *
 * 触发条件（满足任一）：
 * 1. 对话轮数达到阈值（默认10轮）
 * 2. 空闲时间达到阈值（默认15分钟）
 *
 * @param state - 当前触发状态
 * @returns 是否应该触发
 */
export function shouldTriggerConsolidation(state: TriggerState): {
  shouldTrigger: boolean;
  reason: string;
} {
  const now = Math.floor(Date.now() / 1000);

  // 检查对话轮数
  if (state.turnsSinceLastConsolidation >= TRIGGER_CONFIG.minTurns) {
    return {
      shouldTrigger: true,
      reason: `达到 ${state.turnsSinceLastConsolidation} 轮对话（阈值 ${TRIGGER_CONFIG.minTurns}）`
    };
  }

  // 检查空闲时间
  const idleSeconds = now - state.lastActivity;
  const idleMinutes = idleSeconds / 60;

  if (idleMinutes >= TRIGGER_CONFIG.maxIdleMinutes) {
    return {
      shouldTrigger: true,
      reason: `空闲 ${idleMinutes.toFixed(1)} 分钟（阈值 ${TRIGGER_CONFIG.maxIdleMinutes}）`
    };
  }

  return {
    shouldTrigger: false,
    reason: `轮数: ${state.turnsSinceLastConsolidation}/${TRIGGER_CONFIG.minTurns}, 空闲: ${idleMinutes.toFixed(1)}/${TRIGGER_CONFIG.maxIdleMinutes}分钟`
  };
}

/**
 * 获取当前触发状态
 */
export function getTriggerState(sessionId: string): TriggerState {
  const db = new Database(DB_PATH, { readonly: true });

  try {
    // 查询上次固化时间
    const lastConsolStmt = db.prepare(`
      SELECT MAX(created_at) as last_time
      FROM knowledge_triples
      WHERE source_session_id = ?
    `);
    const lastConsol = lastConsolStmt.get(sessionId) as { last_time: number | null } | undefined;
    lastConsolStmt.finalize();

    const lastConsolidation = lastConsol?.last_time ?? 0;

    // 查询上次固化后的对话轮数
    const turnsStmt = db.prepare(`
      SELECT COUNT(*) as count
      FROM session_log
      WHERE session_id = ? AND timestamp > ?
    `);
    const turns = turnsStmt.get(sessionId, lastConsolidation) as { count: number };
    turnsStmt.finalize();

    // 查询最后活动时间
    const lastActivityStmt = db.prepare(`
      SELECT MAX(timestamp) as last_activity
      FROM session_log
      WHERE session_id = ?
    `);
    const lastAct = lastActivityStmt.get(sessionId) as { last_activity: number | null } | undefined;
    lastActivityStmt.finalize();

    return {
      lastConsolidation,
      turnsSinceLastConsolidation: turns?.count ?? 0,
      lastActivity: lastAct?.last_activity ?? 0,
      sessionId
    };
  } finally {
    db.close();
  }
}

/**
 * 更新触发状态（固化完成后调用）
 */
export function updateTriggerState(sessionId: string): void {
  const db = new Database(DB_PATH);

  try {
    const now = Math.floor(Date.now() / 1000);

    // 创建或更新触发状态表
    db.run(`
      CREATE TABLE IF NOT EXISTS sma_trigger_state (
        session_id TEXT PRIMARY KEY,
        last_consolidation INTEGER,
        last_activity INTEGER,
        updated_at INTEGER
      )
    `);

    db.run(`
      INSERT OR REPLACE INTO sma_trigger_state
      (session_id, last_consolidation, last_activity, updated_at)
      VALUES (?, ?, ?, ?)
    `, sessionId, now, now, now);
  } finally {
    db.close();
  }
}

// ============ 知识显著度评分 ============

/**
 * 计算三元组的显著度（永久性）
 *
 * 分类：
 * - core (1.0): 核心事实，永不过期
 * - temp (0.5): 临时信息，90天过期
 * - dynamic (0.3): 动态信息，30天过期
 *
 * @param triple - 三元组字符串
 * @param config - 显著度配置
 * @returns 显著度结果
 */
export function calculateSalience(
  triple: { subject: string; predicate: string; object: string },
  config: SalienceConfig = DEFAULT_SALIENCE_CONFIG
): SalienceResult {
  const text = `${triple.subject} ${triple.predicate} ${triple.object}`.toLowerCase();

  // 检查核心关键词
  for (const keyword of config.coreKeywords) {
    if (text.includes(keyword.toLowerCase())) {
      return {
        permanence: 1.0,
        category: 'core',
        reason: `匹配核心关键词: ${keyword}`
      };
    }
  }

  // 检查动态关键词
  for (const keyword of config.dynamicKeywords) {
    if (text.includes(keyword.toLowerCase())) {
      return {
        permanence: 0.3,
        category: 'dynamic',
        reason: `匹配动态关键词: ${keyword}`
      };
    }
  }

  // 检查临时关键词
  for (const keyword of config.tempKeywords) {
    if (text.includes(keyword.toLowerCase())) {
      return {
        permanence: 0.5,
        category: 'temp',
        reason: `匹配临时关键词: ${keyword}`
      };
    }
  }

  // 默认：普通信息
  return {
    permanence: 0.7,
    category: 'temp',
    reason: '未匹配特定关键词，使用默认值'
  };
}

/**
 * 批量计算显著度
 */
export function batchCalculateSalience(
  triples: Array<{ subject: string; predicate: string; object: string }>
): Array<{ triple: typeof triples[0]; salience: SalienceResult }> {
  return triples.map(triple => ({
    triple,
    salience: calculateSalience(triple)
  }));
}

// ============ 智能清理策略 ============

/**
 * 计算过期时间
 *
 * 规则：
 * - permanence = 1.0 → 永不过期
 * - permanence = 0.7 → 180天
 * - permanence = 0.5 → 90天
 * - permanence = 0.3 → 30天
 * - access_frequency > 10 → 延长50%时间
 */
function calculateExpiryTime(permanence: number, accessCount: number): number {
  if (permanence >= 1.0) {
    return Infinity; // 永不过期
  }

  // 基础过期时间（秒）
  let baseExpiry: number;
  if (permanence >= 0.7) {
    baseExpiry = 180 * 24 * 3600; // 180天
  } else if (permanence >= 0.5) {
    baseExpiry = 90 * 24 * 3600; // 90天
  } else {
    baseExpiry = 30 * 24 * 3600; // 30天
  }

  // 访问频率加成
  if (accessCount > 10) {
    baseExpiry *= 1.5;
  } else if (accessCount > 5) {
    baseExpiry *= 1.2;
  }

  return baseExpiry;
}

/**
 * 智能清理过期知识
 *
 * @returns 清理的三元组数量
 */
export function smartCleanup(): {
  deleted: number;
  kept: number;
  categories: { core: number; temp: number; dynamic: number };
} {
  const db = new Database(DB_PATH);

  try {
    const now = Math.floor(Date.now() / 1000);

    // 获取所有三元组及其访问次数
    const stmt = db.prepare(`
      SELECT id, subject, predicate, object, confidence, created_at,
             COALESCE(access_count, 0) as access_count
      FROM knowledge_triples
    `);

    const triples = stmt.all() as Array<{
      id: number;
      subject: string;
      predicate: string;
      object: string;
      confidence: number;
      created_at: number;
      access_count: number;
    }>;
    stmt.finalize();

    let deleted = 0;
    let kept = 0;
    const categories = { core: 0, temp: 0, dynamic: 0 };

    for (const triple of triples) {
      const salience = calculateSalience(triple);
      const expirySeconds = calculateExpiryTime(salience.permanence, triple.access_count);
      const age = now - triple.created_at;

      if (expirySeconds !== Infinity && age > expirySeconds) {
        // 过期，删除
        db.run('DELETE FROM knowledge_triples WHERE id = ?', triple.id);
        deleted++;
      } else {
        kept++;
        categories[salience.category]++;
      }
    }

    return { deleted, kept, categories };
  } finally {
    db.close();
  }
}

/**
 * 增加访问计数
 */
export function incrementAccessCount(tripleIds: number[]): void {
  if (tripleIds.length === 0) return;

  const db = new Database(DB_PATH);

  try {
    // 确保 access_count 列存在
    db.run(`
      ALTER TABLE knowledge_triples
      ADD COLUMN access_count INTEGER DEFAULT 0
    `).catch(() => { /* 列已存在 */ });

    const placeholders = tripleIds.map(() => '?').join(',');
    db.run(`
      UPDATE knowledge_triples
      SET access_count = COALESCE(access_count, 0) + 1
      WHERE id IN (${placeholders})
    `, ...tripleIds);
  } finally {
    db.close();
  }
}

// ============ 主入口 ============

/**
 * 检查并执行固化（如果需要）
 */
export async function checkAndConsolidate(
  sessionId: string,
  consolidateFn: (sessionId: string) => Promise<number>
): Promise<{ triggered: boolean; triplesCreated: number; reason: string }> {
  const state = getTriggerState(sessionId);
  const { shouldTrigger, reason } = shouldTriggerConsolidation(state);

  if (!shouldTrigger) {
    return { triggered: false, triplesCreated: 0, reason };
  }

  console.log(`[SMA Trigger] 触发固化: ${reason}`);

  try {
    const triplesCreated = await consolidateFn(sessionId);
    updateTriggerState(sessionId);

    return { triggered: true, triplesCreated, reason };
  } catch (error) {
    console.error('[SMA Trigger] 固化失败:', error);
    return { triggered: false, triplesCreated: 0, reason: `固化失败: ${error}` };
  }
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'status') {
    const sessionId = args[1] || 'default';
    const state = getTriggerState(sessionId);
    const { shouldTrigger, reason } = shouldTriggerConsolidation(state);

    console.log('\n=== SMA Trigger Status ===');
    console.log(`Session: ${sessionId}`);
    console.log(`Last consolidation: ${new Date(state.lastConsolidation * 1000).toLocaleString()}`);
    console.log(`Turns since: ${state.turnsSinceLastConsolidation}`);
    console.log(`Last activity: ${new Date(state.lastActivity * 1000).toLocaleString()}`);
    console.log(`Should trigger: ${shouldTrigger ? 'YES' : 'NO'}`);
    console.log(`Reason: ${reason}`);

  } else if (command === 'cleanup') {
    console.log('\n=== SMA Smart Cleanup ===');
    const result = smartCleanup();
    console.log(`Deleted: ${result.deleted}`);
    console.log(`Kept: ${result.kept}`);
    console.log(`Categories: core=${result.categories.core}, temp=${result.categories.temp}, dynamic=${result.categories.dynamic}`);

  } else if (command === 'salience') {
    const subject = args[1] || 'user';
    const predicate = args[2] || 'name';
    const object = args[3] || 'Alice';

    const result = calculateSalience({ subject, predicate, object });
    console.log('\n=== Salience Result ===');
    console.log(`Triple: (${subject}, ${predicate}, ${object})`);
    console.log(`Permanence: ${result.permanence}`);
    console.log(`Category: ${result.category}`);
    console.log(`Reason: ${result.reason}`);

  } else {
    console.log(`
SMA Trigger Manager

Usage:
  bun trigger-manager.ts status [session_id]  - Check trigger status
  bun trigger-manager.ts cleanup              - Run smart cleanup
  bun trigger-manager.ts salience <s> <p> <o> - Calculate salience

Examples:
  bun trigger-manager.ts status abc123
  bun trigger-manager.ts cleanup
  bun trigger-manager.ts salience user name Alice
    `);
  }
}

export type { TriggerState, SalienceConfig, SalienceResult };
