/**
 * Solar 技能动态检索系统
 * 
 * 功能：
 * 1. 扫描所有技能，提取元数据
 * 2. 按关键词/意图匹配检索相关技能
 * 3. 返回 Top-K 技能路径
 */

import { join } from "path";
import { homedir } from "os";
import { readdirSync, readFileSync, existsSync } from "fs";

const SKILLS_DIR = join(homedir(), ".agents", "skills");

// 技能元数据
interface SkillMeta {
  name: string;
  description: string;
  path: string;
  keywords: string[];
  category: "meta" | "domain" | "utility";
}

// 元技能列表（高杠杆，始终优先）
const META_SKILLS = [
  "systems-thinking",
  "problem-definition", 
  "evaluating-trade-offs",
  "strategic-compact",
  "scientific-critical-thinking",
  "sequential-thinking",
  "root-cause-analysis",
  "firstprinciples",
  "decision-helper",
];

// 意图 → 技能映射
const INTENT_SKILL_MAP: Record<string, string[]> = {
  // 元技能触发
  "复杂问题": ["systems-thinking", "problem-definition"],
  "权衡": ["evaluating-trade-offs", "decision-helper"],
  "决策": ["evaluating-trade-offs", "decision-helper", "firstprinciples"],
  "根因": ["root-cause-analysis", "sequential-thinking"],
  "调试": ["root-cause-analysis", "debugging-strategies"],
  "架构": ["architect-reviewer", "architecture-patterns", "evaluating-trade-offs"],
  "设计": ["architecture-patterns", "domain-driven-design"],
  "分析": ["root-cause-analysis", "systems-thinking", "evaluating-trade-offs"],
  
  // 领域技能触发
  "python": ["python-patterns", "python-architect", "python-performance-optimization"],
  "react": ["react-patterns", "react-architect"],
  "kubernetes": ["kubernetes-specialist", "kubernetes-architect"],
  "terraform": ["terraform-engineer", "terraform-module-library"],
  "测试": ["e2e-testing-patterns", "unit-testing-patterns", "playwright-testing"],
  "安全": ["security-audit-patterns", "auth-implementation-patterns"],
  "数据库": ["postgres-patterns", "database-migration-patterns"],
  "api": ["api-design-principles", "rest-api-designer"],
  "性能": ["python-performance-optimization", "performance-optimization-patterns"],
  "重构": ["refactoring-patterns", "legacy-modernizer"],
  "文档": ["technical-writing", "api-documenter"],
  "git": ["git-advanced-workflows", "github-actions-patterns"],
  "ci": ["cicd-pipeline-patterns", "github-actions-patterns"],
  "部署": ["cicd-pipeline-patterns", "vercel-deploy"],
};

// 扫描所有技能
function scanSkills(): SkillMeta[] {
  const skills: SkillMeta[] = [];
  
  try {
    const entries = readdirSync(SKILLS_DIR, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name === "SKILL-INDEX.md") continue;
      
      const skillPath = join(SKILLS_DIR, entry.name, "SKILL.md");
      if (!existsSync(skillPath)) continue;
      
      try {
        const content = readFileSync(skillPath, "utf-8");
        const meta = parseSkillMeta(content, entry.name);
        if (meta) skills.push(meta);
      } catch {
        // 跳过无法读取的技能
      }
    }
  } catch (e) {
    console.error("扫描技能失败:", e);
  }
  
  return skills;
}

// 解析 SKILL.md 元数据
function parseSkillMeta(content: string, dirName: string): SkillMeta | null {
  const nameMatch = content.match(/^name:\s*(.+)$/m);
  const descMatch = content.match(/^description:\s*["']?(.+?)["']?$/m);
  
  const name = nameMatch?.[1] || dirName;
  const description = descMatch?.[1] || "";
  const keywords = extractKeywords(name + " " + description);
  const category = META_SKILLS.includes(dirName) ? "meta" : 
    (dirName.includes("-patterns") || dirName.includes("-architect")) ? "domain" : "utility";
  
  return { name, description, path: join(SKILLS_DIR, dirName), keywords, category };
}

// 提取关键词
function extractKeywords(text: string): string[] {
  const stopWords = new Set(["the", "a", "an", "is", "are", "to", "for", "and", "or", "with", "in", "on"]);
  return text.toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff\s-]/g, " ")
    .split(/\s+/)
    .filter(w => w.length > 2 && !stopWords.has(w))
    .slice(0, 20);
}

// 检索相关技能
function retrieveSkills(query: string, topK: number = 5): SkillMeta[] {
  const queryLower = query.toLowerCase();
  const scores = new Map<string, number>();
  
  // 1. 意图匹配
  for (const [intent, skills] of Object.entries(INTENT_SKILL_MAP)) {
    if (queryLower.includes(intent.toLowerCase())) {
      for (const skill of skills) {
        const baseScore = META_SKILLS.includes(skill) ? 10 : 5;
        scores.set(skill, (scores.get(skill) || 0) + baseScore);
      }
    }
  }
  
  // 2. 关键词匹配
  const queryKeywords = extractKeywords(query);
  for (const keyword of queryKeywords) {
    for (const skill of Object.keys(INTENT_SKILL_MAP).flatMap(k => INTENT_SKILL_MAP[k])) {
      if (skill.toLowerCase().includes(keyword)) {
        scores.set(skill, (scores.get(skill) || 0) + 2);
      }
    }
  }
  
  // 3. 排序返回 Top-K
  const allSkills = scanSkills();
  const skillMap = new Map(allSkills.map(s => [s.name, s]));
  
  const sorted = [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, topK)
    .map(([name]) => skillMap.get(name) || {
      name,
      description: "",
      path: join(SKILLS_DIR, name),
      keywords: [],
      category: (META_SKILLS.includes(name) ? "meta" : "domain") as const,
    });
  
  return sorted;
}

// 读取技能内容
function loadSkillContent(skillName: string): string {
  const skillPath = join(SKILLS_DIR, skillName, "SKILL.md");
  try {
    return readFileSync(skillPath, "utf-8");
  } catch {
    return "";
  }
}

// 生成上下文注入
function buildSkillContext(query: string, maxSkills: number = 3, maxTokens: number = 4000): string {
  const skills = retrieveSkills(query, maxSkills);
  let context = "# 相关技能上下文\n\n";
  let tokenCount = 0;
  
  for (const skill of skills) {
    const content = loadSkillContent(skill.name);
    const skillContext = `\n## ${skill.name}\n\n${content.slice(0, 2000)}\n`;
    const estimatedTokens = skillContext.length / 4;
    if (tokenCount + estimatedTokens > maxTokens) break;
    context += skillContext;
    tokenCount += estimatedTokens;
  }
  
  return context;
}

// CLI 入口
const args = process.argv.slice(2);

if (args[0] === "scan") {
  const skills = scanSkills();
  console.log(`扫描到 ${skills.length} 个技能`);
  console.log("\n元技能:");
  skills.filter(s => s.category === "meta").forEach(s => console.log(`  - ${s.name}`));
  console.log(`\n领域技能: ${skills.filter(s => s.category === "domain").length} 个`);
  console.log(`工具技能: ${skills.filter(s => s.category === "utility").length} 个`);
} else if (args[0] === "search") {
  const query = args.slice(1).join(" ");
  const skills = retrieveSkills(query, 5);
  console.log(`查询: "${query}"`);
  console.log("\n相关技能:");
  skills.forEach((s, i) => console.log(`  ${i + 1}. ${s.name} [${s.category}]`));
} else if (args[0] === "context") {
  const query = args.slice(1).join(" ");
  const context = buildSkillContext(query, 3);
  console.log(context);
} else {
  console.log(`
用法:
  bun skill-retriever.ts scan              # 扫描所有技能
  bun skill-retriever.ts search <query>    # 搜索相关技能
  bun skill-retriever.ts context <query>   # 生成上下文注入
`);
}
