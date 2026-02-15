#!/usr/bin/env bun
/**
 * SMI - Solar Metadata Index
 * 快速查询表结构，一次命中
 */

import Database from "bun:sqlite";
import { join } from "path";

const DB_PATH = join(process.env.HOME!, ".solar", "solar.db");
const db = new Database(DB_PATH);

const command = process.argv[2] || "list";
const arg = process.argv[3];

function showSchema(tableName: string) {
  const row = db
    .prepare("SELECT columns FROM sys_schema_registry WHERE table_name = ?")
    .get(tableName);

  if (!row) {
    console.log(`❌ Table '${tableName}' not found`);
    console.log(`Hint: /smi search ${tableName}`);
    return;
  }

  const columns = JSON.parse((row as any).columns);
  const colNames = columns.map((c: any) => c.name);

  console.log(`\n📋 ${tableName}`);
  console.log("─".repeat(60));
  console.log(`Columns (${colNames.length}):`);
  console.log(colNames.join(", "));
  console.log();

  // 显示主键和非空列
  const pk = columns.filter((c: any) => c.pk).map((c: any) => c.name);
  const required = columns.filter((c: any) => c.notnull && !c.pk).map((c: any) => c.name);

  if (pk.length > 0) {
    console.log(`Primary Key: ${pk.join(", ")}`);
  }
  if (required.length > 0) {
    console.log(`Required: ${required.join(", ")}`);
  }
  console.log();
}

function searchTables(keyword: string) {
  const rows = db
    .prepare(
      "SELECT table_name, table_type FROM sys_schema_registry WHERE table_name LIKE ? ORDER BY table_name"
    )
    .all(`%${keyword}%`);

  if (rows.length === 0) {
    console.log(`❌ No tables found matching '${keyword}'`);
    return;
  }

  console.log(`\n🔍 Found ${rows.length} tables matching '${keyword}':\n`);
  rows.forEach((row: any) => {
    const icon = row.table_type === "view" ? "👁️ " : "📊";
    console.log(`  ${icon} ${row.table_name}`);
  });
  console.log();
}

function listTables(pattern?: string) {
  const query = pattern
    ? "SELECT table_name, table_type FROM sys_schema_registry WHERE table_name LIKE ? ORDER BY table_name"
    : "SELECT table_name, table_type FROM sys_schema_registry ORDER BY table_name";

  const rows = pattern ? db.prepare(query).all(pattern) : db.prepare(query).all();

  console.log(`\n📚 Total: ${rows.length} tables/views\n`);

  // 分组显示
  const groups: Record<string, string[]> = {};
  rows.forEach((row: any) => {
    const prefix = row.table_name.split("_")[0];
    if (!groups[prefix]) groups[prefix] = [];
    groups[prefix].push(row.table_name);
  });

  Object.entries(groups)
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([prefix, tables]) => {
      console.log(`${prefix}_* (${tables.length}):`);
      console.log(`  ${tables.slice(0, 5).join(", ")}${tables.length > 5 ? "..." : ""}`);
    });
  console.log();
}

function refreshSchemas() {
  console.log("🔄 Refreshing schema registry...");

  const { spawnSync } = require("child_process");
  const result = spawnSync("python3", ["/tmp/register_schemas.py"], {
    stdio: "inherit",
  });

  if (result.status === 0) {
    console.log("✓ Schema registry updated");
  } else {
    console.log("❌ Failed to refresh");
  }
}

// 主逻辑
switch (command) {
  case "search":
    if (!arg) {
      console.log("Usage: /smi search <keyword>");
      process.exit(1);
    }
    searchTables(arg);
    break;

  case "list":
    listTables(arg);
    break;

  case "refresh":
    refreshSchemas();
    break;

  default:
    // 默认: 查看表结构
    showSchema(command);
    break;
}

db.close();
