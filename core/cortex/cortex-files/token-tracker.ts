#!/usr/bin/env bun
/**
 * Token Tracker for Cortex Files
 *
 * 追踪各区块的 token 使用情况，生成统计报告
 * 参考 Letta 的 Context Window Overview 实现
 *
 * Usage:
 *   bun token-tracker.ts stats    # 显示统计
 *   bun token-tracker.ts report   # 生成报告
 *   bun token-tracker.ts watch    # 持续监控
 */

import { homedir } from "os";
import { readdirSync, readFileSync, existsSync, writeFileSync } from "fs";
import { join } from "path";
import { Database } from "bun:sqlite";

const DB_PATH = `${homedir()}/.solar/solar.db`;
const CORTEX_ROOT = `${homedir()}/.solar/cortex`;

// ============================================================
// Types
// ============================================================

interface TokenStats {
  total: number;
  byType: Record<string, number>;
  byDirectory: Record<string, number>;
  topFiles: Array<{ path: string; tokens: number; type: string }>;
  utilization: number;
  recommendations: string[];
}

interface TokenHistory {
  date: string;
  total: number;
  byType: Record<string, number>;
}

// ============================================================
// Token Counting
// ============================================================

/**
 * 估算 token 数量
 * 中文约 1.5 字/token，英文约 4 字符/token
 */
export function countTokens(text: string): number {
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
  const otherChars = text.length - chineseChars;
  return Math.ceil(chineseChars / 1.5 + otherChars / 4);
}

/**
 * 计算 token 分布
 */
export function analyzeTokenDistribution(): TokenStats {
  const stats: TokenStats = {
    total: 0,
    byType: {
      system: 0,
      reference: 0,
      entity: 0,
      artifact: 0,
      memory: 0,
    },
    byDirectory: {},
    topFiles: [],
    utilization: 0,
    recommendations: [],
  };

  const dirTypeMap: Record<string, string> = {
    system: "system",
    "knowledge/research": "reference",
    "knowledge/architecture": "reference",
    "knowledge/patterns": "reference",
    "knowledge/lessons": "reference",
    "knowledge/entities/technologies": "entity",
    "knowledge/entities/people": "entity",
    "knowledge/entities/concepts": "entity",
    artifacts: "artifact",
    "artifacts/insights": "artifact",
    "artifacts/reviews": "artifact",
    "artifacts/benchmarks": "artifact",
    memory: "memory",
    "memory/episodic": "memory",
    "memory/semantic": "memory",
  };

  // 遍历目录
  for (const [dir, type] of Object.entries(dirTypeMap)) {
    const fullPath = join(CORTEX_ROOT, dir);
    if (!existsSync(fullPath)) continue;

    const files = readdirSync(fullPath).filter((f) => f.endsWith(".md"));

    for (const file of files) {
      const filePath = join(fullPath, file);
      const content = readFileSync(filePath, "utf-8");

      // 解析 frontmatter
      const frontmatter = parseFrontmatter(content);
      const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");

      const tokens = countTokens(body);
      stats.total += tokens;
      stats.byType[type] = (stats.byType[type] || 0) + tokens;
      stats.byDirectory[dir] = (stats.byDirectory[dir] || 0) + tokens;

      stats.topFiles.push({
        path: join(dir, file),
        tokens,
        type,
      });
    }
  }

  // 计算利用率
  const contextWindow = 200000; // 200K 安全边界
  stats.utilization = (stats.total / contextWindow) * 100;

  // 排序 top files
  stats.topFiles.sort((a, b) => b.tokens - a.tokens);
  stats.topFiles = stats.topFiles.slice(0, 20);

  // 生成建议
  if (stats.utilization > 80) {
    stats.recommendations.push("🔴 Context utilization > 80%, need summarization");
    stats.recommendations.push(
      `   Consider summarizing top files: ${stats.topFiles
        .slice(0, 3)
        .map((f) => f.path.split("/").pop())
        .join(", ")}`
    );
  } else if (stats.utilization > 60) {
    stats.recommendations.push("🟡 Context utilization > 60%, monitor closely");
  }

  if (stats.byType.reference > stats.total * 0.7) {
    stats.recommendations.push("📚 References dominate (>70%), consider filtering by credibility");
  }

  return stats;
}

// ============================================================
// Frontmatter Parser
// ============================================================

function parseFrontmatter(content: string): Record<string, any> {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};

  const frontmatter: Record<string, any> = {};
  const lines = match[1].split("\n");

  for (const line of lines) {
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;

    const key = line.slice(0, colonIdx).trim();
    let value: any = line.slice(colonIdx + 1).trim();

    if (value === "true") value = true;
    else if (value === "false") value = false;
    else if (/^\d+$/.test(value)) value = parseInt(value);
    else if (/^\[.*\]$/.test(value)) {
      value = value
        .slice(1, -1)
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""));
    } else {
      value = value.replace(/^["']|["']$/g, "");
    }

    frontmatter[key] = value;
  }

  return frontmatter;
}

// ============================================================
// History Tracking (SQLite)
// ============================================================

function ensureHistoryTable(db: Database) {
  db.run(`
    CREATE TABLE IF NOT EXISTS cortex_token_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL,
      total_tokens INTEGER NOT NULL,
      system_tokens INTEGER DEFAULT 0,
      reference_tokens INTEGER DEFAULT 0,
      entity_tokens INTEGER DEFAULT 0,
      artifact_tokens INTEGER DEFAULT 0,
      memory_tokens INTEGER DEFAULT 0,
      utilization REAL DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // 创建索引
  db.run(`
    CREATE INDEX IF NOT EXISTS idx_token_history_date
    ON cortex_token_history(date)
  `);
}

export function recordHistory(stats: TokenStats): void {
  const db = new Database(DB_PATH);
  ensureHistoryTable(db);

  const today = new Date().toISOString().split("T")[0];

  // 检查今天是否已记录
  const existing = db
    .query<{ cnt: number }, []>(
      "SELECT COUNT(*) as cnt FROM cortex_token_history WHERE date = ?"
    )
    .get(today);

  if (existing && existing.cnt > 0) {
    // 更新
    db.run(
      `
      UPDATE cortex_token_history SET
        total_tokens = ?,
        system_tokens = ?,
        reference_tokens = ?,
        entity_tokens = ?,
        artifact_tokens = ?,
        memory_tokens = ?,
        utilization = ?
      WHERE date = ?
    `,
      stats.total,
      stats.byType.system || 0,
      stats.byType.reference || 0,
      stats.byType.entity || 0,
      stats.byType.artifact || 0,
      stats.byType.memory || 0,
      stats.utilization,
      today
    );
  } else {
    // 插入
    db.run(
      `
      INSERT INTO cortex_token_history
      (date, total_tokens, system_tokens, reference_tokens, entity_tokens, artifact_tokens, memory_tokens, utilization)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `,
      today,
      stats.total,
      stats.byType.system || 0,
      stats.byType.reference || 0,
      stats.byType.entity || 0,
      stats.byType.artifact || 0,
      stats.byType.memory || 0,
      stats.utilization
    );
  }

  db.close();
}

export function getHistory(days: number = 30): TokenHistory[] {
  const db = new Database(DB_PATH);
  ensureHistoryTable(db);

  const rows = db
    .query<
      {
        date: string;
        total_tokens: number;
        system_tokens: number;
        reference_tokens: number;
        entity_tokens: number;
        artifact_tokens: number;
        memory_tokens: number;
      },
      []
    >(
      `
    SELECT date, total_tokens, system_tokens, reference_tokens, entity_tokens, artifact_tokens, memory_tokens
    FROM cortex_token_history
    ORDER BY date DESC
    LIMIT ?
  `
    )
    .all(days);

  db.close();

  return rows.map((row) => ({
    date: row.date,
    total: row.total_tokens,
    byType: {
      system: row.system_tokens,
      reference: row.reference_tokens,
      entity: row.entity_tokens,
      artifact: row.artifact_tokens,
      memory: row.memory_tokens,
    },
  }));
}

// ============================================================
// Report Generation
// ============================================================

export function generateTokenReport(): string {
  const stats = analyzeTokenDistribution();

  let report = `# Token Usage Report

> Generated: ${new Date().toISOString()}

## Overview

| Metric | Value |
|--------|-------|
| **Total Tokens** | ${stats.total.toLocaleString()} |
| **Context Window** | 200,000 |
| **Utilization** | ${stats.utilization.toFixed(1)}% |

## By Type

| Type | Tokens | % of Total |
|------|--------|------------|
`;

  for (const [type, tokens] of Object.entries(stats.byType)) {
    if (tokens > 0) {
      const pct = ((tokens / stats.total) * 100).toFixed(1);
      report += `| ${type} | ${tokens.toLocaleString()} | ${pct}% |\n`;
    }
  }

  report += `
## By Directory

| Directory | Tokens |
|-----------|--------|
`;

  const sortedDirs = Object.entries(stats.byDirectory)
    .filter(([, tokens]) => tokens > 0)
    .sort((a, b) => b[1] - a[1]);

  for (const [dir, tokens] of sortedDirs) {
    report += `| ${dir} | ${tokens.toLocaleString()} |\n`;
  }

  report += `
## Top 10 Files

| File | Tokens | Type |
|------|--------|------|
`;

  for (const file of stats.topFiles.slice(0, 10)) {
    const shortPath = file.path.split("/").slice(-2).join("/");
    report += `| ${shortPath} | ${file.tokens.toLocaleString()} | ${file.type} |\n`;
  }

  if (stats.recommendations.length > 0) {
    report += `
## Recommendations

${stats.recommendations.map((r) => `- ${r}`).join("\n")}
`;
  }

  return report;
}

// ============================================================
// CLI
// ============================================================

function printStats(stats: TokenStats) {
  console.log("\n📊 Token Usage Statistics\n");
  console.log("┌─────────────────────────────────────────────────────────────┐");
  console.log(`│ Total Tokens: ${stats.total.toLocaleString().padStart(10)}                        │`);
  console.log(`│ Utilization:  ${stats.utilization.toFixed(1).padStart(10)}% of 200K              │`);
  console.log("└─────────────────────────────────────────────────────────────┘");

  console.log("\n📈 By Type:");
  console.log("┌─────────────────┬─────────────┬────────────┐");
  console.log("│ Type            │ Tokens      │ % of Total │");
  console.log("├─────────────────┼─────────────┼────────────┤");

  for (const [type, tokens] of Object.entries(stats.byType)) {
    if (tokens > 0) {
      const pct = ((tokens / stats.total) * 100).toFixed(1);
      console.log(
        `│ ${type.padEnd(15)} │ ${String(tokens.toLocaleString()).padStart(9)} │ ${pct.padStart(9)}% │`
      );
    }
  }

  console.log("└─────────────────┴─────────────┴────────────┘");

  if (stats.recommendations.length > 0) {
    console.log("\n💡 Recommendations:");
    for (const rec of stats.recommendations) {
      console.log(`   ${rec}`);
    }
  }
}

function printHistory(history: TokenHistory[]) {
  if (history.length === 0) {
    console.log("\n📊 No history data available\n");
    return;
  }

  console.log("\n📈 Token History (Last 7 days):\n");
  console.log("┌────────────┬───────────┬────────────┐");
  console.log("│ Date       │ Tokens    │ Change     │");
  console.log("├────────────┼───────────┼────────────┤");

  for (let i = 0; i < Math.min(7, history.length); i++) {
    const h = history[i];
    const prev = history[i + 1];
    const change = prev ? ((h.total - prev.total) / prev.total) * 100 : 0;
    const changeStr = change >= 0 ? `+${change.toFixed(1)}%` : `${change.toFixed(1)}%`;

    console.log(
      `│ ${h.date} │ ${String(h.total.toLocaleString()).padStart(7)} │ ${changeStr.padStart(10)} │`
    );
  }

  console.log("└────────────┴───────────┴────────────┘");
}

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "stats";

  switch (command) {
    case "stats":
      const stats = analyzeTokenDistribution();
      printStats(stats);

      // 记录历史
      recordHistory(stats);
      console.log("\n✓ History recorded");
      break;

    case "history":
      const history = getHistory(30);
      printHistory(history);
      break;

    case "report":
      const report = generateTokenReport();
      const reportPath = join(CORTEX_ROOT, "stats", "TOKEN_REPORT.md");
      writeFileSync(reportPath, report, "utf-8");
      console.log(`\n📄 Report saved to: ${reportPath}\n`);
      console.log(report);
      break;

    case "watch":
      console.log("\n👀 Watching for changes... (Press Ctrl+C to stop)\n");
      let lastTotal = 0;

      setInterval(() => {
        const stats = analyzeTokenDistribution();
        if (stats.total !== lastTotal) {
          const diff = stats.total - lastTotal;
          const sign = diff >= 0 ? "+" : "";
          console.log(
            `[${new Date().toLocaleTimeString()}] Tokens: ${stats.total.toLocaleString()} (${sign}${diff.toLocaleString()})`
          );
          lastTotal = stats.total;
        }
      }, 5000);
      break;

    default:
      console.log(`
Usage:
  bun token-tracker.ts stats    # 显示统计 (并记录历史)
  bun token-tracker.ts history  # 查看历史
  bun token-tracker.ts report   # 生成报告文件
  bun token-tracker.ts watch    # 持续监控
      `);
  }
}

main();
