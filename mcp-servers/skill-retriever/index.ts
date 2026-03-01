/**
 * Skill Retriever MCP Server
 * 
 * 提供技能检索能力，让 AI 按需调用
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

// 元技能列表
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

// 意图映射
const INTENT_SKILL_MAP: Record<string, string[]> = {
  "复杂": ["systems-thinking", "problem-definition"],
  "权衡": ["evaluating-trade-offs", "decision-helper"],
  "决策": ["evaluating-trade-offs", "decision-helper", "firstprinciples"],
  "根因": ["root-cause-analysis", "sequential-thinking"],
  "调试": ["root-cause-analysis", "debugging-strategies"],
  "架构": ["architect-reviewer", "architecture-patterns", "evaluating-trade-offs"],
  "设计": ["architecture-patterns", "domain-driven-design"],
  "分析": ["root-cause-analysis", "systems-thinking", "evaluating-trade-offs"],
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

// 检索技能
function searchSkills(query: string, topK: number = 5): Array<{name: string, category: string}> {
  const queryLower = query.toLowerCase();
  const scores = new Map<string, number>();
  
  // 意图匹配
  for (const [intent, skills] of Object.entries(INTENT_SKILL_MAP)) {
    if (queryLower.includes(intent.toLowerCase())) {
      for (const skill of skills) {
        const baseScore = META_SKILLS.includes(skill) ? 10 : 5;
        scores.set(skill, (scores.get(skill) || 0) + baseScore);
      }
    }
  }
  
  // 关键词匹配
  const keywords = queryLower.split(/\s+/).filter(w => w.length > 2);
  for (const keyword of keywords) {
    for (const skill of Object.keys(INTENT_SKILL_MAP).flatMap(k => INTENT_SKILL_MAP[k])) {
      if (skill.toLowerCase().includes(keyword)) {
        scores.set(skill, (scores.get(skill) || 0) + 2);
      }
    }
  }
  
  // 排序返回
  return [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, topK)
    .map(([name]) => ({
      name,
      category: META_SKILLS.includes(name) ? "meta" : "domain"
    }));
}

// 读取技能内容
function loadSkillContent(skillName: string, maxLength: number = 3000): string {
  const skillPath = join(SKILLS_DIR, skillName, "SKILL.md");
  try {
    const content = readFileSync(skillPath, "utf-8");
    return content.slice(0, maxLength);
  } catch {
    return "";
  }
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
        description: "搜索技能库，查找与用户问题相关的技能。当用户提到：复杂问题、权衡、决策、调试、架构设计、编程语言、测试、安全等场景时调用。返回匹配的技能列表。",
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
        description: "列出所有元技能（高杠杆技能）。元技能是低频但高价值的思维框架，如系统思维、权衡分析、根因分析等。",
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
      const metaSkills = META_SKILLS.map(name => {
        const content = loadSkillContent(name, 200);
        const descMatch = content.match(/description:\s*["']?(.+?)["']?$/m);
        return {
          name,
          description: descMatch?.[1] || ""
        };
      });
      
      return {
        content: [{
          type: "text",
          text: JSON.stringify({ meta_skills: metaSkills }, null, 2)
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
