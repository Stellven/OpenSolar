#!/usr/bin/env bun
/**
 * ARE MCP Server - 让所有大脑都能调用 ARE 编排引擎
 *
 * 功能:
 * - orchestrate: 分析意图并执行编排
 * - plan: 只生成计划不执行
 * - execute_plan: 执行已有计划
 * - list_plans: 列出缓存的计划
 * - stats: 获取执行统计
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { ARE } from './index';
import { IntentToDAG } from './intent-to-dag';
import { Database } from 'bun:sqlite';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

class AREMCPServer {
  private server: Server;
  private are: ARE;
  private intentToDAG: IntentToDAG;
  private db: Database;

  constructor() {
    this.are = new ARE();
    this.intentToDAG = new IntentToDAG();
    this.db = new Database(DB_PATH);

    this.server = new Server(
      { name: 'are-orchestrator', version: '1.0.0' },
      { capabilities: { tools: {} } }
    );

    this.setupHandlers();
  }

  private setupHandlers() {
    // 列出可用工具
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'orchestrate',
          description: '分析用户意图并自动编排执行多步骤任务',
          inputSchema: {
            type: 'object',
            properties: {
              intent: { type: 'string', description: '用户意图' },
              execute: { type: 'boolean', description: '是否执行', default: true }
            },
            required: ['intent']
          }
        },
        {
          name: 'execute_plan',
          description: '执行 PlanIR JSON',
          inputSchema: {
            type: 'object',
            properties: {
              plan_json: { type: 'string', description: 'PlanIR JSON' }
            },
            required: ['plan_json']
          }
        },
        {
          name: 'list_plans',
          description: '列出缓存的计划',
          inputSchema: {
            type: 'object',
            properties: { limit: { type: 'number', default: 10 } }
          }
        },
        {
          name: 'stats',
          description: '获取 ARE 统计',
          inputSchema: { type: 'object', properties: {} }
        }
      ]
    }));

    // 处理工具调用
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      try {
        switch (name) {
          case 'orchestrate': {
            const { intent, execute = true } = args as any;
            const analysis = await this.intentToDAG.analyze(intent);
            if (!execute || !analysis.suggestedPlan) {
              return { content: [{ type: 'text', text: JSON.stringify(analysis, null, 2) }] };
            }
            const result = await this.intentToDAG.execute(intent);
            return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
          }
          case 'execute_plan': {
            const result = await this.are.executeJSON((args as any).plan_json);
            return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
          }
          case 'list_plans': {
            const plans = this.db.query(`SELECT plan_id, intent_text, total_executions FROM are_plan_cache LIMIT ?`).all((args as any).limit || 10);
            return { content: [{ type: 'text', text: JSON.stringify(plans, null, 2) }] };
          }
          case 'stats': {
            const stats = this.db.query(`SELECT (SELECT COUNT(*) FROM are_plan_cache) as plans, (SELECT COUNT(*) FROM are_execution_log) as executions`).get();
            return { content: [{ type: 'text', text: JSON.stringify(stats, null, 2) }] };
          }
          default:
            return { content: [{ type: 'text', text: 'Unknown tool' }], isError: true };
        }
      } catch (e: any) {
        return { content: [{ type: 'text', text: `Error: ${e.message}` }], isError: true };
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('ARE MCP Server running');
  }
}

new AREMCPServer().run().catch(console.error);
