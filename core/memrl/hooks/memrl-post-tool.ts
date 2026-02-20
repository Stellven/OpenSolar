/**
 * MEMRL PostToolUse Hook v2
 *
 * 在工具调用后自动采集 Success/Failure 信号
 * 并更新 Q 值
 *
 * 集成到 Claude Code 的 PostToolUse hook chain
 *
 * v2 更新:
 * - 集成 EnhancedFailureDetector 解决 100:1 数据不平衡
 * - 新增隐式失败信号: 纠正/放弃/不满
 */

import { UtilityCollector } from '../utility-collector';
import { EnhancedFailureDetector, FailureDetectionResult, FailureType } from '../enhanced-failure-detector';
import { QUpdater } from '../q-updater';
import { ImplicitRewardExtractor } from '../implicit-reward-extractor';

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
  private enhancedDetector: EnhancedFailureDetector;
  private updater: QUpdater;
  private implicitExtractor: ImplicitRewardExtractor;
  private enabled: boolean = true;

  constructor(
    dbPath: string = `${process.env.HOME}/.solar/solar.db`
  ) {
    this.collector = new UtilityCollector(dbPath);
    this.enhancedDetector = new EnhancedFailureDetector(dbPath);
    this.updater = new QUpdater(dbPath);
    this.implicitExtractor = new ImplicitRewardExtractor(dbPath);
  }

  /**
   * Hook 主入口 v2
   *
   * 在每个工具调用后执行
   * 优先使用增强型检测器捕获更多失败信号
   */
  async execute(context: ToolCallContext): Promise<{
    signalDetected: boolean;
    signalType?: 'success' | 'failure';
    failureType?: FailureType;
    qValue?: number;
    evidence?: string[];
  }> {
    if (!this.enabled) {
      return { signalDetected: false };
    }

    const { toolName, exitCode, output, userFeedback, intentHash, sessionId } = context;
    const hash = intentHash || this.generateIntentHash(toolName);

    // 1. 优先使用增强型失败检测器
    const failureResult = this.enhancedDetector.detect(
      sessionId,
      toolName,
      exitCode,
      output,
      userFeedback
    );

    if (failureResult.isFailure) {
      // 记录失败信号
      this.enhancedDetector.recordFailure(sessionId, hash, failureResult);

      // 更新 Q 值 (失败 = reward 0)
      const qValue = this.updater.update(hash, `fail_${Date.now()}`, 0);

      console.log(`[MEMRL] 🚨 检测到失败信号: ${failureResult.failureType}`);
      console.log(`        证据: ${failureResult.evidence.join(', ')}`);
      console.log(`        Q 值更新: ${qValue.toFixed(3)}`);

      return {
        signalDetected: true,
        signalType: 'failure',
        failureType: failureResult.failureType!,
        qValue,
        evidence: failureResult.evidence
      };
    }

    // 2. 回退到传统成功检测
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

    // 3. 更新 Q 值
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

    console.log(`[MEMRL] ✅ 检测到 ${result.signal} 信号，Q 值更新: ${qValue.toFixed(3)}`);

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
   * 获取统计 (v3 - 包含隐式奖励提取器)
   */
  async getStats(): Promise<{
    collector: { totalRecords: number; successCount: number; failureCount: number };
    enhanced: { total: number; byType: Record<string, number>; avgConfidence: number };
    implicit: { totalExtracted: number; byType: Record<string, number>; avgReward: number };
    updater: ReturnType<QUpdater['getStats']>;
    balanceRatio: string;
    fusedQImpact: { beforeAvg: number; afterAvg: number; highQReduction: number };
  }> {
    const cStats = this.collector.getStats();
    const eStats = this.enhancedDetector.getStats();
    const iStats = await this.implicitExtractor.getStats();
    const uStats = this.updater.getStats();

    const totalSuccess = cStats.success;
    const totalFailure = cStats.failure + eStats.total + iStats.totalExtracted;
    const balanceRatio = totalFailure > 0
      ? `${(totalSuccess / totalFailure).toFixed(1)}:1`
      : '∞:1';

    // 计算融合 Q 影响
    const fusedQImpact = this.updater.db.prepare(`
      SELECT
        AVG(q_value) as before_avg,
        AVG(0.7 * q_value + 0.3 * u_implicit) as after_avg,
        SUM(CASE WHEN q_value >= 0.6 THEN 1 ELSE 0 END) as high_q_before,
        SUM(CASE WHEN (0.7 * q_value + 0.3 * u_implicit) >= 0.6 THEN 1 ELSE 0 END) as high_q_after
      FROM memrl_utility_store
    `).get() as {
      before_avg: number;
      after_avg: number;
      high_q_before: number;
      high_q_after: number;
    };

    return {
      collector: {
        totalRecords: cStats.total,
        successCount: cStats.success,
        failureCount: cStats.failure
      },
      enhanced: eStats,
      implicit: {
        totalExtracted: iStats.totalExtracted,
        byType: iStats.byType,
        avgReward: iStats.avgReward
      },
      updater: uStats,
      balanceRatio,
      fusedQImpact: {
        beforeAvg: fusedQImpact.before_avg,
        afterAvg: fusedQImpact.after_avg,
        highQReduction: fusedQImpact.high_q_before - fusedQImpact.high_q_after
      }
    };
  }

  close(): void {
    this.collector.close();
    this.enhancedDetector.close();
    this.updater.close();
    this.implicitExtractor.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const hook = new MEMRLPostToolHook();

  const command = process.argv[2] || 'stats';

  if (command === 'stats') {
    console.log('📊 MEMRL Hook 统计 (v3)\n');
    const stats = await hook.getStats();

    console.log('Utility Collector (传统):');
    console.log(`  总记录: ${stats.collector.totalRecords}`);
    console.log(`  成功: ${stats.collector.successCount}`);
    console.log(`  失败: ${stats.collector.failureCount}`);

    console.log('\nEnhanced Failure Detector (新增):');
    console.log(`  总失败信号: ${stats.enhanced.total}`);
    console.log(`  平均置信度: ${stats.enhanced.avgConfidence.toFixed(2)}`);
    console.log(`  按类型:`);
    for (const [type, count] of Object.entries(stats.enhanced.byType)) {
      console.log(`    ${type}: ${count}`);
    }

    console.log('\nImplicit Reward Extractor (v3 新增):');
    console.log(`  总提取: ${stats.implicit.totalExtracted}`);
    console.log(`  平均奖励: ${stats.implicit.avgReward.toFixed(3)}`);
    console.log(`  按类型:`);
    for (const [type, count] of Object.entries(stats.implicit.byType)) {
      console.log(`    ${type}: ${count}`);
    }

    console.log('\nQ-Updater:');
    console.log(`  总记录: ${stats.updater.totalRecords}`);
    console.log(`  平均 Q: ${stats.updater.avgQ.toFixed(3)}`);
    console.log(`  高 Q (≥0.6): ${stats.updater.highQ}`);

    console.log('\n融合 Q 影响:');
    console.log(`  融合前平均: ${stats.fusedQImpact.beforeAvg.toFixed(3)}`);
    console.log(`  融合后平均: ${stats.fusedQImpact.afterAvg.toFixed(3)}`);
    console.log(`  高 Q 减少: ${stats.fusedQImpact.highQReduction} 条`);

    console.log(`\n📊 数据平衡比: ${stats.balanceRatio}`);
  }

  if (command === 'test') {
    console.log('🧪 测试 Hook 执行 (v2)\n');

    // 模拟成功场景
    console.log('--- 成功场景 ---');
    const successResult = await hook.execute({
      toolName: 'Bash',
      exitCode: 0,
      output: '构建成功',
      userFeedback: '好',
      sessionId: 'test_session'
    });
    console.log('结果:', successResult);

    // 模拟失败场景 (显式)
    console.log('\n--- 显式失败 ---');
    const failureResult = await hook.execute({
      toolName: 'Bash',
      exitCode: 1,
      output: 'error: command not found',
      sessionId: 'test_session'
    });
    console.log('结果:', failureResult);

    // 模拟纠正场景 (新增!)
    console.log('\n--- 用户纠正 (新增) ---');
    const correctionResult = await hook.execute({
      toolName: 'Edit',
      exitCode: 0,
      output: '文件已修改',
      userFeedback: '应该是这样的，你忘了加参数',
      sessionId: 'test_session'
    });
    console.log('结果:', correctionResult);

    // 模拟隐性不满场景
    console.log('\n--- 隐性不满 (新增) ---');
    const dissatisfactionResult = await hook.execute({
      toolName: 'Bash',
      exitCode: 0,
      output: '完成',
      userFeedback: '嗯',
      sessionId: 'test_session'
    });
    console.log('结果:', dissatisfactionResult);
  }

  hook.close();
}
