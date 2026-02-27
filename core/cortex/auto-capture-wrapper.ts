#!/usr/bin/env bun
/**
 * Auto-Capture Wrapper - 自动捕获包装器
 *
 * 拦截工具调用，自动保存结果到 staging 表
 * 原则：不要问我，都存下来
 */

import { captureSearch, captureExpertOutput, captureArtifact } from './auto-capture';

// ============================================================
// Search Tool Wrappers (Grep/Glob/WebSearch/WebFetch/Read)
// ============================================================

/**
 * Grep 包装器
 */
export async function grepWithCapture(
  pattern: string,
  options: any = {},
  context?: string
): Promise<any> {
  // 这里应该调用实际的 Grep 工具
  // 由于是在 TypeScript 中，实际调用需要通过 MCP 或其他方式
  // 此处提供接口定义

  const results = await executeGrepTool(pattern, options);

  // 自动捕获
  await captureSearch({
    search_type: 'grep',
    query: pattern,
    context: context || `Grep search: ${pattern}`,
    results: results,
    result_count: Array.isArray(results) ? results.length : null,
    tool_params: options
  });

  return results;
}

/**
 * Glob 包装器
 */
export async function globWithCapture(
  pattern: string,
  path?: string,
  context?: string
): Promise<any> {
  const results = await executeGlobTool(pattern, path);

  await captureSearch({
    search_type: 'glob',
    query: pattern,
    context: context || `Glob search: ${pattern}`,
    results: results,
    result_count: Array.isArray(results) ? results.length : null,
    tool_params: { pattern, path }
  });

  return results;
}

/**
 * WebSearch 包装器
 */
export async function webSearchWithCapture(
  query: string,
  options: any = {},
  context?: string
): Promise<any> {
  const results = await executeWebSearchTool(query, options);

  await captureSearch({
    search_type: 'websearch',
    query: query,
    context: context || `Web search: ${query}`,
    results: results,
    result_count: results?.length || null,
    tool_params: options
  });

  return results;
}

/**
 * WebFetch 包装器
 */
export async function webFetchWithCapture(
  url: string,
  prompt: string,
  context?: string
): Promise<any> {
  const results = await executeWebFetchTool(url, prompt);

  await captureSearch({
    search_type: 'webfetch',
    query: `${url} | ${prompt}`,
    context: context || `WebFetch: ${url}`,
    results: results,
    tool_params: { url, prompt }
  });

  return results;
}

/**
 * Read 包装器
 */
export async function readWithCapture(
  file_path: string,
  options: any = {},
  context?: string
): Promise<any> {
  const results = await executeReadTool(file_path, options);

  await captureSearch({
    search_type: 'read',
    query: file_path,
    context: context || `Read file: ${file_path}`,
    results: results,
    tool_params: options
  });

  return results;
}

// ============================================================
// Brain Router (Expert) Wrapper
// ============================================================

/**
 * Brain Router 包装器
 */
export async function brainRouterWithCapture(
  model: string,
  prompt: string,
  options: {
    system?: string;
    expertRole?: string;
    taskType?: string;
    context?: string;
  } = {}
): Promise<string> {
  const startTime = Date.now();

  // 调用实际的 brain-router
  const result = await executeBrainRouter(model, prompt, options.system);

  const latency = Date.now() - startTime;

  // 自动捕获
  await captureExpertOutput({
    model: model,
    expert_role: options.expertRole,
    system_prompt: options.system,
    user_prompt: prompt,
    output: result,
    task_type: options.taskType,
    context: options.context,
    latency_ms: latency
    // tokens_input/output 需要从 API 响应中获取
  });

  return result;
}

// ============================================================
// Artifact Capture Helpers
// ============================================================

/**
 * 手动捕获开发产物
 * 用于代码生成、设计文档等场景
 */
export async function captureCodeArtifact(
  title: string,
  content: string,
  file_path?: string,
  tags?: string[],
  importance?: number
): Promise<string> {
  return await captureArtifact({
    artifact_type: 'code',
    title,
    content,
    file_path,
    tags,
    importance
  });
}

export async function captureDesignArtifact(
  title: string,
  content: string,
  tags?: string[],
  importance?: number
): Promise<string> {
  return await captureArtifact({
    artifact_type: 'design',
    title,
    content,
    tags,
    importance
  });
}

export async function captureAnalysisArtifact(
  title: string,
  content: string,
  context?: string,
  importance?: number
): Promise<string> {
  return await captureArtifact({
    artifact_type: 'analysis',
    title,
    content,
    context,
    importance
  });
}

export async function captureDecisionArtifact(
  title: string,
  content: string,
  related_task?: string,
  importance?: number
): Promise<string> {
  return await captureArtifact({
    artifact_type: 'decision',
    title,
    content,
    related_task,
    importance: importance || 8  // 决策默认高重要性
  });
}

// ============================================================
// Tool Execution Stubs (需要实际实现)
// ============================================================

/**
 * 以下是工具执行的存根函数
 * 实际使用时需要替换为真实的工具调用逻辑
 */

async function executeGrepTool(pattern: string, options: any): Promise<any> {
  // TODO: 实际调用 Grep 工具
  // 在 Claude Code 环境中，需要通过适当的接口调用
  throw new Error('executeGrepTool: Not implemented - needs actual tool integration');
}

async function executeGlobTool(pattern: string, path?: string): Promise<any> {
  // TODO: 实际调用 Glob 工具
  throw new Error('executeGlobTool: Not implemented - needs actual tool integration');
}

async function executeWebSearchTool(query: string, options: any): Promise<any> {
  // TODO: 实际调用 WebSearch 工具
  throw new Error('executeWebSearchTool: Not implemented - needs actual tool integration');
}

async function executeWebFetchTool(url: string, prompt: string): Promise<any> {
  // TODO: 实际调用 WebFetch 工具
  throw new Error('executeWebFetchTool: Not implemented - needs actual tool integration');
}

async function executeReadTool(file_path: string, options: any): Promise<any> {
  // TODO: 实际调用 Read 工具
  throw new Error('executeReadTool: Not implemented - needs actual tool integration');
}

async function executeBrainRouter(model: string, prompt: string, system?: string): Promise<string> {
  // TODO: 实际调用 mcp__brain-router__complete
  throw new Error('executeBrainRouter: Not implemented - needs actual tool integration');
}

// ============================================================
// Auto-Capture Hook (全局拦截器概念)
// ============================================================

/**
 * 自动捕获钩子配置
 *
 * 注意：由于 TypeScript/Bun 环境的限制，真正的全局拦截需要：
 * 1. 修改 Claude Code 工具调用流程（需要在更底层集成）
 * 2. 或者在每次工具调用时显式使用 wrapper 函数
 *
 * 此模块提供的是 wrapper 方式，需要主动调用
 */
export const AutoCaptureConfig = {
  enabled: true,
  captureSearch: true,
  captureExpert: true,
  captureArtifact: true,
  verbose: false  // 是否输出捕获日志
};

/**
 * 切换自动捕获开关
 */
export function toggleAutoCapture(enabled: boolean) {
  AutoCaptureConfig.enabled = enabled;
  if (AutoCaptureConfig.verbose) {
    console.log(`Auto-capture ${enabled ? 'enabled' : 'disabled'}`);
  }
}
