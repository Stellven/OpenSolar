#!/usr/bin/env bun
/**
 * XiaoAi MCP Server
 *
 * 将小爱 (OpenClaw Agent) 暴露为 MCP 工具
 *
 * 工具列表:
 * - xiaoai_chat: 与小爱对话
 * - xiaoai_status: 获取小爱服务状态
 * - xiaoai_task: 给小爱分配任务
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
import { $ } from "bun";

// ============================================================
// XiaoAi Functions
// ============================================================

interface XiaoAiResponse {
  success: boolean;
  content: string;
  latency_ms?: number;
  error?: string;
}

interface GatewayStatus {
  running: boolean;
  pid?: number;
  port?: number;
  model?: string;
}

/**
 * 调用小爱 (通过 openclaw agent --local)
 */
async function chat(message: string, sessionId?: string): Promise<XiaoAiResponse> {
  const start = Date.now();

  try {
    const sid = sessionId || `solar-${Date.now()}`;

    // 使用 openclaw agent 命令调用小爱
    const result = await $`openclaw agent --local --agent main --session-id ${sid} --message ${message} --timeout 60`.quiet();

    const content = result.stdout.toString().trim();
    const latency = Date.now() - start;

    return {
      success: true,
      content,
      latency_ms: latency,
    };
  } catch (error) {
    return {
      success: false,
      content: "",
      error: error instanceof Error ? error.message : String(error),
      latency_ms: Date.now() - start,
    };
  }
}

/**
 * 获取 Gateway 状态
 */
async function getStatus(): Promise<GatewayStatus> {
  try {
    // 检查 launchd 服务状态
    const result = await $`launchctl list | grep openclaw-gateway`.quiet();
    const output = result.stdout.toString().trim();

    if (output) {
      const match = output.match(/^(\d+)\s+(\d+)\s+(.+)$/);
      if (match) {
        return {
          running: true,
          pid: parseInt(match[1]),
          port: 18789,
          model: "zai/glm-4.7",
        };
      }
    }

    return { running: false };
  } catch {
    return { running: false };
  }
}

/**
 * 给小爱分配任务 (带结构化输出)
 */
async function assignTask(
  taskType: string,
  params: Record<string, unknown>
): Promise<XiaoAiResponse> {
  const taskPrompts: Record<string, string> = {
    email: "处理邮件任务",
    calendar: "处理日历任务",
    reminder: "处理提醒任务",
    note: "处理笔记任务",
    message: "处理消息任务",
    search: "搜索信息",
    summary: "总结内容",
  };

  const promptPrefix = taskPrompts[taskType] || "处理任务";
  const paramsJson = JSON.stringify(params, null, 2);
  const message = `${promptPrefix}:\n${paramsJson}`;

  return chat(message, `task-${taskType}-${Date.now()}`);
}

// ============================================================
// MCP Server Setup
// ============================================================

const server = new Server(
  {
    name: "xiaoai-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// ListTools handler
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "xiaoai_chat",
        description: "与小爱对话，发送消息并获取回复。小爱是 Solar 的 AI 秘书，擅长处理日常事务。",
        inputSchema: {
          type: "object",
          properties: {
            message: {
              type: "string",
              description: "要发送给小爱的消息内容",
            },
            session_id: {
              type: "string",
              description: "可选的会话ID，用于保持对话上下文",
            },
          },
          required: ["message"],
        },
      },
      {
        name: "xiaoai_status",
        description: "获取小爱服务的运行状态，包括是否运行、PID、端口等信息。",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "xiaoai_task",
        description: "给小爱分配特定类型的任务。支持的任务类型: email, calendar, reminder, note, message, search, summary。",
        inputSchema: {
          type: "object",
          properties: {
            task_type: {
              type: "string",
              enum: ["email", "calendar", "reminder", "note", "message", "search", "summary"],
              description: "任务类型",
            },
            params: {
              type: "object",
              description: "任务参数",
            },
          },
          required: ["task_type"],
        },
      },
    ],
  };
});

// CallTool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "xiaoai_chat": {
        const message = args?.message as string;
        const sessionId = args?.session_id as string | undefined;

        if (!message) {
          throw new McpError(ErrorCode.InvalidParams, "message is required");
        }

        const result = await chat(message, sessionId);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "xiaoai_status": {
        const status = await getStatus();

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(status, null, 2),
            },
          ],
        };
      }

      case "xiaoai_task": {
        const taskType = args?.task_type as string;
        const params = (args?.params as Record<string, unknown>) || {};

        if (!taskType) {
          throw new McpError(ErrorCode.InvalidParams, "task_type is required");
        }

        const result = await assignTask(taskType, params);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      default:
        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
    }
  } catch (error) {
    if (error instanceof McpError) {
      throw error;
    }

    throw new McpError(
      ErrorCode.InternalError,
      error instanceof Error ? error.message : String(error)
    );
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("XiaoAi MCP Server started");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
