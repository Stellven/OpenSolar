/**
 * Solar Farm - 端到端验证测试
 */

import { detectPersonaConcentration, getPersonaLevel } from './persona-detector';
import { executePersonaRefactoring, quickFix } from './persona-refractor';

// 测试场景：模拟冷冰冰的数据分析输出
const coldOutputs = [
  '完成！数据已更新。',
  '统计结果如下：\n| 日期 | 用户数 |\n|------|--------|\n| 2/1 | 1000 |',
  '综上所述，用户增长率为 10%。',
  '已处理。请查收。'
];

const warmOutputs = [
  '搞定啦！来看看这个数据～',
  '这个数据有点意思哦，说明用户活跃度在周末会下降呢！',
  '哈哈，撸起袖子干完了，结果还不错～'
];

console.log('\n========== 三层人格防挤出机制 端到端验证 ==========\n');

console.log('【Layer 2: 人格浓度检测】\n');
console.log('冷冰冰输出:');
coldOutputs.forEach((text, i) => {
  const result = detectPersonaConcentration(text);
  const shortText = text.replace(/\n/g, ' ').slice(0, 25);
  console.log(`  ${i+1}. "${shortText}..." → ${getPersonaLevel(text)} (${result.personaScore}分) → ${result.recommendation}`);
});

console.log('\n有温度输出:');
warmOutputs.forEach((text, i) => {
  const result = detectPersonaConcentration(text);
  const shortText = text.slice(0, 25);
  console.log(`  ${i+1}. "${shortText}..." → ${getPersonaLevel(text)} (${result.personaScore}分) → ${result.recommendation}`);
});

console.log('\n【Layer 3: 人格修正】\n');
console.log('微注入修正示例:');
const microResult = quickFix('完成！');
console.log(`  "完成！" → "${microResult}"`);

const microResult2 = quickFix('已更新。');
console.log(`  "已更新。" → "${microResult2}"`);

console.log('\n完整重写触发:');
const refactorResult = executePersonaRefactoring('综上所述，用户增长率为 10%。');
console.log(`  方法: ${refactorResult.method}`);
console.log(`  分数: ${refactorResult.beforeScore} → ${refactorResult.afterScore}`);
console.log(`  成功: ${refactorResult.success ? '✓' : '✗'}`);

console.log('\n========== 验证完成 ==========\n');
