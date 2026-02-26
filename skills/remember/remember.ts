#!/usr/bin/env bun
/**
 * /remember - 任务学习与记忆固化
 *
 * 执行方式:
 *   bun remember.ts              # 交互式学习
 *   bun remember.ts skill <name> # 提取技能
 *   bun remember.ts review       # 查看学习记录
 *   bun remember.ts search <q>   # 搜索记忆
 */

import { Database } from "bun:sqlite";
import { homedir } from "os";
import { join } from "path";
import { existsSync, appendFileSync, writeFileSync, readFileSync } from "fs";

const DB_PATH = `${homedir()}/.solar/solar.db`;
const SKILLS_DIR = `${homedir()}/.claude/skills`;
const CORTEX_DIR = `${homedir()}/.solar/cortex`;

// ============================================================
// Types
// ============================================================

interface LearningEvent {
  task_summary: string;
  learning_type: "skill" | "knowledge" | "insight" | "experience";
  content: string;
  storage_location: "favorites" | "semantic" | "cortex" | "skill";
  storage_id?: string;
  confidence: number;
}

interface ExtractedPattern {
  pattern_type: "command_sequence" | "code_template" | "workflow" | "decision_tree";
  name: string;
  description: string;
  steps: string[];
  code_snippets?: string[];
  confidence: number;
}

// ============================================================
// Pattern Extraction (集成 skill-learner)
// ============================================================

/**
 * 从会话内容中提取可复用的模式
 */
function extractPatterns(sessionContent: string): ExtractedPattern[] {
  const patterns: ExtractedPattern[] = [];

  // 提取命令序列模式
  const commandPattern = /(?:^|\n)(?:`|\$)\s*(\w+(?:\s+\S+)?)/gm;
  const commands: string[] = [];
  let match;

  while ((match = commandPattern.exec(sessionContent)) !== null) {
    commands.push(match[1]);
  }

  // 如果有 3+ 个命令，找重复模式
  if (commands.length >= 3) {
    for (let len = 2; len <= 4; len++) {
      for (let i = 0; i <= commands.length - len; i++) {
        const seqStr = commands.slice(i, i + len).join(" ");
        let count = 0;
        for (let j = 0; j <= commands.length - len; j++) {
          if (commands.slice(j, j + len).join(" ") === seqStr) {
            count++;
          }
        }

        if (count >= 2) {
          const seq = commands.slice(i, i + len).join(" → ");
          patterns.push({
            pattern_type: "command_sequence",
            name: `command-pattern-${patterns.length}`,
            description: `重复命令序列: ${seq}`,
            steps: commands.slice(i, i + len),
            confidence: Math.min(0.7 + count * 0.1, 0.95),
          });
        }
      }
    }
  }

  // 提取代码模板
  const codeBlocks = sessionContent.match(/```[\s\S]*?```/g) || [];
  for (const block of codeBlocks) {
    const lines = block.split("\n");
    if (lines.length > 5) {
      patterns.push({
        pattern_type: "code_template",
        name: `code-template-${patterns.length}`,
        description: `代码模板 (${lines.length} 行)`,
        steps: ["检查上下文", "应用模板", "验证结果"],
        code_snippets: [block],
        confidence: 0.5,
      });
    }
  }

  // 按置信度排序，去重
  const seen = new Set<string>();
  return patterns
    .sort((a, b) => b.confidence - a.confidence)
    .filter(p => {
      const key = p.description;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

// ============================================================
// Database Operations
// ============================================================

function ensureTables(db: Database) {
  db.run(`
    CREATE TABLE IF NOT EXISTS sys_learning_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT DEFAULT (datetime('now', 'localtime')),
      session_id TEXT,
      task_summary TEXT,
      learning_type TEXT,
      content TEXT,
      storage_location TEXT,
      storage_id TEXT,
      confidence REAL DEFAULT 0.8
    )
  `);
}

// ============================================================
// Storage Functions
// ============================================================

/**
 * 存储到 sys_favorites (高价值结论)
 */
function saveToFavorite(db: Database, title: string, content: string, tags: string[]): number {
  const stmt = db.prepare(`
    INSERT INTO sys_favorites (title, question, answer, tags, importance, created_at)
    VALUES ($title, '', $answer, $tags, 8, datetime('now'))
  `);

  const result = stmt.run({
    $title: title,
    $answer: content,
    $tags: JSON.stringify(tags),
  });

  return result.lastInsertRowid;
}

/**
 * 存储到 evo_memory_semantic (知识点)
 */
function saveToSemanticMemory(
  db: Database,
  namespace: string,
  key: string,
  value: string
): void {
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO evo_memory_semantic (namespace, key, value, created_at, last_accessed_at)
    VALUES ($namespace, $key, $value, datetime('now'), datetime('now'))
  `);

  stmt.run({ $namespace: namespace, $key: key, $value: value });
}

/**
 * 存储到 Cortex passages (归档记忆)
 */
function saveToCortex(passage: {
  content: string;
  source_type: string;
  source_id: string;
  importance: number;
}): void {
  const passagesFile = join(CORTEX_DIR, "passages.jsonl");

  const passageData = {
    ...passage,
    passage_id: `passage-${Date.now()}`,
    created_at: new Date().toISOString(),
  };

  appendFileSync(passagesFile, JSON.stringify(passageData) + "\n", "utf-8");
}

/**
 * 创建技能文件
 */
function createSkillFile(name: string, description: string, coreLogic: string): string {
  const skillDir = join(SKILLS_DIR, name);

  if (!existsSync(skillDir)) {
    require("fs").mkdirSync(skillDir, { recursive: true });
  }

  const skillMd = `# /${name} - ${description}

> 来源: /remember 学习 (${new Date().toISOString().split("T")[0]})

## 用法

\`\`\`bash
/${name}
\`\`\`

## 核心逻辑

${coreLogic}

## 示例

TODO: 添加示例

---

*Skill learned from: /remember*
*Created: ${new Date().toISOString().split("T")[0]}*
`;

  writeFileSync(join(skillDir, "SKILL.md"), skillMd, "utf-8");

  return skillDir;
}

/**
 * 记录学习事件
 */
function recordLearning(db: Database, event: LearningEvent): number {
  const stmt = db.prepare(`
    INSERT INTO sys_learning_events
    (session_id, task_summary, learning_type, content, storage_location, storage_id, confidence)
    VALUES (
      substr(hex(randomblob(4)), 1, 8),
      $task_summary,
      $learning_type,
      $content,
      $storage_location,
      $storage_id,
      $confidence
    )
  `);

  const result = stmt.run({
    $task_summary: event.task_summary,
    $learning_type: event.learning_type,
    $content: event.content,
    $storage_location: event.storage_location,
    $storage_id: event.storage_id || "",
    $confidence: event.confidence,
  });

  return result.lastInsertRowid;
}

// ============================================================
// Display Functions
// ============================================================

function displayRememberResult(results: {
  task: string;
  learnings: Array<{
    type: string;
    content: string;
    storage: string;
    storageId?: string;
  }>;
  stored: Array<{ location: string; count: number }>;
}) {
  console.log(`
╭═══════════════════════════════════════════════════════════════════════════════╮
│                         💭 REMEMBER - 任务学习                                 │
╞═══════════════════════════════════════════════════════════════════════════════╡
│                                                                               │
│  📋 任务回顾                                                                  │
│  ─────────────────────────────────────────────────────────────────────────    │
│  任务: ${results.task}
│                                                                               │
│  💡 学习要点                                                                  │
│  ─────────────────────────────────────────────────────────────────────────    │
`);

  for (const learning of results.learnings) {
    const typeEmoji = {
      skill: "🔧",
      knowledge: "📚",
      insight: "💡",
      experience: "⚠️",
    }[learning.type] || "📝";

    console.log(`│  ${typeEmoji} [${learning.type}] ${learning.content.slice(0, 60)}${learning.content.length > 60 ? "..." : ""}`);
    console.log(`│     → 存储: ${learning.storage}${learning.storageId ? ` (${learning.storageId})` : ""}`);
    console.log("│");
  }

  console.log("│  📦 存储结果");
  console.log("│  ─────────────────────────────────────────────────────────────────────────    │");

  for (const { location, count } of results.stored) {
    console.log(`│  ✓ ${location}: +${count}`);
  }

  console.log("│");
  console.log("╰═══════════════════════════════════════════════════════════════════════════════╯");
}

function displayReview(events: Array<{
  id: number;
  timestamp: string;
  task_summary: string;
  learning_type: string;
  content: string;
}>) {
  console.log(`
╭═══════════════════════════════════════════════════════════════════════════════╮
│                         📚 学习记录回顾                                        │
╞═══════════════════════════════════════════════════════════════════════════════╡
│                                                                               │
`);

  if (events.length === 0) {
    console.log("│  暂无学习记录，执行 /remember 开始学习");
  } else {
    for (const event of events) {
      const typeEmoji = {
        skill: "🔧",
        knowledge: "📚",
        insight: "💡",
        experience: "⚠️",
      }[event.learning_type] || "📝";

      const date = event.timestamp.split("T")[0];
      console.log(`│  ${date} ${typeEmoji} ${event.task_summary?.slice(0, 40) || "无任务"}`);
      console.log(`│     ${event.content.slice(0, 50)}...`);
      console.log("│");
    }
  }

  console.log("╰═══════════════════════════════════════════════════════════════════════════════╯");
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "help";

  const db = new Database(DB_PATH);
  ensureTables(db);

  try {
    switch (command) {
      case "skill": {
        const skillName = args[1];
        const description = args[2] || "从任务学习的技能";
        const coreLogic = args.slice(3).join(" ") || "TODO: 添加核心逻辑";

        if (!skillName) {
          console.error("Usage: bun remember.ts skill <name> <description> <core_logic>");
          process.exit(1);
        }

        const skillPath = createSkillFile(skillName, description, coreLogic);

        recordLearning(db, {
          task_summary: `提取技能: ${skillName}`,
          learning_type: "skill",
          content: description,
          storage_location: "skill",
          storage_id: skillName,
          confidence: 0.85,
        });

        console.log(`✓ 技能已创建: ${skillPath}/SKILL.md`);
        console.log(`✓ 使用: /${skillName}`);
        break;
      }

      case "review": {
        const limit = parseInt(args[1]) || 10;

        const events = db
          .prepare<
            Array<{
              id: number;
              timestamp: string;
              task_summary: string;
              learning_type: string;
              content: string;
            }>,
            [number]
          >(`
            SELECT id, timestamp, task_summary, learning_type, content
            FROM sys_learning_events
            ORDER BY timestamp DESC
            LIMIT $limit
          `)
          .all(limit);

        displayReview(events);
        break;
      }

      case "search": {
        const query = args[1];
        if (!query) {
          console.error("Usage: bun remember.ts search <query>");
          process.exit(1);
        }

        const events = db
          .prepare<
            Array<{
              id: number;
              timestamp: string;
              task_summary: string;
              learning_type: string;
              content: string;
              storage_location: string;
            }>,
            [string, string]
          >(`
            SELECT id, timestamp, task_summary, learning_type, content, storage_location
            FROM sys_learning_events
            WHERE task_summary LIKE '%' || $q || '%'
               OR content LIKE '%' || $q || '%'
            ORDER BY timestamp DESC
            LIMIT 20
          `)
          .all(query, query);

        console.log(`\n🔍 搜索结果: "${query}"\n`);
        for (const event of events) {
          console.log(`[${event.learning_type}] ${event.content.slice(0, 80)}...`);
          console.log(`   存储: ${event.storage_location}\n`);
        }

        if (events.length === 0) {
          console.log("未找到相关记忆");
        }
        break;
      }

      case "extract": {
        // 从会话文件中提取模式和技能建议
        const sessionPath = args[1];
        if (!sessionPath) {
          console.error("Usage: bun remember.ts extract <session-file>");
          console.error("  从会话文件中提取可复用的模式，建议创建技能");
          process.exit(1);
        }

        if (!existsSync(sessionPath)) {
          console.error(`文件不存在: ${sessionPath}`);
          process.exit(1);
        }

        const sessionContent = readFileSync(sessionPath, "utf-8");
        const patterns = extractPatterns(sessionContent);

        console.log(`
╭═══════════════════════════════════════════════════════════════════════════════╮
│                         🔍 PATTERN EXTRACTOR                                   │
╞═══════════════════════════════════════════════════════════════════════════════╡
│                                                                               │
│  📄 会话文件: ${sessionPath.slice(-40)}
│  📊 发现模式: ${patterns.length} 个
│                                                                               │
│  ─────────────────────────────────────────────────────────────────────────    │
`);

        if (patterns.length === 0) {
          console.log("│  未发现可复用的模式");
          console.log("╰───────────────────────────────────────────────────────────────────────────────╯");
          break;
        }

        const highConfidence = patterns.filter(p => p.confidence >= 0.8);

        for (const pattern of patterns.slice(0, 10)) {
          const confEmoji = pattern.confidence >= 0.8 ? "🟢" : pattern.confidence >= 0.7 ? "🟡" : "⚪";
          const typeEmoji = {
            command_sequence: "⌨️",
            code_template: "📄",
            workflow: "🔄",
            decision_tree: "🌳",
          }[pattern.pattern_type] || "📝";

          console.log(`│  ${confEmoji} ${typeEmoji} [${(pattern.confidence * 100).toFixed(0)}%] ${pattern.name}`);
          console.log(`│     ${pattern.description.slice(0, 60)}`);
          if (pattern.steps && pattern.steps.length > 0) {
            console.log(`│     步骤: ${pattern.steps.slice(0, 3).join(" → ")}${pattern.steps.length > 3 ? " ..." : ""}`);
          }
          console.log("│");
        }

        if (highConfidence.length > 0) {
          console.log(`│  💡 建议: ${highConfidence.length} 个高置信度模式可以创建为技能`);
          console.log("│     使用: /remember skill <name> <description>");
        }

        console.log("╰═══════════════════════════════════════════════════════════════════════════════╯");
        break;
      }

      case "example": {
        // 示例学习流程
        const exampleResults = {
          task: "实现 embedding-service.ts 多后端支持",
          learnings: [
            {
              type: "skill",
              content: "检测 import.meta.main 防止模块导入时执行 main()",
              storage: "skills/precise-edit",
            },
            {
              type: "knowledge",
              content: "Zhipu embedding-2 API 返回 1024 维向量",
              storage: "evo_memory_semantic",
            },
            {
              type: "experience",
              content: "Bun 模块导入时会执行顶层代码，需用 import.meta.main 隔离",
              storage: "cortex",
            },
          ],
          stored: [
            { location: "sys_favorites", count: 1 },
            { location: "evo_memory_semantic", count: 1 },
            { location: "cortex", count: 1 },
          ],
        };

        displayRememberResult(exampleResults);
        break;
      }

      case "help":
      default:
        console.log(`
/remember - 任务学习与记忆固化

用法:
  bun remember.ts              # 交互式学习 (需要通过 Skill 调用)
  bun remember.ts skill <name> <desc> <logic>  # 创建技能文件
  bun remember.ts extract <file> # 从会话文件提取可复用模式
  bun remember.ts review [n]   # 查看最近 n 条学习记录 (默认 10)
  bun remember.ts search <q>   # 搜索学习记录
  bun remember.ts example      # 显示示例输出

存储位置:
  • sys_favorites       - 高价值结论
  • evo_memory_semantic - 知识点
  • Cortex passages     - 归档记忆
  • skills/*.md         - 可复用技能
        `);
    }
  } finally {
    db.close();
  }
}

if (import.meta.main) {
  main();
}

export {
  saveToFavorite,
  saveToSemanticMemory,
  saveToCortex,
  createSkillFile,
  recordLearning,
};
