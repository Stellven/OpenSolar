#!/usr/bin/env bun
/**
 * Persona Bank 竞技场机制测试脚本
 * 测试固定 4 步 DAG 流程
 */

import { Database } from 'bun:sqlite';

// 简化版 InsightAgent 只测试 Persona Bank 部分
import { PersonaSelector, PhaseType } from './persona-bank-selector';
import { PersonaRecorder } from './persona-bank-recorder';

async function testPersonaBank() {
  console.log('🎭 开始测试 Persona Bank 竞技场机制\n');

  const selector = new PersonaSelector();
  const recorder = new PersonaRecorder();
  const testTopic = 'AI Agent 的记忆机制';
  const taskId = `test-${Date.now()}`;

  try {
    // Step 1: 测试 collect 阶段选人
    console.log('📍 Phase 1: Collect (收集想法)');
    const collectPersonas = await selector.selectForPhase('collect', 4);
    console.log(`选中 ${collectPersonas.length} 个人格 (O+E 特质):\n`);
    collectPersonas.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.role} (${p.persona_id}) - ELO: ${p.elo_rating}`);
    });

    // 模拟记录评分
    for (const persona of collectPersonas.slice(0, 2)) {
      await recorder.recordScore({
        personaId: persona.persona_id,
        taskId,
        phase: 'collect',
        rubricScores: {
          creativity: Math.random() * 3 + 7,
          depth: Math.random() * 3 + 6,
          relevance: Math.random() * 3 + 7
        },
        overallScore: Math.random() * 2 + 7.5
      });
    }
    console.log('✅ 已记录 collect 阶段评分\n');

    // Step 2: 测试 fill_gaps 阶段选人
    console.log('📍 Phase 2: Fill Gaps (补全证据)');
    const fillGapsPersonas = await selector.selectForPhase('fill_gaps', 2);
    console.log(`选中 ${fillGapsPersonas.length} 个人格 (C+A 特质):\n`);
    fillGapsPersonas.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.role} (${p.persona_id}) - ELO: ${p.elo_rating}`);
    });
    console.log();

    // Step 3: 测试 peer_review 阶段选人和互评
    console.log('📍 Phase 3: Peer Review (互评)');
    const reviewPersonas = await selector.selectForPhase('peer_review', 2);
    console.log(`选中 ${reviewPersonas.length} 个人格 (A+C 特质):\n`);
    reviewPersonas.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.role} (${p.persona_id}) - ELO: ${p.elo_rating}`);
    });

    // 模拟互评 (A 评 B, B 评 A)
    if (reviewPersonas.length >= 2) {
      const scoreA = Math.random() * 2 + 7; // 7-9
      const scoreB = Math.random() * 2 + 7;

      const matchResult = await recorder.recordMatch({
        taskId,
        personaA: reviewPersonas[0].persona_id,
        personaB: reviewPersonas[1].persona_id,
        scoreA,
        scoreB
      });

      console.log(`\n  互评结果:`);
      console.log(`  ${reviewPersonas[0].role} 得分: ${scoreA.toFixed(2)} → ELO 变化: ${matchResult.eloChangeA > 0 ? '+' : ''}${matchResult.eloChangeA.toFixed(1)}`);
      console.log(`  ${reviewPersonas[1].role} 得分: ${scoreB.toFixed(2)} → ELO 变化: ${matchResult.eloChangeB > 0 ? '+' : ''}${matchResult.eloChangeB.toFixed(1)}`);
      console.log(`  胜者: ${matchResult.winner}\n`);
    }

    // Step 4: 测试 compose 阶段选人 (多专家有机合并)
    console.log('📍 Phase 4: Compose (多专家有机合并)');
    const composePersonas = await selector.selectForPhase('compose', 3);
    console.log(`选中 ${composePersonas.length} 个人格 (E+O 特质):\n`);
    composePersonas.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.role} (${p.persona_id}) - ELO: ${p.elo_rating}`);
    });
    console.log('\n  章节分工:');
    console.log(`  ${composePersonas[0]?.role}: 引言 + 第1-2章`);
    console.log(`  ${composePersonas[1]?.role}: 第3-4章`);
    console.log(`  ${composePersonas[2]?.role || composePersonas[0]?.role}: 第5章 + 结论`);
    console.log();

    // 查看最终排行榜
    console.log('📊 当前排行榜 (Top 5):');
    const leaderboard = recorder.getLeaderboard(5);
    console.log('┌────┬─────────────────────────┬─────────┬──────────┬────────┐');
    console.log('│ #  │ 人格                    │ ELO     │ 胜率     │ 对局数 │');
    console.log('├────┼─────────────────────────┼─────────┼──────────┼────────┤');
    leaderboard.forEach((p, i) => {
      const role = p.role.padEnd(20, ' ');
      const elo = p.elo_rating.toFixed(0).padStart(7, ' ');
      const winRate = (p.win_rate * 100).toFixed(1).padStart(5, ' ') + '%';
      const matches = p.total_matches.toString().padStart(6, ' ');
      console.log(`│ ${i + 1}  │ ${role} │ ${elo} │ ${winRate} │ ${matches} │`);
    });
    console.log('└────┴─────────────────────────┴─────────┴──────────┴────────┘');

    console.log('\n✅ Persona Bank 竞技场机制测试完成！\n');

  } catch (error) {
    console.error('\n❌ 测试失败:', error);
    process.exit(1);
  }
}

// 运行测试
testPersonaBank();
