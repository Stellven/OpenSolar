/**
 * Prompt A/B 测试 - 验证"人格可观测"
 *
 * 设计目标：
 * - 同一个模型、同一个任务
 * - 只改 KNOBS + CHECKLIST
 * - 观察输出差异
 *
 * 验证假设：
 * - Builder 更快更短、但可验收性更强
 * - Verifier 更会找反例、更少放过漏洞
 */

import { compilePromptV2, ROLE_PATCHES, formatKnobsLine } from './prompt-runtime';

const BRAIN_ROUTER_URL = 'http://localhost:8765';

interface TestResult {
  role: string;
  model: string;
  task: string;
  output: string;
  outputLength: number;
  hasTests: boolean;
  hasClaims: boolean;
  hasConfidence: boolean;
  hasFailureModes: boolean;
  hasEdgeCases: boolean;
  verdict?: string;
  tokenEstimate: number;
}

/**
 * 调用 brain-router
 */
async function callModel(model: string, system: string, prompt: string): Promise<string> {
  try {
    const response = await fetch(`${BRAIN_ROUTER_URL}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, system, prompt }),
    });

    const data = await response.json();
    return data.content || data.error || 'No response';
  } catch (err: any) {
    return `Error: ${err.message}`;
  }
}

/**
 * 检测输出中的可验收元素
 */
function checkOutput(output: string): {
  hasTests: boolean;
  hasClaims: boolean;
  hasConfidence: boolean;
  hasFailureModes: boolean;
  hasEdgeCases: boolean;
  verdict?: string;
} {
  const lower = output.toLowerCase();

  // 检测测试/复现
  const hasTests =
    lower.includes('test') ||
    lower.includes('repro') ||
    lower.includes('verify') ||
    lower.includes('```') && (lower.includes('describe(') || lower.includes('def test'));

  // 检测可检验 claims
  const hasClaims =
    lower.includes('claim') ||
    lower.includes('finding') ||
    lower.includes('conclusion') ||
    lower.includes('evidence');

  // 检测置信度
  const hasConfidence =
    lower.includes('confidence') ||
    lower.includes('%') ||
    lower.includes('high|med|low') ||
    /\d+\/10/.test(output);

  // 检测失败模式
  const hasFailureModes =
    lower.includes('failure') ||
    lower.includes('edge case') ||
    lower.includes('counterexample') ||
    lower.includes('what would change');

  // 检测边界情况
  const hasEdgeCases =
    lower.includes('edge') ||
    lower.includes('boundary') ||
    lower.includes('corner case');

  // 判断 verdict
  let verdict: string | undefined;
  if (lower.includes('verdict')) {
    if (lower.includes('pass')) verdict = 'pass';
    else if (lower.includes('fail')) verdict = 'fail';
    else if (lower.includes('needs_info')) verdict = 'needs_info';
  }

  return { hasTests, hasClaims, hasConfidence, hasFailureModes, hasEdgeCases, verdict };
}

/**
 * 运行 A/B 测试
 */
async function runABTest(
  task: string,
  model: string,
  roles: string[]
): Promise<TestResult[]> {
  const results: TestResult[] = [];

  for (const role of roles) {
    const compiled = compilePromptV2({ role, taskDescription: task });
    const output = await callModel(model, compiled.system, task);
    const checks = checkOutput(output);

    results.push({
      role,
      model,
      task,
      output: output.substring(0, 500) + (output.length > 500 ? '...' : ''),
      outputLength: output.length,
      ...checks,
      tokenEstimate: compiled.tokenEstimate,
    });

    console.log(`  ✓ ${role}: ${output.length} chars`);
  }

  return results;
}

/**
 * 格式化对比报告
 */
function formatComparison(results: TestResult[]): string {
  const lines: string[] = [];

  lines.push('╔════════════════════════════════════════════════════════════════╗');
  lines.push('║               🧪 PROMPT A/B 对比测试结果                        ║');
  lines.push('╚════════════════════════════════════════════════════════════════╝');
  lines.push('');
  lines.push(`任务: ${results[0]?.task || 'N/A'}`);
  lines.push(`模型: ${results[0]?.model || 'N/A'}`);
  lines.push('');

  // 表格头
  lines.push('┌─────────────┬────────┬───────┬───────┬───────┬───────┬───────┐');
  lines.push('│ Role        │ Length │ Tests │ Claims│ Conf. │ Fail. │ Edge  │');
  lines.push('├─────────────┼────────┼───────┼───────┼───────┼───────┼───────┤');

  for (const r of results) {
    const role = r.role.padEnd(11).substring(0, 11);
    const len = String(r.outputLength).padStart(5);
    const tests = r.hasTests ? '  ✓  ' : '  ✗  ';
    const claims = r.hasClaims ? '  ✓  ' : '  ✗  ';
    const conf = r.hasConfidence ? '  ✓  ' : '  ✗  ';
    const fail = r.hasFailureModes ? '  ✓  ' : '  ✗  ';
    const edge = r.hasEdgeCases ? '  ✓  ' : '  ✗  ';

    lines.push(`│ ${role} │ ${len} │ ${tests} │ ${claims} │ ${conf} │ ${fail} │ ${edge} │`);
  }

  lines.push('└─────────────┴────────┴───────┴───────┴───────┴───────┴───────┘');
  lines.push('');

  // 差异分析
  lines.push('## 差异分析');
  lines.push('');

  if (results.length >= 2) {
    const [a, b] = results;
    const lenDiff = b.outputLength - a.outputLength;
    const lenDiffPct = ((lenDiff / a.outputLength) * 100).toFixed(1);

    lines.push(`### 长度对比`);
    lines.push(`- ${a.role}: ${a.outputLength} chars`);
    lines.push(`- ${b.role}: ${b.outputLength} chars (${lenDiff > 0 ? '+' : ''}${lenDiffPct}%)`);
    lines.push('');

    lines.push(`### 可验收性对比`);
    lines.push(`| 指标 | ${a.role} | ${b.role} |`);
    lines.push(`|------|---------|---------|`);
    lines.push(`| Tests | ${a.hasTests ? '✓' : '✗'} | ${b.hasTests ? '✓' : '✗'} |`);
    lines.push(`| Claims | ${a.hasClaims ? '✓' : '✗'} | ${b.hasClaims ? '✓' : '✗'} |`);
    lines.push(`| Confidence | ${a.hasConfidence ? '✓' : '✗'} | ${b.hasConfidence ? '✓' : '✗'} |`);
    lines.push(`| Failure Modes | ${a.hasFailureModes ? '✓' : '✗'} | ${b.hasFailureModes ? '✓' : '✗'} |`);
    lines.push(`| Edge Cases | ${a.hasEdgeCases ? '✓' : '✗'} | ${b.hasEdgeCases ? '✓' : '✗'} |`);
  }

  return lines.join('\n');
}

/**
 * 预设测试任务
 */
const TEST_TASKS = {
  code: `实现一个 LRU Cache，要求：
1. 支持 get(key) 和 put(key, value)
2. 容量满时淘汰最久未使用
3. 时间复杂度 O(1)`,

  review: `审查以下代码，找出潜在问题：

\`\`\`python
def process_data(items):
    result = []
    for i in range(len(items)):
        result.append(items[i] * 2)
    return result
\`\`\``,

  research: `研究: 为什么 Rust 的借用检查器能保证内存安全？列出关键机制和证据。`,

  architecture: `设计一个分布式任务队列系统，需要考虑：可靠性、可扩展性、消息顺序。`,
};

// CLI
if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'run': {
      const taskType = process.argv[3] || 'code';
      const model = process.argv[4] || 'glm-4-plus';
      const task = TEST_TASKS[taskType as keyof typeof TEST_TASKS] || taskType;

      console.log('\n🧪 运行 A/B 测试...\n');
      console.log(`任务类型: ${taskType}`);
      console.log(`模型: ${model}`);
      console.log('');

      // 选择要对比的角色
      const roles = taskType === 'code'
        ? ['builder', 'verifier']
        : taskType === 'review'
        ? ['verifier', 'judge']
        : ['explorer', 'architect'];

      runABTest(task, model, roles).then(results => {
        console.log('\n' + formatComparison(results));
      });
      break;
    }

    case 'task': {
      // 自定义任务
      const task = process.argv[3];
      const model = process.argv[4] || 'glm-4-plus';
      const roles = (process.argv[5] || 'builder,verifier').split(',');

      if (!task) {
        console.error('❌ 请提供任务描述');
        process.exit(1);
      }

      console.log('\n🧪 运行自定义 A/B 测试...\n');

      runABTest(task, model, roles).then(results => {
        console.log('\n' + formatComparison(results));
      });
      break;
    }

    case 'tasks': {
      console.log('\n📋 预设测试任务:\n');
      for (const [type, task] of Object.entries(TEST_TASKS)) {
        console.log(`  ${type}:`);
        console.log(`    ${task.substring(0, 60)}...`);
        console.log('');
      }
      break;
    }

    default:
      console.log(`
🧪 Prompt A/B 测试工具

用法:
  bun prompt-ab-test.ts run <taskType> [model]
    运行预设任务对比
    taskType: code | review | research | architecture
    model: 默认 glm-4-plus

  bun prompt-ab-test.ts task "<任务>" [model] [roles]
    运行自定义任务
    roles: 逗号分隔，默认 builder,verifier

  bun prompt-ab-test.ts tasks
    列出预设测试任务

示例:
  bun prompt-ab-test.ts run code glm-4-plus
  bun prompt-ab-test.ts run review deepseek-r1
  bun prompt-ab-test.ts task "实现一个缓存" gemini-2.5-flash "builder,creator"
`);
  }
}

export { runABTest, checkOutput, formatComparison, TEST_TASKS };
