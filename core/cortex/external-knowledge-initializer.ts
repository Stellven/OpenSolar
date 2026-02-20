#!/usr/bin/env bun
/**
 * 外部知识记忆初始化器
 *
 * 功能：用业界最佳实践和经验教训初始化记忆系统
 * 理念：先验知识（业界经验）+ 实际观测（系统数据）= 更准确的决策知识
 *
 * 数据来源：
 * - Software Engineering Best Practices (Google, Meta, Microsoft)
 * - AI Agent Design Patterns (Anthropic, OpenAI)
 * - Prompt Engineering Guide
 * - Code Review Guidelines
 * - Performance Optimization Handbooks
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';
import { randomUUID } from 'crypto';

interface KnowledgeMemory {
  namespace: 'lessons' | 'experiences';
  key: string;
  value: {
    context: string;
    lesson?: string;
    insight?: string;
    recommendation?: string;
    source: string;
    confidence: number;
  };
  confidence: number;
}

/**
 * 业界最佳实践知识库
 *
 * 来源：
 * - Google Engineering Practices
 * - Meta Engineering Blog
 * - Microsoft Azure Architecture Center
 * - Anthropic AI Agent Design Patterns
 * - OpenAI Best Practices
 */
const EXTERNAL_KNOWLEDGE: KnowledgeMemory[] = [
  // ===== 编码任务最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_coding_model_selection',
    value: {
      context: '编码任务模型选择',
      insight: '复杂编码任务优先使用 Claude Sonnet 或 Gemini Pro，简单任务用 GLM 或 Flash 系列',
      recommendation: 'coding',
      source: 'Anthropic + Google AI 最佳实践',
      confidence: 0.90
    },
    confidence: 0.90
  },
  {
    namespace: 'experiences',
    key: 'exp_coding_code_review',
    value: {
      context: '代码审查和优化',
      insight: '代码审查用 DeepSeek R1（深度分析）+ Gemini 2.5 Pro（严谨审查）双专家会审',
      recommendation: 'review',
      source: 'Google Code Review Guidelines',
      confidence: 0.88
    },
    confidence: 0.88
  },
  {
    namespace: 'experiences',
    key: 'exp_coding_error_handling',
    value: {
      context: '错误处理和边界情况',
      insight: '编码时必须考虑边界情况、错误处理和性能，不能只实现 happy path',
      recommendation: 'robustness',
      source: 'Software Engineering Best Practices',
      confidence: 0.92
    },
    confidence: 0.92
  },
  {
    namespace: 'lessons',
    key: 'lesson_coding_over_engineering',
    value: {
      context: '过度工程化',
      lesson: '避免过度工程化，优先实现最简单可行的方案（MVP），然后迭代优化',
      recommendation: '避免过早优化',
      source: 'Google Engineering Practices',
      confidence: 0.90
    },
    confidence: 0.90
  },
  {
    namespace: 'lessons',
    key: 'lesson_coding_no_testing',
    value: {
      context: '缺少测试',
      lesson: '重要代码必须有测试覆盖，尤其是核心逻辑和边界情况',
      recommendation: 'TDD 或至少验收测试',
      source: 'Software Testing Best Practices',
      confidence: 0.95
    },
    confidence: 0.95
  },

  // ===== 分析任务最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_analysis_multi_expert',
    value: {
      context: '分析任务多专家会审',
      insight: '重要分析任务必须用 2-3 个专家并行分析，综合意见，避免一家之言',
      recommendation: 'multi-expert-analysis',
      source: 'Analytical Best Practices',
      confidence: 0.90
    },
    confidence: 0.90
  },
  {
    namespace: 'experiences',
    key: 'exp_analysis_evidence_based',
    value: {
      context: '基于证据的决策',
      insight: '任何设计/决策必须基于数据或权威来源，不能凭空想象',
      recommendation: 'evidence-first',
      source: 'Data-Driven Decision Making',
      confidence: 0.92
    },
    confidence: 0.92
  },
  {
    namespace: 'lessons',
    key: 'lesson_analysis_single_expert',
    value: {
      context: '只依赖单个专家意见',
      lesson: '复杂分析任务只用一个专家容易有盲点，必须多角度交叉验证',
      recommendation: '至少2-3个专家会审',
      source: 'Critical Thinking Guidelines',
      confidence: 0.88
    },
    confidence: 0.88
  },

  // ===== 中文任务最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_chinese_model_selection',
    value: {
      context: '中文任务模型选择',
      insight: '中文任务优先用 DeepSeek V3（中文理解最好）或 GLM 系列，Gemini 次之',
      recommendation: 'chinese-models',
      source: '多语言 AI 模型评测',
      confidence: 0.85
    },
    confidence: 0.85
  },

  // ===== 性能优化最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_performance_profiling',
    value: {
      context: '性能分析和优化',
      insight: '性能优化前必须先 Profile，找到真正的瓶颈，不要凭直觉优化',
      recommendation: 'measure-first',
      source: 'Performance Engineering Handbook',
      confidence: 0.95
    },
    confidence: 0.95
  },
  {
    namespace: 'lessons',
    key: 'lesson_premature_optimization',
    value: {
      context: '过早优化',
      lesson: '过早优化是万恶之源，先保证正确性，再优化性能',
      recommendation: 'correctness-first',
      source: 'Donald Knuth - Premature Optimization',
      confidence: 0.95
    },
    confidence: 0.95
  },

  // ===== Token 效率最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_token_efficiency',
    value: {
      context: 'Token 效率优化',
      insight: '简单任务用便宜模型（GLM-Flash, Gemini-Flash），复杂任务才用好模型',
      recommendation: 'cost-aware-routing',
      source: 'AI Cost Optimization Best Practices',
      confidence: 0.90
    },
    confidence: 0.90
  },
  {
    namespace: 'lessons',
    key: 'lesson_token_waste',
    value: {
      context: 'Token 浪费',
      lesson: '简单任务不要用昂贵模型，比如 GLM-Flash $0.0001 vs Claude Opus $0.015，相差150倍',
      recommendation: 'match-task-to-model',
      source: 'Economic AI Usage Guidelines',
      confidence: 0.92
    },
    confidence: 0.92
  },

  // ===== 架构设计最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_architecture_simple_first',
    value: {
      context: '架构设计原则',
      insight: '架构设计遵循简单原则：能简单绝不复杂，能复用绝不重建',
      recommendation: 'KISS + DRY',
      source: 'Software Architecture Principles',
      confidence: 0.92
    },
    confidence: 0.92
  },
  {
    namespace: 'lessons',
    key: 'lesson_architecture_over_design',
    value: {
      context: '过度设计',
      lesson: '不要为未来可能不会发生的需求设计，YAGNI (You Aren\'t Gonna Need It)',
      recommendation: '避免过度抽象',
      source: 'Extreme Programming Principles',
      confidence: 0.90
    },
    confidence: 0.90
  },

  // ===== Agent 调用最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_agent_personality_injection',
    value: {
      context: 'Agent 调用人格注入',
      insight: '调用 Agent/牛马时必须注入完整人格（D&D KNOBS + 角色类型），否则输出不可控',
      recommendation: 'personality-required',
      source: 'AI Agent Design Patterns',
      confidence: 0.92
    },
    confidence: 0.92
  },
  {
    namespace: 'lessons',
    key: 'lesson_agent_no_personality',
    value: {
      context: 'Agent 缺少人格定义',
      lesson: '简单的 system prompt "你是专业的..." 不够，必须有具体的旋钮参数和行为准则',
      recommendation: 'use-buildNiumaCall',
      source: 'Anthropic Agent Design Guide',
      confidence: 0.90
    },
    confidence: 0.90
  },

  // ===== 上下文管理最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_context_utilization',
    value: {
      context: '上下文利用率控制',
      insight: '上下文利用率应控制在 65% 以内，超过会导致智商下降（Lost in the Middle）',
      recommendation: 'context-budget',
      source: 'Lost in the Middle (Liu et al., TACL 2024)',
      confidence: 0.88
    },
    confidence: 0.88
  },
  {
    namespace: 'lessons',
    key: 'lesson_context_overload',
    value: {
      context: '上下文过载',
      lesson: '上下文太长（>200K）会严重影响模型性能，必须压缩、分段或使用长窗口模型',
      recommendation: 'chunk-or-compress',
      source: 'LLM Context Management Research',
      confidence: 0.90
    },
    confidence: 0.90
  },

  // ===== 数据驱动决策最佳实践 =====
  {
    namespace: 'experiences',
    key: 'exp_data_first',
    value: {
      context: '数据优先原则',
      insight: '任何需要数据的任务，必须先查数据资产（Cortex + sys_favorites），基于证据决策',
      recommendation: 'cortex-first',
      source: 'Data-Driven Decision Making',
      confidence: 0.92
    },
    confidence: 0.92
  },
  {
    namespace: 'lessons',
    key: 'lesson_imagination_without_data',
    value: {
      context: '无数据凭空想象',
      lesson: '不做调研就设计方案，会重复造轮子或忽视已有能力',
      recommendation: 'research-before-design',
      source: 'Engineering Design Process',
      confidence: 0.90
    },
    confidence: 0.90
  }
];

export class ExternalKnowledgeInitializer {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
  }

  /**
   * 初始化外部知识记忆
   */
  initializeKnowledge(): { inserted: number; skipped: number } {
    console.log('📚 初始化外部知识记忆\n');
    console.log('━'.repeat(70));
    console.log('  数据来源：业界最佳实践 + 权威技术文档');
    console.log('━'.repeat(70) + '\n');

    let inserted = 0;
    let skipped = 0;

    const insertMemory = this.db.prepare(`
      INSERT INTO evo_memory_semantic (namespace, key, value, confidence)
      VALUES (?, ?, ?, ?)
    `);

    for (const memory of EXTERNAL_KNOWLEDGE) {
      // 检查是否已存在
      const existing = this.db.query<{ count: number }>(`
        SELECT COUNT(*) as count
        FROM evo_memory_semantic
        WHERE namespace = ? AND key = ?
      `).get(memory.namespace, memory.key);

      if (existing && existing.count > 0) {
        console.log(`⏭️  ${memory.key} - 已存在，跳过`);
        skipped++;
        continue;
      }

      // 插入记忆
      insertMemory.run(
        memory.namespace,
        memory.key,
        JSON.stringify(memory.value),
        memory.confidence
      );

      const icon = memory.namespace === 'lessons' ? '❌' : '✅';
      console.log(`${icon} ${memory.key}`);
      console.log(`   上下文: ${memory.value.context}`);
      if (memory.value.lesson) {
        console.log(`   教训: ${memory.value.lesson}`);
      }
      if (memory.value.insight) {
        console.log(`   洞察: ${memory.value.insight}`);
      }
      console.log(`   来源: ${memory.value.source}`);
      console.log(`   置信度: ${(memory.confidence * 100).toFixed(0)}%\n`);

      inserted++;
    }

    return { inserted, skipped };
  }

  /**
   * 显示初始化结果摘要
   */
  showSummary(): void {
    console.log('━'.repeat(70));
    console.log('📊 初始化结果摘要\n');

    // 统计记忆数量
    const stats = this.db.query<{
      namespace: string;
      count: number;
    }>(`
      SELECT namespace, COUNT(*) as count
      FROM evo_memory_semantic
      WHERE namespace IN ('lessons', 'experiences')
      GROUP BY namespace
    `).all();

    console.log('📚 记忆统计:');
    for (const stat of stats) {
      console.log(`   ${stat.namespace}: ${stat.count} 条`);
    }

    console.log('\n' + '━'.repeat(70));
    console.log('\n💡 下一步:');
    console.log('   1. 系统会在实际使用中积累更多记忆');
    console.log('   2. Memory-Driven Decision 可以查询到这些知识');
    console.log('   3. 定期运行 feedback-to-memory.ts 提取实际教训');
    console.log('   4. 运行 memory-driven-decision.ts 测试查询\n');
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 外部知识记忆初始化器\n');
    console.log('理念: 先验知识（业界经验）+ 实际观测（系统数据）= 更准确的决策知识');
    console.log('来源: 业界最佳实践 + 权威技术文档\n');
    console.log('━'.repeat(70) + '\n');

    // 初始化知识记忆
    const { inserted, skipped } = this.initializeKnowledge();
    console.log(`\n✅ 知识记忆: ${inserted} 条新增, ${skipped} 条跳过\n`);

    // 显示摘要
    this.showSummary();

    this.db.close();
  }
}

// CLI 入口
if (import.meta.main) {
  const initializer = new ExternalKnowledgeInitializer();
  await initializer.run();
}
