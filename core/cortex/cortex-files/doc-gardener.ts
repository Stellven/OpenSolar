#!/usr/bin/env bun
/**
 * Doc Gardener - 文档园丁 (垃圾回收)
 *
 * 灵感来源: OpenAI "doc-gardening" agent
 * 核心理念: 技术债务像高利贷，持续小额偿还优于集中爆发
 *
 * Usage:
 *   bun doc-gardener.ts scan        # 扫描过时内容
 *   bun doc-gardener.ts report      # 生成报告
 *   bun doc-gardener.ts clean       # 清理明显过时内容
 */

import { homedir } from "os";
import { join } from "path";
import {
  existsSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "fs";

const SOLAR_ROOT = `${homedir()}/.solar`;
const CLAUDE_ROOT = `${homedir()}/.claude`;

// ============================================================
// Types
// ============================================================

interface StaleItem {
  type: "rule" | "skill" | "doc" | "memory" | "plan";
  path: string;
  issue: string;
  severity: "low" | "medium" | "high";
  lastUpdated: string;
  suggestion: string;
}

interface GardenReport {
  scanned: number;
  stale: StaleItem[];
  by_severity: { low: number; medium: number; high: number };
  generated_at: string;
}

// ============================================================
// Scanners
// ============================================================

/**
 * 扫描规则文件
 */
function scanRules(): StaleItem[] {
  const items: StaleItem[] = [];
  const rulesDir = join(CLAUDE_ROOT, "rules");

  if (!existsSync(rulesDir)) return items;

  const files = readdirSync(rulesDir).filter((f) => f.endsWith(".md"));
  const now = Date.now();
  const threeMonths = 90 * 24 * 60 * 60 * 1000;

  for (const file of files) {
    const filePath = join(rulesDir, file);
    const stats = statSync(filePath);
    const content = readFileSync(filePath, "utf-8");
    const age = now - stats.mtimeMs;

    // 检查是否超过 3 个月未更新
    if (age > threeMonths) {
      const days = Math.floor(age / (24 * 60 * 60 * 1000));
      items.push({
        type: "rule",
        path: filePath,
        issue: `${days} 天未更新`,
        severity: days > 180 ? "high" : days > 90 ? "medium" : "low",
        lastUpdated: stats.mtime.toISOString().split("T")[0],
        suggestion: "检查规则是否仍然有效，考虑合并或删除",
      });
    }

    // 检查是否包含过时关键词
    const staleKeywords = ["TODO", "FIXME", "待定", "临时", "temp", "deprecated"];
    for (const keyword of staleKeywords) {
      if (content.toLowerCase().includes(keyword.toLowerCase())) {
        items.push({
          type: "rule",
          path: filePath,
          issue: `包含待处理关键词: ${keyword}`,
          severity: "low",
          lastUpdated: stats.mtime.toISOString().split("T")[0],
          suggestion: "处理或移除待办事项",
        });
        break;
      }
    }
  }

  return items;
}

/**
 * 扫描技能文件
 */
function scanSkills(): StaleItem[] {
  const items: StaleItem[] = [];
  const skillsDir = join(CLAUDE_ROOT, "skills");

  if (!existsSync(skillsDir)) return items;

  const dirs = readdirSync(skillsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  const now = Date.now();
  const sixMonths = 180 * 24 * 60 * 60 * 1000;

  for (const dir of dirs) {
    const skillPath = join(skillsDir, dir, "SKILL.md");
    if (!existsSync(skillPath)) {
      items.push({
        type: "skill",
        path: join(skillsDir, dir),
        issue: "缺少 SKILL.md 文件",
        severity: "medium",
        lastUpdated: "unknown",
        suggestion: "创建 SKILL.md 或删除此目录",
      });
      continue;
    }

    const stats = statSync(skillPath);
    const age = now - stats.mtimeMs;

    if (age > sixMonths) {
      const days = Math.floor(age / (24 * 60 * 60 * 1000));
      items.push({
        type: "skill",
        path: skillPath,
        issue: `${days} 天未更新`,
        severity: "low",
        lastUpdated: stats.mtime.toISOString().split("T")[0],
        suggestion: "检查技能是否仍在使用",
      });
    }
  }

  return items;
}

/**
 * 扫描执行计划
 */
function scanPlans(): StaleItem[] {
  const items: StaleItem[] = [];
  const activeDir = join(SOLAR_ROOT, "docs/exec-plans/active");

  if (!existsSync(activeDir)) return items;

  const files = readdirSync(activeDir).filter((f) => f.endsWith(".md"));
  const now = Date.now();
  const twoWeeks = 14 * 24 * 60 * 60 * 1000;

  for (const file of files) {
    const filePath = join(activeDir, file);
    const stats = statSync(filePath);
    const content = readFileSync(filePath, "utf-8");
    const age = now - stats.mtimeMs;

    // 检查是否所有任务都完成了但还在 active
    if (content.includes("✅") && !content.includes("🔄") && !content.includes("❌")) {
      items.push({
        type: "plan",
        path: filePath,
        issue: "所有任务已完成，仍在 active 目录",
        severity: "medium",
        lastUpdated: stats.mtime.toISOString().split("T")[0],
        suggestion: "移动到 completed/ 目录",
      });
    }

    // 检查是否超过 2 周未更新
    if (age > twoWeeks) {
      const days = Math.floor(age / (24 * 60 * 60 * 1000));
      items.push({
        type: "plan",
        path: filePath,
        issue: `${days} 天未更新`,
        severity: days > 30 ? "high" : "medium",
        lastUpdated: stats.mtime.toISOString().split("T")[0],
        suggestion: "更新进度或移动到适当目录",
      });
    }
  }

  return items;
}

/**
 * 扫描 Memory Blocks
 */
function scanMemoryBlocks(): StaleItem[] {
  const items: StaleItem[] = [];
  const blocksDir = join(SOLAR_ROOT, "memory/blocks");

  if (!existsSync(blocksDir)) return items;

  const files = readdirSync(blocksDir).filter((f) => f.endsWith(".json"));
  const now = Date.now();
  const oneMonth = 30 * 24 * 60 * 60 * 1000;

  for (const file of files) {
    const filePath = join(blocksDir, file);
    const stats = statSync(filePath);
    const content = readFileSync(filePath, "utf-8");
    const age = now - stats.mtimeMs;

    try {
      const block = JSON.parse(content);

      // 检查 project block 是否需要更新
      if (block.label === "project" && age > oneMonth) {
        const days = Math.floor(age / (24 * 60 * 60 * 1000));
        items.push({
          type: "memory",
          path: filePath,
          issue: `project block ${days} 天未更新`,
          severity: "low",
          lastUpdated: stats.mtime.toISOString().split("T")[0],
          suggestion: "更新当前项目状态",
        });
      }

      // 检查利用率
      const utilization = block.value.length / block.limit;
      if (utilization > 0.9) {
        items.push({
          type: "memory",
          path: filePath,
          issue: `block ${block.label} 使用率 ${(utilization * 100).toFixed(0)}%`,
          severity: "medium",
          lastUpdated: stats.mtime.toISOString().split("T")[0],
          suggestion: "考虑扩容或精简内容",
        });
      }
    } catch (e) {
      // JSON 解析错误
    }
  }

  return items;
}

// ============================================================
// Main
// ============================================================

function scanAll(): GardenReport {
  const stale: StaleItem[] = [
    ...scanRules(),
    ...scanSkills(),
    ...scanPlans(),
    ...scanMemoryBlocks(),
  ];

  const bySeverity = {
    low: stale.filter((i) => i.severity === "low").length,
    medium: stale.filter((i) => i.severity === "medium").length,
    high: stale.filter((i) => i.severity === "high").length,
  };

  return {
    scanned: stale.length,
    stale,
    by_severity: bySeverity,
    generated_at: new Date().toISOString(),
  };
}

function displayReport(report: GardenReport) {
  console.log(`
╭═══════════════════════════════════════════════════════════════════════════════╮
│                         🌿 Doc Gardener - 垃圾回收报告                          │
╞═══════════════════════════════════════════════════════════════════════════════╡
│                                                                               │
│  📊 扫描结果                                                                  │
│  ─────────────────────────────────────────────────────────────────────────    │
│  发现问题: ${report.stale.length} 项                                                          │
│  • 高优先级: ${report.by_severity.high}                                                                │
│  • 中优先级: ${report.by_severity.medium}                                                                │
│  • 低优先级: ${report.by_severity.low}                                                                │
│                                                                               │
│  📋 详情                                                                      │
│  ─────────────────────────────────────────────────────────────────────────    │
`);

  // 按严重程度排序
  const sorted = [...report.stale].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return order[a.severity] - order[b.severity];
  });

  for (const item of sorted.slice(0, 15)) {
    const emoji = item.severity === "high" ? "🔴" : item.severity === "medium" ? "🟡" : "🟢";
    const typeEmoji = { rule: "📜", skill: "🔧", doc: "📄", memory: "🧠", plan: "📋" }[item.type];

    console.log(`│  ${emoji} ${typeEmoji} ${item.issue.slice(0, 40).padEnd(40)}`);
    console.log(`│     ${item.suggestion.slice(0, 50)}`);
    console.log("│");
  }

  if (sorted.length > 15) {
    console.log(`│  ... 还有 ${sorted.length - 15} 项`);
  }

  console.log("│");
  console.log("╰═══════════════════════════════════════════════════════════════════════════════╯");
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "scan";

  switch (command) {
    case "scan": {
      const report = scanAll();
      displayReport(report);

      // 保存报告
      const reportPath = join(SOLAR_ROOT, "docs/generated/garden-report.json");
      writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf-8");
      console.log(`\n📄 报告已保存: ${reportPath}`);
      break;
    }

    case "report": {
      const reportPath = join(SOLAR_ROOT, "docs/generated/garden-report.json");
      if (existsSync(reportPath)) {
        const report = JSON.parse(readFileSync(reportPath, "utf-8")) as GardenReport;
        displayReport(report);
      } else {
        console.log("暂无报告，先运行 scan");
      }
      break;
    }

    case "help":
    default:
      console.log(`
Doc Gardener - 文档园丁 (垃圾回收)

用法:
  bun doc-gardener.ts scan     # 扫描并生成报告
  bun doc-gardener.ts report   # 查看上次报告

扫描范围:
  • 规则文件 (rules/*.md)
  • 技能文件 (skills/*/SKILL.md)
  • 执行计划 (docs/exec-plans/)
  • Memory Blocks (memory/blocks/)

灵感来源: OpenAI "doc-gardening" agent
技术债务像高利贷，持续小额偿还优于集中爆发
      `);
  }
}

if (import.meta.main) {
  main();
}

export { scanAll, scanRules, scanSkills, scanPlans, scanMemoryBlocks };
