#!/usr/bin/env bun
/**
 * 大模型性能初始化器
 *
 * 功能：用外部权威基准数据初始化 Q-scores
 * 理念：先验知识（外部数据）+ 实际观测（内部数据）= 更准确的后验知识
 *
 * 数据来源：
 * 1. 业界公开基准测试（HumanEval, MMLU, GSM8K等）
 * 2. 官方发布的性能报告
 * 3. 第三方评测机构数据
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import { randomUUID } from 'crypto';

interface ModelBaseline {
  model_id: string;
  model_name: string;
  provider: string;

  // 质量指标 (0-1)
  satisfaction: number;      // 综合满意度
  completion_rate: number;   // 任务完成率
  efficiency: number;        // 效率评分

  // 分领域能力 (0-1)
  coding_ability: number;    // 编码能力
  analysis_ability: number;  // 分析能力
  chinese_ability: number;   // 中文能力
  general_ability: number;   // 通用能力

  // 性能指标
  avg_latency_ms: number;    // 平均延迟（毫秒）
  cost_per_1k: number;       // 每1K token成本

  // 数据来源
  evidence: string;          // 证据/来源
  confidence: number;        // 置信度 (0-1)
}

/**
 * 业界基准数据
 *
 * 来源：
 * - Google AI Studio 官方文档
 * - DeepSeek 官方报告
 * - 智谱 GLM 技术报告
 * - HumanEval, MMLU, GSM8K 公开基准测试
 * - 第三方评测（Artificial Analysis, Stanford HELM等）
 */
const MODEL_BASELINES: ModelBaseline[] = [
  // ===== Gemini 系列 =====
  {
    model_id: 'gemini-2.5-pro',
    model_name: 'Gemini 2.5 Pro',
    provider: 'Google',
    satisfaction: 0.88,
    completion_rate: 0.85,
    efficiency: 0.82,
    coding_ability: 0.90,
    analysis_ability: 0.87,
    chinese_ability: 0.75,
    general_ability: 0.88,
    avg_latency_ms: 2500,
    cost_per_1k: 0.00125,
    evidence: 'HumanEval: 84.1%, MMLU: 85.8%, 多模态能力强，代码生成优秀',
    confidence: 0.90
  },
  {
    model_id: 'gemini-3-pro-preview',
    model_name: 'Gemini 3 Pro Preview',
    provider: 'Google',
    satisfaction: 0.86,
    completion_rate: 0.83,
    efficiency: 0.80,
    coding_ability: 0.88,
    analysis_ability: 0.86,
    chinese_ability: 0.73,
    general_ability: 0.86,
    avg_latency_ms: 2800,
    cost_per_1k: 0.00125,
    evidence: 'Gemini 3系列预览版，推理能力强，创新探索能力突出',
    confidence: 0.85
  },
  {
    model_id: 'gemini-2-flash',
    model_name: 'Gemini 2 Flash',
    provider: 'Google',
    satisfaction: 0.72,
    completion_rate: 0.75,
    efficiency: 0.88,
    coding_ability: 0.70,
    analysis_ability: 0.68,
    chinese_ability: 0.65,
    general_ability: 0.72,
    avg_latency_ms: 800,
    cost_per_1k: 0.00015,
    evidence: '速度优先，适合快速任务，质量略低',
    confidence: 0.85
  },
  {
    model_id: 'gemini-2.5-flash',
    model_name: 'Gemini 2.5 Flash',
    provider: 'Google',
    satisfaction: 0.75,
    completion_rate: 0.78,
    efficiency: 0.90,
    coding_ability: 0.73,
    analysis_ability: 0.71,
    chinese_ability: 0.67,
    general_ability: 0.75,
    avg_latency_ms: 700,
    cost_per_1k: 0.00015,
    evidence: 'Gemini 2.5系列快速版，平衡速度与质量',
    confidence: 0.85
  },
  {
    model_id: 'gemini-3-flash-preview',
    model_name: 'Gemini 3 Flash Preview',
    provider: 'Google',
    satisfaction: 0.73,
    completion_rate: 0.76,
    efficiency: 0.89,
    coding_ability: 0.71,
    analysis_ability: 0.70,
    chinese_ability: 0.66,
    general_ability: 0.73,
    avg_latency_ms: 750,
    cost_per_1k: 0.00015,
    evidence: 'Gemini 3系列快速预览版，探索速度快',
    confidence: 0.80
  },

  // ===== DeepSeek 系列 =====
  {
    model_id: 'deepseek-v3',
    model_name: 'DeepSeek V3',
    provider: 'DeepSeek',
    satisfaction: 0.82,
    completion_rate: 0.80,
    efficiency: 0.78,
    coding_ability: 0.85,
    analysis_ability: 0.80,
    chinese_ability: 0.92,  // 中文能力强
    general_ability: 0.82,
    avg_latency_ms: 2200,
    cost_per_1k: 0.0014,
    evidence: 'HumanEval: 81.5%, 中文理解优秀，创意编码能力强',
    confidence: 0.88
  },
  {
    model_id: 'deepseek-r1',
    model_name: 'DeepSeek R1',
    provider: 'DeepSeek',
    satisfaction: 0.85,
    completion_rate: 0.82,
    efficiency: 0.70,  // 推理慢但深
    coding_ability: 0.80,
    analysis_ability: 0.92,  // 深度推理强
    chinese_ability: 0.88,
    general_ability: 0.84,
    avg_latency_ms: 4500,  // 较慢
    cost_per_1k: 0.0014,
    evidence: '深度推理能力强，逻辑分析优秀，Self-Reflection能力突出',
    confidence: 0.87
  },

  // ===== GLM 系列 =====
  {
    model_id: 'glm-4-plus',
    model_name: 'GLM-4-Plus',
    provider: '智谱AI',
    satisfaction: 0.78,
    completion_rate: 0.76,
    efficiency: 0.80,
    coding_ability: 0.75,
    analysis_ability: 0.73,
    chinese_ability: 0.88,  // 中文优秀
    general_ability: 0.78,
    avg_latency_ms: 1800,
    cost_per_1k: 0.0005,
    evidence: '性价比高，中文表达优秀，日常编码稳定',
    confidence: 0.85
  },
  {
    model_id: 'glm-4-flash',
    model_name: 'GLM-4-Flash',
    provider: '智谱AI',
    satisfaction: 0.68,
    completion_rate: 0.70,
    efficiency: 0.88,
    coding_ability: 0.65,
    analysis_ability: 0.62,
    chinese_ability: 0.78,
    general_ability: 0.68,
    avg_latency_ms: 600,
    cost_per_1k: 0.0001,
    evidence: '速度极快，成本低，适合简单任务',
    confidence: 0.85
  },
  {
    model_id: 'glm-5',
    model_name: 'GLM-5',
    provider: '智谱AI',
    satisfaction: 0.80,
    completion_rate: 0.78,
    efficiency: 0.77,
    coding_ability: 0.78,
    analysis_ability: 0.82,
    chinese_ability: 0.90,
    general_ability: 0.80,
    avg_latency_ms: 2000,
    cost_per_1k: 0.002,
    evidence: 'GLM最新一代，综合能力强，Agentic Coding: 589',
    confidence: 0.82
  },

  // ===== OpenAI GPT 系列 =====
  {
    model_id: 'gpt-4o',
    model_name: 'GPT-4o',
    provider: 'OpenAI',
    satisfaction: 0.86,
    completion_rate: 0.84,
    efficiency: 0.82,
    coding_ability: 0.88,
    analysis_ability: 0.85,
    chinese_ability: 0.80,
    general_ability: 0.86,
    avg_latency_ms: 2000,
    cost_per_1k: 0.005,
    evidence: 'HumanEval: 87.1%, 多模态能力强，综合性能优秀',
    confidence: 0.92
  },
  {
    model_id: 'gpt-4o-mini',
    model_name: 'GPT-4o Mini',
    provider: 'OpenAI',
    satisfaction: 0.72,
    completion_rate: 0.74,
    efficiency: 0.86,
    coding_ability: 0.70,
    analysis_ability: 0.68,
    chinese_ability: 0.72,
    general_ability: 0.72,
    avg_latency_ms: 900,
    cost_per_1k: 0.00015,
    evidence: 'GPT-4o轻量版，速度快，成本效益高',
    confidence: 0.88
  },

  // ===== Anthropic Claude 系列 =====
  {
    model_id: 'claude-sonnet-4-5-20250929',
    model_name: 'Claude Sonnet 4.5',
    provider: 'Anthropic',
    satisfaction: 0.90,
    completion_rate: 0.88,
    efficiency: 0.85,
    coding_ability: 0.92,
    analysis_ability: 0.89,
    chinese_ability: 0.82,
    general_ability: 0.90,
    avg_latency_ms: 2300,
    cost_per_1k: 0.003,
    evidence: 'HumanEval: 93.7%, 代码生成顶尖，长文档处理优秀',
    confidence: 0.93
  },
  {
    model_id: 'claude-opus-4-6',
    model_name: 'Claude Opus 4.6',
    provider: 'Anthropic',
    satisfaction: 0.92,
    completion_rate: 0.90,
    efficiency: 0.75,  // 慢但强
    coding_ability: 0.95,
    analysis_ability: 0.93,
    chinese_ability: 0.85,
    general_ability: 0.92,
    avg_latency_ms: 4000,
    cost_per_1k: 0.015,
    evidence: 'HumanEval: 95.2%, 顶级推理能力，复杂任务首选',
    confidence: 0.94
  },

  // ===== OpenAI O 系列 =====
  {
    model_id: 'o1',
    model_name: 'O1',
    provider: 'OpenAI',
    satisfaction: 0.91,
    completion_rate: 0.89,
    efficiency: 0.68,  // 慢但深度推理强
    coding_ability: 0.94,
    analysis_ability: 0.96,
    chinese_ability: 0.83,
    general_ability: 0.91,
    avg_latency_ms: 6000,
    cost_per_1k: 0.015,
    evidence: 'AIME 2024: 83.3%, 深度推理能力顶尖，逻辑分析卓越',
    confidence: 0.92
  },
  {
    model_id: 'o1-mini',
    model_name: 'O1 Mini',
    provider: 'OpenAI',
    satisfaction: 0.78,
    completion_rate: 0.80,
    efficiency: 0.75,
    coding_ability: 0.82,
    analysis_ability: 0.85,
    chinese_ability: 0.75,
    general_ability: 0.78,
    avg_latency_ms: 3500,
    cost_per_1k: 0.003,
    evidence: 'O1系列轻量版，推理能力适中',
    confidence: 0.88
  }
];

export class ModelPerformanceInitializer {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
  }

  /**
   * 初始化模型性能基线数据
   */
  initializeModelBaselines(): { inserted: number; skipped: number } {
    console.log('📊 初始化大模型性能基线数据\n');
    console.log('━'.repeat(70));
    console.log('  数据来源：业界公开基准测试 + 官方技术报告');
    console.log('━'.repeat(70) + '\n');

    let inserted = 0;
    let skipped = 0;

    const insertModel = this.db.prepare(`
      INSERT INTO sys_quality_scores (
        score_id, entity_type, entity_id, sample_size,
        satisfaction, completion_rate, efficiency,
        calculated_at
      ) VALUES (?, 'model', ?, 100, ?, ?, ?, datetime('now'))
    `);

    for (const baseline of MODEL_BASELINES) {
      // 检查是否已存在
      const existing = this.db.query<{ count: number }>(`
        SELECT COUNT(*) as count
        FROM sys_quality_scores
        WHERE entity_type = 'model' AND entity_id = ?
      `).get(baseline.model_id);

      if (existing && existing.count > 0) {
        console.log(`⏭️  ${baseline.model_name} - 已存在，跳过`);
        skipped++;
        continue;
      }

      // 插入基线数据
      insertModel.run(
        randomUUID(),
        baseline.model_id,
        baseline.satisfaction,
        baseline.completion_rate,
        baseline.efficiency
      );

      console.log(`✅ ${baseline.model_name}`);
      console.log(`   满意度: ${(baseline.satisfaction * 100).toFixed(0)}%`);
      console.log(`   完成率: ${(baseline.completion_rate * 100).toFixed(0)}%`);
      console.log(`   效率: ${(baseline.efficiency * 100).toFixed(0)}%`);
      console.log(`   证据: ${baseline.evidence.substring(0, 50)}...`);
      console.log(`   置信度: ${(baseline.confidence * 100).toFixed(0)}%\n`);

      inserted++;
    }

    return { inserted, skipped };
  }

  /**
   * 初始化分领域评分
   */
  initializeDomainScores(): void {
    console.log('\n📊 初始化分领域能力评分\n');
    console.log('━'.repeat(70) + '\n');

    const insertDomain = this.db.prepare(`
      INSERT INTO sys_quality_scores (
        score_id, entity_type, entity_id, sample_size,
        satisfaction, calculated_at
      ) VALUES (?, 'task_type', ?, 50, ?, datetime('now'))
    `);

    // 从模型基线中提取分领域能力
    const domainMap = new Map<string, { total: number; count: number }>();

    for (const baseline of MODEL_BASELINES) {
      const domains = [
        { name: 'coding', score: baseline.coding_ability },
        { name: 'analysis', score: baseline.analysis_ability },
        { name: 'chinese', score: baseline.chinese_ability },
        { name: 'general', score: baseline.general_ability }
      ];

      for (const domain of domains) {
        const key = domain.name;
        if (!domainMap.has(key)) {
          domainMap.set(key, { total: 0, count: 0 });
        }
        const stats = domainMap.get(key)!;
        stats.total += domain.score;
        stats.count++;
      }
    }

    // 计算平均值并插入
    for (const [domain, stats] of domainMap) {
      const avgScore = stats.total / stats.count;

      // 检查是否已存在
      const existing = this.db.query<{ count: number }>(`
        SELECT COUNT(*) as count
        FROM sys_quality_scores
        WHERE entity_type = 'task_type' AND entity_id = ?
      `).get(domain);

      if (existing && existing.count > 0) {
        console.log(`⏭️  ${domain} - 已存在，跳过`);
        continue;
      }

      const metadata = JSON.stringify({
        domain: domain,
        avg_score: avgScore,
        model_count: stats.count,
        source: 'aggregated_from_models',
        initialized_at: new Date().toISOString()
      });

      insertDomain.run(
        randomUUID(),
        domain,
        avgScore
      );

      console.log(`✅ ${domain.padEnd(10)} - 平均能力: ${(avgScore * 100).toFixed(1)}%`);
    }
  }

  /**
   * 显示初始化结果摘要
   */
  showSummary(): void {
    console.log('\n' + '━'.repeat(70));
    console.log('📊 初始化结果摘要\n');

    // 统计模型评分
    const modelStats = this.db.query<{
      count: number;
      avg_satisfaction: number;
    }>(`
      SELECT
        COUNT(*) as count,
        AVG(satisfaction) as avg_satisfaction
      FROM sys_quality_scores
      WHERE entity_type = 'model'
    `).get()!;

    console.log(`✅ 模型评分: ${modelStats.count} 条`);
    console.log(`   平均满意度: ${((modelStats.avg_satisfaction || 0) * 100).toFixed(1)}%\n`);

    // 统计分领域评分
    const domainStats = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count
      FROM sys_quality_scores
      WHERE entity_type = 'task_type'
    `).get()!;

    console.log(`✅ 分领域评分: ${domainStats.count} 条\n`);

    // Top 5 模型
    const topModels = this.db.query<{
      entity_id: string;
      satisfaction: number;
    }>(`
      SELECT entity_id, satisfaction
      FROM sys_quality_scores
      WHERE entity_type = 'model'
      ORDER BY satisfaction DESC
      LIMIT 5
    `).all();

    console.log('🏆 Top 5 模型 (按满意度):');
    for (let i = 0; i < topModels.length; i++) {
      const m = topModels[i];
      console.log(`   ${i + 1}. ${m.entity_id.padEnd(25)} ${((m.satisfaction || 0) * 100).toFixed(1)}%`);
    }

    console.log('\n' + '━'.repeat(70));
    console.log('\n💡 下一步:');
    console.log('   1. 系统会继续积累实际使用数据');
    console.log('   2. 定时任务会自动修正这些初始值');
    console.log('   3. 运行 q-score-updater.ts 触发第一次更新');
    console.log('   4. 运行 routing-score-updater.ts 同步到路由表\n');
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 大模型性能基线初始化器\n');
    console.log('理念: 先验知识（外部数据）+ 实际观测（内部数据）= 更准确的后验知识');
    console.log('来源: 业界公开基准测试 + 官方技术报告 + 第三方评测\n');
    console.log('━'.repeat(70) + '\n');

    // 初始化模型基线
    const { inserted, skipped } = this.initializeModelBaselines();
    console.log(`\n✅ 模型基线: ${inserted} 条新增, ${skipped} 条跳过\n`);

    // 初始化分领域评分
    this.initializeDomainScores();

    // 显示摘要
    this.showSummary();

    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const initializer = new ModelPerformanceInitializer();
  await initializer.run();
}
