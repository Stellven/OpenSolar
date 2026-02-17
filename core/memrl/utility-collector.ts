/**
 * MEMRL Utility Collector - 信号采集器
 *
 * Phase 1 核心组件
 * 职责: 任务完成后自动检测 Success/Failure 信号
 */

import { Database } from 'bun:sqlite';

interface TaskContext {
  toolName: string;
  exitCode: number;
  output?: string;
  userFeedback?: string;
  testResult?: 'pass' | 'fail' | 'unknown';
  reviewResult?: 'approved' | 'rejected' | 'unknown';
  sessionId: string;
}

interface SignalResult {
  signal: 'success' | 'failure' | 'unknown';
  confidence: number;
  evidence: string[];
}

interface Experience {
  intentHash: string;
  experienceId: string;
  experienceType: string;
}

export class UtilityCollector {
  private db: Database;

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
  }

  /**
   * 检测 Success 信号
   *
   * 判定条件 (任一满足):
   * 1. 用户说 "好/可以/OK"
   * 2. 工具返回码 = 0
   * 3. 测试通过
   * 4. 审查通过
   */
  detectSuccess(context: TaskContext): SignalResult {
    const evidence: string[] = [];
    let confidence = 0;

    // 1. 检查用户显式反馈
    if (context.userFeedback) {
      const positivePatterns = [
        /^(好|可以|ok|好的|没问题|thanks|谢谢|棒|赞|优秀)$/i,
        /(^|\s)(good|great|perfect|nice|excellent|well done)(\s|$)/i
      ];

      for (const pattern of positivePatterns) {
        if (pattern.test(context.userFeedback)) {
          evidence.push(`用户正向反馈: "${context.userFeedback}"`);
          confidence += 0.5;
          break;
        }
      }
    }

    // 2. 检查工具返回码
    if (context.exitCode === 0) {
      evidence.push(`工具执行成功 (exitCode=0)`);
      confidence += 0.3;
    }

    // 3. 检查测试结果
    if (context.testResult === 'pass') {
      evidence.push(`测试通过`);
      confidence += 0.4;
    }

    // 4. 检查审查结果
    if (context.reviewResult === 'approved') {
      evidence.push(`审查通过`);
      confidence += 0.4;
    }

    const signal = confidence >= 0.3 ? 'success' : 'unknown';
    return { signal, confidence: Math.min(1, confidence), evidence };
  }

  /**
   * 检测 Failure 信号
   *
   * 判定条件 (任一满足):
   * 1. 用户说 "不对/错了/重来"
   * 2. 工具返回码 ≠ 0
   * 3. 测试失败
   * 4. 审查返工
   * 5. 任务中断/超时
   */
  detectFailure(context: TaskContext): SignalResult {
    const evidence: string[] = [];
    let confidence = 0;

    // 1. 检查用户显式负反馈
    if (context.userFeedback) {
      const negativePatterns = [
        /^(不对|错了|重来|不行|不好|有问题|错了)$/i,
        /(^|\s)(wrong|error|fail|bad|incorrect|mistake)(\s|$)/i,
        /^(应该是|其实是|你忘了|你漏了)/i  // 纠正性反馈
      ];

      for (const pattern of negativePatterns) {
        if (pattern.test(context.userFeedback)) {
          evidence.push(`用户负向反馈: "${context.userFeedback}"`);
          confidence += 0.6;
          break;
        }
      }
    }

    // 2. 检查工具返回码
    if (context.exitCode !== 0 && context.exitCode !== undefined) {
      evidence.push(`工具执行失败 (exitCode=${context.exitCode})`);
      confidence += 0.4;
    }

    // 3. 检查测试结果
    if (context.testResult === 'fail') {
      evidence.push(`测试失败`);
      confidence += 0.5;
    }

    // 4. 检查审查结果
    if (context.reviewResult === 'rejected') {
      evidence.push(`审查返工`);
      confidence += 0.5;
    }

    // 5. 检查输出中的错误关键词
    if (context.output) {
      const errorPatterns = [
        /error:/i,
        /exception/i,
        /failed/i,
        /timeout/i
      ];

      for (const pattern of errorPatterns) {
        if (pattern.test(context.output)) {
          evidence.push(`输出包含错误: ${pattern.source}`);
          confidence += 0.2;
          break;
        }
      }
    }

    const signal = confidence >= 0.3 ? 'failure' : 'unknown';
    return { signal, confidence: Math.min(1, confidence), evidence };
  }

  /**
   * 综合判断信号
   */
  detect(context: TaskContext): SignalResult {
    const success = this.detectSuccess(context);
    const failure = this.detectFailure(context);

    // Failure 优先级更高
    if (failure.signal === 'failure') {
      return failure;
    }

    if (success.signal === 'success') {
      return success;
    }

    return { signal: 'unknown', confidence: 0, evidence: ['无明确信号'] };
  }

  /**
   * 记录信号到数据库
   */
  record(
    experience: Experience,
    signal: 'success' | 'failure',
    evidence: string[],
    sessionId: string
  ): number {
    const reward = signal === 'success' ? 1 : 0;

    const stmt = this.db.prepare(`
      INSERT INTO memrl_utility_store
      (intent_hash, experience_id, experience_type, utility_total, fuse_status, session_id, evidence_json)
      VALUES (?, ?, ?, ?, 'OK', ?, ?)
    `);

    const result = stmt.run(
      experience.intentHash,
      experience.experienceId,
      experience.experienceType,
      reward,
      sessionId,
      JSON.stringify({ signal, evidence, timestamp: new Date().toISOString() })
    );

    return result.lastInsertRowid;
  }

  /**
   * 从工具调用上下文提取信号并记录
   */
  collectFromToolCall(
    toolName: string,
    exitCode: number,
    output: string,
    userFeedback: string | undefined,
    intentHash: string,
    sessionId: string
  ): { signal: 'success' | 'failure' | 'unknown'; recorded: boolean } {
    const context: TaskContext = {
      toolName,
      exitCode,
      output,
      userFeedback,
      sessionId,
      testResult: 'unknown',
      reviewResult: 'unknown'
    };

    // 特殊处理测试工具
    if (toolName.toLowerCase().includes('test')) {
      if (output.toLowerCase().includes('pass')) {
        context.testResult = 'pass';
      } else if (output.toLowerCase().includes('fail')) {
        context.testResult = 'fail';
      }
    }

    // 特殊处理审查工具
    if (toolName.toLowerCase().includes('review')) {
      if (output.toLowerCase().includes('approved')) {
        context.reviewResult = 'approved';
      } else if (output.toLowerCase().includes('rejected')) {
        context.reviewResult = 'rejected';
      }
    }

    const result = this.detect(context);

    if (result.signal !== 'unknown') {
      const experience: Experience = {
        intentHash,
        experienceId: `exp_${Date.now()}`,
        experienceType: 'tool_call'
      };

      this.record(experience, result.signal, result.evidence, sessionId);
      return { signal: result.signal, recorded: true };
    }

    return { signal: 'unknown', recorded: false };
  }

  /**
   * 获取最近的信号记录
   */
  getRecentSignals(limit: number = 10): any[] {
    const stmt = this.db.prepare(`
      SELECT
        id,
        intent_hash,
        utility_total as reward,
        fuse_status,
        created_at,
        evidence_json
      FROM memrl_utility_store
      WHERE evidence_json IS NOT NULL
      ORDER BY created_at DESC
      LIMIT ?
    `);

    return stmt.all(limit);
  }

  /**
   * 获取信号统计
   */
  getStats(): { total: number; success: number; failure: number; unknown: number } {
    const stmt = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN utility_total = 1 THEN 1 ELSE 0 END) as success,
        SUM(CASE WHEN utility_total = 0 THEN 1 ELSE 0 END) as failure
      FROM memrl_utility_store
      WHERE evidence_json IS NOT NULL
    `);

    const result = stmt.get() as any;
    return {
      total: result?.total || 0,
      success: result?.success || 0,
      failure: result?.failure || 0,
      unknown: 0
    };
  }

  close(): void {
    this.db.close();
  }
}

// CLI 测试
if (import.meta.main) {
  const collector = new UtilityCollector();

  console.log('🧪 Utility Collector 测试\n');

  // 测试用例
  const testCases: { name: string; context: TaskContext }[] = [
    {
      name: '用户正向反馈',
      context: {
        toolName: 'bash',
        exitCode: 0,
        userFeedback: '好',
        sessionId: 'test'
      }
    },
    {
      name: '工具执行失败',
      context: {
        toolName: 'bash',
        exitCode: 1,
        output: 'Error: command not found',
        sessionId: 'test'
      }
    },
    {
      name: '测试通过',
      context: {
        toolName: 'test',
        exitCode: 0,
        output: 'All tests passed',
        sessionId: 'test'
      }
    },
    {
      name: '用户负向反馈',
      context: {
        toolName: 'edit',
        exitCode: 0,
        userFeedback: '不对，应该是这样的',
        sessionId: 'test'
      }
    }
  ];

  for (const tc of testCases) {
    const result = collector.detect(tc.context);
    console.log(`【${tc.name}】`);
    console.log(`  信号: ${result.signal}`);
    console.log(`  置信度: ${result.confidence.toFixed(2)}`);
    console.log(`  证据: ${result.evidence.join(', ')}`);
    console.log();
  }

  // 显示统计
  const stats = collector.getStats();
  console.log('📊 信号统计:', stats);

  collector.close();
}
