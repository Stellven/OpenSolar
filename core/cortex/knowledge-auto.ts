#!/usr/bin/env bun
/**
 * Knowledge Auto - 自动知识注入
 *
 * 用于 Hook 调用：
 *   bun knowledge-auto.ts "用户的输入内容"
 *
 * 返回：相关知识库内容（如果有匹配）
 *
 * @version 1.0.0
 */

import { Database } from 'bun:sqlite';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const db = new Database(DB_PATH);

// 关键词触发词（这些词出现时自动查知识库）
const TRIGGER_KEYWORDS = [
  // AI/模型相关
  'AGI', 'ASI', 'LLM', 'GPT', 'Claude', 'Gemini', 'DeepSeek', 'GLM',
  '推理', 'inference', '训练', 'training', '微调', 'fine-tun',
  'MoE', 'Transformer', 'Attention', 'KV Cache',
  '智能体', 'agent', 'Agent',

  // 硬件/算力
  'GPU', 'TPU', 'CPU', 'HBM', '内存', 'memory', '带宽', 'bandwidth',
  'FLOPs', '算力', '计算',

  // 人物
  'Jeff Dean', 'Geoffrey Hinton', 'Hinton', 'Oriol Vinyals',

  // 公司
  'Google', 'DeepMind', 'OpenAI', 'Anthropic',

  // 概念
  '帕累托', 'Pareto', '演化', 'evolution', '对齐', 'alignment',
  '异构', 'heterogeneous', '解耦', 'disaggregat',
];

// 用户输入
const userInput = process.argv[2] || '';

if (!userInput) {
  console.log('');
  process.exit(0);
}

// 检测是否触发
const triggers = TRIGGER_KEYWORDS.filter(kw =>
  userInput.toLowerCase().includes(kw.toLowerCase())
);

if (triggers.length === 0) {
  console.log('');
  process.exit(0);
}

// 查询知识库
const results: string[] = [];

for (const keyword of triggers.slice(0, 3)) { // 最多查3个关键词
  // 查实体
  const entities = db.query<{
    name: string;
    type: string;
    description: string;
  }, [string]>(`
    SELECT name, type, description
    FROM knowledge_entities
    WHERE name LIKE ? OR description LIKE ?
    ORDER BY importance DESC
    LIMIT 3
  `).all(`%${keyword}%`, `%${keyword}%`);

  for (const e of entities) {
    results.push(`[${e.type}] ${e.name}${e.description ? ': ' + e.description.substring(0, 60) : ''}`);
  }

  // 查结论
  const claims = db.query<{
    claim_text: string;
    confidence: number;
  }, [string]>(`
    SELECT claim_text, confidence
    FROM knowledge_claims
    WHERE claim_text LIKE ?
    ORDER BY confidence DESC
    LIMIT 2
  `).all(`%${keyword}%`);

  for (const c of claims) {
    results.push(`💡 [${(c.confidence * 100).toFixed(0)}%] ${c.claim_text.substring(0, 80)}`);
  }
}

db.close();

// 输出结果
if (results.length > 0) {
  const unique = [...new Set(results)].slice(0, 5); // 去重，最多5条

  console.log(`
┌─────────────────────────────────────────────────────────────────┐
│  📚 知识库相关内容 (触发: ${triggers.slice(0, 3).join(', ')})
├─────────────────────────────────────────────────────────────────┤
${unique.map(r => `│  ${r.substring(0, 60)}`).join('\n')}
└─────────────────────────────────────────────────────────────────┘
`);
} else {
  console.log('');
}
