/**
 * 小爱洞察协调器
 * 调度老专家干分析活，收集结果供 CEO 考评
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const db = new Database(`${homedir()}/.solar/solar.db`);

// 老专家配置
const EXPERTS = {
  'gemini-2.5-pro': {
    nickname: '技术宅',
    role: 'author',
    system: `你是"技术宅"，性格：严谨务实，追求一致性。
分析问题时要：
1. 结构化清晰
2. 引用具体证据
3. 给出明确结论`
  },
  'deepseek-r1': {
    nickname: '思考驼',
    role: 'reviewer',
    system: `你是"思考驼"，擅长深度推理。
审核分析时要：
1. 检查逻辑漏洞
2. 补充遗漏视角
3. 提出改进建议`
  },
  'deepseek-v3': {
    nickname: '鬼才码农',
    role: 'challenger',
    system: `你是"鬼才码农"，擅长创意思考。
挑战分析时要：
1. 提出反面观点
2. 发现隐藏风险
3. 建议创新方案`
  }
};

// API 配置
const API_CONFIGS: Record<string, { url: string; keyEnv: string; model: string }> = {
  'gemini-2.5-pro': {
    url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-05-06:generateContent',
    keyEnv: 'GOOGLE_API_KEY',
    model: 'gemini-2.5-pro'
  },
  'deepseek-r1': {
    url: 'https://api.deepseek.com/v1/chat/completions',
    keyEnv: 'DEEPSEEK_API_KEY',
    model: 'deepseek-reasoner'
  },
  'deepseek-v3': {
    url: 'https://api.deepseek.com/v1/chat/completions',
    keyEnv: 'DEEPSEEK_API_KEY',
    model: 'deepseek-chat'
  }
};

// 调用老专家
async function callExpert(expertId: string, prompt: string): Promise<{ content: string; tokens: number; latency: number }> {
  const config = API_CONFIGS[expertId];
  const expert = EXPERTS[expertId as keyof typeof EXPERTS];
  const apiKey = process.env[config.keyEnv];

  if (!apiKey) {
    throw new Error(`Missing API key: ${config.keyEnv}`);
  }

  const startTime = Date.now();

  try {
    let response;
    let content: string;
    let tokens = 0;

    if (expertId.startsWith('gemini')) {
      // Google Gemini API
      response = await fetch(`${config.url}?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: `${expert.system}\n\n${prompt}` }] }],
          generationConfig: { maxOutputTokens: 8192 }
        })
      });
      const data = await response.json();
      content = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
      tokens = data.usageMetadata?.totalTokenCount || 0;
    } else {
      // DeepSeek API (OpenAI compatible)
      response = await fetch(config.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model: config.model,
          messages: [
            { role: 'system', content: expert.system },
            { role: 'user', content: prompt }
          ],
          max_tokens: 8192
        })
      });
      const data = await response.json();
      content = data.choices?.[0]?.message?.content || '';
      tokens = data.usage?.total_tokens || 0;
    }

    const latency = Date.now() - startTime;
    return { content, tokens, latency };
  } catch (error) {
    console.error(`Error calling ${expertId}:`, error);
    throw error;
  }
}

// 保存专家输出
function saveOutput(taskId: string, expertModel: string, outputType: string, content: string, tokens: number, latency: number): number {
  const result = db.run(`
    INSERT INTO xiaoai_expert_outputs (task_id, expert_model, output_type, content, token_count, latency_ms)
    VALUES (?, ?, ?, ?, ?, ?)
  `, [taskId, expertModel, outputType, content, tokens, latency]);

  return Number(result.lastInsertRowid);
}

// 保存互评
function savePeerReview(taskId: string, reviewerModel: string, revieweeModel: string, outputId: number, score: number, feedback: string) {
  db.run(`
    INSERT INTO xiaoai_peer_reviews (task_id, reviewer_model, reviewee_model, output_id, score, feedback)
    VALUES (?, ?, ?, ?, ?, ?)
  `, [taskId, reviewerModel, revieweeModel, outputId, score, feedback]);
}

// 解析互评分数
function parseReviewScore(reviewText: string): { score: number; feedback: string } {
  // 尝试从文本中提取分数
  const scoreMatch = reviewText.match(/(\d+(?:\.\d+)?)\s*[\/分]/);
  const score = scoreMatch ? Math.min(10, parseFloat(scoreMatch[1])) : 7;
  return { score, feedback: reviewText };
}

// 主流程
async function runInsight(taskId: string, topic: string) {
  console.log(`\n========================================`);
  console.log(`开始洞察分析: ${topic}`);
  console.log(`任务ID: ${taskId}`);
  console.log(`========================================\n`);

  const outputs: Record<string, { outputId: number; content: string }> = {};

  // Phase 1: 各专家独立分析
  console.log('📝 Phase 1: 专家独立分析\n');

  for (const [expertId, expert] of Object.entries(EXPERTS)) {
    console.log(`  🔬 ${expert.nickname} (${expertId}) 开始分析...`);

    try {
      const prompt = `请对以下主题进行深入分析：\n\n${topic}\n\n要求：
1. 结构化输出，包含概述、关键发现、详细分析、结论建议
2. 引用具体数据或案例支撑观点
3. 字数 800-1500 字`;

      const result = await callExpert(expertId, prompt);
      const outputId = saveOutput(taskId, expertId, 'analysis', result.content, result.tokens, result.latency);

      outputs[expertId] = { outputId, content: result.content };

      console.log(`  ✅ ${expert.nickname} 完成 (${result.tokens} tokens, ${result.latency}ms)\n`);
    } catch (error) {
      console.log(`  ❌ ${expert.nickname} 失败: ${error}\n`);
    }
  }

  // Phase 2: 互评
  console.log('\n🔍 Phase 2: 专家互评\n');

  const expertIds = Object.keys(outputs);
  for (let i = 0; i < expertIds.length; i++) {
    const reviewer = expertIds[i];
    const reviewee = expertIds[(i + 1) % expertIds.length];

    if (!outputs[reviewer] || !outputs[reviewee]) continue;

    console.log(`  👁️ ${EXPERTS[reviewer as keyof typeof EXPERTS].nickname} 评审 ${EXPERTS[reviewee as keyof typeof EXPERTS].nickname} 的分析...`);

    try {
      const prompt = `请评审以下分析报告，给出 1-10 分并说明理由：

【被评审的分析】
${outputs[reviewee].content.slice(0, 2000)}

评分维度：
1. 准确性 (事实是否正确)
2. 深度 (分析是否透彻)
3. 逻辑性 (论证是否严密)
4. 实用性 (建议是否可行)

请给出总分 (X/10) 和具体反馈。`;

      const result = await callExpert(reviewer, prompt);
      const { score, feedback } = parseReviewScore(result.content);

      saveOutput(taskId, reviewer, 'review', result.content, result.tokens, result.latency);
      savePeerReview(taskId, reviewer, reviewee, outputs[reviewee].outputId, score, feedback);

      console.log(`  ✅ 评分: ${score}/10 (${result.tokens} tokens)\n`);
    } catch (error) {
      console.log(`  ❌ 评审失败: ${error}\n`);
    }
  }

  // Phase 3: 综合报告
  console.log('\n📊 Phase 3: 生成综合报告\n');

  const allAnalyses = Object.entries(outputs)
    .map(([id, o]) => `【${EXPERTS[id as keyof typeof EXPERTS].nickname}的分析】\n${o.content.slice(0, 1500)}`)
    .join('\n\n---\n\n');

  try {
    const synthesisPrompt = `请综合以下多位专家的分析，生成一份完整的洞察报告：

${allAnalyses}

要求：
1. 提取各方共识
2. 整合不同视角
3. 形成完整结论
4. 给出行动建议

格式：Markdown，包含标题、摘要、正文、结论`;

    const result = await callExpert('gemini-2.5-pro', synthesisPrompt);
    saveOutput(taskId, 'gemini-2.5-pro', 'synthesis', result.content, result.tokens, result.latency);

    console.log(`  ✅ 综合报告生成完成\n`);
    console.log('\n========================================');
    console.log('📋 综合报告');
    console.log('========================================\n');
    console.log(result.content);
  } catch (error) {
    console.log(`  ❌ 综合报告生成失败: ${error}\n`);
  }

  console.log('\n========================================');
  console.log('✅ 洞察分析完成');
  console.log(`任务ID: ${taskId}`);
  console.log('数据已保存到 solar.db，等待 CEO 考评');
  console.log('========================================\n');
}

// 入口
const taskId = process.argv[2];
const topic = process.argv[3];

if (!taskId || !topic) {
  console.error('用法: bun insight-coordinator.ts <task_id> <topic>');
  process.exit(1);
}

runInsight(taskId, topic).catch(console.error);
