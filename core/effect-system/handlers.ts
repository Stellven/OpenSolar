/**
 * Solar Effect System - Built-in Handlers
 *
 * POC: 连接现有 Solar 能力的 Handler 实现
 *
 * @updated 2026-02-17 - 改用 D&D KNOBS 人格格式
 */

import type { Effect, EffectResult, EffectHandler } from './runtime';
import { $ } from 'bun';
import {
  getNiumoEntry,
  generateExpertSystemPrompt,
  getExpertNickname,
  getExpertRole,
  getAvailableExperts,
  type NiumaJsonEntry
} from '../solar-farm/expert-personality';

// ============================================
// Memory Handler
// ============================================

export const memoryHandler: EffectHandler = {
  type: 'need:memory',

  async handle(effect: Effect<{ query: string; limit?: number; namespace?: string }>): Promise<EffectResult> {
    const { query, limit = 10, namespace } = effect.payload;

    try {
      // 查询 evo_memory_semantic，使用 -json 输出 JSON
      const sql = namespace
        ? `SELECT namespace, key, value FROM evo_memory_semantic
           WHERE (key LIKE '%${query}%' OR value LIKE '%${query}%')
           AND namespace = '${namespace}'
           ORDER BY last_accessed_at DESC LIMIT ${limit}`
        : `SELECT namespace, key, value FROM evo_memory_semantic
           WHERE key LIKE '%${query}%' OR value LIKE '%${query}%'
           ORDER BY last_accessed_at DESC LIMIT ${limit}`;

      const result = Bun.$`sqlite3 ~/.solar/solar.db "${sql}" -json`;
      const text = await result.text();

      return {
        success: true,
        data: text ? JSON.parse(text) : [],
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Personality Handler (D&D KNOBS)
// ============================================

export const personalityHandler: EffectHandler = {
  type: 'need:personality',

  async handle(effect: Effect<{ modelId?: string }>): Promise<EffectResult> {
    // modelId 可以是: gemini-2.5-pro, deepseek-r1, glm-5 等
    const { modelId = 'gemini-2.5-pro' } = effect.payload || {};

    try {
      // 使用 D&D KNOBS 统一接口
      const entry = getNiumoEntry(modelId);

      if (!entry) {
        return {
          success: false,
          error: `Expert not found: ${modelId}. Available: ${getAvailableExperts().join(', ')}`,
          duration: 0
        };
      }

      // 返回 D&D KNOBS 格式
      return {
        success: true,
        data: {
          modelId,
          nickname: entry.nickname,
          role: entry.role,
          knobs: entry.knobs,
          systemPrompt: generateExpertSystemPrompt(modelId)
        },
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Knowledge Handler (Cortex)
// ============================================

export const knowledgeHandler: EffectHandler = {
  type: 'need:knowledge',

  async handle(effect: Effect<{ query: string; limit?: number }>): Promise<EffectResult> {
    const { query, limit = 10 } = effect.payload;

    try {
      // 使用现有的 unified-query
      const result = Bun.$`bun ~/.claude/core/cortex/unified-query.ts search "${query}" ${limit}`;
      const text = await result.text();

      return {
        success: true,
        data: text,
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Write Handler
// ============================================

export const writeHandler: EffectHandler = {
  type: 'perform:write',

  async handle(effect: Effect<{ path: string; content: string; mode?: string }>): Promise<EffectResult> {
    const { path, content, mode = 'overwrite' } = effect.payload;

    try {
      if (mode === 'append') {
        await Bun.write(path, content, { create: true });
      } else {
        await Bun.write(path, content);
      }

      return {
        success: true,
        data: { path, bytesWritten: content.length },
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Store Handler (Memory)
// ============================================

export const storeHandler: EffectHandler = {
  type: 'perform:store',

  async handle(effect: Effect<{ namespace: string; key: string; value: any }>): Promise<EffectResult> {
    const { namespace, key, value } = effect.payload;

    try {
      // 生成 memory_id (使用 namespace + key 的 hash)
      const memoryId = `${namespace}:${key}`;
      const valueJson = JSON.stringify(value).replace(/'/g, "''");
      const sql = `INSERT OR REPLACE INTO evo_memory_semantic
                   (memory_id, namespace, key, value, source_type, confidence, created_at, updated_at, last_accessed_at)
                   VALUES ('${memoryId}', '${namespace}', '${key}', json('${valueJson}'), 'explicit', 1.0, datetime('now'), datetime('now'), datetime('now'))`;

      await Bun.$`sqlite3 ~/.solar/solar.db "${sql}"`;

      return {
        success: true,
        data: { namespace, key, memoryId },
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Delegate Handler (Brain Router)
// ============================================

export const delegateHandler: EffectHandler = {
  type: 'perform:delegate',

  async handle(effect: Effect<{ model: string; task: string; context?: string }>): Promise<EffectResult> {
    const { model, task, context } = effect.payload;

    try {
      // 这里只是 POC，实际应该调用 brain-router MCP
      // 暂时返回模拟结果
      console.log(`[Delegate] Would call ${model} with: ${task}`);

      return {
        success: true,
        data: { model, task, result: `[POC] Delegated to ${model}` },
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Query Handler
// ============================================

export const queryHandler: EffectHandler = {
  type: 'perform:query',

  async handle(effect: Effect<{ sql: string; params?: any[] }>): Promise<EffectResult> {
    const { sql } = effect.payload;

    try {
      const result = Bun.$`sqlite3 ~/.solar/solar.db "${sql}" -json`;
      const text = await result.text();

      return {
        success: true,
        data: JSON.parse(text || '[]'),
        duration: 0
      };
    } catch (error) {
      return {
        success: false,
        error: String(error),
        duration: 0
      };
    }
  }
};

// ============================================
// Register All Handlers
// ============================================

export function registerAllHandlers(runtime: import('./runtime').EffectRuntime): void {
  runtime.registerHandler(memoryHandler);
  runtime.registerHandler(personalityHandler);
  runtime.registerHandler(knowledgeHandler);
  runtime.registerHandler(writeHandler);
  runtime.registerHandler(storeHandler);
  runtime.registerHandler(delegateHandler);
  runtime.registerHandler(queryHandler);

  console.log('✅ All handlers registered');
}
