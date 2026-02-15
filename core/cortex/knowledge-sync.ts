#!/usr/bin/env bun
/**
 * Knowledge Sync - 统一知识库同步引擎
 *
 * 功能：
 * 1. 从多种外部知识源同步数据到 Cortex
 * 2. 支持 Obsidian / Apple Notes / Notion / GitHub 等
 * 3. 自动解析、向量化、去重、入库
 *
 * 使用：
 *   bun knowledge-sync.ts obsidian
 *   bun knowledge-sync.ts apple-notes
 *   bun knowledge-sync.ts all
 */

import { Database } from 'bun:sqlite';
import { readdir, readFile, stat, writeFile } from 'fs/promises';
import { join, extname, basename } from 'path';
import { existsSync } from 'fs';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;

// ============================================================
// 类型定义
// ============================================================

interface KnowledgeSource {
  id: string;
  name: string;
  type: 'obsidian' | 'apple-notes' | 'notion' | 'github' | 'web' | 'pdf';
  path?: string;
  lastSync?: string;
  config?: Record<string, any>;
}

interface ParsedDocument {
  title: string;
  content: string;
  source_type: string;
  source_path: string;
  tags: string[];
  metadata: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

interface SyncResult {
  source: string;
  total: number;
  new: number;
  updated: number;
  skipped: number;
  errors: string[];
}

// ============================================================
// 知识源配置
// ============================================================

const KNOWLEDGE_SOURCES: KnowledgeSource[] = [
  {
    id: 'obsidian-solar',
    name: 'Obsidian Vault (Solar Know)',
    type: 'obsidian',
    path: `${process.env.HOME}/Solar/solar know`,
    config: {
      extensions: ['.md', '.markdown'],
      excludeFolders: ['.obsidian', '.trash', '.git'],
      includeFrontmatter: true,
    }
  },
  {
    id: 'obsidian-icloud',
    name: 'Obsidian Vault (iCloud)',
    type: 'obsidian',
    path: `${process.env.HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents`,
    config: {
      extensions: ['.md', '.markdown'],
      excludeFolders: ['.obsidian', '.trash', '.git'],
      includeFrontmatter: true,
    }
  },
  {
    id: 'apple-notes',
    name: 'Apple Notes',
    type: 'apple-notes',
    config: {
      useSqlite: true,
      dbPath: `${process.env.HOME}/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite`,
    }
  },
  {
    id: 'solar-rules',
    name: 'Solar Rules',
    type: 'obsidian',
    path: `${process.env.HOME}/.claude/rules`,
    config: {
      extensions: ['.md'],
      excludeFolders: [],
      includeFrontmatter: false,
    }
  },
];

// ============================================================
// 核心类
// ============================================================

class KnowledgeSyncEngine {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
    this.initTables();
  }

  private initTables(): void {
    // 同步状态表
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_sync_status (
        source_id TEXT PRIMARY KEY,
        source_name TEXT,
        source_type TEXT,
        last_sync DATETIME,
        total_docs INTEGER DEFAULT 0,
        status TEXT DEFAULT 'idle',
        config JSON
      )
    `);

    // 文档哈希表（用于增量同步）
    this.db.run(`
      CREATE TABLE IF NOT EXISTS cortex_doc_hashes (
        doc_path TEXT PRIMARY KEY,
        content_hash TEXT,
        source_type TEXT,
        synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // cortex_sources 表已存在，不需要创建
    console.log('✅ 数据库表初始化完成');
  }

  // ============================================================
  // Markdown 解析器
  // ============================================================

  private parseMarkdown(content: string, filePath: string): ParsedDocument {
    // 提取 frontmatter
    let metadata: Record<string, any> = {};
    let body = content;

    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
    if (frontmatterMatch) {
      const frontmatter = frontmatterMatch[1];
      body = frontmatterMatch[2];

      // 简单解析 YAML frontmatter
      for (const line of frontmatter.split('\n')) {
        const match = line.match(/^(\w+):\s*(.+)$/);
        if (match) {
          const key = match[1];
          let value: any = match[2].trim();
          // 处理数组
          if (value.startsWith('[') && value.endsWith(']')) {
            value = value.slice(1, -1).split(',').map(s => s.trim());
          }
          metadata[key] = value;
        }
      }
    }

    // 提取标题（从 frontmatter 或第一个 # 标题）
    let title = metadata.title as string || basename(filePath, extname(filePath));
    const titleMatch = body.match(/^#\s+(.+)$/m);
    if (titleMatch && !metadata.title) {
      title = titleMatch[1];
    }

    // 提取标签
    const tags: string[] = [];
    if (metadata.tags) {
      if (Array.isArray(metadata.tags)) {
        tags.push(...metadata.tags);
      } else {
        tags.push(String(metadata.tags));
      }
    }
    // 从内容提取 #tag 格式的标签
    const tagMatches = body.matchAll(/#(\w+)/g);
    for (const match of tagMatches) {
      if (!tags.includes(match[1])) {
        tags.push(match[1]);
      }
    }

    return {
      title,
      content: body.trim(),
      source_type: 'markdown',
      source_path: filePath,
      tags,
      metadata,
    };
  }

  // ============================================================
  // 内容哈希（用于增量同步）
  // ============================================================

  private async hashContent(content: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(content);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 16);
  }

  // ============================================================
  // 同步单个文档
  // ============================================================

  private async syncDocument(doc: ParsedDocument, sourceConfig: KnowledgeSource): Promise<'new' | 'updated' | 'skipped'> {
    const contentHash = await this.hashContent(doc.content);
    const citationKey = `${sourceConfig.id}:${doc.source_path.replace(/\//g, ':')}`.substring(0, 100);

    // 检查是否已存在且未变更
    const existing = this.db.query<{
      content_hash: string;
    }, [string]>(`
      SELECT content_hash FROM cortex_doc_hashes WHERE doc_path = ?
    `).get(doc.source_path);

    if (existing && existing.content_hash === contentHash) {
      return 'skipped';
    }

    // 提取摘要（前 500 字符或第一个段落）
    const finding = doc.content.substring(0, 500);

    // 计算可信度
    let credibility = 0.7; // 默认
    if (sourceConfig.type === 'obsidian') credibility = 0.8;
    if (doc.metadata.credibility) credibility = Number(doc.metadata.credibility);

    // 写入 cortex_sources (使用现有表结构)
    // 表字段: task_id, citation_key, title, url, finding, credibility, expert_model
    // 先检查是否存在相同的 citation_key
    const existingSource = this.db.query<{ source_id: number }, [string]>(`
      SELECT source_id FROM cortex_sources WHERE citation_key = ?
    `).get(citationKey);

    if (existingSource) {
      // 更新
      this.db.run(`
        UPDATE cortex_sources
        SET title = ?, url = ?, finding = ?, credibility = ?, expert_model = ?
        WHERE citation_key = ?
      `, [
        doc.title,
        `file://${doc.source_path}`,
        finding,
        credibility,
        `knowledge-sync:${sourceConfig.type}`,
        citationKey,
      ]);
    } else {
      // 插入
      this.db.run(`
        INSERT INTO cortex_sources (task_id, citation_key, title, url, finding, credibility, expert_model)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `, [
        `sync_${sourceConfig.id}`,
        citationKey,
        doc.title,
        `file://${doc.source_path}`,
        finding,
        credibility,
        `knowledge-sync:${sourceConfig.type}`,
      ]);
    }

    // 更新哈希表
    this.db.run(`
      INSERT INTO cortex_doc_hashes (doc_path, content_hash, source_type, synced_at)
      VALUES (?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(doc_path) DO UPDATE SET
        content_hash = excluded.content_hash,
        synced_at = CURRENT_TIMESTAMP
    `, [doc.source_path, contentHash, sourceConfig.type]);

    return existing ? 'updated' : 'new';
  }

  // ============================================================
  // Obsidian 同步
  // ============================================================

  async syncObsidian(sourceConfig: KnowledgeSource): Promise<SyncResult> {
    const result: SyncResult = {
      source: sourceConfig.name,
      total: 0,
      new: 0,
      updated: 0,
      skipped: 0,
      errors: [],
    };

    const vaultPath = sourceConfig.path;
    if (!vaultPath || !existsSync(vaultPath)) {
      result.errors.push(`Vault 路径不存在: ${vaultPath}`);
      return result;
    }

    const extensions = sourceConfig.config?.extensions || ['.md', '.markdown'];
    const excludeFolders = sourceConfig.config?.excludeFolders || ['.obsidian', '.trash'];

    // 递归读取所有 markdown 文件
    const scanDir = async (dir: string): Promise<string[]> => {
      const files: string[] = [];
      const entries = await readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = join(dir, entry.name);

        if (entry.isDirectory()) {
          if (!excludeFolders.includes(entry.name)) {
            files.push(...await scanDir(fullPath));
          }
        } else if (entry.isFile() && extensions.includes(extname(entry.name))) {
          files.push(fullPath);
        }
      }
      return files;
    };

    const files = await scanDir(vaultPath);
    result.total = files.length;

    console.log(`📁 扫描到 ${files.length} 个文件`);

    for (const filePath of files) {
      try {
        const content = await readFile(filePath, 'utf-8');
        const doc = this.parseMarkdown(content, filePath);
        const status = await this.syncDocument(doc, sourceConfig);

        if (status === 'new') result.new++;
        else if (status === 'updated') result.updated++;
        else result.skipped++;

      } catch (error) {
        result.errors.push(`${filePath}: ${error}`);
      }
    }

    // 更新同步状态
    this.db.run(`
      INSERT INTO cortex_sync_status (source_id, source_name, source_type, last_sync, total_docs, status)
      VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 'completed')
      ON CONFLICT(source_id) DO UPDATE SET
        last_sync = CURRENT_TIMESTAMP,
        total_docs = excluded.total_docs,
        status = 'completed'
    `, [sourceConfig.id, sourceConfig.name, sourceConfig.type, result.total]);

    return result;
  }

  // ============================================================
  // Solar Rules 同步
  // ============================================================

  async syncSolarRules(): Promise<SyncResult> {
    const sourceConfig = KNOWLEDGE_SOURCES.find(s => s.id === 'solar-rules')!;
    return this.syncObsidian(sourceConfig); // 复用 Obsidian 的逻辑
  }

  // ============================================================
  // 同步所有知识源
  // ============================================================

  async syncAll(): Promise<SyncResult[]> {
    const results: SyncResult[] = [];

    // 1. 同步 Solar Rules（内部知识）
    console.log('\n📚 同步 Solar Rules...');
    results.push(await this.syncSolarRules());

    // 2. 同步外部知识源
    for (const source of KNOWLEDGE_SOURCES) {
      if (source.id === 'solar-rules') continue; // 已处理

      console.log(`\n📚 同步 ${source.name}...`);

      if (!source.path || !existsSync(source.path)) {
        console.log(`  ⚠️ 跳过: 路径不存在 (${source.path})`);
        continue;
      }

      if (source.type === 'obsidian') {
        results.push(await this.syncObsidian(source));
      }
    }

    return results;
  }

  // ============================================================
  // 查询知识
  // ============================================================

  query(keyword: string, options?: {
    minCredibility?: number;
    limit?: number;
  }): Array<{
    title: string;
    finding: string;
    credibility: number;
    citation_key: string;
    url: string;
  }> {
    const minCred = options?.minCredibility || 0.5;
    const limit = options?.limit || 10;

    const sql = `
      SELECT title, finding, credibility, citation_key, url
      FROM cortex_sources
      WHERE credibility >= ?
        AND (title LIKE ? OR finding LIKE ?)
      ORDER BY credibility DESC, created_at DESC
      LIMIT ?
    `;

    return this.db.query<{
      title: string;
      finding: string;
      credibility: number;
      citation_key: string;
      url: string;
    }, any[]>(sql).all(minCred, `%${keyword}%`, `%${keyword}%`, limit);
  }

  // ============================================================
  // 状态报告
  // ============================================================

  status(): {
    sources: Array<{ source_id: string; source_name: string; total_docs: number; last_sync: string }>;
    totalDocs: number;
  } {
    const sources = this.db.query<{
      source_id: string;
      source_name: string;
      total_docs: number;
      last_sync: string;
    }, []>(`
      SELECT source_id, source_name, total_docs, last_sync
      FROM cortex_sync_status
      ORDER BY last_sync DESC
    `).all();

    const totalDocs = this.db.query<{ count: number }, []>(`
      SELECT COUNT(*) as count FROM cortex_sources
    `).get()?.count || 0;

    return { sources, totalDocs };
  }

  close(): void {
    this.db.close();
  }
}

// ============================================================
// CLI 入口
// ============================================================

async function main() {
  const args = process.argv.slice(2);
  const command = args[0] || 'status';

  const engine = new KnowledgeSyncEngine();

  try {
    switch (command) {
      case 'sync':
      case 'all':
        const results = await engine.syncAll();
        console.log('\n📊 同步结果:');
        for (const r of results) {
          console.log(`  ${r.source}: ${r.new} 新, ${r.updated} 更新, ${r.skipped} 跳过, ${r.errors.length} 错误`);
        }
        break;

      case 'obsidian':
        // 同步所有 Obsidian vaults
        const obsidianSources = KNOWLEDGE_SOURCES.filter(s => s.type === 'obsidian' && s.id !== 'solar-rules');
        for (const obsSource of obsidianSources) {
          if (!obsSource.path || !existsSync(obsSource.path)) {
            console.log(`  ⚠️ 跳过 ${obsSource.name}: 路径不存在`);
            continue;
          }
          console.log(`\n📚 同步 ${obsSource.name}...`);
          const obsResult = await engine.syncObsidian(obsSource);
          console.log(`  总计: ${obsResult.total}, 新增: ${obsResult.new}, 更新: ${obsResult.updated}`);
          if (obsResult.errors.length > 0) {
            console.log(`  错误: ${obsResult.errors.slice(0, 3).join('; ')}`);
          }
        }
        break;

      case 'rules':
        const rulesResult = await engine.syncSolarRules();
        console.log('\n📊 Solar Rules 同步结果:');
        console.log(`  总计: ${rulesResult.total}, 新增: ${rulesResult.new}, 更新: ${rulesResult.updated}`);
        break;

      case 'query':
        const keyword = args[1];
        if (!keyword) {
          console.log('用法: bun knowledge-sync.ts query <关键词>');
          break;
        }
        const queryResults = engine.query(keyword);
        console.log(`\n🔍 查询 "${keyword}" 结果 (${queryResults.length} 条):`);
        for (const r of queryResults) {
          console.log(`  [${r.credibility.toFixed(2)}] ${r.title}`);
          console.log(`    ${r.finding?.substring(0, 100) || '(无摘要)'}...`);
        }
        break;

      case 'status':
      default:
        const status = engine.status();
        console.log('\n📊 知识库状态:');
        console.log(`  总文档数: ${status.totalDocs}`);
        console.log('\n  已同步来源:');
        for (const s of status.sources) {
          console.log(`    - ${s.source_name}: ${s.total_docs} 篇 (上次同步: ${s.last_sync})`);
        }
        break;
    }
  } finally {
    engine.close();
  }
}

main();
