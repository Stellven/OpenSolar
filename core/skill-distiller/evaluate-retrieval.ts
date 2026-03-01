/**
 * 技能检索评估工具 v2
 * 修复版：正确计算标签匹配
 */

import { retrieveSkills } from './db';
import { Database } from 'bun:sqlite';

// 测试用例
const TEST_CASES = [
  { query: "Python 性能优化", expected_tags: ["python", "performance"] },
  { query: "React 组件设计", expected_tags: ["react", "component"] },
  { query: "API 安全", expected_tags: ["api", "security"] },
  { query: "数据库查询", expected_tags: ["database", "sql", "query"] },
  { query: "Git 提交", expected_tags: ["git", "commit"] },
  { query: "性能调试", expected_tags: ["performance", "debug"] },
  { query: "代码审查", expected_tags: ["review", "code", "quality"] },
  { query: "错误排查", expected_tags: ["error", "debug", "troubleshoot"] },
  { query: "接口设计", expected_tags: ["api", "design"] },
  { query: "测试用例", expected_tags: ["test", "testing"] },
];

console.log("📊 技能检索评估 v2\n");
console.log("─".repeat(60));

let totalHits = 0;
let totalPrecision = 0;
let totalRecall = 0;

for (const tc of TEST_CASES) {
  const result = retrieveSkills({ query: tc.query, top_k: 5 });
  
  // 收集检索到的所有标签
  const retrievedTags = new Set<string>();
  for (const skill of result.skills) {
    for (const tag of (skill.tags || [])) {
      retrievedTags.add(tag.toLowerCase());
    }
  }
  
  // 计算匹配
  const matched: string[] = [];
  for (const expected of tc.expected_tags) {
    for (const rt of retrievedTags) {
      if (rt.includes(expected.toLowerCase()) || expected.toLowerCase().includes(rt)) {
        matched.push(expected);
        break;
      }
    }
  }
  
  const precision = retrievedTags.size > 0 ? matched.length / retrievedTags.size : 0;
  const recall = matched.length / tc.expected_tags.length;
  const hit = matched.length > 0;
  
  totalHits += hit ? 1 : 0;
  totalPrecision += precision;
  totalRecall += recall;
  
  const icon = hit ? "✅" : "❌";
  console.log(`${icon} "${tc.query}"`);
  console.log(`   期望标签: [${tc.expected_tags.join(", ")}]`);
  console.log(`   检索标签: [${Array.from(retrievedTags).slice(0, 6).join(", ")}...]`);
  console.log(`   匹配: [${matched.join(", ")}] | 精准率: ${(precision * 100).toFixed(0)}% | 召回率: ${(recall * 100).toFixed(0)}%`);
  console.log(`   检索技能: ${result.skills.slice(0, 3).map(s => s.name).join(", ")}`);
  console.log("");
}

console.log("─".repeat(60));
console.log("📈 汇总\n");
console.log(`  命中率: ${(totalHits / TEST_CASES.length * 100).toFixed(0)}% (${totalHits}/${TEST_CASES.length})`);
console.log(`  平均精准率: ${(totalPrecision / TEST_CASES.length * 100).toFixed(0)}%`);
console.log(`  平均召回率: ${(totalRecall / TEST_CASES.length * 100).toFixed(0)}%`);

// 问题诊断
console.log("\n─".repeat(60));
console.log("🔍 问题诊断\n");

// 检查标签覆盖率
const db = new Database(`${process.env.HOME}/.solar/solar.db`);
const allTags = db.prepare(`
  SELECT DISTINCT json_each.value as tag
  FROM sys_skill_bank, json_each(tags)
  WHERE status = 'active'
`).all() as { tag: string }[];
db.close();

console.log(`技能库标签数: ${allTags.length}`);

// 检查查询关键词匹配
const testQueries = ["python", "react", "kubernetes", "terraform", "cicd"];
console.log("\n关键词匹配测试:");
for (const q of testQueries) {
  const r = retrieveSkills({ query: q, top_k: 3 });
  const hasMatch = r.skills.some(s => 
    s.name.toLowerCase().includes(q) || 
    (s.tags || []).some((t: string) => t.toLowerCase().includes(q))
  );
  console.log(`  ${hasMatch ? "✅" : "❌"} "${q}" → ${r.skills.length} 结果`);
}
