/**
 * Solar Effect System - Built-in Skills
 *
 * 这些是实现具体能力的 Skills
 * LLM 不知道这些存在，只知道对应的 Abilities
 */

import type { Skill, SkillHandler, SkillContext, SkillResult } from './types';

// ============================================
// Search Skills
// ============================================

const tantivySearchHandler: SkillHandler = async (payload, context) => {
  const { query, scope = 'all', limit = 10 } = payload;

  try {
    // 使用 Tantivy 搜索
    const cmd = `~/.claude/core/search/target/release/solar-search query "${query}" ${limit}`;
    const result = Bun.$`${{ raw: cmd }}`;
    const text = await result.text();

    return {
      success: true,
      data: { results: text, source: 'tantivy' },
      duration: 0
    };
  } catch (error) {
    return {
      success: false,
      error: String(error),
      duration: 0
    };
  }
};

const cortexSearchHandler: SkillHandler = async (payload, context) => {
  const { query, limit = 10 } = payload;

  try {
    // 使用 Cortex 统一查询
    const cmd = `bun ~/.claude/core/cortex/unified-query.ts search "${query}" ${limit}`;
    const result = Bun.$`${{ raw: cmd }}`;
    const text = await result.text();

    return {
      success: true,
      data: { results: text, source: 'cortex' },
      duration: 0
    };
  } catch (error) {
    return {
      success: false,
      error: String(error),
      duration: 0
    };
  }
};

const webSearchHandler: SkillHandler = async (payload, context) => {
  const { query, limit = 10 } = payload;

  // 这里应该调用 Web 搜索 API
  // POC 版本返回占位符
  return {
    success: true,
    data: { results: `[Web Search POC] Query: ${query}`, source: 'web' },
    duration: 0
  };
};

// ============================================
// Recall Skills
// ============================================

const memoryRecallHandler: SkillHandler = async (payload, context) => {
  const { key, namespace } = payload;

  try {
    let sql;
    if (namespace) {
      sql = `SELECT key, value FROM evo_memory_semantic WHERE key LIKE '%${key}%' AND namespace = '${namespace}'`;
    } else {
      sql = `SELECT key, value FROM evo_memory_semantic WHERE key LIKE '%${key}%'`;
    }

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
};

// ============================================
// Store Skills
// ============================================

const sqliteStoreHandler: SkillHandler = async (payload, context) => {
  const { key, value, namespace = 'general', ttl } = payload;

  try {
    const valueJson = JSON.stringify(value).replace(/'/g, "''");
    const sql = `INSERT OR REPLACE INTO evo_memory_semantic (namespace, key, value, created_at, last_accessed_at)
                 VALUES ('${namespace}', '${key}', json('${valueJson}'), datetime('now'), datetime('now'))`;

    await Bun.$`sqlite3 ~/.solar/solar.db "${sql}"`;

    return {
      success: true,
      data: { key, namespace },
      duration: 0
    };
  } catch (error) {
    return {
      success: false,
      error: String(error),
      duration: 0
    };
  }
};

// ============================================
// Write Skills
// ============================================

const fileWriteHandler: SkillHandler = async (payload, context) => {
  const { path, content, mode = 'overwrite' } = payload;

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
};

// ============================================
// Notify Skills
// ============================================

const imessageHandler: SkillHandler = async (payload, context) => {
  const { message, channel } = payload;

  try {
    // 调用 imessage-send skill
    // POC: 简化实现
    console.log(`[iMessage] ${message}`);

    return {
      success: true,
      data: { channel: 'imessage', sent: true },
      duration: 0
    };
  } catch (error) {
    return {
      success: false,
      error: String(error),
      duration: 0
    };
  }
};

const emailHandler: SkillHandler = async (payload, context) => {
  const { message, channel } = payload;

  try {
    console.log(`[Email] ${message}`);

    return {
      success: true,
      data: { channel: 'email', sent: true },
      duration: 0
    };
  } catch (error) {
    return {
      success: false,
      error: String(error),
      duration: 0
    };
  }
};

// ============================================
// Delegate Skills
// ============================================

const brainRouterHandler: SkillHandler = async (payload, context) => {
  const { task, agent, context: taskContext } = payload;

  try {
    // 这里应该调用 brain-router MCP
    // POC: 返回占位符
    console.log(`[Delegate] Task: ${task} → ${agent || 'auto'}`);

    return {
      success: true,
      data: { result: `[POC] Delegated: ${task}`, agent: agent || 'auto' },
      duration: 0
    };
  } catch (error) {
    return {
      success: false,
      error: String(error),
      duration: 0
    };
  }
};

// ============================================
// Query Skills
// ============================================

const sqliteQueryHandler: SkillHandler = async (payload, context) => {
  const { type, expression, params } = payload;

  if (type !== 'sql') {
    return {
      success: false,
      error: `Unsupported query type: ${type}`,
      duration: 0
    };
  }

  try {
    const result = Bun.$`sqlite3 ~/.solar/solar.db "${expression}" -json`;
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
};

// ============================================
// Export All Built-in Skills
// ============================================

export const BUILTIN_SKILLS: Skill[] = [
  // Search Skills
  {
    id: 'tantivy-search',
    implements: 'search',
    handler: tantivySearchHandler,
    priority: 0.95,
    conditions: [{ type: 'availability', expression: 'true' }],
    description: 'Tantivy 全文搜索'
  },
  {
    id: 'cortex-search',
    implements: 'search',
    handler: cortexSearchHandler,
    priority: 0.85,
    description: 'Cortex 知识库搜索'
  },
  {
    id: 'web-search',
    implements: 'search',
    handler: webSearchHandler,
    priority: 0.6,
    conditions: [{ type: 'env', expression: 'WEB_SEARCH_ENABLED' }],
    description: 'Web 搜索'
  },

  // Recall Skills
  {
    id: 'memory-recall',
    implements: 'recall',
    handler: memoryRecallHandler,
    priority: 1.0,
    description: 'SQLite 记忆查询'
  },

  // Store Skills
  {
    id: 'sqlite-store',
    implements: 'store',
    handler: sqliteStoreHandler,
    priority: 1.0,
    description: 'SQLite 持久化存储'
  },

  // Write Skills
  {
    id: 'file-write',
    implements: 'write',
    handler: fileWriteHandler,
    priority: 1.0,
    description: '文件写入'
  },

  // Notify Skills
  {
    id: 'imessage-notify',
    implements: 'notify',
    handler: imessageHandler,
    priority: 0.9,
    conditions: [{ type: 'context', expression: 'payload.channel === "imessage" || payload.channel === undefined' }],
    description: 'iMessage 通知'
  },
  {
    id: 'email-notify',
    implements: 'notify',
    handler: emailHandler,
    priority: 0.7,
    conditions: [{ type: 'context', expression: 'payload.channel === "email"' }],
    description: 'Email 通知'
  },

  // Delegate Skills
  {
    id: 'brain-router',
    implements: 'delegate',
    handler: brainRouterHandler,
    priority: 1.0,
    description: 'Brain Router 牛马调度'
  },

  // Query Skills
  {
    id: 'sqlite-query',
    implements: 'query',
    handler: sqliteQueryHandler,
    priority: 1.0,
    description: 'SQLite 查询'
  }
];

/**
 * 注册所有内置 Skills 到 Registry
 */
export function registerBuiltinSkills(registry: import('./registry').AbilitiesRegistry): void {
  registry.registerSkills(BUILTIN_SKILLS);
  console.log(`✅ Registered ${BUILTIN_SKILLS.length} built-in skills`);
}
