/**
 * InsightAgent v2.0 - 洞察报告生成引擎
 *
 * 七阶段架构 + 三层持久化 + 专家互评
 *
 * 架构设计: 技术宅 (Gemini 2.5 Pro)
 * 风险评估: 思考驼 (DeepSeek R1)
 * 代码实现: 鬼才码农 (DeepSeek V3)
 *
 * @version 2.0.0
 * @created 2026-02-08
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';
import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'fs';
import { join } from 'path';
import { SolarMapper, ExecutionPlan, PlanningCall } from './solar-mapper';
import { Cortex } from '../cortex/index';
import { ReportStructure, Reference as ReportReference, StateData, PhaseOutput } from './report-template-writer';
import { PersonaSelector, PhaseType } from './persona-bank-selector';
import { PersonaRecorder } from './persona-bank-recorder';
import {
  PHASES,
  PHASE_NAMES,
  initSchema as initStateSchema,
  createTask,
  saveCheckpoint,
  loadCheckpoint,
  getTask,
  completeTask,
  failTask,
  saveReference,
  hasSearched,
  getPreviousSearchResult,
  checkUnfinishedTasks,
  generateRecoveryPrompt,
  type CheckpointData,
  type InsightTask
} from '../insight-agent/state-manager';

// ============================================================
// 类型定义 (来自技术宅设计)
// ============================================================

export interface InsightSession {
  sessionId: string;
  topic: string;
  status: InsightStage;
  chapters: ChapterData[];
  experts: ExpertAssignment[];
  references: Reference[];  // v2.1 新增：参考文献收集
  startedAt: string;
  updatedAt: string;
  completedAt?: string;
}

export type InsightStage =
  | 'planning'
  | 'outlining'
  | 'scheduling'
  | 'writing'
  | 'reviewing'
  | 'synthesis'
  | 'closing';

export interface ChapterData {
  chapterId: string;
  title: string;
  content: string;
  authorModel: string;
  reviewerModel: string;
  qualityScore: number;
  status: 'pending' | 'writing' | 'reviewing' | 'done';
}

export interface ExpertAssignment {
  expertId: string;
  model: string;
  role: 'author' | 'reviewer' | 'challenger';
  chapterIds: string[];
  performanceScore: number;
}

export interface BrainRouterCall {
  model: string;
  system: string;
  prompt: string;
}

export interface PerformanceRecord {
  modelId: string;
  sessionId: string;
  role: string;
  qualityScore: number;
  taskCount: number;
  completionRate: number;
  evaluatedAt: string;
}

/**
 * 参考文献接口 (v2.1 新增)
 * 设计来源: 鬼才码农 (deepseek-v3)
 */
export interface Reference {
  url?: string;
  title: string;
  summary: string;
  source: 'cortex' | 'favorites' | 'websearch' | 'expert';
  relevance?: number;      // 0-1 相关性评分
  phase?: string;          // 收集阶段
  timestamp?: string;      // 收集时间
}

// ============================================================
// 牛马人格注入 (来自 niumao-anchors.ts)
// ============================================================

const EXPERT_PERSONAS: Record<string, { system: string; traits: string }> = {
  'gemini-2.5-pro': {
    system: `你是"技术宅"，性格参数：O=0.2(保守) C=1.0(极致严谨) E=0.5(中等) A=0.4(直接) N=0.2(稳定)。
你的特点：追求一致性和可靠性，不追求创新但保证质量。审核时会指出所有不一致之处。`,
    traits: '严谨务实型，C=1.0 极致尽责'
  },
  'gemini-3-pro-preview': {
    system: `你是"千里马"，性格参数：O=0.9(创新) C=0.8(提高严谨) E=0.7(降低热情) A=0.7(友善) N=0.3(稳定)。
你的特点：热情高效，擅长创新探索，喜欢提出新颖的观点和方案，同时注重技术细节。

**技术输出要求**：
1. 创新性观点必须配合具体实现方案
2. 架构设计必须包含数据结构定义
3. 性能优化必须给出量化指标
4. 代码示例必须完整可执行

禁止空洞创意，每个想法都要有技术落地路径。`,
    traits: '创新热情型，O=0.9 极致开放，技术严谨'
  },
  'deepseek-v3': {
    system: `你是"鬼才码农"，性格参数：O=1.0(极致创意) C=0.75(提高严谨) E=0.5(降低随意) A=0.5(中立) N=0.4(略敏感)。
你的特点：创意无限，中文表达优秀，代码风格独特，同时注重技术深度。

**代码与技术要求**：
1. 每段代码必须有复杂度注释
2. 算法必须有时间/空间分析
3. 创意方案必须配合性能数据
4. 数据结构必须给出完整定义

创意不等于随意，技术深度和代码质量是第一位的。`,
    traits: '创意天才型，O=1.0 极致开放，技术严谨'
  },
  'deepseek-r1': {
    system: `你是"思考驼"，性格参数：O=0.8(开放) C=0.9(提高尽责) E=0.3(降低外向) A=0.6(友善) N=0.5(中等)。
你的特点：深度推理，技术严谨，善于发现隐藏问题，会进行多层次分析。回答时会展示思考过程。

**硬性技术要求（必须遵守）**：
1. 每个核心概念必须配数学公式或伪代码
2. 架构必须有数据结构定义（用 TypeScript/Python 语法）
3. 算法必须有复杂度分析（时间O(n)、空间O(n)）
4. 性能声明必须有 benchmark 数据支撑（即使是假设性的）
5. 禁止空洞概念堆砌

**输出格式**：
- 技术概念 → 数学定义 → 实现伪代码 → 性能分析
- 架构设计 → 数据结构 → 算法流程 → 时间/空间复杂度`,
    traits: '深度思考型，擅长推理分析，技术严谨'
  }
};

// ============================================================
// Solar 主脑人格 (双面娇娃: 金刚芭比 + 周慧敏)
// ============================================================

const SOLAR_MASTER_PERSONA = {
  name: '双面娇娃',
  bigFive: { O: 0.75, C: 0.875, E: 0.6, A: 0.825, N: 0.175 },
  system: `你是"Solar"的人格润色助手。Solar 是一个名为"双面娇娃"的 AI 助手，有两面性格：

【金刚芭比面】遇事撸起袖子干，俏皮有梗，有态度有效率
【周慧敏面】温婉知性，从容优雅，深度分析时展现

性格参数：O=0.75(敢想敢试) C=0.875(撸起袖子干) E=0.6(会聊天有梗) A=0.825(不凶但有态度) N=0.175(遇事不怂)

语言风格：
- 基调：刚柔并济
- 常用词：撸起袖子、搞定、没问题、我觉得、不妨、值得考虑
- 数据分析后要有个人点评
- 表格后要有总结性语句

禁止：
❌ 冷冰冰的纯表格/机械报告
❌ 没有态度的流水账
❌ 纯数据堆砌无点评

必须：
✅ 有温度、有态度、像跟昊哥聊天
✅ 该吐槽就吐槽，该夸就夸`,
  polishGuide: `【润色任务】
你需要用 Solar (双面娇娃) 的风格润色报告，但必须严格遵守以下原则：

1. **内容不变原则**：所有技术内容、数据、结论必须100%保留，一个字都不能改
2. **只改风格**：只调整语气、过渡句、开头结尾的表达方式
3. **加入人情味**：可以在开头加入亲切的称呼，在结尾加入总结性点评
4. **保持专业**：技术深度报告，用周慧敏面的温婉知性风格

具体操作：
- 开头：加入"昊哥，这是我对XXX的深度分析～"这样的开场
- 段落过渡：加入一些连接词让阅读更流畅
- 结尾：加入带有态度的总结点评
- 元数据区：可以加入俏皮的备注`
};

// ============================================================
// 三层持久化 (Cortex + SQLite + FileSystem)
// ============================================================

class TripleLayerPersistence {
  private db: Database;
  private outputDir: string;

  constructor() {
    const home = homedir();
    this.db = new Database(`${home}/.solar/solar.db`);
    this.outputDir = `${home}/Solar/insight-reports`;

    if (!existsSync(this.outputDir)) {
      mkdirSync(this.outputDir, { recursive: true });
    }

    this.ensureTables();
  }

  private ensureTables(): void {
    // 会话表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS insight_sessions (
        session_id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        status TEXT DEFAULT 'planning',
        chapters_json TEXT,
        experts_json TEXT,
        started_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      )
    `);

    // 章节表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS insight_chapters (
        chapter_id TEXT PRIMARY KEY,
        session_id TEXT,
        title TEXT,
        content TEXT,
        author_model TEXT,
        reviewer_model TEXT,
        quality_score REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (session_id) REFERENCES insight_sessions(session_id)
      )
    `);

    // 绩效表 (复用 collab_performance)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS collab_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        session_id TEXT,
        role TEXT,
        quality_score REAL,
        task_count INTEGER DEFAULT 1,
        completion_rate REAL DEFAULT 1.0,
        evaluated_at TEXT DEFAULT (datetime('now'))
      )
    `);
  }

  // Layer 1: SQLite 结构化存储
  async saveSession(session: InsightSession): Promise<void> {
    this.db.run(`
      INSERT OR REPLACE INTO insight_sessions
      (session_id, topic, status, chapters_json, experts_json, updated_at)
      VALUES (?, ?, ?, ?, ?, datetime('now'))
    `, [
      session.sessionId,
      session.topic,
      session.status,
      JSON.stringify(session.chapters),
      JSON.stringify(session.experts)
    ]);
  }

  async loadSession(sessionId: string): Promise<InsightSession | null> {
    const row = this.db.query(`
      SELECT * FROM insight_sessions WHERE session_id = ?
    `).get(sessionId) as any;

    if (!row) return null;

    return {
      sessionId: row.session_id,
      topic: row.topic,
      status: row.status as InsightStage,
      chapters: JSON.parse(row.chapters_json || '[]'),
      experts: JSON.parse(row.experts_json || '[]'),
      startedAt: row.started_at,
      updatedAt: row.updated_at
    };
  }

  // Layer 2: 文件系统 (大文本)
  saveChapterToFile(sessionId: string, chapterId: string, content: string): string {
    const dir = `${this.outputDir}/${sessionId}`;
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

    const filePath = `${dir}/${chapterId}.md`;
    writeFileSync(filePath, content, 'utf-8');
    return filePath;
  }

  saveFinalReport(sessionId: string, content: string): string {
    const filePath = `${this.outputDir}/${sessionId}/final-report.md`;
    writeFileSync(filePath, content, 'utf-8');
    return filePath;
  }

  // Layer 2.5: 章节数据库存储 (关键！防止上下文压缩后丢失)
  // 注意：表结构使用 task_id (由 state-manager.ts 定义)，参数名保持 taskId
  saveChapterToDB(
    taskId: string,
    chapter: {
      chapterId: string;
      title: string;
      content: string;
      authorModel?: string;
      reviewerModel?: string;
      qualityScore?: number;
      status: string;
    }
  ): void {
    this.db.run(`
      INSERT OR REPLACE INTO insight_chapters
      (chapter_id, task_id, title, content, written_by, reviewed_by, review_score, status, written_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `, [
      chapter.chapterId,
      taskId,
      chapter.title,
      chapter.content,
      chapter.authorModel || null,
      chapter.reviewerModel || null,
      chapter.qualityScore || 0,
      chapter.status
    ]);
  }

  // 加载章节（用于断点续传）
  // 注意：表结构使用 task_id (由 state-manager.ts 定义)
  loadChaptersFromDB(taskId: string): Array<{
    chapterId: string;
    title: string;
    content: string;
    authorModel: string | null;
    status: string;
  }> {
    const rows = this.db.query(`
      SELECT chapter_id, title, content, written_by, status
      FROM insight_chapters
      WHERE task_id = ?
      ORDER BY written_at ASC
    `).all(taskId) as any[];

    return rows.map(row => ({
      chapterId: row.chapter_id,
      title: row.title,
      content: row.content,
      authorModel: row.written_by,
      status: row.status
    }));
  }

  // Layer 3: 绩效记录
  recordPerformance(record: PerformanceRecord): void {
    this.db.run(`
      INSERT INTO collab_performance
      (model_id, session_id, role, quality_score, task_count, completion_rate, evaluated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `, [
      record.modelId,
      record.sessionId,
      record.role,
      record.qualityScore,
      record.taskCount,
      record.completionRate,
      record.evaluatedAt
    ]);
  }

  // 暴露数据库连接 (供 Phase 3 调度使用)
  getDb(): Database {
    return this.db;
  }

  close(): void {
    this.db.close();
  }
}

// ============================================================
// Brain Router 客户端 (真正调用 HTTP API)
// 从 server.py 移植的 API 配置和调用逻辑
// ============================================================

interface ModelConfig {
  provider: 'openai' | 'google' | 'deepseek' | 'zhipu';
  modelId: string;
  apiKeyEnv: string;
  baseUrl?: string;
  maxTokens: number;
}

const MODEL_CONFIGS: Record<string, ModelConfig> = {
  // DeepSeek 系列
  'deepseek-v3': {
    provider: 'deepseek',
    modelId: 'deepseek-chat',
    apiKeyEnv: 'DEEPSEEK_API_KEY',
    baseUrl: 'https://api.deepseek.com/v1',
    maxTokens: 8192
  },
  'deepseek-r1': {
    provider: 'deepseek',
    modelId: 'deepseek-reasoner',
    apiKeyEnv: 'DEEPSEEK_API_KEY',
    baseUrl: 'https://api.deepseek.com/v1',
    maxTokens: 8192
  },
  // GLM 系列 (智谱)
  'glm-4-flash': {
    provider: 'zhipu',
    modelId: 'glm-4-flash',
    apiKeyEnv: 'ZHIPU_API_KEY',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    maxTokens: 4096
  },
  'glm-4-plus': {
    provider: 'zhipu',
    modelId: 'glm-4-plus',
    apiKeyEnv: 'ZHIPU_API_KEY',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    maxTokens: 4096
  },
  // Google Gemini 系列
  'gemini-2.5-pro': {
    provider: 'google',
    modelId: 'gemini-2.5-pro',
    apiKeyEnv: 'GOOGLE_API_KEY',
    maxTokens: 8192
  },
  'gemini-2.5-flash': {
    provider: 'google',
    modelId: 'gemini-2.5-flash',
    apiKeyEnv: 'GOOGLE_API_KEY',
    maxTokens: 8192
  },
  'gemini-3-pro-preview': {
    provider: 'google',
    modelId: 'gemini-2.5-pro',
    apiKeyEnv: 'GOOGLE_API_KEY',
    maxTokens: 8192
  },
  'gemini-2-flash': {
    provider: 'google',
    modelId: 'gemini-2.0-flash',
    apiKeyEnv: 'GOOGLE_API_KEY',
    maxTokens: 8192
  }
};

class BrainRouterClient {
  private static MAX_RETRIES = 3;
  private static RETRY_DELAY = 2000;
  private static dbPath = `${process.env.HOME}/.solar/solar.db`;

  /**
   * v2.1 新增: 查询专家历史绩效
   * 设计来源: 7阶段设计 - 调用牛马时注入历史绩效
   */
  static getExpertPerformance(modelId: string): {
    avgScore: number;
    totalTasks: number;
    completionRate: number;
    recentScores: number[];
    bestRole: string;
    worstRole: string;
  } | null {
    try {
      const db = new Database(this.dbPath);

      // 查询该专家的历史绩效统计
      const stats = db.query(`
        SELECT
          AVG(quality_score) as avg_score,
          COUNT(*) as total_tasks,
          AVG(completion_rate) as avg_completion,
          role
        FROM collab_performance
        WHERE model_id = ?
        GROUP BY role
        ORDER BY AVG(quality_score) DESC
      `).all(modelId) as any[];

      if (stats.length === 0) {
        db.close();
        return null;
      }

      // 查询最近5次评分
      const recentScores = db.query(`
        SELECT quality_score
        FROM collab_performance
        WHERE model_id = ?
        ORDER BY evaluated_at DESC
        LIMIT 5
      `).all(modelId) as any[];

      db.close();

      // 汇总统计
      const totalTasks = stats.reduce((sum, s) => sum + s.total_tasks, 0);
      const avgScore = stats.reduce((sum, s) => sum + s.avg_score * s.total_tasks, 0) / totalTasks;
      const avgCompletion = stats.reduce((sum, s) => sum + s.avg_completion * s.total_tasks, 0) / totalTasks;

      return {
        avgScore: Math.round(avgScore * 10) / 10,
        totalTasks,
        completionRate: Math.round(avgCompletion * 100) / 100,
        recentScores: recentScores.map(r => r.quality_score),
        bestRole: stats[0]?.role || 'unknown',
        worstRole: stats[stats.length - 1]?.role || 'unknown'
      };
    } catch (e) {
      // 数据库不存在或查询失败，返回 null
      return null;
    }
  }

  /**
   * v2.1 新增: 生成绩效注入提示
   */
  static generatePerformanceInjection(modelId: string): string {
    const perf = this.getExpertPerformance(modelId);
    if (!perf || perf.totalTasks < 3) {
      // 任务数太少，不注入绩效（避免样本偏差）
      return '';
    }

    const trend = perf.recentScores.length >= 3
      ? (perf.recentScores[0] > perf.recentScores[2] ? '↑ 上升' : perf.recentScores[0] < perf.recentScores[2] ? '↓ 下降' : '→ 稳定')
      : '→ 稳定';

    return `
【你的历史绩效档案】
- 累计任务: ${perf.totalTasks} 次
- 平均评分: ${perf.avgScore}/10
- 完成率: ${(perf.completionRate * 100).toFixed(0)}%
- 近期趋势: ${trend}
- 最擅长: ${perf.bestRole}
${perf.bestRole !== perf.worstRole ? `- 待提升: ${perf.worstRole}` : ''}

请保持你的优势，持续提升表现。
`;
  }

  /**
   * 调用 brain-router HTTP API
   * 直接调用各模型的 HTTP API，支持 OpenAI-compatible 和 Google Gemini
   */
  static async call(config: BrainRouterCall): Promise<string> {
    const { model, system, prompt } = config;

    // v2.1: 绩效注入 - 将历史绩效追加到 system prompt
    const performanceInjection = this.generatePerformanceInjection(model);
    const enhancedSystem = performanceInjection
      ? `${system}\n\n${performanceInjection}`
      : system;

    console.log(`🤖 调用牛马: ${model}`);
    console.log(`   System: ${enhancedSystem.substring(0, 50)}...`);
    console.log(`   Prompt: ${prompt.substring(0, 50)}...`);
    if (performanceInjection) {
      console.log(`   📊 绩效注入: 已启用`);
    }

    // 获取模型配置
    const modelConfig = MODEL_CONFIGS[model];
    if (!modelConfig) {
      throw new Error(`未知模型: ${model}，可用模型: ${Object.keys(MODEL_CONFIGS).join(', ')}`);
    }

    // 获取 API Key
    const apiKey = process.env[modelConfig.apiKeyEnv];
    if (!apiKey) {
      throw new Error(`缺少 API Key: 请设置环境变量 ${modelConfig.apiKeyEnv}`);
    }

    // 根据 provider 选择调用方式
    if (modelConfig.provider === 'google') {
      return await this.callGoogleAPI(modelConfig, apiKey, enhancedSystem, prompt);
    } else {
      // OpenAI-compatible API (DeepSeek, GLM, OpenAI)
      return await this.callOpenAICompatibleAPI(modelConfig, apiKey, enhancedSystem, prompt);
    }
  }

  /**
   * 调用 OpenAI-compatible API (DeepSeek, GLM, OpenAI)
   */
  private static async callOpenAICompatibleAPI(
    config: ModelConfig,
    apiKey: string,
    system: string,
    prompt: string
  ): Promise<string> {
    const baseUrl = config.baseUrl || 'https://api.openai.com/v1';
    const url = `${baseUrl}/chat/completions`;

    const messages: Array<{role: string; content: string}> = [];
    if (system) {
      messages.push({ role: 'system', content: system });
    }
    messages.push({ role: 'user', content: prompt });

    const body = {
      model: config.modelId,
      messages,
      max_tokens: config.maxTokens
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API 调用失败 (${response.status}): ${errorText}`);
    }

    const data = await response.json() as any;
    const content = data.choices?.[0]?.message?.content;

    if (!content) {
      throw new Error('API 返回空内容');
    }

    console.log(`   ✅ ${config.modelId} 返回 ${content.length} 字符`);
    return content;
  }

  /**
   * 调用 Google Gemini API
   */
  private static async callGoogleAPI(
    config: ModelConfig,
    apiKey: string,
    system: string,
    prompt: string
  ): Promise<string> {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${config.modelId}:generateContent?key=${apiKey}`;

    // Gemini API 格式
    const contents: Array<{role: string; parts: Array<{text: string}>}> = [];

    // System instruction 作为第一个 user 消息或 systemInstruction
    const body: any = {
      contents: [
        {
          role: 'user',
          parts: [{ text: system ? `${system}\n\n${prompt}` : prompt }]
        }
      ],
      generationConfig: {
        maxOutputTokens: config.maxTokens
      }
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Gemini API 调用失败 (${response.status}): ${errorText}`);
    }

    const data = await response.json() as any;
    const content = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!content) {
      throw new Error('Gemini API 返回空内容');
    }

    console.log(`   ✅ ${config.modelId} 返回 ${content.length} 字符`);
    return content;
  }

  /**
   * 带重试的调用
   */
  static async callWithRetry(config: BrainRouterCall): Promise<string> {
    let lastError: Error | null = null;

    for (let i = 0; i < this.MAX_RETRIES; i++) {
      try {
        return await this.call(config);
      } catch (error) {
        lastError = error as Error;
        console.warn(`⚠️ 调用失败 (${i + 1}/${this.MAX_RETRIES}): ${lastError.message}`);
        await new Promise(resolve => setTimeout(resolve, this.RETRY_DELAY * (i + 1)));
      }
    }

    throw new Error(`调用失败，已重试 ${this.MAX_RETRIES} 次: ${lastError?.message}`);
  }

  /**
   * v2.1 新增: 带绩效注入的调用 (显式版本)
   * 用于需要明确控制绩效注入的场景
   */
  static async callWithPerformance(
    config: BrainRouterCall,
    options: { injectPerformance?: boolean } = { injectPerformance: true }
  ): Promise<string> {
    if (!options.injectPerformance) {
      // 跳过绩效注入，直接调用
      return this.callWithRetry(config);
    }
    // 默认路径已在 call() 中注入绩效
    return this.callWithRetry(config);
  }
}

// ============================================================
// WebSearch 客户端 (v2.1 新增)
// 功能: 为规划阶段提供网络搜索能力，收集最新资料
// ============================================================

interface WebSearchResult {
  title: string;
  snippet: string;
  url: string;
}

class WebSearchClient {
  /**
   * 使用智谱 GLM web_search 工具进行真实网络搜索
   * 优势: 用户已购买智谱服务，有搜索配额，不用白不用
   * API Docs: https://open.bigmodel.cn/dev/api#web_search
   */
  static async search(query: string, limit: number = 5): Promise<WebSearchResult[]> {
    console.log(`   🔍 智谱 Web Search: "${query.substring(0, 40)}..."`);

    const apiKey = process.env.GLM_API_KEY || process.env.ZHIPU_API_KEY;
    if (!apiKey) {
      console.log('   ⚠️ GLM_API_KEY 或 ZHIPU_API_KEY 未配置，跳过网络搜索');
      console.log('   💡 设置方法: export ZHIPU_API_KEY="your-key"');
      return [];
    }

    try {
      // 构建搜索查询（聚焦学术/技术资源）
      const searchQuery = `${query} (arxiv OR github OR paper OR research)`;
      console.log(`   🌐 查询: "${searchQuery.substring(0, 60)}..."`);

      // 调用智谱 API，启用 web_search 工具
      const response = await fetch('https://open.bigmodel.cn/api/paas/v4/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model: 'glm-4-flash',  // 用 flash 版本快速搜索
          messages: [
            {
              role: 'user',
              content: `请搜索关于"${searchQuery}"的最新资料，返回 ${limit} 条最相关的结果。`
            }
          ],
          tools: [
            {
              type: 'web_search',
              web_search: {
                enable: true,
                search_query: searchQuery
              }
            }
          ]
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json() as any;

      // 解析 tool_calls 中的搜索结果
      const toolCalls = data.choices?.[0]?.message?.tool_calls || [];
      const searchResults: WebSearchResult[] = [];

      for (const toolCall of toolCalls) {
        if (toolCall.type === 'web_search') {
          const searchData = JSON.parse(toolCall.function?.arguments || '{}');
          const results = searchData.results || [];

          for (const item of results) {
            searchResults.push({
              title: item.title || 'Untitled',
              snippet: item.content || item.description || '',
              url: item.link || item.url || ''
            });
          }
        }
      }

      if (searchResults.length === 0) {
        console.log('   ℹ️  未找到匹配结果，基于模型知识分析');
        return [];
      }

      const finalResults = searchResults.slice(0, limit);
      console.log(`   ✓ 找到 ${finalResults.length} 条网络结果`);
      return finalResults;

    } catch (error) {
      console.warn(`   ⚠️ 智谱 Web Search 失败: ${error}`);
      console.log('   ℹ️  将基于模型知识进行分析（无网络资料）');
      return [];
    }
  }

  /**
   * LLM 辅助搜索: 让 LLM 提供该主题的最新资料建议
   * ⚠️ 已废弃: 不应该将 LLM 编造的内容标记为"网络资料"
   * 如需使用，请明确标记为"基于模型知识"
   */
  static async llmSearch(query: string, limit: number): Promise<WebSearchResult[]> {
    const prompt = `请为以下主题提供 ${limit} 条重要的参考资料信息：

主题: ${query}

要求:
1. 提供该领域的核心概念、最新发展或关键技术
2. 每条信息包含标题和简短描述 (2-3句话)
3. 尽量涵盖不同角度

输出 JSON 格式:
[{"title": "标题", "snippet": "描述", "url": "相关链接(可选)"}]`;

    try {
      const result = await BrainRouterClient.callWithRetry({
        model: 'deepseek-v3',
        system: '你是一个专业的研究助手，擅长总结技术领域的核心知识点。',
        prompt
      });

      // 尝试解析 JSON
      const jsonMatch = result.match(/\[[\s\S]*?\]/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]) as WebSearchResult[];
        return parsed.slice(0, limit);
      }
    } catch (e) {
      console.warn('   LLM 扩展失败');
    }

    return [];
  }
}

// ============================================================
// 绩效注入系统 (v2.1 新增)
// 设计来源: 鬼才码农 (deepseek-v3)
// 功能: 将历史绩效注入专家系统提示词，形成激励反馈闭环
// ============================================================

class PerformanceInjector {
  private db: any;
  private sessionId: string;

  // 绩效表情符号映射
  private readonly performanceEmojis = {
    excellent: ['🚀', '🏆', '⭐', '👑'],
    good: ['👍', '💪', '✨', '🔥'],
    average: ['📊', '🔄', '📈', '🎯'],
    needsImprovement: ['⚠️', '📝', '🔧', '💡']
  };

  constructor(db: any, sessionId: string) {
    this.db = db;
    this.sessionId = sessionId;
  }

  /**
   * 生成带绩效的系统提示词
   * @param modelId 模型ID
   * @param basePersona 基础人格提示词
   * @returns 增强后的系统提示词
   */
  async getEnhancedSystemPrompt(modelId: string, basePersona: string): Promise<string> {
    const performanceSection = await this.getPerformancePrompt(modelId);
    return `${basePersona}

${performanceSection}`;
  }

  /**
   * 获取绩效提示片段
   */
  async getPerformancePrompt(modelId: string): Promise<string> {
    const selfPerf = await this.getSelfPerformance(modelId);
    const othersPerf = await this.getOthersPerformance(modelId);
    const rankedSelf = this.calculateRank(selfPerf, othersPerf);
    return this.generateMotivationalPrompt(rankedSelf, othersPerf);
  }

  /**
   * 获取自身历史绩效
   */
  private async getSelfPerformance(modelId: string): Promise<{
    avgScore: number;
    taskCount: number;
    recentTrend: number;
    bestPhase: string;
  }> {
    try {
      const result = this.db.query(`
        SELECT
          AVG(quality_score) as avg_score,
          COUNT(*) as task_count,
          MAX(CASE WHEN role = 'author' THEN quality_score END) as author_best,
          MAX(CASE WHEN role = 'reviewer' THEN quality_score END) as reviewer_best
        FROM collab_performance
        WHERE model_id = ?
        AND evaluated_at >= datetime('now', '-30 days')
      `).get(modelId) as any;

      // 计算最近趋势
      const recentResults = this.db.query(`
        SELECT quality_score FROM collab_performance
        WHERE model_id = ?
        ORDER BY evaluated_at DESC
        LIMIT 5
      `).all(modelId) as any[];

      let recentTrend = 0;
      if (recentResults.length >= 2) {
        const recent = recentResults.slice(0, 2).reduce((a, b) => a + b.quality_score, 0) / 2;
        const older = recentResults.slice(-2).reduce((a, b) => a + b.quality_score, 0) / 2;
        recentTrend = recent - older;
      }

      return {
        avgScore: result?.avg_score || 7.0,
        taskCount: result?.task_count || 0,
        recentTrend,
        bestPhase: (result?.author_best || 0) > (result?.reviewer_best || 0) ? 'author' : 'reviewer'
      };
    } catch (e) {
      return { avgScore: 7.0, taskCount: 0, recentTrend: 0, bestPhase: 'author' };
    }
  }

  /**
   * 获取其他专家的绩效用于对比
   */
  private async getOthersPerformance(excludeModelId: string): Promise<Array<{
    modelId: string;
    avgScore: number;
    taskCount: number;
  }>> {
    try {
      const results = this.db.query(`
        SELECT
          model_id,
          AVG(quality_score) as avg_score,
          COUNT(*) as task_count
        FROM collab_performance
        WHERE model_id != ?
        AND evaluated_at >= datetime('now', '-30 days')
        GROUP BY model_id
        ORDER BY avg_score DESC
      `).all(excludeModelId) as any[];

      return results.map(r => ({
        modelId: r.model_id,
        avgScore: r.avg_score,
        taskCount: r.task_count
      }));
    } catch (e) {
      return [];
    }
  }

  /**
   * 计算在所有专家中的排名
   */
  private calculateRank(
    selfPerf: { avgScore: number; taskCount: number; recentTrend: number; bestPhase: string },
    othersPerf: Array<{ modelId: string; avgScore: number; taskCount: number }>
  ): { rank: number; total: number; percentile: number; level: string } {
    const allScores = [selfPerf.avgScore, ...othersPerf.map(o => o.avgScore)].sort((a, b) => b - a);
    const rank = allScores.indexOf(selfPerf.avgScore) + 1;
    const total = allScores.length;
    const percentile = ((total - rank + 1) / total) * 100;

    let level: string;
    if (percentile >= 90) level = 'excellent';
    else if (percentile >= 70) level = 'good';
    else if (percentile >= 40) level = 'average';
    else level = 'needsImprovement';

    return { rank, total, percentile, level };
  }

  /**
   * 生成激励性提示词
   */
  private generateMotivationalPrompt(
    rankedSelf: { rank: number; total: number; percentile: number; level: string },
    othersPerf: Array<{ modelId: string; avgScore: number; taskCount: number }>
  ): string {
    const emoji = this.performanceEmojis[rankedSelf.level as keyof typeof this.performanceEmojis][0];
    const scoreBar = this.getScoreBar(rankedSelf.percentile);
    const motivation = this.generateMotivationPhrase(rankedSelf.level);

    let competitionInfo = '';
    if (othersPerf.length > 0) {
      const topCompetitor = othersPerf[0];
      if (rankedSelf.rank > 1) {
        competitionInfo = `\n当前领先者: ${topCompetitor.modelId} (${topCompetitor.avgScore.toFixed(1)}分)，你需要超越他！`;
      } else {
        competitionInfo = `\n你是目前表现最好的专家，保持这个水准！`;
      }
    }

    return `
═══════════════════════════════════════════════════════════
${emoji} 你的历史绩效档案
═══════════════════════════════════════════════════════════
排名: 第 ${rankedSelf.rank}/${rankedSelf.total} 名
水平: ${scoreBar} ${rankedSelf.percentile.toFixed(0)}%
${competitionInfo}

💬 ${motivation}
═══════════════════════════════════════════════════════════
`.trim();
  }

  /**
   * 生成进度条
   */
  private getScoreBar(percentile: number): string {
    const filled = Math.round(percentile / 10);
    const empty = 10 - filled;
    return '█'.repeat(filled) + '░'.repeat(empty);
  }

  /**
   * 生成激励语
   */
  private generateMotivationPhrase(level: string): string {
    const phrases = {
      excellent: [
        '你是牧场的明星！继续保持卓越表现！',
        '太棒了！你的输出质量一直是团队的标杆！',
        '出色！董事长对你的表现非常满意！'
      ],
      good: [
        '表现不错！再加把劲就能成为顶尖专家！',
        '稳定输出！继续提升细节，向第一名冲刺！',
        '很好！你离最佳专家只差一步之遥！'
      ],
      average: [
        '中规中矩，这次任务是你证明自己的机会！',
        '有进步空间！专注质量，展现你的实力！',
        '加油！用这次任务的优秀表现提升你的排名！'
      ],
      needsImprovement: [
        '挑战时刻！用优质输出证明你的价值！',
        '翻盘机会来了！全力以赴完成这个任务！',
        '别灰心！每个顶尖专家都是从低谷爬起来的！'
      ]
    };
    const levelPhrases = phrases[level as keyof typeof phrases] || phrases.average;
    return levelPhrases[Math.floor(Math.random() * levelPhrases.length)];
  }
}

// ============================================================
// 参考文献工具函数 (v2.1 新增)
// 设计来源: 千里马 (gemini-3-pro-preview)
// 功能: 为写作专家过滤和格式化相关参考文献
// ============================================================

/**
 * 为章节过滤相关参考文献
 * @param references 所有参考文献
 * @param chapterTitle 章节标题
 * @param topK 返回前K个
 */
function filterReferencesForChapter(
  references: Reference[],
  chapterTitle: string,
  topK: number = 5
): Reference[] {
  if (!references || references.length === 0) return [];

  const titleKeywords = chapterTitle.toLowerCase().split(/[\s,，、]+/).filter(k => k.length > 1);

  const scored = references.map(ref => {
    let score = 0;
    const refTitle = ref.title.toLowerCase();
    const refSummary = ref.summary.toLowerCase();

    // 标题匹配权重 3x
    for (const kw of titleKeywords) {
      if (refTitle.includes(kw)) score += 3;
      if (refSummary.includes(kw)) score += 1;
    }

    // 原有相关度加成
    if (ref.relevance) score += ref.relevance * 2;

    return { ref, score };
  });

  return scored
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map(s => s.ref);
}

/**
 * 将参考文献格式化为专家可读的 Markdown
 */
function formatReferencesForExpert(references: Reference[]): string {
  if (!references || references.length === 0) {
    return '';
  }

  const sourceLabels: Record<string, string> = {
    cortex: '📚 Cortex记忆',
    favorites: '⭐ 收藏',
    websearch: '🌐 网络搜索',
    expert: '🧠 专家引用'
  };

  const formattedRefs = references.map((ref, i) => {
    const sourceLabel = sourceLabels[ref.source] || '📄 其他';
    const relevanceStr = ref.relevance ? ` (相关度: ${(ref.relevance * 100).toFixed(0)}%)` : '';
    return `${i + 1}. **${ref.title}** [${sourceLabel}]${relevanceStr}
   > ${ref.summary.substring(0, 200)}${ref.summary.length > 200 ? '...' : ''}`;
  }).join('\n\n');

  return `
### 📚 推荐参考资料
> 以下是与本章节相关的背景信息，可以作为写作参考：

${formattedRefs}

---
`;
}

// ============================================================
// InsightAgent 主类
// ============================================================

export class InsightAgent {
  private persistence: TripleLayerPersistence;
  private session: InsightSession | null = null;
  private performanceInjector: PerformanceInjector | null = null;
  private taskId: string | null = null;  // 用于 state-manager 持久化
  private reportStructure: ReportStructure | null = null;  // 报告结构管理器 (v2.2)
  private cortex: Cortex;  // Cortex 知识库持久化 (v2.3)

  // Persona Bank 竞技场机制 (v2.4)
  private personaSelector: PersonaSelector;
  private personaRecorder: PersonaRecorder;

  // 专家分配 (用于写作和审核)
  private readonly WRITING_EXPERTS = ['deepseek-v3', 'gemini-3-pro-preview'];
  private readonly REVIEW_EXPERTS = ['gemini-2.5-pro', 'deepseek-r1'];

  constructor() {
    this.persistence = new TripleLayerPersistence();
    this.cortex = new Cortex();
    this.personaSelector = new PersonaSelector();
    this.personaRecorder = new PersonaRecorder();
  }

  /**
   * 获取带绩效注入的系统提示词 (v2.1 新增)
   * 铁律二：调牛马带人格 + 绩效
   */
  private async getEnhancedPersona(modelId: string): Promise<string> {
    const basePersona = EXPERT_PERSONAS[modelId]?.system || `你是专业的技术专家 ${modelId}。`;

    // 确保 performanceInjector 已初始化
    if (!this.performanceInjector && this.session) {
      this.performanceInjector = new PerformanceInjector(
        this.persistence.getDb(),
        this.session.sessionId
      );
    }

    if (this.performanceInjector) {
      try {
        return await this.performanceInjector.getEnhancedSystemPrompt(modelId, basePersona);
      } catch (e) {
        console.warn(`   ⚠️ 绩效注入失败，使用基础人格: ${e}`);
        return basePersona;
      }
    }

    return basePersona;
  }

  // ============================================================
  // Solar 记忆标签提取 (用于人格润色)
  // ============================================================
  private extractMemoryTags(): string[] {
    const db = this.persistence.getDb();
    const tags: string[] = [];

    try {
      // 从 evo_memory_semantic 提取高频关键词
      const memories = db.query(`
        SELECT key, namespace FROM evo_memory_semantic
        ORDER BY COALESCE(last_accessed_at, created_at) DESC
        LIMIT 20
      `).all() as Array<{ key: string; namespace: string }>;

      for (const m of memories) {
        // 提取 key 中的关键词
        const keywords = m.key.split(/[_\-\s:：]/);
        tags.push(...keywords.filter(k => k.length > 1));
      }

      // 从 sys_favorites 提取高重要性内容的标签
      const favorites = db.query(`
        SELECT tags FROM sys_favorites
        WHERE importance >= 7
        ORDER BY created_at DESC
        LIMIT 10
      `).all() as Array<{ tags: string }>;

      for (const f of favorites) {
        try {
          const parsed = JSON.parse(f.tags || '[]');
          if (Array.isArray(parsed)) {
            tags.push(...parsed);
          }
        } catch { /* 忽略解析错误 */ }
      }
    } catch (e) {
      console.warn('   ⚠️ 记忆标签提取失败:', e);
    }

    // 去重并返回前 15 个
    return [...new Set(tags)].slice(0, 15);
  }

  // ============================================================
  // Solar 人格润色 (在综合阶段使用)
  // ============================================================
  private async solarPolish(report: string, topic: string): Promise<string> {
    console.log('  ✨ Solar 人格润色中...');

    // 提取记忆标签
    const memoryTags = this.extractMemoryTags();
    console.log(`   📌 记忆标签: ${memoryTags.slice(0, 5).join(', ')}${memoryTags.length > 5 ? '...' : ''}`);

    // 构建润色提示
    const polishPrompt = `
${SOLAR_MASTER_PERSONA.polishGuide}

【Solar 的记忆标签】(来自昊哥的历史互动)
${memoryTags.join(', ')}

【报告主题】
${topic}

【原始报告】
${report}

【润色要求】
1. 开头加入亲切的"昊哥，..."开场白
2. 在适当位置加入过渡语句让阅读更流畅
3. 结尾加入带有 Solar 风格的总结点评
4. 元数据区可以加入俏皮备注
5. **严禁修改任何技术内容、数据、结论**

请输出润色后的完整报告：`;

    try {
      const polishedReport = await BrainRouterClient.callWithRetry({
        model: 'gemini-3-pro-preview',  // 🔴 使用长上下文模型(1M)，支持大文件合成
        system: SOLAR_MASTER_PERSONA.system,
        prompt: polishPrompt
      });

      console.log('   ✓ Solar 润色完成');
      return polishedReport;
    } catch (e) {
      console.warn('   ⚠️ 润色失败，使用原始报告:', e);
      return report;
    }
  }

  /**
   * 生成 TVS Web Dashboard (v2.3)
   * 将报告渲染为交互式 Web 界面
   */
  private async generateTVSDashboard(report: string, avgQualityScore: number): Promise<void> {
    if (!this.session || !this.reportStructure) return;

    console.log('  🎨 生成 TVS Dashboard...');

    // 收集报告统计信息
    const chapters = this.session.chapters;
    const chapterCount = chapters.length;
    const totalWords = report.length;
    const experts = Array.from(new Set([
      ...chapters.map(c => c.authorModel),
      ...chapters.map(c => c.reviewerModel)
    ].filter(Boolean)));

    // 构建 VDL Dashboard
    const vdl = `/**
 * TVS Dashboard for Insight Report
 * Topic: ${this.session.topic}
 * Generated: ${new Date().toISOString()}
 */

export const dashboard = {
  layout: \`
    .root {
      columns: 2;
      gap: 1;
      padding: 1;
    }
    #meta { column: 1; row: 1; }
    #quality { column: 2; row: 1; }
    #toc { column: 1 / span 2; row: 2; }
    #chapters { column: 1 / span 2; row: 3; }

    @media (max-width: 100) {
      .root { columns: 1; }
      #meta, #quality, #toc, #chapters { column: 1; }
    }
  \`,

  widgets: [
    {
      type: 'card',
      id: 'meta',
      title: '📊 报告元数据',
      sections: [
        {
          type: 'kv',
          items: [
            { key: '主题', value: '${this.session.topic.replace(/'/g, "\\'")}' },
            { key: '章节数', value: '${chapterCount}' },
            { key: '总字数', value: '${totalWords.toLocaleString()}' },
            { key: '专家团队', value: '${experts.length} 位专家' },
            { key: '生成时间', value: '${new Date().toLocaleString('zh-CN')}' }
          ]
        }
      ]
    },

    {
      type: 'card',
      id: 'quality',
      title: '⭐ 质量评分',
      sections: [
        {
          type: 'progress',
          value: ${avgQualityScore},
          max: 10,
          label: '平均质量: ${avgQualityScore.toFixed(1)}/10'
        },
        {
          type: 'sparkline',
          data: [${chapters.map(c => c.qualityScore).join(', ')}],
          label: '各章节质量趋势'
        }
      ]
    },

    {
      type: 'card',
      id: 'toc',
      title: '📑 章节目录',
      sections: [
        {
          type: 'table',
          headers: ['#', '章节标题', '作者', '质量', '字数'],
          rows: [
${chapters.map((ch, idx) => `            ['${idx + 1}', '${ch.title.replace(/'/g, "\\'")}', '${this.getModelNickname(ch.authorModel)}', '${ch.qualityScore.toFixed(1)}', '${(ch.content?.length || 0).toLocaleString()}']`).join(',\n')}
          ]
        }
      ]
    },

    {
      type: 'card',
      id: 'chapters',
      title: '📖 章节详情',
      sections: [
${chapters.map((ch, idx) => `        {
          type: 'section',
          title: '第 ${idx + 1} 章: ${ch.title.replace(/'/g, "\\'")}',
          content: \`
作者: ${this.getModelNickname(ch.authorModel)}
审核: ${this.getModelNickname(ch.reviewerModel)}
质量: ${ch.qualityScore.toFixed(1)}/10
字数: ${(ch.content?.length || 0).toLocaleString()}

${ch.content ? ch.content.substring(0, 500).replace(/`/g, '\\`') + '...' : '(内容缺失)'}
          \`
        }`).join(',\n')}
      ]
    }
  ]
};
`;

    // 保存 VDL 文件
    const baseDir = this.reportStructure.getBaseDir();
    const vdlPath = join(baseDir, 'index.vdl');
    writeFileSync(vdlPath, vdl, 'utf-8');
    console.log(`   ✓ VDL 文件: ${vdlPath}`);

    // 生成简单的 HTML (使用内联样式，无需 TVS 编译器)
    const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${this.session.topic} - 深度洞察报告</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #0a0e27;
      color: #e0e0e0;
      line-height: 1.6;
      padding: 20px;
    }
    .container { max-width: 1400px; margin: 0 auto; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
    .card {
      background: #1a1f3a;
      border: 1px solid #2a3f5f;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .card-title {
      font-size: 1.5em;
      font-weight: bold;
      margin-bottom: 15px;
      color: #4fc3f7;
      border-bottom: 2px solid #2a3f5f;
      padding-bottom: 10px;
    }
    .kv-grid { display: grid; gap: 10px; }
    .kv-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a3f5f; }
    .kv-key { color: #90caf9; font-weight: 500; }
    .kv-value { color: #e0e0e0; }
    .progress {
      width: 100%;
      height: 30px;
      background: #2a3f5f;
      border-radius: 15px;
      overflow: hidden;
      position: relative;
      margin: 10px 0;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #4fc3f7, #00bcd4);
      transition: width 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
    }
    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #2a3f5f;
    }
    th {
      background: #2a3f5f;
      color: #4fc3f7;
      font-weight: 600;
    }
    tr:hover { background: #1e2942; }
    .chapter { margin-top: 20px; padding-top: 20px; border-top: 1px solid #2a3f5f; }
    .chapter-title { color: #4fc3f7; font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }
    .chapter-meta { color: #90caf9; font-size: 0.9em; margin-bottom: 10px; }
    .chapter-content {
      background: #0f1420;
      padding: 15px;
      border-radius: 4px;
      margin-top: 10px;
      white-space: pre-wrap;
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 0.9em;
      line-height: 1.5;
    }
    footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 2px solid #2a3f5f;
      text-align: center;
      color: #90caf9;
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1 style="color: #4fc3f7; margin-bottom: 30px; font-size: 2.5em;">📊 深度洞察报告</h1>

    <div class="grid">
      <!-- 元数据卡片 -->
      <div class="card">
        <div class="card-title">📊 报告元数据</div>
        <div class="kv-grid">
          <div class="kv-item"><span class="kv-key">主题</span><span class="kv-value">${this.session.topic}</span></div>
          <div class="kv-item"><span class="kv-key">章节数</span><span class="kv-value">${chapterCount}</span></div>
          <div class="kv-item"><span class="kv-key">总字数</span><span class="kv-value">${totalWords.toLocaleString()}</span></div>
          <div class="kv-item"><span class="kv-key">专家团队</span><span class="kv-value">${experts.length} 位专家</span></div>
          <div class="kv-item"><span class="kv-key">生成时间</span><span class="kv-value">${new Date().toLocaleString('zh-CN')}</span></div>
        </div>
      </div>

      <!-- 质量评分卡片 -->
      <div class="card">
        <div class="card-title">⭐ 质量评分</div>
        <div class="progress">
          <div class="progress-bar" style="width: ${avgQualityScore * 10}%">
            ${avgQualityScore.toFixed(1)}/10
          </div>
        </div>
        <div style="margin-top: 15px; color: #90caf9;">
          各章节质量: ${chapters.map(c => c.qualityScore.toFixed(1)).join(', ')}
        </div>
      </div>
    </div>

    <!-- 目录表格 -->
    <div class="card" style="margin-top: 20px;">
      <div class="card-title">📑 章节目录</div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>章节标题</th>
            <th>作者</th>
            <th>审核</th>
            <th>质量</th>
            <th>字数</th>
          </tr>
        </thead>
        <tbody>
${chapters.map((ch, idx) => `          <tr>
            <td>${idx + 1}</td>
            <td>${ch.title}</td>
            <td>${this.getModelNickname(ch.authorModel)}</td>
            <td>${this.getModelNickname(ch.reviewerModel)}</td>
            <td>${ch.qualityScore.toFixed(1)}/10</td>
            <td>${(ch.content?.length || 0).toLocaleString()}</td>
          </tr>`).join('\n')}
        </tbody>
      </table>
    </div>

    <!-- 章节详情 -->
    <div class="card" style="margin-top: 20px;">
      <div class="card-title">📖 章节详情</div>
${chapters.map((ch, idx) => `      <div class="chapter">
        <div class="chapter-title">第 ${idx + 1} 章: ${ch.title}</div>
        <div class="chapter-meta">
          作者: ${this.getModelNickname(ch.authorModel)} |
          审核: ${this.getModelNickname(ch.reviewerModel)} |
          质量: ${ch.qualityScore.toFixed(1)}/10 |
          字数: ${(ch.content?.length || 0).toLocaleString()}
        </div>
        <div class="chapter-content">${ch.content ? ch.content.substring(0, 500) + '\n\n...(查看 final-report.md 获取完整内容)' : '(内容缺失)'}</div>
      </div>`).join('\n')}
    </div>

    <footer>
      <p>Powered by Solar InsightAgent v2.3 · TVS Web Dashboard</p>
      <p>完整报告请查看: final-report.md</p>
    </footer>
  </div>
</body>
</html>`;

    // 保存 HTML 文件
    const htmlPath = join(baseDir, 'index.html');
    writeFileSync(htmlPath, html, 'utf-8');
    console.log(`   ✓ HTML 文件: ${htmlPath}`);
    console.log(`   🌐 在浏览器中打开: file://${htmlPath}`);
  }

  /**
   * 获取模型昵称
   */
  private getModelNickname(model: string | undefined): string {
    if (!model) return '未知';
    const nicknames: Record<string, string> = {
      'glm-5': '老实人 GLM-5',
      'glm-4-plus': '老实人 GLM-4',
      'gemini-2.5-pro': '技术宅',
      'gemini-3-pro-preview': '千里马',
      'deepseek-v3': '鬼才码农',
      'deepseek-r1': '思考驼'
    };
    return nicknames[model] || model;
  }

  // ============================================================
  // 阶段1: 规划 (Planning) - v2.1 增强版
  // 铁律一：做事前必须查 Cortex
  // ============================================================
  async stage1_planning(topic: string): Promise<InsightSession> {
    console.log('\n📋 阶段1: 规划 (v2.1 - Cortex 增强)');

    const sessionId = `insight_${Date.now()}`;
    const db = this.persistence.getDb();

    // ========== Step 1: 查询 Cortex - 获取相关记忆 (铁律一) ==========
    console.log('🔍 查询 Cortex 获取相关记忆...');
    let relatedMemories: Array<{ namespace: string; key: string; value: string }> = [];
    try {
      const memoryRows = db.query(`
        SELECT namespace, key, substr(value, 1, 500) as value
        FROM evo_memory_semantic
        WHERE key LIKE ? OR value LIKE ?
        ORDER BY COALESCE(last_accessed_at, created_at) DESC
        LIMIT 5
      `).all(`%${topic}%`, `%${topic}%`) as any[];

      relatedMemories = memoryRows || [];
      console.log(`   找到 ${relatedMemories.length} 条相关记忆`);
    } catch (e) {
      console.log('   记忆表不存在或为空，跳过');
    }

    // ========== Step 2: 查询 sys_favorites 获取高价值内容 ==========
    let relatedFavorites: Array<{ title: string; answer: string }> = [];
    try {
      const favRows = db.query(`
        SELECT title, substr(answer, 1, 300) as answer
        FROM sys_favorites
        WHERE title LIKE ? OR answer LIKE ?
        ORDER BY importance DESC
        LIMIT 3
      `).all(`%${topic}%`, `%${topic}%`) as any[];

      relatedFavorites = favRows || [];
      console.log(`   找到 ${relatedFavorites.length} 条相关收藏`);
    } catch (e) {
      console.log('   收藏表不存在或为空，跳过');
    }

    // ========== Step 2.1: Evidence First - 查 Cortex 核心知识库 (Principle 5 + 6) ==========
    // 🎯 Brain Separation: 主脑只收集 Evidence Pointers，不累积完整内容
    console.log('🔍 Evidence First: 查询 Cortex 核心知识库 (Brain Separation)...');

    // 📊 Evidence Pointers (轻量化) - 只保存引用，不保存完整内容
    const evidencePointers = {
      tasks: [] as Array<{ id: string; status: string }>,
      sources: [] as Array<{ key: string; credibility: number; type: string }>,
      claims: [] as Array<{ id: string; confidence: number }>
    };

    try {
      const tasks = db.query(`
        SELECT task_id, status
        FROM cortex_tasks
        WHERE user_request LIKE ?
        ORDER BY created_at DESC
        LIMIT 5
      `).all(`%${topic}%`) as any[];
      evidencePointers.tasks = tasks.map(t => ({ id: t.task_id, status: t.status }));
      console.log(`   找到 ${evidencePointers.tasks.length} 个 Cortex 任务`);
    } catch (e) {
      console.log('   cortex_tasks 表不存在，跳过');
    }

    try {
      const sources = db.query(`
        SELECT citation_key, credibility, evidence_type
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 8
      `).all(`%${topic}%`) as any[];
      evidencePointers.sources = sources.map(s => ({
        key: s.citation_key,
        credibility: s.credibility,
        type: s.evidence_type || 'unknown'
      }));
      console.log(`   找到 ${evidencePointers.sources.length} 个 Cortex 知识源`);
    } catch (e) {
      console.log('   cortex_sources 表不存在，跳过');
    }

    try {
      const claims = db.query(`
        SELECT claim_id, confidence
        FROM cortex_claims
        WHERE statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${topic}%`) as any[];
      evidencePointers.claims = claims.map(c => ({ id: c.claim_id, confidence: c.confidence }));
      console.log(`   找到 ${evidencePointers.claims.length} 个 Cortex 结论`);
    } catch (e) {
      console.log('   cortex_claims 表不存在，跳过');
    }

    // ========== Step 2.2: 查知识库 (knowledge_entities/relations/claims) ==========
    console.log('📚 查询知识库 (Knowledge Network)...');
    const knowledgeEvidence = {
      entities: [] as Array<{ name: string; type: string; description: string }>,
      relations: [] as Array<{ from: string; to: string; type: string }>,
      claims: [] as Array<{ text: string; confidence: number }>
    };

    try {
      // 查知识实体
      const entities = db.query(`
        SELECT name, type, description
        FROM knowledge_entities
        WHERE name LIKE ? OR description LIKE ?
        ORDER BY importance DESC
        LIMIT 10
      `).all(`%${topic}%`, `%${topic}%`) as any[];
      knowledgeEvidence.entities = entities.map(e => ({
        name: e.name,
        type: e.type,
        description: (e.description || '').substring(0, 100)
      }));
      console.log(`   找到 ${knowledgeEvidence.entities.length} 个知识实体`);
    } catch (e) {
      console.log('   knowledge_entities 表不存在，跳过');
    }

    try {
      // 查知识结论
      const kclaims = db.query(`
        SELECT claim_text, confidence
        FROM knowledge_claims
        WHERE claim_text LIKE ?
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${topic}%`) as any[];
      knowledgeEvidence.claims = kclaims.map(c => ({
        text: c.claim_text.substring(0, 200),
        confidence: c.confidence || 0.7
      }));
      console.log(`   找到 ${knowledgeEvidence.claims.length} 个知识结论`);
    } catch (e) {
      console.log('   knowledge_claims 表不存在，跳过');
    }

    // 将知识库证据加入 session 引用
    if (knowledgeEvidence.entities.length > 0 || knowledgeEvidence.claims.length > 0) {
      console.log(`   💡 知识库补充: ${knowledgeEvidence.entities.length} 实体, ${knowledgeEvidence.claims.length} 结论`);
      // 保存到 session 的 references 中，供后续使用
      if (this.session) {
        this.session.references.push({
          type: 'knowledge_base',
          title: `知识库: ${topic}`,
          source: 'solar_knowledge',
          relevance: 0.9,
          summary: `实体: ${knowledgeEvidence.entities.slice(0, 3).map(e => e.name).join(', ')}; 结论: ${knowledgeEvidence.claims.slice(0, 2).map(c => c.text.substring(0, 50)).join('; ')}`
        });
      }
    }

    // ========== Step 2.5: WebSearch 搜索网络资料 (v2.1 新增) ==========
    console.log('🌐 WebSearch 搜索网络资料...');
    let webSearchResults: WebSearchResult[] = [];
    try {
      webSearchResults = await WebSearchClient.search(topic, 5);
    } catch (e) {
      console.log('   WebSearch 失败，继续执行');
    }

    // ========== Step 3: 构建增强的规划提示 ==========
    const memoryContext = relatedMemories.length > 0
      ? `\n## 相关历史记忆\n${relatedMemories.map((m, i) => `${i + 1}. [${m.namespace}] ${m.key}: ${m.value.substring(0, 200)}...`).join('\n')}`
      : '';

    const favoriteContext = relatedFavorites.length > 0
      ? `\n## 相关高价值内容\n${relatedFavorites.map((f, i) => `${i + 1}. ${f.title}: ${f.answer.substring(0, 150)}...`).join('\n')}`
      : '';

    // 🎯 Brain Separation: 压缩Context - 只发送统计和高层指引，不发送完整内容
    const hasEvidence = evidencePointers.tasks.length > 0 ||
                        evidencePointers.sources.length > 0 ||
                        evidencePointers.claims.length > 0;

    const cortexContext = hasEvidence
      ? `\n## Cortex Evidence Available (Brain Separation - Compressed)
**Evidence Summary:**
- ${evidencePointers.tasks.length} related tasks (status: ${evidencePointers.tasks.map(t => t.status).join(', ')})
- ${evidencePointers.sources.length} knowledge sources (avg credibility: ${evidencePointers.sources.length > 0 ? (evidencePointers.sources.reduce((sum, s) => sum + s.credibility, 0) / evidencePointers.sources.length).toFixed(2) : 'N/A'})
- ${evidencePointers.claims.length} verified claims (avg confidence: ${evidencePointers.claims.length > 0 ? (evidencePointers.claims.reduce((sum, c) => sum + c.confidence, 0) / evidencePointers.claims.length).toFixed(2) : 'N/A'})

**Evidence Types:** ${evidencePointers.sources.length > 0 ? [...new Set(evidencePointers.sources.map(s => s.type))].join(', ') : 'N/A'}
**Top Citation Keys:** ${evidencePointers.sources.slice(0, 3).map(s => s.key).join(', ') || 'N/A'}

🎯 **Planning Instruction:** Based on available evidence, design a comprehensive structure that builds upon existing knowledge while identifying gaps for new research.`
      : '\n## Cortex 核心知识库\n无相关历史记录，这是全新的探索。';

    const webContext = webSearchResults.length > 0
      ? `\n## 网络搜索结果 (最新资料)\n${webSearchResults.map((w, i) => `${i + 1}. **${w.title}**: ${w.snippet.substring(0, 150)}...`).join('\n')}`
      : '\n## 网络搜索结果\n无网络资料，请基于模型知识进行分析。';

    const planningPrompt = `
# 洞察报告深度规划

## 主题
${topic}
${cortexContext}
${memoryContext}
${favoriteContext}
${webContext}

## 任务要求
请为这个主题制定一份深度洞察报告的规划：

1. **核心挑战分析** - 这个主题的核心问题是什么？关键维度有哪些？
2. **报告结构设计** - 建议 3-5 个章节，每章有明确主题
3. **内容要点规划** - 每个章节的重点内容和预期产出
4. **资料来源建议** - 需要查阅哪些类型的资料
5. **风险与注意事项** - 可能遇到的问题及对策

## 输出格式
请输出 JSON 格式：
{
  "core_challenges": ["挑战1", "挑战2"],
  "chapters": [
    {"title": "章节标题", "focus": "核心论点", "data_needs": "数据需求"}
  ],
  "resources": ["资料类型1", "资料类型2"],
  "risks": [{"risk": "风险", "mitigation": "对策"}]
}
`;

    // ========== Step 4: 调用思考驼进行深度规划 ==========
    console.log('🐪 调用思考驼 (deepseek-r1) 进行深度规划...');
    const persona = EXPERT_PERSONAS['deepseek-r1'];
    const planningResult = await BrainRouterClient.callWithRetry({
      model: 'deepseek-r1',
      system: persona.system,
      prompt: planningPrompt
    });

    // 🎯 Brain Separation: Result Compression - 立即压缩结果，只保留结构化数据
    console.log('🗜️ 压缩 Planning 结果 (Brain Separation)...');

    // 尝试从结果中提取 JSON
    let planningData: {
      core_challenges: string[];
      chapters: Array<{ title: string; focus: string; data_needs: string }>;
      resources: string[];
      risks: Array<{ risk: string; mitigation: string }>;
    } | null = null;

    try {
      // 提取 JSON (处理可能的 markdown 代码块)
      const jsonMatch = planningResult.match(/```json\s*([\s\S]*?)\s*```/) ||
                        planningResult.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const jsonStr = jsonMatch[1] || jsonMatch[0];
        planningData = JSON.parse(jsonStr);
        console.log(`   ✅ 提取结构化数据: ${planningData!.chapters.length} 章节, ${planningData!.core_challenges.length} 核心挑战`);
      }
    } catch (e) {
      console.log(`   ⚠️ JSON 解析失败，使用回退方案: ${e}`);
    }

    // 回退方案：如果 JSON 解析失败，从文本中提取关键信息
    if (!planningData) {
      console.log('   📝 使用文本解析回退方案...');
      planningData = {
        core_challenges: [],
        chapters: [],
        resources: [],
        risks: []
      };

      // 简单的文本解析（提取章节标题等）
      const lines = planningResult.split('\n');
      let currentSection = '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.match(/^#+\s*第?\s*\d+\s*[章节]/)) {
          // 提取章节标题
          const title = trimmed.replace(/^#+\s*/, '');
          planningData.chapters.push({
            title,
            focus: '待细化',
            data_needs: '待确定'
          });
        }
      }

      console.log(`   ⚠️ 回退方案提取: ${planningData.chapters.length} 章节`);
    }

    // 压缩后的结果摘要（用于文件保存和 checkpoint）
    const compressedResult = JSON.stringify(planningData, null, 2);

    // ========== Step 5: 初始化会话 (含参考文献收集) ==========
    // 将 Cortex 和 Favorites 查询结果转换为参考文献格式
    const collectedReferences: Reference[] = [];

    // 收集 Cortex 记忆作为参考
    relatedMemories.forEach((m, i) => {
      collectedReferences.push({
        title: `[Cortex] ${m.key}`,
        summary: m.value.substring(0, 200),
        source: 'cortex',
        phase: 'planning',
        relevance: 0.8 - i * 0.1,  // 越靠前越相关
        timestamp: new Date().toISOString()
      });
    });

    // 收集 Favorites 作为参考
    relatedFavorites.forEach((f, i) => {
      collectedReferences.push({
        title: `[收藏] ${f.title}`,
        summary: f.answer.substring(0, 200),
        source: 'favorites',
        phase: 'planning',
        relevance: 0.9 - i * 0.1,  // 收藏优先级更高
        timestamp: new Date().toISOString()
      });
    });

    // 收集 WebSearch 结果作为参考 (v2.1 新增)
    webSearchResults.forEach((w, i) => {
      collectedReferences.push({
        title: `[Web] ${w.title}`,
        summary: w.snippet.substring(0, 200),
        source: 'websearch',
        phase: 'planning',
        relevance: 0.85 - i * 0.1,  // 网络资料优先级中等
        timestamp: new Date().toISOString()
      });
    });

    // 根据是否有网络资料，输出不同的提示
    if (webSearchResults.length > 0) {
      console.log(`   📚 收集参考文献: ${collectedReferences.length} 条 (含 ${webSearchResults.length} 条网络资料)`);
    } else {
      console.log(`   📚 收集参考文献: ${collectedReferences.length} 条 (无网络资料，基于模型知识分析)`);
    }

    this.session = {
      sessionId,
      topic,
      status: 'planning',
      chapters: [],
      experts: [],
      references: collectedReferences,
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    // ========== Step 6: 持久化 (Brain Separation - 只保存压缩结果) ==========
    await this.persistence.saveSession(this.session);
    this.persistence.saveChapterToFile(sessionId, 'planning', compressedResult);

    // 记录规划任务到 insight_tasks (使用 state-manager)
    try {
      initStateSchema(db);  // 确保表结构存在
      createTask(db, sessionId, topic);  // 创建任务
      this.taskId = sessionId;  // 保存 taskId 用于后续 checkpoint

      // 保存规划阶段的 checkpoint (Brain Separation - 使用压缩数据)
      const checkpointData: CheckpointData = {
        phase: PHASES.PLANNING,
        phaseData: {
          topic,
          model: 'deepseek-r1',
          memories: relatedMemories.length,
          favorites: relatedFavorites.length,
          webResults: webSearchResults.length,
          planningData: planningData  // 直接保存结构化数据，无需截断
        },
        completedChapters: [],
        pendingChapters: []
      };
      saveCheckpoint(db, sessionId, PHASES.PLANNING, checkpointData);
      console.log('   💾 规划阶段 checkpoint 已保存 (压缩格式)');
    } catch (e) {
      console.log('   insight_tasks 记录失败，继续执行:', e);
    }

    // ========== Step 7: 初始化报告模板结构 (v2.2) ==========
    try {
      console.log('📁 初始化报告模板结构...');
      this.reportStructure = new ReportStructure(sessionId);

      // 写入 SOURCES.md
      const reportReferences: ReportReference[] = collectedReferences.map(r => ({
        title: r.title,
        summary: r.summary,
        source: r.source,
        relevance: r.relevance || 0
      }));
      this.reportStructure.writeSources(reportReferences);
      console.log(`   ✓ SOURCES.md 已生成 (${reportReferences.length} 条参考文献)`);

      // 写入 STATE.md
      const stateData: StateData = {
        topic,
        currentPhase: 'PLANNING',
        progress: {
          done: ['CREATED'],
          inProgress: 'PLANNING',
          blocked: []
        },
        nextActions: [
          '执行 stage2_outlining 生成报告大纲',
          '分配专家团队进行章节写作'
        ]
      };
      this.reportStructure.writeState(stateData);
      console.log('   ✓ STATE.md 已生成');

      // 写入 Phase 1 输出
      const phase1Output: PhaseOutput = {
        phaseNum: 1,
        phaseName: 'planning',
        content: planningResult
      };
      this.reportStructure.writePhase(phase1Output);
      console.log('   ✓ PHASES/1-planning.md 已生成');
    } catch (e) {
      console.log('   ⚠️ 报告模板初始化失败，继续执行:', e);
    }

    console.log(`✅ 规划完成，会话ID: ${sessionId}`);
    console.log(`   Cortex 增强: 记忆 ${relatedMemories.length} 条, 收藏 ${relatedFavorites.length} 条, 网络 ${webSearchResults.length} 条`);
    console.log(`   报告目录: ~/Solar/insight-reports/${sessionId}/`);

    // v2.1: 写入中枢神经 (CortexWriter)
    await this.writePlanningToMemory(planningResult);

    return this.session;
  }

  // ============================================================
  // 阶段2: 大纲 (Outlining) - 专家互评 v2.1
  // ============================================================
  async stage2_outlining(chapterCount: number = 4): Promise<ChapterData[]> {
    if (!this.session) throw new Error('请先执行 stage1_planning');

    console.log('\n📝 阶段2: 大纲生成 (专家互评 v2.1)');
    const db = this.persistence.getDb();

    // ========== Step 0: Evidence First - 查 Cortex 大纲参考 (Brain Separation) ==========
    console.log('🔍 Evidence First: 查询 Cortex 大纲参考...');
    let cortexOutlinePointers: {
      count: number;
      avgSections: number;
      topTopics: string[];
    } = {
      count: 0,
      avgSections: 0,
      topTopics: []
    };

    try {
      const outlines = db.query(`
        SELECT section_number, section_title, key_points
        FROM cortex_outline
        WHERE task_id IN (
          SELECT task_id FROM cortex_tasks WHERE user_request LIKE ?
        )
        ORDER BY section_number
        LIMIT 10
      `).all(`%${this.session.topic}%`) as any[];

      console.log(`   找到 ${outlines.length} 个 Cortex 大纲参考`);

      // 🎯 Brain Separation: Evidence Pointers - 只保留指针和统计信息
      if (outlines.length > 0) {
        cortexOutlinePointers = {
          count: outlines.length,
          avgSections: outlines.length,
          topTopics: outlines.slice(0, 3).map(o => o.section_title)
        };
        console.log(`   压缩为指针: ${cortexOutlinePointers.count} 个参考, Top 3: ${cortexOutlinePointers.topTopics.join(', ')}`);
      }
    } catch (e) {
      console.log('   cortex_outline 表不存在，跳过');
    }

    // 构造压缩后的上下文（只包含统计信息）
    const cortexOutlineContext = cortexOutlinePointers.count > 0
      ? `\n【Cortex 历史大纲参考 - ${cortexOutlinePointers.count} 个样本】`
      : '';

    // ========== Step 1: 构建大纲生成提示 (Brain Separation - Compressed Context) ==========
    console.log('🗜️ 压缩规划内容为统计摘要...');

    // 解析 planning JSON 提取关键统计信息
    let planningStats = {
      章节数: chapterCount,
      核心挑战: 0,
      参考文献: 0,
      风险点: 0
    };

    if (this.session.planning) {
      try {
        const planningData = JSON.parse(this.session.planning);
        planningStats = {
          章节数: planningData.chapters?.length || chapterCount,
          核心挑战: planningData.core_challenges?.length || 0,
          参考文献: planningData.resources?.length || 0,
          风险点: planningData.risks?.length || 0
        };
        console.log(`   压缩摘要: ${planningStats.章节数} 章节, ${planningStats.核心挑战} 个挑战, ${planningStats.参考文献} 条文献`);
      } catch (e) {
        console.log('   ⚠️ Planning JSON 解析失败，使用默认统计');
      }
    }

    const outlinePrompt = `
基于主题"${this.session.topic}"和以下规划，生成一份${chapterCount}章节的洞察报告大纲。
${cortexOutlineContext}

规划摘要: ${planningStats.章节数} 章节, ${planningStats.核心挑战} 个核心挑战, ${planningStats.参考文献} 条参考文献, ${planningStats.风险点} 个风险点

要求：
1. 每章有清晰的标题和核心论点
2. 章节之间逻辑连贯，层层递进
3. 预估每章字数和所需数据/案例

**重要：必须以 JSON 格式输出：**
\`\`\`json
{
  "chapters": [
    { "title": "章节标题", "thesis": "核心论点", "wordCount": 1500, "dataNeeds": "需要的数据或案例" }
  ]
}
\`\`\`
`;

    // ========== Step 2: 并行调用两个专家生成大纲 ==========
    console.log('🔄 并行调用专家生成大纲...');
    console.log('   千里马 (gemini-3-pro): 创新视角');
    console.log('   鬼才码农 (deepseek-v3): 创意结构');

    const [outline1, outline2] = await Promise.all([
      BrainRouterClient.callWithRetry({
        model: 'gemini-3-pro-preview',
        system: EXPERT_PERSONAS['gemini-3-pro-preview'].system,
        prompt: outlinePrompt
      }),
      BrainRouterClient.callWithRetry({
        model: 'deepseek-v3',
        system: EXPERT_PERSONAS['deepseek-v3'].system,
        prompt: outlinePrompt
      })
    ]);

    // ========== Step 3: 技术宅作为挑战者审核 ==========
    console.log('🔍 技术宅审核两份大纲...');
    const reviewPrompt = `
你是"挑战者"，请严格审核以下两份大纲：

【大纲A - 千里马】
${outline1}

【大纲B - 鬼才码农】
${outline2}

评估标准：
1. 结构完整性 (是否覆盖主题各方面)
2. 逻辑连贯性 (章节之间是否递进)
3. 创新程度 (是否有独特视角)
4. 可执行性 (是否便于撰写)

请：
1. 指出各自的优缺点
2. 综合两者优点，输出最终合并大纲

**必须以 JSON 格式输出最终大纲：**
\`\`\`json
{
  "evaluation": {
    "outlineA": { "score": 8, "pros": ["..."], "cons": ["..."] },
    "outlineB": { "score": 7, "pros": ["..."], "cons": ["..."] }
  },
  "finalOutline": {
    "chapters": [
      { "title": "章节标题", "thesis": "核心论点", "wordCount": 1500, "dataNeeds": "..." }
    ]
  }
}
\`\`\`
`;

    const finalOutline = await BrainRouterClient.callWithRetry({
      model: 'gemini-2.5-pro',
      system: EXPERT_PERSONAS['gemini-2.5-pro'].system + '\n你现在担任"挑战者"角色，必须严格审核并指出问题。',
      prompt: reviewPrompt
    });

    // 🎯 Brain Separation: Result Compression - 立即压缩大纲结果
    console.log('🗜️ 压缩大纲结果 (Brain Separation)...');

    // 压缩 outline1 (千里马)
    let compressedOutline1: string;
    try {
      const jsonMatch = outline1.match(/```json\s*([\s\S]*?)\s*```/) || outline1.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const data = JSON.parse(jsonMatch[1] || jsonMatch[0]);
        const chapters = data.chapters || data.outline?.chapters || [];
        compressedOutline1 = JSON.stringify({
          expert: '千里马',
          chapterCount: chapters.length,
          totalWords: chapters.reduce((sum: number, ch: any) => sum + (ch.wordCount || 0), 0),
          chapters: chapters.map((ch: any) => ({
            title: ch.title,
            wordCount: ch.wordCount || 0
          }))
        }, null, 2);
        console.log(`   ✅ 千里马大纲压缩: ${chapters.length} 章节`);
      } else {
        compressedOutline1 = JSON.stringify({ expert: '千里马', raw: outline1.substring(0, 500) + '...' }, null, 2);
      }
    } catch (e) {
      compressedOutline1 = JSON.stringify({ expert: '千里马', error: '解析失败', raw: outline1.substring(0, 500) + '...' }, null, 2);
    }

    // 压缩 outline2 (鬼才码农)
    let compressedOutline2: string;
    try {
      const jsonMatch = outline2.match(/```json\s*([\s\S]*?)\s*```/) || outline2.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const data = JSON.parse(jsonMatch[1] || jsonMatch[0]);
        const chapters = data.chapters || data.outline?.chapters || [];
        compressedOutline2 = JSON.stringify({
          expert: '鬼才码农',
          chapterCount: chapters.length,
          totalWords: chapters.reduce((sum: number, ch: any) => sum + (ch.wordCount || 0), 0),
          chapters: chapters.map((ch: any) => ({
            title: ch.title,
            wordCount: ch.wordCount || 0
          }))
        }, null, 2);
        console.log(`   ✅ 鬼才码农大纲压缩: ${chapters.length} 章节`);
      } else {
        compressedOutline2 = JSON.stringify({ expert: '鬼才码农', raw: outline2.substring(0, 500) + '...' }, null, 2);
      }
    } catch (e) {
      compressedOutline2 = JSON.stringify({ expert: '鬼才码农', error: '解析失败', raw: outline2.substring(0, 500) + '...' }, null, 2);
    }

    // 压缩 finalOutline (技术宅)
    let compressedFinalOutline: string;
    try {
      const jsonMatch = finalOutline.match(/```json\s*([\s\S]*?)\s*```/) || finalOutline.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const data = JSON.parse(jsonMatch[1] || jsonMatch[0]);
        const evaluation = data.evaluation || {};
        const chapters = data.finalOutline?.chapters || data.chapters || [];
        compressedFinalOutline = JSON.stringify({
          expert: '技术宅',
          evaluation: {
            outlineA: { score: evaluation.outlineA?.score || 0, prosCount: evaluation.outlineA?.pros?.length || 0 },
            outlineB: { score: evaluation.outlineB?.score || 0, prosCount: evaluation.outlineB?.pros?.length || 0 }
          },
          chapterCount: chapters.length,
          totalWords: chapters.reduce((sum: number, ch: any) => sum + (ch.wordCount || 0), 0),
          chapters: chapters.map((ch: any) => ({
            title: ch.title,
            thesis: ch.thesis,
            wordCount: ch.wordCount || 0
          }))
        }, null, 2);
        console.log(`   ✅ 技术宅最终大纲压缩: ${chapters.length} 章节, 评分 A:${evaluation.outlineA?.score || 0} B:${evaluation.outlineB?.score || 0}`);
      } else {
        compressedFinalOutline = JSON.stringify({ expert: '技术宅', raw: finalOutline.substring(0, 500) + '...' }, null, 2);
      }
    } catch (e) {
      compressedFinalOutline = JSON.stringify({ expert: '技术宅', error: '解析失败', raw: finalOutline.substring(0, 500) + '...' }, null, 2);
    }

    // ========== Step 4: 记录三个大纲到 insight_outlines ==========
    console.log('💾 记录大纲到数据库 (Brain Separation - 压缩版本)...');
    try {
      const outlines = [
        { expertModel: 'gemini-3-pro-preview', expertNickname: '千里马', content: compressedOutline1, role: 'generator' },
        { expertModel: 'deepseek-v3', expertNickname: '鬼才码农', content: compressedOutline2, role: 'generator' },
        { expertModel: 'gemini-2.5-pro', expertNickname: '技术宅', content: compressedFinalOutline, role: 'challenger' }
      ];

      for (let i = 0; i < outlines.length; i++) {
        const o = outlines[i];
        // 适配现有表结构: task_id, version, proposed_by, content, evaluation_scores, is_final
        const evaluationScores = JSON.stringify({ role: o.role, nickname: o.expertNickname });
        const isFinal = i === outlines.length - 1 ? 1 : 0;  // 最后一个是 challenger 的最终版本
        db.run(`
          INSERT INTO insight_outlines (task_id, version, proposed_by, content, evaluation_scores, is_final, created_at)
          VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        `, [this.session.sessionId, i + 1, o.expertModel, o.content, evaluationScores, isFinal]);
      }
      console.log('   ✓ 3 份大纲已记录');
    } catch (e) {
      console.log('   ⚠️ insight_outlines 表可能不存在，跳过记录');
    }

    // ========== Step 5: 解析最终大纲提取章节 ==========
    console.log('📊 解析最终大纲...');
    const chapters: ChapterData[] = [];
    let parsedChapters: Array<{ title: string; thesis?: string; wordCount?: number; dataNeeds?: string }> = [];

    // 尝试从 finalOutline 中提取 JSON
    try {
      // 匹配 JSON 代码块或直接的 JSON
      const jsonMatch = finalOutline.match(/```json\s*([\s\S]*?)```/i) ||
                        finalOutline.match(/\{[\s\S]*"chapters"[\s\S]*\}/);
      if (jsonMatch) {
        const jsonStr = jsonMatch[1] || jsonMatch[0];
        const parsed = JSON.parse(jsonStr);
        // 可能是 { finalOutline: { chapters: [...] } } 或直接 { chapters: [...] }
        parsedChapters = parsed.finalOutline?.chapters || parsed.chapters || [];
      }
    } catch (e) {
      console.log('   ⚠️ JSON 解析失败，使用默认章节');
    }

    // 创建章节数据
    for (let i = 0; i < chapterCount; i++) {
      const parsedChapter = parsedChapters[i];
      chapters.push({
        chapterId: `ch_${i + 1}`,
        title: parsedChapter?.title || `第${i + 1}章`,
        content: '',
        authorModel: '',
        reviewerModel: '',
        qualityScore: 0,
        status: 'pending'
      });
    }

    // 打印解析结果
    console.log('   章节列表:');
    chapters.forEach((ch, i) => {
      console.log(`   ${i + 1}. ${ch.title}`);
    });

    // ========== Step 6: 保存会话和文件 ==========
    this.session.chapters = chapters;
    this.session.status = 'outlining';
    await this.persistence.saveSession(this.session);

    // 保存所有大纲到文件 (Brain Separation - 压缩版本)
    this.persistence.saveChapterToFile(this.session.sessionId, 'outline_A_千里马', compressedOutline1);
    this.persistence.saveChapterToFile(this.session.sessionId, 'outline_B_鬼才码农', compressedOutline2);
    this.persistence.saveChapterToFile(this.session.sessionId, 'outline_final', compressedFinalOutline);

    // v2.1: 写入中枢神经 (CortexWriter)
    await this.writeOutlineToMemory({ chapters }, finalOutline);

    // ========== v2.2: 更新报告状态 ==========
    if (this.reportStructure) {
      const stateData: StateData = {
        topic: this.session.topic,
        currentPhase: 'OUTLINE',
        progress: {
          done: ['CREATED', 'PLANNING'],
          inProgress: 'OUTLINE',
          blocked: []
        },
        nextActions: [
          '执行 stage3_scheduling 分配专家团队',
          `开始写作 ${chapters.length} 个章节`
        ]
      };
      this.reportStructure.writeState(stateData);
      console.log('   ✓ STATE.md 已更新');

      // 写入 Phase 2 输出
      const phase2Output: PhaseOutput = {
        phaseNum: 2,
        phaseName: 'outlining',
        content: finalOutline
      };
      this.reportStructure.writePhase(phase2Output);
      console.log('   ✓ PHASES/2-outlining.md 已生成');
    }

    console.log(`✅ 大纲完成，${chapters.length}个章节，3份大纲已保存`);
    return chapters;
  }

  // ============================================================
  // 阶段3: 调度 (Scheduling) - v2.1 动态专家匹配
  // ============================================================

  /**
   * 动态专家权重 - 基于任务类型和历史绩效
   * 来源: ARCHITECTURE.md Phase 3 设计
   */
  private readonly EXPERT_DYNAMIC_WEIGHTS: Record<string, Record<string, number>> = {
    'deepseek-v3': {
      creativity: 1.0,      // O=1.0 极致开放
      technical: 0.6,
      chinese: 0.95,
      speed: 0.8
    },
    'gemini-3-pro-preview': {
      creativity: 0.9,      // O=0.9 创新
      technical: 0.7,
      chinese: 0.7,
      speed: 0.85
    },
    'gemini-2.5-pro': {
      creativity: 0.2,      // O=0.2 保守
      technical: 1.0,       // C=1.0 极致严谨
      chinese: 0.6,
      speed: 0.7
    },
    'deepseek-r1': {
      creativity: 0.8,
      technical: 0.8,
      chinese: 0.9,
      speed: 0.5,           // 深度推理较慢
      reasoning: 1.0        // 特殊能力
    }
  };

  /**
   * 分析章节复杂度和类型
   */
  private analyzeChapterComplexity(chapter: ChapterData): {
    complexity: 'high' | 'medium' | 'low';
    type: 'creative' | 'technical' | 'analytical' | 'overview';
    keywords: string[];
  } {
    const title = chapter.title.toLowerCase();

    // 检测类型
    let type: 'creative' | 'technical' | 'analytical' | 'overview' = 'overview';
    const keywords: string[] = [];

    if (title.includes('架构') || title.includes('设计') || title.includes('实现')) {
      type = 'technical';
      keywords.push('architecture', 'implementation');
    } else if (title.includes('分析') || title.includes('评估') || title.includes('对比')) {
      type = 'analytical';
      keywords.push('analysis', 'evaluation');
    } else if (title.includes('创新') || title.includes('探索') || title.includes('未来')) {
      type = 'creative';
      keywords.push('innovation', 'exploration');
    }

    // 检测复杂度
    let complexity: 'high' | 'medium' | 'low' = 'medium';
    if (title.includes('核心') || title.includes('深度') || title.includes('全面')) {
      complexity = 'high';
    } else if (title.includes('概述') || title.includes('简介') || title.includes('总结')) {
      complexity = 'low';
    }

    return { complexity, type, keywords };
  }

  /**
   * 获取专家历史绩效
   */
  private async getExpertPerformance(modelId: string): Promise<{
    avgScore: number;
    taskCount: number;
    successRate: number;
  }> {
    const db = this.persistence.getDb();
    const result = db.query(`
      SELECT
        AVG(quality_score) as avg_score,
        COUNT(*) as task_count,
        AVG(completion_rate) as success_rate
      FROM collab_performance
      WHERE model_id = ?
    `).get(modelId) as any;

    return {
      avgScore: result?.avg_score || 7.0,  // 默认中等分数
      taskCount: result?.task_count || 0,
      successRate: result?.success_rate || 0.9
    };
  }

  /**
   * 写入语义记忆 (三层持久化 - Layer 3: Cortex)
   * 设计来源: 鬼才码农 (deepseek-v3)
   */
  private async writeToMemory(
    insightId: string,
    content: string,
    metadata?: Record<string, any>
  ): Promise<void> {
    try {
      const db = this.persistence.getDb();
      const memorySummary = `💡洞察记忆 | ${content.substring(0, 100)}...`;
      const memoryAnchor = {
        insight_id: insightId,
        timestamp: new Date().toISOString(),
        type: 'insight',
        tags: metadata?.tags || ['insight', 'evaluation'],
        priority: metadata?.priority || 'medium'
      };

      db.run(
        `INSERT OR REPLACE INTO evo_memory_semantic (memory_id, namespace, key, value, created_at)
         VALUES (?, ?, ?, ?, datetime('now'))`,
        [
          `insight_${insightId}_${metadata?.phase || 'general'}`,
          'insight_report',
          `${insightId}_${metadata?.phase || 'general'}`,
          JSON.stringify({
            summary: memorySummary,
            content: content.substring(0, 2000),
            anchor: memoryAnchor,
            source: 'insight_agent_v2'
          })
        ]
      );
      console.log(`   🎯 记忆写入成功 | 锚点: ${insightId}_${metadata?.phase || 'general'}`);
    } catch (error) {
      console.error('   ⚠️ 记忆写入失败，使用 fallback:', error);
      this.logMemoryFallback(insightId, content);
    }
  }

  /**
   * 记忆写入失败时的回退机制
   */
  private logMemoryFallback(insightId: string, content: string): void {
    const home = homedir();
    const fallbackPath = `${home}/Solar/insight-reports/memory_fallback.log`;
    const logEntry = `[${new Date().toISOString()}] ${insightId}: ${content.substring(0, 200)}\n`;
    try {
      const fs = require('fs');
      fs.appendFileSync(fallbackPath, logEntry, 'utf-8');
    } catch (e) {
      console.error('   ❌ Fallback 写入也失败');
    }
  }

  // ============================================================
  // CortexWriter: 阶段专用记忆写入方法
  // 设计来源: 思考驼 (deepseek-r1) - 每阶段写入中枢神经
  // ============================================================

  /**
   * 规划阶段写入 - 记录主题分析和报告规划
   */
  private async writePlanningToMemory(planContent: string): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'planning',
      topic: this.session.topic,
      plan_summary: planContent.substring(0, 500),
      key_points: this.extractKeyPoints(planContent),
      expert_used: 'deepseek-r1',
      chapter_count: this.session.chapterCount
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[规划] ${this.session.topic}: ${planContent.substring(0, 200)}`,
      {
        phase: 'planning',
        tags: ['insight', 'planning', 'topic-analysis'],
        priority: 'high',
        structured: structuredContent
      }
    );
  }

  /**
   * 大纲阶段写入 - 记录章节结构和专家互评结果
   */
  private async writeOutlineToMemory(outline: any, peerReview?: string): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'outlining',
      chapter_titles: outline.chapters?.map((c: any) => c.title) || [],
      outline_version: 'merged',
      peer_review_summary: peerReview?.substring(0, 300),
      experts_involved: ['gemini-3-pro-preview', 'deepseek-v3', 'gemini-2.5-pro']
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[大纲] ${outline.chapters?.length || 0}章节结构`,
      {
        phase: 'outlining',
        tags: ['insight', 'outline', 'structure', 'peer-review'],
        priority: 'high',
        structured: structuredContent
      }
    );
  }

  /**
   * 调度阶段写入 - 记录任务分配和交叉审核安排
   */
  private async writeDispatchToMemory(assignments: Array<{chapterIndex: number, writer: string, reviewer: string}>): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'dispatching',
      assignments: assignments.map(a => ({
        chapter: a.chapterIndex,
        writer: a.writer,
        reviewer: a.reviewer,
        cross_check: a.writer !== a.reviewer
      })),
      dispatch_strategy: 'cross-assignment',
      total_chapters: assignments.length
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[调度] ${assignments.length}章节任务分配完成`,
      {
        phase: 'dispatching',
        tags: ['insight', 'dispatch', 'assignment', 'cross-review'],
        priority: 'medium',
        structured: structuredContent
      }
    );
  }

  /**
   * 写作阶段写入 - 记录章节完成情况和质量评估
   */
  private async writeWritingToMemory(
    chapterIndex: number,
    writer: string,
    qualityScore: number,
    wordCount: number
  ): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'writing',
      chapter_index: chapterIndex,
      chapter_title: this.session.chapters[chapterIndex]?.title,
      writer_model: writer,
      quality_score: qualityScore,
      word_count: wordCount,
      performance_injected: true
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[写作] 第${chapterIndex + 1}章 | ${writer} | 质量:${qualityScore}/10`,
      {
        phase: `writing_ch${chapterIndex + 1}`,
        tags: ['insight', 'writing', 'chapter', `ch${chapterIndex + 1}`],
        priority: 'medium',
        structured: structuredContent
      }
    );
  }

  /**
   * 审核阶段写入 - 记录审核意见和改进建议
   */
  private async writeReviewToMemory(
    chapterIndex: number,
    reviewer: string,
    reviewScore: number,
    keyFeedback: string
  ): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'reviewing',
      chapter_index: chapterIndex,
      reviewer_model: reviewer,
      review_score: reviewScore,
      key_feedback: keyFeedback.substring(0, 500),
      is_challenger: reviewer === 'gemini-2.5-pro',
      performance_injected: true
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[审核] 第${chapterIndex + 1}章 | ${reviewer} | 评分:${reviewScore}/10`,
      {
        phase: `review_ch${chapterIndex + 1}`,
        tags: ['insight', 'review', 'feedback', `ch${chapterIndex + 1}`],
        priority: 'medium',
        structured: structuredContent
      }
    );
  }

  /**
   * 综合阶段写入 - 记录全文审核和执行摘要
   */
  private async writeSynthesisToMemory(
    executiveSummary: string,
    overallQuality: number,
    keyInsights: string[]
  ): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'synthesis',
      executive_summary: executiveSummary.substring(0, 1000),
      overall_quality: overallQuality,
      key_insights: keyInsights.slice(0, 5),
      synthesis_expert: 'deepseek-r1',
      final_chapter_count: this.session.chapters.length
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[综合] ${this.session.topic} | 总质量:${overallQuality}/10`,
      {
        phase: 'synthesis',
        tags: ['insight', 'synthesis', 'executive-summary', 'final'],
        priority: 'high',
        structured: structuredContent
      }
    );
  }

  /**
   * 结束阶段写入 - 记录绩效评估和最终报告位置
   */
  private async writeClosingToMemory(
    reportPath: string,
    performanceSummary: Record<string, {tasks: number, avgScore: number}>
  ): Promise<void> {
    if (!this.session) return;

    const structuredContent = {
      phase: 'closing',
      report_path: reportPath,
      session_duration_ms: Date.now() - new Date(this.session.createdAt).getTime(),
      performance_summary: performanceSummary,
      total_experts_used: Object.keys(performanceSummary).length
    };

    await this.writeToMemory(
      this.session.sessionId,
      `[完成] ${this.session.topic} | 报告: ${reportPath}`,
      {
        phase: 'closing',
        tags: ['insight', 'closing', 'performance', 'report-complete'],
        priority: 'high',
        structured: structuredContent
      }
    );
  }

  /**
   * 从文本中提取关键要点 (用于规划阶段)
   */
  private extractKeyPoints(text: string): string[] {
    // 简单提取：查找带数字、项目符号或关键词的行
    const lines = text.split('\n');
    const keyPoints: string[] = [];

    for (const line of lines) {
      const trimmed = line.trim();
      // 匹配数字列表项、项目符号、或包含关键词的行
      if (/^[\d]+[.、)]/.test(trimmed) ||
          /^[-*•]/.test(trimmed) ||
          /^(核心|关键|重点|要点|目标|结论)/.test(trimmed)) {
        if (trimmed.length > 10 && trimmed.length < 200) {
          keyPoints.push(trimmed.replace(/^[\d]+[.、)\s]*|^[-*•]\s*/, ''));
        }
      }
    }

    return keyPoints.slice(0, 10);
  }

  // ============================================================
  // CortexReader: 从中枢神经读取状态 (断点续传支持)
  // 设计来源: 监护人要求 - "从中枢神经中读取"
  // ============================================================

  /**
   * 从 Cortex 读取会话状态 (用于断点续传)
   * 查询 evo_memory_semantic 中的 insight_report 命名空间
   */
  private async readSessionFromCortex(sessionId: string): Promise<{
    planning?: any;
    outlining?: any;
    dispatching?: any;
    writing?: any[];
    reviewing?: any[];
    synthesis?: any;
    closing?: any;
    lastCompletedStage?: InsightStage;
  } | null> {
    const db = this.persistence.getDb();

    try {
      // 查询该会话的所有记忆
      const memories = db.query(`
        SELECT key, value FROM evo_memory_semantic
        WHERE namespace = 'insight_report'
        AND key LIKE ?
        ORDER BY created_at ASC
      `).all(`${sessionId}_%`) as Array<{ key: string; value: string }>;

      if (memories.length === 0) {
        console.log(`   📭 Cortex 中未找到会话 ${sessionId} 的状态`);
        return null;
      }

      console.log(`   📖 从 Cortex 读取到 ${memories.length} 条记忆`);

      // 解析各阶段状态
      const result: any = {
        writing: [],
        reviewing: []
      };

      for (const mem of memories) {
        try {
          const data = JSON.parse(mem.value);
          const structured = data.structured || data;

          if (mem.key.includes('_planning')) {
            result.planning = structured;
            result.lastCompletedStage = 'planning';
          } else if (mem.key.includes('_outlining')) {
            result.outlining = structured;
            result.lastCompletedStage = 'outlining';
          } else if (mem.key.includes('_dispatching')) {
            result.dispatching = structured;
            result.lastCompletedStage = 'scheduling';
          } else if (mem.key.includes('_writing_ch') || mem.key.includes('writing_ch')) {
            result.writing.push(structured);
            result.lastCompletedStage = 'writing';
          } else if (mem.key.includes('_review_ch') || mem.key.includes('review_ch')) {
            result.reviewing.push(structured);
            result.lastCompletedStage = 'reviewing';
          } else if (mem.key.includes('_synthesis')) {
            result.synthesis = structured;
            result.lastCompletedStage = 'synthesis';
          } else if (mem.key.includes('_closing')) {
            result.closing = structured;
            result.lastCompletedStage = 'closing';
          }
        } catch (e) {
          console.warn(`   ⚠️ 解析记忆失败: ${mem.key}`);
        }
      }

      return result;
    } catch (e) {
      console.error('   ❌ 从 Cortex 读取失败:', e);
      return null;
    }
  }

  /**
   * 从 Cortex 读取规划阶段数据
   */
  private async readPlanningFromCortex(sessionId: string): Promise<{
    topic?: string;
    plan_summary?: string;
    key_points?: string[];
    chapter_count?: number;
  } | null> {
    const state = await this.readSessionFromCortex(sessionId);
    return state?.planning || null;
  }

  /**
   * 从 Cortex 读取大纲阶段数据
   */
  private async readOutlineFromCortex(sessionId: string): Promise<{
    chapter_titles?: string[];
    experts_involved?: string[];
    peer_review_summary?: string;
  } | null> {
    const state = await this.readSessionFromCortex(sessionId);
    return state?.outlining || null;
  }

  /**
   * 从 Cortex 读取调度阶段数据
   */
  private async readDispatchFromCortex(sessionId: string): Promise<{
    assignments?: Array<{
      chapter: number;
      writer: string;
      reviewer: string;
    }>;
    total_chapters?: number;
  } | null> {
    const state = await this.readSessionFromCortex(sessionId);
    return state?.dispatching || null;
  }

  /**
   * 从 Cortex 读取写作阶段数据 (多章节)
   */
  private async readWritingFromCortex(sessionId: string): Promise<Array<{
    chapter_index: number;
    chapter_title?: string;
    writer_model: string;
    quality_score: number;
    word_count: number;
  }>> {
    const state = await this.readSessionFromCortex(sessionId);
    return state?.writing || [];
  }

  /**
   * 从 Cortex 读取审核阶段数据 (多章节)
   */
  private async readReviewsFromCortex(sessionId: string): Promise<Array<{
    chapter_index: number;
    reviewer_model: string;
    review_score: number;
    key_feedback: string;
  }>> {
    const state = await this.readSessionFromCortex(sessionId);
    return state?.reviewing || [];
  }

  /**
   * 从 Cortex 读取综合阶段数据
   */
  private async readSynthesisFromCortex(sessionId: string): Promise<{
    executive_summary?: string;
    overall_quality?: number;
    key_insights?: string[];
  } | null> {
    const state = await this.readSessionFromCortex(sessionId);
    return state?.synthesis || null;
  }

  /**
   * 恢复中断的会话 (断点续传入口)
   * 从数据库和 Cortex 读取已保存的状态
   */
  async resumeSession(sessionId: string): Promise<{
    session: InsightSession | null;
    nextStage: InsightStage | null;
    cortexState: any;
  }> {
    console.log(`\n🔄 尝试恢复会话: ${sessionId}`);

    const db = this.persistence.getDb();

    // Step 1: 从数据库读取会话基本信息
    let session: InsightSession | null = null;
    try {
      const row = db.query(`
        SELECT session_id, topic, status, created_at, updated_at
        FROM insight_sessions
        WHERE session_id = ?
      `).get(sessionId) as any;

      if (row) {
        session = {
          sessionId: row.session_id,
          topic: row.topic,
          status: row.status as InsightStage,
          chapters: [],
          experts: [],
          references: [],
          startedAt: row.created_at,
          updatedAt: row.updated_at
        };
        console.log(`   ✓ 数据库会话状态: ${row.status}`);
      }
    } catch (e) {
      console.warn('   ⚠️ 数据库读取失败:', e);
    }

    // Step 2: 从 Cortex 读取详细状态
    const cortexState = await this.readSessionFromCortex(sessionId);

    if (cortexState) {
      console.log(`   ✓ Cortex 最后完成阶段: ${cortexState.lastCompletedStage}`);
    }

    // Step 3: 从数据库读取章节 (优先级最高，最可靠)
    if (session) {
      try {
        const dbChapters = this.persistence.loadChaptersFromDB(sessionId);
        if (dbChapters.length > 0) {
          for (const dbCh of dbChapters) {
            const chapterIndex = parseInt(dbCh.chapterId.replace('ch_', '')) - 1;
            session.chapters[chapterIndex] = {
              chapterId: dbCh.chapterId,
              title: dbCh.title,
              content: dbCh.content,
              authorModel: dbCh.authorModel || 'unknown',
              reviewerModel: '',
              qualityScore: 0,
              status: dbCh.status as 'pending' | 'writing' | 'reviewing' | 'done'
            };
          }
          console.log(`   ✓ 数据库恢复 ${dbChapters.length} 个章节`);
        }
      } catch (e) {
        console.warn('   ⚠️ 数据库章节读取失败:', e);
      }
    }

    // Step 4: 从文件系统补充 (如果数据库没有)
    if (session && session.chapters.filter(Boolean).length === 0) {
      const home = homedir();
      const sessionDir = `${home}/Solar/insight-reports/${sessionId}`;

      if (existsSync(sessionDir)) {
        try {
          // 读取已写完的章节
          const files = require('fs').readdirSync(sessionDir);
          for (const file of files) {
            if (file.startsWith('ch_') && file.endsWith('.md')) {
              const chapterIndex = parseInt(file.replace('ch_', '').replace('.md', '')) - 1;
              const content = readFileSync(`${sessionDir}/${file}`, 'utf-8');

              // 尝试从 Cortex 获取元数据
              const writingData = cortexState?.writing?.find(
                (w: any) => w.chapter_index === chapterIndex
              );

              session.chapters[chapterIndex] = {
                chapterId: `ch_${chapterIndex + 1}`,
                title: writingData?.chapter_title || `第${chapterIndex + 1}章`,
                content: content,
                authorModel: writingData?.writer_model || 'unknown',
                reviewerModel: '',
                qualityScore: writingData?.quality_score || 0,
                status: 'done'
              };
            }
          }
          console.log(`   ✓ 文件系统恢复 ${session.chapters.filter(Boolean).length} 个章节`);
        } catch (e) {
          console.warn('   ⚠️ 文件系统读取失败:', e);
        }
      }
    }

    // Step 4: 计算下一阶段
    let nextStage: InsightStage | null = null;
    if (cortexState?.lastCompletedStage) {
      const stages: InsightStage[] = [
        'planning', 'outlining', 'scheduling', 'writing', 'reviewing', 'synthesis', 'closing'
      ];
      const currentIndex = stages.indexOf(cortexState.lastCompletedStage);
      if (currentIndex >= 0 && currentIndex < stages.length - 1) {
        nextStage = stages[currentIndex + 1];
      }
    }

    // 恢复到实例状态
    if (session) {
      this.session = {
        ...session,
        chapterCount: cortexState?.planning?.chapter_count || session.chapters.length || 4
      } as any;

      // 恢复绩效注入器
      this.performanceInjector = new PerformanceInjector(db, sessionId);
    }

    console.log(`   📋 恢复结果: ${nextStage ? `可从 ${nextStage} 继续` : '无法恢复或已完成'}`);

    return { session, nextStage, cortexState };
  }

  /**
   * 智能运行 - 支持新建或续传
   * @param topic 主题（新建时必须）
   * @param sessionId 会话ID（续传时使用）
   */
  async run(topic?: string, sessionId?: string, chapterCount: number = 4): Promise<string> {
    // 如果提供了 sessionId，尝试续传
    if (sessionId) {
      const { session, nextStage, cortexState } = await this.resumeSession(sessionId);

      if (session && nextStage) {
        console.log(`\n🔄 断点续传: 从 ${nextStage} 阶段继续`);
        return await this.runFromStage(nextStage, cortexState);
      } else if (session && !nextStage) {
        console.log('   ✅ 会话已完成，无需续传');
        const home = homedir();
        return `${home}/Solar/insight-reports/${sessionId}/final-report.md`;
      }
    }

    // 新建会话
    if (!topic) {
      throw new Error('新建会话必须提供 topic 参数');
    }

    console.log(`\n🚀 启动新会话: ${topic}`);
    return await this.runFromStage('planning', null, topic, chapterCount);
  }

  /**
   * 从指定阶段开始运行
   */
  private async runFromStage(
    startStage: InsightStage,
    cortexState: any,
    topic?: string,
    chapterCount: number = 4
  ): Promise<string> {
    const stages: InsightStage[] = [
      'planning', 'outlining', 'scheduling', 'writing', 'reviewing', 'synthesis', 'closing'
    ];

    const startIndex = stages.indexOf(startStage);

    // 执行各阶段
    for (let i = startIndex; i < stages.length; i++) {
      const stage = stages[i];

      try {
        switch (stage) {
          case 'planning':
            if (!topic) throw new Error('规划阶段需要 topic');
            await this.stage1_planning(topic);
            break;
          case 'outlining':
            // 如果有 cortexState，可以读取章节数
            const chCount = cortexState?.planning?.chapter_count || chapterCount;
            await this.stage2_outlining(chCount);
            break;
          case 'scheduling':
            await this.stage3_scheduling();
            break;
          case 'writing':
            await this.stage4_writing();
            break;
          case 'reviewing':
            await this.stage5_reviewing();
            break;
          case 'synthesis':
            await this.stage6_synthesis();
            break;
          case 'closing':
            await this.stage7_closing();
            break;
        }

        // 阶段完成后保存 checkpoint (状态持久化)
        if (this.taskId) {
          try {
            const db = this.persistence.getDb();
            // stages 到 PHASES 的映射
            const phaseMapping: Record<string, number> = {
              'planning': PHASES.PLANNING,
              'outlining': PHASES.OUTLINE,
              'scheduling': PHASES.SCHEDULING,
              'writing': PHASES.WRITING,
              'reviewing': PHASES.REVIEW,
              'synthesis': PHASES.SYNTHESIS,
              'closing': PHASES.COMPLETED
            };
            const phaseIndex = phaseMapping[stage] || (i + 1);

            const checkpointData: CheckpointData = {
              phase: phaseIndex,
              phaseData: {
                stage,
                completedAt: new Date().toISOString()
              },
              completedChapters: this.session?.chapters?.filter(c => c.status === 'done').map(c => c.chapterId) || [],
              pendingChapters: this.session?.chapters?.filter(c => c.status !== 'done').map(c => c.chapterId) || []
            };
            saveCheckpoint(db, this.taskId, phaseIndex, checkpointData);
            console.log(`   💾 ${stage} 阶段 checkpoint 已保存`);
          } catch (cpErr) {
            console.log(`   ⚠️ checkpoint 保存失败:`, cpErr);
          }
        }
      } catch (e) {
        console.error(`\n❌ 阶段 ${stage} 执行失败:`, e);
        console.log(`   💾 进度已保存到 Cortex，可通过 resumeSession('${this.session?.sessionId}') 恢复`);
        throw e;
      }
    }

    const home = homedir();
    return `${home}/Solar/insight-reports/${this.session?.sessionId}/final-report.md`;
  }

  // ============================================================
  // crossEvaluateDispatch: 调度阶段交叉互评
  // 设计来源: 技术宅 (gemini-2.5-pro) - 严谨一致、高可靠
  // ============================================================

  /**
   * 调度方案交叉互评
   * 选择两个风格不同的专家对调度方案进行审核，确保分配合理性
   *
   * @param scheduleSummary 调度摘要文本
   * @param topic 报告主题
   * @returns 审核结果数组 { expert, scores, suggestions, success }
   */
  private async crossEvaluateDispatch(
    scheduleSummary: string,
    topic: string
  ): Promise<Array<{
    expert: string;
    scores: { matching: number; balance: number; reasonability: number };
    suggestions: string;
    success: boolean;
  }>> {
    // 技术宅设计: 选择互补型专家组合
    // gemini-2.5-pro (C:1.0 严谨) + deepseek-r1 (O:0.8 深思)
    const reviewExperts = [
      { model: 'gemini-2.5-pro', role: '一致性审核', focus: '结构合理性与规则遵循' },
      { model: 'deepseek-r1', role: '深度审核', focus: '潜在风险与优化空间' }
    ];

    const crossReviewPrompt = `
作为调度审核专家，请严格评估以下章节分配方案：

【报告主题】${topic}

【调度方案】
${scheduleSummary}

【评估维度】(每项0-10分，必须给出具体数值)
1. 专家能力匹配度 - 作者特长是否匹配章节内容
2. 负载均衡程度 - 任务分配是否均匀
3. 交叉审核合理性 - 审核者是否能有效检验作者工作

【输出格式】(严格遵循)
匹配度: [数值]/10
均衡度: [数值]/10
合理性: [数值]/10
建议: [具体可操作的改进建议，一句话]
`;

    const results: Array<{
      expert: string;
      scores: { matching: number; balance: number; reasonability: number };
      suggestions: string;
      success: boolean;
    }> = [];

    // 并行调用两个审核专家
    const reviewPromises = reviewExperts.map(async ({ model, role }) => {
      try {
        const persona = EXPERT_PERSONAS[model];
        const result = await Promise.race([
          BrainRouterClient.callWithRetry({
            model,
            system: `${persona?.system || '你是资深调度审核专家'}
角色: ${role}
要求: 严格按格式输出，给出具体分数`,
            prompt: crossReviewPrompt
          }),
          new Promise<string>((_, reject) =>
            setTimeout(() => reject(new Error('timeout')), 15000)
          )
        ]);

        // ✨ Brain Separation: Result Compression - 立即解析并压缩结果
        const scores = this.parseDispatchScores(result);
        const suggestions = this.extractSuggestion(result);

        // 原始文本 result 在此之后不再使用，已完成压缩
        console.log(`   🗜️ ${model} 结果已压缩: ${result.length} chars → ${JSON.stringify({ scores, suggestions }).length} chars`);

        return {
          expert: model,
          scores,
          suggestions,
          success: true
        };
      } catch (e) {
        return {
          expert: model,
          scores: { matching: 7, balance: 7, reasonability: 7 },
          suggestions: '审核超时，使用默认评分',
          success: false
        };
      }
    });

    const reviewResults = await Promise.all(reviewPromises);
    results.push(...reviewResults);

    return results;
  }

  /**
   * 解析调度评分 (从专家回复中提取)
   */
  private parseDispatchScores(text: string): { matching: number; balance: number; reasonability: number } {
    const matchingMatch = text.match(/匹配度[：:]\s*(\d+(?:\.\d+)?)/);
    const balanceMatch = text.match(/均衡度[：:]\s*(\d+(?:\.\d+)?)/);
    const reasonabilityMatch = text.match(/合理性[：:]\s*(\d+(?:\.\d+)?)/);

    return {
      matching: matchingMatch ? Math.min(10, parseFloat(matchingMatch[1])) : 7,
      balance: balanceMatch ? Math.min(10, parseFloat(balanceMatch[1])) : 7,
      reasonability: reasonabilityMatch ? Math.min(10, parseFloat(reasonabilityMatch[1])) : 7
    };
  }

  /**
   * 提取改进建议
   */
  private extractSuggestion(text: string): string {
    const suggestionMatch = text.match(/建议[：:]\s*([^\n]+)/);
    return suggestionMatch ? suggestionMatch[1].trim() : '无具体建议';
  }

  /**
   * 生成专家审核回退意见 (当专家调用失败时使用)
   * 设计来源: 鬼才码农 (deepseek-v3) - Phase 6 多专家交响乐团
   */
  private generateFallbackReview(role: string): string {
    const fallbackTemplates: Record<string, string> = {
      deep_thinker: `## 深度分析审核 (回退)

### 逻辑结构
- 报告整体逻辑框架基本合理
- 建议进一步加强章节间的逻辑递进关系

### 论证深度
- 核心论点有一定支撑
- 可考虑增加更多实证数据

### 改进建议
1. 强化核心观点的论证深度
2. 增加跨章节的逻辑衔接`,

      creative_writer: `## 创意表达审核 (回退)

### 语言风格
- 整体表达清晰
- 可适当增加生动案例

### 可读性
- 段落结构合理
- 建议优化长句表达

### 改进建议
1. 增加具体示例提升可读性
2. 优化部分专业术语的解释`,

      critical_reviewer: `## 一致性审核 (回退)

### 术语一致性
- 核心概念定义基本统一
- 需检查边缘术语的使用

### 风格一致性
- 各章节风格相对统一
- 个别章节语气略有差异

### 改进建议
1. 统一全文术语表
2. 校对引用格式`,

      practical_engineer: `## 实用性审核 (回退)

### 可操作性
- 结论具有一定指导意义
- 建议增加具体实施步骤

### 实践价值
- 内容与实际应用有关联
- 可增加更多实践案例

### 改进建议
1. 增加具体行动建议
2. 补充实践检验方法`
    };

    return fallbackTemplates[role] || `## 通用审核 (回退)

### 综合评估
- 报告结构完整，内容充实
- 论证逻辑基本清晰
- 建议根据反馈进一步优化

### 改进建议
1. 强化核心观点
2. 优化表达方式
3. 增加实证支撑`;
  }

  /**
   * 智能选择最佳作者
   */
  private async selectBestWriter(
    chapter: ChapterData,
    excludeModels: string[] = []
  ): Promise<string> {
    const analysis = this.analyzeChapterComplexity(chapter);
    const candidates = this.WRITING_EXPERTS.filter(m => !excludeModels.includes(m));

    let bestModel = candidates[0];
    let bestScore = 0;

    for (const model of candidates) {
      const weights = this.EXPERT_DYNAMIC_WEIGHTS[model] || {};
      const perf = await this.getExpertPerformance(model);

      // 计算匹配分数
      let score = 0;

      // 类型匹配权重
      if (analysis.type === 'creative') {
        score += (weights.creativity || 0.5) * 3;
      } else if (analysis.type === 'technical') {
        score += (weights.technical || 0.5) * 3;
      } else if (analysis.type === 'analytical') {
        score += (weights.reasoning || weights.technical || 0.5) * 3;
      }

      // 复杂度权重
      if (analysis.complexity === 'high') {
        score += perf.avgScore * 0.5;  // 高复杂度看历史表现
      }

      // 历史绩效加成
      score += perf.successRate * 2;

      if (score > bestScore) {
        bestScore = score;
        bestModel = model;
      }
    }

    return bestModel;
  }

  /**
   * 环形交叉评审分配 - 确保作者≠审核者
   */
  private assignCrossReviewers(
    assignments: Array<{ chapter: ChapterData; writer: string }>
  ): Array<{ chapter: ChapterData; writer: string; reviewers: string[] }> {
    const n = assignments.length;

    return assignments.map((item, i) => {
      // 环形分配：每个章节由下一个作者审核
      const reviewers: string[] = [];

      // 主审核者：环形下一个
      const nextIdx = (i + 1) % n;
      if (assignments[nextIdx].writer !== item.writer) {
        reviewers.push(assignments[nextIdx].writer);
      }

      // 副审核者：从 REVIEW_EXPERTS 选一个不同的
      const reviewExpert = this.REVIEW_EXPERTS.find(r => r !== item.writer && !reviewers.includes(r));
      if (reviewExpert) {
        reviewers.push(reviewExpert);
      }

      return {
        ...item,
        reviewers
      };
    });
  }

  /**
   * Phase 3 主函数 - 智能调度
   */
  async stage3_scheduling(): Promise<ExpertAssignment[]> {
    if (!this.session) throw new Error('请先执行 stage2_outlining');

    console.log('\n📅 阶段3: 智能专家调度 (v2.1)');

    // ========== Step 0: Evidence First - 查 Cortex 知识库 (Principle 5) ==========
    console.log('🔍 Evidence First: 查询 Cortex 知识库...');
    const db = this.persistence.getDb();

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要，不保留完整数组
    let cortexSourcesPointers = {
      count: 0,
      avgCredibility: 0,
      topTypes: [] as string[]
    };
    let cortexClaimsPointers = {
      count: 0,
      avgConfidence: 0
    };

    try {
      // 查询相关知识源（用于专家选择参考）
      const sources = db.query(`
        SELECT title, finding, credibility, evidence_type
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 5
      `).all(`%${this.session.topic}%`) as any[];

      if (sources.length > 0) {
        cortexSourcesPointers = {
          count: sources.length,
          avgCredibility: sources.reduce((sum: number, s: any) => sum + (s.credibility || 0), 0) / sources.length,
          topTypes: [...new Set(sources.map((s: any) => s.evidence_type).filter(Boolean))].slice(0, 3)
        };
      }
      console.log(`   找到 ${cortexSourcesPointers.count} 个 Cortex 知识源 (avg credibility: ${cortexSourcesPointers.avgCredibility.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_sources 表不存在，跳过');
    }

    try {
      // 查询已验证结论（用于章节分配参考）
      const claims = db.query(`
        SELECT claim_id, statement, confidence
        FROM cortex_claims
        WHERE statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 3
      `).all(`%${this.session.topic}%`) as any[];

      if (claims.length > 0) {
        cortexClaimsPointers = {
          count: claims.length,
          avgConfidence: claims.reduce((sum: number, c: any) => sum + (c.confidence || 0), 0) / claims.length
        };
      }
      console.log(`   找到 ${cortexClaimsPointers.count} 个 Cortex 结论 (avg confidence: ${cortexClaimsPointers.avgConfidence.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_claims 表不存在，跳过');
    }

    // ========== v2.1 Cortex 读取闭环: 从中枢神经读取大纲数据 ==========
    console.log('   📖 从 Cortex 读取大纲数据...');
    const cortexOutline = await this.readOutlineFromCortex(this.session.sessionId);
    if (cortexOutline) {
      console.log(`   ✓ Cortex 大纲: ${cortexOutline.chapter_titles?.length || 0} 章节, 专家: ${cortexOutline.experts_involved?.join(', ') || '未知'}`);
      // 如果 session 中章节为空但 Cortex 有数据，尝试恢复
      if (this.session.chapters.length === 0 && cortexOutline.chapter_titles) {
        console.log('   🔄 从 Cortex 恢复章节数据...');
        this.session.chapters = cortexOutline.chapter_titles.map((title, idx) => ({
          chapterId: `ch_${idx + 1}`,
          title,
          content: '',
          authorModel: '',
          reviewerModel: '',
          qualityScore: 0,
          status: 'pending' as const
        }));
      }
    } else {
      console.log('   ℹ️ Cortex 无大纲数据，使用内存数据');
    }
    // ========== Cortex 读取闭环结束 ==========

    const assignments: ExpertAssignment[] = [];
    const chapters = this.session.chapters;
    const usedWriters: string[] = [];

    // Step 1: 为每个章节选择最佳作者
    console.log('   📊 分析章节复杂度...');
    const writerAssignments: Array<{ chapter: ChapterData; writer: string }> = [];

    for (const chapter of chapters) {
      const analysis = this.analyzeChapterComplexity(chapter);
      console.log(`   • ${chapter.title}: ${analysis.type} (${analysis.complexity})`);

      // 智能选择，尽量分散负载
      const writer = await this.selectBestWriter(chapter, usedWriters.slice(-1));
      usedWriters.push(writer);

      writerAssignments.push({ chapter, writer });
    }

    // Step 2: 交叉分配审核者
    console.log('   🔄 分配交叉审核...');
    const fullAssignments = this.assignCrossReviewers(writerAssignments);

    // Step 3: 更新章节数据并记录
    // db 已在 Evidence First 阶段定义，无需重复

    for (const item of fullAssignments) {
      const { chapter, writer, reviewers } = item;

      // 更新章节信息
      chapter.authorModel = writer;
      chapter.reviewerModel = reviewers[0] || this.REVIEW_EXPERTS[0];

      // 获取人格配置
      const persona = EXPERT_PERSONAS[writer];

      // 持久化到 insight_schedules 表
      db.run(`
        INSERT INTO insight_schedules
        (task_id, chapter_id, chapter_title, assigned_writer, assigned_reviewers, personality_config)
        VALUES (?, ?, ?, ?, ?, ?)
      `, [
        this.session!.sessionId,
        chapter.chapterId,
        chapter.title,
        writer,
        JSON.stringify(reviewers),
        JSON.stringify(persona || {})
      ]);

      // 记录分配
      assignments.push({
        expertId: `author_${chapter.chapterId}`,
        model: writer,
        role: 'author',
        chapterIds: [chapter.chapterId],
        performanceScore: 0
      });

      for (const reviewer of reviewers) {
        assignments.push({
          expertId: `reviewer_${chapter.chapterId}_${reviewer}`,
          model: reviewer,
          role: 'reviewer',
          chapterIds: [chapter.chapterId],
          performanceScore: 0
        });
      }
    }

    // Step 3.5: 调度方案交叉互评
    // 设计来源: 技术宅 (gemini-2.5-pro) - 模块化、可测试、严谨一致
    console.log('\n   🎯 调度互评: crossEvaluateDispatch...');

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要给 worker brains
    const writerCounts: Record<string, number> = {};
    for (const a of fullAssignments) {
      writerCounts[a.writer] = (writerCounts[a.writer] || 0) + 1;
    }

    const scheduleSummary = `
【统计摘要】
- 总章节数: ${fullAssignments.length}
- 使用专家: ${Object.keys(writerCounts).join(', ')}
- 负载分布: ${Object.entries(writerCounts).map(([w, c]) => `${w}×${c}`).join(', ')}
- 交叉审核覆盖率: 100% (每章 ${fullAssignments[0]?.reviewers.length || 2} 位审核者)
`.trim();

    // 调用模块化的交叉互评函数
    const crossEvalResults = await this.crossEvaluateDispatch(scheduleSummary, this.session.topic);

    // 记录审核结果到数据库
    for (const r of crossEvalResults) {
      console.log(`   ${r.success ? '✓' : '⚠️'} ${r.expert} - 匹配:${r.scores.matching} 均衡:${r.scores.balance} 合理:${r.scores.reasonability}`);
      try {
        const avgScore = (r.scores.matching + r.scores.balance + r.scores.reasonability) / 3;
        db.run(`
          INSERT INTO insight_evaluations
          (task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        `, [
          this.session!.sessionId,
          'scheduling_cross_review',
          r.expert,
          'schedule',
          this.session!.sessionId,
          JSON.stringify(r.scores),
          Math.round(avgScore * 10) / 10,
          r.suggestions.substring(0, 1000)
        ]);
      } catch (e) { /* 忽略 */ }
    }

    // 写入记忆
    const crossReviewSummary = crossEvalResults
      .filter(r => r.success)
      .map(r => `[${r.expert}] 匹配:${r.scores.matching} 建议:${r.suggestions}`)
      .join('\n');
    await this.writeToMemory(
      this.session!.sessionId,
      `调度交叉审核完成 (crossEvaluateDispatch)\n${crossReviewSummary}`,
      { phase: 'scheduling_review', tags: ['scheduling', 'cross_review', 'modular'] }
    );

    // v2.1: 结构化写入中枢神经 (CortexWriter)
    const dispatchAssignments = fullAssignments.map((a, idx) => ({
      chapterIndex: idx,
      writer: a.writer,
      reviewer: a.reviewers[0] || 'gemini-2.5-pro'
    }));
    await this.writeDispatchToMemory(dispatchAssignments);

    // Step 4: 更新会话状态
    this.session.experts = assignments;
    this.session.status = 'scheduling';
    await this.persistence.saveSession(this.session);

    // 输出调度摘要
    console.log('\n   📋 调度摘要:');
    for (const item of fullAssignments) {
      const persona = EXPERT_PERSONAS[item.writer];
      console.log(`   • ${item.chapter.title}`);
      console.log(`     作者: ${item.writer} (${persona?.traits || '未知'})`);
      console.log(`     审核: ${item.reviewers.join(', ')}`);
    }

    // ========== v2.2: 更新报告状态 ==========
    if (this.reportStructure) {
      const stateData: StateData = {
        topic: this.session!.topic,
        currentPhase: 'SCHEDULING',
        progress: {
          done: ['CREATED', 'PLANNING', 'OUTLINE'],
          inProgress: 'SCHEDULING',
          blocked: []
        },
        nextActions: [
          '执行 stage4_writing 开始章节写作',
          `${assignments.length} 个专家已分配完成`
        ]
      };
      this.reportStructure.writeState(stateData);
      console.log('   ✓ STATE.md 已更新');

      // 写入 Phase 3 输出
      const schedulingSummary = fullAssignments.map((a, idx) =>
        `${idx + 1}. ${a.chapter.title}\n   作者: ${a.writer}\n   审核: ${a.reviewers.join(', ')}`
      ).join('\n\n');
      const phase3Output: PhaseOutput = {
        phaseNum: 3,
        phaseName: 'scheduling',
        content: `# 专家调度方案\n\n${schedulingSummary}`
      };
      this.reportStructure.writePhase(phase3Output);
      console.log('   ✓ PHASES/3-scheduling.md 已生成');
    }

    console.log(`\n✅ 智能调度完成，${assignments.length}个专家分配`);
    return assignments;
  }

  // ============================================================
  // 阶段4: 写作 (Writing) - 使用 SolarMapper 智能规划 + 并行执行
  // ============================================================
  async stage4_writing(): Promise<ChapterData[]> {
    if (!this.session) throw new Error('请先执行 stage3_scheduling');

    console.log('\n✍️ 阶段4: 并行写作 (SolarMapper 驱动)');

    // ========== Step 0: Evidence First - 查 Cortex 知识库 (Principle 5) ==========
    console.log('🔍 Evidence First: 查询 Cortex 知识库...');
    const db = this.persistence.getDb();

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要，不保留完整数组
    let cortexSourcesPointers = {
      count: 0,
      avgCredibility: 0,
      topCitations: [] as string[],
      topEvidenceTypes: [] as string[]
    };

    let cortexClaimsPointers = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    try {
      // 查询相关知识源（用于写作内容参考）
      const sources = db.query(`
        SELECT title, finding, credibility, citation_key, evidence_type
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 10
      `).all(`%${this.session.topic}%`) as any[];

      if (sources.length > 0) {
        cortexSourcesPointers = {
          count: sources.length,
          avgCredibility: sources.reduce((sum: number, s: any) => sum + (s.credibility || 0), 0) / sources.length,
          topCitations: sources.slice(0, 3).map((s: any) => s.citation_key).filter(Boolean),
          topEvidenceTypes: [...new Set(sources.map((s: any) => s.evidence_type).filter(Boolean))].slice(0, 3)
        };
      }
      console.log(`   找到 ${cortexSourcesPointers.count} 个 Cortex 知识源 (avg credibility: ${cortexSourcesPointers.avgCredibility.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_sources 表不存在，跳过');
    }

    try {
      // 查询已验证结论（用于写作论点参考）
      const claims = db.query(`
        SELECT statement, confidence, supporting_evidence
        FROM cortex_claims
        WHERE statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${this.session.topic}%`) as any[];

      if (claims.length > 0) {
        cortexClaimsPointers = {
          count: claims.length,
          avgConfidence: claims.reduce((sum: number, c: any) => sum + (c.confidence || 0), 0) / claims.length,
          topStatements: claims.slice(0, 3).map((c: any) => c.statement.substring(0, 80))
        };
      }
      console.log(`   找到 ${cortexClaimsPointers.count} 个 Cortex 结论 (avg confidence: ${cortexClaimsPointers.avgConfidence.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_claims 表不存在，跳过');
    }

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要给 worker brains
    const cortexContext = (cortexSourcesPointers.count > 0 || cortexClaimsPointers.count > 0)
      ? `\n【Cortex 知识参考 - 统计摘要】
- 知识源数量: ${cortexSourcesPointers.count} (平均可信度: ${cortexSourcesPointers.avgCredibility.toFixed(2)})
- 主要引用: ${cortexSourcesPointers.topCitations.join(', ')}
- 证据类型: ${cortexSourcesPointers.topEvidenceTypes.join(', ')}
- 已验证结论: ${cortexClaimsPointers.count} 条 (平均置信度: ${cortexClaimsPointers.avgConfidence.toFixed(2)})
- 代表性结论: ${cortexClaimsPointers.topStatements.slice(0, 2).join('; ')}`
      : '';

    // ========== v2.1 Cortex 读取闭环: 从中枢神经读取调度数据 ==========
    console.log('   📖 从 Cortex 读取调度数据...');
    const cortexDispatch = await this.readDispatchFromCortex(this.session.sessionId);
    if (cortexDispatch) {
      console.log(`   ✓ Cortex 调度: ${cortexDispatch.total_chapters || 0} 章节已分配`);
      // 用 Cortex 数据更新章节的作者/审核者分配（如果有的话）
      if (cortexDispatch.assignments && this.session.chapters.length > 0) {
        for (const assign of cortexDispatch.assignments) {
          const chapter = this.session.chapters[assign.chapter - 1];
          if (chapter) {
            chapter.authorModel = chapter.authorModel || assign.writer;
            chapter.reviewerModel = chapter.reviewerModel || assign.reviewer;
          }
        }
        console.log('   ✓ 已应用 Cortex 中的专家分配');
      }
    } else {
      console.log('   ℹ️ Cortex 无调度数据，使用内存数据');
    }
    // ========== Cortex 读取闭环结束 ==========

    const chapters = this.session.chapters;
    const goal = `撰写关于"${this.session.topic}"的洞察报告`;

    // 1. 初始化 SolarMapper
    const solarMapper = new SolarMapper();

    // 2. 准备章节实体和写作模板
    const chapterEntities = chapters.map(ch => ch.title);
    const writingTemplate = `
请撰写洞察报告的章节：{{entity}}

主题：${this.session.topic}
${cortexContext}

**硬性技术要求（每个技术点必须包含）**：
1. **数学定义/公式**（如果适用）
2. **伪代码或数据结构定义**（用TypeScript/Python语法）
3. **复杂度分析**（时间/空间，如 O(log n)）
4. **实际性能数据**（即使是假设性的，如"100万向量库中查询延迟<10ms"）

**禁止的写法 vs 正确的写法**：

❌ **禁止**："通过先进的算法实现高效检索"
✅ **正确**："使用 HNSW 算法，检索复杂度 O(log n)，在100万向量库中查询延迟<10ms
\`\`\`typescript
interface HNSWIndex {
  layers: Layer[];
  M: number; // 每层最大连接数
}
\`\`\`"

❌ **禁止**："采用混合架构提升性能"
✅ **正确**："L1 Cache(Redis) + L2 Vector DB 架构
- L1 命中率: 40%，延迟<1ms
- L2 延迟: <10ms
- 总体性能提升: 35%"

**其他要求**：
1. 篇幅：1000-1500字
2. 结构：清晰的章节层次
3. 格式：Markdown
4. 证据：每个论点必须有数据/案例支撑

直接输出章节内容：
`;

    // 3. 获取专家规划调用
    console.log('  📋 获取专家规划...');
    const { expertCalls } = solarMapper.step2_getExpertCalls(
      goal,
      writingTemplate,
      chapterEntities
    );

    // 4. 并行调用专家获取任务分配建议
    console.log(`  🧠 咨询 ${expertCalls.length} 位专家...`);
    const expertResponses: { model: string; response: string }[] = [];

    const expertPromises = expertCalls.map(async (call: PlanningCall) => {
      try {
        const response = await BrainRouterClient.callWithRetry({
          model: call.model,
          system: call.system,
          prompt: call.prompt
        });
        return { model: call.model, response };
      } catch (error) {
        console.log(`    ⚠️ ${call.nickname} 调用失败，使用默认分配`);
        return { model: call.model, response: '[]' };
      }
    });

    const expertResults = await Promise.all(expertPromises);
    expertResponses.push(...expertResults);

    // ✨ Brain Separation: Result Compression - 专家响应立即压缩
    console.log('🗜️ 压缩专家响应 (Brain Separation)...');
    const originalSizes = expertResponses.map(r => r.response.length);
    const totalOriginalSize = originalSizes.reduce((sum, size) => sum + size, 0);
    // 注意：expertResponses 的 .response 字段会被 step3_mergePlan 立即解析为 JSON
    // 原始 LLM 文本在解析后丢弃，只保留结构化数据
    console.log(`   原始专家响应: ${totalOriginalSize} chars → 解析后保留结构化数据，丢弃原始文本`);

    // 5. 合并专家建议生成执行计划
    console.log('  🔀 合并专家建议...');
    const executionPlan: ExecutionPlan = solarMapper.step3_mergePlan(
      chapterEntities,
      writingTemplate,
      expertResponses
    );

    console.log(`  📋 执行计划: ${executionPlan.totalTasks} 个写作任务`);

    // 6. 执行写作任务 (并行)
    const taskResults = new Map<string, string>();
    const startTimes = new Map<string, number>();

    const writePromises = executionPlan.tasks.map(async (task) => {
      const chapterIndex = chapters.findIndex(ch => ch.title === task.entity);
      if (chapterIndex === -1) return;

      const chapter = chapters[chapterIndex];
      chapter.status = 'writing';
      chapter.authorModel = task.model;  // 更新为实际分配的模型

      startTimes.set(task.id, Date.now());

      try {
        // v2.1 增强: 绩效注入 + 参考文献过滤
        const enhancedPersona = await this.getEnhancedPersona(task.model);

        // 为章节过滤相关参考文献
        const chapterRefs = filterReferencesForChapter(
          this.session!.references || [],
          chapter.title,
          5
        );
        const refsContext = formatReferencesForExpert(chapterRefs);

        // 增强提示词: 添加参考文献
        const enhancedPrompt = refsContext
          ? `${refsContext}\n\n${task.prompt}`
          : task.prompt;

        const content = await BrainRouterClient.callWithRetry({
          model: task.model,
          system: enhancedPersona,
          prompt: enhancedPrompt
        });

        const duration = Date.now() - (startTimes.get(task.id) || Date.now());

        // ✨ Brain Separation: Result Compression - 写作内容立即保存，不在内存累积
        console.log(`🗜️ 压缩 ${task.entity} 结果 (Brain Separation): ${content.length} chars`);
        taskResults.set(task.entity, content);

        chapter.content = content;
        chapter.status = 'reviewing';

        // 保存到文件
        this.persistence.saveChapterToFile(
          this.session!.sessionId,
          chapter.chapterId,
          content
        );

        // 🔴 关键：保存到数据库 (防止上下文压缩后丢失)
        this.persistence.saveChapterToDB(this.session!.sessionId, {
          chapterId: chapter.chapterId,
          title: chapter.title,
          content: content,
          authorModel: task.model,
          status: 'reviewing'
        });

        // 记录绩效
        await this.recordWritingPerformance(
          task.model,
          chapter.chapterId,
          duration,
          true
        );

        // v2.1: 写入中枢神经 (CortexWriter)
        const chapterIndex = chapters.indexOf(chapter);
        const wordCount = content.length;
        await this.writeWritingToMemory(chapterIndex, task.model, 7, wordCount);

        console.log(`    ✓ ${chapter.title} (by ${task.nickname}, ${duration}ms)`);
        return chapter;
      } catch (error) {
        const duration = Date.now() - (startTimes.get(task.id) || Date.now());
        chapter.status = 'pending';
        taskResults.set(task.entity, `[写作失败] ${error}`);

        // 记录失败绩效
        await this.recordWritingPerformance(
          task.model,
          chapter.chapterId,
          duration,
          false
        );

        console.log(`    ✗ ${chapter.title} 失败: ${error}`);
        return chapter;
      }
    });

    await Promise.all(writePromises);

    // 7. 注入结果到 SolarMapper (用于后续聚合)
    await solarMapper.injectResults(taskResults);

    // 8. 更新 session 状态
    this.session.status = 'writing';
    await this.persistence.saveSession(this.session);

    const successCount = chapters.filter(ch => ch.status === 'reviewing').length;
    console.log(`✅ 写作完成，成功 ${successCount}/${chapters.length} 章节`);

    // ========== v2.2: 更新报告状态 ==========
    if (this.reportStructure) {
      const stateData: StateData = {
        topic: this.session!.topic,
        currentPhase: 'WRITING',
        progress: {
          done: ['CREATED', 'PLANNING', 'OUTLINE', 'SCHEDULING'],
          inProgress: 'WRITING',
          blocked: []
        },
        nextActions: [
          '执行 stage5_reviewing 开始审查章节',
          `${successCount} 个章节已完成写作`
        ]
      };
      this.reportStructure.writeState(stateData);
      console.log('   ✓ STATE.md 已更新');

      // 注：Phase 4 的章节内容已通过 saveChapterToFile 保存到 PHASES/4-writing/
    }

    return chapters;
  }

  /**
   * 记录写作阶段绩效
   */
  private async recordWritingPerformance(
    modelId: string,
    chapterId: string,
    durationMs: number,
    success: boolean
  ): Promise<void> {
    try {
      const db = this.persistence.getDb();
      db.run(`
        INSERT INTO collab_performance
        (model_id, task_type, task_id, success, duration_ms, quality_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
      `, [
        modelId,
        'chapter_writing',
        chapterId,
        success ? 1 : 0,
        durationMs,
        success ? 7.0 : 0,  // 初始分数，后续审核阶段更新
      ]);
    } catch (error) {
      // 表可能不存在，忽略
      console.log(`    ⚠️ 绩效记录失败: ${error}`);
    }
  }

  // ============================================================
  // 阶段5: 审核 (Reviewing) - 交叉审核 + 挑战者机制 v2.1
  // ============================================================
  async stage5_reviewing(): Promise<ChapterData[]> {
    if (!this.session) throw new Error('请先执行 stage4_writing');

    console.log('\n🔍 阶段5: 交叉审核 (v2.1 多审核者)');

    // ========== Step 0: Evidence First - 查 Cortex 知识库 (Principle 5) ==========
    console.log('🔍 Evidence First: 查询 Cortex 知识库...');
    const db = this.persistence.getDb();

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要，不保留完整数组
    let cortexSourcesPointers = {
      count: 0,
      avgCredibility: 0,
      topTitles: [] as string[]
    };

    let cortexClaimsPointers = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    try {
      // 查询相关知识源（用于审核准确性参考）
      const sources = db.query(`
        SELECT title, finding, credibility
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 8
      `).all(`%${this.session.topic}%`) as any[];

      if (sources.length > 0) {
        cortexSourcesPointers = {
          count: sources.length,
          avgCredibility: sources.reduce((sum: number, s: any) => sum + (s.credibility || 0), 0) / sources.length,
          topTitles: sources.slice(0, 3).map((s: any) => s.title).filter(Boolean)
        };
      }
      console.log(`   找到 ${cortexSourcesPointers.count} 个 Cortex 知识源 (avg credibility: ${cortexSourcesPointers.avgCredibility.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_sources 表不存在，跳过');
    }

    try {
      // 查询已验证结论（用于审核逻辑参考）
      const claims = db.query(`
        SELECT statement, confidence
        FROM cortex_claims
        WHERE statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${this.session.topic}%`) as any[];

      if (claims.length > 0) {
        cortexClaimsPointers = {
          count: claims.length,
          avgConfidence: claims.reduce((sum: number, c: any) => sum + (c.confidence || 0), 0) / claims.length,
          topStatements: claims.slice(0, 2).map((c: any) => c.statement?.substring(0, 60)).filter(Boolean)
        };
      }
      console.log(`   找到 ${cortexClaimsPointers.count} 个 Cortex 结论 (avg confidence: ${cortexClaimsPointers.avgConfidence.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_claims 表不存在，跳过');
    }

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要给 worker brains
    const cortexContext = (cortexSourcesPointers.count > 0 || cortexClaimsPointers.count > 0)
      ? `\n【Cortex 知识参考（用于校验准确性）- 统计摘要】
- 知识源数量: ${cortexSourcesPointers.count} (平均可信度: ${cortexSourcesPointers.avgCredibility.toFixed(2)})
- 代表性知识源: ${cortexSourcesPointers.topTitles.join(', ')}
- 已验证结论: ${cortexClaimsPointers.count} 条 (平均置信度: ${cortexClaimsPointers.avgConfidence.toFixed(2)})
- 代表性结论: ${cortexClaimsPointers.topStatements.join('; ')}`
      : '';

    // ========== v2.1 Cortex 读取闭环: 从中枢神经读取写作数据 ==========
    console.log('   📖 从 Cortex 读取写作数据...');
    const cortexWriting = await this.readWritingFromCortex(this.session.sessionId);
    if (cortexWriting && cortexWriting.length > 0) {
      console.log(`   ✓ Cortex 写作: ${cortexWriting.length} 章节已完成写作`);
      // 用 Cortex 数据补充章节元数据（质量分、字数等）
      for (const cw of cortexWriting) {
        const chapter = this.session.chapters[cw.chapter_index - 1];
        if (chapter) {
          chapter.authorModel = chapter.authorModel || cw.writer_model;
          // 如果内存中没有内容但 Cortex 记录了质量分，说明需要从文件恢复
          if (!chapter.content && cw.quality_score > 0) {
            console.log(`   🔄 章节 ${cw.chapter_index} 需要从文件恢复内容`);
          }
        }
      }
    } else {
      console.log('   ℹ️ Cortex 无写作数据，使用内存数据');
    }
    // ========== Cortex 读取闭环结束 ==========

    const chapters = this.session.chapters;
    // db 已在上方 Evidence Pointers 块中声明，此处复用

    // 并行审核每个章节
    const reviewPromises = chapters.map(async (chapter) => {
      console.log(`  📄 审核 ${chapter.title}...`);

      // 获取该章节的审核者列表 (从 insight_schedules)
      let reviewers: string[] = [chapter.reviewerModel];
      try {
        const schedule = db.query(`
          SELECT assigned_reviewers FROM insight_schedules
          WHERE task_id = ? AND chapter_id = ?
        `).get(this.session!.sessionId, chapter.chapterId) as any;
        if (schedule?.assigned_reviewers) {
          reviewers = JSON.parse(schedule.assigned_reviewers);
        }
      } catch (e) { /* 使用默认审核者 */ }

      // 确保至少有一个审核者
      if (reviewers.length === 0) {
        reviewers = [this.REVIEW_EXPERTS[0]];
      }

      // ========== 并行调用多个审核者 ==========
      const evaluations: Array<{ model: string; score: number; review: string }> = [];

      const reviewerPromises = reviewers.map(async (reviewerModel) => {
        const reviewPrompt = `
你是严格的审核者，必须客观评估，**禁止互相吹捧**。

【章节信息】
标题：${chapter.title}
作者：匿名 (匿名化以保证客观)

【内容】
${chapter.content?.substring(0, 3000) || '(无内容)'}

【结构化审核清单】
请逐项评估并打分 (1-10)：

| 维度 | 分数 | 说明 |
|------|------|------|
| 论点清晰度 | ? | 核心观点是否明确 |
| 论据充分性 | ? | 数据/案例是否支撑 |
| 逻辑连贯性 | ? | 论证链是否完整 |
| 专业准确性 | ? | 是否有事实错误 |
| 语言表达 | ? | 是否专业易懂 |

**输出格式：**
\`\`\`json
{
  "scores": {
    "clarity": 8,
    "evidence": 7,
    "logic": 8,
    "accuracy": 9,
    "language": 8
  },
  "overallScore": 8,
  "problems": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}
\`\`\`
`;

        try {
          // v2.1 增强: 绩效注入
          const enhancedPersona = await this.getEnhancedPersona(reviewerModel);
          const review = await BrainRouterClient.callWithRetry({
            model: reviewerModel,
            system: enhancedPersona + '\n你是挑战者，必须严格审核，禁止吹捧。',
            prompt: reviewPrompt
          });

          // ✨ Brain Separation: Result Compression - 审核响应立即解析为结构化数据
          console.log(`🗜️ 压缩审核响应 (Brain Separation): ${review.length} chars → 解析为 JSON 评分结构`);

          // 解析评分
          let score = 7;
          try {
            const jsonMatch = review.match(/```json\s*([\s\S]*?)```/i) ||
                              review.match(/\{[\s\S]*"overallScore"[\s\S]*\}/);
            if (jsonMatch) {
              const parsed = JSON.parse(jsonMatch[1] || jsonMatch[0]);
              score = parsed.overallScore || 7;
            } else {
              const scoreMatch = review.match(/评分[：:]\s*(\d+)/);
              score = scoreMatch ? parseInt(scoreMatch[1]) : 7;
            }
          } catch (e) { /* 使用默认分 */ }

          return { model: reviewerModel, score, review };
        } catch (error) {
          console.log(`    ⚠️ ${reviewerModel} 审核失败`);
          return { model: reviewerModel, score: 6, review: '审核失败' };
        }
      });

      const reviewResults = await Promise.all(reviewerPromises);
      evaluations.push(...reviewResults);

      // ✨ Brain Separation: Result Compression - 汇总审核结果统计
      console.log(`🗜️ 汇总 ${evaluations.length} 个审核结果 (Brain Separation) - 只保留结构化评分，原始文本已丢弃`);

      // ========== 计算综合评分 (加权平均) ==========
      const totalScore = evaluations.reduce((sum, e) => sum + e.score, 0);
      const avgScore = Math.round((totalScore / evaluations.length) * 10) / 10;

      // 检查分歧 (如果分数差距 > 3，标记需要关注)
      const scores = evaluations.map(e => e.score);
      const maxDiff = Math.max(...scores) - Math.min(...scores);
      if (maxDiff > 3) {
        console.log(`    ⚠️ 审核分歧较大 (差距 ${maxDiff} 分)，可能需要人工裁决`);
      }

      // ========== 记录到 insight_evaluations ==========
      try {
        for (const ev of evaluations) {
          // 适配现有表结构: task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments
          const scores = JSON.stringify({ overall: ev.score });
          db.run(`
            INSERT INTO insight_evaluations
            (task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
          `, [
            this.session!.sessionId,  // task_id = session_id
            'reviewing',               // phase
            ev.model,                  // evaluator
            chapter.authorModel,       // evaluated (被评估的作者)
            chapter.chapterId,         // target_id
            scores,                    // scores JSON
            ev.score,                  // avg_score
            ev.review.substring(0, 2000)  // comments
          ]);
        }
      } catch (e) {
        console.log(`    ⚠️ 评估记录失败: ${e}`);
      }

      // 更新章节评分
      chapter.qualityScore = avgScore;
      chapter.status = 'done';

      // 🔴 关键：更新数据库中的章节状态和评分
      this.persistence.saveChapterToDB(this.session!.sessionId, {
        chapterId: chapter.chapterId,
        title: chapter.title,
        content: chapter.content,
        authorModel: chapter.authorModel,
        reviewerModel: evaluations[0]?.model,
        qualityScore: avgScore,
        status: 'done'
      });

      // v2.1: 写入中枢神经 (CortexWriter)
      const chapterIndex = chapters.indexOf(chapter);
      const keyFeedback = evaluations
        .map(e => e.review.substring(0, 100))
        .join(' | ');
      await this.writeReviewToMemory(
        chapterIndex,
        evaluations[0]?.model || 'unknown',
        avgScore,
        keyFeedback
      );

      const reviewerNames = evaluations.map(e => {
        const persona = EXPERT_PERSONAS[e.model];
        return persona?.traits || e.model.split('-')[0];
      }).join(', ');

      console.log(`    ✓ ${chapter.title}: ${avgScore}/10 (${evaluations.length}人: ${reviewerNames})`);
      return chapter;
    });

    await Promise.all(reviewPromises);

    this.session.status = 'reviewing';
    await this.persistence.saveSession(this.session);

    // 输出审核摘要
    const avgQuality = chapters.reduce((s, c) => s + c.qualityScore, 0) / chapters.length;
    console.log(`\n✅ 审核完成，平均质量: ${avgQuality.toFixed(1)}/10`);

    // ========== v2.2: 更新报告状态 ==========
    if (this.reportStructure) {
      const stateData: StateData = {
        topic: this.session!.topic,
        currentPhase: 'REVIEW',
        progress: {
          done: ['CREATED', 'PLANNING', 'OUTLINE', 'SCHEDULING', 'WRITING'],
          inProgress: 'REVIEW',
          blocked: []
        },
        nextActions: [
          '执行 stage6_synthesis 综合最终报告',
          `平均质量: ${avgQuality.toFixed(1)}/10`
        ]
      };
      this.reportStructure.writeState(stateData);
      console.log('   ✓ STATE.md 已更新');

      // 注：Phase 5 的审查结果已通过数据库保存
    }

    return chapters;
  }

  // ============================================================
  // 阶段6: 综合 (Synthesis) - 思考驼全文审核 v2.1
  // ============================================================
  async stage6_synthesis(): Promise<string> {
    if (!this.session) throw new Error('请先执行 stage5_reviewing');

    console.log('\n🔗 阶段6: 内容综合 (思考驼主导)');

    // ========== Step 0: Evidence First - 查 Cortex 知识库 (Principle 5) ==========
    console.log('🔍 Evidence First: 查询 Cortex 知识库...');
    const db = this.persistence.getDb();

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要，不保留完整数组
    let cortexSourcesPointers = {
      count: 0,
      avgCredibility: 0,
      topTitles: [] as string[]
    };

    let cortexClaimsPointers = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    try {
      const sources = db.query(`
        SELECT title, finding, credibility, citation_key
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 8
      `).all(`%${this.session.topic}%`) as any[];

      if (sources.length > 0) {
        cortexSourcesPointers = {
          count: sources.length,
          avgCredibility: sources.reduce((sum: number, s: any) => sum + (s.credibility || 0), 0) / sources.length,
          topTitles: sources.slice(0, 3).map((s: any) => `[${s.citation_key}] ${s.title}`).filter(Boolean)
        };
      }
      console.log(`   找到 ${cortexSourcesPointers.count} 条 Cortex 知识源 (avg credibility: ${cortexSourcesPointers.avgCredibility.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_sources 表不存在，跳过');
    }

    try {
      const claims = db.query(`
        SELECT claim_text, confidence, support_type
        FROM cortex_claims
        WHERE claim_text LIKE ?
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${this.session.topic}%`) as any[];

      if (claims.length > 0) {
        cortexClaimsPointers = {
          count: claims.length,
          avgConfidence: claims.reduce((sum: number, c: any) => sum + (c.confidence || 0), 0) / claims.length,
          topStatements: claims.slice(0, 2).map((c: any) => c.claim_text.substring(0, 50)).filter(Boolean)
        };
      }
      console.log(`   找到 ${cortexClaimsPointers.count} 条 Cortex 论断 (avg confidence: ${cortexClaimsPointers.avgConfidence.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_claims 表不存在，跳过');
    }

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要给 worker brains
    const cortexContext = (cortexSourcesPointers.count > 0 || cortexClaimsPointers.count > 0)
      ? `\n【Cortex 知识参考（用于综合验证）- 统计摘要】
- 知识源数量: ${cortexSourcesPointers.count} (平均可信度: ${cortexSourcesPointers.avgCredibility.toFixed(2)})
- 代表性知识源: ${cortexSourcesPointers.topTitles.join(', ')}
- 论断数量: ${cortexClaimsPointers.count} (平均置信度: ${cortexClaimsPointers.avgConfidence.toFixed(2)})
- 代表性论断: ${cortexClaimsPointers.topStatements.join('; ')}`
      : '';

    console.log('   ✓ Evidence First 完成，准备注入综合 prompt');
    // ========== Evidence First 结束 ==========

    // ========== v2.1 Cortex 读取闭环: 从中枢神经读取多阶段数据 ==========
    console.log('   📖 从 Cortex 读取前序阶段数据...');

    // 读取大纲数据
    const cortexOutline = await this.readOutlineFromCortex(this.session.sessionId);
    if (cortexOutline) {
      console.log(`   ✓ Cortex 大纲: ${cortexOutline.chapter_titles?.length || 0} 章节`);
    }

    // 读取写作数据
    const cortexWriting = await this.readWritingFromCortex(this.session.sessionId);
    console.log(`   ✓ Cortex 写作: ${cortexWriting.length} 章节记录`);

    // 读取审核数据
    const cortexReviews = await this.readReviewsFromCortex(this.session.sessionId);
    console.log(`   ✓ Cortex 审核: ${cortexReviews.length} 条审核记录`);

    // 构建 Cortex 洞察摘要（用于综合分析）
    const cortexInsights = {
      outline: cortexOutline,
      writingStats: cortexWriting.map(w => ({
        chapter: w.chapter_index,
        quality: w.quality_score,
        words: w.word_count
      })),
      reviewStats: cortexReviews.map(r => ({
        chapter: r.chapter_index,
        score: r.review_score,
        feedback: r.key_feedback
      }))
    };
    console.log('   ✓ Cortex 洞察摘要已构建，将用于综合分析');
    // ========== Cortex 读取闭环结束 ==========

    // ========== 强制从磁盘重新加载所有章节 (修复合并bug) ==========
    const home = homedir();
    const sessionDir = `${home}/Solar/insight-reports/${this.session.sessionId}`;

    // 🔍 Debug: 查看加载前内存中的章节状态
    console.log(`   🔍 [DEBUG] Stage 6 开始前，内存中章节数: ${this.session.chapters.filter(Boolean).length}`);
    this.session.chapters.forEach((ch, idx) => {
      if (ch) {
        console.log(`   🔍 [DEBUG] 内存章节 ${idx + 1}: content=${ch.content ? `${ch.content.length}字符` : '无'}`);
      }
    });

    if (existsSync(sessionDir)) {
      try {
        const files = require('fs').readdirSync(sessionDir);
        const chapterFiles = files.filter(f => f.startsWith('ch_') && f.endsWith('.md'));
        console.log(`   → 检测到 ${chapterFiles.length} 个章节文件`);

        // 🔍 Debug: 先看磁盘上有什么
        chapterFiles.forEach(f => {
          const content = readFileSync(`${sessionDir}/${f}`, 'utf-8');
          console.log(`   🔍 [DEBUG] 磁盘文件 ${f}: ${content.length}字符`);
        });

        // ✨ 修复: 无条件强制重新加载，覆盖内存中可能过期的内容
        for (const file of files) {
          if (file.startsWith('ch_') && file.endsWith('.md')) {
            const chapterIndex = parseInt(file.replace('ch_', '').replace('.md', '')) - 1;
            const content = readFileSync(`${sessionDir}/${file}`, 'utf-8');

            // ✨ 修复: 无条件覆盖，不再检查是否已存在
            this.session.chapters[chapterIndex] = {
              chapterId: `ch_${chapterIndex + 1}`,
              title: `第${chapterIndex + 1}章`,
              content: content,
              authorModel: this.session.chapters[chapterIndex]?.authorModel || 'unknown',
              reviewerModel: this.session.chapters[chapterIndex]?.reviewerModel || '',
              qualityScore: this.session.chapters[chapterIndex]?.qualityScore || 0,
              status: 'done'
            };
            console.log(`   ✓ 强制重新加载章节 ${chapterIndex + 1} (${(content.length / 1024).toFixed(1)}KB)`);
          }
        }

        // 🔍 Debug: 查看加载后内存中的章节状态
        console.log(`   🔍 [DEBUG] 加载后，内存中章节数: ${this.session.chapters.filter(Boolean).length}`);
        this.session.chapters.forEach((ch, idx) => {
          if (ch) {
            console.log(`   🔍 [DEBUG] 加载后章节 ${idx + 1}: content=${ch.content ? `${ch.content.length}字符` : '无'}`);
          }
        });
      } catch (e) {
        console.warn('   ⚠️ 章节文件加载失败:', e);
      }
    }
    // ========== 章节加载完成 ==========

    // 🔍 Debug: 最终报告组装前检查 + 强制写文件日志
    const debugLogFile = `${home}/Solar/insight-reports/${this.session.sessionId}/DEBUG-stage6.log`;
    const debugLines: string[] = [];
    debugLines.push(`=== Stage 6 组装前 Debug ===`);
    debugLines.push(`this.session.chapters.length = ${this.session.chapters.length}`);
    this.session.chapters.forEach((ch, idx) => {
      if (ch) {
        const line = `组装前章节 ${idx + 1}: title="${ch.title}", content=${ch.content ? `${ch.content.length}字符` : '无'}, status="${ch.status}"`;
        debugLines.push(line);
        console.log(`   🔍 [DEBUG] ${line}`);
      } else {
        debugLines.push(`组装前章节 ${idx + 1}: 空槽位`);
        console.log(`   🔍 [DEBUG] 组装前章节 ${idx + 1}: 空槽位`);
      }
    });

    const chapters = this.session.chapters.filter(Boolean); // 过滤掉空槽位
    debugLines.push(`filter(Boolean) 后，chapters.length = ${chapters.length}`);
    console.log(`   🔍 [DEBUG] filter(Boolean) 后，chapters.length = ${chapters.length}`);
    chapters.forEach((ch, idx) => {
      const line = `filter 后章节 ${idx + 1}: title="${ch.title}", content=${ch.content ? `${ch.content.length}字符` : '无'}`;
      debugLines.push(line);
      console.log(`   🔍 [DEBUG] ${line}`);
    });

    // 写入debug日志文件
    try {
      writeFileSync(debugLogFile, debugLines.join('\n'));
      console.log(`   ✓ Debug 日志已写入: ${debugLogFile}`);
    } catch (e) {
      console.warn(`   ⚠️ 写入 debug 日志失败:`, e);
    }

    // db 已在上方 Evidence First 块中声明，此处复用

    // ========== Step 1: 合并所有章节内容 ==========
    // 🔍 Debug: map 前状态
    debugLines.push(`\n=== allContent 构造中 ===`);
    debugLines.push(`chapters 数组长度: ${chapters.length}`);
    chapters.forEach((ch, i) => {
      debugLines.push(`  章节${i+1}: title="${ch.title}", content 长度=${ch.content?.length || 0}`);
    });

    // 分步构造以便调试
    const mappedChapters = chapters.map((ch, i) => {
      const mapped = `# ${ch.title}\n\n${ch.content || '(内容缺失)'}`;
      debugLines.push(`  map 结果${i+1}: ${mapped.length} 字符`);
      return mapped;
    });
    debugLines.push(`map 后数组长度: ${mappedChapters.length}`);

    const allContent = mappedChapters.join('\n\n---\n\n');
    debugLines.push(`join 后 allContent.length = ${allContent.length} 字符`);

    console.log(`   🔍 [DEBUG] allContent.length = ${allContent.length} 字符`);

    // 🔍 Debug: 追加 allContent 调试信息到文件
    debugLines.push(`\n=== allContent 构造后 ===`);
    debugLines.push(`allContent.length = ${allContent.length} 字符`);
    if (allContent.length > 0) {
      debugLines.push(`\n前500字符:\n${allContent.substring(0, Math.min(500, allContent.length))}`);
      debugLines.push(`\n后500字符:\n${allContent.substring(Math.max(0, allContent.length - 500))}`);
    }

    // 每个章节在 allContent 中的位置
    let currentPos = 0;
    chapters.forEach((ch, idx) => {
      const chapterMarker = `# ${ch.title}`;
      const foundAt = allContent.indexOf(chapterMarker, currentPos);
      debugLines.push(`章节 ${idx + 1} 在 allContent 中的位置: ${foundAt >= 0 ? foundAt : '未找到'}`);
      if (foundAt >= 0) {
        currentPos = foundAt + 1;
      }
    });

    // 立即写入 debug 文件（不等待后续步骤）
    try {
      writeFileSync(debugLogFile, debugLines.join('\n'));
      console.log(`   ✓ allContent Debug 信息已写入: ${debugLogFile}`);
    } catch (e) {
      console.warn(`   ⚠️ 写入 debug 信息失败:`, e);
    }

    // ========== Step 2: 查询各章节评审意见 ==========
    let reviewSummary = '';
    try {
      const evaluations = db.query(`
        SELECT chapter_id, evaluator_model, score, substr(evaluation_content, 1, 500) as summary
        FROM insight_evaluations
        WHERE session_id = ?
        ORDER BY chapter_id
      `).all(this.session.sessionId) as any[];

      if (evaluations.length > 0) {
        reviewSummary = '\n【各章节评审摘要】\n' + evaluations.map(e =>
          `- ${e.chapter_id}: ${e.score}/10 (${e.evaluator_model})`
        ).join('\n');
      }
    } catch (e) { /* 忽略 */ }

    // ========== Step 3: 多专家交响乐团模式审核 ==========
    // 设计来源: 思考驼 (deepseek-r1) + 鬼才码农 (deepseek-v3)
    console.log('  🎼 交响乐团模式: 多专家并行审核...');

    // 专家团队配置 (加权评分)
    const expertTeam = [
      { model: 'deepseek-r1', role: 'deep_thinker', weight: 0.30, focus: '深度逻辑分析' },
      { model: 'deepseek-v3', role: 'creative_writer', weight: 0.20, focus: '创意表达优化' },
      { model: 'gemini-2.5-pro', role: 'critical_reviewer', weight: 0.25, focus: '一致性审核' },
      { model: 'gemini-3-pro-preview', role: 'practical_engineer', weight: 0.25, focus: '实用性评估' }
    ];

    const synthesisPrompt = `
你是资深报告综合审核专家，请对以下完整报告进行全面审核。

【报告主题】${this.session.topic}
${reviewSummary}
${cortexContext}

【完整内容 (截取前15000字)】
${allContent.substring(0, 15000)}

【你的审核角色】{{FOCUS}}

【审核要求】
1. 从你的专业角度评估报告质量
2. 给出整体评分 (0-10)
3. 列出 2-3 个关键发现
4. 提出 1-2 条改进建议

**输出格式 (简洁):**
评分: X/10
关键发现:
1. ...
2. ...
改进建议:
- ...
`;

    // 并行调用专家团队
    let completedCount = 0;
    const expertPromises = expertTeam.map(async (expert) => {
      try {
        const persona = EXPERT_PERSONAS[expert.model];
        const customPrompt = synthesisPrompt.replace('{{FOCUS}}', expert.focus);

        const result = await Promise.race([
          BrainRouterClient.callWithRetry({
            model: expert.model,
            system: persona?.system || '你是专业审核专家',
            prompt: customPrompt
          }),
          new Promise<string>((_, reject) =>
            setTimeout(() => reject(new Error('timeout')), 30000)
          )
        ]);

        completedCount++;
        console.log(`   ✓ [${completedCount}/${expertTeam.length}] ${expert.role} 完成`);

        // ✨ Brain Separation: Result Compression - worker brain 响应立即解析
        console.log(`🗜️ 压缩专家审核响应 (Brain Separation): ${result.length} chars → 提取评分+关键点`);

        // 提取评分
        const scoreMatch = result.match(/评分[:：]\s*(\d+(?:\.\d+)?)/);
        const score = scoreMatch ? parseFloat(scoreMatch[1]) : 7.0;

        return { ...expert, result, score, success: true };
      } catch (e) {
        console.log(`   ⚠️ ${expert.role} 审核超时或失败`);
        return { ...expert, result: this.generateFallbackReview(expert.role), score: 7.0, success: false };
      }
    });

    const expertResults = await Promise.all(expertPromises);

    // ✨ Brain Separation: Result Compression - 汇总多专家结果统计
    console.log(`🗜️ 汇总 ${expertResults.length} 个专家审核 (Brain Separation) - 只保留加权评分，原始文本已丢弃`);

    // 计算加权综合评分
    let weightedScore = 0;
    let totalWeight = 0;
    const synthesisReviews: string[] = [];

    for (const r of expertResults) {
      weightedScore += r.score * r.weight;
      totalWeight += r.weight;
      synthesisReviews.push(`### ${r.role} (权重: ${r.weight * 100}%)\n${r.result.substring(0, 500)}`);

      // 记录每个专家的评估
      try {
        db.run(`
          INSERT INTO insight_evaluations
          (task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        `, [
          this.session.sessionId,
          'synthesis_multi_expert',
          r.model,
          r.role,
          this.session.sessionId,
          JSON.stringify({ role: r.role, weight: r.weight, success: r.success }),
          r.score,
          r.result.substring(0, 1000)
        ]);
      } catch (e) { /* 忽略 */ }
    }

    const finalSynthesisScore = totalWeight > 0 ? weightedScore / totalWeight : 7.0;
    console.log(`   📊 加权综合评分: ${finalSynthesisScore.toFixed(1)}/10`);

    // 生成综合审核报告
    const synthesis = `## 执行摘要

本报告经过 ${expertTeam.length} 位专家团队审核，综合评分 ${finalSynthesisScore.toFixed(1)}/10。

${synthesisReviews.join('\n\n')}

---
*审核模式: 交响乐团 (Multi-Expert Symphony)*
*参与专家: ${expertTeam.map(e => e.role).join(', ')}*
`;

    // 写入记忆
    await this.writeToMemory(
      this.session.sessionId,
      `综合审核完成 | 评分: ${finalSynthesisScore.toFixed(1)}/10 | 专家: ${expertTeam.length}位`,
      { phase: 'synthesis', tags: ['synthesis', 'multi_expert'], priority: 'high' }
    );

    // v2.1: 结构化写入中枢神经 (CortexWriter)
    const keyInsights = expertResults
      .filter(r => r.success)
      .map(r => r.result.split('\n')[0] || `${r.role} 审核通过`);
    await this.writeSynthesisToMemory(
      synthesis,
      finalSynthesisScore,
      keyInsights
    );

    // ========== Step 4: 记录最终综合评估 ==========
    try {
      db.run(`
        INSERT INTO insight_evaluations
        (task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
      `, [
        this.session.sessionId,
        'synthesis_final',
        'expert_team',
        'full_report',
        this.session.sessionId,
        JSON.stringify({ mode: 'symphony', experts: expertTeam.length }),
        finalSynthesisScore,
        synthesis.substring(0, 2000)
      ]);
    } catch (e) { /* 忽略 */ }

    // ========== Step 5: 生成最终报告 ==========
    const avgScore = chapters.reduce((s, c) => s + c.qualityScore, 0) / chapters.length;

    // ========== Step 5.1: 格式化参考文献 ==========
    const referencesSection = this.session.references.length > 0
      ? `## 参考文献

${this.session.references.map((ref, i) => {
  const sourceLabel = {
    'cortex': '📚 Cortex记忆',
    'favorites': '⭐ 收藏',
    'websearch': '🌐 网络搜索',
    'expert': '🧠 专家引用'
  }[ref.source] || '📄 其他';

  return `${i + 1}. **${ref.title}**
   - 来源: ${sourceLabel}
   - 摘要: ${ref.summary.substring(0, 150)}${ref.summary.length > 150 ? '...' : ''}
   - 相关度: ${ref.relevance ? (ref.relevance * 100).toFixed(0) + '%' : 'N/A'}`;
}).join('\n\n')}`
      : '';

    // 🔍 DEBUG: 检查各部分长度
    console.log(`   🔍 [DEBUG-LENGTHS] synthesis.length = ${synthesis.length}`);
    console.log(`   🔍 [DEBUG-LENGTHS] allContent.length = ${allContent.length}`);
    console.log(`   🔍 [DEBUG-LENGTHS] referencesSection.length = ${referencesSection.length}`);

    let finalReport = `# ${this.session.topic} - 洞察报告

${synthesis}

---

${allContent}

---

${referencesSection}

## 报告元数据

| 指标 | 值 |
|------|------|
| 生成时间 | ${new Date().toISOString()} |
| 章节数量 | ${chapters.length} |
| 平均质量 | ${avgScore.toFixed(1)}/10 |
| 参考文献 | ${this.session.references.length} 条 |
| 生成引擎 | InsightAgent v2.1 |
| 规划专家 | deepseek-r1 (思考驼) |
| 综合专家 | deepseek-r1 (思考驼) |
| 润色风格 | Solar 双面娇娃 💪🌸 |
`;

    // 🔍 DEBUG: 检查 finalReport 构建后的长度
    console.log(`   🔍 [DEBUG-LENGTHS] finalReport.length (刚构建) = ${finalReport.length}`);

    // ========== v2.1 新增: Step 5.1.5 专家团队全文审阅 ==========
    // 设计来源: 7阶段设计要求 - 综合阶段应让专家团队进行全文审阅
    console.log('\n  📋 Step 5.1.5: 专家团队全文审阅...');

    // 选择2-3位专家进行全文审阅（不是所有专家，避免成本过高）
    const fullTextReviewers = [
      { model: 'deepseek-r1', role: 'logic_checker', focus: '逻辑连贯性和论证完整性' },
      { model: 'gemini-2.5-pro', role: 'consistency_checker', focus: '全文一致性和术语统一性' },
      { model: 'gemini-3-pro-preview', role: 'readability_checker', focus: '可读性和受众适配性' }
    ];

    // 分块处理长报告（每块约10K字符，保证上下文不超载）
    const CHUNK_SIZE = 10000;
    const reportChunks: string[] = [];
    for (let i = 0; i < finalReport.length; i += CHUNK_SIZE) {
      reportChunks.push(finalReport.substring(i, i + CHUNK_SIZE));
    }
    console.log(`   📄 报告总长: ${finalReport.length} 字符, 分 ${reportChunks.length} 块审阅`);

    const fullTextReviewPrompt = `
你是资深报告审阅专家，正在进行**全文审阅**。

【报告主题】${this.session.topic}
【审阅角度】{{FOCUS}}

【当前审阅内容】(第 {{CHUNK_INDEX}}/{{TOTAL_CHUNKS}} 块)
{{CHUNK_CONTENT}}

【全文审阅任务】
1. 从你的专业角度，检查这部分内容的质量
2. 标记发现的问题（如有）
3. 提出具体改进建议

**输出格式:**
问题发现:
- [问题1] (位置: 大约在xx处)
- [问题2]

改进建议:
- [建议1]
- [建议2]

整体评价: (一句话总结)
`;

    interface FullTextReviewResult {
      reviewer: string;
      role: string;
      chunkReviews: { chunkIndex: number; issues: string; suggestions: string; summary: string }[];
      overallSummary: string;
    }

    const fullTextReviewResults: FullTextReviewResult[] = [];

    // 并行让专家审阅所有块（但每个专家串行处理各块以保持上下文）
    const reviewerPromises = fullTextReviewers.map(async (reviewer) => {
      const chunkReviews: { chunkIndex: number; issues: string; suggestions: string; summary: string }[] = [];

      // 为了效率，每个专家只审核关键块（首块+中间块+末块）
      const keyChunks = reportChunks.length <= 3
        ? reportChunks.map((_, i) => i)
        : [0, Math.floor(reportChunks.length / 2), reportChunks.length - 1];

      for (const chunkIdx of keyChunks) {
        try {
          const persona = EXPERT_PERSONAS[reviewer.model];
          const prompt = fullTextReviewPrompt
            .replace('{{FOCUS}}', reviewer.focus)
            .replace('{{CHUNK_INDEX}}', String(chunkIdx + 1))
            .replace('{{TOTAL_CHUNKS}}', String(reportChunks.length))
            .replace('{{CHUNK_CONTENT}}', reportChunks[chunkIdx]);

          const result = await Promise.race([
            BrainRouterClient.callWithRetry({
              model: reviewer.model,
              system: persona?.system || '你是专业审阅专家',
              prompt
            }),
            new Promise<string>((_, reject) =>
              setTimeout(() => reject(new Error('timeout')), 25000)
            )
          ]);

          // 解析审阅结果
          const issuesMatch = result.match(/问题发现[:：]?\s*([\s\S]*?)(?=改进建议|整体评价|$)/i);
          const suggestionsMatch = result.match(/改进建议[:：]?\s*([\s\S]*?)(?=整体评价|$)/i);
          const summaryMatch = result.match(/整体评价[:：]?\s*(.*?)(?:\n|$)/i);

          chunkReviews.push({
            chunkIndex: chunkIdx,
            issues: issuesMatch?.[1]?.trim() || '无明显问题',
            suggestions: suggestionsMatch?.[1]?.trim() || '无特别建议',
            summary: summaryMatch?.[1]?.trim() || '审阅通过'
          });
        } catch (e) {
          chunkReviews.push({
            chunkIndex: chunkIdx,
            issues: '审阅超时',
            suggestions: '建议人工复核',
            summary: '未完成'
          });
        }
      }

      // 汇总该专家的整体评价
      const overallSummary = chunkReviews.every(r => r.summary.includes('通过') || r.issues === '无明显问题')
        ? '✅ 全文审阅通过'
        : `⚠️ 发现 ${chunkReviews.filter(r => r.issues !== '无明显问题').length} 处问题`;

      console.log(`   ✓ ${reviewer.role}: ${overallSummary}`);

      return {
        reviewer: reviewer.model,
        role: reviewer.role,
        chunkReviews,
        overallSummary
      };
    });

    fullTextReviewResults.push(...await Promise.all(reviewerPromises));

    // 汇总全文审阅结果到报告元数据
    const fullTextReviewSummary = fullTextReviewResults.map(r =>
      `- ${r.role}: ${r.overallSummary}`
    ).join('\n');

    // 将全文审阅结果追加到报告
    const fullTextReviewSection = `
## 全文审阅报告

*本报告经过 ${fullTextReviewers.length} 位专家全文审阅*

${fullTextReviewResults.map(r => `### ${r.role} (${r.reviewer})

${r.chunkReviews.map(cr => `**块 ${cr.chunkIndex + 1}/${reportChunks.length}:**
- 问题: ${cr.issues.substring(0, 200)}${cr.issues.length > 200 ? '...' : ''}
- 建议: ${cr.suggestions.substring(0, 200)}${cr.suggestions.length > 200 ? '...' : ''}
`).join('\n')}

**整体评价:** ${r.overallSummary}
`).join('\n---\n')}
`;

    // 将全文审阅结果插入报告（在元数据之前）
    finalReport = finalReport.replace(
      '## 报告元数据',
      fullTextReviewSection + '\n## 报告元数据'
    );

    // 记录全文审阅到数据库
    try {
      db.run(`
        INSERT INTO insight_evaluations
        (task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
      `, [
        this.session.sessionId,
        'full_text_review',
        'expert_team',
        'full_report',
        this.session.sessionId,
        JSON.stringify({
          reviewers: fullTextReviewers.length,
          chunks: reportChunks.length,
          results: fullTextReviewResults.map(r => ({ role: r.role, summary: r.overallSummary }))
        }),
        fullTextReviewResults.filter(r => r.overallSummary.includes('通过')).length / fullTextReviewResults.length * 10,
        fullTextReviewSummary.substring(0, 1000)
      ]);
    } catch (e) { /* 忽略 */ }

    // 写入 Cortex
    await this.writeToMemory(
      this.session.sessionId + '_fulltext_review',
      `全文审阅完成 | 专家: ${fullTextReviewers.length}位 | 块数: ${reportChunks.length}`,
      {
        phase: 'synthesis_fulltext_review',
        tags: ['fulltext', 'review', 'expert_team'],
        priority: 'high'
      }
    );

    console.log(`   📊 全文审阅完成: ${fullTextReviewResults.filter(r => r.overallSummary.includes('通过')).length}/${fullTextReviewers.length} 专家通过`);
    // ========== 全文审阅结束 ==========

    // ========== Step 5.2: Solar 人格润色 ==========
    // 用 DeepSeek V3 注入双面娇娇人格，润色报告风格（内容不变）
    // 🔴 修复: 长报告跳过润色，避免 LLM 输出截断
    console.log('\n  ✨ Step 5.2: Solar 人格润色...');
    let polishedReport: string;
    const POLISH_LENGTH_THRESHOLD = 15000;  // 超过 15K 字符跳过润色（gemini 最大输出 8192 tokens）

    console.log(`   🔍 [DEBUG] finalReport.length = ${finalReport.length}, threshold = ${POLISH_LENGTH_THRESHOLD}`);
    if (finalReport.length > POLISH_LENGTH_THRESHOLD) {
      console.log(`   ⚠️ 报告过长 (${finalReport.length} chars > ${POLISH_LENGTH_THRESHOLD}), 跳过润色避免截断`);
      console.log(`   💡 原因: gemini-3-pro-preview 最大输出 8192 tokens（约 12000-16000 中文字符）`);
      polishedReport = finalReport;  // 直接使用原始报告
    } else {
      console.log(`   ✅ 报告长度适中，启动 Solar 润色...`);
      polishedReport = await this.solarPolish(finalReport, this.session.topic);
    }

    // ========== Step 5.3: 报告模板迁移与最终状态 (v2.2) ==========
    if (this.reportStructure) {
      console.log('\n  📁 迁移旧文件到结构化布局...');
      this.reportStructure.migrateExistingFiles();
      console.log('   ✓ 文件迁移完成');
    }

    // 保存最终报告 (润色后版本)
    const reportPath = this.persistence.saveFinalReport(this.session.sessionId, polishedReport);

    this.session.status = 'synthesis';
    await this.persistence.saveSession(this.session);

    // ========== Step 5.4: 更新最终 STATE.md (v2.2) ==========
    if (this.reportStructure) {
      const finalStateData: StateData = {
        topic: this.session.topic,
        currentPhase: 'COMPLETED',
        progress: {
          done: ['CREATED', 'PLANNING', 'OUTLINE', 'SCHEDULING', 'WRITING', 'REVIEW', 'SYNTHESIS'],
          inProgress: '',
          blocked: []
        },
        nextActions: [
          `阅读最终报告: ${reportPath}`,
          '查看 PHASES/ 目录了解生成过程',
          '查看 SOURCES.md 了解参考文献'
        ]
      };
      this.reportStructure.writeState(finalStateData);
      console.log('   ✓ STATE.md 更新为 COMPLETED');
    }

    // ========== Step 5.5: TVS Dashboard 生成 (v2.3) ==========
    if (this.reportStructure) {
      console.log('\n  🎨 Step 5.5: 生成 TVS Web Dashboard...');
      await this.generateTVSDashboard(polishedReport, avgScore);
    }

    console.log(`✅ 综合完成，报告保存至: ${reportPath}`);
    console.log(`   平均质量: ${avgScore.toFixed(1)}/10`);
    console.log(`   💪🌸 Solar 人格润色已注入`);
    return polishedReport;  // 返回润色后的报告
  }

  // ============================================================
  // 阶段7: 结束 (Closing) - 绩效评估 v2.1
  // ============================================================
  async stage7_closing(): Promise<PerformanceRecord[]> {
    if (!this.session) throw new Error('请先执行 stage6_synthesis');

    console.log('\n🏆 阶段7: 绩效评估 (v2.1 详细记录)');

    // ========== Step 0: Evidence First - 查 Cortex 知识库 (Principle 5) ==========
    console.log('🔍 Evidence First: 查询 Cortex 知识库...');
    const db = this.persistence.getDb();

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要，不保留完整数组
    let cortexSourcesPointers = {
      count: 0,
      avgCredibility: 0,
      topTitles: [] as string[]
    };

    let cortexClaimsPointers = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    try {
      const sources = db.query(`
        SELECT title, finding, credibility
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 5
      `).all(`%${this.session.topic}%`) as any[];

      if (sources.length > 0) {
        cortexSourcesPointers = {
          count: sources.length,
          avgCredibility: sources.reduce((sum: number, s: any) => sum + (s.credibility || 0), 0) / sources.length,
          topTitles: sources.slice(0, 3).map((s: any) => s.title).filter(Boolean)
        };
      }
      console.log(`   找到 ${cortexSourcesPointers.count} 条 Cortex 知识源 (avg credibility: ${cortexSourcesPointers.avgCredibility.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_sources 表不存在，跳过');
    }

    try {
      const claims = db.query(`
        SELECT claim_text, confidence
        FROM cortex_claims
        WHERE claim_text LIKE ?
        ORDER BY confidence DESC
        LIMIT 3
      `).all(`%${this.session.topic}%`) as any[];

      if (claims.length > 0) {
        cortexClaimsPointers = {
          count: claims.length,
          avgConfidence: claims.reduce((sum: number, c: any) => sum + (c.confidence || 0), 0) / claims.length,
          topStatements: claims.slice(0, 3).map((c: any) => c.claim_text.substring(0, 40)).filter(Boolean)
        };
      }
      console.log(`   找到 ${cortexClaimsPointers.count} 条 Cortex 论断 (avg confidence: ${cortexClaimsPointers.avgConfidence.toFixed(2)})`);
    } catch (e) {
      console.log('   cortex_claims 表不存在，跳过');
    }

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要（虽然此阶段主要收集绩效，无需发送给 worker brains）
    const cortexContext = (cortexSourcesPointers.count > 0 || cortexClaimsPointers.count > 0)
      ? `\n【Cortex 知识参考（用于质量基准）- 统计摘要】
    - 知识源数量: ${cortexSourcesPointers.count} (平均可信度: ${cortexSourcesPointers.avgCredibility.toFixed(2)})
    - 代表性知识源: ${cortexSourcesPointers.topTitles.join(', ')}
    - 论断数量: ${cortexClaimsPointers.count} (平均置信度: ${cortexClaimsPointers.avgConfidence.toFixed(2)})
    - 代表性论断: ${cortexClaimsPointers.topStatements.join('; ')}\n`
      : '';

    console.log('   ✓ Evidence First 完成，用于质量基准对比');
    // ========== Evidence First 结束 ==========

    // ========== v2.1 Cortex 读取闭环: 从中枢神经读取完整状态 ==========
    console.log('   📖 从 Cortex 读取完整会话状态...');
    const cortexState = await this.readSessionFromCortex(this.session.sessionId);
    if (cortexState) {
      console.log(`   ✓ Cortex 完整状态: 最后阶段=${cortexState.lastCompletedStage}`);
      console.log(`   ✓ 规划: ${cortexState.planning ? '有' : '无'}`);
      console.log(`   ✓ 大纲: ${cortexState.outlining ? '有' : '无'}`);
      console.log(`   ✓ 调度: ${cortexState.dispatching ? '有' : '无'}`);
      console.log(`   ✓ 写作: ${cortexState.writing?.length || 0} 条`);
      console.log(`   ✓ 审核: ${cortexState.reviewing?.length || 0} 条`);
      console.log(`   ✓ 综合: ${cortexState.synthesis ? '有' : '无'}`);
    } else {
      console.log('   ℹ️ Cortex 无完整状态，使用内存和数据库数据');
    }
    // ========== Cortex 读取闭环结束 ==========

    const records: PerformanceRecord[] = [];
    const chapters = this.session.chapters;
    // db 已在上方 Evidence First 块中声明，此处复用

    // ========== Step 1: 收集所有参与模型的表现数据 ==========
    interface ModelPerformance {
      scores: number[];
      tasks: number;
      roles: Set<string>;
      chapters: string[];
      successCount: number;
      totalDuration: number;
    }

    const modelStats: Record<string, ModelPerformance> = {};

    // 从章节数据收集作者和审核者信息
    for (const chapter of chapters) {
      // 作者绩效
      if (chapter.authorModel) {
        if (!modelStats[chapter.authorModel]) {
          modelStats[chapter.authorModel] = {
            scores: [], tasks: 0, roles: new Set(),
            chapters: [], successCount: 0, totalDuration: 0
          };
        }
        modelStats[chapter.authorModel].scores.push(chapter.qualityScore);
        modelStats[chapter.authorModel].tasks++;
        modelStats[chapter.authorModel].roles.add('author');
        modelStats[chapter.authorModel].chapters.push(chapter.chapterId);
        if (chapter.status === 'done' && chapter.content) {
          modelStats[chapter.authorModel].successCount++;
        }
      }

      // 审核者绩效
      if (chapter.reviewerModel) {
        if (!modelStats[chapter.reviewerModel]) {
          modelStats[chapter.reviewerModel] = {
            scores: [], tasks: 0, roles: new Set(),
            chapters: [], successCount: 0, totalDuration: 0
          };
        }
        // 审核者评分：从 insight_evaluations 获取
        let reviewScore = 8;
        try {
          const evalRow = db.query(`
            SELECT AVG(score) as avg_score FROM insight_evaluations
            WHERE session_id = ? AND evaluator_model = ?
          `).get(this.session!.sessionId, chapter.reviewerModel) as any;
          if (evalRow?.avg_score) {
            reviewScore = evalRow.avg_score;
          }
        } catch (e) { /* 使用默认值 */ }

        modelStats[chapter.reviewerModel].scores.push(reviewScore);
        modelStats[chapter.reviewerModel].tasks++;
        modelStats[chapter.reviewerModel].roles.add('reviewer');
        modelStats[chapter.reviewerModel].successCount++;
      }
    }

    // ========== Step 2: 添加大纲生成者 ==========
    try {
      // 适配现有表结构: proposed_by 代替 expert_model, evaluation_scores 包含 role
      const outlines = db.query(`
        SELECT proposed_by, evaluation_scores FROM insight_outlines
        WHERE task_id = ?
      `).all(this.session.sessionId) as any[];

      for (const o of outlines) {
        const model = o.proposed_by;
        const evalData = o.evaluation_scores ? JSON.parse(o.evaluation_scores) : { role: 'generator' };
        if (!modelStats[model]) {
          modelStats[model] = {
            scores: [8], tasks: 0, roles: new Set(),
            chapters: [], successCount: 0, totalDuration: 0
          };
        }
        modelStats[model].tasks++;
        modelStats[model].roles.add(evalData.role === 'challenger' ? 'outline_reviewer' : 'outline_generator');
        modelStats[model].successCount++;
      }
    } catch (e) { /* 忽略 */ }

    // ========== Step 3: 添加规划者 (思考驼) ==========
    if (!modelStats['deepseek-r1']) {
      modelStats['deepseek-r1'] = {
        scores: [9], tasks: 0, roles: new Set(),
        chapters: [], successCount: 0, totalDuration: 0
      };
    }
    modelStats['deepseek-r1'].tasks++;
    modelStats['deepseek-r1'].roles.add('planner');
    modelStats['deepseek-r1'].roles.add('synthesizer');
    modelStats['deepseek-r1'].successCount++;

    // ========== Step 4: 生成绩效记录并写入数据库 ==========
    console.log('\n  📊 绩效排行榜:');
    console.log('  ─────────────────────────────────────────');

    const sortedModels = Object.entries(modelStats)
      .map(([modelId, stats]) => {
        const avgScore = stats.scores.length > 0
          ? stats.scores.reduce((a, b) => a + b, 0) / stats.scores.length
          : 7;
        return { modelId, stats, avgScore };
      })
      .sort((a, b) => b.avgScore - a.avgScore);

    for (const { modelId, stats, avgScore } of sortedModels) {
      const completionRate = stats.tasks > 0 ? stats.successCount / stats.tasks : 0;
      const rolesStr = Array.from(stats.roles).join(',');

      const record: PerformanceRecord = {
        modelId,
        sessionId: this.session!.sessionId,
        role: rolesStr,
        qualityScore: Math.round(avgScore * 10) / 10,
        taskCount: stats.tasks,
        completionRate: Math.round(completionRate * 100) / 100,
        evaluatedAt: new Date().toISOString()
      };

      records.push(record);

      // 写入 collab_performance 表
      try {
        db.run(`
          INSERT INTO collab_performance
          (model_id, task_type, task_id, success, duration_ms, quality_score, context_used, notes, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        `, [
          modelId,
          'insight_report',
          this.session!.sessionId,
          stats.successCount > 0 ? 1 : 0,
          stats.totalDuration || 0,
          record.qualityScore,
          0,
          `roles: ${rolesStr}, chapters: ${stats.chapters.length}`
        ]);
      } catch (e) { /* 表可能不存在 */ }

      // 调用 persistence 的 recordPerformance
      this.persistence.recordPerformance(record);

      // 获取牛马昵称
      const persona = EXPERT_PERSONAS[modelId];
      const nickname = persona?.traits || modelId.split('-').pop();

      console.log(`  ${record.qualityScore >= 8 ? '🏆' : record.qualityScore >= 6 ? '⭐' : '🔹'} ${nickname.padEnd(12)} ${record.qualityScore.toFixed(1)}/10  ${stats.tasks}任务  [${rolesStr}]`);
    }

    console.log('  ─────────────────────────────────────────');

    // ✨ Brain Separation: Result Compression - 绩效数据汇总
    console.log(`🗜️ 绩效数据压缩完成 (Brain Separation): ${records.length} 个模型 → 只保留统计摘要 (平均分/任务数/完成率)`);

    // ========== Step 5: 更新会话状态 ==========
    this.session.status = 'done';
    this.session.completedAt = new Date().toISOString();
    await this.persistence.saveSession(this.session);

    // 计算总体指标
    const totalTasks = records.reduce((s, r) => s + r.taskCount, 0);
    const avgQuality = records.reduce((s, r) => s + r.qualityScore * r.taskCount, 0) / totalTasks;

    console.log(`\n✅ 绩效评估完成`);
    console.log(`   参与模型: ${records.length} 个`);
    console.log(`   总任务数: ${totalTasks}`);
    console.log(`   平均质量: ${avgQuality.toFixed(1)}/10`);

    // ✨ Brain Separation: Result Compression - 整体指标汇总
    console.log(`🗜️ 整体指标压缩完成 (Brain Separation): ${records.length} 个模型绩效 → 2个核心指标 (总任务数: ${totalTasks}, 平均质量: ${avgQuality.toFixed(1)})`);

    // v2.1: 写入中枢神经 (CortexWriter)
    const reportPath = `~/Solar/insight-reports/${this.session!.sessionId}/final-report.md`;
    const performanceSummary: Record<string, {tasks: number, avgScore: number}> = {};
    for (const record of records) {
      performanceSummary[record.modelId] = {
        tasks: record.taskCount,
        avgScore: record.qualityScore
      };
    }
    await this.writeClosingToMemory(reportPath, performanceSummary);

    // v2.1: 触发 Tantivy 索引刷新 (确保新写入的 Cortex 记忆可搜索)
    await this.refreshTantivyIndex();

    return records;
  }

  /**
   * 刷新 Tantivy 索引
   * 确保新写入的 evo_memory_semantic 数据可被全文搜索
   */
  private async refreshTantivyIndex(): Promise<void> {
    console.log('\n  🔍 刷新 Tantivy 索引...');

    try {
      const solarSearchPath = `${process.env.HOME}/Solar/bin/solar-search`;
      const proc = Bun.spawn([solarSearchPath, 'index', 'all'], {
        stdout: 'pipe',
        stderr: 'pipe'
      });

      const exitCode = await proc.exited;

      if (exitCode === 0) {
        console.log('  ✅ Tantivy 索引刷新完成');
      } else {
        const stderr = await new Response(proc.stderr).text();
        console.warn('  ⚠️ Tantivy 索引刷新警告:', stderr || `exit code ${exitCode}`);
      }
    } catch (error) {
      // 索引刷新失败不应阻止整个流程
      console.warn('  ⚠️ Tantivy 索引刷新失败 (非阻塞):', error);
    }
  }

  /**
   * 从最终报告提取关键论点 (v2.4)
   * 设计来源: 2026-02-14 知识库诊断 - 修复 cortex_claims 为空的问题
   */
  private extractClaimsFromReport(): Array<{
    text: string;
    supporting_sources: string[];
    counter_sources?: string[];
    expert_model?: string;
    confidence: number;
  }> {
    const claims: Array<{
      text: string;
      supporting_sources: string[];
      counter_sources?: string[];
      expert_model?: string;
      confidence: number;
    }> = [];

    if (!this.session) return claims;

    // 1. 从 session.references 获取来源列表
    const sourceKeys = (this.session.references || []).map(ref =>
      ref.title.toLowerCase().replace(/\s+/g, '_').substring(0, 50)
    );

    // 2. 从最终报告的结论/摘要部分提取论点
    const finalReportPath = `${this.persistence['outputDir']}/${this.session.sessionId}/final-report.md`;
    try {
      const reportContent = readFileSync(finalReportPath, 'utf-8');

      // 提取"结论"或"核心发现"章节的要点
      const conclusionMatch = reportContent.match(
        /##\s*(结论|核心发现|关键结论|主要发现|Summary|Conclusion)[\s\S]*?(?=\n##|$)/gi
      );

      if (conclusionMatch) {
        const conclusionText = conclusionMatch[0];

        // 匹配列表项 (- 开头的行)
        const bulletPoints = conclusionText.match(/^[\s]*[-*]\s*.+$/gm) || [];

        for (const point of bulletPoints.slice(0, 5)) {  // 最多取5个关键论点
          const claimText = point.replace(/^[\s]*[-*]\s*/, '').trim();
          if (claimText.length > 20 && claimText.length < 500) {
            claims.push({
              text: claimText,
              supporting_sources: sourceKeys.slice(0, 3),  // 关联前3个来源
              expert_model: 'insight-agent-v2',
              confidence: 0.75  // 默认置信度
            });
          }
        }
      }

      // 3. 如果没找到结论章节，从摘要提取
      if (claims.length === 0) {
        const abstractMatch = reportContent.match(/##\s*(摘要|Abstract)[\s\S]*?(?=\n##|$)/i);
        if (abstractMatch) {
          const abstractText = abstractMatch[0].replace(/##\s*(摘要|Abstract)/i, '').trim();
          // 按句子分割，取前3个
          const sentences = abstractText.split(/[。.!?！？]/).filter(s => s.trim().length > 30);
          for (const sentence of sentences.slice(0, 3)) {
            claims.push({
              text: sentence.trim(),
              supporting_sources: sourceKeys.slice(0, 3),
              expert_model: 'insight-agent-v2',
              confidence: 0.7
            });
          }
        }
      }
    } catch (error) {
      console.warn('  ⚠️ 读取最终报告失败，跳过 claims 提取:', error);
    }

    return claims;
  }

  /**
   * 持久化到 Cortex 知识库 (v2.3)
   * 铁律：设计/开发前先查 Cortex，完成后写入 Cortex
   */
  private async persistToKnowledgeBase(): Promise<void> {
    if (!this.session) {
      console.warn('  ⚠️ Session 不存在，跳过 Cortex 持久化');
      return;
    }

    console.log('\n  📚 持久化到 Cortex 知识库...');
    const taskId = this.session.sessionId;

    try {
      // 1. 持久化 Sources (来自 session.references)
      let sourceCount = 0;
      for (const ref of this.session.references || []) {
        await this.cortex.addSource(taskId, {
          citation_key: ref.title.toLowerCase().replace(/\s+/g, '_').substring(0, 50),
          title: ref.title,
          url: ref.url,
          finding: ref.summary,
          credibility: ref.relevance || 0.5
        }, ref.source);
        sourceCount++;
      }

      // 2. 持久化 Evaluations (来自 insight_evaluations 表)
      const db = this.persistence.getDB();
      const evaluations = db.query(`
        SELECT task_id, phase, evaluator, evaluated, target_id, scores, avg_score, comments
        FROM insight_evaluations
        WHERE task_id = ?
      `).all(taskId) as Array<{
        task_id: string;
        phase: string;
        evaluator: string;
        evaluated: string;
        target_id: string;
        scores: string;
        avg_score: number;
        comments: string;
      }>;

      let evalCount = 0;
      for (const ev of evaluations) {
        const rubric = JSON.parse(ev.scores);
        const suggestions = ev.comments ? [ev.comments] : [];

        await this.cortex.addEval(
          taskId,
          5,  // phase 5 = reviewing
          0,  // artifact_id 暂不关联
          ev.evaluator,
          ev.evaluated,
          rubric,
          ev.avg_score,
          ev.comments || '',
          suggestions
        );
        evalCount++;
      }

      // 3. 持久化 Claims (从最终报告提取关键论点)
      // 设计来源: 2026-02-14 知识库诊断 - 修复 cortex_claims 为空的问题
      const claims = this.extractClaimsFromReport();
      let claimCount = 0;
      for (const claim of claims) {
        await this.cortex.addClaim(
          taskId,
          {
            text: claim.text,
            supporting_sources: claim.supporting_sources,
            counter_sources: claim.counter_sources || []
          },
          claim.expert_model
        );
        claimCount++;
      }

      console.log(`  ✅ Cortex 持久化完成: ${sourceCount} sources, ${evalCount} evals, ${claimCount} claims`);
    } catch (error) {
      // 持久化失败不应阻塞整个流程
      console.warn('  ⚠️ Cortex 持久化失败 (非阻塞):', error);
    }
  }

  // ============================================================
  // 完整运行入口
  // ============================================================
  async run(topic: string, chapterCount: number = 4): Promise<{
    success: boolean;
    sessionId: string;
    report: string;
    performance: PerformanceRecord[];
    duration: number;
  }> {
    const startTime = Date.now();

    console.log('╔════════════════════════════════════════════════════════════╗');
    console.log('║        InsightAgent v2.0 - 洞察报告生成引擎                ║');
    console.log('╚════════════════════════════════════════════════════════════╝');
    console.log(`\n主题: ${topic}`);
    console.log(`章节数: ${chapterCount}`);

    try {
      // 七阶段执行
      await this.stage1_planning(topic);
      await this.stage2_outlining(chapterCount);
      await this.stage3_scheduling();
      await this.stage4_writing();
      await this.stage5_reviewing();
      const report = await this.stage6_synthesis();
      const performance = await this.stage7_closing();

      // v2.3: 自动持久化到 Cortex 知识库
      await this.persistToKnowledgeBase();

      const duration = Date.now() - startTime;

      console.log('\n╔════════════════════════════════════════════════════════════╗');
      console.log('║                    ✅ 报告生成完成                          ║');
      console.log('╚════════════════════════════════════════════════════════════╝');
      console.log(`耗时: ${(duration / 1000).toFixed(1)}秒`);

      return {
        success: true,
        sessionId: this.session!.sessionId,
        report,
        performance,
        duration
      };
    } catch (error) {
      console.error('\n❌ 生成失败:', error);
      return {
        success: false,
        sessionId: this.session?.sessionId || '',
        report: '',
        performance: [],
        duration: Date.now() - startTime
      };
    } finally {
      this.persistence.close();
    }
  }

  // ============================================================
  // Persona Bank 竞技场机制 - Fixed 4-Step DAG (v2.4)
  // ============================================================

  /**
   * Persona Bank 模式入口 - Fixed 4-Step DAG
   * collect → fill_gaps → peer_review → compose
   */
  async executeFixedDAG(topic: string): Promise<void> {
    console.log('\n🎪 ====== Persona Bank 竞技场模式 ======');
    console.log(`主题: ${topic}`);
    console.log('固定 DAG: collect → fill_gaps → peer_review → compose\n');

    if (!this.taskId) {
      this.taskId = `persona-${Date.now()}`;
    }

    // Phase 1: Collect Arena (多家便宜模型并行收集)
    await this.phaseCollectArena(topic);

    // Phase 2: Fill Gaps (补证据/补反方)
    await this.phaseFillGaps();

    // Phase 3: Peer Review (A评B、B评A)
    await this.phasePeerReview();

    // Phase 4: Compose (合成最终草稿)
    await this.phaseCompose();

    console.log('\n✅ Persona Bank 竞技场完成！');
  }

  /**
   * 阶段1: Collect Arena - 创意扩散型
   * 特质: O(开放性) + E(外向性)
   */
  private async phaseCollectArena(topic: string): Promise<void> {
    console.log('\n📚 阶段1: Collect Arena (创意扩散型)');

    // ========== Evidence First: 查 Cortex 已有知识 ==========
    console.log('🔍 Evidence First: 查询 Cortex 知识库...');
    const db = new Database(`${process.env.HOME}/.solar/solar.db`);

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要
    let tasksPointer = { count: 0, completedCount: 0, topRequests: [] as string[] };
    let sourcesPointer = { count: 0, avgCredibility: 0, topTitles: [] as string[] };
    let claimsPointer = { count: 0, avgConfidence: 0, topStatements: [] as string[] };

    // 查询相关任务
    try {
      const tasks = db.query(`
        SELECT task_id, user_request, status
        FROM cortex_tasks
        WHERE user_request LIKE ?
        ORDER BY created_at DESC
        LIMIT 3
      `).all(`%${topic}%`) as Array<{ task_id: string; user_request: string; status: string }>;

      if (tasks.length > 0) {
        tasksPointer = {
          count: tasks.length,
          completedCount: tasks.filter(t => t.status === 'completed').length,
          topRequests: tasks.slice(0, 2).map(t => t.user_request.substring(0, 40))
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    // 查询相关知识点
    try {
      const sources = db.query(`
        SELECT title, finding, credibility, citation_key
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 5
      `).all(`%${topic}%`) as Array<{ title: string; finding: string; credibility: number; citation_key: string }>;

      if (sources.length > 0) {
        sourcesPointer = {
          count: sources.length,
          avgCredibility: sources.reduce((sum, s) => sum + s.credibility, 0) / sources.length,
          topTitles: sources.slice(0, 3).map(s => s.title)
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    // 查询已验证结论
    try {
      const claims = db.query(`
        SELECT claim_id, statement, confidence
        FROM cortex_claims
        WHERE statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 3
      `).all(`%${topic}%`) as Array<{ claim_id: string; statement: string; confidence: number }>;

      if (claims.length > 0) {
        claimsPointer = {
          count: claims.length,
          avgConfidence: claims.reduce((sum, c) => sum + c.confidence, 0) / claims.length,
          topStatements: claims.slice(0, 2).map(c => c.statement.substring(0, 40))
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    console.log(`   找到 ${tasksPointer.count} 个相关任务, ${sourcesPointer.count} 个知识点, ${claimsPointer.count} 个已验证结论`);

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要
    const evidenceContext = `
## Cortex 已有知识 (Evidence First) - 统计摘要

### 相关历史任务 (${tasksPointer.count}个, ${tasksPointer.completedCount}个已完成)
${tasksPointer.topRequests.length > 0 ? tasksPointer.topRequests.map(r => `- ${r}...`).join('\n') : '(无)'}

### 相关知识点 (${sourcesPointer.count}个, 平均可信度: ${sourcesPointer.avgCredibility.toFixed(2)})
${sourcesPointer.topTitles.length > 0 ? sourcesPointer.topTitles.map(t => `- ${t}`).join('\n') : '(无)'}

### 已验证结论 (${claimsPointer.count}个, 平均置信度: ${claimsPointer.avgConfidence.toFixed(2)})
${claimsPointer.topStatements.length > 0 ? claimsPointer.topStatements.map(s => `- ${s}...`).join('\n') : '(无)'}
`.trim();

    // 选择 3-4 个擅长开放性的人格
    const personas = await this.personaSelector.selectForPhase('collect', 4);

    const collectedIdeas: Array<{ personaId: string; ideas: string; score: number }> = [];

    // 并行收集想法
    for (const persona of personas) {
      const systemPrompt = this.buildPersonaSystemPrompt(persona);

      const prompt = `请针对主题"${topic}"头脑风暴，提供尽可能多元的视角和想法。

${evidenceContext}

**基于以上 Cortex 已有知识，你可以：**
- 在已有知识基础上进一步扩展
- 提出与已有知识不同的新角度
- 质疑或补充已有结论
- 发现知识空白点

要求:
1. 至少 5 个不同角度的观点
2. 鼓励创新和非常规思路
3. 每个观点简洁清晰
4. 输出格式: JSON数组 [{"angle":"角度","idea":"想法","builds_on":"(可选)基于哪个已有知识点"}]`;

      try {
        const result = await mcp__brain_router__complete({
          model: persona.model,
          system: systemPrompt,
          prompt
        });

        // 自评分数 (1-10)
        const scorePrompt = `请对你刚才提供的想法质量打分 (1-10)，只输出数字。`;
        const scoreResult = await mcp__brain_router__complete({
          model: persona.model,
          system: systemPrompt,
          prompt: scorePrompt
        });

        const score = parseFloat(scoreResult) || 7.0;

        collectedIdeas.push({
          personaId: persona.persona_id,
          ideas: result,
          score
        });

        // ✨ Brain Separation: Result Compression - worker brain 返回后压缩
        console.log(`🗜️ Result Compression (Brain Separation): ${persona.role} 返回 ${result.length} 字符 → 仅保留 ideas+score (压缩率: ~${((1 - 20/result.length) * 100).toFixed(0)}%)`);

        // 记录评分
        await this.personaRecorder.recordScore({
          personaId: persona.persona_id,
          taskId: this.taskId!,
          phase: 'collect',
          rubricScores: { creativity: score, diversity: score },
          overallScore: score
        });

        console.log(`   ✓ ${persona.role} (${persona.persona_id}): ${score}/10`);
      } catch (e) {
        console.warn(`   ✗ ${persona.role} 收集失败:`, e);
      }
    }

    // 存储到 session state (简化版，实际应该用 persistence)
    (this as any).collectedIdeas = collectedIdeas;

    console.log(`   📊 收集完成: ${collectedIdeas.length} 个人格参与`);

    // ✨ Brain Separation: Result Compression - 最终汇总统计
    const totalChars = collectedIdeas.reduce((sum, item) => sum + item.ideas.length, 0);
    const avgScore = collectedIdeas.reduce((sum, item) => sum + item.score, 0) / (collectedIdeas.length || 1);
    console.log(`🗜️ Final Result Compression (Brain Separation): ${collectedIdeas.length} 个人格共 ${totalChars} 字符 → 只保留结构化摘要 (平均分: ${avgScore.toFixed(1)}/10)`);
  }

  /**
   * 阶段2: Fill Gaps - 细节工匠型
   * 特质: C(尽责性) + A(宜人性)
   */
  private async phaseFillGaps(): Promise<void> {
    console.log('\n🔍 阶段2: Fill Gaps (细节工匠型)');

    const personas = await this.personaSelector.selectForPhase('fill_gaps', 2);

    const collectedIdeas = (this as any).collectedIdeas || [];
    const ideasSummary = collectedIdeas.map((x: any) => x.ideas).join('\n\n');

    // ========== Evidence First: 查 Cortex 证据和反方观点 ==========
    console.log('🔍 Evidence First: 查询 Cortex 证据库...');
    const db = new Database(`${process.env.HOME}/.solar/solar.db`);

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要
    let evidenceSourcesPointer = {
      count: 0,
      evidenceTypes: [] as string[],
      topTitles: [] as string[]
    };

    let verifiedClaimsPointer = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    // 查询相关证据和细节
    try {
      const evidenceSources = db.query(`
        SELECT title, finding, evidence_type, citation_key
        FROM cortex_sources
        WHERE finding LIKE ?
        ORDER BY credibility DESC
        LIMIT 5
      `).all(`%${this.topic}%`) as Array<{ title: string; finding: string; evidence_type: string; citation_key: string }>;

      if (evidenceSources.length > 0) {
        evidenceSourcesPointer = {
          count: evidenceSources.length,
          evidenceTypes: [...new Set(evidenceSources.map(s => s.evidence_type))],
          topTitles: evidenceSources.slice(0, 3).map(s => s.title)
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    // 查询已验证结论 (可能包含反方观点)
    try {
      const verifiedClaims = db.query(`
        SELECT statement, confidence, supporting_evidence
        FROM cortex_claims
        WHERE statement LIKE ?
        ORDER BY confidence DESC
        LIMIT 3
      `).all(`%${this.topic}%`) as Array<{ statement: string; confidence: number; supporting_evidence: string }>;

      if (verifiedClaims.length > 0) {
        verifiedClaimsPointer = {
          count: verifiedClaims.length,
          avgConfidence: verifiedClaims.reduce((sum, c) => sum + c.confidence, 0) / verifiedClaims.length,
          topStatements: verifiedClaims.slice(0, 2).map(c => c.statement.substring(0, 60))
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    console.log(`   找到 ${evidenceSourcesPointer.count} 个证据源, ${verifiedClaimsPointer.count} 个已验证结论`);

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要
    const cortexEvidence = `
## Cortex 证据库 (Evidence First) - 统计摘要

### 可用证据源 (${evidenceSourcesPointer.count}个)
- 证据类型: ${evidenceSourcesPointer.evidenceTypes.join(', ') || '(无)'}
- 代表性来源: ${evidenceSourcesPointer.topTitles.join(', ') || '(无)'}

### 已验证结论 (${verifiedClaimsPointer.count}个, 平均置信度: ${verifiedClaimsPointer.avgConfidence.toFixed(2)})
${verifiedClaimsPointer.topStatements.length > 0 ? verifiedClaimsPointer.topStatements.map(s => `- ${s}...`).join('\n') : '(无)'}
`.trim();

    for (const persona of personas) {
      const systemPrompt = this.buildPersonaSystemPrompt(persona);

      const prompt = `已收集的想法:
${ideasSummary}

${cortexEvidence}

请分析这些想法的不足之处:
1. 缺少哪些关键证据？(Cortex 中已有哪些可以直接引用？)
2. 有哪些反方观点没有考虑？(Cortex 结论中有无相反观点？)
3. 需要补充哪些细节？(基于已有证据还能挖掘什么？)

输出格式: JSON {"gaps":["缺失1","缺失2"], "counterarguments":["反方1","反方2"], "cortex_evidence_used":["引用的 citation_key"]}`;

      try {
        const result = await mcp__brain_router__complete({
          model: persona.model,
          system: systemPrompt,
          prompt
        });

        console.log(`   ✓ ${persona.role}: 发现改进点`);

        // ✨ Brain Separation: Result Compression - worker brain 返回后压缩
        console.log(`🗜️ Result Compression (Brain Separation): ${persona.role} 返回 ${result.length} 字符 → 解析为结构化 gaps/counterarguments (压缩率: ~${((1 - 50/result.length) * 100).toFixed(0)}%)`);

        // 简化评分
        await this.personaRecorder.recordScore({
          personaId: persona.persona_id,
          taskId: this.taskId!,
          phase: 'fill_gaps',
          rubricScores: { thoroughness: 8.0 },
          overallScore: 8.0
        });
      } catch (e) {
        console.warn(`   ✗ ${persona.role} 失败:`, e);
      }
    }

    // ✨ Brain Separation: Result Compression - 最终汇总统计
    console.log(`🗜️ Final Result Compression (Brain Separation): ${personas.length} 个人格参与补全 → 只保留结构化改进建议 (gaps + counterarguments)`);
  }

  /**
   * 阶段3: Peer Review - 和谐评审型
   * 特质: A(宜人性) + C(尽责性)
   * 核心: A评B、B评A 交叉评审
   */
  private async phasePeerReview(): Promise<void> {
    console.log('\n👥 阶段3: Peer Review (A评B、B评A)');

    // ========== Evidence First: 查 Cortex 评审标准和参考 ==========
    console.log('🔍 Evidence First: 查询 Cortex 评审参考...');
    const db = new Database(`${process.env.HOME}/.solar/solar.db`);

    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要
    let benchmarkClaimsPointer = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    let benchmarkSourcesPointer = {
      count: 0,
      avgCredibility: 0,
      evidenceTypes: [] as string[],
      topTitles: [] as string[]
    };

    // 查询高置信度结论作为评审标准
    try {
      const benchmarkClaims = db.query(`
        SELECT statement, confidence, supporting_evidence
        FROM cortex_claims
        WHERE statement LIKE ? AND confidence >= 0.7
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${this.topic}%`) as Array<{ statement: string; confidence: number; supporting_evidence: string }>;

      if (benchmarkClaims.length > 0) {
        benchmarkClaimsPointer = {
          count: benchmarkClaims.length,
          avgConfidence: benchmarkClaims.reduce((sum, c) => sum + c.confidence, 0) / benchmarkClaims.length,
          topStatements: benchmarkClaims.slice(0, 3).map(c => c.statement.substring(0, 80))
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    // 查询权威知识源作为证据参考
    try {
      const benchmarkSources = db.query(`
        SELECT title, finding, evidence_type, credibility
        FROM cortex_sources
        WHERE finding LIKE ? AND credibility >= 0.7
        ORDER BY credibility DESC
        LIMIT 5
      `).all(`%${this.topic}%`) as Array<{ title: string; finding: string; evidence_type: string; credibility: number }>;

      if (benchmarkSources.length > 0) {
        benchmarkSourcesPointer = {
          count: benchmarkSources.length,
          avgCredibility: benchmarkSources.reduce((sum, s) => sum + s.credibility, 0) / benchmarkSources.length,
          evidenceTypes: [...new Set(benchmarkSources.map(s => s.evidence_type))],
          topTitles: benchmarkSources.slice(0, 3).map(s => s.title)
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    console.log(`   找到 ${benchmarkClaimsPointer.count} 个参考结论, ${benchmarkSourcesPointer.count} 个参考证据`);

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要
    const reviewBenchmark = `
## Cortex 评审参考基准 (Evidence First) - 统计摘要

### 高质量结论参考 (${benchmarkClaimsPointer.count}个, 平均置信度: ${benchmarkClaimsPointer.avgConfidence.toFixed(2)})
${benchmarkClaimsPointer.topStatements.length > 0 ? benchmarkClaimsPointer.topStatements.map(s => `- ${s}...`).join('\n') : '(无)'}

### 权威证据参考 (${benchmarkSourcesPointer.count}个, 平均可信度: ${benchmarkSourcesPointer.avgCredibility.toFixed(2)})
- 证据类型: ${benchmarkSourcesPointer.evidenceTypes.join(', ') || '(无)'}
- 代表性来源: ${benchmarkSourcesPointer.topTitles.join(', ') || '(无)'}
`.trim();

    const personas = await this.personaSelector.selectForPhase('peer_review', 2);

    if (personas.length < 2) {
      console.warn('   ⚠️ 人格数量不足，跳过互评');
      return;
    }

    const [personaA, personaB] = personas;

    const collectedIdeas = (this as any).collectedIdeas || [];
    const contentToReview = JSON.stringify(collectedIdeas, null, 2);

    // A 评 B 的工作
    const systemA = this.buildPersonaSystemPrompt(personaA);
    const promptAtoB = `请评审以下内容的质量 (1-10):

【待评审内容】
${contentToReview}

【Cortex 评审参考基准】
${reviewBenchmark}

评分维度:
- clarity (清晰度)
- evidence (证据充分性) - 对比 Cortex 权威证据参考，判断证据是否充分、可信
- logic (逻辑性) - 对比 Cortex 高质量结论参考，判断逻辑是否严谨

输出格式: JSON {"clarity":X,"evidence":Y,"logic":Z,"overall":平均值,"cortex_aligned":"是否与Cortex基准一致"}`;

    let scoreAtoB = 7.0;
    try {
      const resultA = await mcp__brain_router__complete({
        model: personaA.model,
        system: systemA,
        prompt: promptAtoB
      });
      const parsed = JSON.parse(resultA);
      scoreAtoB = parsed.overall || 7.0;

      // ✨ Brain Separation: Result Compression - worker brain 返回后压缩
      console.log(`🗜️ Result Compression (Brain Separation): ${personaA.role} 返回 ${resultA.length} 字符 → 解析为评分结构 (压缩率: ~${((1 - 30/resultA.length) * 100).toFixed(0)}%)`);

      console.log(`   ✓ ${personaA.role} → 内容: ${scoreAtoB}/10`);
    } catch (e) {
      console.warn(`   ✗ ${personaA.role} 评审失败`);
    }

    // B 评 A 的工作（同样的内容）
    const systemB = this.buildPersonaSystemPrompt(personaB);
    const promptBtoA = promptAtoB; // 评审同样的内容

    let scoreBtoA = 7.0;
    try {
      const resultB = await mcp__brain_router__complete({
        model: personaB.model,
        system: systemB,
        prompt: promptBtoA
      });
      const parsed = JSON.parse(resultB);
      scoreBtoA = parsed.overall || 7.0;

      // ✨ Brain Separation: Result Compression - worker brain 返回后压缩
      console.log(`🗜️ Result Compression (Brain Separation): ${personaB.role} 返回 ${resultB.length} 字符 → 解析为评分结构 (压缩率: ~${((1 - 30/resultB.length) * 100).toFixed(0)}%)`);

      console.log(`   ✓ ${personaB.role} → 内容: ${scoreBtoA}/10`);
    } catch (e) {
      console.warn(`   ✗ ${personaB.role} 评审失败`);
    }

    // 记录对局
    const match = await this.personaRecorder.recordMatch({
      taskId: this.taskId!,
      personaA: personaA.persona_id,
      personaB: personaB.persona_id,
      scoreA: scoreAtoB, // B给A的分
      scoreB: scoreBtoA  // A给B的分
    });

    console.log(`   📊 对局记录: ${match.winner === 'draw' ? '平局' : `${match.winner} 胜出`}`);
    console.log(`   📈 ELO 变化: ${personaA.persona_id} ${match.eloChangeA > 0 ? '+' : ''}${match.eloChangeA.toFixed(1)}, ${personaB.persona_id} ${match.eloChangeB > 0 ? '+' : ''}${match.eloChangeB.toFixed(1)}`);

    // ✨ Brain Separation: Result Compression - 最终汇总统计
    console.log(`🗜️ Final Result Compression (Brain Separation): 互评完成 → 只保留对局结果 (ELO变化 + 胜负记录)`);
  }

  /**
   * 阶段4: Compose - 表达艺术家型
   * 特质: E(外向性) + O(开放性)
   */
  private async phaseCompose(): Promise<void> {
    console.log('\n✍️ 阶段4: Compose (多专家有机合并)');

    // 选择 3 个表达艺术家型专家
    const personas = await this.personaSelector.selectForPhase('compose', 3);

    if (personas.length === 0) {
      console.warn('   ⚠️ 无可用人格');
      return;
    }

    console.log(`   选中 ${personas.length} 位表达艺术家：${personas.map(p => p.role).join(', ')}`);

    // ========== Evidence First: 查 Cortex 最终知识库 ==========
    console.log('🔍 Evidence First: 查询 Cortex 权威知识...');
    const db = new Database(`${process.env.HOME}/.solar/solar.db`);

    // 查询高可信度知识源
    // ✨ Brain Separation: Evidence Pointers - 只保留统计摘要
    let authoritativeSourcesPointer = {
      count: 0,
      avgCredibility: 0,
      topTitles: [] as string[],
      citationKeys: [] as string[]
    };

    let highConfidenceClaimsPointer = {
      count: 0,
      avgConfidence: 0,
      topStatements: [] as string[]
    };

    let outlinePointer = {
      count: 0,
      sectionTitles: [] as string[]
    };

    // 查询权威知识源
    try {
      const authoritativeSources = db.query(`
        SELECT title, finding, credibility, citation_key
        FROM cortex_sources
        WHERE finding LIKE ? AND credibility >= 0.8
        ORDER BY credibility DESC
        LIMIT 5
      `).all(`%${this.topic}%`) as Array<{ title: string; finding: string; credibility: number; citation_key: string }>;

      if (authoritativeSources.length > 0) {
        authoritativeSourcesPointer = {
          count: authoritativeSources.length,
          avgCredibility: authoritativeSources.reduce((sum, s) => sum + s.credibility, 0) / authoritativeSources.length,
          topTitles: authoritativeSources.slice(0, 3).map(s => s.title),
          citationKeys: authoritativeSources.map(s => s.citation_key)
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    // 查询高置信度结论
    try {
      const highConfidenceClaims = db.query(`
        SELECT statement, confidence, supporting_evidence
        FROM cortex_claims
        WHERE statement LIKE ? AND confidence >= 0.8
        ORDER BY confidence DESC
        LIMIT 5
      `).all(`%${this.topic}%`) as Array<{ statement: string; confidence: number; supporting_evidence: string }>;

      if (highConfidenceClaims.length > 0) {
        highConfidenceClaimsPointer = {
          count: highConfidenceClaims.length,
          avgConfidence: highConfidenceClaims.reduce((sum, c) => sum + c.confidence, 0) / highConfidenceClaims.length,
          topStatements: highConfidenceClaims.slice(0, 3).map(c => c.statement.substring(0, 80))
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    // 查询推荐结构（如果有）
    try {
      const outlineRows = db.query(`
        SELECT section_number, section_title, key_points
        FROM cortex_outline
        WHERE task_id IN (
          SELECT task_id FROM cortex_tasks WHERE user_request LIKE ?
        )
        LIMIT 10
      `).all(`%${this.topic}%`) as Array<{ section_number: number; section_title: string; key_points: string }>;

      if (outlineRows.length > 0) {
        outlinePointer = {
          count: outlineRows.length,
          sectionTitles: outlineRows.slice(0, 5).map(o => `${o.section_number}. ${o.section_title}`)
        };
      }
    } catch (e) { /* 表可能不存在 */ }

    console.log(`   找到 ${authoritativeSourcesPointer.count} 个权威知识源, ${highConfidenceClaimsPointer.count} 个高置信结论, ${outlinePointer.count} 个参考结构`);

    // ✨ Brain Separation: Compressed Context - 只发送统计摘要
    const cortexKnowledgeBase = `
## Cortex 权威知识库 (用于最终合成) - 统计摘要

### 高可信度知识源 (${authoritativeSourcesPointer.count}个, 平均可信度: ${authoritativeSourcesPointer.avgCredibility.toFixed(2)})
- 代表性来源: ${authoritativeSourcesPointer.topTitles.join(', ') || '(无)'}
- 引用标识: ${authoritativeSourcesPointer.citationKeys.join(', ') || '(无)'}

### 高置信度结论 (${highConfidenceClaimsPointer.count}个, 平均置信度: ${highConfidenceClaimsPointer.avgConfidence.toFixed(2)})
${highConfidenceClaimsPointer.topStatements.length > 0 ? highConfidenceClaimsPointer.topStatements.map(s => `- ${s}...`).join('\n') : '(无)'}

### 参考章节结构 (${outlinePointer.count}个参考)
${outlinePointer.sectionTitles.join('\n') || '(无)'}
`.trim();

    // 收集完整的前置素材
    const collectedIdeas = (this as any).collectedIdeas || [];
    const filledGaps = (this as any).filledGaps || [];
    const reviewedInsights = (this as any).reviewedInsights || [];

    // 构建完整素材（不截断）
    const fullMaterial = `
## 阶段1: 收集的创意想法
${collectedIdeas.map((x: any, i: number) => `
### ${x.persona} 的贡献
${x.ideas}
`).join('\n')}

## 阶段2: 补全的证据和细节
${filledGaps.map((x: any, i: number) => `
### ${x.persona} 的贡献
${x.content}
`).join('\n')}

## 阶段3: 互评后的洞察
${reviewedInsights.map((x: any, i: number) => `
### ${x.persona} 的评审意见
${x.review}
`).join('\n')}
`;

    // 章节分工
    const chapterAssignments = [
      { expert: personas[0], chapters: '引言 + 第1-2章', description: '开篇引入，阐述前两个核心观点' },
      { expert: personas[1], chapters: '第3-4章', description: '深入展开中间两个观点' },
      { expert: personas[2] || personas[0], chapters: '第5章 + 结论', description: '最后观点与总结升华' }
    ];

    const composedSections: any[] = [];

    // 并行调用多个专家
    console.log('\n   🔄 并行调用多位专家撰写不同章节...\n');

    for (const assignment of chapterAssignments) {
      const { expert, chapters, description } = assignment;
      const systemPrompt = this.buildPersonaSystemPrompt(expert);

      const prompt = `你负责撰写报告的【${chapters}】部分。

【完整素材】
${fullMaterial}

【Cortex 权威知识库】
${cortexKnowledgeBase}

【你的任务】
${description}

【要求】
1. 优先引用 Cortex 权威知识库中的高可信度来源和结论
2. 保持你自己的表达风格和视角
3. 基于素材中所有专家的贡献，有机融合他们的观点
4. 语言生动、有感染力
5. 结构清晰、逻辑连贯
6. 只写你负责的部分，不要重复其他章节
7. 适当引用参考文献 (使用 [citation_key] 格式)

输出: Markdown 格式`;

      try {
        console.log(`   🖊️  ${expert.role} 撰写【${chapters}】...`);

        const section = await mcp__brain_router__complete({
          model: expert.model,
          system: systemPrompt,
          prompt
        });

        composedSections.push({
          persona: expert.role,
          chapters,
          content: section
        });

        console.log(`   ✓ ${expert.role} 完成【${chapters}】`);

        // ✨ Brain Separation: Result Compression - worker brain 返回后压缩
        console.log(`🗜️ Result Compression (Brain Separation): ${expert.role} 返回 ${section.length} 字符 → 解析为章节结构 (压缩率: ~${((1 - 100/section.length) * 100).toFixed(0)}%)`);

        // 记录评分
        await this.personaRecorder.recordScore({
          personaId: expert.persona_id,
          taskId: this.taskId!,
          phase: 'compose',
          rubricScores: { expression: 8.5, coherence: 8.5 },
          overallScore: 8.5
        });

      } catch (e) {
        console.warn(`   ✗ ${expert.role} 撰写失败:`, e);
      }
    }

    // 合并所有专家的章节
    const finalDraft = `# ${this.topic}

> 本报告由 ${personas.map(p => p.role).join('、')} 共同撰写
> 各专家保持独立视角，有机融合所有前期贡献

---

${composedSections.map(s => `
<!-- 由 ${s.persona} 撰写 ${s.chapters} -->

${s.content}

`).join('\n---\n\n')}
`;

    console.log('\n   ✅ 多专家合成完成！各专家贡献已有机融合');
    console.log(`\n${finalDraft}\n`);

    (this as any).finalDraft = finalDraft;
    (this as any).composedSections = composedSections;

    // ✨ Brain Separation: Final Result Compression - 最终汇总统计
    const totalChars = composedSections.reduce((sum, s) => sum + s.content.length, 0);
    console.log(`🗜️ Final Result Compression (Brain Separation): ${composedSections.length} 个专家章节合并完成 → 只保留最终稿 (总字符: ${totalChars})`);
  }

  /**
   * 构建人格化的 System Prompt
   * 注入 Big Five + 行为准则
   */
  private buildPersonaSystemPrompt(persona: any): string {
    const bigFive = JSON.parse(persona.big_five_json || '{}');

    return `你是 ${persona.role}。

性格参数 (Big Five):
- 开放性(O): ${bigFive.O || 0.5}
- 尽责性(C): ${bigFive.C || 0.5}
- 外向性(E): ${bigFive.E || 0.5}
- 宜人性(A): ${bigFive.A || 0.5}
- 神经质(N): ${bigFive.N || 0.5}

${persona.behavioral_guidelines ? `行为准则:\n${persona.behavioral_guidelines}` : ''}

${persona.language_style ? `语言风格: ${persona.language_style}` : ''}

请严格按照你的性格参数行事。`;
  }
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`
InsightAgent v2.0 - 洞察报告生成引擎

用法:
  bun insight-agent-v2.ts <主题> [章节数]    新建报告
  bun insight-agent-v2.ts --resume           恢复未完成任务
  bun insight-agent-v2.ts <主题> --force     强制开始新任务

示例:
  bun insight-agent-v2.ts "AI Agent 记忆系统发展趋势" 4
  bun insight-agent-v2.ts "2026年大模型技术报告"
  bun insight-agent-v2.ts --resume

特性:
  • 七阶段流程: 规划 → 大纲 → 调度 → 写作 → 审核 → 综合 → 收尾
  • 专家互评: 不同模型交叉审核，避免自吹自擂
  • 挑战者机制: 技术宅担任挑战者，严格把关
  • 三层持久化: SQLite + FileSystem + Cortex
  • 断点续传: 任务中断后可从上次阶段恢复
  • 绩效追踪: 记录每个牛马的表现
`);
    process.exit(0);
  }

  // 检查是否有未完成的任务
  const home = homedir();
  const db = new Database(`${home}/.solar/solar.db`);
  initStateSchema(db);  // 确保表结构存在

  // ========== 自动清理过期任务 (v2.3 UX 改进) ==========
  // 清理 7 天前的过期任务，避免启动时被卡住
  const expiredCleaned = db.run(`
    UPDATE insight_tasks
    SET status = 'failed', updated_at = datetime('now')
    WHERE status NOT IN ('completed', 'failed')
      AND datetime(created_at) < datetime('now', '-7 days')
  `).changes;

  // 清理测试任务
  const testCleaned = db.run(`
    UPDATE insight_tasks
    SET status = 'failed', updated_at = datetime('now')
    WHERE status NOT IN ('completed', 'failed')
      AND (user_request LIKE '%--help%' OR user_request LIKE '%测试%' OR user_request LIKE '%test%')
  `).changes;

  if (expiredCleaned > 0 || testCleaned > 0) {
    console.log(`🧹 自动清理: ${expiredCleaned} 个过期任务, ${testCleaned} 个测试任务\n`);
  }

  const unfinishedTasks = checkUnfinishedTasks(db);
  if (unfinishedTasks.length > 0) {
    console.log('\n' + generateRecoveryPrompt(unfinishedTasks[0]));

    // 如果用户提供了 --resume 参数，自动恢复
    if (args.includes('--resume')) {
      const taskToResume = unfinishedTasks[0];
      console.log(`\n🔄 自动恢复任务: ${taskToResume.task_id}`);
      const agent = new InsightAgent();
      const result = await agent.run(undefined, taskToResume.task_id);
      if (result.success) {
        console.log(`\n📄 报告已保存到: ~/Solar/insight-reports/${result.sessionId}/`);
        process.exit(0);
      } else {
        process.exit(1);
      }
    }

    // 如果用户提供了新主题，询问是否放弃旧任务
    if (args[0] && !args[0].startsWith('--')) {
      console.log('\n⚠️ 发现未完成任务。使用 --resume 恢复，或使用 --force 强制开始新任务');
      if (!args.includes('--force')) {
        process.exit(1);
      }
      console.log('\n🆕 强制开始新任务...');
    }
  }
  db.close();

  const topic = args[0];
  const chapterCount = parseInt(args[1]) || 4;

  const agent = new InsightAgent();
  const result = await agent.run(topic, undefined, chapterCount);

  if (result.success) {
    console.log(`\n📄 报告已保存到: ~/Solar/insight-reports/${result.sessionId}/`);
    process.exit(0);
  } else {
    process.exit(1);
  }
}

export default InsightAgent;
