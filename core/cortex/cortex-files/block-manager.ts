#!/usr/bin/env bun
/**
 * Block Manager - Memory Block 管理器
 *
 * 灵感来源: Letta Memory Blocks
 * 核心概念: 标签化的上下文区块，可编译成 Prompt
 *
 * Usage:
 *   bun block-manager.ts compile        # 编译所有 Block 为 Prompt
 *   bun block-manager.ts list           # 列出所有 Block
 *   bun block-manager.ts get <label>    # 获取指定 Block
 *   bun block-manager.ts update <label> # 更新 Block
 */

import { homedir } from "os";
import { join } from "path";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "fs";

const BLOCKS_DIR = `${homedir()}/.solar/memory/blocks`;

// ============================================================
// Types
// ============================================================

export interface MemoryBlock {
  label: string;
  value: string;
  limit: number;
  read_only: boolean;
  description: string;
  priority: number;
  updated_at: string;
}

export interface CompiledMemory {
  total_chars: number;
  blocks: MemoryBlock[];
  prompt: string;
}

// ============================================================
// Block Operations
// ============================================================

/**
 * 加载所有 Block
 */
export function loadBlocks(): MemoryBlock[] {
  if (!existsSync(BLOCKS_DIR)) {
    return [];
  }

  const blocks: MemoryBlock[] = [];
  const files = readdirSync(BLOCKS_DIR).filter((f) => f.endsWith(".json"));

  for (const file of files) {
    try {
      const content = readFileSync(join(BLOCKS_DIR, file), "utf-8");
      const block = JSON.parse(content) as MemoryBlock;
      blocks.push(block);
    } catch (e) {
      console.error(`Failed to load block: ${file}`);
    }
  }

  // 按 priority 排序
  return blocks.sort((a, b) => a.priority - b.priority);
}

/**
 * 获取指定 Block
 */
export function getBlock(label: string): MemoryBlock | null {
  const blocks = loadBlocks();
  return blocks.find((b) => b.label === label) || null;
}

/**
 * 更新 Block
 */
export function updateBlock(label: string, value: string): boolean {
  const block = getBlock(label);

  if (!block) {
    console.error(`Block not found: ${label}`);
    return false;
  }

  if (block.read_only) {
    console.error(`Block is read-only: ${label}`);
    return false;
  }

  // 检查长度限制
  if (value.length > block.limit) {
    console.error(`Value exceeds limit (${value.length} > ${block.limit})`);
    return false;
  }

  block.value = value;
  block.updated_at = new Date().toISOString().split("T")[0];

  const filePath = join(BLOCKS_DIR, `${label}.json`);
  writeFileSync(filePath, JSON.stringify(block, null, 2), "utf-8");

  return true;
}

/**
 * 编译所有 Block 为 Prompt (类似 Letta Memory.compile())
 */
export function compileBlocks(maxChars?: number): CompiledMemory {
  const blocks = loadBlocks();
  let totalChars = 0;

  const lines: string[] = [];
  lines.push("═══════════════════════════════════════════════════════════════");
  lines.push("                    SOLAR MEMORY BLOCKS");
  lines.push("═══════════════════════════════════════════════════════════════");
  lines.push("");

  for (const block of blocks) {
    // 检查是否超过限制
    if (maxChars && totalChars + block.value.length > maxChars) {
      // 截断处理
      const remaining = maxChars - totalChars;
      if (remaining > 100) {
        lines.push(`┌─ ${block.label.toUpperCase()} ─────────────────────────────┐`);
        lines.push(`│ ${block.value.slice(0, remaining - 50)}...`);
        lines.push(`└${"─".repeat(60)}┘`);
        lines.push("");
        totalChars += remaining;
      }
      break;
    }

    lines.push(`┌─ ${block.label.toUpperCase()} ─────────────────────────────┐`);

    // 按 limit 截断
    let value = block.value;
    if (value.length > block.limit) {
      value = value.slice(0, block.limit - 20) + "...";
    }

    // 添加前缀
    for (const line of value.split("\n")) {
      lines.push(`│ ${line}`);
    }

    lines.push(`└${"─".repeat(60)}┘`);
    lines.push("");

    totalChars += block.value.length;
  }

  lines.push("═══════════════════════════════════════════════════════════════");

  return {
    total_chars: totalChars,
    blocks,
    prompt: lines.join("\n"),
  };
}

/**
 * 获取 Block 统计
 */
export function getBlockStats(): {
  count: number;
  total_chars: number;
  total_limit: number;
  utilization: number;
} {
  const blocks = loadBlocks();

  const totalChars = blocks.reduce((sum, b) => sum + b.value.length, 0);
  const totalLimit = blocks.reduce((sum, b) => sum + b.limit, 0);

  return {
    count: blocks.length,
    total_chars: totalChars,
    total_limit: totalLimit,
    utilization: Math.round((totalChars / totalLimit) * 100),
  };
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "help";

  switch (command) {
    case "compile": {
      const maxChars = args[1] ? parseInt(args[1]) : undefined;
      const compiled = compileBlocks(maxChars);
      console.log(compiled.prompt);
      console.log(`\n📊 Total: ${compiled.total_chars} chars`);
      break;
    }

    case "list": {
      const blocks = loadBlocks();
      console.log("\n📦 Memory Blocks\n");

      for (const block of blocks) {
        const ro = block.read_only ? "🔒" : "✏️";
        const util = Math.round((block.value.length / block.limit) * 100);
        console.log(`  ${ro} ${block.label.padEnd(12)} ${block.value.length}/${block.limit} (${util}%)`);
        console.log(`     ${block.description}`);
      }

      const stats = getBlockStats();
      console.log(`\n  📊 总计: ${stats.count} blocks, ${stats.total_chars}/${stats.total_limit} chars (${stats.utilization}%)`);
      break;
    }

    case "get": {
      const label = args[1];
      if (!label) {
        console.error("Usage: bun block-manager.ts get <label>");
        process.exit(1);
      }

      const block = getBlock(label);
      if (block) {
        console.log(`\n📦 Block: ${label}\n`);
        console.log(block.value);
        console.log(`\n📊 ${block.value.length}/${block.limit} chars`);
      } else {
        console.error(`Block not found: ${label}`);
      }
      break;
    }

    case "stats": {
      const stats = getBlockStats();
      console.log("\n📊 Memory Block Stats\n");
      console.log(`  Blocks:    ${stats.count}`);
      console.log(`  Total:     ${stats.total_chars} chars`);
      console.log(`  Limit:     ${stats.total_limit} chars`);
      console.log(`  Utilization: ${stats.utilization}%`);
      break;
    }

    case "help":
    default:
      console.log(`
Block Manager - Memory Block 管理器

用法:
  bun block-manager.ts compile [max]  # 编译为 Prompt
  bun block-manager.ts list           # 列出所有 Block
  bun block-manager.ts get <label>    # 获取 Block 内容
  bun block-manager.ts stats          # 显示统计

Block 文件位置:
  ~/.solar/memory/blocks/*.json

灵感来源: Letta Memory Blocks
      `);
  }
}

if (import.meta.main) {
  main();
}

// Functions are already exported above
