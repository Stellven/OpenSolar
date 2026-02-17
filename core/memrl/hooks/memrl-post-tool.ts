/**
 * MEMRL PostToolUse Hook
 *
 * 在工具调用后自动采集 Success/Failure 信号
 * 并更新 Q 值
 *
 * 集成到 Claude Code 的 PostToolUse hook chain
 */

import { UtilityCollector } from '../utility-collector';
import { QUpdater } from '../q-updater';

interface ToolCallContext {
  toolName: string;
  exitCode: number;
  output: string;
  userFeedback?: string;
  intentHash?: string;
  sessionId: string;
}

export class MEMRLPostToolHook {
  private collector: UtilityCollector;
  private updater: QUpdater;
  private enabled: boolean = true;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`
  ) {
    this.collector = new UtilityCollector(dbPath);
    this.updater = new QUpdater(dbPath);
  }

  /**
   * Hook 主入口
   *
   * 在每个工具调用后执行
   */
  async execute(context: ToolCallContext): Promise<{
    signalDetected: boolean;
    signalType?: 'success' | 'failure';
    qValue?: number;
  }> {
    if (!this.enabled) {
      return { signalDetected: false };
    }

    const { toolName, exitCode, output, userFeedback, intentHash, sessionId } = context;

    // 1. 检测信号
    const hash = intentHash || this.generateIntentHash(toolName);
    const result = this.collector.collectFromToolCall(
      toolName,
      exitCode,
      output,
      userFeedback || undefined,
      hash,
      sessionId
    );

    if (result.signal === 'unknown' || !result.recorded) {
      return { signalDetected: false };
    }

    // 2. 更新 Q 值 (查询刚才记录的 experience)
    const recent = this.collector.getRecentSignals(1);
    if (recent.length === 0) {
      return { signalDetected: false };
    }

    const reward = result.signal === 'success' ? 1 : 0;
    const qValue = this.updater.update(
      hash,
      `exp_${recent[0].id}`,
      reward
    );

    console.log(`[MEMRL] 检测到 ${result.signal} 信号，Q 值更新: ${qValue.toFixed(3)}`);

    return {
      signalDetected: true,
      signalType: result.signal,
      qValue
    };
  }

  /**
   * 生成 Intent Hash (简化版)
   */
  private generateIntentHash(toolName: string): string {
    // 基于工具名生成 hash
    let hash = 0;
    for (let i = 0; i < toolName.length; i++) {
      const char = toolName.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return `intent_tool_${Math.abs(hash).toString(16)}`;
  }

  /**
   * 启用/禁用 Hook
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  /**
   * 获取统计
   */
  getStats(): {
    collector: { totalRecords: number; successCount: number; failureCount: number };
    updater: ReturnType<QUpdater['getStats']>;
  } {
    const cStats = this.collector.getStats();
    return {
      collector: {
        totalRecords: cStats.total,
        successCount: cStats.success,
        failureCount: cStats.failure
      },
      updater: this.updater.getStats()
    };
  }

  close(): void {
    this.collector.close();
    this.updater.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const hook = new MEMRLPostToolHook();

  const command = process.argv[2] || 'stats';

  if (command === 'stats') {
    console.log('📊 MEMRL Hook 统计\n');
    const stats = hook.getStats();
    console.log('Utility Collector:');
    console.log(`  总记录: ${stats.collector.totalRecords}`);
    console.log(`  成功: ${stats.collector.successCount}`);
    console.log(`  失败: ${stats.collector.failureCount}`);
    console.log('\nQ-Updater:');
    console.log(`  总记录: ${stats.updater.totalRecords}`);
    console.log(`  平均 Q: ${stats.updater.avgQ.toFixed(3)}`);
    console.log(`  高 Q (≥0.6): ${stats.updater.highQ}`);
  }

  if (command === 'test') {
    console.log('🧪 测试 Hook 执行\n');

    // 模拟成功场景
    const successResult = await hook.execute({
      toolName: 'Bash',
      exitCode: 0,
      output: '构建成功',
      userFeedback: '好',
      sessionId: 'test_session'
    });
    console.log('成功场景:', successResult);

    // 模拟失败场景
    const failureResult = await hook.execute({
      toolName: 'Bash',
      exitCode: 1,
      output: 'error: command not found',
      sessionId: 'test_session'
    });
    console.log('失败场景:', failureResult);
  }

  hook.close();
}
