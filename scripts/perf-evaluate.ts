#!/usr/bin/env bun
/**
 * 牛马互评脚本 - 让一个牛马评价另一个牛马的输出
 * 运行: bun ~/.claude/scripts/perf-evaluate.ts <model_id> <task_type> <output_summary>
 */
import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const home = homedir();
const db = new Database(`${home}/.solar/solar.db`);

// 牛马列表（用于选择评分者）
const evaluators = [
  'glm-4-flash',      // 便宜快速，适合评分
  'gemini-2.5-flash', // 免费，适合评分
];

// 选择评分者（排除被评者）
function selectEvaluator(excludeModel: string): string {
  const available = evaluators.filter(e => e !== excludeModel);
  return available[Math.floor(Math.random() * available.length)] || 'glm-4-flash';
}

// 记录待评任务
export async function recordForEval(
  modelId: string,
  taskType: string,
  taskSummary: string,
  inputTokens: number,
  outputTokens: number,
  latencyMs: number
): Promise<number> {
  const stmt = db.prepare(`
    INSERT INTO collab_performance
    (model_id, task_type, task_summary, input_tokens, output_tokens, latency_ms)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  const result = stmt.run(modelId, taskType, taskSummary, inputTokens, outputTokens, latencyMs);
  return Number(result.lastInsertRowid);
}

// 提交评分
export function submitEvaluation(
  perfId: number,
  evaluatorId: string,
  score: number,
  reason: string
): void {
  const stmt = db.prepare(`
    UPDATE collab_performance
    SET quality_score = ?, evaluated_by = ?, evaluation_reason = ?
    WHERE perf_id = ?
  `);
  stmt.run(score, evaluatorId, reason, perfId);
}

// 生成评分 prompt
export function genEvalPrompt(taskSummary: string, output: string): string {
  return `请评价以下AI输出的质量（0-10分）：

任务：${taskSummary}
输出：${output.slice(0, 500)}...

评分标准：
- 10分：完美，无可挑剔
- 8-9分：优秀，minor issues
- 6-7分：合格，能用
- 4-5分：勉强，有明显问题
- 0-3分：差，需要重做

请用JSON格式回复：{"score": X, "reason": "简短理由"}`;
}

// CLI 入口
if (import.meta.main) {
  const [modelId, taskType, summary] = process.argv.slice(2);
  if (!modelId) {
    console.log('用法: bun perf-evaluate.ts <model_id> <task_type> <summary>');
    process.exit(1);
  }

  const perfId = await recordForEval(modelId, taskType || 'general', summary || '', 0, 0, 0);
  console.log(`📝 已记录任务 #${perfId}，待评分`);
  console.log(`🎯 建议评分者: ${selectEvaluator(modelId)}`);
}

export { selectEvaluator };
