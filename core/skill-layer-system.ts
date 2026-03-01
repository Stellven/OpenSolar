/**
 * Solar 技能分层系统
 * 
 * 借鉴 AgentSkillOS 理念， * 将技能分为三层， * 实现动态加载和优先级管理
 */

import { join } from "path";
import { homedir } from "os";
import { readFileSync, existsSync, readdirSync } from "fs";

const SKILLS_DIR = join(homedir(), ".agents", "skills");
const SOLAR_SKILLS_DIR = join(homedir(), ".claude", "skills");

// ============ 技能分层定义 ============

/**
 * 核心层（Core Layer）
 * 始终加载，影响所有输出
 * 
 * 包含：元技能 + Solar 核心技能
 */
const CORE_SKILLS = {
  // 元技能（思维框架）
  meta: [
    "systems-thinking",        // 系统思维
    "evaluating-trade-offs",   // 权衡分析
    "problem-definition",      // 问题定义
    "root-cause-analysis",    // 根因分析
    "decision-helper",         // 决策辅助
    "firstprinciples",         // 第一性原理
    "sequential-thinking",     // 顺序推理
  ],
  
  // Solar 核心技能
  solar: [
    "commit",           // Git 提交
    "review",            // 代码审查
    "test",              // 测试运行
    "docs",              // 文档生成
    "build",             // 构建项目
    "sp-brainstorming",   // 头脑风暴
    "sp-debugging",       // 系统调试
    "sp-tdd",             // 测试驱动开发
    "sp-code-review",     // 代码审查
  ],
};

/**
 * 领域层（Domain Layer）
 * 按需检索，根据用户意图动态加载
 * 
 * 包含：编程语言、框架、工具的专家级技能
 */
const DOMAIN_SKILLS: Record<string, string[]> = {
  // 编程语言
  languages: [
    "python-patterns",
    "python-architect",
    "python-performance-optimization",
    "javascript-architect",
    "typescript-expert",
    "golang-patterns",
    "rust-patterns",
    "swift-patterns",
    "cpp-pro",
  ],
  
  // 前端框架
  frontend: [
    "react-patterns",
    "react-architect",
    "nextjs-patterns",
    "vue-patterns",
    "angular-architect",
    "frontend-performance-optimization",
    "tailwind-patterns",
    "shadcn-ui",
  ],
  
  // 后端框架
  backend: [
    "django-patterns",
    "fastapi-patterns",
    "nestjs-patterns",
    "springboot-patterns",
    "nodejs-backend-patterns",
    "api-design-principles",
    "rest-api-designer",
    "graphql-architect",
  ],
  
  // 云原生/DevOps
  cloud: [
    "kubernetes-specialist",
    "kubernetes-architect",
    "terraform-engineer",
    "docker-patterns",
    "cicd-pipeline-patterns",
    "github-actions-patterns",
    "git-advanced-workflows",
    "sre-engineer",
    "chaos-engineer",
  ],
  
  // 数据库
  database: [
    "postgres-patterns",
    "mysql-patterns",
    "redis-patterns",
    "mongodb-patterns",
    "database-migration-patterns",
    "database-performance-tuning",
  ],
  
  // 安全
  security: [
    "security-audit-patterns",
    "auth-implementation-patterns",
    "threat-modeling-patterns",
    "penetration-testing",
    "xss-prevention",
    "sql-injection-prevention",
  ],
  
  // 测试
  testing: [
    "e2e-testing-patterns",
    "unit-testing-patterns",
    "playwright-testing",
    "testing-strategies",
    "mutation-testing",
    "property-based-testing",
  ],
  
  // AI/ML
  ai: [
    "ai-engineer",
    "llm-architect",
    "llm-evaluation",
    "mlops-engineer",
    "rag-engineer",
    "prompt-engineering-patterns",
  ],
};

/**
 * 工具层（Utility Layer）
 * 冷启动，只有明确需要时才加载
 * 
 * 包含：具体工具操作、小众领域
 */
const UTILITY_KEYWORDS = [
  // 这些技能只有在明确提到时才触发
  // 通过关键词匹配
];

// ============ 意图识别 ============

/**
 * 用户意图 → 技能类别映射
 */
const INTENT_DOMAIN_MAP: Record<string, keyof typeof DOMAIN_SKILLS> = {
  // 语言关键词
  "python": "languages",
  "javascript": "languages",
  "typescript": "languages",
  "golang": "languages",
  "go语言": "languages",
  "rust": "languages",
  "swift": "languages",
  "cpp": "languages",
  "c++": "languages",
  
  // 前端关键词
  "react": "frontend",
  "nextjs": "frontend",
  "next.js": "frontend",
  "vue": "frontend",
  "angular": "frontend",
  "前端": "frontend",
  "ui": "frontend",
  "css": "frontend",
  "tailwind": "frontend",
  
  // 后端关键词
  "django": "backend",
  "fastapi": "backend",
  "nestjs": "backend",
  "spring": "backend",
  "api": "backend",
  "rest": "backend",
  "graphql": "backend",
  "后端": "backend",
  
  // 云原生关键词
  "kubernetes": "cloud",
  "k8s": "cloud",
  "docker": "cloud",
  "terraform": "cloud",
  "ci/cd": "cloud",
  "cicd": "cloud",
  "部署": "cloud",
  "deploy": "cloud",
  "devops": "cloud",
  "sre": "cloud",
  
  // 数据库关键词
  "数据库": "database",
  "postgres": "database",
  "mysql": "database",
  "redis": "database",
  "mongodb": "database",
  "sql": "database",
  
  // 安全关键词
  "安全": "security",
  "security": "security",
  "渗透": "security",
  "漏洞": "security",
  "xss": "security",
  "注入": "security",
  
  // 测试关键词
  "测试": "testing",
  "test": "testing",
  "e2e": "testing",
  "playwright": "testing",
  
  // AI 关键词
  "ai": "ai",
  "ml": "ai",
  "llm": "ai",
  "机器学习": "ai",
  "大模型": "ai",
  "rag": "ai",
  "prompt": "ai",
};

// ============ 技能检索器 ============

export interface SkillRetrievalResult {
  core: string[];      // 核心层技能
  domain: string[];    // 领域层技能
  utility: string[];   // 工具层技能
  context: string;     // 生成的上下文
}

/**
 * 根据用户输入检索相关技能
 */
export function retrieveSkillsByLayer(
  userInput: string,
  options: {
    maxDomainSkills?: number;
    maxUtilitySkills?: number;
    maxContextTokens?: number;
  } = {}
): SkillRetrievalResult {
  const {
    maxDomainSkills = 5,
    maxUtilitySkills = 3,
    maxContextTokens = 4000,
  } = options;
  
  const inputLower = userInput.toLowerCase();
  
  // 1. 核心层：始终包含
  const core = [
    ...CORE_SKILLS.meta,
    ...CORE_SKILLS.solar,
  ];
  
  // 2. 领域层：根据意图匹配
  const matchedDomains = new Set<keyof typeof DOMAIN_SKILLS>();
  
  for (const [keyword, domain] of Object.entries(INTENT_DOMAIN_MAP)) {
    if (inputLower.includes(keyword.toLowerCase())) {
      matchedDomains.add(domain);
    }
  }
  
  const domain: string[] = [];
  for (const d of matchedDomains) {
    const skills = DOMAIN_SKILLS[d] || [];
    domain.push(...skills.slice(0, 3)); // 每个领域最多3个
  }
  
  // 3. 工具层：精确匹配
  const utility: string[] = [];
  // 从剩余技能中匹配
  const allSkills = listAllSkills();
  for (const skill of allSkills) {
    if (inputLower.includes(skill.toLowerCase()) && 
        !core.includes(skill) && 
        !domain.includes(skill)) {
      utility.push(skill);
      if (utility.length >= maxUtilitySkills) break;
    }
  }
  
  // 4. 生成上下文
  const context = buildSkillContext([...core, ...domain, ...utility], maxContextTokens);
  
  return { core, domain, utility, context };
}

/**
 * 列出所有可用技能
 */
function listAllSkills(): string[] {
  const skills: string[] = [];
  
  try {
    const entries = readdirSync(SKILLS_DIR, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        skills.push(entry.name);
      }
    }
  } catch (e) {
    // ignore
  }
  
  try {
    const entries = readdirSync(SOLAR_SKILLS_DIR, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        skills.push(entry.name);
      }
    }
  } catch (e) {
    // ignore
  }
  
  return [...new Set(skills)];
}

/**
 * 构建技能上下文
 */
function buildSkillContext(skillNames: string[], maxTokens: number): string {
  let context = "# 技能上下文\n\n";
  let estimatedTokens = 0;
  
  for (const name of skillNames) {
    const skillPath = findSkillPath(name);
    if (!skillPath) continue;
    
    try {
      const content = readFileSync(skillPath, "utf-8");
      const skillContext = `\n## ${name}\n\n${content.slice(0, 1500)}\n`;
      const tokens = skillContext.length / 4;
      
      if (estimatedTokens + tokens > maxTokens) break;
      
      context += skillContext;
      estimatedTokens += tokens;
    } catch (e) {
      // ignore
    }
  }
  
  return context;
}

/**
 * 查找技能路径
 */
function findSkillPath(skillName: string): string | null {
  const paths = [
    join(SKILLS_DIR, skillName, "SKILL.md"),
    join(SOLAR_SKILLS_DIR, skillName, "SKILL.md"),
  ];
  
  for (const p of paths) {
    if (existsSync(p)) return p;
  }
  return null;
}

// ============ CLI 入口 ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  
  if (args[0] === "retrieve") {
    const query = args.slice(1).join(" ");
    const result = retrieveSkillsByLayer(query);
    
    console.log("=== 核心层 ===");
    result.core.forEach(s => console.log(`  ${s}`));
    
    console.log("\n=== 领域层 ===");
    result.domain.forEach(s => console.log(`  ${s}`));
    
    console.log("\n=== 工具层 ===");
    result.utility.forEach(s => console.log(`  ${s}`));
    
    console.log(`\n总技能数: ${result.core.length + result.domain.length + result.utility.length}`);
  } else if (args[0] === "stats") {
    const allSkills = listAllSkills();
    console.log(`总技能数: ${allSkills.length}`);
    console.log(`核心层: ${CORE_SKILLS.meta.length + CORE_SKILLS.solar.length}`);
    console.log(`领域层: ${Object.values(DOMAIN_SKILLS).flat().length}`);
  } else {
    console.log(`
用法:
  bun skill-layer-system.ts retrieve <query>   # 检索技能
  bun skill-layer-system.ts stats              # 统计技能
`);
  }
}
