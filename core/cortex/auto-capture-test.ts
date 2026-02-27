#!/usr/bin/env bun
/**
 * Auto-Capture System End-to-End Test
 *
 * 测试完整流程:
 * 1. 捕获搜索结果/专家输出/开发产物
 * 2. 批量抽取知识
 * 3. 验证知识图谱更新
 */

import Database from 'bun:sqlite';
import {
  captureSearch,
  captureExpertOutput,
  captureArtifact
} from './auto-capture';
import {
  detectCodeArtifact,
  detectDesignArtifact,
  detectAnalysisArtifact,
  detectDecisionArtifact
} from './auto-capture-detector';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
  captureId?: string;
}

const results: TestResult[] = [];

/**
 * Test 1: 捕获搜索结果
 */
async function testSearchCapture(): Promise<TestResult> {
  try {
    const captureId = await captureSearch({
      search_type: 'grep',
      query: 'function handleError',
      context: '测试搜索捕获',
      results: {
        files: ['test1.ts', 'test2.ts'],
        matches: ['line 10: function handleError()', 'line 25: function handleError()']
      },
      result_count: 2,
      tool_params: { pattern: 'handleError', glob: '*.ts' }
    });

    // 验证数据库记录
    const db = new Database(DB_PATH);
    const record = db.query(`SELECT * FROM sys_search_cache WHERE search_id = ?`).get(captureId);
    db.close();

    if (!record) {
      return { name: 'Search Capture', passed: false, error: '数据库未找到记录' };
    }

    return { name: 'Search Capture', passed: true, captureId };
  } catch (error: any) {
    return { name: 'Search Capture', passed: false, error: error.message };
  }
}

/**
 * Test 2: 捕获专家输出
 */
async function testExpertCapture(): Promise<TestResult> {
  try {
    const captureId = await captureExpertOutput({
      model: 'gemini-2.5-flash',
      expert_role: '测试专家',
      system_prompt: 'You are a test expert',
      user_prompt: '分析这段代码的性能问题',
      output: '代码存在以下性能问题:\n1. 未缓存重复计算\n2. 嵌套循环过深\n3. 内存分配过于频繁',
      task_type: 'analysis',
      context: '性能分析测试',
      tokens_input: 150,
      tokens_output: 80,
      latency_ms: 1200
    });

    const db = new Database(DB_PATH);
    const record = db.query(`SELECT * FROM sys_expert_outputs WHERE output_id = ?`).get(captureId);
    db.close();

    if (!record) {
      return { name: 'Expert Output Capture', passed: false, error: '数据库未找到记录' };
    }

    return { name: 'Expert Output Capture', passed: true, captureId };
  } catch (error: any) {
    return { name: 'Expert Output Capture', passed: false, error: error.message };
  }
}

/**
 * Test 3: 捕获开发产物
 */
async function testArtifactCapture(): Promise<TestResult> {
  try {
    const captureId = await captureArtifact({
      artifact_type: 'design',
      title: '测试架构设计',
      content: `
# 系统架构设计

┌─────────────────┐      ┌─────────────────┐
│   Frontend      │ ───→ │   API Gateway   │
└─────────────────┘      └─────────────────┘
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                  ┌─────────────┐   ┌─────────────┐
                  │  Service A  │   │  Service B  │
                  └─────────────┘   └─────────────┘
`,
      tags: ['architecture', 'design', 'test'],
      context: '测试架构设计捕获',
      importance: 8
    });

    const db = new Database(DB_PATH);
    const record = db.query(`SELECT * FROM sys_dev_artifacts WHERE artifact_id = ?`).get(captureId);
    db.close();

    if (!record) {
      return { name: 'Artifact Capture', passed: false, error: '数据库未找到记录' };
    }

    return { name: 'Artifact Capture', passed: true, captureId };
  } catch (error: any) {
    return { name: 'Artifact Capture', passed: false, error: error.message };
  }
}

/**
 * Test 4: 内容检测器 - 设计产物
 */
async function testDesignDetector(): Promise<TestResult> {
  try {
    const designContent = `
# API 接口设计

## 数据流向

┌──────────┐      ┌──────────┐      ┌──────────┐
│  Client  │ ───→ │  Server  │ ───→ │    DB    │
└──────────┘      └──────────┘      └──────────┘

## 接口定义

POST /api/users
GET /api/users/:id
`;

    const captureId = await detectDesignArtifact(
      designContent,
      '测试设计检测',
      '设计检测器测试'
    );

    if (!captureId) {
      return { name: 'Design Detector', passed: false, error: '未检测到设计产物' };
    }

    return { name: 'Design Detector', passed: true, captureId };
  } catch (error: any) {
    return { name: 'Design Detector', passed: false, error: error.message };
  }
}

/**
 * Test 5: 内容检测器 - 分析产物
 */
async function testAnalysisDetector(): Promise<TestResult> {
  try {
    const analysisContent = `
# 性能分析报告

## 测试结果

| 指标 | 基准值 | 优化后 | 提升 |
|------|--------|--------|------|
| QPS  | 1000   | 3500   | 250% |
| P50  | 15ms   | 5ms    | 67%  |
| P99  | 150ms  | 35ms   | 77%  |

## 结论

通过缓存优化和并发改进，性能提升显著。
`;

    const captureId = await detectAnalysisArtifact(
      analysisContent,
      '测试分析检测',
      '分析检测器测试'
    );

    if (!captureId) {
      return { name: 'Analysis Detector', passed: false, error: '未检测到分析产物' };
    }

    return { name: 'Analysis Detector', passed: true, captureId };
  } catch (error: any) {
    return { name: 'Analysis Detector', passed: false, error: error.message };
  }
}

/**
 * Test 6: 内容检测器 - 决策产物
 */
async function testDecisionDetector(): Promise<TestResult> {
  try {
    const decisionContent = `
# 技术选型决策

## 决定

采用 PostgreSQL 作为主数据库，而不是 MongoDB

## 原因

1. 数据结构相对固定
2. 需要强事务支持
3. 团队更熟悉 SQL

## 风险

迁移成本较高，需要数据迁移工具
`;

    const captureId = await detectDecisionArtifact(
      decisionContent,
      '测试决策检测',
      '决策检测器测试'
    );

    if (!captureId) {
      return { name: 'Decision Detector', passed: false, error: '未检测到决策产物' };
    }

    return { name: 'Decision Detector', passed: true, captureId };
  } catch (error: any) {
    return { name: 'Decision Detector', passed: false, error: error.message };
  }
}

/**
 * Test 7: 查看待提取条目
 */
async function testPendingView(): Promise<TestResult> {
  try {
    const db = new Database(DB_PATH);
    const pending = db.query(`
      SELECT source_type, COUNT(*) as count
      FROM v_pending_extraction
      GROUP BY source_type
    `).all();
    db.close();

    if (pending.length === 0) {
      return { name: 'Pending View', passed: false, error: '未找到待提取条目' };
    }

    console.log('\n📋 待提取条目统计:');
    pending.forEach((row: any) => {
      console.log(`   ${row.source_type}: ${row.count} 条`);
    });

    return { name: 'Pending View', passed: true };
  } catch (error: any) {
    return { name: 'Pending View', passed: false, error: error.message };
  }
}

/**
 * Test 8: 统计视图
 */
async function testStatsView(): Promise<TestResult> {
  try {
    const db = new Database(DB_PATH);
    const stats = db.query(`SELECT * FROM v_capture_stats`).all();
    db.close();

    console.log('\n📊 捕获统计:');
    stats.forEach((row: any) => {
      console.log(`   ${row.category}:`);
      console.log(`      总数: ${row.total} | 已同步: ${row.synced} | 待处理: ${row.pending}`);
    });

    return { name: 'Stats View', passed: true };
  } catch (error: any) {
    return { name: 'Stats View', passed: false, error: error.message };
  }
}

/**
 * 执行所有测试
 */
async function runAllTests() {
  console.log('🧪 自动捕获系统 端到端测试\n');
  console.log('═'.repeat(70));

  const tests = [
    testSearchCapture,
    testExpertCapture,
    testArtifactCapture,
    testDesignDetector,
    testAnalysisDetector,
    testDecisionDetector,
    testPendingView,
    testStatsView
  ];

  for (const test of tests) {
    const result = await test();
    results.push(result);

    const icon = result.passed ? '✅' : '❌';
    console.log(`${icon} ${result.name}`);
    if (result.captureId) {
      console.log(`   ID: ${result.captureId}`);
    }
    if (result.error) {
      console.log(`   错误: ${result.error}`);
    }
  }

  console.log('\n' + '═'.repeat(70));

  const passed = results.filter(r => r.passed).length;
  const total = results.length;
  const passRate = ((passed / total) * 100).toFixed(1);

  console.log(`\n📈 测试结果: ${passed}/${total} 通过 (${passRate}%)`);

  if (passed === total) {
    console.log('\n🎉 所有测试通过！自动捕获系统工作正常。\n');
    console.log('💡 下一步:');
    console.log('   1. 运行批量知识抽取:');
    console.log('      bun ~/.claude/core/cortex/auto-capture-batch-extract.ts --limit 10 --dry-run');
    console.log('   2. 检查抽取结果:');
    console.log('      bun ~/.claude/core/cortex/auto-capture.ts stats');
  } else {
    console.log('\n⚠️ 部分测试失败，请检查错误信息。');
  }
}

// 执行测试
if (import.meta.main) {
  runAllTests().catch(console.error);
}
