#!/usr/bin/env bun
/**
 * Skill Learner - 从任务中自动学习技能
 *
 * 灵感来源: Letta 技能学习机制
 * 核心理念: 技能即 .md 文件，可版本控制，从任务中自动提取
 *
 * Usage:
 *   bun skill-learner.ts analyze <session-file>  # 分析会话提取技能
 *   bun skill-learner.ts create <name> <desc>    # 创建技能模板
 *   bun skill-learner.ts list                    # 列出所有技能
 *   bun skill-learner.ts stats                   # 技能统计
 */

import { homedir } from "os";
import { join, basename } from "path";
import { existsSync, readdirSync, readFileSync, writeFileSync, statSync } from "fs";

const SKILLS_DIR = `${homedir()}/.claude/skills`;
const DB_PATH = `${homedir()}/.solar/solar.db`;

// ============================================================
// Types
// ============================================================

interface SkillMeta {
  name: string;
  path: string;
  description: string;
  source: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
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
// Skill Discovery
// ============================================================

/**
 * 扫描所有技能
 */
export function scanSkills(): SkillMeta[] {
  const skills: SkillMeta[] = [];

  if (!existsSync(SKILLS_DIR)) {
    return skills;
  }

  const dirs = readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  for (const dir of dirs) {
    const skillPath = join(SKILLS_DIR, dir, "SKILL.md");

    if (!existsSync(skillPath)) {
      continue;
    }

    try {
      const content = readFileSync(skillPath, "utf-8");
      const stats = statSync(skillPath);

      // 提取描述 (第一行 # 标题)
      const titleMatch = content.match(/^#\s+(.+?)\s*[-–—]\s*(.+)$/m);
      const description = titleMatch
        ? titleMatch[2]
        : content.split("\n").find((l) => l.startsWith(">"))?.slice(1).trim() || "";

      // 提取来源
      const sourceMatch = content.match(/来源:\s*(.+)/);
      const source = sourceMatch ? sourceMatch[1] : "manual";

      skills.push({
        name: dir,
        path: skillPath,
        description: description.slice(0, 100),
        source,
        created_at: stats.birthtime.toISOString().split("T")[0],
        updated_at: stats.mtime.toISOString().split("T")[0],
        usage_count: 0, // TODO: 从日志统计
      });
    } catch (e) {
      console.error(`Failed to scan skill: ${dir}`);
    }
  }

  return skills;
}

/**
 * 按来源分组统计
 */
export function getSkillStats(): {
  total: number;
  by_source: Record<string, number>;
  recent: SkillMeta[];
} {
  const skills = scanSkills();

  const bySource: Record<string, number> = {};
  for (const skill of skills) {
    const source = skill.source || "manual";
    bySource[source] = (bySource[source] || 0) + 1;
  }

  const recent = skills
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 10);

  return {
    total: skills.length,
    by_source: bySource,
    recent,
  };
}

// ============================================================
// Skill Creation
// ============================================================

/**
 * 创建技能模板
 */
export function createSkillTemplate(
  name: string,
  description: string,
  source: string = "manual",
  steps: string[] = []
): string {
  const skillDir = join(SKILLS_DIR, name);

  if (!existsSync(skillDir)) {
    require("fs").mkdirSync(skillDir, { recursive: true });
  }

  const today = new Date().toISOString().split("T")[0];

  const template = `# /${name} - ${description}

> 来源: ${source}
> 创建: ${today}

## 用法

\`\`\`bash
/${name} [args]
\`\`\`

## 核心逻辑

${steps.length > 0 ? steps.map((s, i) => `${i + 1}. ${s}`).join("\n") : "TODO: 添加核心逻辑"}

## 示例

\`\`\`
TODO: 添加示例
\`\`\`

## 变更记录

| 日期 | 变更 |
|------|------|
| ${today} | 初始创建 |

---

*Skill: ${name}*
*Created: ${today}*
`;

  const skillPath = join(skillDir, "SKILL.md");
  writeFileSync(skillPath, template, "utf-8");

  // 注册到数据库
  try {
    const { Database } = require("bun:sqlite");
    const db = new Database(DB_PATH);

    db.run(`
      INSERT OR REPLACE INTO sys_skills (skill_id, name, command, description, status, created_at)
      VALUES (?, ?, ?, ?, 'active', datetime('now'))
    `, [`skill_${name}`, name, name, description]);

    db.close();
  } catch (e) {
    // 忽略数据库错误
  }

  return skillPath;
}

// ============================================================
// Pattern Extraction
// ============================================================

/**
 * 从会话文件中提取模式
 */
export function extractPatterns(sessionContent: string): ExtractedPattern[] {
  const patterns: ExtractedPattern[] = [];

  // 提取命令序列模式
  const commandPattern = /(?:^|\n)(?:`|\$)\s*(\w+(?:\s+\S+)?)/gm;
  const commands: string[] = [];
  let match;

  while ((match = commandPattern.exec(sessionContent)) !== null) {
    commands.push(match[1]);
  }

  // 如果有 3+ 个重复的命令序列，可能是技能
  if (commands.length >= 3) {
    // 找重复模式
    for (let len = 2; len <= 4; len++) {
      for (let i = 0; i <= commands.length - len; i++) {
        const seq = commands.slice(i, i + len).join(" → ");

        // 检查是否重复
        const seqStr = commands.slice(i, i + len).join(" ");
        let count = 0;
        for (let j = 0; j <= commands.length - len; j++) {
          if (commands.slice(j, j + len).join(" ") === seqStr) {
            count++;
          }
        }

        if (count >= 2) {
          patterns.push({
            pattern_type: "command_sequence",
            name: `command-pattern-${patterns.length}`,
            description: `重复命令序列: ${seq}`,
            steps: commands.slice(i, i + len),
            confidence: 0.7 + count * 0.1,
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
      // 有一定长度的代码块
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

  return patterns;
}

/**
 * 分析会话并建议技能
 */
export function analyzeSessionForSkills(sessionPath: string): {
  patterns: ExtractedPattern[];
  suggestions: Array<{ name: string; description: string; steps: string[] }>;
} {
  if (!existsSync(sessionPath)) {
    return { patterns: [], suggestions: [] };
  }

  const content = readFileSync(sessionPath, "utf-8");
  const patterns = extractPatterns(content);

  // 生成建议
  const suggestions = patterns
    .filter((p) => p.confidence >= 0.7)
    .map((p) => ({
      name: p.name.replace(/-/g, "_").toLowerCase(),
      description: p.description,
      steps: p.steps,
    }));

  return { patterns, suggestions };
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "help";

  switch (command) {
    case "list": {
      const skills = scanSkills();
      console.log("\n📚 技能列表\n");

      for (const skill of skills) {
        const source = skill.source === "manual" ? "📝" : "🤖";
        console.log(`  ${source} /${skill.name.padEnd(20)} ${skill.description.slice(0, 40)}`);
      }

      console.log(`\n  📊 总计: ${skills.length} 个技能`);
      break;
    }

    case "stats": {
      const stats = getSkillStats();
      console.log("\n📊 技能统计\n");
      console.log(`  总计: ${stats.total} 个技能\n`);

      console.log("  按来源:");
      for (const [source, count] of Object.entries(stats.by_source)) {
        console.log(`    • ${source}: ${count}`);
      }

      console.log("\n  最近更新:");
      for (const skill of stats.recent.slice(0, 5)) {
        console.log(`    • ${skill.updated_at} /${skill.name}`);
      }
      break;
    }

    case "create": {
      const name = args[1];
      const description = args[2] || "新技能";
      const source = args[3] || "manual";

      if (!name) {
        console.error("Usage: bun skill-learner.ts create <name> <description> [source]");
        process.exit(1);
      }

      const path = createSkillTemplate(name, description, source);
      console.log(`✓ 技能已创建: ${path}`);
      console.log(`✓ 使用: /${name}`);
      break;
    }

    case "analyze": {
      const sessionPath = args[1];
      if (!sessionPath) {
        console.error("Usage: bun skill-learner.ts analyze <session-file>");
        process.exit(1);
      }

      const result = analyzeSessionForSkills(sessionPath);
      console.log("\n🔍 会话分析结果\n");

      console.log("  发现模式:");
      for (const p of result.patterns) {
        console.log(`    • [${p.confidence.toFixed(2)}] ${p.description}`);
      }

      if (result.suggestions.length > 0) {
        console.log("\n  💡 建议创建技能:");
        for (const s of result.suggestions) {
          console.log(`    /${s.name}: ${s.description}`);
        }
      }
      break;
    }

    case "help":
    default:
      console.log(`
Skill Learner - 从任务中自动学习技能

用法:
  bun skill-learner.ts list              # 列出所有技能
  bun skill-learner.ts stats             # 技能统计
  bun skill-learner.ts create <name> <desc> [source]  # 创建技能
  bun skill-learner.ts analyze <file>    # 分析会话提取模式

技能文件位置:
  ~/.claude/skills/*/SKILL.md

灵感来源: Letta 技能学习机制
技能即 .md 文件，可版本控制，从任务中自动提取
      `);
  }
}

if (import.meta.main) {
  main();
}

// Functions are already exported above
