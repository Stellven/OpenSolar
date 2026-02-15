#!/usr/bin/env bun
/**
 * sync-claude-usage.ts
 * 同步 Claude Code stats-cache.json 到 solar.db
 *
 * Usage: bun sync-claude-usage.ts [--force]
 */

import { Database } from "bun:sqlite";
import { readFileSync, existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const STATS_CACHE = join(homedir(), ".claude/stats-cache.json");
const SOLAR_DB = join(homedir(), ".solar/solar.db");

interface StatsCache {
  version: number;
  lastComputedDate: string;
  dailyActivity: Array<{
    date: string;
    messageCount: number;
    sessionCount: number;
    toolCallCount: number;
  }>;
  dailyModelTokens: Array<{
    date: string;
    tokensByModel: Record<string, number>;
  }>;
  modelUsage: Record<string, {
    inputTokens: number;
    outputTokens: number;
    cacheReadInputTokens: number;
    cacheCreationInputTokens: number;
    webSearchRequests?: number;
    costUSD?: number;
  }>;
  totalSessions: number;
  totalMessages: number;
}

function syncClaudeUsage(force: boolean = false): void {
  // 检查文件是否存在
  if (!existsSync(STATS_CACHE)) {
    console.error(`❌ stats-cache.json not found: ${STATS_CACHE}`);
    process.exit(1);
  }

  if (!existsSync(SOLAR_DB)) {
    console.error(`❌ solar.db not found: ${SOLAR_DB}`);
    process.exit(1);
  }

  // 读取 stats-cache.json
  const statsData = JSON.parse(readFileSync(STATS_CACHE, "utf-8")) as StatsCache;

  // 打开数据库
  const db = new Database(SOLAR_DB);

  // 创建 activity 查找表
  const activityMap = new Map<string, { messages: number; sessions: number; tools: number }>();
  for (const day of statsData.dailyActivity) {
    activityMap.set(day.date, {
      messages: day.messageCount,
      sessions: day.sessionCount,
      tools: day.toolCallCount
    });
  }

  // 使用事务批量插入
  const insertStmt = db.prepare(`
    INSERT INTO sys_claude_usage
    (date, model, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
     message_count, session_count, tool_call_count, synced_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ON CONFLICT(date, model) DO UPDATE SET
      input_tokens = excluded.input_tokens,
      output_tokens = excluded.output_tokens,
      cache_read_tokens = excluded.cache_read_tokens,
      cache_creation_tokens = excluded.cache_creation_tokens,
      message_count = excluded.message_count,
      session_count = excluded.session_count,
      tool_call_count = excluded.tool_call_count,
      synced_at = datetime('now')
  `);

  let insertedCount = 0;
  let updatedCount = 0;

  // 从 modelUsage 获取总计数据（按模型聚合）
  const modelTotals: Record<string, { input: number; output: number; cacheRead: number; cacheCreate: number }> = {};
  for (const [model, usage] of Object.entries(statsData.modelUsage)) {
    modelTotals[model] = {
      input: usage.inputTokens,
      output: usage.outputTokens,
      cacheRead: usage.cacheReadInputTokens,
      cacheCreate: usage.cacheCreationInputTokens
    };
  }

  // 插入每日数据
  db.transaction(() => {
    for (const dayData of statsData.dailyModelTokens) {
      const activity = activityMap.get(dayData.date) || { messages: 0, sessions: 0, tools: 0 };

      for (const [model, tokens] of Object.entries(dayData.tokensByModel)) {
        // dailyModelTokens 只记录了总 tokens，无法区分 input/output
        // 我们需要从 modelUsage 按比例分配
        const total = modelTotals[model];
        if (total) {
          const totalTokens = total.input + total.output;
          const inputRatio = totalTokens > 0 ? total.input / totalTokens : 0.5;
          const outputRatio = totalTokens > 0 ? total.output / totalTokens : 0.5;

          const estimatedInput = Math.round(tokens * inputRatio);
          const estimatedOutput = Math.round(tokens * outputRatio);

          // 按比例分配 cache tokens (基于每日 tokens 占总量的比例)
          const dayRatio = totalTokens > 0 ? tokens / totalTokens : 0;
          const estimatedCacheRead = Math.round(total.cacheRead * dayRatio);
          const estimatedCacheCreate = Math.round(total.cacheCreate * dayRatio);

          try {
            insertStmt.run(
              dayData.date,
              model,
              estimatedInput,
              estimatedOutput,
              estimatedCacheRead,
              estimatedCacheCreate,
              activity.messages,
              activity.sessions,
              activity.tools
            );
            insertedCount++;
          } catch (e) {
            updatedCount++;
          }
        }
      }
    }
  })();

  db.close();

  console.log(`✅ Claude usage synced to solar.db`);
  console.log(`   📊 Records: ${insertedCount} inserted/updated`);
  console.log(`   📅 Date range: ${statsData.dailyModelTokens[0]?.date} ~ ${statsData.lastComputedDate}`);
  console.log(`   🤖 Models: ${Object.keys(statsData.modelUsage).join(", ")}`);

  // 输出汇总统计
  console.log(`\n📈 Total Usage Summary:`);
  for (const [model, usage] of Object.entries(statsData.modelUsage)) {
    const shortName = model.replace("claude-", "").replace("-20251101", "").replace("-20250929", "");
    console.log(`   ${shortName}: ${(usage.inputTokens/1000000).toFixed(2)}M in + ${(usage.outputTokens/1000000).toFixed(2)}M out`);
    if (usage.cacheReadInputTokens > 0) {
      console.log(`      Cache: ${(usage.cacheReadInputTokens/1000000000).toFixed(2)}B read + ${(usage.cacheCreationInputTokens/1000000000).toFixed(2)}B create`);
    }
  }
}

// 命令行执行
const force = process.argv.includes("--force");
syncClaudeUsage(force);
