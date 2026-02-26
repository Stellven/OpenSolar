#!/usr/bin/env bun
/**
 * Obsidian 自动同步 Hook
 *
 * 被 insight-agent 或其他模块调用，自动将内容同步到 Obsidian
 */

import { writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';

const VAULT_PATH = process.env.HOME + '/Library/Mobile Documents/com~apple~CloudDocs/solar know';

interface SyncOptions {
  type: 'insight' | 'analysis' | 'daily' | 'note' | 'research';
  title: string;
  content: string;
  tags?: string[];
  source?: string;  // 来源链接或引用
}

const TYPE_DIRS: Record<string, string> = {
  insight: 'Insights',
  analysis: 'Analysis',
  daily: 'Daily',
  note: 'Inbox',
  research: 'Research'
};

/**
 * 同步内容到 Obsidian
 */
export async function syncToObsidian(options: SyncOptions): Promise<string> {
  const { type, title, content, tags = [], source } = options;

  // 确定目录
  const dir = join(VAULT_PATH, TYPE_DIRS[type] || 'Inbox');
  if (!existsSync(dir)) {
    await mkdir(dir, { recursive: true });
  }

  // 生成文件名
  const safeTitle = title.replace(/[\/\\:*?"<>|]/g, '-').substring(0, 100);
  const date = new Date().toISOString().split('T')[0];
  const fileName = `${safeTitle}.md`;
  const filePath = join(dir, fileName);

  // 生成完整内容
  const tagStr = ['solar', 'auto-sync', ...tags].map(t => `"${t}"`).join(', ');

  const fullContent = `---
title: "${title}"
created: ${date}
type: ${type}
tags: [${tagStr}]
${source ? `source: "${source}"` : ''}
---

# ${title}

${content}

---
*由 Solar 自动同步 @ ${new Date().toLocaleString('zh-CN')}*
`;

  await writeFile(filePath, fullContent, 'utf-8');

  return filePath;
}

/**
 * 同步 Insight 研究报告
 */
export async function syncInsightReport(topic: string, report: string, sources?: string[]): Promise<string> {
  return syncToObsidian({
    type: 'insight',
    title: `Insight: ${topic}`,
    content: report,
    tags: ['insight', 'research'],
    source: sources?.join('\n')
  });
}

/**
 * 同步分析结论
 */
export async function syncAnalysis(title: string, analysis: string): Promise<string> {
  return syncToObsidian({
    type: 'analysis',
    title,
    content: analysis,
    tags: ['analysis']
  });
}

// CLI
if (import.meta.main) {
  const [cmd, ...args] = process.argv.slice(2);

  if (cmd === 'insight') {
    const [topic, report] = args;
    if (!topic || !report) {
      console.log('用法: auto-sync insight "主题" "报告内容"');
      process.exit(1);
    }
    const path = await syncInsightReport(topic, report);
    console.log(`✓ Insight 已同步: ${path}`);
  } else if (cmd === 'analysis') {
    const [title, content] = args;
    if (!title || !content) {
      console.log('用法: auto-sync analysis "标题" "内容"');
      process.exit(1);
    }
    const path = await syncAnalysis(title, content);
    console.log(`✓ 分析已同步: ${path}`);
  } else {
    console.log(`
Obsidian 自动同步

用法:
  auto-sync insight "主题" "报告内容"
  auto-sync analysis "标题" "内容"

导出的函数:
  - syncToObsidian(options)
  - syncInsightReport(topic, report)
  - syncAnalysis(title, analysis)
`);
  }
}

export default { syncToObsidian, syncInsightReport, syncAnalysis };
