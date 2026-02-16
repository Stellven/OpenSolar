#!/usr/bin/env bun
/**
 * Cortex Files Sync Tool
 *
 * 将数据库内容同步到文件系统，支持大模型直接 Read 访问
 *
 * Usage:
 *   bun sync.ts --full         # 全量同步
 *   bun sync.ts --incremental  # 增量同步
 *   bun sync.ts --status       # 查看状态
 */

import { Database } from "bun:sqlite";
import { homedir } from "os";
import { join } from "path";
import { mkdirSync, writeFileSync, existsSync, readdirSync, statSync } from "fs";

const DB_PATH = `${homedir()}/.solar/solar.db`;
const CORTEX_ROOT = `${homedir()}/.solar/cortex`;

// ============================================================
// Types
// ============================================================

interface Source {
  source_id: number;
  title: string;
  finding: string | null;
  credibility: number;
  url: string | null;
  citation_key: string | null;
  expert_model: string | null;
  created_at: string;
}

interface Entity {
  entity_id: number;
  name: string;
  type: string;
  description: string | null;
  importance: number;
  created_at: string;
}

interface Relation {
  from_entity: string;
  to_entity: string;
  relation_type: string;
  confidence: number;
}

interface SyncStats {
  sources: number;
  entities: number;
  artifacts: number;
  files_created: number;
  files_updated: number;
  files_deleted: number;
}

// ============================================================
// Directory Structure
// ============================================================

const DIR_STRUCTURE = {
  system: [
    "IDENTITY.md",
    "IRON_LAWS.md",
    "PERSONALITY.md",
    "GUARDIAN.md",
  ],
  knowledge: [
    "architecture",
    "patterns",
    "lessons",
    "research",
    "entities/technologies",
    "entities/people",
    "entities/concepts",
  ],
  artifacts: [
    "insights",
    "reviews",
    "benchmarks",
  ],
  memory: [
    "episodic",
    "semantic",
  ],
  stats: [],
};

function ensureDirectories() {
  // 创建根目录
  if (!existsSync(CORTEX_ROOT)) {
    mkdirSync(CORTEX_ROOT, { recursive: true });
  }

  // 创建子目录
  const createDir = (dir: string) => {
    const path = join(CORTEX_ROOT, dir);
    if (!existsSync(path)) {
      mkdirSync(path, { recursive: true });
    }
  };

  for (const [parent, children] of Object.entries(DIR_STRUCTURE)) {
    createDir(parent);
    for (const child of children) {
      if (!child.endsWith(".md")) {
        createDir(join(parent, child));
      }
    }
  }

  console.log("✓ 目录结构已创建");
}

// ============================================================
// Markdown Generation
// ============================================================

function generateFrontmatter(source: Source): string {
  const tags = source.expert_model ? [source.expert_model] : [];
  const keywords = source.title.split(/\s+/).filter(w => w.length > 2);

  // Letta-style fields for LLM context management
  const description = source.finding
    ? source.finding.substring(0, 100).replace(/\n/g, " ").trim()
    : source.title;
  const limit = 2000;  // Default token limit
  const readOnly = source.credibility >= 0.9;  // High-credibility sources are protected

  return `---
id: source-${source.source_id}
type: reference
created: ${source.created_at.split(" ")[0] || source.created_at}
credibility: ${source.credibility.toFixed(2)}
description: "${description.replace(/"/g, '\\"')}"
limit: ${limit}
read_only: ${readOnly}
tags: [${tags.join(", ")}]
keywords: [${keywords.slice(0, 5).join(", ")}]
source: ${source.citation_key || "imported"}
---`;
}

function sourceToMarkdown(source: Source): string {
  const frontmatter = generateFrontmatter(source);
  const title = source.title;
  const summary = source.finding ? source.finding.substring(0, 200) : "";
  const content = source.finding || "";

  return `${frontmatter}

# ${title}

${summary ? `> ${summary}${summary.length >= 200 ? "..." : ""}\n` : ""}

## 详细内容

${content}

${source.url ? `\n**来源**: [${source.url}](${source.url})\n` : ""}
`;
}

function entityToMarkdown(entity: Entity, relations: Relation[]): string {
  // 分离出度和入度关系
  const outgoing = relations.filter(r => r.from_entity === entity.name);
  const incoming = relations.filter(r => r.to_entity === entity.name);

  let relationsSection = "";
  if (outgoing.length > 0 || incoming.length > 0) {
    relationsSection = "\n## 关系网络\n";

    if (outgoing.length > 0) {
      relationsSection += "\n### 指向\n";
      for (const r of outgoing.slice(0, 20)) {
        relationsSection += `- **${r.relation_type}** → [[${r.to_entity}]] (${(r.confidence * 100).toFixed(0)}%)\n`;
      }
      if (outgoing.length > 20) {
        relationsSection += `- ... 还有 ${outgoing.length - 20} 条\n`;
      }
    }

    if (incoming.length > 0) {
      relationsSection += "\n### 被引用\n";
      for (const r of incoming.slice(0, 10)) {
        relationsSection += `- [[${r.from_entity}]] **${r.relation_type}** → (${(r.confidence * 100).toFixed(0)}%)\n`;
      }
      if (incoming.length > 10) {
        relationsSection += `- ... 还有 ${incoming.length - 10} 条\n`;
      }
    }
  }

  // Letta-style fields for LLM context management
  const description = entity.description
    ? entity.description.substring(0, 100).replace(/\n/g, " ").trim()
    : `${entity.type}: ${entity.name}`;
  const limit = entity.importance >= 0.8 ? 3000 : 1500;  // Important entities get more context
  const readOnly = entity.importance >= 0.9;  // High-importance entities are protected

  return `---
id: entity-${entity.entity_id}
type: ${entity.type}
importance: ${entity.importance.toFixed(2)}
relations: ${relations.length}
created: ${entity.created_at.split(" ")[0]}
description: "${description.replace(/"/g, '\\"')}"
limit: ${limit}
read_only: ${readOnly}
---

# ${entity.name}

${entity.description || "暂无描述"}

## 类型
${entity.type}

## 重要程度
${"★".repeat(Math.round(entity.importance * 5))}${"☆".repeat(5 - Math.round(entity.importance * 5))}
${relationsSection}`;
}

// ============================================================
// Sync Functions
// ============================================================

function syncSources(db: Database, stats: SyncStats) {
  const sources = db.query<Source, []>(`
    SELECT source_id, title, finding, credibility, url, citation_key, expert_model, created_at
    FROM cortex_sources
    ORDER BY credibility DESC
  `).all();

  console.log(`📚 同步 ${sources.length} 条参考资料...`);

  for (const source of sources) {
    // 根据 source_type 决定目录
    let subdir = "knowledge/research";
    if (source.title.includes("铁律") || source.title.includes("Rule")) {
      subdir = "knowledge/patterns";
    } else if (source.title.includes("架构") || source.title.includes("Architecture")) {
      subdir = "knowledge/architecture";
    } else if (source.title.includes("教训") || source.title.includes("Lesson")) {
      subdir = "knowledge/lessons";
    }

    // 生成文件名
    const safeName = source.title
      .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "-")
      .replace(/-+/g, "-")
      .substring(0, 50);
    const filename = `${safeName}.md`;
    const filepath = join(CORTEX_ROOT, subdir, filename);

    const content = sourceToMarkdown(source);

    if (existsSync(filepath)) {
      stats.files_updated++;
    } else {
      stats.files_created++;
    }

    writeFileSync(filepath, content, "utf-8");
  }

  stats.sources = sources.length;
}

function syncEntities(db: Database, stats: SyncStats) {
  const entities = db.query<Entity, []>(`
    SELECT entity_id, name, type, description, importance, created_at
    FROM knowledge_entities
    ORDER BY importance DESC
  `).all();

  // 预加载所有关系
  const allRelations = db.query<Relation, []>(`
    SELECT from_entity, to_entity, relation_type, confidence
    FROM knowledge_relations
  `).all();

  console.log(`🧠 同步 ${entities.length} 个知识实体 (含 ${allRelations.length} 条关系)...`);

  for (const entity of entities) {
    // 查找与该实体相关的所有关系
    const entityRelations = allRelations.filter(
      r => r.from_entity === entity.name || r.to_entity === entity.name
    );

    // 根据 type 决定目录
    let subdir = "entities/concepts";
    if (entity.type === "technology") {
      subdir = "entities/technologies";
    } else if (entity.type === "person") {
      subdir = "entities/people";
    }

    const safeName = entity.name
      .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "-")
      .replace(/-+/g, "-")
      .substring(0, 50);
    const filename = `${safeName}.md`;
    const filepath = join(CORTEX_ROOT, "knowledge", subdir, filename);

    const content = entityToMarkdown(entity, entityRelations);

    if (existsSync(filepath)) {
      stats.files_updated++;
    } else {
      stats.files_created++;
    }

    writeFileSync(filepath, content, "utf-8");
  }

  stats.entities = entities.length;
}

function generateDashboard(db: Database) {
  const stats = {
    sources: 0,
    entities: 0,
    relations: 0,
    artifacts: 0,
  };

  try {
    stats.sources = (db.query("SELECT COUNT(*) as cnt FROM cortex_sources").get() as { cnt: number })?.cnt || 0;
    stats.entities = (db.query("SELECT COUNT(*) as cnt FROM knowledge_entities").get() as { cnt: number })?.cnt || 0;
    stats.relations = (db.query("SELECT COUNT(*) as cnt FROM knowledge_relations").get() as { cnt: number })?.cnt || 0;
    stats.artifacts = (db.query("SELECT COUNT(*) as cnt FROM cortex_artifacts").get() as { cnt: number })?.cnt || 0;
  } catch (e) {
    // Ignore
  }

  const today = new Date().toISOString().split("T")[0];

  const content = `---
type: dashboard
generated: ${today}
---

# Cortex Dashboard

> 生成时间: ${today}

## 📊 统计概览

| 指标 | 数量 |
|------|------|
| 参考资料 | ${stats.sources} |
| 知识实体 | ${stats.entities} |
| 关系连接 | ${stats.relations} |
| 分析产物 | ${stats.artifacts} |
| **总计** | **${stats.sources + stats.entities + stats.relations + stats.artifacts}** |

## 📁 目录结构

\`\`\`
cortex/
├── system/        # 核心身份 (始终加载)
├── knowledge/     # 知识库 (按需读取)
│   ├── architecture/
│   ├── patterns/
│   ├── lessons/
│   └── entities/
├── artifacts/     # 分析产物
├── memory/        # 对话记忆
└── stats/         # 统计信息
\`\`\`

## 🔄 最近更新

查看 Git 历史了解最近变更:

\`\`\`bash
cd ~/.solar/cortex && git log --oneline -10
\`\`\`
`;

  writeFileSync(join(CORTEX_ROOT, "stats", "DASHBOARD.md"), content, "utf-8");
  console.log("📊 Dashboard 已生成");
}

function gitCommit(stats: SyncStats) {
  const message = `sync: update cortex files from DB

Changes:
- Sources: ${stats.sources}
- Entities: ${stats.entities}
- Files created: ${stats.files_created}
- Files updated: ${stats.files_updated}

Generated by cortex-files/sync.ts`;

  try {
    // 检查是否是 git 仓库
    if (!existsSync(join(CORTEX_ROOT, ".git"))) {
      console.log("⚠️  非 Git 仓库，跳过提交");
      console.log("提示: 运行 'cd ~/.solar/cortex && git init' 初始化");
      return;
    }

    // Git add
    Bun.spawnSync(["git", "add", "-A"], { cwd: CORTEX_ROOT });

    // Git commit
    const result = Bun.spawnSync(["git", "commit", "-m", message], { cwd: CORTEX_ROOT });

    if (result.status === 0) {
      console.log("✓ Git 提交成功");
    } else {
      console.log("⚠️  无变更需要提交");
    }
  } catch (e) {
    console.log("⚠️  Git 操作失败:", e);
  }
}

// ============================================================
// Main
// ============================================================

function printStatus() {
  console.log("\n📊 Cortex Files 状态\n");

  if (!existsSync(CORTEX_ROOT)) {
    console.log("❌ Cortex 目录不存在，请先运行 --full 同步");
    return;
  }

  // 统计文件数
  const countFiles = (dir: string): number => {
    if (!existsSync(dir)) return 0;
    let count = 0;
    for (const file of readdirSync(dir)) {
      const path = join(dir, file);
      if (statSync(path).isDirectory()) {
        count += countFiles(path);
      } else if (file.endsWith(".md")) {
        count++;
      }
    }
    return count;
  };

  console.log(`目录: ${CORTEX_ROOT}`);
  console.log(`文件数: ${countFiles(CORTEX_ROOT)}`);
  console.log(`Git: ${existsSync(join(CORTEX_ROOT, ".git")) ? "✓ 已初始化" : "❌ 未初始化"}`);
  console.log();
}

async function main() {
  const args = Bun.argv.slice(2);
  const mode = args[0] || "--status";

  if (mode === "--status") {
    printStatus();
    return;
  }

  console.log("🔄 Cortex Files 同步开始\n");

  // 确保目录结构
  ensureDirectories();

  // 打开数据库
  const db = new Database(DB_PATH);

  const stats: SyncStats = {
    sources: 0,
    entities: 0,
    artifacts: 0,
    files_created: 0,
    files_updated: 0,
    files_deleted: 0,
  };

  try {
    // 同步数据
    syncSources(db, stats);
    syncEntities(db, stats);
    generateDashboard(db);

    // Git 提交
    gitCommit(stats);

    console.log("\n✅ 同步完成!");
    console.log(`   文件创建: ${stats.files_created}`);
    console.log(`   文件更新: ${stats.files_updated}`);
    console.log(`   目录: ${CORTEX_ROOT}`);

  } finally {
    db.close();
  }
}

main();
