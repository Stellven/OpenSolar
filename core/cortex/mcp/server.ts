#!/usr/bin/env bun
/**
 * Cortex MCP Server
 *
 * 将 Cortex 中枢神经暴露为 MCP 工具
 *
 * 工具列表:
 * - cortex_search: 统一搜索 (Cortex + Knowledge)
 * - cortex_evidence: 获取证据包
 * - cortex_graph: 知识图谱查询
 * - cortex_stats: 统计信息
 *
 * @version 1.0.0
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ErrorCode,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { Database } from "bun:sqlite";
import { homedir } from "os";

const DB_PATH = `${homedir()}/.solar/solar.db`;

// ============================================================
// Cortex Query Functions
// ============================================================

interface SearchResult {
  source_id: number;
  title: string;
  finding: string | null;
  credibility: number;
  url: string | null;
}

interface KnowledgeEntity {
  entity_id: number;
  name: string;
  type: string;
  description: string | null;
  importance: number;
}

interface KnowledgeRelation {
  relation_id: number;
  source_entity: string;
  target_entity: string;
  relation_type: string;
  confidence: number;
}

function searchCortex(db: Database, query: string, limit: number = 10): SearchResult[] {
  const sql = `
    SELECT source_id, title, finding, credibility, url
    FROM cortex_sources
    WHERE title LIKE ? OR finding LIKE ?
    ORDER BY credibility DESC
    LIMIT ?
  `;
  const pattern = `%${query}%`;
  return db.query(sql).all(pattern, pattern, limit) as SearchResult[];
}

function searchKnowledge(db: Database, query: string, limit: number = 5): KnowledgeEntity[] {
  const sql = `
    SELECT entity_id, name, type, description, importance
    FROM knowledge_entities
    WHERE name LIKE ? OR description LIKE ?
    ORDER BY importance DESC
    LIMIT ?
  `;
  const pattern = `%${query}%`;
  return db.query(sql).all(pattern, pattern, limit) as KnowledgeEntity[];
}

function getKnowledgeGraph(db: Database, entityName: string): { relations: KnowledgeRelation[]; entities: KnowledgeEntity[] } {
  // 查找相关实体
  const entitySql = `
    SELECT entity_id, name, type, description, importance
    FROM knowledge_entities
    WHERE name = ? OR name IN (
      SELECT from_entity FROM knowledge_relations WHERE to_entity = ?
      UNION
      SELECT to_entity FROM knowledge_relations WHERE from_entity = ?
    )
  `;
  const entities = db.query(entitySql).all(entityName, entityName, entityName) as KnowledgeEntity[];

  // 查找相关关系
  const relationSql = `
    SELECT relation_id, from_entity as source_entity, to_entity as target_entity, relation_type, confidence
    FROM knowledge_relations
    WHERE from_entity = ? OR to_entity = ?
    ORDER BY confidence DESC
    LIMIT 20
  `;
  const relations = db.query(relationSql).all(entityName, entityName) as KnowledgeRelation[];

  return { entities, relations };
}

function getStats(db: Database): object {
  const stats = {
    cortex_sources: 0,
    cortex_claims: 0,
    cortex_artifacts: 0,
    knowledge_entities: 0,
    knowledge_relations: 0,
  };

  try {
    stats.cortex_sources = (db.query("SELECT COUNT(*) as cnt FROM cortex_sources").get() as { cnt: number })?.cnt || 0;
    stats.cortex_claims = (db.query("SELECT COUNT(*) as cnt FROM cortex_claims").get() as { cnt: number })?.cnt || 0;
    stats.cortex_artifacts = (db.query("SELECT COUNT(*) as cnt FROM cortex_artifacts").get() as { cnt: number })?.cnt || 0;
    stats.knowledge_entities = (db.query("SELECT COUNT(*) as cnt FROM knowledge_entities").get() as { cnt: number })?.cnt || 0;
    stats.knowledge_relations = (db.query("SELECT COUNT(*) as cnt FROM knowledge_relations").get() as { cnt: number })?.cnt || 0;
  } catch (e) {
    // Ignore errors
  }

  return stats;
}

// ============================================================
// MCP Server Setup
// ============================================================

const server = new Server(
  { name: "cortex-mcp-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// List Tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "cortex_search",
        description: "搜索 Cortex 中枢神经和知识图谱。返回相关的参考资料、实体和关系。使用场景：设计/开发前查已有知识、查找历史分析、验证假设。",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "搜索关键词或问题",
            },
            limit: {
              type: "number",
              description: "返回结果数量，默认 10",
              default: 10,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "cortex_graph",
        description: "查询知识图谱。返回指定实体及其相关实体和关系网络。使用场景：理解概念关系、追踪引用链、发现隐藏连接。",
        inputSchema: {
          type: "object",
          properties: {
            entity: {
              type: "string",
              description: "实体名称（如技术名、人名、概念名）",
            },
          },
          required: ["entity"],
        },
      },
      {
        name: "cortex_stats",
        description: "获取 Cortex 统计信息。返回数据量和健康状态。",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  };
});

// Handle Tool Calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const db = new Database(DB_PATH);

  try {
    switch (name) {
      case "cortex_search": {
        const query = args?.query as string;
        const limit = (args?.limit as number) || 10;

        if (!query) {
          throw new McpError(ErrorCode.InvalidParams, "Missing query parameter");
        }

        const cortexResults = searchCortex(db, query, limit);
        const knowledgeResults = searchKnowledge(db, query, 5);

        // 格式化输出
        let output = `🔍 Cortex 搜索结果: "${query}"\n\n`;

        if (cortexResults.length > 0) {
          output += `📚 参考资料 (${cortexResults.length}):\n`;
          cortexResults.forEach((r, i) => {
            output += `${i + 1}. [${Math.round(r.credibility * 100)}%] ${r.title}\n`;
            if (r.finding) {
              output += `   ${r.finding.substring(0, 150)}${r.finding.length > 150 ? '...' : ''}\n`;
            }
          });
        }

        if (knowledgeResults.length > 0) {
          output += `\n👤 知识实体 (${knowledgeResults.length}):\n`;
          knowledgeResults.forEach((e) => {
            output += `[${e.type}] ${e.name}`;
            if (e.description) {
              output += `: ${e.description.substring(0, 100)}${e.description.length > 100 ? '...' : ''}`;
            }
            output += "\n";
          });
        }

        if (cortexResults.length === 0 && knowledgeResults.length === 0) {
          output += "未找到相关结果。\n";
        }

        return { content: [{ type: "text", text: output }] };
      }

      case "cortex_graph": {
        const entity = args?.entity as string;

        if (!entity) {
          throw new McpError(ErrorCode.InvalidParams, "Missing entity parameter");
        }

        const { entities, relations } = getKnowledgeGraph(db, entity);

        let output = `🔗 知识图谱: "${entity}"\n\n`;

        if (entities.length > 0) {
          output += `实体 (${entities.length}):\n`;
          entities.forEach((e) => {
            output += `• [${e.type}] ${e.name}`;
            if (e.description) {
              output += ` - ${e.description.substring(0, 80)}`;
            }
            output += "\n";
          });
        }

        if (relations.length > 0) {
          output += `\n关系 (${relations.length}):\n`;
          relations.forEach((r) => {
            output += `• ${r.source_entity} --[${r.relation_type}]--> ${r.target_entity} (${Math.round(r.confidence * 100)}%)\n`;
          });
        }

        if (entities.length === 0 && relations.length === 0) {
          output += `未找到实体 "${entity}" 相关的知识图谱。\n`;
        }

        return { content: [{ type: "text", text: output }] };
      }

      case "cortex_stats": {
        const stats = getStats(db);

        const output = `📊 Cortex 统计信息

📚 Cortex 数据:
   • 参考资料: ${stats.cortex_sources} 条
   • 论证结论: ${stats.cortex_claims} 条
   • 分析产物: ${stats.cortex_artifacts} 个

🧠 知识图谱:
   • 实体: ${stats.knowledge_entities} 个
   • 关系: ${stats.knowledge_relations} 条

总计: ${stats.cortex_sources + stats.cortex_claims + stats.cortex_artifacts + stats.knowledge_entities + stats.knowledge_relations} 条知识
`;

        return { content: [{ type: "text", text: output }] };
      }

      default:
        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
    }
  } finally {
    db.close();
  }
});

// Start Server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Cortex MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
