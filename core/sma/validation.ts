#!/usr/bin/env bun
/**
 * SMA v1.0 Phase 3 价值验证脚本
 *
 * 功能:
 * 1. 从 JSONL 提取真实会话
 * 2. 测试 L2→L3 知识提取质量
 * 3. 计算准确率/召回率
 * 4. 对比有/无 L2 的记忆召回差异
 */

import { Database } from 'bun:sqlite';
import { logTurn, retrieveContext, triggerConsolidation } from './memory-controller';
import fs from 'fs';
import path from 'path';

// 类型定义
interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

interface Triple {
  subject: string;
  predicate: string;
  object: string;
}

interface AnnotationData {
  turnId: number;
  userInput: string;
  aiOutput: string;
  expectedTriples: Triple[];  // 人工标注的"黄金标准"
  extractedTriples: Triple[];  // L2→L3 自动提取的
}

interface ValidationMetrics {
  precision: number;   // 准确率: 提取的三元组中正确的比例
  recall: number;      // 召回率: 应该提取的三元组中成功提取的比例
  f1Score: number;     // F1 分数: precision 和 recall 的调和平均
  totalExpected: number;
  totalExtracted: number;
  correctExtracted: number;
}

/**
 * 从 JSONL 文件提取会话
 */
async function extractConversations(jsonlPath: string, limit: number = 20): Promise<ConversationTurn[]> {
  const content = await Bun.file(jsonlPath).text();
  const lines = content.trim().split('\n').slice(0, limit);

  const conversations: ConversationTurn[] = [];

  for (const line of lines) {
    try {
      const record = JSON.parse(line);
      if (record.role && record.content) {
        conversations.push({
          role: record.role,
          content: typeof record.content === 'string'
            ? record.content
            : JSON.stringify(record.content),
          timestamp: record.timestamp
        });
      }
    } catch (e) {
      console.warn('Failed to parse line:', e);
    }
  }

  return conversations;
}

/**
 * 将会话写入 L2
 */
async function writeToL2(conversations: ConversationTurn[], sessionId: string): Promise<void> {
  let turnId = 1;
  let userInput = '';

  for (const conv of conversations) {
    if (conv.role === 'user') {
      userInput = conv.content;
    } else if (conv.role === 'assistant' && userInput) {
      await logTurn({
        sessionId,
        turnId: turnId++,
        userInput,
        aiOutput: conv.content,
        metadata: { validation: true }
      });
      userInput = '';
    }
  }
}

/**
 * 三元组相似度比较 (简单字符串匹配)
 */
function tripleEquals(a: Triple, b: Triple): boolean {
  return a.subject === b.subject &&
         a.predicate === b.predicate &&
         a.object === b.object;
}

/**
 * 计算验证指标
 */
function calculateMetrics(annotationData: AnnotationData[]): ValidationMetrics {
  let totalExpected = 0;
  let totalExtracted = 0;
  let correctExtracted = 0;

  for (const data of annotationData) {
    totalExpected += data.expectedTriples.length;
    totalExtracted += data.extractedTriples.length;

    // 计算正确提取的三元组数量
    for (const extracted of data.extractedTriples) {
      if (data.expectedTriples.some(expected => tripleEquals(expected, extracted))) {
        correctExtracted++;
      }
    }
  }

  const precision = totalExtracted > 0 ? correctExtracted / totalExtracted : 0;
  const recall = totalExpected > 0 ? correctExtracted / totalExpected : 0;
  const f1Score = (precision + recall) > 0
    ? 2 * (precision * recall) / (precision + recall)
    : 0;

  return {
    precision,
    recall,
    f1Score,
    totalExpected,
    totalExtracted,
    correctExtracted
  };
}

/**
 * 生成人工标注模板
 */
async function generateAnnotationTemplate(
  conversations: ConversationTurn[],
  outputPath: string
): Promise<void> {
  const template = {
    instructions: "请为每个对话轮次标注应该提取的知识三元组（subject, predicate, object）",
    format: {
      subject: "主语（实体）",
      predicate: "谓语（关系）",
      object: "宾语（实体/属性）"
    },
    example: {
      userInput: "SMA 是什么？",
      aiOutput: "SMA 是 Solar Memory Architecture，三层记忆系统。",
      expectedTriples: [
        { subject: "SMA", predicate: "是", object: "Solar Memory Architecture" },
        { subject: "SMA", predicate: "是", object: "三层记忆系统" }
      ]
    },
    annotations: [] as any[]
  };

  let turnId = 1;
  let userInput = '';

  for (const conv of conversations) {
    if (conv.role === 'user') {
      userInput = conv.content;
    } else if (conv.role === 'assistant' && userInput) {
      template.annotations.push({
        turnId: turnId++,
        userInput,
        aiOutput: conv.content,
        expectedTriples: []  // 待人工填写
      });
      userInput = '';
    }
  }

  await Bun.write(outputPath, JSON.stringify(template, null, 2));
  console.log(`✅ 标注模板已生成: ${outputPath}`);
  console.log(`📝 请编辑此文件，为每个对话轮次添加 expectedTriples`);
}

/**
 * 执行验证
 */
async function runValidation(annotationPath: string): Promise<void> {
  console.log('🧪 SMA v1.0 Phase 3 价值验证\n');

  // 读取标注数据
  const annotationFile = await Bun.file(annotationPath).json();
  const annotations: AnnotationData[] = annotationFile.annotations;

  if (annotations.length === 0) {
    console.error('❌ 标注数据为空');
    return;
  }

  // 检查是否有人工标注
  const hasAnnotations = annotations.some(a => a.expectedTriples && a.expectedTriples.length > 0);
  if (!hasAnnotations) {
    console.warn('⚠️  尚未完成人工标注，将只测试提取功能');
  }

  const sessionId = `validation_${Date.now()}`;

  // 1. 写入 L2
  console.log('📝 写入 L2 Episodic Buffer...');
  for (const ann of annotations) {
    await logTurn({
      sessionId,
      turnId: ann.turnId,
      userInput: ann.userInput,
      aiOutput: ann.aiOutput,
      metadata: { validation: true }
    });
  }
  console.log(`   ✅ 写入 ${annotations.length} 条记录\n`);

  // 2. 触发 L2→L3 知识固化
  console.log('⚡ 触发 L2→L3 知识固化...');
  const start = performance.now();
  const extractedCount = await triggerConsolidation(sessionId, { minTurns: 1 });
  const duration = performance.now() - start;
  console.log(`   ✅ 提取了 ${extractedCount} 个三元组 (${duration.toFixed(2)}ms)\n`);

  // 3. 获取提取的三元组
  console.log('🔍 检索提取的三元组...');
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);
  const triples = db.prepare(`
    SELECT subject, predicate, object
    FROM knowledge_triples
    WHERE created_at >= ?
    ORDER BY triple_id
  `).all(Math.floor(Date.now() / 1000) - 60) as Triple[];

  console.log(`   📊 提取到 ${triples.length} 个三元组:`);
  triples.forEach((t, i) => {
    console.log(`   ${i + 1}. (${t.subject}, ${t.predicate}, ${t.object})`);
  });
  console.log('');

  // 4. 如果有人工标注，计算指标
  if (hasAnnotations) {
    console.log('📈 计算验证指标...');

    // 将提取的三元组分配回对应的 annotation
    // (简化版本：假设顺序一致)
    for (const ann of annotations) {
      ann.extractedTriples = triples;  // 实际应该更精确地匹配
    }

    const metrics = calculateMetrics(annotations);

    console.log('   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('   🎯 L2→L3 提取质量指标');
    console.log('   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`   准确率 (Precision): ${(metrics.precision * 100).toFixed(2)}%`);
    console.log(`   召回率 (Recall):    ${(metrics.recall * 100).toFixed(2)}%`);
    console.log(`   F1 分数:            ${(metrics.f1Score * 100).toFixed(2)}%`);
    console.log('   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`   期望提取: ${metrics.totalExpected}`);
    console.log(`   实际提取: ${metrics.totalExtracted}`);
    console.log(`   正确提取: ${metrics.correctExtracted}`);
    console.log('   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

    // 5. Go/No-Go 决策建议
    console.log('🚦 Go/No-Go 决策建议:');
    if (metrics.f1Score >= 0.7) {
      console.log('   ✅ GO - F1 分数 >= 0.7，价值充分');
      console.log('   建议: 继续 Phase 4 (清理策略)');
    } else if (metrics.f1Score >= 0.5) {
      console.log('   ⚠️  MAYBE - F1 分数 0.5~0.7，价值中等');
      console.log('   建议: 改进提取规则或调整评估标准');
    } else {
      console.log('   ❌ NO-GO - F1 分数 < 0.5，价值不足');
      console.log('   建议: 止步于 Phase 3，或重新设计提取算法');
    }
  }

  // 清理测试数据
  console.log('\n🧹 清理测试数据...');
  db.run('DELETE FROM session_log WHERE session_id = ?', [sessionId]);
  db.run('DELETE FROM knowledge_triples WHERE created_at >= ?',
    [Math.floor(Date.now() / 1000) - 60]);
  console.log('   ✅ 清理完成');
}

// 主流程
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'generate-template') {
    // 生成标注模板
    const jsonlPath = args[1] || '/tmp/sample_conversations.jsonl';
    const outputPath = args[2] || '/Users/sihaoli/.claude/core/sma/annotation_template.json';

    const conversations = await extractConversations(jsonlPath, 20);
    await generateAnnotationTemplate(conversations, outputPath);

  } else if (command === 'validate') {
    // 执行验证
    const annotationPath = args[1] || '/Users/sihaoli/.claude/core/sma/annotation_template.json';
    await runValidation(annotationPath);

  } else {
    console.log('SMA v1.0 Phase 3 价值验证工具');
    console.log('');
    console.log('用法:');
    console.log('  bun validation.ts generate-template [jsonl路径] [输出路径]');
    console.log('    - 从 JSONL 提取会话并生成标注模板');
    console.log('');
    console.log('  bun validation.ts validate [标注文件路径]');
    console.log('    - 执行验证并计算 L2→L3 提取质量指标');
    console.log('');
    console.log('示例:');
    console.log('  bun validation.ts generate-template /tmp/sample_conversations.jsonl');
    console.log('  bun validation.ts validate annotation_template.json');
  }
}

main().catch(console.error);
