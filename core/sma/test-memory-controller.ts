#!/usr/bin/env bun
/**
 * SMA v1.0 Phase 2 功能验证脚本
 * 测试 memory-controller.ts 的三个核心函数
 */

import { logTurn, retrieveContext, triggerConsolidation } from './memory-controller';

async function runTests() {
  console.log('🧪 SMA v1.0 Phase 2 功能验证\n');

  const testSessionId = `test_session_${Date.now()}`;
  let passCount = 0;
  let failCount = 0;

  // Test 1: logTurn() - L2 写入测试
  try {
    console.log('📝 Test 1: logTurn() - L2 写入');
    const start1 = performance.now();

    await logTurn({
      sessionId: testSessionId,
      turnId: 1,
      userInput: 'SMA 是什么？',
      aiOutput: 'SMA 是 Solar Memory Architecture，三层记忆系统。',
      metadata: { test: true }
    });

    await logTurn({
      sessionId: testSessionId,
      turnId: 2,
      userInput: 'L2 可以做什么？',
      aiOutput: 'L2 可以无损记录所有会话轨迹。',
      metadata: { test: true }
    });

    await logTurn({
      sessionId: testSessionId,
      turnId: 3,
      userInput: 'L3 有什么优势？',
      aiOutput: 'L3 有结构化存储，查询快速。',
      metadata: { test: true }
    });

    const duration1 = performance.now() - start1;
    console.log(`   ✅ 写入 3 条记录成功 (${duration1.toFixed(2)}ms)`);
    console.log(`   ${duration1 < 200 ? '✅' : '⚠️'} 性能: P95 < 200ms 目标 ${duration1 < 200 ? '达标' : '未达标'}\n`);
    passCount++;
  } catch (error) {
    console.error(`   ❌ 失败:`, error);
    failCount++;
  }

  // Test 2: retrieveContext() - L2/L3 检索测试
  try {
    console.log('🔍 Test 2: retrieveContext() - L2/L3 检索');
    const start2 = performance.now();

    const result = await retrieveContext('SMA', {
      sessionId: testSessionId,
      limit: 10
    });

    const duration2 = performance.now() - start2;
    console.log(`   ✅ 检索成功 (${duration2.toFixed(2)}ms)`);
    console.log(`   ${duration2 < 100 ? '✅' : '⚠️'} 性能: P95 < 100ms 目标 ${duration2 < 100 ? '达标' : '未达标'}`);
    console.log(`   📊 结果: ${result.turns.length} turns, ${result.triples.length} triples`);

    if (result.turns.length > 0) {
      console.log(`   📝 示例: "${result.turns[0].userInput.substring(0, 30)}..."`);
    }
    console.log('');
    passCount++;
  } catch (error) {
    console.error(`   ❌ 失败:`, error);
    failCount++;
  }

  // Test 3: triggerConsolidation() - L2→L3 知识固化测试
  try {
    console.log('⚡ Test 3: triggerConsolidation() - L2→L3 知识固化');

    // 先写入足够的轮次
    for (let i = 4; i <= 7; i++) {
      await logTurn({
        sessionId: testSessionId,
        turnId: i,
        userInput: `测试输入 ${i}`,
        aiOutput: `测试输出 ${i}。这里有一些知识模式。`,
        metadata: { test: true }
      });
    }

    const start3 = performance.now();
    const extractedCount = await triggerConsolidation(testSessionId, {
      minTurns: 5
    });
    const duration3 = performance.now() - start3;

    console.log(`   ✅ 知识固化成功 (${duration3.toFixed(2)}ms)`);
    console.log(`   📊 提取了 ${extractedCount} 个三元组`);

    // 验证提取的三元组
    const checkResult = await retrieveContext('SMA', { limit: 20 });
    console.log(`   📝 数据库中共有 ${checkResult.triples.length} 个三元组`);

    if (checkResult.triples.length > 0) {
      console.log(`   🔗 示例: (${checkResult.triples[0].subject}, ${checkResult.triples[0].predicate}, ${checkResult.triples[0].object})`);
    }
    console.log('');
    passCount++;
  } catch (error) {
    console.error(`   ❌ 失败:`, error);
    failCount++;
  }

  // 清理测试数据
  try {
    console.log('🧹 清理测试数据...');
    const { Database } = await import('bun:sqlite');
    const db = new Database(`${process.env.HOME}/.solar/solar.db`);

    db.run('DELETE FROM session_log WHERE session_id = ?', [testSessionId]);
    db.run('DELETE FROM knowledge_triples WHERE subject LIKE ?', ['%测试%']);

    console.log('   ✅ 清理完成\n');
  } catch (error) {
    console.error('   ⚠️ 清理失败:', error);
  }

  // 测试总结
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📊 测试结果汇总');
  console.log(`   通过: ${passCount}/3`);
  console.log(`   失败: ${failCount}/3`);
  console.log(`   状态: ${failCount === 0 ? '✅ 全部通过' : '❌ 存在失败'}`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  if (failCount === 0) {
    console.log('🎉 SMA v1.0 Phase 2 核心功能验证通过！');
    process.exit(0);
  } else {
    console.error('❌ 部分测试失败，请检查错误信息');
    process.exit(1);
  }
}

// 运行测试
runTests().catch(error => {
  console.error('❌ 测试运行失败:', error);
  process.exit(1);
});
