/**
 * Solar Cortex - Data Ledger
 *
 * 数据账本管理器
 * 铁律: 先查账本，再查数据，再思考计算
 *
 * @version 1.0.0
 * @created 2026-02-06
 */

import { Database } from 'bun:sqlite';
import { execSync } from 'child_process';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

interface LedgerEntry {
  ledger_id: number;
  category: string;
  source_type: string;
  source_name: string;
  description: string;
  record_count: number;
  status: string;
  notes: string;
  last_checked: string;
}

interface LedgerSummary {
  category: string;
  source_count: number;
  total_records: number;
  critical_issues: number;
  warnings: number;
}

export class DataLedger {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
  }

  // 获取账本摘要
  getSummary(): LedgerSummary[] {
    return this.db.query<LedgerSummary, []>(`
      SELECT * FROM v_data_ledger_summary
    `).all();
  }

  // 获取问题列表
  getIssues(): LedgerEntry[] {
    return this.db.query<LedgerEntry, []>(`
      SELECT * FROM v_data_ledger_issues
    `).all();
  }

  // 获取特定类别的数据源
  getByCategory(category: string): LedgerEntry[] {
    return this.db.query<LedgerEntry, [string]>(`
      SELECT * FROM sys_data_ledger
      WHERE category = ? AND status = 'active'
      ORDER BY record_count DESC
    `).all(category);
  }

  // 刷新单个表的记录数
  refreshTable(tableName: string): void {
    try {
      const count = this.db.query<{ cnt: number }, []>(`
        SELECT COUNT(*) as cnt FROM ${tableName}
      `).get()?.cnt || 0;

      this.db.run(`
        UPDATE sys_data_ledger
        SET record_count = ?, last_checked = datetime('now'), updated_at = datetime('now')
        WHERE source_type = 'table' AND source_name = ?
      `, [count, tableName]);
    } catch (e) {
      // 表可能不存在
    }
  }

  // 刷新所有表
  refreshAll(): { updated: number; errors: string[] } {
    const tables = this.db.query<{ source_name: string }, []>(`
      SELECT source_name FROM sys_data_ledger WHERE source_type = 'table'
    `).all();

    let updated = 0;
    const errors: string[] = [];

    for (const { source_name } of tables) {
      try {
        this.refreshTable(source_name);
        updated++;
      } catch (e: any) {
        errors.push(`${source_name}: ${e.message}`);
      }
    }

    // 刷新 JSONL 文件统计
    try {
      const result = execSync(`find ~/.claude/projects -name "*.jsonl" -type f 2>/dev/null | wc -l`).toString().trim();
      const fileCount = parseInt(result) || 0;
      this.db.run(`
        UPDATE sys_data_ledger
        SET record_count = ?, last_checked = datetime('now')
        WHERE source_name LIKE '%jsonl%'
      `, [fileCount]);
    } catch (e) {
      errors.push('JSONL files: failed to count');
    }

    return { updated, errors };
  }

  // 登记新数据源
  register(entry: Partial<LedgerEntry>): void {
    this.db.run(`
      INSERT OR REPLACE INTO sys_data_ledger
      (category, source_type, source_name, description, record_count, status, notes, last_checked)
      VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `, [
      entry.category,
      entry.source_type,
      entry.source_name,
      entry.description || '',
      entry.record_count || 0,
      entry.status || 'active',
      entry.notes || ''
    ]);
  }

  // 打印摘要 (CLI)
  printSummary(): void {
    console.log('\n📒 Solar 数据账本摘要\n');
    console.log('─'.repeat(70));

    const summary = this.getSummary();
    console.log('类别\t\t数据源\t记录数\t\t🔴严重\t🟡警告');
    console.log('─'.repeat(70));

    for (const s of summary) {
      const records = s.total_records.toLocaleString().padStart(10);
      console.log(`${s.category}\t\t${s.source_count}\t${records}\t\t${s.critical_issues}\t${s.warnings}`);
    }

    console.log('─'.repeat(70));

    // 打印问题
    const issues = this.getIssues();
    if (issues.length > 0) {
      console.log('\n⚠️ 需要关注的问题:\n');
      for (const issue of issues) {
        console.log(`  [${issue.category}] ${issue.source_name}: ${issue.notes}`);
      }
    }
  }

  close() {
    this.db.close();
  }
}

// ============================================================================
// CLI
// ============================================================================

if (import.meta.main) {
  const ledger = new DataLedger();
  const cmd = process.argv[2];

  switch (cmd) {
    case 'summary':
    case undefined:
      ledger.printSummary();
      break;

    case 'issues':
      console.log('\n⚠️ 数据账本问题列表:\n');
      const issues = ledger.getIssues();
      for (const issue of issues) {
        console.log(`[${issue.category}] ${issue.source_name}`);
        console.log(`  记录数: ${issue.record_count}`);
        console.log(`  问题: ${issue.notes}`);
        console.log();
      }
      break;

    case 'refresh':
      console.log('刷新数据账本...');
      const result = ledger.refreshAll();
      console.log(`✓ 已更新 ${result.updated} 个数据源`);
      if (result.errors.length > 0) {
        console.log('错误:', result.errors.join(', '));
      }
      ledger.printSummary();
      break;

    case 'category':
      const cat = process.argv[3];
      if (!cat) {
        console.log('Usage: bun ledger.ts category <类别>');
        console.log('类别: 轨迹/对话/本体/记忆/反馈/资源/路由/索引');
        break;
      }
      const entries = ledger.getByCategory(cat);
      console.log(`\n${cat} 类数据源:\n`);
      for (const e of entries) {
        console.log(`  ${e.source_name}: ${e.record_count} 条 - ${e.notes}`);
      }
      break;

    default:
      console.log(`
Usage: bun ledger.ts <command>

Commands:
  summary     - 显示账本摘要 (默认)
  issues      - 显示问题列表
  refresh     - 刷新所有数据源的记录数
  category <类别> - 查看特定类别

类别: 轨迹/对话/本体/记忆/反馈/资源/路由/索引

铁律: 先查账本 → 再查数据 → 再思考 → 再计算
      `);
  }

  ledger.close();
}

export default DataLedger;
