#!/usr/bin/env bun
/**
 * Solar Web Dashboard - Page Generator
 *
 * 生成并注册页面到 Dashboard
 *
 * Usage:
 *   bun generate.ts register <file.html>
 *   bun generate.ts list
 *   bun generate.ts scan
 */

import { Database } from 'bun:sqlite';
import { readFileSync, existsSync, copyFileSync, mkdirSync, readdirSync, statSync } from 'fs';
import { join, basename, dirname } from 'path';

const DB_PATH = join(process.env.HOME!, '.claude/solar.db');
const WEB_ROOT = dirname(import.meta.path);
const PAGES_DIR = join(WEB_ROOT, 'pages');

// 确保 pages 目录存在
if (!existsSync(PAGES_DIR)) {
  mkdirSync(PAGES_DIR, { recursive: true });
}

// 初始化数据库
function getDb(): Database {
  const db = new Database(DB_PATH);

  // 确保表存在
  const schemaPath = join(WEB_ROOT, 'schema.sql');
  if (existsSync(schemaPath)) {
    db.exec(readFileSync(schemaPath, 'utf-8'));
  }

  return db;
}

// 从 HTML 提取信息
function extractPageInfo(filePath: string): {
  title: string;
  description: string;
  category: string;
  icon: string;
} {
  const content = readFileSync(filePath, 'utf-8');
  const fileName = basename(filePath, '.html');

  // 提取标题
  const titleMatch = content.match(/<title>([^<]+)<\/title>/i);
  const title = titleMatch ? titleMatch[1] : fileName;

  // 提取描述 (meta description)
  const descMatch = content.match(/<meta\s+name="description"\s+content="([^"]+)"/i);
  const description = descMatch ? descMatch[1] : '';

  // 根据文件名/内容推断分类
  let category = 'general';
  let icon = '📄';

  const lowerName = fileName.toLowerCase();
  const lowerContent = content.toLowerCase();

  if (lowerName.includes('architecture') || lowerName.includes('design') || lowerContent.includes('架构')) {
    category = 'architecture';
    icon = '🏗️';
  } else if (lowerName.includes('report') || lowerName.includes('analysis') || lowerContent.includes('报告')) {
    category = 'report';
    icon = '📊';
  } else if (lowerName.includes('tool') || lowerName.includes('util')) {
    category = 'tool';
    icon = '🔧';
  } else if (lowerName.includes('system') || lowerName.includes('status') || lowerName.includes('dashboard')) {
    category = 'system';
    icon = '⚙️';
  }

  return { title, description, category, icon };
}

// 注册页面
function registerPage(
  db: Database,
  pageId: string,
  title: string,
  icon: string,
  category: string,
  description: string,
  sourceType: string,
  sourcePath: string,
  sortOrder: number = 100,
  pinned: boolean = false
): void {
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO sys_web_pages
    (page_id, title, icon, category, description, source_type, source_path, sort_order, pinned)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  stmt.run(pageId, title, icon, category, description, sourceType, sourcePath, sortOrder, pinned ? 1 : 0);
  console.log(`✓ Registered: ${pageId} (${category})`);
}

// 命令: register
function cmdRegister(filePath: string): void {
  if (!existsSync(filePath)) {
    console.error(`Error: File not found: ${filePath}`);
    process.exit(1);
  }

  const db = getDb();
  const fileName = basename(filePath);
  const pageId = basename(filePath, '.html');

  // 复制到 pages 目录
  const targetPath = join(PAGES_DIR, fileName);
  if (filePath !== targetPath) {
    copyFileSync(filePath, targetPath);
    console.log(`Copied to: ${targetPath}`);
  }

  // 提取信息并注册
  const info = extractPageInfo(filePath);
  registerPage(
    db,
    pageId,
    info.title,
    info.icon,
    info.category,
    info.description,
    'file',
    `/pages/${fileName}`
  );

  db.close();
  console.log(`\n页面已注册到 Dashboard: http://localhost:8800`);
}

// 命令: list
function cmdList(): void {
  const db = getDb();
  const pages = db.query('SELECT * FROM v_web_pages').all() as any[];

  console.log('\n╭─ 📑 Dashboard Pages ─────────────────────────────────────╮');

  if (pages.length === 0) {
    console.log('│  (无注册页面)                                            │');
  } else {
    for (const page of pages) {
      const pinned = page.pinned ? '📌' : '  ';
      const views = page.view_count || 0;
      console.log(`│ ${pinned} ${page.icon} ${page.title.padEnd(30)} [${page.category}] Views: ${views}`);
    }
  }

  console.log('╰──────────────────────────────────────────────────────────╯');
  db.close();
}

// 命令: scan - 扫描并注册 pages 目录
function cmdScan(): void {
  const db = getDb();

  if (!existsSync(PAGES_DIR)) {
    console.log('Pages directory does not exist');
    return;
  }

  const files = readdirSync(PAGES_DIR);
  let count = 0;

  for (const file of files) {
    if (!file.endsWith('.html')) continue;

    const filePath = join(PAGES_DIR, file);
    const stat = statSync(filePath);
    if (!stat.isFile()) continue;

    const pageId = basename(file, '.html');
    const info = extractPageInfo(filePath);

    registerPage(
      db,
      pageId,
      info.title,
      info.icon,
      info.category,
      info.description,
      'file',
      `/pages/${file}`
    );
    count++;
  }

  console.log(`\nScanned and registered ${count} pages`);
  db.close();
}

// 命令: migrate - 迁移外部 HTML 文件
function cmdMigrate(sourcePath: string): void {
  if (!existsSync(sourcePath)) {
    console.error(`Error: Source not found: ${sourcePath}`);
    process.exit(1);
  }

  const stat = statSync(sourcePath);

  if (stat.isDirectory()) {
    // 迁移目录下所有 HTML 文件
    const files = readdirSync(sourcePath);
    for (const file of files) {
      if (file.endsWith('.html')) {
        const filePath = join(sourcePath, file);
        cmdRegister(filePath);
      }
    }
  } else if (stat.isFile() && sourcePath.endsWith('.html')) {
    cmdRegister(sourcePath);
  } else {
    console.error('Source must be an HTML file or directory');
    process.exit(1);
  }
}

// ============================================================================
// Main
// ============================================================================

const args = process.argv.slice(2);
const command = args[0];

switch (command) {
  case 'register':
    if (!args[1]) {
      console.error('Usage: bun generate.ts register <file.html>');
      process.exit(1);
    }
    cmdRegister(args[1]);
    break;

  case 'list':
    cmdList();
    break;

  case 'scan':
    cmdScan();
    break;

  case 'migrate':
    if (!args[1]) {
      console.error('Usage: bun generate.ts migrate <path>');
      process.exit(1);
    }
    cmdMigrate(args[1]);
    break;

  default:
    console.log(`
Solar Web Dashboard - Page Generator

Usage:
  bun generate.ts register <file.html>  - 注册单个页面
  bun generate.ts list                  - 列出所有页面
  bun generate.ts scan                  - 扫描 pages 目录
  bun generate.ts migrate <path>        - 迁移外部 HTML
`);
}
