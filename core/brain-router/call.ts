#!/usr/bin/env bun
/**
 * Brain Router 简化调用接口
 *
 * 用法: bun call.ts <model> <prompt>
 *
 * 示例:
 *   bun call.ts glm-4-flash "总结这段话"
 *   bun call.ts gemini-2.5-pro "分析这个架构"
 */

import { execSync } from 'child_process';

const HOME = process.env.HOME || '/Users/sihaoli';
const SOLAR_DB = `${HOME}/.solar/solar.db`;

// 模型别名映射
const MODEL_ALIASES: Record<string, string> = {
  // GLM 系列
  'glm-4-flash': 'glm-4-flash',
  'glm-4-plus': 'glm-4-plus',
  'glm-5': 'glm-5',
  '小快手': 'glm-4-flash',
  '建设者': 'glm-4-plus',
  '智囊': 'glm-5',

  // Gemini 系列
  'gemini-2-flash': 'gemini-2-flash',
  'gemini-2.5-flash': 'gemini-2.5-flash-preview-05-20',
  'gemini-2.5-pro': 'gemini-2.5-pro-preview-05-06',
  'gemini-3-pro': 'gemini-3-pro-preview',
  'gemini-3-flash': 'gemini-3-flash-preview',
  '闪电侠': 'gemini-2-flash',
  '稳健派': 'gemini-2.5-pro',
  '探索派': 'gemini-3-pro',

  // DeepSeek 系列
  'deepseek-v3': 'deepseek-chat',      // DeepSeek V3 通过 deepseek-chat 访问
  'deepseek-r1': 'deepseek-reasoner',  // DeepSeek R1 推理模型
  'deepseek-chat': 'deepseek-chat',
  '创想家': 'deepseek-chat',
  '审判官': 'deepseek-reasoner',

  // 其他
  'gpt-4o': 'gpt-4o',
  'gpt-4o-mini': 'gpt-4o-mini',
  'o1': 'o1',
  'o1-mini': 'o1-mini',
  '综合官': 'gpt-4o',
  '小管家': 'gpt-4o-mini',
};

// API 端点
const API_ENDPOINTS: Record<string, { url: string; keyEnv: string }> = {
  'glm': { url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions', keyEnv: 'GLM_API_KEY' },
  'gemini': { url: 'https://generativelanguage.googleapis.com/v1beta/models', keyEnv: 'GEMINI_API_KEY' },
  'deepseek': { url: 'https://api.deepseek.com/v1/chat/completions', keyEnv: 'DEEPSEEK_API_KEY' },
  'gpt': { url: 'https://api.openai.com/v1/chat/completions', keyEnv: 'OPENAI_API_KEY' },
  'o1': { url: 'https://api.openai.com/v1/chat/completions', keyEnv: 'OPENAI_API_KEY' },
};

function getModelProvider(model: string): string {
  if (model.startsWith('glm')) return 'glm';
  if (model.startsWith('gemini')) return 'gemini';
  if (model.startsWith('deepseek')) return 'deepseek';
  if (model.startsWith('gpt') || model.startsWith('o1')) return 'gpt';
  return 'glm'; // 默认
}

async function callGLM(model: string, prompt: string, systemPrompt?: string): Promise<string> {
  const apiKey = process.env.GLM_API_KEY;
  if (!apiKey) {
    throw new Error('GLM_API_KEY 环境变量未设置');
  }

  const actualModel = MODEL_ALIASES[model] || model;

  const response = await fetch('https://open.bigmodel.cn/api/paas/v4/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: actualModel,
      messages: [
        ...(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []),
        { role: 'user', content: prompt },
      ],
      max_tokens: 4096,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`GLM API 错误: ${response.status} ${error}`);
  }

  const data = await response.json() as any;
  return data.choices[0]?.message?.content || '';
}

async function callGemini(model: string, prompt: string, systemPrompt?: string): Promise<string> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY 环境变量未设置');
  }

  const actualModel = MODEL_ALIASES[model] || model;

  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${actualModel}:generateContent?key=${apiKey}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        systemInstruction: systemPrompt ? { parts: [{ text: systemPrompt }] } : undefined,
        generationConfig: {
          maxOutputTokens: 8192,
        },
      }),
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Gemini API 错误: ${response.status} ${error}`);
  }

  const data = await response.json() as any;
  return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
}

async function callDeepSeek(model: string, prompt: string, systemPrompt?: string): Promise<string> {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) {
    throw new Error('DEEPSEEK_API_KEY 环境变量未设置');
  }

  const actualModel = MODEL_ALIASES[model] || model;

  const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: actualModel,
      messages: [
        ...(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []),
        { role: 'user', content: prompt },
      ],
      max_tokens: 8192,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`DeepSeek API 错误: ${response.status} ${error}`);
  }

  const data = await response.json() as any;
  return data.choices[0]?.message?.content || '';
}

async function callOpenAI(model: string, prompt: string, systemPrompt?: string): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY 环境变量未设置');
  }

  const actualModel = MODEL_ALIASES[model] || model;

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: actualModel,
      messages: [
        ...(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []),
        { role: 'user', content: prompt },
      ],
      max_tokens: 16384,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenAI API 错误: ${response.status} ${error}`);
  }

  const data = await response.json() as any;
  return data.choices[0]?.message?.content || '';
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log('用法: bun call.ts <model> <prompt> [system]');
    console.log('');
    console.log('模型别名:');
    console.log('  GLM: glm-4-flash (小快手), glm-4-plus (建设者), glm-5 (智囊)');
    console.log('  Gemini: gemini-2.5-pro (稳健派), gemini-3-pro (探索派)');
    console.log('  DeepSeek: deepseek-v3 (创想家), deepseek-r1 (审判官)');
    console.log('  OpenAI: gpt-4o (综合官), gpt-4o-mini (小管家)');
    process.exit(1);
  }

  const model = args[0];
  let prompt = args[1];
  const systemPrompt = args[2];

  // 解码 URL 编码的 prompt
  try {
    prompt = decodeURIComponent(prompt);
  } catch {
    // 如果解码失败，保持原样
  }

  const provider = getModelProvider(model);
  console.error(`调用 ${provider}/${model}...`);

  try {
    let result: string;

    switch (provider) {
      case 'glm':
        result = await callGLM(model, prompt, systemPrompt);
        break;
      case 'gemini':
        result = await callGemini(model, prompt, systemPrompt);
        break;
      case 'deepseek':
        result = await callDeepSeek(model, prompt, systemPrompt);
        break;
      case 'gpt':
        result = await callOpenAI(model, prompt, systemPrompt);
        break;
      default:
        throw new Error(`未知模型提供商: ${provider}`);
    }

    console.log(result);
  } catch (error) {
    console.error('调用失败:', error);
    process.exit(1);
  }
}

main();
