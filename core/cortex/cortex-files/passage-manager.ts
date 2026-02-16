#!/usr/bin/env bun
/**
 * Passage Manager for Cortex Files
 *
 * 参考 Letta 的 passage_manager.py 实现
 * 并发生成嵌入，双写到 SQLite + Tantivy
 *
 * Usage:
 *   bun passage-manager.ts index     # 索引所有 passages
 *   bun passage-manager.ts search    # 搜索
 *   bun passage-manager.ts stats     # 查看统计
 */

import { Database } from "bun:sqlite";
import { homedir } from "os";
import { join } from "path";
import {
  readdirSync,
  readFileSync,
  existsSync,
  writeFileSync,
  mkdirSync,
} from "fs";
import { spawnSync } from "child_process";

const DB_PATH = `${homedir()}/.solar/solar.db`;
const CORTEX_ROOT = `${homedir()}/.solar/cortex`;
const TANTIVY_BIN = `${homedir()}/.claude/core/search/target/release/solar-search`;

// ============================================================
// Types
// ============================================================

interface Passage {
  passage_id: string;
  content: string;
  embedding?: number[];
  source_type: string;
  source_id: string;
  importance: number;
  created_at: string;
}

interface IndexStats {
  total_passages: number;
  indexed: number;
  failed: number;
  total_tokens: number;
  duration_ms: number;
}

// ============================================================
// Passage Extraction
// ============================================================

/**
 * 从 Markdown 文件提取 passages (段落级)
 */
function extractPassagesFromFile(
  filePath: string,
  content: string
): Passage[] {
  const passages: Passage[] = [];

  // 解析 frontmatter
  const frontmatter = parseFrontmatter(content);
  const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");

  // 提取标题
  const title = body.match(/^#\s+(.+)$/m)?.[1] || frontmatter.title || "";

  // 按段落分割
  const paragraphs = body.split(/\n\n+/).filter((p) => p.trim().length > 50);

  // 创建 passage
  for (let i = 0; i < paragraphs.length; i++) {
    const p = paragraphs[i].trim();

    // 跳过太短的段落
    if (p.length < 50) continue;

    // 计算 token
    const tokens = countTokens(p);

    passages.push({
      passage_id: `${frontmatter.id || filePath}-${i}`,
      content: p,
      source_type: frontmatter.type || "unknown",
      source_id: frontmatter.id || filePath,
      importance: frontmatter.importance || frontmatter.credibility || 0.5,
      created_at: frontmatter.created || new Date().toISOString().split("T")[0],
    });
  }

  // 如果没有段落，创建一个整体 passage
  if (passages.length === 0 && body.trim().length > 50) {
    passages.push({
      passage_id: frontmatter.id || filePath,
      content: body.trim(),
      source_type: frontmatter.type || "unknown",
      source_id: frontmatter.id || filePath,
      importance: frontmatter.importance || frontmatter.credibility || 0.5,
      created_at: frontmatter.created || new Date().toISOString().split("T")[0],
    });
  }

  return passages;
}

// ============================================================
// Concurrent Embedding Generation (Letta-style)
// ============================================================

/**
 * 并发生成嵌入
 * 参考 Letta: await asyncio.gather(*[embedding_func(msg.content) for msg in messages])
 */
async function generateEmbeddingsConcurrent(
  passages: Passage[],
  concurrency: number = 5
): Promise<Map<string, number[]>> {
  const embeddings = new Map<string, number[]>();

  // 分批处理
  for (let i = 0; i < passages.length; i += concurrency) {
    const batch = passages.slice(i, i + concurrency);

    // 并发生成
    const results = await Promise.all(
      batch.map(async (p) => {
        try {
          const embedding = await generateEmbedding(p.content);
          return { id: p.passage_id, embedding };
        } catch (e) {
          console.error(`   ✗ Failed to embed ${p.passage_id}: ${e}`);
          return { id: p.passage_id, embedding: null };
        }
      })
    );

    // 收集结果
    for (const { id, embedding } of results) {
      if (embedding) {
        embeddings.set(id, embedding);
      }
    }

    // 显示进度
    process.stdout.write(
      `\r   📊 嵌入进度: ${Math.min(i + concurrency, passages.length)}/${passages.length}`
    );
  }

  console.log(); // 换行
  return embeddings;
}

/**
 * 生成单个嵌入向量
 * 调用本地嵌入服务或 API
 */
async function generateEmbedding(text: string): Promise<number[] | null> {
  try {
    // 方法1: 调用本地嵌入服务 (如果可用)
    // const response = await fetch("http://localhost:8080/embed", {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify({ text }),
    // });
    // return (await response.json()).embedding;

    // 方法2: 使用简单的哈希作为伪嵌入 (演示用)
    // 实际使用时替换为真实嵌入服务
    const hash = simpleHash(text);
    const embedding = new Array(128).fill(0);
    for (let i = 0; i < Math.min(hash.length, 128); i++) {
      embedding[i] = (hash.charCodeAt(i) % 1000) / 1000;
    }
    return embedding;
  } catch (e) {
    return null;
  }
}

function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}

// ============================================================
// Dual-Write Strategy (SQLite + Tantivy)
// ============================================================

/**
 * 双写 passages 到 SQLite 和 Tantivy
 * 参考 Letta: self.db.add(passage); self.vector_db.upsert(passage)
 */
async function dualWritePassages(
  passages: Passage[],
  embeddings: Map<string, number[]>
): Promise<{ sqlite: number; tantivy: number }> {
  const result = { sqlite: 0, tantivy: 0 };

  // 1. 写入 SQLite
  const db = new Database(DB_PATH);

  // 确保 passages 表存在
  db.run(`
    CREATE TABLE IF NOT EXISTS cortex_passages (
      passage_id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      source_type TEXT,
      source_id TEXT,
      importance REAL DEFAULT 0.5,
      tokens INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      indexed_at DATETIME
    )
  `);

  // 创建索引
  db.run(`
    CREATE INDEX IF NOT EXISTS idx_passages_source
    ON cortex_passages(source_type, source_id)
  `);

  // 准备语句
  const insertStmt = db.prepare(`
    INSERT OR REPLACE INTO cortex_passages
    (passage_id, content, source_type, source_id, importance, tokens, indexed_at)
    VALUES ($passage_id, $content, $source_type, $source_id, $importance, $tokens, datetime('now'))
  `);

  // 批量插入
  const insertMany = db.transaction((items: Passage[]) => {
    for (const p of items) {
      insertStmt.run({
        $passage_id: p.passage_id,
        $content: p.content,
        $source_type: p.source_type,
        $source_id: p.source_id,
        $importance: p.importance,
        $tokens: countTokens(p.content),
      });
    }
  });

  insertMany(passages);
  result.sqlite = passages.length;
  db.close();

  // 2. 写入 Tantivy (如果可用)
  if (existsSync(TANTIVY_BIN)) {
    // 创建临时 JSONL 文件
    const tmpFile = `/tmp/passages_${Date.now()}.jsonl`;
    const lines = passages.map((p) =>
      JSON.stringify({
        id: p.passage_id,
        content: p.content,
        source_type: p.source_type,
        importance: p.importance,
      })
    );
    writeFileSync(tmpFile, lines.join("\n"), "utf-8");

    // 调用 Tantivy 索引
    const result = spawnSync(TANTIVY_BIN, ["index", "passages", tmpFile], {
      encoding: "utf-8",
    });

    if (result.status === 0) {
      result.tantivy = passages.length;
    }

    // 清理临时文件
    // fs.unlinkSync(tmpFile);
  }

  return result;
}

// ============================================================
// Indexing
// ============================================================

async function indexAllPassages(): Promise<IndexStats> {
  const startTime = Date.now();
  const stats: IndexStats = {
    total_passages: 0,
    indexed: 0,
    failed: 0,
    total_tokens: 0,
    duration_ms: 0,
  };

  console.log("\n📊 开始索引 Passages...\n");

  // 1. 提取所有 passages
  const allPassages: Passage[] = [];

  const dirs = [
    "knowledge/research",
    "knowledge/architecture",
    "knowledge/patterns",
    "knowledge/lessons",
    "knowledge/entities/technologies",
    "knowledge/entities/people",
    "knowledge/entities/concepts",
    "artifacts",
  ];

  for (const dir of dirs) {
    const fullPath = join(CORTEX_ROOT, dir);
    if (!existsSync(fullPath)) continue;

    const files = readdirSync(fullPath).filter((f) => f.endsWith(".md"));

    for (const file of files) {
      const filePath = join(fullPath, file);
      const content = readFileSync(filePath, "utf-8");
      const passages = extractPassagesFromFile(filePath, content);
      allPassages.push(...passages);
    }
  }

  stats.total_passages = allPassages.length;
  console.log(`   📚 提取了 ${allPassages.length} 个 passages`);

  // 2. 并发生成嵌入
  console.log("\n   🔢 生成嵌入向量...");
  const embeddings = await generateEmbeddingsConcurrent(allPassages, 10);
  console.log(`   ✓ 成功生成 ${embeddings.size} 个嵌入`);

  // 3. 双写
  console.log("\n   💾 双写到 SQLite + Tantivy...");
  const writeResult = await dualWritePassages(allPassages, embeddings);
  console.log(`   ✓ SQLite: ${writeResult.sqlite} 条`);
  console.log(`   ✓ Tantivy: ${writeResult.tantivy} 条`);

  stats.indexed = writeResult.sqlite;
  stats.failed = stats.total_passages - stats.indexed;
  stats.total_tokens = allPassages.reduce(
    (sum, p) => sum + countTokens(p.content),
    0
  );
  stats.duration_ms = Date.now() - startTime;

  // 4. 输出统计
  console.log("\n┌─────────────────────────────────────────────────────────────┐");
  console.log("│                     📊 索引统计                              │");
  console.log("├─────────────────────────────────────────────────────────────┤");
  console.log(`│ Total Passages: ${String(stats.total_passages).padStart(10)}                          │`);
  console.log(`│ Indexed:        ${String(stats.indexed).padStart(10)}                          │`);
  console.log(`│ Failed:         ${String(stats.failed).padStart(10)}                          │`);
  console.log(`│ Total Tokens:   ${String(stats.total_tokens.toLocaleString()).padStart(10)}                          │`);
  console.log(`│ Duration:       ${String(stats.duration_ms + "ms").padStart(10)}                          │`);
  console.log("└─────────────────────────────────────────────────────────────┘");

  return stats;
}

// ============================================================
// Search
// ============================================================

async function searchPassages(query: string, limit: number = 10): Promise<Passage[]> {
  const db = new Database(DB_PATH);

  // 使用 FTS 或 LIKE 搜索
  const results = db
    .query<
      {
        passage_id: string;
        content: string;
        source_type: string;
        source_id: string;
        importance: number;
        tokens: number;
      },
      [string, number]
    >(
      `
    SELECT passage_id, content, source_type, source_id, importance, tokens
    FROM cortex_passages
    WHERE content LIKE '%' || $query || '%'
    ORDER BY importance DESC
    LIMIT $limit
  `
    )
    .all(query, limit);

  db.close();

  return results.map((r) => ({
    passage_id: r.passage_id,
    content: r.content,
    source_type: r.source_type,
    source_id: r.source_id,
    importance: r.importance,
    created_at: "",
  }));
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

function countTokens(text: string): number {
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
  const otherChars = text.length - chineseChars;
  return Math.ceil(chineseChars / 1.5 + otherChars / 4);
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "stats";

  switch (command) {
    case "index":
      await indexAllPassages();
      break;

    case "search":
      const query = args[1];
      if (!query) {
        console.error("Usage: bun passage-manager.ts search <query>");
        process.exit(1);
      }

      const results = await searchPassages(query, 10);
      console.log(`\n🔍 搜索结果: "${query}"\n`);

      for (const r of results) {
        const preview = r.content.slice(0, 100).replace(/\n/g, " ");
        console.log(`📄 [${r.source_type}] ${r.source_id}`);
        console.log(`   ${preview}...\n`);
      }
      break;

    case "stats":
      const db = new Database(DB_PATH);
      try {
        const count = db
          .query<{ cnt: number }, []>(
            "SELECT COUNT(*) as cnt FROM cortex_passages"
          )
          .get();
        const byType = db
          .query<{ source_type: string; cnt: number }, []>(
            "SELECT source_type, COUNT(*) as cnt FROM cortex_passages GROUP BY source_type"
          )
          .all();

        console.log("\n📊 Passage 统计\n");
        console.log(`   总数: ${count?.cnt || 0}`);
        console.log("\n   按类型:");
        for (const { source_type, cnt } of byType) {
          console.log(`   - ${source_type}: ${cnt}`);
        }
      } catch (e) {
        console.log("   尚未索引，运行 'bun passage-manager.ts index'");
      }
      db.close();
      break;

    case "clear":
      const db2 = new Database(DB_PATH);
      db2.run("DELETE FROM cortex_passages");
      db2.close();
      console.log("✓ 已清除所有 passages");
      break;

    default:
      console.log(`
Usage:
  bun passage-manager.ts index     # 索引所有 passages
  bun passage-manager.ts search <q> # 搜索
  bun passage-manager.ts stats      # 查看统计
  bun passage-manager.ts clear      # 清除索引
      `);
  }
}

main();
