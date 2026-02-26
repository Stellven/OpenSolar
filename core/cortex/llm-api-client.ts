/**
 * LLM API Client - 直接调用模型 API（绕过 brain-router HTTP）
 *
 * brain-router 仅支持 MCP (stdio) 协议，不提供 HTTP 服务。
 * 此模块直接调用各模型供应商 API。
 *
 * 支持：DeepSeek (V3/R1), GLM (4-plus/4-flash/5), Gemini (2.5-pro/3-pro)
 *
 * @created 2026-02-22
 */

import { readFileSync } from 'fs';

// ============================================================
// API 配置
// ============================================================

const ENV_PATH = `${process.env.HOME}/.solar/brain-router/.env`;

interface ApiKeys {
  ZHIPU_API_KEY: string;
  DEEPSEEK_API_KEY: string;
  GOOGLE_API_KEY: string;
}

let _cachedKeys: ApiKeys | null = null;

function loadApiKeys(): ApiKeys {
  if (_cachedKeys) return _cachedKeys;

  try {
    const envContent = readFileSync(ENV_PATH, 'utf-8');
    const keys: Record<string, string> = {};
    for (const line of envContent.split('\n')) {
      const match = line.match(/^(\w+)=(.+)$/);
      if (match) keys[match[1]] = match[2].trim();
    }
    _cachedKeys = {
      ZHIPU_API_KEY: keys.ZHIPU_API_KEY || '',
      DEEPSEEK_API_KEY: keys.DEEPSEEK_API_KEY || '',
      GOOGLE_API_KEY: keys.GOOGLE_API_KEY || '',
    };
    return _cachedKeys;
  } catch (err) {
    throw new Error(`无法加载 API keys from ${ENV_PATH}: ${err}`);
  }
}

// ============================================================
// 模型路由
// ============================================================

type Provider = 'deepseek' | 'zhipu' | 'google';

interface ModelRoute {
  provider: Provider;
  apiModel: string;  // 实际发给 API 的 model ID
}

const MODEL_ROUTES: Record<string, ModelRoute> = {
  // DeepSeek
  'deepseek-v3':        { provider: 'deepseek', apiModel: 'deepseek-chat' },
  'deepseek-chat':      { provider: 'deepseek', apiModel: 'deepseek-chat' },
  'deepseek-r1':        { provider: 'deepseek', apiModel: 'deepseek-reasoner' },
  'deepseek-reasoner':  { provider: 'deepseek', apiModel: 'deepseek-reasoner' },
  // GLM / ZhiPu
  'glm-5':         { provider: 'zhipu', apiModel: 'glm-5' },
  'glm-4-flash':        { provider: 'zhipu', apiModel: 'glm-4-flash' },
  'glm-5':              { provider: 'zhipu', apiModel: 'glm-5' },
  // Gemini / Google
  'gemini-2.5-pro':     { provider: 'google', apiModel: 'gemini-2.5-pro' },
  'gemini-2-pro':       { provider: 'google', apiModel: 'gemini-2.0-pro' },
  'gemini-2-flash':     { provider: 'google', apiModel: 'gemini-2.0-flash' },
  'gemini-2.5-flash':   { provider: 'google', apiModel: 'gemini-2.5-flash' },
  'gemini-3-pro-preview': { provider: 'google', apiModel: 'gemini-3-pro-preview' },
};

function getModelRoute(model: string): ModelRoute {
  const route = MODEL_ROUTES[model];
  if (!route) {
    // 猜测: glm 开头 → zhipu, deepseek 开头 → deepseek, gemini 开头 → google
    if (model.startsWith('glm'))      return { provider: 'zhipu', apiModel: model };
    if (model.startsWith('deepseek')) return { provider: 'deepseek', apiModel: model };
    if (model.startsWith('gemini'))   return { provider: 'google', apiModel: model };
    // 默认走 zhipu
    return { provider: 'zhipu', apiModel: model };
  }
  return route;
}

// ============================================================
// OpenAI-compatible 调用 (DeepSeek, GLM/ZhiPu)
// ============================================================

async function callOpenAICompatible(
  baseUrl: string,
  apiKey: string,
  model: string,
  systemPrompt: string,
  userPrompt: string,
  temperature: number
): Promise<string> {
  const messages: Array<{ role: string; content: string }> = [];
  if (systemPrompt) {
    messages.push({ role: 'system', content: systemPrompt });
  }
  messages.push({ role: 'user', content: userPrompt });

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages,
      temperature,
      max_tokens: 4096,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(`API 调用失败 [${model}]: ${response.status} ${response.statusText} - ${errorText.substring(0, 200)}`);
  }

  const data = await response.json() as any;
  return data.choices?.[0]?.message?.content || '';
}

// ============================================================
// Gemini 调用 (Google)
// ============================================================

async function callGemini(
  apiKey: string,
  model: string,
  systemPrompt: string,
  userPrompt: string,
  temperature: number
): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  const contents: any[] = [];

  // Gemini 用 system_instruction 传系统提示
  const body: any = {
    contents: [
      {
        role: 'user',
        parts: [{ text: userPrompt }],
      },
    ],
    generationConfig: {
      temperature,
      maxOutputTokens: 4096,
    },
  };

  if (systemPrompt) {
    body.system_instruction = {
      parts: [{ text: systemPrompt }],
    };
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(`Gemini API 调用失败 [${model}]: ${response.status} ${response.statusText} - ${errorText.substring(0, 200)}`);
  }

  const data = await response.json() as any;
  return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
}

// ============================================================
// 统一入口
// ============================================================

/**
 * 调用 LLM API（直接调用模型供应商，不经过 brain-router HTTP）
 *
 * @param model - 模型名称 (如 'glm-5', 'deepseek-r1', 'gemini-2.5-pro')
 * @param systemPrompt - 系统提示
 * @param userPrompt - 用户提示
 * @param temperature - 温度 (默认 0.3)
 * @returns LLM 输出文本
 */
export async function callLLM(
  model: string,
  systemPrompt: string,
  userPrompt: string,
  temperature: number = 0.3
): Promise<string> {
  const keys = loadApiKeys();
  const route = getModelRoute(model);

  switch (route.provider) {
    case 'deepseek':
      return callOpenAICompatible(
        'https://api.deepseek.com/v1',
        keys.DEEPSEEK_API_KEY,
        route.apiModel,
        systemPrompt,
        userPrompt,
        temperature
      );

    case 'zhipu':
      return callOpenAICompatible(
        'https://open.bigmodel.cn/api/paas/v4',
        keys.ZHIPU_API_KEY,
        route.apiModel,
        systemPrompt,
        userPrompt,
        temperature
      );

    case 'google':
      return callGemini(
        keys.GOOGLE_API_KEY,
        route.apiModel,
        systemPrompt,
        userPrompt,
        temperature
      );

    default:
      throw new Error(`未知的模型供应商: ${route.provider} (model=${model})`);
  }
}
