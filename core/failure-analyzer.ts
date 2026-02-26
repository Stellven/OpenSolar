/**
 * Failure Analyzer - 失败模式分析与诊断
 *
 * 从 Plan-and-Act 研究中提取的失败分析能力
 * 用于增强 Solar 战略家/治理官的诊断能力
 */

export enum FailureCategory {
  PERMISSION = 'PERMISSION',
  RESOURCE = 'RESOURCE',
  NETWORK = 'NETWORK',
  LOGIC = 'LOGIC',
  UNKNOWN = 'UNKNOWN'
}

export interface FailurePattern {
  category: FailureCategory;
  count: number;
  examples: string[];
  suggestedFix?: string;
}

export interface ExecutionStep {
  stepId: string;
  action: string;
  result: 'success' | 'failure' | 'partial';
  output: any;
  executedAt: string;
}

/**
 * 分类单个错误
 */
export function classifyError(error: string): FailureCategory {
  const lowerError = error.toLowerCase();

  if (lowerError.includes('permission') ||
      lowerError.includes('access denied') ||
      lowerError.includes('forbidden') ||
      lowerError.includes('unauthorized')) {
    return FailureCategory.PERMISSION;
  }

  if (lowerError.includes('out of memory') ||
      lowerError.includes('disk full') ||
      lowerError.includes('quota exceeded') ||
      lowerError.includes('resource limit')) {
    return FailureCategory.RESOURCE;
  }

  if (lowerError.includes('timeout') ||
      lowerError.includes('connection') ||
      lowerError.includes('network') ||
      lowerError.includes('econnrefused') ||
      lowerError.includes('etimedout')) {
    return FailureCategory.NETWORK;
  }

  if (lowerError.includes('syntax error') ||
      lowerError.includes('type error') ||
      lowerError.includes('reference error') ||
      lowerError.includes('undefined') ||
      lowerError.includes('null')) {
    return FailureCategory.LOGIC;
  }

  return FailureCategory.UNKNOWN;
}

/**
 * 分析执行历史中的失败模式
 */
export function analyzeFailurePatterns(history: ExecutionStep[]): Map<FailureCategory, FailurePattern> {
  const patterns = new Map<FailureCategory, FailurePattern>();

  // 初始化所有类别
  Object.values(FailureCategory).forEach(cat => {
    patterns.set(cat, {
      category: cat,
      count: 0,
      examples: []
    });
  });

  // 分析每个失败的步骤
  history.forEach(step => {
    if (step.result === 'failure' && step.output?.error) {
      const category = classifyError(step.output.error);
      const pattern = patterns.get(category)!;

      pattern.count++;
      if (pattern.examples.length < 3) {
        pattern.examples.push(step.output.error);
      }
    }
  });

  // 为每个类别添加修复建议
  patterns.forEach((pattern, category) => {
    if (pattern.count > 0) {
      pattern.suggestedFix = getSuggestedFix(category, pattern);
    }
  });

  return patterns;
}

/**
 * 获取修复建议
 */
function getSuggestedFix(category: FailureCategory, pattern: FailurePattern): string {
  switch (category) {
    case FailureCategory.PERMISSION:
      return `权限问题 (${pattern.count}次)：检查文件权限、API 密钥、或请求监护人授权`;

    case FailureCategory.RESOURCE:
      return `资源不足 (${pattern.count}次)：清理临时文件、增加配额、或分批处理`;

    case FailureCategory.NETWORK:
      return `网络问题 (${pattern.count}次)：检查网络连接、增加超时时间、或添加重试逻辑`;

    case FailureCategory.LOGIC:
      return `逻辑错误 (${pattern.count}次)：检查代码逻辑、类型定义、或调用牛马审查`;

    case FailureCategory.UNKNOWN:
      return `未知错误 (${pattern.count}次)：需要深度分析，建议调用审判官 (deepseek-r1) 诊断`;

    default:
      return '未分类的错误';
  }
}

/**
 * 生成失败分析报告（用于战略家/治理官）
 */
export function generateFailureReport(history: ExecutionStep[]): string {
  const patterns = analyzeFailurePatterns(history);
  const hasFailures = Array.from(patterns.values()).some(p => p.count > 0);

  if (!hasFailures) {
    return '✅ 无失败记录';
  }

  let report = '⚠️ 失败模式分析：\n\n';

  patterns.forEach((pattern, category) => {
    if (pattern.count > 0) {
      report += `**${category}** (${pattern.count}次)\n`;
      report += `- 建议：${pattern.suggestedFix}\n`;
      if (pattern.examples.length > 0) {
        report += `- 示例：${pattern.examples[0]}\n`;
      }
      report += '\n';
    }
  });

  return report;
}

/**
 * 判断是否需要重新规划
 */
export function shouldReplan(history: ExecutionStep[], consecutiveErrors: number = 0): boolean {
  // 连续失败超过 2 次
  if (consecutiveErrors > 2) {
    return true;
  }

  // 分析失败模式
  const patterns = analyzeFailurePatterns(history);

  // 权限问题超过 1 次（可能需要改变策略）
  const permissionFailures = patterns.get(FailureCategory.PERMISSION)?.count || 0;
  if (permissionFailures > 1) {
    return true;
  }

  // 逻辑错误超过 2 次（说明方案有问题）
  const logicFailures = patterns.get(FailureCategory.LOGIC)?.count || 0;
  if (logicFailures > 2) {
    return true;
  }

  // 总失败率超过 50%
  const totalSteps = history.length;
  const failedSteps = history.filter(s => s.result === 'failure').length;
  if (totalSteps > 3 && failedSteps / totalSteps > 0.5) {
    return true;
  }

  return false;
}
