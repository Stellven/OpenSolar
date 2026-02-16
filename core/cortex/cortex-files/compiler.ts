#!/usr/bin/env bun
/**
 * Cortex Files Compiler
 *
 * 参考 Letta 的 Memory.compile() 实现
 * 将内存块渲染成 LLM 友好的 XML 格式
 *
 * Usage:
 *   bun compiler.ts compile  # 编译所有块
 *   bun compiler.ts overview # 显示 token 概览
 */

import { readdirSync, readFileSync, statSync, existsSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const CORTEX_ROOT = `${homedir()}/.solar/cortex`;

// ============================================================
// Types
// ============================================================

interface MemoryBlock {
  id: string;
  label: string;
  type: "system" | "reference" | "entity" | "artifact" | "memory";
  value: string;
  limit: number;
  read_only: boolean;
  description: string;
  importance: number;
  file_path: string;
}

interface ContextOverview {
  system: number;
  references: number;
  entities: number;
  artifacts: number;
  memory: number;
  total: number;
}

// ============================================================
// Token Counting (简化版 - 约 4 字符 = 1 token)
// ============================================================

function countTokens(text: string): number {
  // 简化估算: 中文约 1.5 字/token, 英文约 4 字符/token
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
  const otherChars = text.length - chineseChars;
  return Math.ceil(chineseChars / 1.5 + otherChars / 4);
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

    // 解析类型
    if (value === "true") value = true;
    else if (value === "false") value = false;
    else if (/^\d+$/.test(value)) value = parseInt(value);
    else if (/^\[.*\]$/.test(value)) {
      // 数组
      value = value
        .slice(1, -1)
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""));
    } else {
      // 字符串，去掉引号
      value = value.replace(/^["']|["']$/g, "");
    }

    frontmatter[key] = value;
  }

  return frontmatter;
}

// ============================================================
// Load Memory Blocks
// ============================================================

function loadBlocks(): MemoryBlock[] {
  const blocks: MemoryBlock[] = [];

  const dirs = [
    { path: "system", type: "system" as const },
    { path: "knowledge/research", type: "reference" as const },
    { path: "knowledge/architecture", type: "reference" as const },
    { path: "knowledge/patterns", type: "reference" as const },
    { path: "knowledge/lessons", type: "reference" as const },
    { path: "knowledge/entities/technologies", type: "entity" as const },
    { path: "knowledge/entities/people", type: "entity" as const },
    { path: "knowledge/entities/concepts", type: "entity" as const },
    { path: "artifacts", type: "artifact" as const },
    { path: "memory", type: "memory" as const },
  ];

  for (const dir of dirs) {
    const fullPath = join(CORTEX_ROOT, dir.path);
    if (!existsSync(fullPath)) continue;

    const files = readdirSync(fullPath).filter((f) => f.endsWith(".md"));

    for (const file of files) {
      const filePath = join(fullPath, file);
      const content = readFileSync(filePath, "utf-8");
      const frontmatter = parseFrontmatter(content);

      // 提取正文 (去掉 frontmatter)
      const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");

      blocks.push({
        id: frontmatter.id || file,
        label: frontmatter.title || file.replace(".md", ""),
        type: dir.type,
        value: body.trim(),
        limit: frontmatter.limit || 2000,
        read_only: frontmatter.read_only || false,
        description: frontmatter.description || "",
        importance: frontmatter.importance || frontmatter.credibility || 0.5,
        file_path: filePath,
      });
    }
  }

  // 按重要性排序
  blocks.sort((a, b) => b.importance - a.importance);

  return blocks;
}

// ============================================================
// Compile (Letta-style)
// ============================================================

function compile(
  blocks: MemoryBlock[],
  options: {
    label?: string;
    includeSystem?: boolean;
    maxTokens?: number;
    format?: "xml" | "markdown";
  } = {}
): string {
  const { label = "context_blocks", includeSystem = true, maxTokens = 0, format = "xml" } = options;

  let totalTokens = 0;
  let result = `<${label}>\n`;
  let lineNum = 1;

  // 1. 系统块优先 (始终包含)
  const systemBlocks = blocks.filter((b) => b.type === "system");
  for (const block of systemBlocks) {
    if (!includeSystem && block.type === "system") continue;

    const blockStr = formatBlock(block, lineNum, format);
    const blockTokens = countTokens(blockStr);

    if (maxTokens > 0 && totalTokens + blockTokens > maxTokens) break;

    result += blockStr;
    lineNum += blockStr.split("\n").length;
    totalTokens += blockTokens;
  }

  // 2. 按重要性排序的其他块
  const otherBlocks = blocks.filter((b) => b.type !== "system");
  for (const block of otherBlocks) {
    const blockStr = formatBlock(block, lineNum, format);
    const blockTokens = countTokens(blockStr);

    if (maxTokens > 0 && totalTokens + blockTokens > maxTokens) {
      // 超出限制，尝试摘要
      if (block.description) {
        const summaryStr = formatSummaryBlock(block, lineNum, format);
        const summaryTokens = countTokens(summaryStr);
        if (totalTokens + summaryTokens <= maxTokens) {
          result += summaryStr;
          lineNum += summaryStr.split("\n").length;
          totalTokens += summaryTokens;
        }
      }
      break;
    }

    result += blockStr;
    lineNum += blockStr.split("\n").length;
    totalTokens += blockTokens;
  }

  result += `</${label}>`;

  return result;
}

function formatBlock(block: MemoryBlock, lineNum: number, format: string): string {
  if (format === "markdown") {
    return `## [${block.label}] (line ${lineNum}, limit ${block.limit}${block.read_only ? ", READ-ONLY" : ""})\n\n${block.value}\n\n---\n\n`;
  }

  // XML format (default)
  let meta = `label="${block.label}" line="${lineNum}" limit="${block.limit}"`;
  if (block.read_only) meta += ' read_only="true"';
  const importance = typeof block.importance === 'number' ? block.importance : parseFloat(block.importance) || 0.5;
  if (importance >= 0.8) meta += ` importance="${importance.toFixed(2)}"`;

  return `<block ${meta}>\n${block.value}\n</block>\n\n`;
}

function formatSummaryBlock(block: MemoryBlock, lineNum: number, format: string): string {
  if (format === "markdown") {
    return `## [${block.label}] (SUMMARY, line ${lineNum})\n\n${block.description}\n\n---\n\n`;
  }

  return `<block label="${block.label}" line="${lineNum}" summary="true">\n${block.description}\n</block>\n\n`;
}

// ============================================================
// Context Overview (Token Tracking)
// ============================================================

function getOverview(blocks: MemoryBlock[]): ContextOverview {
  const overview: ContextOverview = {
    system: 0,
    references: 0,
    entities: 0,
    artifacts: 0,
    memory: 0,
    total: 0,
  };

  for (const block of blocks) {
    const tokens = countTokens(block.value);
    overview.total += tokens;

    switch (block.type) {
      case "system":
        overview.system += tokens;
        break;
      case "reference":
        overview.references += tokens;
        break;
      case "entity":
        overview.entities += tokens;
        break;
      case "artifact":
        overview.artifacts += tokens;
        break;
      case "memory":
        overview.memory += tokens;
        break;
    }
  }

  return overview;
}

// ============================================================
// CLI
// ============================================================

function printOverview(overview: ContextOverview) {
  console.log("\n📊 Context Window Overview\n");
  console.log("┌─────────────────┬─────────────┬────────────┐");
  console.log("│ Section         │ Tokens      │ % of Total │");
  console.log("├─────────────────┼─────────────┼────────────┤");

  const sections = [
    ["System", overview.system],
    ["References", overview.references],
    ["Entities", overview.entities],
    ["Artifacts", overview.artifacts],
    ["Memory", overview.memory],
  ];

  for (const [name, tokens] of sections) {
    const pct = ((tokens / overview.total) * 100).toFixed(1);
    console.log(`│ ${name.padEnd(15)} │ ${String(tokens).padStart(9)} │ ${pct.padStart(9)}% │`);
  }

  console.log("├─────────────────┼─────────────┼────────────┤");
  console.log(`│ ${"Total".padEnd(15)} │ ${String(overview.total).padStart(9)} │ ${"100.0".padStart(9)}% │`);
  console.log("└─────────────────┴─────────────┴────────────┘");

  // 估算可用的上下文
  const contextWindow = 200000; // Gemini 1M, 留 200K 安全边界
  const utilization = ((overview.total / contextWindow) * 100).toFixed(1);
  console.log(`\n📈 Utilization: ${utilization}% of 200K context window`);

  if (overview.total > contextWindow * 0.7) {
    console.log("⚠️  Warning: Context utilization > 70%, consider summarization");
  }
}

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "overview";

  const blocks = loadBlocks();

  switch (command) {
    case "compile":
      const format = args.includes("--markdown") ? "markdown" : "xml";
      const maxTokens = args.includes("--max")
        ? parseInt(args[args.indexOf("--max") + 1])
        : 0;

      const compiled = compile(blocks, { format, maxTokens });
      console.log(compiled);
      console.error(`\n# Stats: ${blocks.length} blocks, ${countTokens(compiled)} tokens`);
      break;

    case "overview":
      printOverview(getOverview(blocks));
      break;

    case "blocks":
      console.log("\n📚 Loaded Blocks:\n");
      for (const block of blocks.slice(0, 20)) {
        const tokens = countTokens(block.value);
        const readOnly = block.read_only ? "🔒" : "  ";
        console.log(
          `${readOnly} [${block.type.padEnd(8)}] ${block.label.padEnd(30)} ${String(tokens).padStart(5)} tokens`
        );
      }
      if (blocks.length > 20) {
        console.log(`\n... and ${blocks.length - 20} more blocks`);
      }
      break;

    default:
      console.log(`
Usage:
  bun compiler.ts compile    # 编译所有块为 XML
  bun compiler.ts compile --markdown  # Markdown 格式
  bun compiler.ts compile --max 50000 # 限制 50K tokens
  bun compiler.ts overview   # 显示 token 概览
  bun compiler.ts blocks     # 列出所有块
      `);
  }
}

main();
