#!/usr/bin/env bun
/**
 * Obsidian 知识抽取器 v2
 *
 * 从 Obsidian vault 读取 Markdown，抽取知识写入:
 * 1. 文件存储: ~/.solar/extracted_knowledge/
 * 2. 同步到 Obsidian: solar know/Extracted/
 *
 * 用法:
 *   bun knowledge-extractor.ts extract <文件名>   # 抽取单个文件
 *   bun knowledge-extractor.ts extract-all        # 抽取所有文件
 *   bun knowledge-extractor.ts status             # 查看状态
 */

import { readFile, readdir, writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join, basename } from 'path';

const VAULT_PATH = process.env.HOME + '/Library/Mobile Documents/com~apple~CloudDocs/solar know';
const EXTRACTED_DIR = process.env.HOME + '/.solar/extracted_knowledge';
const EXTRACTED_IN_VAULT = join(VAULT_PATH, 'Extracted');

// 知识类型
type KnowledgeType = 'concept' | 'insight' | 'method' | 'reference' | 'lesson';

interface ExtractedKnowledge {
  type: KnowledgeType;
  title: string;
  finding: string;
  applicability: string;
  tags: string[];
  source_file: string;
  credibility: number;
  created_at: string;
}

// 确保目录存在
async function ensureDirs() {
  for (const dir of [EXTRACTED_DIR, EXTRACTED_IN_VAULT]) {
    if (!existsSync(dir)) {
      await mkdir(dir, { recursive: true });
    }
  }
}

// 检查是否已处理
function isProcessed(fileName: string): boolean {
  const markerFile = join(EXTRACTED_DIR, '.processed');
  if (!existsSync(markerFile)) return false;

  // 简单检查：看文件名是否在已处理列表中
  const processed = require('fs').readFileSync(markerFile, 'utf-8').split('\n');
  return processed.includes(fileName);
}

// 标记已处理
async function markProcessed(fileName: string) {
  const markerFile = join(EXTRACTED_DIR, '.processed');
  const existing = existsSync(markerFile)
    ? require('fs').readFileSync(markerFile, 'utf-8')
    : '';
  await writeFile(markerFile, existing + fileName + '\n', 'utf-8');
}

// 写入知识到文件
async function writeKnowledge(knowledge: ExtractedKnowledge) {
  const safeTitle = knowledge.title.replace(/[\/\\:*?"<>|]/g, '-').substring(0, 50);
  const fileName = `${knowledge.type}_${safeTitle}.md`;

  const content = `# ${knowledge.title}

| 属性 | 值 |
|------|-----|
| 类型 | ${knowledge.type} |
| 可信度 | ${knowledge.credibility} |
| 来源 | ${knowledge.source_file} |
| 标签 | ${knowledge.tags.join(', ')} |
| 创建时间 | ${knowledge.created_at} |

## 核心发现

${knowledge.finding}

## 适用场景

${knowledge.applicability}

---
*由 Solar 知识抽取器自动生成*
`;

  // 写入到两个位置
  await writeFile(join(EXTRACTED_DIR, fileName), content, 'utf-8');
  await writeFile(join(EXTRACTED_IN_VAULT, fileName), content, 'utf-8');

  return fileName;
}

// 抽取单个文件的知识（简单规则抽取）
async function extractFile(fileName: string): Promise<ExtractedKnowledge[]> {
  let filePath = join(VAULT_PATH, fileName);
  if (!fileName.endsWith('.md')) {
    filePath += '.md';
  }

  if (!existsSync(filePath)) {
    console.log(`文件不存在: ${filePath}`);
    return [];
  }

  const content = await readFile(filePath, 'utf-8');
  const knowledge: ExtractedKnowledge[] = [];

  // 提取标题
  const titleMatch = content.match(/^#\s+(.+)$/m);
  const title = titleMatch ? titleMatch[1] : basename(fileName, '.md');

  // 提取摘要（第一段非空内容，过滤 frontmatter）
  const lines = content.split('\n');
  let inFrontmatter = false;
  let summary = '';

  for (const line of lines) {
    if (line.trim() === '---') {
      inFrontmatter = !inFrontmatter;
      continue;
    }
    if (inFrontmatter) continue;
    if (line.startsWith('#')) continue;
    if (line.trim() && !summary) {
      summary = line.trim();
    }
    if (summary && line.trim()) {
      summary += ' ' + line.trim();
    }
    if (summary.length > 300) break;
  }

  // 提取标签
  const tagMatches = content.match(/#[\w\u4e00-\u9fa5]+/g) || [];
  const tags = [...new Set(tagMatches.map(t => t.substring(1)))].slice(0, 5);

  // 生成知识条目
  if (summary.length > 50) {
    // 判断类型
    let type: KnowledgeType = 'reference';
    if (title.includes('研究') || title.includes('分析')) type = 'insight';
    if (title.includes('方法') || title.includes('实现')) type = 'method';
    if (title.includes('论文') || title.includes('Paper')) type = 'reference';
    if (title.includes('教训') || title.includes('踩坑')) type = 'lesson';

    knowledge.push({
      type,
      title,
      finding: summary.substring(0, 500),
      applicability: '从 Obsidian 笔记抽取',
      tags: tags.length > 0 ? tags : ['obsidian', 'imported'],
      source_file: fileName,
      credibility: 0.7,
      created_at: new Date().toISOString()
    });
  }

  return knowledge;
}

// 获取所有 md 文件
async function getAllMdFiles(): Promise<string[]> {
  const files: string[] = [];

  async function scan(dir: string) {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name.startsWith('.')) continue;
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        await scan(fullPath);
      } else if (entry.isFile() && entry.name.endsWith('.md')) {
        files.push(fullPath.replace(VAULT_PATH + '/', ''));
      }
    }
  }

  await scan(VAULT_PATH);
  return files;
}

// CLI
const [cmd, ...args] = process.argv.slice(2);

async function main() {
  await ensureDirs();

  switch (cmd) {
    case 'extract': {
      const [fileName] = args;
      if (!fileName) {
        console.log('用法: knowledge-extractor extract <文件名>');
        process.exit(1);
      }

      if (isProcessed(fileName)) {
        console.log(`✓ 已处理过: ${fileName}`);
        break;
      }

      console.log(`抽取: ${fileName}`);
      const knowledge = await extractFile(fileName);

      if (knowledge.length === 0) {
        console.log('  未抽取到知识');
      } else {
        for (const k of knowledge) {
          const file = await writeKnowledge(k);
          console.log(`  ✓ ${k.title} [${k.type}] → ${file}`);
        }
        await markProcessed(fileName);
      }
      break;
    }

    case 'extract-all': {
      console.log('扫描 Obsidian vault...\n');
      const files = await getAllMdFiles();
      console.log(`找到 ${files.length} 个文件\n`);

      let processed = 0;
      let skipped = 0;
      let extracted = 0;

      for (const file of files) {
        // 跳过 Extracted 目录
        if (file.startsWith('Extracted/')) continue;
        if (file.startsWith('Daily/')) continue;

        if (isProcessed(file)) {
          skipped++;
          continue;
        }

        console.log(`处理: ${file}`);
        const knowledge = await extractFile(file);

        if (knowledge.length > 0) {
          for (const k of knowledge) {
            await writeKnowledge(k);
            extracted++;
          }
          console.log(`  ✓ 抽取 ${knowledge.length} 条知识`);
          await markProcessed(file);
        }
        processed++;
      }

      console.log(`\n=== 完成 ===`);
      console.log(`处理: ${processed} | 跳过: ${skipped} | 抽取: ${extracted} 条知识`);
      console.log(`\n知识存储位置:`);
      console.log(`  - ${EXTRACTED_DIR}`);
      console.log(`  - ${EXTRACTED_IN_VAULT}`);
      break;
    }

    case 'status': {
      const files = await getAllMdFiles();
      let processed = 0;

      for (const file of files) {
        if (isProcessed(file)) {
          processed++;
        }
      }

      console.log(`Obsidian 知识抽取状态`);
      console.log(`---`);
      console.log(`Vault: ${VAULT_PATH}`);
      console.log(`总文件: ${files.length}`);
      console.log(`已处理: ${processed}`);
      console.log(`待处理: ${files.length - processed}`);

      // 查看已抽取的知识
      const extractedFiles = existsSync(EXTRACTED_DIR)
        ? (await readdir(EXTRACTED_DIR)).filter(f => f.endsWith('.md'))
        : [];

      console.log(`\n已抽取知识: ${extractedFiles.length} 条`);
      if (extractedFiles.length > 0) {
        console.log(`存储位置:`);
        console.log(`  - ${EXTRACTED_DIR}`);
        console.log(`  - ${EXTRACTED_IN_VAULT} (同步到 Obsidian)`);
      }
      break;
    }

    default:
      console.log(`
Obsidian 知识抽取器 v2

用法:
  knowledge-extractor extract <文件名>   抽取单个文件
  knowledge-extractor extract-all        抽取所有文件
  knowledge-extractor status             查看状态

知识存储:
  - ~/.solar/extracted_knowledge/
  - Obsidian: solar know/Extracted/

Vault: ${VAULT_PATH}
`);
  }
}

main().catch(console.error);
