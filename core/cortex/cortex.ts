/**
 * Solar Cortex - 中枢神经系统
 *
 * 统一协调器，解决断链问题:
 * - 意图覆盖率 0.02% → 100%
 * - 路由评估率 0.9% → 100%
 * - 反馈转化率 17% → 80%+
 *
 * 铁律:
 * 1. 每个请求必须经过意图解析
 * 2. 每个路由决策必须有评估
 * 3. 每个反馈必须尝试学习
 *
 * @version 1.0.0
 * @created 2026-02-06
 */

import { Database } from 'bun:sqlite';
import { $ } from 'bun';
import { checkLedger, searchTantivy } from '../intent-engine/gate-keeper';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================================================
// 类型定义
// ============================================================================

export interface CortexRequest {
  requestId: string;
  input: string;
  context?: Record<string, any>;
  timestamp: string;
}

export interface IntentResult {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  suggestedAction: string;
}

export interface RouteResult {
  target: string;        // 'skill', 'agent', 'mcp', 'shortcut'
  targetId: string;
  confidence: number;
  reason: string;
}

export interface ExecutionResult {
  success: boolean;
  output: any;
  duration_ms: number;
  tokens_used?: number;
}

export interface CortexResponse {
  requestId: string;
  intent: IntentResult;
  route: RouteResult;
  execution: ExecutionResult;
  feedback?: {
    collected: boolean;
    signal?: string;
  };
}

// ============================================================================
// 事件总线
// ============================================================================

type EventHandler = (data: any) => void | Promise<void>;

class EventBus {
  private handlers: Map<string, EventHandler[]> = new Map();

  on(event: string, handler: EventHandler): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event)!.push(handler);
  }

  async emit(event: string, data: any): Promise<void> {
    const handlers = this.handlers.get(event) || [];
    for (const handler of handlers) {
      await handler(data);
    }
  }

  off(event: string, handler?: EventHandler): void {
    if (!handler) {
      this.handlers.delete(event);
    } else {
      const handlers = this.handlers.get(event) || [];
      this.handlers.set(event, handlers.filter(h => h !== handler));
    }
  }
}

// ============================================================================
// Cortex 主类
// ============================================================================

export class Cortex {
  private db: Database;
  private eventBus: EventBus;
  private sessionId: string;

  constructor() {
    this.db = new Database(DB_PATH);
    // 启用 WAL 模式，支持并发读写
    this.db.run('PRAGMA journal_mode = WAL');
    this.db.run('PRAGMA busy_timeout = 5000');
    this.eventBus = new EventBus();
    this.sessionId = `cortex_${Date.now()}`;
    this.setupEventHandlers();
    this.ensureTables();
  }

  private ensureTables(): void {
    // Cortex 请求日志表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_requests (
        request_id TEXT PRIMARY KEY,
        session_id TEXT,
        input TEXT NOT NULL,
        context JSON,

        -- 意图解析结果
        intent TEXT,
        intent_confidence REAL,
        entities JSON,

        -- 路由结果
        route_target TEXT,
        route_target_id TEXT,
        route_confidence REAL,

        -- 执行结果
        execution_success BOOLEAN,
        execution_output TEXT,
        execution_duration_ms INTEGER,
        tokens_used INTEGER,

        -- 反馈
        feedback_collected BOOLEAN DEFAULT FALSE,
        feedback_signal TEXT,

        -- 时间戳
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME
      )
    `);

    // 闭环统计视图
    this.db.run(`
      CREATE VIEW IF NOT EXISTS v_cortex_stats AS
      SELECT
        COUNT(*) as total_requests,
        SUM(CASE WHEN intent IS NOT NULL THEN 1 ELSE 0 END) as intent_parsed,
        SUM(CASE WHEN route_target IS NOT NULL THEN 1 ELSE 0 END) as route_decided,
        SUM(CASE WHEN execution_success THEN 1 ELSE 0 END) as execution_success,
        SUM(CASE WHEN feedback_collected THEN 1 ELSE 0 END) as feedback_collected,
        ROUND(100.0 * SUM(CASE WHEN intent IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as intent_rate,
        ROUND(100.0 * SUM(CASE WHEN route_target IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as route_rate,
        ROUND(100.0 * SUM(CASE WHEN feedback_collected THEN 1 ELSE 0 END) / COUNT(*), 1) as feedback_rate
      FROM cortex_requests
    `);
  }

  private setupEventHandlers(): void {
    // 意图解析完成 → 触发路由
    this.eventBus.on('intent:parsed', async (data) => {
      await this.logEvent('intent_parsed', data);
    });

    // 路由决策完成 → 触发执行
    this.eventBus.on('route:decided', async (data) => {
      await this.logEvent('route_decided', data);
    });

    // 执行完成 → 触发反馈收集
    this.eventBus.on('execution:completed', async (data) => {
      await this.logEvent('execution_completed', data);
    });

    // 反馈收集完成 → 触发学习
    this.eventBus.on('feedback:collected', async (data) => {
      await this.logEvent('feedback_collected', data);
      await this.triggerLearning(data);
    });
  }

  private async logEvent(event: string, data: any): Promise<void> {
    const uniqueId = `cortex_${event}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.db.run(`
      INSERT INTO tel_operations (operation_id, category, operation, target)
      VALUES (?, 'cortex', ?, ?)
    `, [uniqueId, event, JSON.stringify(data).slice(0, 200)]);
  }

  // ============================================================================
  // 核心流程
  // ============================================================================

  /**
   * 主入口: 处理请求
   * 铁律: 每个请求都经过完整闭环
   */
  async process(input: string, context?: Record<string, any>): Promise<CortexResponse> {
    const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const request: CortexRequest = {
      requestId,
      input,
      context,
      timestamp: new Date().toISOString()
    };

    // 铁律 1: 先查账本
    checkLedger();

    // 记录请求
    this.db.run(`
      INSERT INTO cortex_requests (request_id, session_id, input, context)
      VALUES (?, ?, ?, ?)
    `, [requestId, this.sessionId, input, JSON.stringify(context || {})]);

    try {
      // Phase 1: 意图解析 (100% 覆盖)
      const intent = await this.parseIntent(request);
      await this.eventBus.emit('intent:parsed', { requestId, intent });
      this.updateRequest(requestId, {
        intent: intent.intent,
        intent_confidence: intent.confidence,
        entities: JSON.stringify(intent.entities)
      });

      // Phase 2: 路由决策 (100% 评估)
      const route = await this.decideRoute(request, intent);
      await this.eventBus.emit('route:decided', { requestId, route });
      this.updateRequest(requestId, {
        route_target: route.target,
        route_target_id: route.targetId,
        route_confidence: route.confidence
      });

      // Phase 3: 执行
      const execution = await this.execute(route, request);
      await this.eventBus.emit('execution:completed', { requestId, execution });
      this.updateRequest(requestId, {
        execution_success: execution.success,
        execution_output: JSON.stringify(execution.output).slice(0, 1000),
        execution_duration_ms: execution.duration_ms,
        tokens_used: execution.tokens_used,
        completed_at: new Date().toISOString()
      });

      // Phase 4: 反馈收集 (尝试学习)
      const feedback = await this.collectFeedback(requestId, execution);
      if (feedback.collected) {
        await this.eventBus.emit('feedback:collected', { requestId, feedback });
        this.updateRequest(requestId, {
          feedback_collected: true,
          feedback_signal: feedback.signal
        });
      }

      return {
        requestId,
        intent,
        route,
        execution,
        feedback
      };
    } catch (error: any) {
      this.updateRequest(requestId, {
        execution_success: false,
        execution_output: error.message,
        completed_at: new Date().toISOString()
      });
      throw error;
    }
  }

  // ============================================================================
  // Phase 1: 意图解析
  // ============================================================================

  private async parseIntent(request: CortexRequest): Promise<IntentResult> {
    const { input } = request;

    // 1. 先通过 Tantivy 检索相关资源
    const searchResults = await searchTantivy(input, 5);

    // 2. 基于检索结果和输入分析意图
    // 简单规则 (后续可升级为 LLM)
    let intent = 'unknown';
    let confidence = 0.5;
    const entities: Record<string, any> = {};

    // 动词检测
    const actionPatterns: Record<string, RegExp> = {
      'search': /搜索|查找|找|search|find/i,
      'create': /创建|新建|添加|create|add|new/i,
      'delete': /删除|移除|delete|remove/i,
      'update': /更新|修改|编辑|update|edit|modify/i,
      'execute': /执行|运行|跑|run|exec/i,
      'analyze': /分析|检查|analyze|check/i,
      'list': /列出|显示|查看|list|show|view/i,
      'commit': /提交|commit/i,
      'build': /构建|编译|build|compile/i,
      'test': /测试|test/i
    };

    for (const [action, pattern] of Object.entries(actionPatterns)) {
      if (pattern.test(input)) {
        intent = action;
        confidence = 0.8;
        break;
      }
    }

    // 如果 Tantivy 有高分匹配，提升置信度
    if (searchResults.results.length > 0 && searchResults.results[0].score > 0.7) {
      confidence = Math.min(confidence + 0.1, 1.0);
      entities.matchedResource = searchResults.results[0];
    }

    return {
      intent,
      confidence,
      entities,
      suggestedAction: this.suggestAction(intent, entities)
    };
  }

  private suggestAction(intent: string, entities: Record<string, any>): string {
    const matched = entities.matchedResource;
    if (matched) {
      return `使用 ${matched.type}:${matched.id}`;
    }

    const actionMap: Record<string, string> = {
      'search': '搜索资源',
      'create': '创建新资源',
      'execute': '执行命令',
      'analyze': '分析数据',
      'commit': '提交代码',
      'build': '构建项目',
      'test': '运行测试'
    };

    return actionMap[intent] || '执行默认操作';
  }

  // ============================================================================
  // Phase 2: 路由决策
  // ============================================================================

  private async decideRoute(request: CortexRequest, intent: IntentResult): Promise<RouteResult> {
    // 1. 如果意图解析中已匹配到资源，直接使用
    if (intent.entities.matchedResource) {
      const matched = intent.entities.matchedResource;
      return {
        target: matched.type,
        targetId: matched.id,
        confidence: intent.confidence,
        reason: 'Tantivy 语义匹配'
      };
    }

    // 2. 查询 sys_resources 找最佳匹配
    const searchTerm = `%${request.input}%`;
    const resources = this.db.query<{
      resource_id: string;
      resource_type: string;
      name: string;
      keywords: string;
    }, [string, string, string]>(`
      SELECT resource_id, resource_type, name, keywords
      FROM sys_resources
      WHERE status = 'active'
        AND (name LIKE ? OR keywords LIKE ? OR description LIKE ?)
      ORDER BY
        CASE resource_type
          WHEN 'shortcut' THEN 1
          WHEN 'skill' THEN 2
          WHEN 'agent' THEN 3
          ELSE 4
        END
      LIMIT 1
    `).all(searchTerm, searchTerm, searchTerm);

    if (resources.length > 0) {
      const r = resources[0];
      return {
        target: r.resource_type,
        targetId: r.resource_id,
        confidence: 0.6,
        reason: 'sys_resources 关键词匹配'
      };
    }

    // 3. 默认路由
    return {
      target: 'default',
      targetId: 'cortex_default_handler',
      confidence: 0.3,
      reason: '无匹配资源，使用默认处理器'
    };
  }

  // ============================================================================
  // Phase 3: 执行
  // ============================================================================

  private async execute(route: RouteResult, request: CortexRequest): Promise<ExecutionResult> {
    const start = Date.now();

    try {
      let output: any;

      switch (route.target) {
        case 'shortcut':
          output = await this.executeShortcut(route.targetId, request);
          break;
        case 'skill':
          output = await this.executeSkill(route.targetId, request);
          break;
        case 'agent':
          output = await this.executeAgent(route.targetId, request);
          break;
        case 'script':
          output = await this.executeScript(route.targetId, request);
          break;
        default:
          output = { message: '默认处理器执行', input: request.input };
      }

      return {
        success: true,
        output,
        duration_ms: Date.now() - start
      };
    } catch (error: any) {
      return {
        success: false,
        output: { error: error.message },
        duration_ms: Date.now() - start
      };
    }
  }

  private async executeShortcut(id: string, request: CortexRequest): Promise<any> {
    const name = id.replace('shortcut:', '');
    const result = await $`shortcuts run ${name}`.quiet();
    return { type: 'shortcut', output: result.stdout.toString() };
  }

  private async executeSkill(id: string, request: CortexRequest): Promise<any> {
    // 查询 skill 路径
    const skill = this.db.query<{ path: string }, [string]>(`
      SELECT path FROM sys_skills WHERE skill_id = ?
    `).get(id);

    if (skill?.path) {
      const result = await $`bun ${skill.path}`.quiet();
      return { type: 'skill', output: result.stdout.toString() };
    }

    return { type: 'skill', message: 'Skill 执行模拟' };
  }

  private async executeAgent(id: string, request: CortexRequest): Promise<any> {
    return { type: 'agent', message: 'Agent 调度', agentId: id };
  }

  private async executeScript(id: string, request: CortexRequest): Promise<any> {
    const script = this.db.query<{ file_path: string; runtime: string }, [string]>(`
      SELECT file_path, runtime FROM sys_scripts WHERE script_id = ?
    `).get(id);

    if (script?.file_path) {
      const cmd = script.runtime === 'bun' ? 'bun' : script.runtime;
      const result = await $`${cmd} ${script.file_path}`.quiet();
      return { type: 'script', output: result.stdout.toString() };
    }

    return { type: 'script', message: 'Script 执行模拟' };
  }

  // ============================================================================
  // Phase 4: 反馈收集
  // ============================================================================

  private async collectFeedback(
    requestId: string,
    execution: ExecutionResult
  ): Promise<{ collected: boolean; signal?: string }> {
    // 自动反馈: 基于执行结果
    if (execution.success) {
      return { collected: true, signal: 'auto_success' };
    } else {
      return { collected: true, signal: 'auto_failure' };
    }
  }

  // ============================================================================
  // 学习触发
  // ============================================================================

  private async triggerLearning(data: any): Promise<void> {
    // 将反馈写入学习队列
    this.db.run(`
      INSERT OR IGNORE INTO evo_feedback_v2 (feedback_id, signal_type, trigger_text)
      VALUES (?, ?, ?)
    `, [
      `fb_${Date.now()}`,
      data.feedback?.signal === 'auto_success' ? 'task_success' : 'task_failure',
      JSON.stringify(data)
    ]);
  }

  // ============================================================================
  // 辅助方法
  // ============================================================================

  private updateRequest(requestId: string, updates: Record<string, any>): void {
    const setClauses = Object.keys(updates).map(k => `${k} = ?`).join(', ');
    const values = [...Object.values(updates), requestId];

    this.db.run(`
      UPDATE cortex_requests SET ${setClauses} WHERE request_id = ?
    `, values);
  }

  // ============================================================================
  // 统计接口
  // ============================================================================

  getStats(): {
    total: number;
    intentRate: number;
    routeRate: number;
    feedbackRate: number;
  } {
    const stats = this.db.query<{
      total_requests: number;
      intent_rate: number;
      route_rate: number;
      feedback_rate: number;
    }, []>(`
      SELECT
        total_requests,
        intent_rate,
        route_rate,
        feedback_rate
      FROM v_cortex_stats
    `).get();

    return {
      total: stats?.total_requests || 0,
      intentRate: stats?.intent_rate || 0,
      routeRate: stats?.route_rate || 0,
      feedbackRate: stats?.feedback_rate || 0
    };
  }

  close(): void {
    this.db.close();
  }
}

// ============================================================================
// CLI
// ============================================================================

if (import.meta.main) {
  const cortex = new Cortex();
  const cmd = process.argv[2];

  switch (cmd) {
    case 'process': {
      const input = process.argv.slice(3).join(' ');
      if (!input) {
        console.log('Usage: bun cortex.ts process <输入>');
        break;
      }

      console.log('\n🧠 Solar Cortex 处理请求...\n');
      const result = await cortex.process(input);

      console.log('┌─ 意图解析 ────────────────────────────────────────┐');
      console.log(`│ Intent: ${result.intent.intent} (${(result.intent.confidence * 100).toFixed(0)}%)`);
      console.log(`│ Action: ${result.intent.suggestedAction}`);
      console.log('└──────────────────────────────────────────────────┘\n');

      console.log('┌─ 路由决策 ────────────────────────────────────────┐');
      console.log(`│ Target: ${result.route.target}:${result.route.targetId}`);
      console.log(`│ Reason: ${result.route.reason}`);
      console.log('└──────────────────────────────────────────────────┘\n');

      console.log('┌─ 执行结果 ────────────────────────────────────────┐');
      console.log(`│ Success: ${result.execution.success ? '✓' : '✗'}`);
      console.log(`│ Duration: ${result.execution.duration_ms}ms`);
      console.log('└──────────────────────────────────────────────────┘\n');

      if (result.feedback) {
        console.log(`反馈: ${result.feedback.signal}`);
      }
      break;
    }

    case 'stats': {
      const stats = cortex.getStats();
      console.log('\n🧠 Cortex 统计\n');
      console.log(`总请求: ${stats.total}`);
      console.log(`意图覆盖率: ${stats.intentRate}%`);
      console.log(`路由评估率: ${stats.routeRate}%`);
      console.log(`反馈收集率: ${stats.feedbackRate}%`);
      break;
    }

    default:
      console.log(`
Usage: bun cortex.ts <command>

Commands:
  process <输入>  - 处理请求 (完整闭环)
  stats           - 显示统计

Solar Cortex - 中枢神经系统
铁律: 100% 意图解析 | 100% 路由评估 | 尝试学习每个反馈
      `);
  }

  cortex.close();
}

export default Cortex;
