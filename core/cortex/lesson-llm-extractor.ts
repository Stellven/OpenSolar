#!/usr/bin/env bun
/**
 * LLM 教训提取器 - 使用老专家从失败案例中提取结构化教训
 *
 * 功能：
 * 1. 读取 evo_memory_semantic 中"系统自动标记"的教训
 * 2. 调用老专家（deepseek-r1/gemini-2.5-pro）提取结构化知识
 * 3. 更新记忆内容为结构化格式
 *
 * 创建时间: 2026-02-20
 */

import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

console.log('🧠 LLM 教训提取器启动\n');

// 1. 统计待提取教训
const pending = db.query(`
  SELECT COUNT(*) as count
  FROM evo_memory_semantic
  WHERE namespace = 'lessons'
    AND value LIKE '%系统自动标记：已识别为失败案例%'
`).get() as any;

console.log(`📋 待提取教训: ${pending.count} 条\n`);

if (pending.count === 0) {
  console.log('✅ 没有待提取的教训');
  db.close();
  process.exit(0);
}

// 2. 读取教训（批量处理，每批10条）
const batchSize = 10;
const lessons = db.query(`
  SELECT key, value
  FROM evo_memory_semantic
  WHERE namespace = 'lessons'
    AND value LIKE '%系统自动标记：已识别为失败案例%'
    AND value NOT LIKE '%llm_extracted%'
  ORDER BY created_at DESC
  LIMIT ?
`).all(batchSize) as any[];

console.log(`📝 本次处理: ${lessons.length} 条\n`);

// 3. 提取结构化教训的接口
interface ExtractedLesson {
  core_lesson: string;              // 核心教训（一句话）
  applicable_scenarios: string[];   // 适用场景
  avoidance_methods: string[];      // 避免方法
  severity: 'critical' | 'warning' | 'info';  // 严重程度
  tags: string[];                   // 标签
}

// 4. 调用老专家提取结构化教训
async function extractWithLLM(context: string): Promise<ExtractedLesson> {
  // 调用审判官（deepseek-r1）提取结构化教训
  // 审判官擅长深度推理、质疑假设，适合从失败中提取教训

  const prompt = `请从以下失败案例中提取结构化教训：

## 失败上下文
${context}

## 提取要求
请输出 JSON 格式，包含以下字段：
1. core_lesson: 核心教训（一句话，20-40字）
2. applicable_scenarios: 适用场景（2-3个场景）
3. avoidance_methods: 避免方法（2-3个具体方法）
4. severity: 严重程度（"critical" | "warning" | "info"）
   - critical: 导致任务失败、系统崩溃、数据丢失
   - warning: 影响质量、性能、用户体验
   - info: 改进建议、最佳实践
5. tags: 标签（2-4个，如 "file-ops", "tool-use", "data-access", "reasoning"）

## 输出格式
只输出 JSON，不要其他内容。示例：
{
  "core_lesson": "不要假设文件存在，执行前必须先验证",
  "applicable_scenarios": ["文件操作前", "读取配置时", "加载数据文件时"],
  "avoidance_methods": ["使用 Read 工具先检查文件", "添加错误处理逻辑", "使用 try-catch"],
  "severity": "critical",
  "tags": ["file-ops", "error-handling"]
}`;

  try {
    // 调用 brain-router MCP（审判官 deepseek-r1）
    const response = await fetch('http://localhost:15721/v1/complete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.ANTHROPIC_AUTH_TOKEN || 'local'}`
      },
      body: JSON.stringify({
        model: 'deepseek-r1',
        system: `你是审判官（deepseek-r1），D&D 角色是 judge（审判官）。

KNOBS (10 个可调节旋钮):
• rigor=5 (极高严谨，证据门槛高)
• skepticism=5 (质疑一切假设)
• exploration=1 (保守审慎，不冒进)
• decisiveness=2 (谨慎决策，宁可慢)
• riskAversion=5 (极度规避风险)
• toolFirst=3 (适度使用工具)
• compression=4 (简洁精准)
• selfCritique=5 (极强自检)
• socialEmpathy=2 (冷静克制，不讨好)
• competitiveness=1 (不竞争，只陈述事实)

LEVEL=3 (资深审判官)

你的职责：
1. 从失败案例中提取结构化教训
2. 证据优先：任何结论必须有上下文支撑
3. 反例优先：先找推翻假设的证据
4. 不确定时明确说"不确定"
5. 输出必须是合法的 JSON，不要有额外文字`,
        prompt,
        temperature: 0.3  // 降低温度，提高一致性
      })
    });

    if (!response.ok) {
      throw new Error(`Brain Router 调用失败: ${response.status}`);
    }

    const data = await response.json();
    const content = data.content || data.completion || '';

    // 提取 JSON
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('未找到 JSON 输出');
    }

    const extracted = JSON.parse(jsonMatch[0]) as ExtractedLesson;

    // 验证字段
    if (!extracted.core_lesson || !extracted.applicable_scenarios || !extracted.avoidance_methods) {
      throw new Error('缺少必需字段');
    }

    return extracted;

  } catch (error: any) {
    console.error(`   ⚠️  LLM 提取失败: ${error.message}`);

    // 失败时回退到规则提取
    const contextLower = context.toLowerCase();
    let severity: 'critical' | 'warning' | 'info' = 'warning';
    if (contextLower.includes('error') || contextLower.includes('fail') || contextLower.includes('exception')) {
      severity = 'critical';
    }

    const tags: string[] = [];
    if (contextLower.includes('read') || contextLower.includes('file')) tags.push('file-ops');
    if (contextLower.includes('tool') || contextLower.includes('bash')) tags.push('tool-use');
    if (tags.length === 0) tags.push('general');

    return {
      core_lesson: '提取失败，需人工复核',
      applicable_scenarios: ['类似上下文的任务执行'],
      avoidance_methods: ['参考相关规则文件', '执行前先查数据'],
      severity,
      tags
    };
  }
}

// 5. 批量处理
const updateStmt = db.prepare(`
  UPDATE evo_memory_semantic
  SET value = ?
  WHERE key = ?
`);

db.run('BEGIN TRANSACTION');

try {
  let processed = 0;
  let errors = 0;

  for (const lesson of lessons) {
    try {
      const value = JSON.parse(lesson.value);

      // 提取上下文
      const context = value.context || '';

      // 调用 LLM 提取
      console.log(`   处理: ${lesson.key.substring(0, 30)}...`);
      const extracted = await extractWithLLM(context);

      // 更新为结构化格式
      const newValue = {
        ...value,
        extracted_lesson: extracted,
        extraction_status: 'llm_extracted',
        extraction_timestamp: new Date().toISOString()
      };

      updateStmt.run(JSON.stringify(newValue), lesson.key);
      processed++;

    } catch (error: any) {
      console.error(`   ⚠️  失败 [${lesson.key}]: ${error.message}`);
      errors++;
    }
  }

  db.run('COMMIT');

  console.log(`\n✅ 处理完成:`);
  console.log(`   成功: ${processed}`);
  console.log(`   失败: ${errors}`);

} catch (error) {
  db.run('ROLLBACK');
  console.error('❌ 批量处理失败:', error);
  throw error;
}

// 6. 显示剩余统计
const remaining = db.query(`
  SELECT COUNT(*) as count
  FROM evo_memory_semantic
  WHERE namespace = 'lessons'
    AND value LIKE '%系统自动标记：已识别为失败案例%'
`).get() as any;

console.log(`\n📊 剩余待提取: ${remaining.count} 条`);

if (remaining.count > 0) {
  console.log('\n💡 建议: 运行多次以提取所有教训');
}

db.close();

console.log('\n🎉 LLM 教训提取完成!');
