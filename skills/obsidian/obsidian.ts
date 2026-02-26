#!/usr/bin/env bun
/**
 * Obsidian Skill - 与 solar know vault 双向同步
 *
 * 用法:
 *   bun obsidian.ts new "标题" "内容"
 *   bun obsidian.ts search "关键词"
 *   bun obsidian.ts read "文件名"
 *   bun obsidian.ts today
 *   bun obsidian.ts list
 *   bun obsidian.ts sync "类型" "标题" "内容"
 */

import { writeFile, readFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join, basename } from 'path';
import { execSync } from 'child_process';

const VAULT_PATH = process.env.HOME + '/Library/Mobile Documents/com~apple~CloudDocs/solar know';

// 子目录
const DIRS = {
  insights: 'Insights',
  analysis: 'Analysis',
  daily: 'Daily',
  inbox: 'Inbox'
};

// 确保目录存在
async function ensureDirs() {
  for (const dir of Object.values(DIRS)) {
    const path = join(VAULT_PATH, dir);
    if (!existsSync(path)) {
      await mkdir(path, { recursive: true });
    }
  }
}

// 创建新笔记
async function createNote(title: string, content: string, subdir?: string) {
  await ensureDirs();

  const safeTitle = title.replace(/[\/\\:*?"<>|]/g, '-');
  const fileName = `${safeTitle}.md`;
  const dir = subdir ? join(VAULT_PATH, subdir) : VAULT_PATH;
  const filePath = join(dir, fileName);

  // 添加 frontmatter
  const fullContent = `---
title: ${title}
created: ${new Date().toISOString().split('T')[0]}
tags: [solar, auto-generated]
---

${content}
`;

  await writeFile(filePath, fullContent, 'utf-8');

  // 用 Obsidian URI 打开
  const obsidianUrl = `obsidian://open?vault=solar%20know&file=${encodeURIComponent(subdir ? `${subdir}/${fileName}` : fileName)}`;

  return { path: filePath, url: obsidianUrl };
}

// 搜索笔记
function searchNotes(query: string) {
  try {
    const result = execSync(
      `grep -ril "${query}" "${VAULT_PATH}" --include="*.md" 2>/dev/null`,
      { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 }
    );

    const files = result.trim().split('\n').filter(Boolean);

    return files.map(f => ({
      path: f,
      name: basename(f, '.md'),
      relativePath: f.replace(VAULT_PATH + '/', '')
    }));
  } catch {
    return [];
  }
}

// 读取笔记
async function readNote(fileName: string) {
  // 尝试直接路径
  let filePath = join(VAULT_PATH, fileName);

  // 如果没有 .md 后缀，加上
  if (!filePath.endsWith('.md')) {
    filePath += '.md';
  }

  // 如果文件不存在，搜索
  if (!existsSync(filePath)) {
    const results = searchNotes(fileName);
    if (results.length > 0) {
      filePath = results[0].path;
    } else {
      return null;
    }
  }

  const content = await readFile(filePath, 'utf-8');
  return { path: filePath, content };
}

// 列出所有笔记
function listNotes() {
  try {
    const result = execSync(
      `find "${VAULT_PATH}" -name "*.md" -type f ! -path "*/.obsidian/*" 2>/dev/null | head -50`,
      { encoding: 'utf-8' }
    );

    const files = result.trim().split('\n').filter(Boolean);

    return files.map(f => ({
      path: f,
      name: basename(f, '.md'),
      relativePath: f.replace(VAULT_PATH + '/', '')
    }));
  } catch {
    return [];
  }
}

// 创建今日日记
async function createDaily() {
  const today = new Date();
  const dateStr = today.toISOString().split('T')[0];
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');

  const dir = join(VAULT_PATH, DIRS.daily, String(year), String(month));
  if (!existsSync(dir)) {
    await mkdir(dir, { recursive: true });
  }

  const filePath = join(dir, `${dateStr}.md`);

  if (!existsSync(filePath)) {
    const content = `# ${dateStr}

## 今日重点

-

## 笔记



## 待办

- [ ]

---
created: ${dateStr}
tags: [daily, journal]
`;
    await writeFile(filePath, content, 'utf-8');
  }

  const obsidianUrl = `obsidian://open?vault=solar%20know&file=${encodeURIComponent(`Daily/${year}/${month}/${dateStr}`)}`;

  return { path: filePath, url: obsidianUrl, isNew: !existsSync(filePath) };
}

// 同步内容（自动分类）
async function syncContent(type: string, title: string, content: string) {
  const typeMap: Record<string, string> = {
    insight: DIRS.insights,
    analysis: DIRS.analysis,
    daily: DIRS.daily,
    note: DIRS.inbox
  };

  const subdir = typeMap[type.toLowerCase()] || DIRS.inbox;
  return createNote(title, content, subdir);
}

// CLI
const [cmd, ...args] = process.argv.slice(2);

async function main() {
  switch (cmd) {
    case 'new': {
      const [title, content = ''] = args;
      if (!title) {
        console.log('用法: obsidian new "标题" "内容"');
        process.exit(1);
      }
      const result = await createNote(title, content);
      console.log(`✓ 笔记已创建: ${result.path}`);
      console.log(`打开: ${result.url}`);
      break;
    }

    case 'search': {
      const [query] = args;
      if (!query) {
        console.log('用法: obsidian search "关键词"');
        process.exit(1);
      }
      const results = searchNotes(query);
      if (results.length === 0) {
        console.log('未找到匹配的笔记');
      } else {
        console.log(`找到 ${results.length} 个笔记:`);
        results.forEach((r, i) => {
          console.log(`  ${i + 1}. ${r.name}`);
          console.log(`     ${r.relativePath}`);
        });
      }
      break;
    }

    case 'read': {
      const [fileName] = args;
      if (!fileName) {
        console.log('用法: obsidian read "文件名"');
        process.exit(1);
      }
      const result = await readNote(fileName);
      if (!result) {
        console.log('未找到笔记');
        process.exit(1);
      }
      console.log(`# ${result.path}\n`);
      console.log(result.content);
      break;
    }

    case 'list': {
      const notes = listNotes();
      console.log(`共 ${notes.length} 个笔记:\n`);
      notes.forEach((n, i) => {
        console.log(`${String(i + 1).padStart(2)}. ${n.name}`);
      });
      break;
    }

    case 'today': {
      const result = await createDaily();
      console.log(`${result.isNew ? '✓ 已创建' : '→ 已存在'}: ${result.path}`);
      console.log(`打开: ${result.url}`);
      break;
    }

    case 'sync': {
      const [type, title, content] = args;
      if (!type || !title || !content) {
        console.log('用法: obsidian sync <类型> "标题" "内容"');
        console.log('类型: insight | analysis | daily | note');
        process.exit(1);
      }
      const result = await syncContent(type, title, content);
      console.log(`✓ 已同步到 ${result.path}`);
      break;
    }

    default:
      console.log(`
Obsidian Skill - solar know vault

用法:
  obsidian new "标题" "内容"     创建新笔记
  obsidian search "关键词"       搜索笔记
  obsidian read "文件名"         读取笔记
  obsidian list                  列出所有笔记
  obsidian today                 创建/打开今日日记
  obsidian sync <类型> "标题" "内容"  同步内容

Vault: ${VAULT_PATH}
`);
  }
}

main().catch(console.error);
