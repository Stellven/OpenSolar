#!/usr/bin/env bun
/**
 * Code Search - 代码搜索工具（优先用 Cortex 索引）
 *
 * 功能：
 * 1. 符号搜索：查找函数/类/接口定义
 * 2. 代码块定位：显示定义周围的代码
 * 3. 内容搜索：在文件内容中搜索
 */

import { Database } from 'bun:sqlite';
import { spawnSync } from 'child_process';
import { readFileSync } from 'fs';

const HOME = process.env.HOME || '/Users/sihaoli';
const DB_PATH = `${HOME}/.solar/solar.db`;

interface SearchResult {
  file_path: string;
  symbol_type: string;
  symbol_name: string;
  line_number: number;
  signature: string;
  docstring: string;
  project: string;
  code_block?: string;  // 新增：代码块
}

/**
 * 读取代码块（符号定义周围的代码）
 */
function readCodeBlock(filePath: string, lineNumber: number, contextLines: number = 20): string {
  try {
    const content = readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');
    const start = Math.max(0, lineNumber - contextLines - 1);
    const end = Math.min(lines.length, lineNumber + contextLines);

    return lines.slice(start, end)
      .map((line, i) => {
        const lineNum = start + i + 1;
        const marker = lineNum === lineNumber ? '>>>' : '   ';
        return `${marker} ${String(lineNum).padStart(4)} | ${line}`;
      })
      .join('\n');
  } catch {
    return `[无法读取文件: ${filePath}]`;
  }
}

function searchByIndex(query: string, options: { type?: string; project?: string; limit?: number; withCode?: boolean }): SearchResult[] {
  const db = new Database(DB_PATH);
  let sql = `SELECT c.* FROM code_index c JOIN code_index_fts fts ON c.id = fts.rowid WHERE code_index_fts MATCH $query`;
  const params: Record<string, any> = { $query: query, $limit: options.limit || 20 };

  if (options.type) {
    sql += ' AND c.symbol_type = $type';
    params.$type = options.type;
  }
  if (options.project) {
    sql += ' AND c.project LIKE $project';
    params.$project = `%${options.project}%`;
  }
  sql += ' ORDER BY bm25(code_index_fts) LIMIT $limit';

  try {
    const results = db.prepare(sql).all(params) as SearchResult[];
    // 如果需要代码块，读取并附加
    if (options.withCode) {
      for (const r of results) {
        r.code_block = readCodeBlock(r.file_path, r.line_number);
      }
    }
    return results;
  } catch {
    return [];
  }
}

function searchByGrep(query: string, path?: string): { file: string; line: number; content: string }[] {
  const searchPath = path || HOME;
  const result = spawnSync('grep', ['-rn', '--color=never', '--include=*.ts', '--include=*.js', '--include=*.py', query, searchPath], { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
  if (result.status !== 0 || !result.stdout) return [];
  return result.stdout.split('\n').slice(0, 50).filter(Boolean).map(line => {
    const [file, lineNum, ...content] = line.split(':');
    return { file, line: parseInt(lineNum), content: content.join(':') };
  });
}

export async function searchCode(query: string, options: { type?: string; project?: string; path?: string; useFallback?: boolean; limit?: number; withCode?: boolean } = {}): Promise<{ source: 'index' | 'grep'; results: any[]; duration: number }> {
  const start = Date.now();
  const indexResults = searchByIndex(query, { type: options.type, project: options.project, limit: options.limit || 20, withCode: options.withCode });
  if (indexResults.length > 0) return { source: 'index', results: indexResults, duration: Date.now() - start };
  if (options.useFallback !== false) {
    const grepResults = searchByGrep(query, options.path);
    return { source: 'grep', results: grepResults, duration: Date.now() - start };
  }
  return { source: 'index', results: [], duration: Date.now() - start };
}

export async function findDefinition(symbolName: string, withCode: boolean = false): Promise<SearchResult | null> {
  const results = searchByIndex(symbolName, { limit: 1, withCode });
  return results[0] || null;
}

/**
 * 导出给 Claude Code 使用的函数
 */
export function getCodeBlock(filePath: string, lineNumber: number, context: number = 20): string {
  return readCodeBlock(filePath, lineNumber, context);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log('Code Search - 代码搜索（优先用 Cortex 索引）');
    console.log('');
    console.log('用法: code-search <查询> [选项]');
    console.log('');
    console.log('选项:');
    console.log('  --type <类型>    符号类型 (function/class/interface)');
    console.log('  --project <项目> 项目名称过滤');
    console.log('  --code           显示代码块（推荐）');
    console.log('  --grep           强制用 grep 搜索');
    console.log('');
    console.log('示例:');
    console.log('  code-search "database" --code');
    console.log('  code-search "callLLM" --type function --code');
    process.exit(0);
  }

  const query = args.find(a => !a.startsWith('--')) || '';
  const typeIdx = args.indexOf('--type');
  const projectIdx = args.indexOf('--project');
  const useGrep = args.includes('--grep');
  const withCode = args.includes('--code');

  const options = {
    type: typeIdx >= 0 ? args[typeIdx + 1] : undefined,
    project: projectIdx >= 0 ? args[projectIdx + 1] : undefined,
    useFallback: !useGrep,
    withCode,
  };

  if (useGrep) {
    const start = Date.now();
    const results = searchByGrep(query);
    console.log(`\n🔍 Grep "${query}" (${Date.now() - start}ms):\n`);
    for (const r of results.slice(0, 20)) {
      console.log(`  ${r.file}:${r.line}: ${r.content.trim().slice(0, 60)}`);
    }
  } else {
    const result = await searchCode(query, options);
    const icon = result.source === 'index' ? '📇' : '🔍';

    console.log(`\n${icon} ${result.source} "${query}" (${result.duration}ms):\n`);

    for (const r of result.results) {
      if ('symbol_name' in r) {
        console.log(`━━━ ${r.symbol_type} ${r.symbol_name} ━━━`);
        console.log(`📁 ${r.file_path}:${r.line_number}`);
        if (r.docstring) console.log(`📝 ${r.docstring.slice(0, 80)}`);
        if (r.code_block) {
          console.log(`\n${r.code_block}\n`);
        } else {
          console.log(`   ${r.signature}`);
        }
        console.log();
      } else {
        console.log(`  ${r.file}:${r.line}: ${r.content.trim().slice(0, 60)}`);
      }
    }
  }
}

main().catch(console.error);
