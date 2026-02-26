#!/usr/bin/env bun
/**
 * Routing Decision MCP Server
 *
 * 提供模型推荐查询接口，集成 effective_score
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { Database } from 'bun:sqlite';

const db = new Database(process.env.HOME + '/.solar/solar.db');

const server = new Server(
  { name: "routing-decision", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// ═══════════════════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════════════════

function getRecommendedModels(threshold: number = 0.7) {
  const rules = db.query(`
    SELECT target_model, effective_score, rule_name
    FROM sys_routing_model
    WHERE enabled = 1
    ORDER BY effective_score DESC
  `).all() as any[];

  const modelStats = new Map<string, any>();

  for (const rule of rules) {
    const modelId = rule.target_model;

    if (!modelStats.has(modelId)) {
      modelStats.set(modelId, {
        model_id: modelId,
        scores: [],
        rules: []
      });
    }

    const stats = modelStats.get(modelId)!;
    stats.scores.push(rule.effective_score);
    stats.rules.push(rule.rule_name);
  }

  // 计算平均分
  const results = Array.from(modelStats.values()).map(stats => ({
    model_id: stats.model_id,
    avg_effective_score: stats.scores.reduce((a: number, b: number) => a + b, 0) / stats.scores.length,
    min_effective_score: Math.min(...stats.scores),
    max_effective_score: Math.max(...stats.scores),
    rule_count: stats.scores.length
  }));

  // 过滤并排序
  return results
    .filter(m => m.avg_effective_score >= threshold)
    .sort((a, b) => b.avg_effective_score - a.avg_effective_score);
}

function getModelRecommendation(taskType: string, complexity: number = 5) {
  const threshold = 0.7;
  const models = getRecommendedModels(threshold);

  // 根据任务类型和复杂度推荐
  let recommended = models;

  // 复杂任务优先推荐高端模型
  if (complexity >= 7) {
    recommended = models.filter(m =>
      m.avg_effective_score >= 0.85 &&
      ['deepseek-r1', 'gemini-2.5-pro', 'o1'].includes(m.model_id)
    );
  }

  // 简单任务推荐快速模型
  if (complexity <= 3) {
    recommended = models.filter(m =>
      ['glm-4-flash', 'glm-5'].includes(m.model_id)
    );
  }

  return recommended.length > 0 ? recommended[0] : models[0];
}

// ═══════════════════════════════════════════════════════════════════════════
// Tools
// ═══════════════════════════════════════════════════════════════════════════

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_recommended_models",
      description: "获取推荐模型列表（基于 effective_score）",
      inputSchema: {
        type: "object",
        properties: {
          threshold: {
            type: "number",
            description: "最低有效分数阈值（默认 0.7）",
            default: 0.7
          }
        }
      }
    },
    {
      name: "get_model_recommendation",
      description: "根据任务类型和复杂度获取模型推荐",
      inputSchema: {
        type: "object",
        properties: {
          task_type: {
            type: "string",
            description: "任务类型 (coding/analysis/reasoning/general)"
          },
          complexity: {
            type: "number",
            description: "复杂度 (1-10)",
            default: 5
          }
        },
        required: ["task_type"]
      }
    }
  ]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "get_recommended_models") {
      const threshold = args?.threshold ?? 0.7;
      const models = getRecommendedModels(threshold);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            threshold,
            count: models.length,
            models
          }, null, 2)
        }]
      };
    }

    if (name === "get_model_recommendation") {
      const taskType = args?.task_type || "general";
      const complexity = args?.complexity ?? 5;
      const recommendation = getModelRecommendation(taskType, complexity);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            task_type: taskType,
            complexity,
            recommendation
          }, null, 2)
        }]
      };
    }

    throw new Error(`Unknown tool: ${name}`);
  } catch (error: any) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({ error: error.message })
      }]
    };
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// Start Server
// ═══════════════════════════════════════════════════════════════════════════

const transport = new StdioServerTransport();
server.connect(transport);

console.error("Routing Decision MCP Server running on stdio");
