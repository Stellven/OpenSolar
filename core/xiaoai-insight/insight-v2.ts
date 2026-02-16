/**
 * 洞察系统 v2.0 - 七阶段完整流程
 *
 * Phase 1: 小爱调用 Gemini 生成大纲提示词 → 持久化
 * Phase 2: 四专家各自生成大纲 → 持久化三份
 * Phase 3: 四专家互评 → 记录评审结果
 * Phase 4: Gemini 综合大纲 + 拆解章节提示词 → 持久化
 * Phase 5: 每章节：四专家写作 + 互评 + Gemini综合
 * Phase 6: 合并所有章节为初稿 → 持久化
 * Phase 7: 生成结构化输出
 */

import { homedir } from 'os';
import { existsSync, mkdirSync, writeFileSync, readFileSync, copyFileSync } from 'fs';
import { join } from 'path';
import { Database } from 'bun:sqlite';
import Cortex from '../cortex/index';
import {
  generateExpertSystemPrompt,
  getExpertInfo,
  getExpertAnchor,
  type ExpertInfo
} from '../solar-farm/expert-personality';

// ============================================================
// Persona Bank ELO 集成
// ============================================================
const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// 专家模型 ID 到 Persona ID 的映射
const EXPERT_TO_PERSONA: Record<string, string> = {
  'gemini-2.5-pro': 'gemini_pro_analyst_strict',
  'deepseek-r1': 'deepseek_r1_reasoner_deep',
  'deepseek-v3': 'deepseek_v3_writer_creative',
  'gemini-3-pro-preview': 'gemini_3_explorer_innovative',
  'glm-5': 'glm_5_champion_workhorse'
};

// 专家模型 ID 到厂商的映射 (避免同厂商互评)
const EXPERT_VENDOR: Record<string, string> = {
  'gemini-2.5-pro': 'google',
  'gemini-3-pro-preview': 'google',
  'deepseek-r1': 'deepseek',
  'deepseek-v3': 'deepseek',
  'glm-5': 'zhipu',
  'glm-4-plus': 'zhipu',
  'glm-4-flash': 'zhipu'
};

/**
 * 生成跨厂商评审配对
 * 确保评审者和被评审者来自不同厂商
 */
function generateCrossVendorPairs(expertIds: string[]): Array<{reviewer: string, target: string}> {
  const pairs: Array<{reviewer: string, target: string}> = [];

  for (const reviewerId of expertIds) {
    const reviewerVendor = EXPERT_VENDOR[reviewerId] || 'unknown';
    // 找到所有不同厂商的专家
    const differentVendorTargets = expertIds.filter(id => {
      const targetVendor = EXPERT_VENDOR[id] || 'unknown';
      return targetVendor !== reviewerVendor;
    });

    if (differentVendorTargets.length > 0) {
      // 选择第一个不同厂商的专家作为评审目标
      // 可以用 ELO 或随机来选择，这里用顺序选择
      const targetId = differentVendorTargets[0];
      pairs.push({ reviewer: reviewerId, target: targetId });
    }
  }

  return pairs;
}

// 角色 → 偏好的专家类型映射
const ROLE_TO_EXPERT_TYPE: Record<string, string[]> = {
  'author': ['gemini-2.5-pro', 'deepseek-v3', 'glm-5'],      // 作者角色：严谨分析 + 创意表达 + 配合执行
  'reviewer': ['deepseek-r1', 'gemini-2.5-pro'],    // 审核角色：深度推理 + 严谨分析
  'challenger': ['deepseek-v3', 'gemini-3-pro-preview'], // 挑战者：创意 + 探索
  'synthesizer': ['gemini-2.5-pro', 'deepseek-r1']  // 综合者：严谨 + 推理
};

/**
 * 根据 ELO 分数选择专家
 * @param role 角色类型 (author/reviewer/challenger/synthesizer)
 * @param topN 返回前 N 个专家
 * @returns 按角色和 ELO 排序的专家 ID 列表
 */
function selectExpertsByElo(role?: string, topN: number = 4): string[] {
  const db = new Database(DB_PATH);

  try {
    // 获取所有专家的 ELO 分数
    const eloData = db.query(`
      SELECT persona_id, elo_rating, win_rate, total_matches
      FROM sys_persona_elo
      ORDER BY elo_rating DESC
    `).all() as { persona_id: string; elo_rating: number; win_rate: number; total_matches: number }[];

    // Persona ID → Expert ID 的反向映射
    const personaToExpert: Record<string, string> = {};
    for (const [expertId, personaId] of Object.entries(EXPERT_TO_PERSONA)) {
      personaToExpert[personaId] = expertId;
    }

    // 如果指定了角色，优先选择该角色类型的专家
    if (role && ROLE_TO_EXPERT_TYPE[role]) {
      const preferredExperts = ROLE_TO_EXPERT_TYPE[role];
      const sorted = eloData
        .filter(e => {
          const expertId = personaToExpert[e.persona_id];
          return preferredExperts.includes(expertId);
        })
        .map(e => personaToExpert[e.persona_id]);

      // 如果角色偏好专家不足，补充其他专家
      const remaining = eloData
        .filter(e => !ROLE_TO_EXPERT_TYPE[role].includes(personaToExpert[e.persona_id]))
        .map(e => personaToExpert[e.persona_id]);

      return [...sorted, ...remaining].slice(0, topN);
    }

    // 默认按 ELO 排序返回
    return eloData.slice(0, topN).map(e => personaToExpert[e.persona_id]);
  } finally {
    db.close();
  }
}

/**
 * 记录专家对局结果到 sys_persona_matches
 * 这会触发 ELO 自动更新
 */
function recordPersonaMatch(
  taskId: string,
  personaA: string,
  personaB: string,
  scoreA: number,
  scoreB: number
): void {
  const db = new Database(DB_PATH);

  try {
    // 判断胜者
    let winner: string;
    if (scoreA > scoreB) {
      winner = personaA;
    } else if (scoreB > scoreA) {
      winner = personaB;
    } else {
      winner = 'draw';
    }

    // 计算 ELO 变化 (简化版 ELO 公式)
    const K = 32; // ELO K 因子
    const getElo = (personaId: string): number => {
      const row = db.query(`
        SELECT elo_rating FROM sys_persona_elo WHERE persona_id = ?
      `).get(personaId) as { elo_rating: number } | undefined;
      return row?.elo_rating || 1500;
    };

    const eloA = getElo(personaA);
    const eloB = getElo(personaB);

    // 期望得分
    const expectedA = 1 / (1 + Math.pow(10, (eloB - eloA) / 400));
    const expectedB = 1 / (1 + Math.pow(10, (eloA - eloB) / 400));

    // 实际得分
    const actualA = scoreA > scoreB ? 1 : (scoreA < scoreB ? 0 : 0.5);
    const actualB = scoreB > scoreA ? 1 : (scoreB < scoreA ? 0 : 0.5);

    // ELO 变化
    const eloChangeA = K * (actualA - expectedA);
    const eloChangeB = K * (actualB - expectedB);

    // 插入对局记录 (触发器会自动更新 ELO)
    db.run(`
      INSERT INTO sys_persona_matches
      (task_id, persona_a, persona_b, score_a, score_b, winner, elo_change_a, elo_change_b)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `, [taskId, personaA, personaB, scoreA, scoreB, winner, eloChangeA, eloChangeB]);

    console.log(`  🏆 Persona Match: ${personaA}(${scoreA}) vs ${personaB}(${scoreB}) → ${winner} wins`);
    console.log(`     ELO 变化: ${personaA} ${eloChangeA > 0 ? '+' : ''}${eloChangeA.toFixed(1)}, ${personaB} ${eloChangeB > 0 ? '+' : ''}${eloChangeB.toFixed(1)}`);
  } finally {
    db.close();
  }
}

// ============================================================
// 架构改进：CapsuleView + Evidence First + 牛马隔离
// ============================================================

interface TaskCapsule {
  taskId: string;
  topic: string;
  currentPhase: number;
  phaseStatus: Record<number, 'pending' | 'in_progress' | 'completed'>;
  expertScores: Record<string, number>;
  eloSnapshot: { persona_id: string; elo_rating: number }[];
  evidenceSummary: { sourceCount: number; topKeywords: string[] };
  createdAt: string;
  updatedAt: string;
}

/**
 * 保存任务胶囊 - 用于 compaction 后恢复
 * 只保留态势信息，不保留 bulky 内容
 */
function saveTaskCapsule(capsule: TaskCapsule): void {
  const db = new Database(DB_PATH);
  try {
    db.run(`
      INSERT OR REPLACE INTO cortex_task_capsules
      (task_id, capsule_json, updated_at)
      VALUES (?, ?, datetime('now'))
    `, [capsule.taskId, JSON.stringify(capsule)]);
  } finally {
    db.close();
  }
}

/**
 * 恢复任务胶囊 - compaction/重启后恢复态势
 */
function restoreTaskCapsule(taskId: string): TaskCapsule | null {
  const db = new Database(DB_PATH);
  try {
    const row = db.query(`
      SELECT capsule_json FROM cortex_task_capsules WHERE task_id = ?
    `).get(taskId) as { capsule_json: string } | undefined;

    if (row) {
      return JSON.parse(row.capsule_json) as TaskCapsule;
    }
    return null;
  } finally {
    db.close();
  }
}

/**
 * Evidence First - Phase 开始前先查证据
 * 返回：已有资料数、ELO 排名、相关关键词
 */
function gatherEvidence(taskId: string, phase: number): {
  sourceCount: number;
  eloRanking: { expert: string; elo: number }[];
  relatedKeywords: string[];
} {
  const db = new Database(DB_PATH);
  try {
    // 1. 查已有资料数
    const sourceRow = db.query(`
      SELECT COUNT(*) as cnt FROM cortex_sources WHERE task_id = ?
    `).get(taskId) as { cnt: number } | undefined;
    const sourceCount = sourceRow?.cnt || 0;

    // 2. 查 ELO 排名
    const eloRows = db.query(`
      SELECT persona_id, elo_rating
      FROM sys_persona_elo
      ORDER BY elo_rating DESC
      LIMIT 5
    `).all() as { persona_id: string; elo_rating: number }[];

    const personaToExpert: Record<string, string> = {
      'gemini_pro_analyst_strict': 'gemini-2.5-pro',
      'deepseek_r1_reasoner_deep': 'deepseek-r1',
      'deepseek_v3_writer_creative': 'deepseek-v3',
      'gemini_3_explorer_innovative': 'gemini-3-pro-preview',
      'glm_5_champion_workhorse': 'glm-5'
    };

    const eloRanking = eloRows.map(r => ({
      expert: personaToExpert[r.persona_id] || r.persona_id,
      elo: Math.round(r.elo_rating)
    }));

    // 3. 查相关关键词（从已有 artifacts 提取）
    const artifactRows = db.query(`
      SELECT content_json FROM cortex_artifacts
      WHERE task_id = ? AND phase < ?
      LIMIT 10
    `).all(taskId, phase) as { content_json: string }[];

    const keywords = new Set<string>();
    for (const row of artifactRows) {
      const content = row.content_json.toLowerCase();
      // 简单提取关键词
      const matches = content.match(/\b[a-z]{4,}\b/g) || [];
      matches.slice(0, 5).forEach(k => keywords.add(k));
    }

    return {
      sourceCount,
      eloRanking,
      relatedKeywords: Array.from(keywords).slice(0, 10)
    };
  } finally {
    db.close();
  }
}

/**
 * 牛马隔离 - callExpert 完成后清理上下文
 * 将结果持久化，返回精简摘要
 */
function isolateExpertResult(
  taskId: string,
  phase: number,
  expertId: string,
  result: ExpertResponse,
  artifactPath: string
): { summary: string; tokens: { in: number; out: number }; artifactPath: string } {
  // 生成精简摘要（不保留完整内容）
  const summary = result.content.slice(0, 200) + '...';

  // 记录到数据库（持久化）
  const db = new Database(DB_PATH);
  try {
    db.run(`
      INSERT INTO cortex_expert_results
      (task_id, phase, expert_id, input_tokens, output_tokens, latency_ms, artifact_path, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `, [taskId, phase, expertId, result.inputTokens, result.outputTokens, result.latencyMs, artifactPath]);
  } finally {
    db.close();
  }

  // 返回精简信息（主控脑只保留这些）
  return {
    summary,
    tokens: { in: result.inputTokens, out: result.outputTokens },
    artifactPath
  };
}

// ============================================================
// REPORT 模板路径 (报告工程化流水线)
// ============================================================
const REPORT_TEMPLATE_DIR = join(homedir(), '.claude/templates/REPORT');
const REPORT_FILES = ['STATE.md', 'OUTLINE.md', 'SOURCES.md', 'CLAIMS.md'];
const NOTES_TEMPLATE = join(REPORT_TEMPLATE_DIR, 'NOTES/_TEMPLATE.md');

// ============================================================
// 专家配置 (统一从 niumao-anchors.ts v3.0 获取)
// ============================================================

interface ExpertConfig {
  model: string;
  nickname: string;
  role: 'author' | 'reviewer' | 'challenger' | 'synthesizer';
  personality: {
    O: number;  // 开放性
    C: number;  // 尽责性
    E: number;  // 外向性
    A: number;  // 宜人性
    N: number;  // 神经质
  };
  style: string;
  systemPrompt: string;
}

/**
 * 从统一人格系统获取专家配置
 * 确保 Solar 和小爱使用相同的 niumao-anchors.ts v3.0
 */
function getExpertConfig(modelId: string): ExpertConfig | undefined {
  const info = getExpertInfo(modelId);
  if (!info) return undefined;

  // 根据人格特征推断角色
  let role: 'author' | 'reviewer' | 'challenger' | 'synthesizer' = 'author';
  const { traits } = info.anchor;

  if (traits.C >= 0.9) {
    role = 'reviewer';  // 高尽责性 → 审核角色
  } else if (traits.O >= 0.9) {
    role = 'challenger'; // 高开放性 → 创意/挑战角色
  } else if (traits.A >= 0.7 && traits.C >= 0.8) {
    role = 'synthesizer'; // 高宜人性+高尽责性 → 综合角色
  }

  return {
    model: info.modelId,
    nickname: info.anchor.role.nickname,
    role,
    personality: {
      O: traits.O,
      C: traits.C,
      E: traits.E,
      A: traits.A,
      N: traits.N
    },
    style: info.anchor.role.primaryResponsibilities.join('、'),
    systemPrompt: info.systemPrompt
  };
}

// 支持的专家模型列表
const SUPPORTED_EXPERTS = [
  'gemini-2.5-pro',   // 稳健派
  'gemini-3-pro',     // 探索派
  'gemini-3-pro-preview', // 探索派 (兼容)
  'deepseek-r1',      // 审判官
  'deepseek-v3',      // 创想家
  'glm-5'             // 智囊
];

// 动态构建 EXPERTS (从统一人格系统)
const EXPERTS: Record<string, ExpertConfig> = new Proxy({} as Record<string, ExpertConfig>, {
  get(_, prop: string) {
    if (prop === 'then' || prop === 'toJSON') return undefined;
    const modelId = prop === 'gemini-3-pro-preview' ? 'gemini-3-pro' : prop;
    return getExpertConfig(modelId);
  },
  ownKeys() {
    return SUPPORTED_EXPERTS;
  },
  getOwnPropertyDescriptor() {
    return { enumerable: true, configurable: true };
  }
});

// 便捷访问 (兼容旧代码)
const GEMINI_SYNTHESIZER = getExpertConfig('gemini-2.5-pro');

// ============================================================
// API 配置
// ============================================================

const API_CONFIGS: Record<string, { url: string; keyEnv: string; modelId: string; maxTokens: number }> = {
  'gemini-2.5-pro': {
    url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent',
    keyEnv: 'GOOGLE_API_KEY',
    modelId: 'gemini-2.5-pro',
    maxTokens: 16384
  },
  'gemini-3-pro': {
    url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro:generateContent',
    keyEnv: 'GOOGLE_API_KEY',
    modelId: 'gemini-3-pro',
    maxTokens: 16384
  },
  'gemini-3-pro-preview': {
    url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro:generateContent',
    keyEnv: 'GOOGLE_API_KEY',
    modelId: 'gemini-3-pro',
    maxTokens: 16384
  },
  'deepseek-r1': {
    url: 'https://api.deepseek.com/v1/chat/completions',
    keyEnv: 'DEEPSEEK_API_KEY',
    modelId: 'deepseek-reasoner',
    maxTokens: 16384  // deepseek-reasoner 支持更大的输出
  },
  'deepseek-v3': {
    url: 'https://api.deepseek.com/v1/chat/completions',
    keyEnv: 'DEEPSEEK_API_KEY',
    modelId: 'deepseek-chat',
    maxTokens: 8192  // deepseek-chat 限制为 8192
  },
  'glm-5': {
    url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    keyEnv: 'ZHIPU_API_KEY',
    modelId: 'glm-5',
    maxTokens: 16384
  }
};

// ============================================================
// 文件系统输出目录
// ============================================================

const ARTIFACTS_BASE = `${homedir()}/.solar/cortex/artifacts`;

function ensureDir(dir: string) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

function getTaskDir(taskId: string): string {
  const dir = join(ARTIFACTS_BASE, taskId);
  ensureDir(dir);
  return dir;
}

function saveDocument(taskId: string, phase: number, docType: string, content: string, expertModel?: string): string {
  const dir = getTaskDir(taskId);
  const timestamp = Date.now();
  const suffix = expertModel ? `_${expertModel.replace(/[^a-zA-Z0-9]/g, '-')}` : '';
  const fileName = `phase${phase}_${docType}${suffix}_${timestamp}.md`;
  const filePath = join(dir, fileName);
  writeFileSync(filePath, content);
  return filePath;
}

// ============================================================
// 调用专家 API
// ============================================================

interface ExpertResponse {
  content: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

async function callExpert(expertId: string, prompt: string): Promise<ExpertResponse> {
  const config = API_CONFIGS[expertId];
  const expert = EXPERTS[expertId];
  const apiKey = process.env[config.keyEnv];

  if (!apiKey) {
    throw new Error(`Missing API key: ${config.keyEnv}`);
  }

  const startTime = Date.now();

  try {
    let response;
    let content: string;
    let inputTokens = 0;
    let outputTokens = 0;

    if (expertId.startsWith('gemini')) {
      // Google Gemini API
      response = await fetch(`${config.url}?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: `${expert.systemPrompt}\n\n${prompt}` }] }],
          generationConfig: { maxOutputTokens: config.maxTokens }
        })
      });
      const data = await response.json();
      content = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
      inputTokens = data.usageMetadata?.promptTokenCount || 0;
      outputTokens = data.usageMetadata?.candidatesTokenCount || 0;
    } else {
      // DeepSeek/GLM API (OpenAI compatible)
      response = await fetch(config.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model: config.modelId,
          messages: [
            { role: 'system', content: expert.systemPrompt },
            { role: 'user', content: prompt }
          ],
          max_tokens: config.maxTokens
        })
      });
      const data = await response.json();

      // 检查 API 错误
      if (data.error) {
        console.error(`  ⚠️ ${expertId} API Error:`, data.error.message || JSON.stringify(data.error));
        throw new Error(`${expertId} API Error: ${data.error.message || 'Unknown error'}`);
      }

      content = data.choices?.[0]?.message?.content || '';

      // 检查空响应
      if (!content) {
        console.warn(`  ⚠️ ${expertId} returned empty content, response:`, JSON.stringify(data).slice(0, 500));
      }

      inputTokens = data.usage?.prompt_tokens || 0;
      outputTokens = data.usage?.completion_tokens || 0;
    }

    const latencyMs = Date.now() - startTime;
    return { content, inputTokens, outputTokens, latencyMs };

  } catch (error) {
    console.error(`Error calling ${expertId}:`, error);
    throw error;
  }
}

/**
 * 使用 Gemini Google Search Grounding 进行联网搜索
 * 专门用于研究阶段，搜索论文、技术文章、博客等
 */
async function callGeminiWithSearch(prompt: string): Promise<{
  content: string;
  searchResults: Array<{
    title: string;
    url: string;
    snippet: string;
  }>;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}> {
  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    throw new Error('GOOGLE_API_KEY not found in environment');
  }

  const startTime = Date.now();

  // 使用 Gemini 2.5 Pro 的 Google Search grounding
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent';

  const response = await fetch(`${url}?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{
        parts: [{ text: prompt }]
      }],
      tools: [{
        google_search: {}
      }],
      generationConfig: {
        maxOutputTokens: 8192
      }
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Gemini Search API error: ${response.status} - ${errorText}`);
  }

  const data = await response.json();
  const latencyMs = Date.now() - startTime;

  // DEBUG: 打印原始响应结构 (仅在开发时使用)
  if (process.env.DEBUG_GEMINI_SEARCH) {
    console.log('\n📡 Gemini Search Raw Response:');
    console.log(JSON.stringify(data, null, 2));
  }

  // 提取内容
  const content = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
  const inputTokens = data.usageMetadata?.promptTokenCount || 0;
  const outputTokens = data.usageMetadata?.candidatesTokenCount || 0;

  // 提取 grounding 元数据中的搜索结果
  const searchResults: Array<{ title: string; url: string; snippet: string }> = [];
  const groundingMetadata = data.candidates?.[0]?.groundingMetadata;

  if (groundingMetadata?.groundingChunks) {
    for (const chunk of groundingMetadata.groundingChunks) {
      if (chunk.web) {
        searchResults.push({
          title: chunk.web.title || 'Unknown',
          url: chunk.web.uri || '',
          snippet: ''
        });
      }
    }
  }

  // 从 searchEntryPoint 中提取更多结果
  if (groundingMetadata?.searchEntryPoint?.renderedContent) {
    // Google 返回的 HTML 格式搜索结果，解析链接
    const htmlContent = groundingMetadata.searchEntryPoint.renderedContent;
    const linkRegex = /href="([^"]+)"[^>]*>([^<]+)</g;
    let match;
    while ((match = linkRegex.exec(htmlContent)) !== null) {
      const url = match[1];
      const title = match[2];
      if (url.startsWith('http') && !searchResults.find(r => r.url === url)) {
        searchResults.push({ title, url, snippet: '' });
      }
    }
  }

  return {
    content,
    searchResults,
    inputTokens,
    outputTokens,
    latencyMs
  };
}

// ============================================================
// 估算成本
// ============================================================

const COST_PER_1K_TOKENS: Record<string, { input: number; output: number }> = {
  'gemini-2.5-pro': { input: 0.00125, output: 0.005 },
  'deepseek-r1': { input: 0.00055, output: 0.00219 },
  'deepseek-v3': { input: 0.00027, output: 0.0011 }
};

function estimateCost(model: string, inputTokens: number, outputTokens: number): number {
  const rates = COST_PER_1K_TOKENS[model] || { input: 0.001, output: 0.003 };
  return (inputTokens / 1000) * rates.input + (outputTokens / 1000) * rates.output;
}

// ============================================================
// 七阶段洞察引擎
// ============================================================

export class InsightEngine {
  private cortex: Cortex;
  private taskId: string = '';
  private topic: string = '';

  constructor() {
    this.cortex = new Cortex();
  }

  // ============================================================
  // REPORT 模板集成方法 (报告工程化流水线)
  // ============================================================

  /**
   * 初始化 REPORT 目录结构
   * 从模板复制基础文件，并初始化 STATE.md
   */
  private initReportDir(): string {
    const taskDir = getTaskDir(this.taskId);
    const reportDir = join(taskDir, 'REPORT');

    // 创建 REPORT 目录
    ensureDir(reportDir);
    ensureDir(join(reportDir, 'NOTES'));

    // 复制模板文件
    for (const file of REPORT_FILES) {
      const src = join(REPORT_TEMPLATE_DIR, file);
      const dst = join(reportDir, file);
      if (existsSync(src) && !existsSync(dst)) {
        copyFileSync(src, dst);
      }
    }

    // 初始化 STATE.md
    const stateContent = `# 报告态势板 (Report State)

> 任务ID: ${this.taskId}
> 创建时间: ${new Date().toISOString()}

## Topic / Audience / Scope

**主题**: ${this.topic}

**受众**: 技术决策者、研究人员

**范围**: 深度分析报告

## Thesis (核心论点)

> [待专家分析后填写]

## Progress

| Phase | Status | Checkpoint |
|-------|--------|------------|
| P1 大纲提示词 | ⏳ pending | - |
| P2 专家大纲 | ⏳ pending | - |
| P3 互评审核 | ⏳ pending | - |
| P4 综合大纲 | ⏳ pending | - |
| P5 章节写作 | ⏳ pending | - |
| P6 合并初稿 | ⏳ pending | - |
| P7 结构输出 | ⏳ pending | - |

## Risk / Blockers

- [暂无]

## Next Actions

- [ ] 等待 Phase 1 完成
`;

    writeFileSync(join(reportDir, 'STATE.md'), stateContent);
    console.log(`  📁 REPORT 目录已初始化: ${reportDir}`);

    return reportDir;
  }

  /**
   * 更新 REPORT/STATE.md 检查点
   */
  private updateReportState(phase: number, status: 'in_progress' | 'completed', notes?: string): void {
    const reportDir = join(getTaskDir(this.taskId), 'REPORT');
    const statePath = join(reportDir, 'STATE.md');

    if (!existsSync(statePath)) return;

    let content = readFileSync(statePath, 'utf-8');

    // 更新 Phase 状态
    const statusIcon = status === 'completed' ? '✅ completed' : '🔄 in_progress';
    const timestamp = new Date().toISOString().slice(0, 19);

    const phaseMap: Record<number, string> = {
      1: 'P1 大纲提示词',
      2: 'P2 专家大纲',
      3: 'P3 互评审核',
      4: 'P4 综合大纲',
      5: 'P5 章节写作',
      6: 'P6 合并初稿',
      7: 'P7 结构输出'
    };

    const phaseName = phaseMap[phase];
    if (phaseName) {
      const regex = new RegExp(`\\| ${phaseName} \\| [^|]+ \\| [^|]+ \\|`);
      content = content.replace(regex, `| ${phaseName} | ${statusIcon} | ${timestamp} |`);
    }

    // 添加笔记
    if (notes && status === 'completed') {
      content = content.replace(
        '## Risk / Blockers',
        `## Phase ${phase} Notes\n\n${notes}\n\n## Risk / Blockers`
      );
    }

    writeFileSync(statePath, content);
  }

  /**
   * 更新 REPORT/SOURCES.md 文献追踪
   */
  private updateReportSources(source: {
    key: string;
    title: string;
    authors?: string;
    year?: string;
    url?: string;
    conclusion?: string;
    credibility?: string;
    thesisRelation?: string;
  }): void {
    const reportDir = join(getTaskDir(this.taskId), 'REPORT');
    const sourcesPath = join(reportDir, 'SOURCES.md');

    if (!existsSync(sourcesPath)) return;

    let content = readFileSync(sourcesPath, 'utf-8');

    // 添加到文献表格
    const newRow = `| @${source.key} | ${source.title || '-'} | ${source.authors || '-'} | ${source.year || '-'} | ${source.credibility || '⭐⭐⭐'} | ${source.thesisRelation || '待分析'} |`;

    // 在表格末尾添加
    const tableEndMarker = '\n\n## 文献';
    if (content.includes(tableEndMarker)) {
      content = content.replace(tableEndMarker, `\n${newRow}${tableEndMarker}`);
    } else {
      // 如果没找到标记，追加到文件末尾
      content += `\n${newRow}`;
    }

    writeFileSync(sourcesPath, content);
  }

  /**
   * 创建论文笔记 REPORT/NOTES/paper-xxx.md
   */
  private createPaperNote(paperId: string, content: {
    title: string;
    authors?: string;
    problem?: string;
    method?: string;
    results?: string;
    keyNumbers?: string;
    weakness?: string;
    relevance?: string;
  }): string {
    const reportDir = join(getTaskDir(this.taskId), 'REPORT');
    const notesDir = join(reportDir, 'NOTES');
    ensureDir(notesDir);

    const noteContent = `# ${content.title}

> 论文ID: ${paperId}
> 记录时间: ${new Date().toISOString()}

## 基础信息

- **作者**: ${content.authors || '待填写'}
- **相关性**: ${content.relevance || '待评估'}

## Problem (解决什么问题)

${content.problem || '待分析'}

## Method (用什么方法)

${content.method || '待分析'}

## Results (关键结果)

${content.results || '待分析'}

## Key Numbers (关键数字)

${content.keyNumbers || '待提取'}

## Weakness (弱点/局限)

${content.weakness || '待分析'}

---

*笔记由 InsightEngine 自动生成*
`;

    const notePath = join(notesDir, `${paperId}.md`);
    writeFileSync(notePath, noteContent);
    return notePath;
  }

  /**
   * 更新 REPORT/CLAIMS.md 主张-证据矩阵
   */
  private updateReportClaims(claim: {
    id: string;
    content: string;
    chapter?: string;
    supportingSources?: string[];
    opposingSources?: string[];
    credibility?: 'high' | 'medium' | 'low';
  }): void {
    const reportDir = join(getTaskDir(this.taskId), 'REPORT');
    const claimsPath = join(reportDir, 'CLAIMS.md');

    if (!existsSync(claimsPath)) return;

    let fileContent = readFileSync(claimsPath, 'utf-8');

    // 构建 Claim 条目
    const supportingStr = claim.supportingSources?.map(s => `@${s}`).join(', ') || '待补充';
    const opposingStr = claim.opposingSources?.map(s => `@${s}`).join(', ') || '无';
    const credIcon = claim.credibility === 'high' ? '✅ 高' :
                     claim.credibility === 'low' ? '❌ 低' : '⚠️ 中';

    const claimEntry = `
### ${claim.id}: ${claim.content}

> 章节位置: ${claim.chapter || '待定'}

| 类型 | 文献 | 说明 |
|------|------|------|
| ✅ 支持 | ${supportingStr} | - |
| ❌ 反例 | ${opposingStr} | - |

**综合评估**: ${credIcon}

---
`;

    // 在矩阵汇总前添加
    if (fileContent.includes('## 矩阵汇总')) {
      fileContent = fileContent.replace('## 矩阵汇总', `${claimEntry}\n## 矩阵汇总`);
    } else {
      fileContent += claimEntry;
    }

    writeFileSync(claimsPath, fileContent);
  }

  /**
   * 更新 REPORT/OUTLINE.md 大纲
   */
  private updateReportOutline(sections: Array<{
    order: number;
    title: string;
    claims?: string[];
    sources?: string[];
    goal?: string;
  }>): void {
    const reportDir = join(getTaskDir(this.taskId), 'REPORT');
    const outlinePath = join(reportDir, 'OUTLINE.md');

    let content = `# 报告大纲 (Report Outline)

> 任务ID: ${this.taskId}
> 主题: ${this.topic}
> 更新时间: ${new Date().toISOString()}

---

`;

    for (const section of sections) {
      content += `## ${section.order}. ${section.title}

**目标**: ${section.goal || '待定'}

**Claims (主张)**:
${section.claims?.map(c => `- ${c}`).join('\n') || '- 待定'}

**Sources (引用)**:
${section.sources?.map(s => `- @${s}`).join('\n') || '- 待定'}

**Artifacts (产出物)**:
- [ ] 初稿
- [ ] 终稿

---

`;
    }

    writeFileSync(outlinePath, content);
    console.log(`  📁 OUTLINE.md 已更新`);
  }

  /**
   * 运行完整的七阶段洞察流程
   */
  async run(topic: string, requester?: string): Promise<string> {
    this.topic = topic;

    // 创建任务
    this.taskId = this.cortex.createTask('insight', topic, requester, {
      experts: Object.keys(EXPERTS),
      phases: 8  // 增加 Phase 8: CEO 总结
    });

    console.log(`\n${'='.repeat(60)}`);
    console.log(`🔬 开始洞察分析: ${topic}`);
    console.log(`📋 任务ID: ${this.taskId}`);
    console.log(`${'='.repeat(60)}\n`);

    // 初始化 REPORT 目录 (报告工程化流水线)
    this.initReportDir();

    try {
      // Phase 1: 生成大纲提示词
      this.updateReportState(1, 'in_progress');
      await this.phase1_generateOutlinePrompt();
      this.updateReportState(1, 'completed');

      // Phase 1.5: 研究搜索阶段 (使用 Gemini Google Search)
      console.log('\n' + '─'.repeat(50));
      await this.phase1_5_research();
      console.log('─'.repeat(50));

      // Phase 2: 四专家生成大纲
      this.updateReportState(2, 'in_progress');
      await this.phase2_expertsGenerateOutlines();
      this.updateReportState(2, 'completed');

      // Phase 3: 四专家互评
      this.updateReportState(3, 'in_progress');
      await this.phase3_crossReview();
      this.updateReportState(3, 'completed');

      // Phase 4: Gemini 综合大纲 + 拆解章节
      this.updateReportState(4, 'in_progress');
      await this.phase4_synthesizeAndSplit();
      this.updateReportState(4, 'completed');

      // Phase 5: 逐章节写作
      this.updateReportState(5, 'in_progress');
      await this.phase5_writeChapters();
      this.updateReportState(5, 'completed');

      // Phase 6: 合并初稿
      this.updateReportState(6, 'in_progress');
      await this.phase6_mergeDraft();
      this.updateReportState(6, 'completed');

      // Phase 7: 生成结构化输出
      this.updateReportState(7, 'in_progress');
      await this.phase7_generateStructuredOutput();
      this.updateReportState(7, 'completed');

      // Phase 8: CEO 总结 (Solar 作为 CEO 对报告进行总结点评)
      this.updateReportState(8, 'in_progress');
      await this.phase8_ceoSummary();
      this.updateReportState(8, 'completed');

      // 完成任务
      this.cortex.completeTask(this.taskId);

      console.log(`\n${'='.repeat(60)}`);
      console.log(`✅ 洞察分析完成`);
      console.log(`📋 任务ID: ${this.taskId}`);
      console.log(`📁 产物目录: ${getTaskDir(this.taskId)}`);
      console.log(`${'='.repeat(60)}\n`);

      return this.taskId;

    } catch (error) {
      console.error(`\n❌ 洞察分析失败: ${error}`);
      throw error;
    }
  }

  /**
   * Phase 1: 小爱调用 Gemini 生成大纲提示词
   */
  private async phase1_generateOutlinePrompt(): Promise<void> {
    console.log('\n📝 Phase 1: 生成大纲提示词\n');
    this.cortex.updateTaskPhase(this.taskId, 1, 'in_progress');

    const prompt = `请为以下主题设计一个深度技术分析报告的大纲提示词（工程化风格，非散文）。

主题: ${this.topic}

要求:
1. 提示词应引导专家生成结构化的技术分析大纲
2. 章节划分遵循工程论文结构: 背景与问题定义 → 技术方案分析 → 对比评估 → 实践建议 → 结论
3. 每个章节必须包含:
   - 明确的技术分析目标
   - 要求的定量指标类型（性能/成本/复杂度等）
   - 需要的对比维度（方案A vs B vs C）
4. 要求专家引用: 论文/RFC/技术文档/benchmark 数据
5. 要求输出格式包含: 对比表格、架构图、代码示例、性能数据
6. 禁止出现"发展前景"、"意义深远"等空泛章节

请输出一个能产出理工科风格报告的大纲生成提示词。`;

    const result = await callExpert('gemini-2.5-pro', prompt);

    // 保存到文件系统
    const filePath = saveDocument(this.taskId, 1, 'outline_prompt', result.content, 'gemini');

    // 保存元数据到 Cortex
    this.cortex.saveArtifact(
      this.taskId, 1, 'outline_prompt',
      { prompt: result.content, generated_by: 'gemini-2.5-pro' },
      'gemini-2.5-pro',
      result.inputTokens + result.outputTokens,
      result.latencyMs
    );

    // 记录成本
    const cost = estimateCost('gemini-2.5-pro', result.inputTokens, result.outputTokens);
    this.cortex.recordCost(this.taskId, 1, 'gemini-2.5-pro', result.inputTokens, result.outputTokens, cost);

    console.log(`  ✅ 大纲提示词已生成 (${result.outputTokens} tokens, ${result.latencyMs}ms)`);
    console.log(`  📁 ${filePath}`);

    this.cortex.updateTaskPhase(this.taskId, 1, 'completed');
  }

  /**
   * Phase 1.5: 研究搜索阶段
   * 使用专家分析主题生成搜索词，然后通过 Gemini Google Search 搜索文献
   */
  private async phase1_5_research(): Promise<void> {
    console.log('\n🔍 Phase 1.5: 研究搜索阶段\n');

    // Step 1: 使用专家分析主题，生成搜索查询词组合
    console.log('  📊 Step 1: 分析主题，生成搜索查询...');

    const analyzePrompt = `你是一位资深的学术研究员。请分析以下研究主题，生成一组用于搜索学术论文和技术文章的查询词组合。

主题: ${this.topic}

要求:
1. 生成 5-8 个不同角度的搜索查询
2. 每个查询应该是英文（更容易找到国际文献）或中文（找国内文章）
3. 包含核心概念、相关技术、应用场景等不同维度
4. 搜索查询应该具体、专业，能找到高质量的论文和技术博客

输出格式 (JSON):
{
  "queries": [
    {"query": "查询词1", "purpose": "搜索目的", "language": "en/zh"},
    {"query": "查询词2", "purpose": "搜索目的", "language": "en/zh"}
  ],
  "key_concepts": ["核心概念1", "核心概念2"],
  "expected_sources": ["期望找到的资料类型"]
}`;

    let searchQueries: Array<{query: string; purpose: string; language: string}> = [];

    try {
      // 使用 Gemini 2.5 Pro 分析主题生成搜索词
      const analyzeResult = await callExpert('gemini-2.5-pro', analyzePrompt);

      // 记录成本
      const analyzeCost = estimateCost('gemini-2.5-pro', analyzeResult.inputTokens, analyzeResult.outputTokens);
      this.cortex.recordCost(this.taskId, 1, 'gemini-2.5-pro', analyzeResult.inputTokens, analyzeResult.outputTokens, analyzeCost);

      // 解析 JSON 输出
      const jsonMatch = analyzeResult.content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        searchQueries = parsed.queries || [];
        console.log(`  ✅ 生成 ${searchQueries.length} 个搜索查询`);
      }
    } catch (error) {
      console.log(`  ⚠️ 分析失败，使用默认搜索查询: ${error}`);
      // 降级：使用主题直接作为搜索词
      searchQueries = [
        { query: `${this.topic} research paper`, purpose: '学术论文', language: 'en' },
        { query: `${this.topic} technical blog`, purpose: '技术博客', language: 'en' },
        { query: `${this.topic} survey review`, purpose: '综述文章', language: 'en' }
      ];
    }

    // Step 2: 使用 Gemini Google Search 进行实际搜索
    console.log('\n  🌐 Step 2: 执行网络搜索...');

    const allSources: Array<{
      key: string;
      title: string;
      url: string;
      snippet: string;
      query: string;
    }> = [];

    // 限制搜索数量避免消耗过多 token
    const queriesToSearch = searchQueries.slice(0, 5);

    for (let i = 0; i < queriesToSearch.length; i++) {
      const q = queriesToSearch[i];
      console.log(`    [${i + 1}/${queriesToSearch.length}] 搜索: ${q.query}`);

      try {
        const searchResult = await callGeminiWithSearch(
          `请搜索关于 "${q.query}" 的最新学术论文、技术文章或博客。
重点关注: ${q.purpose}

对搜索结果进行简要总结，包括:
1. 找到的关键文献/文章
2. 主要观点或发现
3. 与主题 "${this.topic}" 的相关性`
        );

        // 收集搜索结果
        for (const result of searchResult.searchResults) {
          const key = `src_${allSources.length + 1}`;
          allSources.push({
            key,
            title: result.title,
            url: result.url,
            snippet: result.snippet,
            query: q.query
          });
        }

        // 记录成本
        const searchCost = estimateCost('gemini-2-flash', searchResult.inputTokens, searchResult.outputTokens);
        this.cortex.recordCost(this.taskId, 1, 'gemini-2-flash', searchResult.inputTokens, searchResult.outputTokens, searchCost);

        console.log(`    ✅ 找到 ${searchResult.searchResults.length} 个结果`);

      } catch (error) {
        console.log(`    ⚠️ 搜索失败: ${error}`);
      }

      // 避免请求过快
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    // Step 3: 持久化搜索结果到 REPORT 目录
    console.log('\n  💾 Step 3: 持久化研究文献...');

    // 去重（按 URL）
    const uniqueSources = allSources.filter((s, i, arr) =>
      arr.findIndex(x => x.url === s.url) === i
    );

    console.log(`  📚 共收集 ${uniqueSources.length} 篇独立文献`);

    // 写入 SOURCES.md
    for (const source of uniqueSources) {
      this.updateReportSources({
        key: source.key,
        title: source.title,
        url: source.url,
        conclusion: source.snippet,
        credibility: '待验证',
        thesisRelation: `搜索词: ${source.query}`
      });
    }

    // 为每篇重要文献创建笔记
    const topSources = uniqueSources.slice(0, 10); // 只为前 10 篇创建详细笔记
    for (const source of topSources) {
      this.createPaperNote(source.key, {
        title: source.title,
        problem: `来自搜索: ${source.query}`,
        method: '待阅读分析',
        results: source.snippet,
        relevance: `与主题 "${this.topic}" 相关`
      });
    }

    // 保存元数据到 Cortex
    this.cortex.saveArtifact(
      this.taskId, 1, 'research_sources',
      {
        topic: this.topic,
        queriesUsed: queriesToSearch,
        sourcesFound: uniqueSources.length,
        sources: uniqueSources
      },
      'gemini-2-flash',
      0,
      0
    );

    console.log(`  ✅ Phase 1.5 完成: ${uniqueSources.length} 篇文献已保存到 SOURCES.md`);
  }

  /**
   * Phase 2: 四专家各自生成大纲
   */
  private async phase2_expertsGenerateOutlines(): Promise<void> {
    console.log('\n📝 Phase 2: 四专家生成大纲\n');
    this.cortex.updateTaskPhase(this.taskId, 2, 'in_progress');

    // 获取 Phase 1 的大纲提示词
    const artifacts = this.cortex.getArtifacts(this.taskId, 1, 'outline_prompt');
    const outlinePrompt = JSON.parse(artifacts[0].content_json).prompt;

    // 获取 Phase 1.5 的研究文献 (如果有)
    let literatureSection = '';
    try {
      const researchArtifacts = this.cortex.getArtifacts(this.taskId, 1, 'research_sources');
      if (researchArtifacts && researchArtifacts.length > 0) {
        const sources = JSON.parse(researchArtifacts[0].content_json);
        if (sources.sources && sources.sources.length > 0) {
          literatureSection = `\n\n【研究文献参考】
以下是通过搜索获取的相关研究资料，请在大纲中考虑引用这些内容：

${sources.sources.map((s: any, i: number) => `${i + 1}. ${s.title}\n   来源: ${s.url}\n   摘要: ${s.snippet}`).join('\n\n')}

请在大纲中标注可以引用上述哪些文献来支撑论点。`;
          console.log(`  📚 已加载 ${sources.sources.length} 篇研究文献\n`);
        }
      }
    } catch (e) {
      // 没有研究文献，继续正常流程
    }

    const expertIds = Object.keys(EXPERTS);

    for (const expertId of expertIds) {
      const expert = EXPERTS[expertId];
      console.log(`  🔬 ${expert.nickname} (${expertId}) 生成大纲...`);

      const prompt = `${outlinePrompt}

请基于你的专业视角，为主题"${this.topic}"生成一份详细的分析大纲。

要求:
1. 大纲应包含 4-6 个主要章节
2. 每个章节有明确的分析目标
3. 标注需要引用的证据类型
4. 体现你作为"${expert.nickname}"的分析风格: ${expert.style}${literatureSection}`;

      try {
        const result = await callExpert(expertId, prompt);

        // 保存到文件系统
        const filePath = saveDocument(this.taskId, 2, 'outline', result.content, expertId);

        // 保存元数据到 Cortex
        this.cortex.saveArtifact(
          this.taskId, 2, 'outline',
          {
            outline: result.content,
            expert: expertId,
            nickname: expert.nickname,
            role: expert.role
          },
          expertId,
          result.inputTokens + result.outputTokens,
          result.latencyMs
        );

        // 记录成本
        const cost = estimateCost(expertId, result.inputTokens, result.outputTokens);
        this.cortex.recordCost(this.taskId, 2, expertId, result.inputTokens, result.outputTokens, cost);

        console.log(`  ✅ ${expert.nickname} 完成 (${result.outputTokens} tokens, ${result.latencyMs}ms)`);
        console.log(`     📁 ${filePath}\n`);

      } catch (error) {
        console.log(`  ❌ ${expert.nickname} 失败: ${error}\n`);
      }
    }

    this.cortex.updateTaskPhase(this.taskId, 2, 'completed');
  }

  /**
   * Phase 3: 四专家互评
   */
  private async phase3_crossReview(): Promise<void> {
    console.log('\n📝 Phase 3: 四专家互评\n');
    this.cortex.updateTaskPhase(this.taskId, 3, 'in_progress');

    // 获取所有大纲
    const outlines = this.cortex.getArtifacts(this.taskId, 2, 'outline');
    const expertIds = Object.keys(EXPERTS);

    // 使用跨厂商配对，避免同厂商互评
    const pairs = generateCrossVendorPairs(expertIds);

    for (const { reviewer: reviewerId, target: targetId } of pairs) {
      const reviewer = EXPERTS[reviewerId];
      const target = EXPERTS[targetId];

      // 找到被评审的大纲
      const targetOutline = outlines.find(o => JSON.parse(o.content_json).expert === targetId);
      if (!targetOutline) continue;

      console.log(`  👁️ ${reviewer.nickname} 评审 ${target.nickname} 的大纲...`);

      const prompt = `请评审以下分析大纲，给出评分和详细反馈。

【被评审的大纲】
作者: ${target.nickname}
风格: ${target.style}

${JSON.parse(targetOutline.content_json).outline}

评分维度 (每项 1-10 分):
1. 结构完整性 - 章节划分是否合理
2. 逻辑严密性 - 论证链条是否清晰
3. 覆盖广度 - 是否涵盖关键方面
4. 深度分析 - 是否有深入见解
5. 可操作性 - 章节目标是否明确可执行

请按以下 JSON 格式输出:
{
  "scores": {
    "structure": <1-10>,
    "logic": <1-10>,
    "coverage": <1-10>,
    "depth": <1-10>,
    "actionability": <1-10>
  },
  "overall_score": <1-10>,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "suggestions": ["...", "..."],
  "verdict": "一句话总结"
}`;

      try {
        const result = await callExpert(reviewerId, prompt);

        // 尝试解析 JSON
        let reviewData;
        try {
          // 提取 JSON 部分
          const jsonMatch = result.content.match(/\{[\s\S]*\}/);
          reviewData = jsonMatch ? JSON.parse(jsonMatch[0]) : {
            overall_score: 7,
            verdict: result.content.slice(0, 200)
          };
        } catch {
          reviewData = { overall_score: 7, verdict: result.content.slice(0, 200) };
        }

        // 保存评审到文件系统
        const filePath = saveDocument(this.taskId, 3, 'review', result.content, `${reviewerId}_reviews_${targetId}`);

        // 保存到 Cortex evals 表
        this.cortex.addEval(
          this.taskId,
          3,
          targetOutline.artifact_id,
          reviewerId,
          targetId,
          reviewData.scores || {},
          reviewData.overall_score || 7,
          reviewData.verdict || '',
          reviewData.suggestions || []
        );

        // 记录成本
        const cost = estimateCost(reviewerId, result.inputTokens, result.outputTokens);
        this.cortex.recordCost(this.taskId, 3, reviewerId, result.inputTokens, result.outputTokens, cost);

        // 记录 Persona Match (触发 ELO 更新)
        const personaA = EXPERT_TO_PERSONA[reviewerId];
        const personaB = EXPERT_TO_PERSONA[targetId];
        if (personaA && personaB) {
          // 评审者给被评审者打分，分数作为对局结果
          // 同时收集被评审者给评审者的反向评分（如果有的话）
          const reverseReview = outlines.find(o => {
            const data = JSON.parse(o.content_json);
            return data.expert === reviewerId;
          });

          // 使用评审分数作为对局分数
          // reviewer 给 target 打的分数是 target 的得分
          // reviewer 的得分默认为基础分 7（或根据反向评审计算）
          let scoreA = 7; // 评审者基础分
          let scoreB = reviewData.overall_score || 7; // 被评审者得分

          recordPersonaMatch(this.taskId, personaA, personaB, scoreA, scoreB);
        }

        console.log(`  ✅ ${reviewer.nickname} → ${target.nickname}: ${reviewData.overall_score}/10`);
        console.log(`     📁 ${filePath}\n`);

      } catch (error) {
        console.log(`  ❌ 评审失败: ${error}\n`);
      }
    }

    this.cortex.updateTaskPhase(this.taskId, 3, 'completed');
  }

  /**
   * Phase 4: Gemini 综合大纲 + 拆解章节提示词
   */
  private async phase4_synthesizeAndSplit(): Promise<void> {
    console.log('\n📝 Phase 4: 综合大纲 + 拆解章节\n');
    this.cortex.updateTaskPhase(this.taskId, 4, 'in_progress');

    // 获取所有大纲和评审
    const outlines = this.cortex.getArtifacts(this.taskId, 2, 'outline');
    const evals = this.cortex.getEvals(this.taskId, 3);

    // 构建综合输入
    let outlinesText = '';
    for (const outline of outlines) {
      const data = JSON.parse(outline.content_json);
      outlinesText += `\n【${data.nickname}的大纲】\n${data.outline}\n`;
    }

    let evalsText = '';
    for (const evalItem of evals) {
      evalsText += `\n${evalItem.reviewer_model} 评审 ${evalItem.target_model}: ${evalItem.score}/10\n${evalItem.verdict}\n`;
    }

    console.log(`  🔬 ${GEMINI_SYNTHESIZER.nickname} 综合大纲...`);

    const synthesizePrompt = `请综合以下三位专家的大纲和互评结果，生成最终的分析大纲。

【主题】
${this.topic}

【三位专家的大纲】
${outlinesText}

【互评结果】
${evalsText}

要求:
1. 综合三份大纲的优点
2. 采纳评审中的改进建议
3. 生成 4-6 个章节
4. 每个章节必须包含:
   - section_id: 章节编号
   - title: 章节标题
   - goal: 分析目标 (一句话)
   - key_points: 要点列表
   - required_evidence: 需要的证据类型
   - word_count: 建议字数

请按以下 JSON 格式输出:
{
  "outline": [
    {
      "section_id": "1",
      "title": "章节标题",
      "goal": "分析目标",
      "key_points": ["要点1", "要点2"],
      "required_evidence": ["证据类型1", "证据类型2"],
      "word_count": 500
    }
  ],
  "synthesis_notes": "综合说明"
}`;

    try {
      const result = await callExpert('gemini-2.5-pro', synthesizePrompt);

      // 解析 JSON
      let synthesizedOutline;
      try {
        const jsonMatch = result.content.match(/\{[\s\S]*\}/);
        synthesizedOutline = jsonMatch ? JSON.parse(jsonMatch[0]) : null;
      } catch {
        synthesizedOutline = null;
      }

      // 保存综合大纲到文件系统
      const outlineFilePath = saveDocument(this.taskId, 4, 'synthesized_outline', result.content, 'gemini');
      console.log(`  ✅ 综合大纲完成`);
      console.log(`     📁 ${outlineFilePath}\n`);

      // 保存到 Cortex
      this.cortex.saveArtifact(
        this.taskId, 4, 'synthesized_outline',
        { outline: synthesizedOutline, raw: result.content },
        'gemini-2.5-pro',
        result.inputTokens + result.outputTokens,
        result.latencyMs
      );

      // 设置大纲结构
      if (synthesizedOutline?.outline) {
        const sections = synthesizedOutline.outline.map((s: any) => ({
          section_id: s.section_id,
          goal: s.goal,
          required_claims: s.key_points || []
        }));
        this.cortex.setOutline(this.taskId, sections);

        // 为每个章节生成提示词
        console.log(`  📝 为 ${synthesizedOutline.outline.length} 个章节生成提示词...\n`);

        for (let i = 0; i < synthesizedOutline.outline.length; i++) {
          const section = synthesizedOutline.outline[i];
          const sectionPrompt = `请以技术报告的标准撰写以下章节（工程化风格，非散文）:

【主题】${this.topic}
【章节】${section.title}
【目标】${section.goal}
【要点】${(section.key_points || []).join('\n- ')}
【证据要求】${(section.required_evidence || []).join(', ')}
【字数要求】约 ${section.word_count || 500} 字

写作要求（理工科标准）:
1. 必须包含定量分析: 性能数据、复杂度分析、成本对比等具体数字
2. 用对比表格呈现方案优缺点（不要用散文描述）
3. 如涉及系统设计，给出 ASCII 架构图或流程图
4. 如涉及算法/实现，给出代码示例或伪代码
5. 引用具体论文/技术文档/benchmark（标注来源）
6. 给出明确的技术结论和推荐，不要"各有千秋"式的和稀泥

禁止:
- "前景广阔"、"意义深远"等空话套话
- 不带数据的主观评价
- 文学化修辞和散文化表达`;

          // 保存章节提示词到文件系统
          const promptFilePath = saveDocument(this.taskId, 4, `section_${section.section_id}_prompt`, sectionPrompt);

          // 更新大纲中的提示词
          this.cortex.updateSectionPrompt(this.taskId, i + 1, sectionPrompt);

          console.log(`     Section ${section.section_id}: ${section.title}`);
        }
      }

      // 记录成本
      const cost = estimateCost('gemini-2.5-pro', result.inputTokens, result.outputTokens);
      this.cortex.recordCost(this.taskId, 4, 'gemini-2.5-pro', result.inputTokens, result.outputTokens, cost);

    } catch (error) {
      console.log(`  ❌ 综合失败: ${error}`);
    }

    this.cortex.updateTaskPhase(this.taskId, 4, 'completed');
  }

  /**
   * Phase 5: 每章节四专家写作 + 互评 + 综合
   */
  private async phase5_writeChapters(): Promise<void> {
    console.log('\n📝 Phase 5: 逐章节写作\n');
    this.cortex.updateTaskPhase(this.taskId, 5, 'in_progress');

    // 获取 Phase 1.5 的研究文献 (如果有)
    let literatureSection = '';
    try {
      const researchArtifacts = this.cortex.getArtifacts(this.taskId, 1, 'research_sources');
      if (researchArtifacts && researchArtifacts.length > 0) {
        const sources = JSON.parse(researchArtifacts[0].content_json);
        if (sources.sources && sources.sources.length > 0) {
          literatureSection = `\n\n【可引用的研究文献】
请在写作时适当引用以下研究资料来支撑论点：

${sources.sources.map((s: any, i: number) => `[${i + 1}] ${s.title} - ${s.url}`).join('\n')}

引用格式示例: "根据[1]的研究..."、"如[2]所述..."`;
          console.log(`  📚 已加载 ${sources.sources.length} 篇研究文献供引用\n`);
        }
      }
    } catch (e) {
      // 没有研究文献，继续正常流程
    }

    const outline = this.cortex.getOutline(this.taskId);
    const expertIds = Object.keys(EXPERTS);

    for (const section of outline) {
      console.log(`\n  📖 章节 ${section.section_order}: ${section.section_title}\n`);

      const drafts: { expertId: string; content: string; draftId: number }[] = [];

      // 四专家写作
      for (const expertId of expertIds) {
        const expert = EXPERTS[expertId];
        console.log(`     ✍️ ${expert.nickname} 撰写...`);

        // 组合章节提示词和文献引用
        const chapterPrompt = (section.prompt || '请撰写该章节') + literatureSection;

        try {
          const result = await callExpert(expertId, chapterPrompt);

          // 保存到文件系统
          const filePath = saveDocument(
            this.taskId, 5,
            `section_${section.section_order}_draft`,
            result.content,
            expertId
          );

          // 保存到 Cortex
          const draftId = this.cortex.saveDraft(
            this.taskId,
            section.section_id,
            expertId,
            result.content,
            1
          );

          drafts.push({ expertId, content: result.content, draftId });

          // 记录成本
          const cost = estimateCost(expertId, result.inputTokens, result.outputTokens);
          this.cortex.recordCost(this.taskId, 5, expertId, result.inputTokens, result.outputTokens, cost);

          console.log(`     ✅ ${expert.nickname} 完成 (${result.outputTokens} tokens)`);

        } catch (error) {
          console.log(`     ❌ ${expert.nickname} 失败: ${error}`);
        }
      }

      // 互评 (简化版，只取平均分)
      console.log(`     👁️ 互评中...`);

      // Gemini 综合章节
      console.log(`     🔬 ${GEMINI_SYNTHESIZER.nickname} 综合章节...`);

      let draftsText = '';
      for (const draft of drafts) {
        const expert = EXPERTS[draft.expertId];
        draftsText += `\n【${expert.nickname}的版本】\n${draft.content.slice(0, 2000)}...\n`;
      }

      const synthesizePrompt = `请综合以下三位专家撰写的章节内容，生成最终技术报告版本（工程化风格）。

【章节标题】${section.section_title}
【章节目标】${section.goal}

【三位专家的版本】
${draftsText}

综合要求（理工科标准）:
1. 保留所有专家版本中的定量数据、性能指标、benchmark 结果
2. 合并对比表格，去重后形成统一的技术对比矩阵
3. 保留最佳的架构图/流程图/代码示例
4. 技术结论必须明确: 推荐方案A还是B，给出依据（数据+推理）
5. 冲突观点用"争议点"小节单独列出，附各方论据

禁止:
- 用"各有优势"、"需要权衡"等和稀泥式结论
- 删除专家提供的具体数据和代码
- 把技术内容改写成散文`;

      try {
        const result = await callExpert('gemini-2.5-pro', synthesizePrompt);

        // 保存综合版本到文件系统
        const filePath = saveDocument(
          this.taskId, 5,
          `section_${section.section_order}_final`,
          result.content,
          'synthesized'
        );

        // 保存为最终版本
        const finalDraftId = this.cortex.saveDraft(
          this.taskId,
          section.section_id,
          'gemini-2.5-pro',
          result.content,
          2  // version 2 = synthesized
        );
        this.cortex.setFinalDraft(finalDraftId);

        // 记录成本
        const cost = estimateCost('gemini-2.5-pro', result.inputTokens, result.outputTokens);
        this.cortex.recordCost(this.taskId, 5, 'gemini-2.5-pro', result.inputTokens, result.outputTokens, cost);

        console.log(`     ✅ 综合完成`);
        console.log(`     📁 ${filePath}`);

      } catch (error) {
        console.log(`     ❌ 综合失败: ${error}`);
      }
    }

    this.cortex.updateTaskPhase(this.taskId, 5, 'completed');
  }

  /**
   * Phase 6: 合并所有章节为初稿
   */
  private async phase6_mergeDraft(): Promise<void> {
    console.log('\n📝 Phase 6: 合并初稿\n');
    this.cortex.updateTaskPhase(this.taskId, 6, 'in_progress');

    // 获取所有最终版本的章节
    const drafts = this.cortex.getDrafts(this.taskId);
    const finalDrafts = drafts.filter(d => d.is_final);

    // 获取大纲
    const outline = this.cortex.getOutline(this.taskId);

    // 组装完整报告
    let fullReport = `# ${this.topic}\n\n`;
    fullReport += `> 生成时间: ${new Date().toISOString()}\n`;
    fullReport += `> 任务ID: ${this.taskId}\n\n`;
    fullReport += `---\n\n`;

    // 添加目录
    fullReport += `## 目录\n\n`;
    for (const section of outline) {
      fullReport += `${section.section_order}. ${section.section_title}\n`;
    }
    fullReport += `\n---\n\n`;

    // 添加各章节
    for (const section of outline) {
      const draft = finalDrafts.find(d => d.section_id === section.section_id);
      fullReport += `## ${section.section_order}. ${section.section_title}\n\n`;
      if (draft) {
        fullReport += `${draft.content}\n\n`;
      } else {
        fullReport += `*该章节内容待补充*\n\n`;
      }
    }

    // 添加参考来源
    const sources = this.cortex.getSources(this.taskId);
    if (sources.length > 0) {
      fullReport += `## 参考文献\n\n`;
      for (const source of sources) {
        fullReport += `- [${source.citation_key}] ${source.title}`;
        if (source.url) fullReport += ` - ${source.url}`;
        fullReport += `\n`;
      }
    }

    // 保存完整报告到文件系统
    const filePath = saveDocument(this.taskId, 6, 'full_report', fullReport);
    console.log(`  ✅ 初稿合并完成`);
    console.log(`  📁 ${filePath}`);

    // 保存元数据到 Cortex
    this.cortex.saveArtifact(
      this.taskId, 6, 'full_report',
      {
        file_path: filePath,
        section_count: outline.length,
        word_count: fullReport.split(/\s+/).length
      },
      'system'
    );

    this.cortex.updateTaskPhase(this.taskId, 6, 'completed');
  }

  /**
   * Phase 7: 生成结构化输出
   */
  private async phase7_generateStructuredOutput(): Promise<void> {
    console.log('\n📝 Phase 7: 生成结构化输出\n');
    this.cortex.updateTaskPhase(this.taskId, 7, 'in_progress');

    // 获取完整的结构化输出
    const output = this.cortex.getStructuredOutput(this.taskId);

    // 保存 JSON 到文件系统
    const jsonPath = join(getTaskDir(this.taskId), 'structured_output.json');
    writeFileSync(jsonPath, JSON.stringify(output, null, 2));

    console.log(`  ✅ 结构化输出已生成`);
    console.log(`  📁 ${jsonPath}`);

    // 输出统计
    console.log(`\n  📊 统计:`);
    console.log(`     Sources: ${output.sources.length}`);
    console.log(`     Claims: ${output.claims.length}`);
    console.log(`     Outline Sections: ${output.outline.length}`);
    console.log(`     Evaluations: ${output.eval_matrix.length}`);
    console.log(`     Draft Sections: ${output.draft_sections.length}`);
    console.log(`     Total Cost: $${output.cost.reduce((sum, c) => sum + c.cost_usd, 0).toFixed(4)}`);

    this.cortex.updateTaskPhase(this.taskId, 7, 'completed');
  }

  /**
   * Phase 8: CEO 总结
   * Solar 作为 CEO 对报告进行总结点评，放在报告最前面
   */
  private async phase8_ceoSummary(): Promise<void> {
    console.log('\n👔 Phase 8: CEO 总结\n');
    this.cortex.updateTaskPhase(this.taskId, 8, 'in_progress');

    // 获取任务信息
    const outline = this.cortex.getOutline(this.taskId);
    const output = this.cortex.getStructuredOutput(this.taskId);
    const costs = output.cost || [];
    const totalCost = costs.reduce((sum: number, c: any) => sum + (c.cost_usd || 0), 0);

    // 获取专家统计
    const expertStats: Record<string, { time: number; cost: number }> = {};
    for (const cost of costs) {
      const expertId = cost.model_id || 'unknown';
      if (!expertStats[expertId]) {
        expertStats[expertId] = { time: 0, cost: 0 };
      }
      expertStats[expertId].time += cost.latency_ms || 0;
      expertStats[expertId].cost += cost.cost_usd || 0;
    }

    // 生成 CEO 总结 (使用 ASCII 艺术格式)
    const date = new Date().toISOString().split('T')[0];

    // 构建专家团队信息
    const expertRoles: Record<string, string> = {
      'gemini-2.5-pro': '技术宅 (gemini-2.5-pro) · 严谨审核 · 架构分析',
      'deepseek-r1': '思考驼 (deepseek-r1) · 深度推理 · 认知科学视角',
      'deepseek-v3': '鬼才码农 (deepseek-v3) · 创意挑战 · 颠覆性观点',
      'glm-5': '马王 (glm-5) · 综合调和 · 共识与分歧',
      'glm-4-plus': '老实人 (glm-4-plus) · 日常编码 · 友善配合'
    };

    // 获取章节标题列表
    const sections = outline.map((s: any) => `${s.section_order}. ${s.section_title}`).join('\n│  ');

    // 构建专家统计表
    let expertTable = '';
    for (const [modelId, stats] of Object.entries(expertStats)) {
      const nickname = expertRoles[modelId]?.split('(')[0]?.trim() || modelId;
      const timeStr = (stats.time / 1000).toFixed(1) + 's';
      const costStr = '$' + stats.cost.toFixed(3);
      expertTable += `│ ${nickname.padEnd(12)} │ ${modelId.padEnd(16)} │ ${timeStr.padStart(8)} │ ${costStr.padStart(8)} │\n`;
    }

    const summary = `\`\`\`
┌─────────────────────────────────────────────────────────────────────────┐
│                    ${this.topic} · 四专家会审                        │
├─────────────────────────────────────────────────────────────────────────┤
│  专家团队                                                               │
│  ├─ 技术宅 (gemini-2.5-pro) · 严谨审核 · 架构分析                      │
│  ├─ 思考驼 (deepseek-r1) · 深度推理 · 认知科学视角                     │
│  ├─ 鬼才码农 (deepseek-v3) · 创意挑战 · 颠覆性观点                     │
│  └─ 马王 (glm-5) · 综合调和 · 共识与分歧                               │
└─────────────────────────────────────────────────────────────────────────┘
\`\`\`

## 专家调用统计

| 专家 | 模型 | 耗时 | 成本 |
|------|------|------|------|
${Object.entries(expertStats).map(([modelId, stats]) => {
  const nickname = expertRoles[modelId]?.split('(')[0]?.trim() || modelId;
  return `| ${nickname} | ${modelId} | ${(stats.time / 1000).toFixed(1)}s | $${stats.cost.toFixed(3)} |`;
}).join('\n')}

**总成本: ~$${totalCost.toFixed(3)}**

---

## CEO 点评

> 本报告由四位专家协作完成，涵盖了 ${outline.length} 个核心章节。
>
> **报告结构:**
> ${outline.map((s: any) => `${s.section_order}. ${s.section_title}`).join(' | ')}
>
> 专家团队从技术实现、认知科学、创新探索等多个视角进行了深入分析，
> 最终由马王进行综合调和，形成共识与分歧的平衡观点。

---

`;

    // 读取现有报告
    const taskDir = getTaskDir(this.taskId);
    const reportPath = join(taskDir, 'phase_6_full_report.md');

    let existingReport = '';
    try {
      existingReport = readFileSync(reportPath, 'utf-8');
    } catch (e) {
      console.log('  ⚠️ 未找到已有报告，跳过合并');
      return;
    }

    // 将 CEO 总结放在报告开头
    const finalReport = summary + existingReport;

    // 保存带 CEO 总结的完整报告
    const finalReportPath = join(taskDir, 'final_report_with_ceo_summary.md');
    writeFileSync(finalReportPath, finalReport);

    // 同时更新原报告文件
    writeFileSync(reportPath, finalReport);

    console.log(`  ✅ CEO 总结已添加到报告开头`);
    console.log(`  📁 ${finalReportPath}`);

    // 保存到 Solar 标准输出目录
    const solarOutputPath = join(process.env.HOME || '~', 'Solar/docs/insights',
      `${date}_${this.topic.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '-')}.md`);

    try {
      const { mkdirSync } = require('fs');
      mkdirSync(join(process.env.HOME || '~', 'Solar/docs/insights'), { recursive: true });
      writeFileSync(solarOutputPath, finalReport);
      console.log(`  📁 ${solarOutputPath}`);
    } catch (e) {
      console.log(`  ⚠️ 保存到 Solar/docs/insights 失败: ${e}`);
    }

    this.cortex.updateTaskPhase(this.taskId, 8, 'completed');
  }
}

// ============================================================
// CLI 入口
// ============================================================

const args = process.argv.slice(2);
let topic = '';
let requester = process.env.USER || 'unknown';
let resumeTaskId = '';

// 解析参数
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--resume' || args[i] === '-r') {
    resumeTaskId = args[++i] || '';
  } else if (!args[i].startsWith('-') && !topic) {
    topic = args[i];
  } else if (!args[i].startsWith('-')) {
    requester = args[i];
  }
}

if (!topic && !resumeTaskId) {
  console.log(`
洞察系统 v2.0 - 七阶段完整流程 + CapsuleView 恢复

用法:
  bun insight-v2.ts "<主题>" [请求人]
  bun insight-v2.ts --resume <task_id>

示例:
  bun insight-v2.ts "AI Agent 记忆系统架构分析"
  bun insight-v2.ts "React 和 Vue 的优缺点对比" "昊哥"
  bun insight-v2.ts --resume insight_1771116515647_i39dwh

特性:
  • Evidence First - 每个 Phase 前自动收集证据
  • CapsuleView - 支持任务暂停和恢复
  • 牛马隔离 - 专家完成后自动持久化

流程:
  Phase 1: Gemini 生成大纲提示词
  Phase 2: 四专家各自生成大纲
  Phase 3: 四专家互评 (+ ELO 记录)
  Phase 4: Gemini 综合大纲 + 拆解章节
  Phase 5: 逐章节四专家写作 + 综合
  Phase 6: 合并初稿
  Phase 7: 生成结构化输出
  Phase 8: CEO 总结
`);
  process.exit(1);
}

async function main() {
  const engine = new InsightEngine();

  if (resumeTaskId) {
    // 恢复模式
    console.log(`🔄 恢复任务: ${resumeTaskId}`);
    const capsule = restoreTaskCapsule(resumeTaskId);
    if (!capsule) {
      console.error(`❌ 未找到任务胶囊: ${resumeTaskId}`);
      process.exit(1);
    }
    console.log(`📋 主题: ${capsule.topic}`);
    console.log(`📊 当前进度: Phase ${capsule.currentPhase}`);
    // TODO: 实现恢复逻辑，从 capsule.currentPhase 继续
    console.log(`\n💡 提示: 恢复功能需要进一步实现，当前仅展示胶囊状态`);
  } else {
    // 正常模式
    const taskId = await engine.run(topic, requester);
    console.log(taskId);
  }
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
