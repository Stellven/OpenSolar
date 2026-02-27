#!/usr/bin/env bun
/**
 * SMA Integration - 与 Solar 功能集成
 *
 * 提供统一的 SMA 查询接口，供 @Architect, @Reviewer, /build 等功能调用
 *
 * @version 1.0.0
 * @created 2026-02-27
 */

import { retrieveWithRAG, formatRAGContext } from './rag-retriever';
import { calculateSalience } from './trigger-manager';
import { mergeAndDeduplicate } from './consolidation-enhanced';

// ============ 类型定义 ============

export interface SMAContext {
  triples: Array<{
    subject: string;
    predicate: string;
    object: string;
    confidence: number;
  }>;
  sessions: Array<{
    userInput: string;
    aiOutput: string;
    timestamp: number;
  }>;
  formattedContext: string;
  metadata: {
    queryTime: number;
    anchorsFound: number;
    l2Hits: number;
    l3Hits: number;
  };
}

export interface IntegrationConfig {
  maxTriples: number;
  maxSessions: number;
  minConfidence: number;
  timeout: number;
}

const DEFAULT_CONFIG: IntegrationConfig = {
  maxTriples: 10,
  maxSessions: 5,
  minConfidence: 0.6,
  timeout: 100 // ms
};

// ============ 场景化查询函数 ============

/**
 * @Architect 集成 - 获取历史设计决策
 *
 * 用途：架构设计时注入历史约束、已验证模式、已知问题
 *
 * @param topic - 设计主题 (如 "支付系统", "用户认证")
 * @param config - 配置选项
 * @returns SMA 上下文
 */
export function getArchitectContext(
  topic: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // 构建查询关键词
  const keywords = [
    topic,
    '架构', '设计', '约束', '决策',
    '技术选型', '方案'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

/**
 * @Reviewer 集成 - 获取历史 bug 模式
 *
 * 用途：代码评审时检查历史同类问题
 *
 * @param module - 模块名 (如 "支付", "认证")
 * @param config - 配置选项
 * @returns SMA 上下文
 */
export function getReviewerContext(
  module: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // 构建查询关键词 - 侧重 bug 和问题
  const keywords = [
    module,
    'bug', '问题', '错误', '修复',
    '安全', '漏洞', '风险'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

/**
 * /build 集成 - 获取代码模式
 *
 * 用途：实现功能时复用历史代码模式
 *
 * @param feature - 功能描述 (如 "用户登录", "文件上传")
 * @param config - 配置选项
 * @returns SMA 上下文
 */
export function getBuildContext(
  feature: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // 构建查询关键词 - 侧重实现和代码
  const keywords = [
    feature,
    '实现', '代码', '模式',
    '模板', '示例', '参考'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

// ============ Prompt 注入工具 ============

/**
 * 生成 @Architect 的历史约束 prompt
 */
export function formatArchitectPrompt(context: SMAContext): string {
  if (context.triples.length === 0 && context.sessions.length === 0) {
    return ''; // 无历史数据，不注入
  }

  const parts: string[] = ['[历史记忆 - 从 SMA 检索到的相关上下文]'];

  // L3 知识
  if (context.triples.length > 0) {
    parts.push('\n【已知约束/决策】');
    context.triples.slice(0, 5).forEach(t => {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object} (置信度: ${t.confidence.toFixed(2)})`);
    });
  }

  // L2 会话摘要
  if (context.sessions.length > 0) {
    parts.push('\n【历史讨论要点】');
    context.sessions.slice(0, 3).forEach((s, i) => {
      const preview = s.userInput.slice(0, 60);
      parts.push(`- ${preview}${s.userInput.length > 60 ? '...' : ''}`);
    });
  }

  parts.push('\n请考虑上述历史约束和决策，避免重复已否决的方案。');

  return parts.join('\n');
}

/**
 * 生成 @Reviewer 的历史问题 prompt
 */
export function formatReviewerPrompt(context: SMAContext): string {
  if (context.triples.length === 0 && context.sessions.length === 0) {
    return '';
  }

  const parts: string[] = ['[历史问题库 - 检查是否存在同类问题]'];

  // L3 知识
  if (context.triples.length > 0) {
    parts.push('\n【已知问题模式】');
    context.triples.slice(0, 5).forEach(t => {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object}`);
    });
  }

  parts.push('\n请检查当前代码是否存在上述同类问题。');

  return parts.join('\n');
}

/**
 * 生成 /build 的代码模式 prompt
 */
export function formatBuildPrompt(context: SMAContext): string {
  if (context.triples.length === 0 && context.sessions.length === 0) {
    return '';
  }

  const parts: string[] = ['[历史实现参考]'];

  // L3 知识
  if (context.triples.length > 0) {
    parts.push('\n【已验证模式】');
    context.triples.slice(0, 5).forEach(t => {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object}`);
    });
  }

  parts.push('\n可参考上述已验证的实现模式，但需根据当前需求调整。');

  return parts.join('\n');
}

// ============ 更多 Agent 集成 ============

/**
 * @Tester 集成 - 获取历史测试用例和性能基线
 *
 * 用途：测试时参考历史用例，检查性能回归
 */
export function getTesterContext(
  module: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const keywords = [
    module,
    '测试', 'test', '用例', '性能', '基准', 'baseline'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

/**
 * @PM 集成 - 获取历史任务和需求变更
 *
 * 用途：项目管理时参考历史任务，避免重复规划
 */
export function getPMContext(
  project: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const keywords = [
    project,
    '任务', '需求', '里程碑', '变更', '风险'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

/**
 * @Researcher 集成 - 获取历史研究和调研结果
 *
 * 用途：研究时参考历史调研，避免重复工作
 */
export function getResearcherContext(
  topic: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const keywords = [
    topic,
    '研究', '调研', '分析', '方案', '可行性'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

/**
 * @Guard 集成 - 获取历史规范和合规要求
 *
 * 用途：检查时参考历史规范，确保一致性
 */
export function getGuardContext(
  area: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const keywords = [
    area,
    '规范', '规则', '合规', '约束', '标准'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

/**
 * @Ops 集成 - 获取历史部署配置
 *
 * 用途：部署时参考历史配置，避免踩坑
 */
export function getOpsContext(
  service: string,
  config: Partial<IntegrationConfig> = {}
): SMAContext {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const keywords = [
    service,
    '部署', 'deploy', '配置', '环境', 'Docker'
  ].join(' ');

  const result = retrieveWithRAG(keywords, {
    l2Limit: cfg.maxSessions,
    l3Limit: cfg.maxTriples,
    minConfidence: cfg.minConfidence
  });

  return {
    triples: result.triples,
    sessions: result.turns.map(t => ({
      userInput: (t as any).user_input || '',
      aiOutput: (t as any).ai_output || '',
      timestamp: t.timestamp
    })),
    formattedContext: formatRAGContext(result),
    metadata: result.metadata
  };
}

// ============ Prompt 格式化扩展 ============

/**
 * 生成 @Tester 的历史测试 prompt
 */
export function formatTesterPrompt(context: SMAContext): string {
  if (context.triples.length === 0) return '';

  const parts: string[] = ['[历史测试参考]'];

  if (context.triples.length > 0) {
    parts.push('\n【已验证测试点】');
    context.triples.slice(0, 5).forEach(t => {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object}`);
    });
  }

  parts.push('\n请参考上述历史测试用例，确保覆盖相同场景。');
  return parts.join('\n');
}

/**
 * 生成 @PM 的历史任务 prompt
 */
export function formatPMPrompt(context: SMAContext): string {
  if (context.triples.length === 0) return '';

  const parts: string[] = ['[历史任务参考]'];

  if (context.triples.length > 0) {
    parts.push('\n【已完成任务/需求】');
    context.triples.slice(0, 5).forEach(t => {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object}`);
    });
  }

  parts.push('\n请参考上述历史任务，避免重复规划。');
  return parts.join('\n');
}

/**
 * 生成 @Researcher 的历史研究 prompt
 */
export function formatResearcherPrompt(context: SMAContext): string {
  if (context.triples.length === 0) return '';

  const parts: string[] = ['[历史研究参考]'];

  if (context.triples.length > 0) {
    parts.push('\n【已有研究结论】');
    context.triples.slice(0, 5).forEach(t => {
      parts.push(`- ${t.subject} ${t.predicate} ${t.object}`);
    });
  }

  parts.push('\n请参考上述历史研究，避免重复调研。');
  return parts.join('\n');
}

// ============ 学习反馈接口 ============

/**
 * 从设计决策中提取知识并存入 SMA
 *
 * @param design - 设计决策内容
 * @param sessionId - 会话 ID
 */
export function learnFromDesign(design: string, sessionId: string): void {
  // TODO: 实现从设计文档提取三元组
  // 1. 调用 LLM 提取三元组
  // 2. 计算显著度
  // 3. 合并去重
  // 4. 写入 L3
  console.log(`[SMA] Learning from design: ${design.slice(0, 50)}...`);
}

/**
 * 从 bug 修复中提取知识并存入 SMA
 *
 * @param bug - bug 描述
 * @param fix - 修复方案
 * @param sessionId - 会话 ID
 */
export function learnFromBugFix(bug: string, fix: string, sessionId: string): void {
  // TODO: 实现从 bug 修复提取知识
  console.log(`[SMA] Learning from bug fix: ${bug.slice(0, 50)}...`);
}

/**
 * 从测试结果中提取知识
 */
export function learnFromTest(module: string, results: string, sessionId: string): void {
  console.log(`[SMA] Learning from test: ${module}...`);
}

/**
 * 从部署记录中提取知识
 */
export function learnFromDeploy(service: string, config: string, sessionId: string): void {
  console.log(`[SMA] Learning from deploy: ${service}...`);
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];
  const topic = args[1] || '支付系统';

  const commands: Record<string, () => void> = {
    architect: () => {
      console.log(`\n=== @Architect SMA Context: ${topic} ===\n`);
      const context = getArchitectContext(topic);
      console.log(context.formattedContext);
      console.log('\n--- 注入 Prompt ---');
      console.log(formatArchitectPrompt(context));
    },
    reviewer: () => {
      console.log(`\n=== @Reviewer SMA Context: ${topic} ===\n`);
      const context = getReviewerContext(topic);
      console.log(context.formattedContext);
      console.log('\n--- 注入 Prompt ---');
      console.log(formatReviewerPrompt(context));
    },
    build: () => {
      console.log(`\n=== /build SMA Context: ${topic} ===\n`);
      const context = getBuildContext(topic);
      console.log(context.formattedContext);
      console.log('\n--- 注入 Prompt ---');
      console.log(formatBuildPrompt(context));
    },
    tester: () => {
      console.log(`\n=== @Tester SMA Context: ${topic} ===\n`);
      const context = getTesterContext(topic);
      console.log(context.formattedContext);
      console.log('\n--- 注入 Prompt ---');
      console.log(formatTesterPrompt(context));
    },
    pm: () => {
      console.log(`\n=== @PM SMA Context: ${topic} ===\n`);
      const context = getPMContext(topic);
      console.log(context.formattedContext);
      console.log('\n--- 注入 Prompt ---');
      console.log(formatPMPrompt(context));
    },
    researcher: () => {
      console.log(`\n=== @Researcher SMA Context: ${topic} ===\n`);
      const context = getResearcherContext(topic);
      console.log(context.formattedContext);
      console.log('\n--- 注入 Prompt ---');
      console.log(formatResearcherPrompt(context));
    },
    guard: () => {
      console.log(`\n=== @Guard SMA Context: ${topic} ===\n`);
      const context = getGuardContext(topic);
      console.log(context.formattedContext);
    },
    ops: () => {
      console.log(`\n=== @Ops SMA Context: ${topic} ===\n`);
      const context = getOpsContext(topic);
      console.log(context.formattedContext);
    },
  };

  if (command && commands[command]) {
    commands[command]();
  } else {
    console.log(`
SMA Integration CLI - 支持 8 个 Agent

Usage:
  bun sma-integration.ts <agent> <topic>

Agents:
  architect  - @Architect (历史决策)
  reviewer   - @Reviewer (历史bug)
  build      - /build (代码模式)
  tester     - @Tester (测试用例/性能基线)
  pm         - @PM (历史任务/需求)
  researcher - @Researcher (历史研究)
  guard      - @Guard (规范/合规)
  ops        - @Ops (部署配置)

Examples:
  bun sma-integration.ts architect "支付系统"
  bun sma-integration.ts tester "认证模块"
  bun sma-integration.ts pm "Solar项目"
  bun sma-integration.ts researcher "RAG技术"
    `);
  }
}

export type { SMAContext, IntegrationConfig };
