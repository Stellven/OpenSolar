/**
 * CEO 考评模块
 * Solar CEO 对老专家的绩效评估
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const db = new Database(`${homedir()}/.solar/solar.db`);

interface ExpertPerformance {
  expert_model: string;
  task_count: number;
  output_count: number;
  avg_peer_score: number;
  total_tokens: number;
  avg_latency: number;
  efficiency_score: number;
}

interface EvaluationResult {
  expert_model: string;
  grade: string;
  score: number;
  strengths: string[];
  weaknesses: string[];
  recommendation: string;
}

// 获取专家绩效数据
function getExpertPerformance(periodDays: number = 30): ExpertPerformance[] {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - periodDays);
  const cutoffStr = cutoff.toISOString().split('T')[0];

  const query = `
    SELECT
      eo.expert_model,
      COUNT(DISTINCT eo.task_id) as task_count,
      COUNT(eo.output_id) as output_count,
      COALESCE(AVG(pr.score), 0) as avg_peer_score,
      COALESCE(SUM(eo.token_count), 0) as total_tokens,
      COALESCE(AVG(eo.latency_ms), 0) as avg_latency,
      CASE WHEN SUM(eo.token_count) > 0
           THEN COALESCE(AVG(pr.score), 5) * 1000 / (SUM(eo.token_count) / COUNT(eo.output_id))
           ELSE 0 END as efficiency_score
    FROM xiaoai_expert_outputs eo
    LEFT JOIN xiaoai_peer_reviews pr ON eo.output_id = pr.output_id
    WHERE eo.created_at >= ?
    GROUP BY eo.expert_model
    ORDER BY avg_peer_score DESC
  `;

  return db.query(query).all(cutoffStr) as ExpertPerformance[];
}

// 计算综合评分
function calculateGrade(perf: ExpertPerformance): { grade: string; score: number } {
  // 权重分配
  const weights = {
    peer_score: 0.4,      // 互评分数
    efficiency: 0.25,     // 效率 (质量/token)
    reliability: 0.2,     // 可靠性 (任务完成数)
    speed: 0.15           // 速度 (延迟)
  };

  // 归一化各指标到 0-100
  const peerScoreNorm = (perf.avg_peer_score / 10) * 100;
  const efficiencyNorm = Math.min(perf.efficiency_score * 10, 100);
  const reliabilityNorm = Math.min(perf.task_count * 10, 100);
  const speedNorm = Math.max(0, 100 - (perf.avg_latency / 100)); // 延迟越低越好

  // 加权计算
  const score =
    peerScoreNorm * weights.peer_score +
    efficiencyNorm * weights.efficiency +
    reliabilityNorm * weights.reliability +
    speedNorm * weights.speed;

  // 评级
  let grade: string;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return { grade, score };
}

// 生成评价和建议
function generateEvaluation(perf: ExpertPerformance): EvaluationResult {
  const { grade, score } = calculateGrade(perf);
  const strengths: string[] = [];
  const weaknesses: string[] = [];
  let recommendation = '';

  // 分析优势
  if (perf.avg_peer_score >= 8) {
    strengths.push('互评分数高，输出质量优秀');
  }
  if (perf.efficiency_score > 5) {
    strengths.push('效率高，token利用率好');
  }
  if (perf.avg_latency < 5000) {
    strengths.push('响应速度快');
  }
  if (perf.task_count >= 5) {
    strengths.push('参与度高，经验丰富');
  }

  // 分析劣势
  if (perf.avg_peer_score < 6) {
    weaknesses.push('互评分数偏低，需要提高输出质量');
  }
  if (perf.efficiency_score < 2) {
    weaknesses.push('效率偏低，token消耗过多');
  }
  if (perf.avg_latency > 10000) {
    weaknesses.push('响应较慢');
  }
  if (perf.task_count < 2) {
    weaknesses.push('参与任务少，样本不足');
  }

  // 调度建议
  if (grade === 'A' || grade === 'B') {
    recommendation = '优先调度，可承担复杂分析任务';
  } else if (grade === 'C') {
    recommendation = '正常调度，适合一般分析任务';
  } else if (grade === 'D') {
    recommendation = '减少调度，仅用于简单任务或作为备选';
  } else {
    recommendation = '暂停调度，需要观察改进';
  }

  return {
    expert_model: perf.expert_model,
    grade,
    score,
    strengths,
    weaknesses,
    recommendation
  };
}

// 保存考评结果
function saveEvaluation(eval_result: EvaluationResult, perf: ExpertPerformance, periodDays: number) {
  const periodEnd = new Date();
  const periodStart = new Date();
  periodStart.setDate(periodStart.getDate() - periodDays);

  // 保存到 CEO 考评表
  db.run(`
    INSERT OR REPLACE INTO ceo_expert_evaluations
    (expert_model, period_start, period_end, task_count, avg_peer_score,
     avg_quality_score, completion_rate, efficiency_score, overall_grade, ceo_comments)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `, [
    eval_result.expert_model,
    periodStart.toISOString().split('T')[0],
    periodEnd.toISOString().split('T')[0],
    perf.task_count,
    perf.avg_peer_score,
    eval_result.score,
    1.0, // 完成率暂时设为100%
    perf.efficiency_score,
    eval_result.grade,
    JSON.stringify({
      strengths: eval_result.strengths,
      weaknesses: eval_result.weaknesses,
      recommendation: eval_result.recommendation
    })
  ]);

  // 更新调度策略
  const priority = eval_result.grade === 'A' ? 1.0 :
                   eval_result.grade === 'B' ? 0.8 :
                   eval_result.grade === 'C' ? 0.6 :
                   eval_result.grade === 'D' ? 0.3 : 0.1;

  const recommended = eval_result.grade !== 'F';

  db.run(`
    INSERT OR REPLACE INTO ceo_scheduling_policy
    (expert_model, task_type, priority_score, recommended, reason, updated_at)
    VALUES (?, 'analysis', ?, ?, ?, datetime('now'))
  `, [
    eval_result.expert_model,
    priority,
    recommended ? 1 : 0,
    eval_result.recommendation
  ]);
}

// 主函数：执行考评
function runEvaluation(periodDays: number = 30) {
  console.log(`\n========================================`);
  console.log(`🏆 CEO 考评报告`);
  console.log(`考评周期: 最近 ${periodDays} 天`);
  console.log(`========================================\n`);

  const performances = getExpertPerformance(periodDays);

  if (performances.length === 0) {
    console.log('⚠️ 暂无专家绩效数据\n');
    return;
  }

  const results: EvaluationResult[] = [];

  for (const perf of performances) {
    const eval_result = generateEvaluation(perf);
    results.push(eval_result);
    saveEvaluation(eval_result, perf, periodDays);

    // 输出考评结果
    console.log(`┌─ ${perf.expert_model} ──────────────────────────────────┐`);
    console.log(`│ 评级: ${eval_result.grade} (${eval_result.score.toFixed(1)}分)`);
    console.log(`│`);
    console.log(`│ 绩效数据:`);
    console.log(`│   任务数: ${perf.task_count}`);
    console.log(`│   输出数: ${perf.output_count}`);
    console.log(`│   互评均分: ${perf.avg_peer_score.toFixed(2)}/10`);
    console.log(`│   平均延迟: ${perf.avg_latency.toFixed(0)}ms`);
    console.log(`│   效率分: ${perf.efficiency_score.toFixed(2)}`);
    console.log(`│`);
    if (eval_result.strengths.length > 0) {
      console.log(`│ ✅ 优势:`);
      eval_result.strengths.forEach(s => console.log(`│   • ${s}`));
    }
    if (eval_result.weaknesses.length > 0) {
      console.log(`│ ⚠️ 待改进:`);
      eval_result.weaknesses.forEach(w => console.log(`│   • ${w}`));
    }
    console.log(`│`);
    console.log(`│ 📋 调度建议: ${eval_result.recommendation}`);
    console.log(`└──────────────────────────────────────────────────────┘\n`);
  }

  // 输出排名
  console.log(`========================================`);
  console.log(`📊 专家排名`);
  console.log(`========================================`);
  results
    .sort((a, b) => b.score - a.score)
    .forEach((r, i) => {
      const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '  ';
      console.log(`${medal} ${i + 1}. ${r.expert_model} - ${r.grade} (${r.score.toFixed(1)}分)`);
    });

  console.log(`\n调度策略已更新到 ceo_scheduling_policy 表`);
  console.log(`========================================\n`);

  return results;
}

// 查看当前调度策略
function showSchedulingPolicy() {
  console.log(`\n========================================`);
  console.log(`📋 当前调度策略`);
  console.log(`========================================\n`);

  const policies = db.query(`
    SELECT expert_model, task_type, priority_score, recommended, reason, updated_at
    FROM ceo_scheduling_policy
    ORDER BY priority_score DESC
  `).all() as any[];

  if (policies.length === 0) {
    console.log('暂无调度策略，请先运行考评\n');
    return;
  }

  policies.forEach(p => {
    const status = p.recommended ? '✅ 推荐' : '❌ 不推荐';
    console.log(`${p.expert_model}`);
    console.log(`  优先级: ${(p.priority_score * 100).toFixed(0)}%`);
    console.log(`  状态: ${status}`);
    console.log(`  建议: ${p.reason}`);
    console.log(`  更新: ${p.updated_at}\n`);
  });
}

// CLI 入口
const command = process.argv[2];
const days = parseInt(process.argv[3]) || 30;

switch (command) {
  case 'evaluate':
  case 'eval':
    runEvaluation(days);
    break;
  case 'policy':
  case 'show':
    showSchedulingPolicy();
    break;
  default:
    console.log('用法:');
    console.log('  bun ceo-evaluator.ts evaluate [天数]  - 执行考评 (默认30天)');
    console.log('  bun ceo-evaluator.ts policy           - 查看调度策略');
}
