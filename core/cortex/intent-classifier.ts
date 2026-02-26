#!/usr/bin/env bun
/**
 * 简化意图分类器 - 基于关键词的快速分类
 *
 * 功能：
 * 1. 从用户查询中提取意图
 * 2. 基于关键词规则分类
 * 3. 返回结构化意图对象
 *
 * 创建时间: 2026-02-20
 */

interface IntentResult {
  primary: string;
  secondary: string[];
  confidence: number;
  keywords: string[];
}

// 意图分类规则
const INTENT_RULES = [
  {
    intent: 'coding',
    keywords: ['实现', '编写', '开发', '代码', '函数', '类', '模块', '编码', 'debug', '修复'],
    weight: 1.0
  },
  {
    intent: 'analysis',
    keywords: ['分析', '评估', '审查', '检查', '诊断', '研究', '调研', '洞察'],
    weight: 0.9
  },
  {
    intent: 'creative',
    keywords: ['设计', '创意', '构想', '发明', '创新', '头脑风暴'],
    weight: 0.9
  },
  {
    intent: 'reasoning',
    keywords: ['推理', '逻辑', '证明', '推导', '演绎', '归纳'],
    weight: 0.95
  },
  {
    intent: 'explanation',
    keywords: ['解释', '说明', '教学', '讲解', '教会', '理解'],
    weight: 0.85
  },
  {
    intent: 'test',
    keywords: ['测试', '验证', '检验', 'test', 'benchmark', '性能'],
    weight: 0.85
  },
  {
    intent: 'docs',
    keywords: ['文档', 'readme', '注释', '说明', '文档化'],
    weight: 0.8
  },
  {
    intent: 'quick',
    keywords: ['快速', '简单', '查', '看', '列出', '显示'],
    weight: 0.75
  },
  {
    intent: 'general',
    keywords: ['帮我', '请', '能否', '可以'],
    weight: 0.5
  }
];

export function classifyIntent(query: string): IntentResult {
  const lowerQuery = query.toLowerCase();

  // 计算每个意图的匹配分数
  const scores: { intent: string; score: number; keywords: string[] }[] = [];

  for (const rule of INTENT_RULES) {
    const matchedKeywords = rule.keywords.filter(kw => lowerQuery.includes(kw));
    if (matchedKeywords.length > 0) {
      const score = matchedKeywords.length * rule.weight;
      scores.push({
        intent: rule.intent,
        score,
        keywords: matchedKeywords
      });
    }
  }

  // 排序并选择最佳匹配
  scores.sort((a, b) => b.score - a.score);

  if (scores.length === 0) {
    return {
      primary: 'general',
      secondary: [],
      confidence: 0.5,
      keywords: []
    };
  }

  const primary = scores[0];
  const secondary = scores.slice(1, 3).map(s => s.intent);

  // 置信度归一化
  const confidence = Math.min(primary.score / 3, 1.0);

  return {
    primary: primary.intent,
    secondary,
    confidence,
    keywords: primary.keywords
  };
}

// CLI 测试
if (import.meta.main) {
  const testQueries = [
    '实现一个快速排序算法',
    '分析这段代码的性能问题',
    '设计一个创意的用户界面',
    '解释什么是闭包',
    '测试这个函数的正确性'
  ];

  console.log('🧪 意图分类器测试:\n');

  for (const query of testQueries) {
    const result = classifyIntent(query);
    console.log(`查询: "${query}"`);
    console.log(`  主要意图: ${result.primary} (${(result.confidence * 100).toFixed(0)}%)`);
    console.log(`  关键词: ${result.keywords.join(', ')}`);
    console.log('');
  }
}
