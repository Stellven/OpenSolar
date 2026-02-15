#!/usr/bin/env bun
/**
 * Skill Generator - 从模板快速生成 Skill
 *
 * 使用:
 *   bun run skill-gen.ts --type monitor --name hn-monitor --api "https://..."
 *   bun run skill-gen.ts --type fetch --name weather --api "https://..."
 *   bun run skill-gen.ts --type crud --name notes
 *   bun run skill-gen.ts --list  # 列出可用模板
 */

import * as fs from "fs";
import * as path from "path";
import { homedir } from "os";

// ==================== 配置 ====================

const TEMPLATES_DIR = path.join(homedir(), ".claude", "skill-templates");
const SKILLS_DIR = path.join(homedir(), ".claude", "skills");
const LAUNCH_AGENTS_DIR = path.join(homedir(), "Library", "LaunchAgents");
const BUN_PATH = path.join(homedir(), ".bun", "bin", "bun");

// ==================== 模板类型 ====================

interface TemplateConfig {
  type: string;
  name: string;
  description: string;
  files: string[];
  requiredParams: string[];
  optionalParams: Record<string, string>;
}

const TEMPLATES: Record<string, TemplateConfig> = {
  monitor: {
    type: "monitor",
    name: "Monitor (定时监控)",
    description: "定时抓取数据 + 存储 + TVS 展示",
    files: ["monitor.ts.template", "monitor.SKILL.md.template", "monitor.plist.template"],
    requiredParams: ["name", "api"],
    optionalParams: {
      interval: "1",
      count: "30",
      emoji: "📡",
    },
  },
  fetch: {
    type: "fetch",
    name: "Fetch (API 获取)",
    description: "从 API 获取数据并展示",
    files: ["fetch.ts.template"],
    requiredParams: ["name", "api"],
    optionalParams: {
      emoji: "🔍",
    },
  },
  crud: {
    type: "crud",
    name: "CRUD (数据管理)",
    description: "数据增删改查",
    files: ["crud.ts.template"],
    requiredParams: ["name"],
    optionalParams: {
      table: "",
      emoji: "📝",
    },
  },
};

// ==================== 参数解析 ====================

interface GeneratorParams {
  type: string;
  name: string;
  api?: string;
  description?: string;
  interval?: number;
  count?: number;
  emoji?: string;
  table?: string;
  dataType?: string;
  fields?: string;
}

function parseArgs(): GeneratorParams | null {
  const args = process.argv.slice(2);

  if (args.includes("--list") || args.includes("-l")) {
    listTemplates();
    return null;
  }

  if (args.includes("--help") || args.includes("-h")) {
    printHelp();
    return null;
  }

  const params: GeneratorParams = {
    type: "",
    name: "",
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    switch (arg) {
      case "--type":
      case "-t":
        params.type = next || "";
        i++;
        break;
      case "--name":
      case "-n":
        params.name = next || "";
        i++;
        break;
      case "--api":
      case "-a":
        params.api = next || "";
        i++;
        break;
      case "--desc":
      case "-d":
        params.description = next || "";
        i++;
        break;
      case "--interval":
      case "-i":
        params.interval = parseInt(next) || 1;
        i++;
        break;
      case "--count":
      case "-c":
        params.count = parseInt(next) || 30;
        i++;
        break;
      case "--emoji":
      case "-e":
        params.emoji = next || "";
        i++;
        break;
      case "--table":
        params.table = next || "";
        i++;
        break;
    }
  }

  // 验证必须参数
  if (!params.type) {
    console.error("Error: --type is required");
    console.log("Use --list to see available templates");
    return null;
  }

  if (!TEMPLATES[params.type]) {
    console.error(`Error: Unknown template type: ${params.type}`);
    console.log("Use --list to see available templates");
    return null;
  }

  if (!params.name) {
    console.error("Error: --name is required");
    return null;
  }

  const template = TEMPLATES[params.type];
  if (template.requiredParams.includes("api") && !params.api) {
    console.error("Error: --api is required for this template type");
    return null;
  }

  return params;
}

// ==================== 模板处理 ====================

function loadTemplate(filename: string): string {
  const filepath = path.join(TEMPLATES_DIR, filename);
  if (!fs.existsSync(filepath)) {
    throw new Error(`Template not found: ${filepath}`);
  }
  return fs.readFileSync(filepath, "utf-8");
}

function fillTemplate(template: string, vars: Record<string, string>): string {
  let result = template;
  for (const [key, value] of Object.entries(vars)) {
    const pattern = new RegExp(`\\{\\{${key}\\}\\}`, "g");
    result = result.replace(pattern, value);
  }
  return result;
}

function generateVars(params: GeneratorParams): Record<string, string> {
  const now = new Date().toISOString();
  const skillPath = path.join(SKILLS_DIR, params.name);
  const tableName = params.table || params.name.replace(/-/g, "_");

  return {
    // 基础信息
    SKILL_NAME: params.name,
    SKILL_COMMAND: params.name,
    SKILL_DESCRIPTION: params.description || `${params.name} skill`,
    SKILL_LONG_DESCRIPTION: params.description || `Auto-generated ${params.type} skill for ${params.name}`,
    SKILL_TITLE: params.name.toUpperCase().replace(/-/g, " "),
    SKILL_EMOJI: params.emoji || TEMPLATES[params.type].optionalParams.emoji || "🔧",
    SKILL_PATH: skillPath,
    GENERATED_AT: now,

    // API 相关
    API_URL: params.api || "",
    API_SOURCE: params.api ? new URL(params.api).hostname : "API",
    HEADERS: "{}",

    // 数据库相关
    TABLE_NAME: tableName,
    TABLE_SCHEMA: "      -- TODO: Define your schema\n      data TEXT,",
    TABLE_SCHEMA_DOC: "  data TEXT,",

    // 数据类型 (默认简单结构)
    DATA_TYPE: `${capitalize(params.name.replace(/-/g, ""))}Item`,
    DATA_FIELDS: "  id: number;\n  data: string;",

    // 插入/更新相关
    INSERT_COLUMNS: "data",
    INSERT_PLACEHOLDERS: "?",
    INSERT_VALUES: "item.data",
    INSERT_PARAMS: "data.data",
    UPDATE_SET: "data = ?",
    UPDATE_PARAMS: "data.data",
    ADD_DATA: 'data: args[1]',
    UPDATE_DATA: 'data: args[2]',
    PRINT_FIELDS: '│  Data: ${item.data?.padEnd(56) || ""}│',

    // 解析逻辑 (默认)
    PARSE_LOGIC: "const results = Array.isArray(data) ? data : [data];",
    FORMAT_LOGIC: 'return `  ${rank}. ${JSON.stringify(item).slice(0, 55)}...`;',

    // 定时相关
    INTERVAL_HOURS: String(params.interval || 1),
    INTERVAL_SECONDS: String((params.interval || 1) * 3600),
    FETCH_COUNT: String(params.count || 30),

    // 路径相关
    HOME: homedir(),
    BUN_PATH: BUN_PATH,
    BUN_PATH_DIR: path.dirname(BUN_PATH),
  };
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ==================== 生成 Skill ====================

function generateSkill(params: GeneratorParams): void {
  const template = TEMPLATES[params.type];
  const vars = generateVars(params);
  const skillDir = path.join(SKILLS_DIR, params.name);

  console.log(`\n🔧 Generating ${template.name} skill: ${params.name}\n`);

  // 创建目录
  if (!fs.existsSync(skillDir)) {
    fs.mkdirSync(skillDir, { recursive: true });
  }

  // 生成文件
  for (const templateFile of template.files) {
    const content = fillTemplate(loadTemplate(templateFile), vars);

    let outputFile: string;
    let outputPath: string;

    if (templateFile.endsWith(".ts.template")) {
      outputFile = templateFile.includes("crud") ? "crud.ts" : "fetch.ts";
      outputPath = path.join(skillDir, outputFile);
    } else if (templateFile.endsWith(".SKILL.md.template")) {
      outputFile = "SKILL.md";
      outputPath = path.join(skillDir, outputFile);
    } else if (templateFile.endsWith(".plist.template")) {
      outputFile = `com.solar.${params.name}.plist`;
      outputPath = path.join(LAUNCH_AGENTS_DIR, outputFile);
    } else {
      continue;
    }

    fs.writeFileSync(outputPath, content);
    console.log(`  ✓ Created: ${outputPath}`);
  }

  // 生成 SKILL.md (如果没有模板)
  if (!template.files.some((f) => f.includes("SKILL.md"))) {
    const skillMd = `# /${params.name} - ${params.description || params.name}

Auto-generated ${params.type} skill.

## Usage

\`\`\`bash
/${params.name}
\`\`\`

---
*Generated at: ${new Date().toISOString()}*
`;
    const skillMdPath = path.join(skillDir, "SKILL.md");
    fs.writeFileSync(skillMdPath, skillMd);
    console.log(`  ✓ Created: ${skillMdPath}`);
  }

  console.log(`
┌─────────────────────────────────────────────────────────────────┐
│                     ✅ SKILL GENERATED                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Name      ${params.name.padEnd(53)}│
│  Type      ${template.name.padEnd(53)}│
│  Path      ~/.claude/skills/${params.name.padEnd(37)}│
│                                                                 │
│  Next Steps:                                                    │
│  1. Edit fetch.ts to customize data parsing                     │
│  2. Update SKILL.md documentation                               │
│  3. Test: bun run ~/.claude/skills/${params.name}/fetch.ts${" ".repeat(Math.max(0, 15 - params.name.length))}│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list
`);
}

// ==================== 帮助信息 ====================

function listTemplates(): void {
  console.log(`
┌─────────────────────────────────────────────────────────────────┐
│                     📦 AVAILABLE TEMPLATES                       │
├─────────────────────────────────────────────────────────────────┤`);

  for (const [key, config] of Object.entries(TEMPLATES)) {
    console.log(`│                                                                 │`);
    console.log(`│  ${key.padEnd(10)} ${config.name.padEnd(50)}│`);
    console.log(`│             ${config.description.padEnd(50)}│`);
    console.log(`│             Required: ${config.requiredParams.join(", ").padEnd(40)}│`);
  }

  console.log(`│                                                                 │
└─────────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list
`);
}

function printHelp(): void {
  console.log(`
Skill Generator - 从模板快速生成 Skill

Usage:
  bun run skill-gen.ts [options]

Options:
  --type, -t <type>     Template type (monitor, fetch, crud)
  --name, -n <name>     Skill name (e.g., hn-monitor, weather)
  --api, -a <url>       API URL (required for monitor/fetch)
  --desc, -d <desc>     Description
  --interval, -i <hrs>  Update interval in hours (default: 1)
  --count, -c <num>     Items to fetch (default: 30)
  --emoji, -e <emoji>   Skill emoji
  --list, -l            List available templates
  --help, -h            Show this help

Examples:
  bun run skill-gen.ts --type monitor --name hn-monitor --api "https://hn.api..."
  bun run skill-gen.ts --type fetch --name weather --api "https://weather.api..."
  bun run skill-gen.ts --type crud --name notes
`);
}

// ==================== 主程序 ====================

function main(): void {
  const params = parseArgs();
  if (params) {
    generateSkill(params);
  }
}

main();
