/**
 * Skill Retriever MCP Server v2.0
 *
 * 借鉴 AgentSkillOS 理念，实现三层技能架构
 * - Core Layer: 元技能 + Solar 核心，始终加载
 * - Domain Layer: 按意图动态检索
 * - Utility Layer: 冷启动，精确匹配
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { join } from "path";
import { homedir } from "os";
import { readdirSync, readFileSync, existsSync } from "fs";

const SKILLS_DIR = join(homedir(), ".agents", "skills");
const SOLAR_SKILLS_DIR = join(homedir(), ".claude", "skills");

// ============ 技能分层定义 ============

/**
 * 核心层（Core Layer）
 * 始终加载，影响所有输出
 */
const CORE_SKILLS = {
  meta: [
    "systems-thinking",
    "evaluating-trade-offs",
    "problem-definition",
    "root-cause-analysis",
    "decision-helper",
    "firstprinciples",
    "sequential-thinking",
    "scientific-critical-thinking",
    "strategic-compact",
  ],
  solar: [
    "commit",
    "review",
    "test",
    "docs",
    "build",
  ],
};

/**
 * 领域层（Domain Layer）
 * 按意图动态加载
 */
const DOMAIN_SKILLS: Record<string, string[]> = {
  languages: [
    "python-patterns", "python-architect", "python-performance-optimization",
    "javascript-pro", "typescript-expert", "golang-patterns", "rust-patterns",
  ],
  frontend: [
    "react-patterns", "react-architect", "nextjs-patterns", "vue-expert",
    "frontend-performance-optimization", "tailwind-patterns", "shadcn-ui",
  ],
  backend: [
    "django-patterns", "fastapi-development", "nestjs-expert", "springboot-patterns",
    "api-design-principles", "rest-api-design", "graphql-architect",
  ],
  cloud: [
    "kubernetes-specialist", "kubernetes-architect", "terraform-engineer",
    "docker-patterns", "cicd-pipeline-patterns", "github-actions-patterns",
  ],
  database: [
    "postgres-patterns", "mysql-patterns", "redis-patterns", "mongodb-patterns",
    "database-migration", "database-performance-tuning",
  ],
  security: [
    "security-audit-patterns", "auth-implementation-patterns",
    "threat-modeling-patterns", "penetration-testing",
  ],
  testing: [
    "e2e-testing-patterns", "unit-testing-patterns", "playwright-testing",
    "testing-strategies", "property-based-testing",
  ],
  ai: [
    "ai-engineer", "llm-architect", "llm-evaluation", "mlops-engineer",
    "rag-engineer", "prompt-engineering-patterns",
  ],
};

/**
 * 意图 → 领域映射
 */
const INTENT_DOMAIN_MAP: Record<string, keyof typeof DOMAIN_SKILLS> = {
  "python": "languages", "javascript": "languages", "typescript": "languages",
  "golang": "languages", "rust": "languages", "swift": "languages",
  "react": "frontend", "nextjs": "frontend", "next.js": "frontend",
  "vue": "frontend", "angular": "frontend", "前端": "frontend",
  "css": "frontend", "tailwind": "frontend", "ui": "frontend",
  "django": "backend", "fastapi": "backend", "nestjs": "backend",
  "spring": "backend", "api": "backend", "rest": "backend", "graphql": "backend",
  "后端": "backend",
  "kubernetes": "cloud", "k8s": "cloud", "docker": "cloud",
  "terraform": "cloud", "ci/cd": "cloud", "cicd": "cloud",
  "部署": "cloud", "deploy": "cloud", "devops": "cloud",
  "数据库": "database", "postgres": "database", "mysql": "database",
  "redis": "database", "mongodb": "database", "sql": "database",
  "安全": "security", "security": "security", "渗透": "security",
  "漏洞": "security", "xss": "security", "注入": "security",
  "测试": "testing", "test": "testing", "e2e": "testing",
  "playwright": "testing", "unit": "testing",
  "ai": "ai", "llm": "ai", "ml": "ai", "机器学习": "ai",
  "大模型": "ai", "rag": "ai", "prompt": "ai",
};

// 旧的元技能列表（兼容）
const META_SKILLS = CORE_SKILLS.meta;

// 旧的意图映射（兼容）
const INTENT_SKILL_MAP: Record<string, string[]> = {
  "复杂": ["systems-thinking", "problem-definition"],
  "权衡": ["evaluating-trade-offs", "decision-helper"],
  "决策": ["evaluating-trade-offs", "decision-helper", "firstprinciples"],
  "根因": ["root-cause-analysis", "sequential-thinking"],
  "调试": ["root-cause-analysis", "debugging-strategies"],
  "架构": ["architect-reviewer", "architecture-patterns"],
  "分析": ["root-cause-analysis", "systems-thinking"],
  ...Object.fromEntries(
    Object.entries(INTENT_DOMAIN_MAP).map(([k, v]) => [k, DOMAIN_SKILLS[v]?.slice(0, 3) || []])
  ),
};

// ============ 分层检索 ============

export interface LayeredSkillResult {
  core: string[];
  domain: string[];
  utility: string[];
  total: number;
}

/**
 * 分层检索技能
 */
function retrieveByLayer(query: string, maxDomain: number = 9, maxUtility: number = 3): LayeredSkillResult {
  const queryLower = query.toLowerCase();

  // 1. 核心层：始终包含
  const core = [...CORE_SKILLS.meta, ...CORE_SKILLS.solar];

  // 2. 领域层：根据意图匹配
  const matchedDomains = new Set<keyof typeof DOMAIN_SKILLS>();
  for (const [keyword, domain] of Object.entries(INTENT_DOMAIN_MAP)) {
    if (queryLower.includes(keyword.toLowerCase())) {
      matchedDomains.add(domain);
    }
  }

  const domain: string[] = [];
  for (const d of matchedDomains) {
    const skills = DOMAIN_SKILLS[d] || [];
    domain.push(...skills.slice(0, 3));
    if (domain.length >= maxDomain) break;
  }

  // 3. 工具层：精确匹配
  const utility: string[] = [];
  const allSkills = listAllSkills();
  for (const skill of allSkills) {
    if (queryLower.includes(skill.toLowerCase()) &&
        !core.includes(skill) &&
        !domain.includes(skill)) {
      utility.push(skill);
      if (utility.length >= maxUtility) break;
    }
  }

  return { core, domain, utility, total: core.length + domain.length + utility.length };
}

/**
 * 列出所有技能
 */
function listAllSkills(): string[] {
  const skills: string[] = [];
  try {
    const entries = readdirSync(SKILLS_DIR, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) skills.push(entry.name);
    }
  } catch {}
  try {
    const entries = readdirSync(SOLAR_SKILLS_DIR, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) skills.push(entry.name);
    }
  } catch {}
  return [...new Set(skills)];
}

// 旧版搜索函数（兼容）
function searchSkills(query: string, topK: number = 5): Array<{name: string, category: string}> {
  const result = retrieveByLayer(query, topK);
  return [
    ...result.core.map(name => ({ name, category: "core" as const })),
    ...result.domain.map(name => ({ name, category: "domain" as const })),
    ...result.utility.map(name => ({ name, category: "utility" as const })),
  ].slice(0, topK);
}

// 读取技能内容
function loadSkillContent(skillName: string, maxLength: number = 3000): string {
  const paths = [
    join(SKILLS_DIR, skillName, "SKILL.md"),
    join(SOLAR_SKILLS_DIR, skillName, "SKILL.md"),
  ];
  for (const skillPath of paths) {
    try {
      const content = readFileSync(skillPath, "utf-8");
      return content.slice(0, maxLength);
    } catch {}
  }
  return "";
}

// 创建 MCP Server
const server = new Server(
  { name: "skill-retriever", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// 注册工具列表
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_skills",
        description: "搜索技能库，查找与用户问题相关的技能。使用三层架构：核心层（始终加载）+ 领域层（按意图匹配）+ 工具层（精确匹配）。当用户提到：复杂问题、权衡、决策、调试、架构设计、编程语言、测试、安全等场景时调用。",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "用户的问题或意图，用于匹配相关技能"
            },
            top_k: {
              type: "number",
              description: "返回的技能数量，默认5",
              default: 5
            }
          },
          required: ["query"]
        }
      },
      {
        name: "retrieve_layered",
        description: "分层检索技能（v2.0）。返回三层技能：core（核心层-元技能+Solar核心）、domain（领域层-按意图匹配）、utility（工具层-精确匹配）。推荐使用此工具获取更精准的技能推荐。",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "用户的问题或意图"
            },
            max_domain: {
              type: "number",
              description: "领域层最大技能数，默认9",
              default: 9
            },
            max_utility: {
              type: "number",
              description: "工具层最大技能数，默认3",
              default: 3
            }
          },
          required: ["query"]
        }
      },
      {
        name: "load_skill",
        description: "加载指定技能的完整内容。用于深入了解某个技能的具体指导。技能名称如：systems-thinking, python-patterns, kubernetes-specialist 等。",
        inputSchema: {
          type: "object",
          properties: {
            skill_name: {
              type: "string",
              description: "技能名称"
            }
          },
          required: ["skill_name"]
        }
      },
      {
        name: "list_meta_skills",
        description: "列出所有元技能（核心层-思维框架）。元技能是高杠杆技能，如系统思维、权衡分析、根因分析等。这些技能始终被加载。",
        inputSchema: {
          type: "object",
          properties: {}
        }
      },
      {
        name: "skill_stats",
        description: "获取技能库统计信息，包括总技能数、分层统计、可用领域等。",
        inputSchema: {
          type: "object",
          properties: {}
        }
      }
    ]
  };
});

// 处理工具调用
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "search_skills") {
      const query = args?.query as string || "";
      const topK = (args?.top_k as number) || 5;
      const skills = searchSkills(query, topK);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({ query, matched_skills: skills }, null, 2)
        }]
      };
    }

    if (name === "retrieve_layered") {
      const query = args?.query as string || "";
      const maxDomain = (args?.max_domain as number) || 9;
      const maxUtility = (args?.max_utility as number) || 3;
      const result = retrieveByLayer(query, maxDomain, maxUtility);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            query,
            layers: {
              core: { count: result.core.length, skills: result.core },
              domain: { count: result.domain.length, skills: result.domain },
              utility: { count: result.utility.length, skills: result.utility },
            },
            total: result.total
          }, null, 2)
        }]
      };
    }

    if (name === "load_skill") {
      const skillName = args?.skill_name as string || "";
      const content = loadSkillContent(skillName);

      if (!content) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ error: `技能 ${skillName} 不存在或无法读取` })
          }]
        };
      }

      return {
        content: [{
          type: "text",
          text: content
        }]
      };
    }

    if (name === "list_meta_skills") {
      const metaSkills = CORE_SKILLS.meta.map(name => {
        const content = loadSkillContent(name, 200);
        const descMatch = content.match(/description:\s*["']?(.+?)["']?$/m);
        return {
          name,
          layer: "core",
          description: descMatch?.[1] || ""
        };
      });

      return {
        content: [{
          type: "text",
          text: JSON.stringify({ meta_skills: metaSkills, count: metaSkills.length }, null, 2)
        }]
      };
    }

    if (name === "skill_stats") {
      const allSkills = listAllSkills();
      const domainCount = Object.values(DOMAIN_SKILLS).flat().length;

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            total_skills: allSkills.length,
            layers: {
              core: { count: CORE_SKILLS.meta.length + CORE_SKILLS.solar.length, description: "元技能 + Solar核心" },
              domain: { count: domainCount, categories: Object.keys(DOMAIN_SKILLS) },
              utility: { count: allSkills.length - CORE_SKILLS.meta.length - CORE_SKILLS.solar.length - domainCount, description: "剩余技能" }
            },
            available_domains: Object.keys(DOMAIN_SKILLS)
          }, null, 2)
        }]
      };
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({ error: `未知工具: ${name}` })
      }]
    };
  } catch (error) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({ error: String(error) })
      }]
    };
  }
});

// 启动服务
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Skill Retriever MCP Server started");
}

main().catch(console.error);
