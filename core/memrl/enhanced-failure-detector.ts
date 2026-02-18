/**
 * MEMRL Enhanced Failure Detector - 增强型失败检测器
 *
 * 解决 100:1 数据不平衡问题 (Success=1677, Failure=16)
 *
 * 新增信号源:
 * 1. 隐式失败: 任务放弃、上下文切换、话题突变
 * 2. 纠正信号: 用户说"应该是"、"其实"、"你忘了"
 * 3. 行为信号: 重复尝试、长时间无进展、频繁撤销
 * 4. 间接失败: 工具输出包含警告、非零退出码、超时
 */

import { Database } from 'bun:sqlite';

// 会话上下文
interface SessionContext {
  sessionId: string;
  startTime: number;
  toolCalls: ToolCallRecord[];
  userMessages: string[];
  lastIntentHash: string;
  correctionCount: number;
  undoCount: number;
  retryCount: number;
}

interface ToolCallRecord {
  toolName: string;
  exitCode: number;
  timestamp: number;
  output?: string;
  duration?: number;
}

// 失败信号类型
export enum FailureType {
  // 显式失败 (原有)
  EXPLICIT_NEGATIVE = 'explicit_negative',      // 用户说"不对/错了"
  EXIT_CODE_ERROR = 'exit_code_error',          // 非零退出码
  TEST_FAILURE = 'test_failure',                // 测试失败
  REVIEW_REJECTION = 'review_rejection',        // 审查返工
  OUTPUT_ERROR = 'output_error',                // 输出包含错误

  // 隐式失败 (新增)
  USER_CORRECTION = 'user_correction',          // 用户纠正 ("应该是...")
  TASK_ABANDONMENT = 'task_abandonment',        // 任务放弃 (话题切换)
  REPEATED_FAILURE = 'repeated_failure',        // 重复失败 (同一操作多次)
  EXCESSIVE_DURATION = 'excessive_duration',    // 过长耗时 (无进展)
  FREQUENT_UNDO = 'frequent_undo',              // 频繁撤销
  CONTEXT_OVERFLOW = 'context_overflow',        // 上下文溢出 (compact前)
  IMPLICIT_DISSATISFACTION = 'implicit_dissatisfaction'  // 隐性不满
}

// 失败检测结果
export interface FailureDetectionResult {
  isFailure: boolean;
  failureType: FailureType | null;
  confidence: number;
  evidence: string[];
  severity: 'low' | 'medium' | 'high';
}

export class EnhancedFailureDetector {
  private db: Database;
  private sessionContexts: Map<string, SessionContext> = new Map();

  // 纠正性反馈模式 (用户在纠正我，说明我之前做错了)
  private readonly correctionPatterns = [
    /^(应该是|其实是|你忘了|你漏了|不对|不是|错了)/i,
    /(actually|in fact|you forgot|you missed|that's wrong|not quite)/i,
    /让我(来|重新)/i,  // "让我来" = 你做得不好
    /(等等|慢着|停)/i,  // "等等" = 停下，有问题
    /(我想的是|我的意思是)/i,  // 解释意图 = 理解错误
  ];

  // 任务放弃模式 (话题切换 = 上个任务没做好)
  private readonly abandonmentPatterns = [
    /^(算了|就这样吧|先不管了)/i,
    /(nevermind|forget it|let's move on)/i,
    /^(换个话题|说点别的)/i,
  ];

  // 隐性不满模式
  private readonly dissatisfactionPatterns = [
    /^(嗯|哦|好吧)$/i,  // 单字回复 = 不满意但不想说
    /^(\?|？？|什么)/i,  // 困惑 = 没理解需求
    /(不太对|好像不对|感觉怪怪的)/i,
  ];

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
    this.initSessionTracking();
  }

  /**
   * 初始化会话追踪
   */
  private initSessionTracking(): void {
    // 创建会话追踪表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS memrl_session_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        intent_hash TEXT,
        tool_name TEXT,
        exit_code INTEGER,
        duration_ms INTEGER,
        failure_type TEXT,
        confidence REAL,
        evidence_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  /**
   * 主检测入口
   */
  detect(
    sessionId: string,
    toolName: string,
    exitCode: number,
    output: string,
    userMessage?: string
  ): FailureDetectionResult {
    const context = this.getOrCreateContext(sessionId);

    // 记录工具调用
    context.toolCalls.push({
      toolName,
      exitCode,
      timestamp: Date.now(),
      output
    });

    // 1. 显式失败检测 (原有逻辑)
    const explicitResult = this.detectExplicitFailure(exitCode, output, userMessage);
    if (explicitResult.isFailure) {
      return explicitResult;
    }

    // 2. 纠正信号检测 (新增 - 关键!)
    if (userMessage) {
      context.userMessages.push(userMessage);
      const correctionResult = this.detectUserCorrection(userMessage);
      if (correctionResult.isFailure) {
        context.correctionCount++;
        return correctionResult;
      }

      // 3. 任务放弃检测
      const abandonmentResult = this.detectTaskAbandonment(userMessage, context);
      if (abandonmentResult.isFailure) {
        return abandonmentResult;
      }

      // 4. 隐性不满检测
      const dissatisfactionResult = this.detectImplicitDissatisfaction(userMessage);
      if (dissatisfactionResult.isFailure) {
        return dissatisfactionResult;
      }
    }

    // 5. 重复失败检测
    const repeatedResult = this.detectRepeatedFailure(context);
    if (repeatedResult.isFailure) {
      context.retryCount++;
      return repeatedResult;
    }

    // 6. 过长耗时检测
    const durationResult = this.detectExcessiveDuration(context);
    if (durationResult.isFailure) {
      return durationResult;
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 1. 显式失败检测 (原有逻辑)
   */
  private detectExplicitFailure(
    exitCode: number,
    output: string,
    userMessage?: string
  ): FailureDetectionResult {
    // 用户显式负反馈
    if (userMessage) {
      const negativePatterns = [
        /^(不对|错了|重来|不行|不好|有问题|完全不对|太差了)$/i,
        /(^|\s)(wrong|error|fail|bad|incorrect|mistake|terrible|awful)(\s|$)/i,
      ];

      for (const pattern of negativePatterns) {
        if (pattern.test(userMessage)) {
          return {
            isFailure: true,
            failureType: FailureType.EXPLICIT_NEGATIVE,
            confidence: 0.9,
            evidence: [`用户显式负反馈: "${userMessage}"`],
            severity: 'high'
          };
        }
      }
    }

    // 非零退出码
    if (exitCode !== 0 && exitCode !== undefined) {
      return {
        isFailure: true,
        failureType: FailureType.EXIT_CODE_ERROR,
        confidence: 0.7,
        evidence: [`工具执行失败 (exitCode=${exitCode})`],
        severity: 'medium'
      };
    }

    // 测试失败
    if (output && /test.*fail|failed.*test/i.test(output)) {
      return {
        isFailure: true,
        failureType: FailureType.TEST_FAILURE,
        confidence: 0.8,
        evidence: ['测试失败'],
        severity: 'high'
      };
    }

    // 输出包含错误
    if (output) {
      const errorPatterns = [/error:/i, /exception/i, /failed/i, /timeout/i];
      for (const pattern of errorPatterns) {
        if (pattern.test(output)) {
          return {
            isFailure: true,
            failureType: FailureType.OUTPUT_ERROR,
            confidence: 0.5,
            evidence: [`输出包含错误: ${pattern.source}`],
            severity: 'medium'
          };
        }
      }
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 2. 纠正信号检测 (新增 - 关键!)
   *
   * 用户纠正 = 我之前做错了 = 失败信号
   */
  private detectUserCorrection(userMessage: string): FailureDetectionResult {
    for (const pattern of this.correctionPatterns) {
      if (pattern.test(userMessage)) {
        return {
          isFailure: true,
          failureType: FailureType.USER_CORRECTION,
          confidence: 0.7,  // 纠正意味着之前的输出有问题
          evidence: [`用户纠正: "${userMessage}" - 隐含之前的输出有问题`],
          severity: 'medium'
        };
      }
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 3. 任务放弃检测
   *
   * 用户放弃/切换话题 = 任务没完成好 = 失败
   */
  private detectTaskAbandonment(
    userMessage: string,
    context: SessionContext
  ): FailureDetectionResult {
    // 检查放弃模式
    for (const pattern of this.abandonmentPatterns) {
      if (pattern.test(userMessage)) {
        // 只有在有工具调用后才算放弃
        if (context.toolCalls.length > 0) {
          return {
            isFailure: true,
            failureType: FailureType.TASK_ABANDONMENT,
            confidence: 0.6,
            evidence: [`任务放弃: "${userMessage}" - 用户放弃了当前任务`],
            severity: 'medium'
          };
        }
      }
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 4. 隐性不满检测
   *
   * 用户不满意的隐含表达
   */
  private detectImplicitDissatisfaction(userMessage: string): FailureDetectionResult {
    for (const pattern of this.dissatisfactionPatterns) {
      if (pattern.test(userMessage)) {
        return {
          isFailure: true,
          failureType: FailureType.IMPLICIT_DISSATISFACTION,
          confidence: 0.4,  // 置信度较低，但仍是失败信号
          evidence: [`隐性不满: "${userMessage}"`],
          severity: 'low'
        };
      }
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 5. 重复失败检测
   *
   * 同一工具多次调用失败 = 持续失败
   */
  private detectRepeatedFailure(context: SessionContext): FailureDetectionResult {
    if (context.toolCalls.length < 3) {
      return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
    }

    // 检查最近 3 次调用
    const recentCalls = context.toolCalls.slice(-3);
    const failedCount = recentCalls.filter(c => c.exitCode !== 0).length;

    if (failedCount >= 2) {
      return {
        isFailure: true,
        failureType: FailureType.REPEATED_FAILURE,
        confidence: 0.7,
        evidence: [`重复失败: 最近 3 次调用中 ${failedCount} 次失败`],
        severity: 'high'
      };
    }

    // 检查相同工具被多次调用 (可能是重试)
    const toolCounts = new Map<string, number>();
    for (const call of recentCalls) {
      toolCounts.set(call.toolName, (toolCounts.get(call.toolName) || 0) + 1);
    }

    for (const [toolName, count] of toolCounts) {
      if (count >= 3) {
        return {
          isFailure: true,
          failureType: FailureType.REPEATED_FAILURE,
          confidence: 0.6,
          evidence: [`重复调用: ${toolName} 被调用 ${count} 次`],
          severity: 'medium'
        };
      }
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 6. 过长耗时检测
   *
   * 任务执行时间过长 = 可能卡住了
   */
  private detectExcessiveDuration(context: SessionContext): FailureDetectionResult {
    const duration = Date.now() - context.startTime;

    // 超过 10 分钟且工具调用超过 20 次
    if (duration > 10 * 60 * 1000 && context.toolCalls.length > 20) {
      return {
        isFailure: true,
        failureType: FailureType.EXCESSIVE_DURATION,
        confidence: 0.5,
        evidence: [`过长耗时: ${Math.round(duration / 60000)}分钟, ${context.toolCalls.length}次工具调用`],
        severity: 'medium'
      };
    }

    return { isFailure: false, failureType: null, confidence: 0, evidence: [], severity: 'low' };
  }

  /**
   * 获取或创建会话上下文
   */
  private getOrCreateContext(sessionId: string): SessionContext {
    if (!this.sessionContexts.has(sessionId)) {
      this.sessionContexts.set(sessionId, {
        sessionId,
        startTime: Date.now(),
        toolCalls: [],
        userMessages: [],
        lastIntentHash: '',
        correctionCount: 0,
        undoCount: 0,
        retryCount: 0
      });
    }
    return this.sessionContexts.get(sessionId)!;
  }

  /**
   * 记录失败信号
   */
  recordFailure(
    sessionId: string,
    intentHash: string,
    result: FailureDetectionResult
  ): void {
    if (!result.isFailure) return;

    this.db.run(`
      INSERT INTO memrl_utility_store
      (intent_hash, experience_id, experience_type, utility_total, fuse_status, session_id, evidence_json)
      VALUES (?, ?, 'failure_signal', 0, 'OK', ?, ?)
    `, [
      intentHash,
      `fail_${Date.now()}`,
      sessionId,
      JSON.stringify({
        failureType: result.failureType,
        confidence: result.confidence,
        evidence: result.evidence,
        severity: result.severity,
        timestamp: new Date().toISOString()
      })
    ]);
  }

  /**
   * 获取失败信号统计
   */
  getStats(): {
    total: number;
    byType: Record<string, number>;
    avgConfidence: number;
  } {
    const records = this.db.query(`
      SELECT evidence_json
      FROM memrl_utility_store
      WHERE utility_total = 0 AND evidence_json IS NOT NULL
    `).all() as any[];

    const byType: Record<string, number> = {};
    let totalConfidence = 0;

    for (const record of records) {
      try {
        const evidence = JSON.parse(record.evidence_json);
        if (evidence.failureType) {
          byType[evidence.failureType] = (byType[evidence.failureType] || 0) + 1;
          totalConfidence += evidence.confidence || 0;
        }
      } catch (e) {
        // 忽略解析错误
      }
    }

    return {
      total: records.length,
      byType,
      avgConfidence: records.length > 0 ? totalConfidence / records.length : 0
    };
  }

  /**
   * 清理过期会话
   */
  cleanup(maxAgeMs: number = 30 * 60 * 1000): void {
    const now = Date.now();
    for (const [sessionId, context] of this.sessionContexts) {
      if (now - context.startTime > maxAgeMs) {
        this.sessionContexts.delete(sessionId);
      }
    }
  }

  close(): void {
    this.db.close();
  }
}

// CLI 测试
if (import.meta.main) {
  const detector = new EnhancedFailureDetector();

  console.log('🧪 Enhanced Failure Detector 测试\n');

  const testCases = [
    { msg: '应该是这样的', desc: '纠正信号' },
    { msg: '其实我想的是', desc: '意图解释' },
    { msg: '你忘了加那个参数', desc: '遗漏提醒' },
    { msg: '算了，先不管了', desc: '任务放弃' },
    { msg: '嗯', desc: '隐性不满' },
    { msg: '不对', desc: '显式负反馈' },
    { msg: '这个看起来还行', desc: '中性反馈' },
  ];

  for (const tc of testCases) {
    const result = detector.detect('test-session', 'test', 0, '', tc.msg);
    console.log(`【${tc.desc}】"${tc.msg}"`);
    console.log(`  失败: ${result.isFailure}`);
    if (result.isFailure) {
      console.log(`  类型: ${result.failureType}`);
      console.log(`  置信度: ${result.confidence}`);
      console.log(`  证据: ${result.evidence.join(', ')}`);
    }
    console.log();
  }

  detector.close();
}
