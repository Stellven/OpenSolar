/**
 * Skill-RAG: Parameter Extractor
 *
 * 从用户消息中提取 {{参数}} 并填入 playbook 模板
 *
 * 策略: 基于参数名称的启发式提取
 * - description/error/problem → 用户原始消息
 * - code/code_diff → 提取代码块
 * - language → 检测编程语言
 * - file_path → 检测文件路径
 * - context → 附加上下文或原始消息
 *
 * Part of Step 2: Skill-RAG Plan A
 * @version 1.0.0
 * @created 2026-02-24
 */

// ============================================================
// 类型定义
// ============================================================

export interface ExtractedParams {
  [key: string]: string;
}

export interface FilledTemplate {
  template: string;           // Original template
  filled: string;             // Template with params filled in
  params: ExtractedParams;    // Extracted param values
  unfilled: string[];         // Params that couldn't be filled
  confidence: number;         // 0-1, proportion of params filled
}

// ============================================================
// 参数名提取
// ============================================================

/**
 * Extract {{param}} names from template string
 */
export function extractParamNames(template: string): string[] {
  const matches = template.match(/\{\{(\w+)\}\}/g);
  if (!matches) return [];
  return [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))];
}

// ============================================================
// 核心提取
// ============================================================

/**
 * Extract parameters from user message and fill template
 *
 * @param template - Playbook template with {{param}} placeholders
 * @param userMessage - Raw user message
 * @param additionalContext - Optional additional context (e.g. code, file content)
 */
export function extractParams(
  template: string,
  userMessage: string,
  additionalContext?: string
): FilledTemplate {
  const paramNames = extractParamNames(template);
  const params: ExtractedParams = {};
  const unfilled: string[] = [];

  for (const name of paramNames) {
    const value = extractSingleParam(name, userMessage, additionalContext);
    if (value) {
      params[name] = value;
    } else {
      unfilled.push(name);
    }
  }

  // Fill template with extracted values
  let filled = template;
  for (const [key, value] of Object.entries(params)) {
    filled = filled.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value);
  }

  const confidence = paramNames.length === 0
    ? 1.0
    : (paramNames.length - unfilled.length) / paramNames.length;

  return { template, filled, params, unfilled, confidence };
}

// ============================================================
// 单参数提取策略
// ============================================================

/**
 * Extract a single parameter value based on its name
 * Uses heuristic mapping from param name to extraction strategy
 */
function extractSingleParam(
  paramName: string,
  userMessage: string,
  additionalContext?: string
): string | null {
  const name = paramName.toLowerCase();

  // Category 1: Full message → description-like params
  const descriptionParams = [
    'problem_description', 'error_message', 'description', 'question',
    'task_description', 'requirement', 'issue', 'commit_message',
    'change_description', 'summary'
  ];
  if (descriptionParams.includes(name)) {
    return userMessage;
  }

  // Category 2: Context params
  const contextParams = ['context', 'background', 'additional_context', 'environment'];
  if (contextParams.includes(name)) {
    return additionalContext || userMessage;
  }

  // Category 3: Code-related → extract code blocks
  const codeParams = ['code', 'code_diff', 'code_snippet', 'source_code', 'code_block'];
  if (codeParams.includes(name)) {
    const codeBlock = extractCodeBlock(userMessage);
    if (codeBlock) return codeBlock;
    if (additionalContext) {
      const ctxCode = extractCodeBlock(additionalContext);
      if (ctxCode) return ctxCode;
    }
    // Fallback: if no code block found, maybe the whole message is code
    return additionalContext || null;
  }

  // Category 4: Language detection
  const langParams = ['language', 'programming_language', 'lang'];
  if (langParams.includes(name)) {
    return detectLanguage(userMessage) || detectLanguage(additionalContext || '');
  }

  // Category 5: File path detection
  const pathParams = ['file_path', 'filepath', 'file', 'path'];
  if (pathParams.includes(name)) {
    return detectFilePath(userMessage);
  }

  // Category 6: Severity / priority
  const severityParams = ['severity', 'priority', 'urgency'];
  if (severityParams.includes(name)) {
    return detectSeverity(userMessage) || 'medium';
  }

  // Category 7: Checklist / focus areas
  const listParams = ['checklist', 'focus_areas', 'review_points'];
  if (listParams.includes(name)) {
    return userMessage;
  }

  // Fallback: use entire user message as value
  return userMessage;
}

// ============================================================
// 辅助提取函数
// ============================================================

/**
 * Extract code block from markdown-style text
 */
function extractCodeBlock(text: string): string | null {
  // Try ```...``` blocks first
  const tripleMatch = text.match(/```[\w]*\n?([\s\S]*?)```/);
  if (tripleMatch) return tripleMatch[1].trim();

  // Try indented code blocks (4+ spaces)
  const lines = text.split('\n');
  const codeLines = lines.filter(l => l.startsWith('    ') || l.startsWith('\t'));
  if (codeLines.length >= 2) {
    return codeLines.map(l => l.replace(/^    |\t/, '')).join('\n');
  }

  return null;
}

/**
 * Detect programming language from text
 */
function detectLanguage(text: string): string | null {
  const langs: Record<string, string[]> = {
    'TypeScript': ['typescript', 'ts', '.ts', 'bun'],
    'JavaScript': ['javascript', 'js', '.js', 'node'],
    'Python': ['python', 'py', '.py', 'pip'],
    'Rust': ['rust', 'rs', '.rs', 'cargo'],
    'Go': ['golang', '.go', 'go '],
    'SQL': ['sql', 'sqlite', 'postgres', 'mysql'],
    'Bash': ['bash', 'shell', 'sh', '.sh'],
    'Swift': ['swift', '.swift', 'xcode'],
    'C++': ['cpp', 'c++', '.cpp', '.hpp'],
    'Java': ['java', '.java', 'maven', 'gradle'],
  };

  const lower = text.toLowerCase();
  for (const [lang, keywords] of Object.entries(langs)) {
    if (keywords.some(kw => lower.includes(kw))) return lang;
  }
  return null;
}

/**
 * Detect file path from text
 */
function detectFilePath(text: string): string | null {
  // Match Unix-style paths
  const pathMatch = text.match(/(?:^|\s)((?:~?\/|\.\/)[^\s,;]+)/);
  return pathMatch ? pathMatch[1] : null;
}

/**
 * Detect severity/priority from text
 */
function detectSeverity(text: string): string | null {
  const lower = text.toLowerCase();
  if (['严重', '紧急', 'critical', 'urgent', 'p0', '崩溃'].some(w => lower.includes(w))) return 'critical';
  if (['重要', 'high', 'p1', '很慢'].some(w => lower.includes(w))) return 'high';
  if (['一般', 'medium', 'normal', 'p2'].some(w => lower.includes(w))) return 'medium';
  if (['低', 'low', 'minor', 'p3'].some(w => lower.includes(w))) return 'low';
  return null;
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log(`
Skill-RAG: Parameter Extractor v1.0

用法:
  bun param-extractor.ts <template> <user_message> [context]

示例:
  bun param-extractor.ts "分析错误: {{error_message}} 上下文: {{context}}" "TypeError: xxx is undefined"
  bun param-extractor.ts "审查代码: {{code_diff}} 关注: {{checklist}}" "帮我看看这段代码有没有bug"
`);
    process.exit(0);
  }

  const [template, userMessage, context] = args;
  const result = extractParams(template, userMessage, context);

  console.log('\n📋 参数提取结果:');
  console.log(`  模板参数: ${extractParamNames(template).map(p => `{{${p}}}`).join(', ')}`);
  console.log(`  提取到: ${Object.keys(result.params).length}`);
  console.log(`  未填充: ${result.unfilled.length > 0 ? result.unfilled.map(p => `{{${p}}}`).join(', ') : '无'}`);
  console.log(`  置信度: ${(result.confidence * 100).toFixed(0)}%`);
  console.log('\n  填充后模板 (前300字):');
  console.log(`  ${result.filled.substring(0, 300)}${result.filled.length > 300 ? '...' : ''}`);
  console.log();
}
