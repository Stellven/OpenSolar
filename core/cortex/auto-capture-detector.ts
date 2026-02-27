#!/usr/bin/env bun
/**
 * Auto-Capture Detector - 自动产物检测器
 *
 * 在工作流程中自动检测并捕获开发产物
 * 原则：不要问我，都存下来
 */

import { captureArtifact } from './auto-capture';
import { readFileSync } from 'fs';

/**
 * 代码产物检测器
 * 检测新创建或修改的代码文件
 */
export async function detectCodeArtifact(
  filePath: string,
  operation: 'create' | 'edit',
  context?: string
): Promise<string | null> {
  try {
    // 读取文件内容
    const content = readFileSync(filePath, 'utf-8');

    // 只捕获有实质性代码的文件 (> 50 行或 > 500 字符)
    const lines = content.split('\n');
    if (lines.length < 50 && content.length < 500) {
      return null; // 太小的文件不捕获
    }

    // 确定文件类型和标签
    const ext = filePath.split('.').pop()?.toLowerCase();
    const tags = ['code', ext || 'unknown'];

    // 根据内容推断重要性
    const importance = inferCodeImportance(content, filePath);

    // 生成标题
    const fileName = filePath.split('/').pop() || 'unknown';
    const title = `${operation === 'create' ? '新建' : '修改'}代码: ${fileName}`;

    // 捕获
    return await captureArtifact({
      artifact_type: 'code',
      title,
      content,
      file_path: filePath,
      tags,
      context: context || `${operation} ${filePath}`,
      importance
    });
  } catch (error) {
    console.error(`代码产物检测失败: ${error}`);
    return null;
  }
}

/**
 * 设计产物检测器
 * 检测架构图、流程图、设计文档等
 */
export async function detectDesignArtifact(
  content: string,
  title: string,
  context?: string
): Promise<string | null> {
  try {
    // 检测是否包含设计元素
    const hasBoxDrawing = /[┌┐└┘├┤─│╭╮╰╯]/.test(content);
    const hasFlowchars = /[→←↑↓⇒⇐⇑⇓]/.test(content);
    const hasArchKeywords = /(架构|设计|流程|模块|组件|接口|API|Schema|Architecture|Design)/i.test(content);

    if (!hasBoxDrawing && !hasFlowchars && !hasArchKeywords) {
      return null; // 不是设计文档
    }

    // 确定标签
    const tags = ['design'];
    if (hasBoxDrawing || hasFlowchars) tags.push('diagram');
    if (/Schema|CREATE TABLE/i.test(content)) tags.push('database');
    if (/API|接口|endpoint/i.test(content)) tags.push('api');

    // 设计文档通常重要性较高
    const importance = 8;

    // 捕获
    return await captureArtifact({
      artifact_type: 'design',
      title,
      content,
      tags,
      context: context || '设计产物',
      importance
    });
  } catch (error) {
    console.error(`设计产物检测失败: ${error}`);
    return null;
  }
}

/**
 * 分析产物检测器
 * 检测技术分析、性能分析、数据分析等
 */
export async function detectAnalysisArtifact(
  content: string,
  title: string,
  context?: string
): Promise<string | null> {
  try {
    // 检测是否包含分析元素
    const hasStats = /\d+%|\d+ms|\d+MB|P\d+|平均|中位数|百分位|QPS|TPS/i.test(content);
    const hasTable = /\|.*\|.*\|/.test(content); // Markdown 表格
    const hasAnalysisKeywords = /(分析|评估|对比|结论|建议|优化|性能|Analysis|Performance|Benchmark)/i.test(content);

    if (!hasStats && !hasTable && !hasAnalysisKeywords) {
      return null; // 不是分析文档
    }

    // 确定标签
    const tags = ['analysis'];
    if (hasStats) tags.push('statistics');
    if (/性能|Performance|Benchmark|延迟|Latency/i.test(content)) tags.push('performance');
    if (/对比|比较|Comparison|vs/i.test(content)) tags.push('comparison');

    // 分析文档重要性适中
    const importance = 7;

    // 捕获
    return await captureArtifact({
      artifact_type: 'analysis',
      title,
      content,
      tags,
      context: context || '分析产物',
      importance
    });
  } catch (error) {
    console.error(`分析产物检测失败: ${error}`);
    return null;
  }
}

/**
 * 决策产物检测器
 * 检测重要的技术决策、方案选择等
 */
export async function detectDecisionArtifact(
  content: string,
  title: string,
  context?: string,
  relatedTask?: string
): Promise<string | null> {
  try {
    // 检测是否包含决策元素
    const hasDecisionKeywords = /(决定|选择|采用|拒绝|Decision|Choose|Adopt|Reject|方案|Plan|Strategy)/i.test(content);
    const hasRationale = /(原因|理由|因为|Reason|Because|优势|劣势|Pros|Cons)/i.test(content);
    const hasAlternatives = /(另一种|替代|Alternative|vs|对比)/i.test(content);

    if (!hasDecisionKeywords) {
      return null; // 不是决策文档
    }

    // 确定标签
    const tags = ['decision'];
    if (hasRationale) tags.push('rationale');
    if (hasAlternatives) tags.push('alternatives');

    // 决策文档重要性很高
    const importance = 9;

    // 捕获
    return await captureArtifact({
      artifact_type: 'decision',
      title,
      content,
      tags,
      context: context || '决策产物',
      related_task: relatedTask,
      importance
    });
  } catch (error) {
    console.error(`决策产物检测失败: ${error}`);
    return null;
  }
}

/**
 * 通用产物检测器
 * 自动推断产物类型并捕获
 */
export async function detectAndCaptureArtifact(
  content: string,
  title: string,
  context?: string,
  filePath?: string
): Promise<string | null> {
  // 优先级：决策 > 设计 > 分析 > 代码

  // 1. 检测决策
  const decisionId = await detectDecisionArtifact(content, title, context);
  if (decisionId) return decisionId;

  // 2. 检测设计
  const designId = await detectDesignArtifact(content, title, context);
  if (designId) return designId;

  // 3. 检测分析
  const analysisId = await detectAnalysisArtifact(content, title, context);
  if (analysisId) return analysisId;

  // 4. 如果有文件路径，检测代码
  if (filePath) {
    const codeId = await detectCodeArtifact(filePath, 'create', context);
    if (codeId) return codeId;
  }

  // 都不匹配，返回 null
  return null;
}

/**
 * 推断代码重要性
 */
function inferCodeImportance(content: string, filePath: string): number {
  let importance = 5; // 基础分

  // 核心目录加分
  if (filePath.includes('/core/')) importance += 1;
  if (filePath.includes('/cortex/')) importance += 1;

  // 类型
  if (filePath.endsWith('.ts') || filePath.endsWith('.js')) importance += 1;
  if (filePath.endsWith('-schema.sql')) importance += 2;

  // 复杂度
  const lines = content.split('\n').length;
  if (lines > 200) importance += 1;
  if (lines > 500) importance += 1;

  // 关键词
  if (/export class|export interface|export type/.test(content)) importance += 1;
  if (/CREATE TABLE|ALTER TABLE/.test(content)) importance += 1;

  // 限制范围
  return Math.min(10, Math.max(1, importance));
}

/**
 * Batch 产物检测器
 * 批量检测多个文件
 */
export async function detectBatchArtifacts(
  files: Array<{ path: string; operation: 'create' | 'edit' }>,
  context?: string
): Promise<string[]> {
  const ids: string[] = [];

  for (const file of files) {
    const id = await detectCodeArtifact(file.path, file.operation, context);
    if (id) ids.push(id);
  }

  return ids;
}

// CLI 接口
if (import.meta.main) {
  const command = process.argv[2];
  const arg1 = process.argv[3];
  const arg2 = process.argv[4];

  switch (command) {
    case 'code':
      if (!arg1) {
        console.error('用法: bun auto-capture-detector.ts code <文件路径> [create|edit]');
        process.exit(1);
      }
      const operation = (arg2 || 'create') as 'create' | 'edit';
      const codeId = await detectCodeArtifact(arg1, operation);
      console.log(codeId ? `✅ 代码产物已捕获: ${codeId}` : '⚠️ 未捕获（不符合条件）');
      break;

    case 'design':
      console.log('用法: 从代码中调用 detectDesignArtifact()');
      break;

    case 'analysis':
      console.log('用法: 从代码中调用 detectAnalysisArtifact()');
      break;

    default:
      console.log(`
Auto-Capture Detector - 自动产物检测器

用法:
  bun auto-capture-detector.ts code <文件路径> [create|edit]

自动检测类型:
  • 代码 (code)     - 新建/修改的代码文件
  • 设计 (design)   - 架构图、流程图、设计文档
  • 分析 (analysis) - 技术分析、性能分析、对比分析
  • 决策 (decision) - 重要技术决策、方案选择

在代码中使用:
  import { detectCodeArtifact, detectDesignArtifact, ... } from './auto-capture-detector';
      `);
  }
}
