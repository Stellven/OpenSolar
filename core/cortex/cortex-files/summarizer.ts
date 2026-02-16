#!/usr/bin/env bun
/**
 * Cortex Files Summarizer
 *
 * 参考 Letta 的 Summarization 策略实现
 * 两种模式: static_buffer / importance_eviction
 *
 * Usage:
 *   bun summarizer.ts summarize <file.md>
 *   bun summarizer.ts batch  # 批量生成摘要
 *   bun summarizer.ts stats  # 查看统计
 */

import { Database } from "bun:sqlite";
import { homedir } from "os";
import { readdirSync, readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";

const DB_PATH = `${homedir()}/.solar/solar.db`;
const CORTEX_ROOT = `${homedir()}/.solar/cortex`;

// ============================================================
// Letta-style Summary Prompts
// ============================================================

export const SUMMARY_PROMPTS = {
  // Letta 实测有效的 100 字摘要提示词
  standard: `Summarize the following content in 100 words or less.
Capture the most important details, facts, and information.
Focus on key concepts and actionable insights.

Content:
{content}

Summary (100 words or less):`,

  // 结构化摘要 (适合技术文档)
  structured: `Summarize the following technical content in 100 words or less.
Include:
- Main concept/topic
- Key technical details
- Important conclusions or recommendations

Content:
{content}

Technical Summary (100 words or less):`,

  // 中文摘要
  chinese: `请用100字以内总结以下内容。
抓住最重要的信息、事实和见解。
突出关键概念和可操作的要点。

内容:
{content}

摘要 (100字以内):`,

  // 重要性优先摘要 (用于 eviction 策略)
  importance: `Summarize the following content in 50 words or less.
Prioritize:
1. Core concepts that must be preserved
2. Key facts and numbers
3. Critical conclusions

Content:
{content}

Priority Summary (50 words or less):`,
};

// ============================================================
// Summarization Strategies
// ============================================================

export type SummaryMode = "static" | "importance" | "auto";

export interface SummaryOptions {
  mode: SummaryMode;
  promptType: keyof typeof SUMMARY_PROMPTS;
  maxLength: number;
  model: string;
}

export const DEFAULT_OPTIONS: SummaryOptions = {
  mode: "importance", // 默认使用 importanceEviction（不需要 LLM）
  promptType: "standard",
  maxLength: 100,
  model: "glm-4-flash", // 便宜的摘要模型
};

// LLM API 配置 (可选)
const LLM_API_URL = process.env.LLM_API_URL || "http://localhost:3000/api/complete";
const LLM_ENABLED = process.env.LLM_ENABLED !== "false"; // 默认尝试 LLM

/**
 * 计算摘要的触发阈值
 */
export function shouldSummarize(
  content: string,
  limit: number,
  utilization: number = 0.8
): boolean {
  const contentLength = content.length;
  // 如果内容超过 limit 的 80%，需要摘要
  return contentLength > limit * utilization;
}

/**
 * 静态缓冲区策略 - 固定 token 数摘要
 */
export async function staticBufferSummarize(
  content: string,
  options: Partial<SummaryOptions> = {}
): Promise<string> {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // 如果 LLM 未启用或不可用，使用 importanceEviction 作为 fallback
  if (!LLM_ENABLED) {
    return importanceEviction(content, 0.7, opts.maxLength * 2);
  }

  const prompt = SUMMARY_PROMPTS[opts.promptType].replace("{content}", content);

  try {
    // 调用 LLM API
    const response = await fetch(LLM_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: opts.model,
        prompt,
        max_tokens: 150, // 100字摘要约 150 tokens
      }),
    });

    if (!response.ok) {
      // Fallback: 使用 importanceEviction
      return importanceEviction(content, 0.7, opts.maxLength * 2);
    }

    const data = await response.json();
    return data.completion || importanceEviction(content, 0.7, opts.maxLength * 2);
  } catch (e) {
    // 网络错误或 API 不可用，使用 fallback
    return importanceEviction(content, 0.7, opts.maxLength * 2);
  }
}

/**
 * 重要性驱逐策略 - 保留关键信息
 */
export function importanceEviction(
  content: string,
  importance: number,
  limit: number
): string {
  // 高重要性内容保留更多
  const retentionRatio = Math.min(1, importance + 0.3);
  const targetLength = Math.floor(limit * retentionRatio);

  // 1. 提取段落
  const paragraphs = content.split(/\n\n+/);

  // 2. 按重要性评分 (简单启发式)
  const scored = paragraphs.map((p) => ({
    content: p,
    score: scoreParagraph(p),
  }));

  // 3. 排序并选择
  scored.sort((a, b) => b.score - a.score);

  let result = "";
  for (const { content: p } of scored) {
    if (result.length + p.length + 2 <= targetLength) {
      result += p + "\n\n";
    } else {
      break;
    }
  }

  return result.trim() || content.slice(0, targetLength);
}

/**
 * 段落评分启发式
 */
function scoreParagraph(p: string): number {
  let score = 0;

  // 包含数字/数据
  if (/\d+%|\d+\.\d+|\d+[KMG]?/.test(p)) score += 0.3;

  // 包含关键词
  if (/important|critical|key|核心|重要|关键/.test(p)) score += 0.2;

  // 包含结论性词语
  if (/therefore|thus|conclusion|所以|结论|因此/.test(p)) score += 0.2;

  // 长度适中 (不是太短也不是太长)
  if (p.length > 100 && p.length < 500) score += 0.1;

  // 包含列表结构
  if (/^[-*•]\s/m.test(p)) score += 0.1;

  return score;
}

/**
 * 自动选择策略
 */
export async function autoSummarize(
  content: string,
  options: Partial<SummaryOptions> & { importance?: number; limit?: number } = {}
): Promise<string> {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // 根据内容长度和重要性选择策略
  const length = content.length;
  const limit = opts.limit || 2000;
  const importance = opts.importance || 0.5;

  if (length <= limit * 0.5) {
    // 内容不长，不需要摘要
    return content;
  } else if (length <= limit && importance > 0.7) {
    // 高重要性但不太长，用 importance 策略保留更多
    return importanceEviction(content, importance, limit);
  } else {
    // 内容很长或重要性一般，用静态摘要
    return staticBufferSummarize(content, opts);
  }
}

// ============================================================
// Batch Processing
// ============================================================

interface SummaryStats {
  total: number;
  summarized: number;
  skipped: number;
  failed: number;
  tokensSaved: number;
}

export async function batchSummarize(
  dryRun: boolean = true
): Promise<SummaryStats> {
  const stats: SummaryStats = {
    total: 0,
    summarized: 0,
    skipped: 0,
    failed: 0,
    tokensSaved: 0,
  };

  // 遍历所有 .md 文件
  const dirs = [
    "knowledge/research",
    "knowledge/architecture",
    "knowledge/patterns",
    "knowledge/lessons",
    "knowledge/entities",
    "artifacts",
  ];

  for (const dir of dirs) {
    const fullPath = join(CORTEX_ROOT, dir);
    if (!existsSync(fullPath)) continue;

    const files = readdirSync(fullPath).filter((f) => f.endsWith(".md"));

    for (const file of files) {
      stats.total++;
      const filePath = join(fullPath, file);
      const content = readFileSync(filePath, "utf-8");

      // 解析 frontmatter
      const frontmatter = parseFrontmatter(content);
      const limit = frontmatter.limit || 2000;
      const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");

      if (body.length <= limit * 0.5) {
        stats.skipped++;
        continue;
      }

      // 生成摘要
      try {
        const summary = await autoSummarize(body, {
          limit,
          importance: frontmatter.importance || 0.5,
        });

        stats.tokensSaved += body.length - summary.length;
        stats.summarized++;

        if (!dryRun) {
          // 更新 frontmatter 的 description
          const newFrontmatter = {
            ...frontmatter,
            description: summary.slice(0, 100),
          };

          const newContent = generateMarkdown(newFrontmatter, body);
          writeFileSync(filePath, newContent, "utf-8");

          console.log(`✓ Summarized: ${file}`);
        } else {
          console.log(`[DRY-RUN] Would summarize: ${file}`);
        }
      } catch (e) {
        stats.failed++;
        console.error(`✗ Failed: ${file}`, e);
      }
    }
  }

  return stats;
}

// ============================================================
// Helpers
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

function generateMarkdown(
  frontmatter: Record<string, any>,
  body: string
): string {
  let fm = "---\n";
  for (const [key, value] of Object.entries(frontmatter)) {
    if (Array.isArray(value)) {
      fm += `${key}: [${value.join(", ")}]\n`;
    } else if (typeof value === "string" && value.includes(":")) {
      fm += `${key}: "${value}"\n`;
    } else {
      fm += `${key}: ${value}\n`;
    }
  }
  fm += "---\n\n";
  return fm + body;
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "stats";

  switch (command) {
    case "summarize":
      const filePath = args[1];
      if (!filePath) {
        console.error("Usage: bun summarizer.ts summarize <file.md>");
        process.exit(1);
      }

      const content = readFileSync(filePath, "utf-8");
      const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");
      const summary = await autoSummarize(body);

      console.log("\n📄 Original:", body.length, "chars");
      console.log("📝 Summary:", summary.length, "chars");
      console.log("\n---\n");
      console.log(summary);
      break;

    case "batch":
      const dryRun = !args.includes("--apply");
      console.log(dryRun ? "\n🔍 DRY-RUN MODE\n" : "\n✍️ APPLYING CHANGES\n");

      const stats = await batchSummarize(dryRun);

      console.log("\n📊 Summary Statistics:");
      console.log(`   Total files: ${stats.total}`);
      console.log(`   Summarized: ${stats.summarized}`);
      console.log(`   Skipped: ${stats.skipped}`);
      console.log(`   Failed: ${stats.failed}`);
      console.log(`   Tokens saved: ~${Math.floor(stats.tokensSaved / 4)}`);

      if (dryRun) {
        console.log("\n💡 Run with --apply to make changes");
      }
      break;

    case "stats":
      console.log("\n📊 Summarizer Configuration:");
      console.log("   Default model:", DEFAULT_OPTIONS.model);
      console.log("   Max length:", DEFAULT_OPTIONS.maxLength, "words");
      console.log("   Available prompts:", Object.keys(SUMMARY_PROMPTS).join(", "));
      break;

    case "prompts":
      console.log("\n📝 Available Summary Prompts:\n");
      for (const [name, prompt] of Object.entries(SUMMARY_PROMPTS)) {
        console.log(`--- ${name} ---`);
        console.log(prompt.slice(0, 200) + "...\n");
      }
      break;

    default:
      console.log(`
Usage:
  bun summarizer.ts summarize <file.md>  # 摘要单个文件
  bun summarizer.ts batch               # 批量生成摘要 (dry-run)
  bun summarizer.ts batch --apply       # 批量生成并应用
  bun summarizer.ts stats               # 查看配置
  bun summarizer.ts prompts             # 查看所有提示词
      `);
  }
}

main();
