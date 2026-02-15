#!/usr/bin/env bun
/**
 * Report Template Writer
 *
 * 为深度洞察报告生成结构化目录与元数据文件
 * 集成到 insight-agent-v2.ts 的三层持久化系统
 *
 * 核心功能:
 * - 初始化 REPORT 结构 (PHASES/, NOTES/, SOURCES.md, STATE.md)
 * - 从 session.references 生成 SOURCES.md
 * - 跟踪 7 阶段进度到 STATE.md
 * - 迁移旧的扁平文件到结构化布局
 */

import { existsSync, mkdirSync, writeFileSync, readdirSync, readFileSync, renameSync } from 'fs';
import { join } from 'path';

export interface Reference {
  title: string;
  summary: string;
  source: string;
  relevance: number;
  timestamp?: string;
}

export interface StateData {
  topic: string;
  currentPhase: string;
  progress: {
    done: string[];
    inProgress: string;
    blocked?: string[];
  };
  nextActions: string[];
}

export interface PhaseOutput {
  phaseNum: number;
  phaseName: string;
  content: string;
  timestamp?: string;
}

/**
 * 报告结构管理器
 *
 * 目录结构:
 * ~/.solar/insight-reports/<session_id>/
 *   ├── PHASES/
 *   │   ├── 1-planning.md
 *   │   ├── 2-outlining.md
 *   │   ├── 4-writing/
 *   │   │   ├── chapter-1.md
 *   │   │   └── chapter-2.md
 *   │   ├── 5-review/
 *   │   │   ├── eval-1.md
 *   │   │   └── eval-2.md
 *   │   └── 6-synthesis.md
 *   ├── SOURCES.md
 *   ├── STATE.md
 *   ├── NOTES/
 *   └── final-report.md
 */
export class ReportStructure {
  private sessionId: string;
  private baseDir: string;

  constructor(sessionId: string, baseDir: string = `${process.env.HOME}/.solar/insight-reports`) {
    this.sessionId = sessionId;
    this.baseDir = join(baseDir, sessionId);
    this.initStructure();
  }

  /**
   * 初始化报告目录结构
   */
  private initStructure(): void {
    const dirs = [
      this.baseDir,
      join(this.baseDir, 'PHASES'),
      join(this.baseDir, 'PHASES', '4-writing'),
      join(this.baseDir, 'PHASES', '5-review'),
      join(this.baseDir, 'NOTES')
    ];

    dirs.forEach(dir => {
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
      }
    });
  }

  /**
   * 生成 SOURCES.md
   * 从 Phase 1 Planning 收集的 references 生成参考文献列表
   */
  writeSources(references: Reference[]): void {
    if (!references || references.length === 0) {
      return;
    }

    // 按相关性排序
    const sorted = [...references].sort((a, b) => (b.relevance || 0) - (a.relevance || 0));

    const content = `# 数据来源与参考文献

## 数据资产 (Cortex)

${this.formatCortexSources(sorted.filter(r => r.source.includes('cortex') || r.source.includes('favorites')))}

## 网络搜索 (WebSearch)

${this.formatWebSources(sorted.filter(r => r.source.includes('web') || r.source.includes('search')))}

## 相关性排序

| 标题 | 相关性 | 来源 |
|------|--------|------|
${sorted.map(r => `| ${r.title} | ${(r.relevance * 100).toFixed(0)}% | ${r.source} |`).join('\n')}

---

*生成时间: ${new Date().toISOString()}*
*会话 ID: ${this.sessionId}*
`;

    writeFileSync(join(this.baseDir, 'SOURCES.md'), content, 'utf-8');
  }

  private formatCortexSources(refs: Reference[]): string {
    if (refs.length === 0) return '*(无)*';
    return refs.map((r, i) => `${i + 1}. **${r.title}**\n   - ${r.summary}\n   - 来源: ${r.source}`).join('\n\n');
  }

  private formatWebSources(refs: Reference[]): string {
    if (refs.length === 0) return '*(无)*';
    return refs.map((r, i) => `${i + 1}. [${r.title}](${r.source})\n   - ${r.summary}`).join('\n\n');
  }

  /**
   * 写入 STATE.md
   * 跟踪 7 阶段进度，对抗上下文压缩
   */
  writeState(data: StateData): void {
    const phaseMap: Record<string, string> = {
      'CREATED': '0/7 - 已创建',
      'PLANNING': '1/7 - 规划中',
      'OUTLINE': '2/7 - 大纲',
      'SCHEDULING': '3/7 - 调度',
      'WRITING': '4/7 - 写作',
      'REVIEW': '5/7 - 审查',
      'SYNTHESIS': '6/7 - 综合',
      'COMPLETED': '7/7 - 完成'
    };

    const progress = Math.round((data.progress.done.length / 7) * 100);

    const content = `# Mission
深度洞察报告: ${data.topic}

# Constraints
- 7 阶段流程: Planning → Outline → Scheduling → Writing → Review → Synthesis → Completed
- 4 专家团队: GLM-5 (综合) / Gemini 2.5 Pro (撰写/审查) / DeepSeek R1 (挑战) / DeepSeek V3 (撰写)
- 三层持久化: Cortex + SQLite + FileSystem
- 每阶段输出到 PHASES/<stage>.md

# Current Plan
当前阶段: ${phaseMap[data.currentPhase] || data.currentPhase}

# Progress
- Done: ${data.progress.done.join(', ')}
- In-Progress: ${data.progress.inProgress}
${data.progress.blocked && data.progress.blocked.length > 0 ? `- Blocked: ${data.progress.blocked.join(', ')}` : ''}

进度: ${'█'.repeat(Math.floor(progress / 10))}${'░'.repeat(10 - Math.floor(progress / 10))} ${progress}%

# Next Actions
${data.nextActions.map(a => `- [ ] ${a}`).join('\n')}

---

*更新时间: ${new Date().toISOString()}*
*会话 ID: ${this.sessionId}*
`;

    writeFileSync(join(this.baseDir, 'STATE.md'), content, 'utf-8');
  }

  /**
   * 写入阶段输出到 PHASES/<num>-<name>.md
   */
  writePhase(output: PhaseOutput): void {
    const { phaseNum, phaseName, content } = output;

    // Phase 4 (writing) 和 Phase 5 (review) 的输出放到子目录
    let targetPath: string;
    if (phaseNum === 4) {
      // chapter-*.md 已经在 4-writing/ 子目录
      return; // 由 saveChapterToFile 处理
    } else if (phaseNum === 5) {
      // eval-*.md 已经在 5-review/ 子目录
      return; // 由评审流程处理
    } else {
      targetPath = join(this.baseDir, 'PHASES', `${phaseNum}-${phaseName}.md`);
    }

    const wrappedContent = `# Phase ${phaseNum}: ${phaseName}

${content}

---

*生成时间: ${output.timestamp || new Date().toISOString()}*
*会话 ID: ${this.sessionId}*
`;

    writeFileSync(targetPath, wrappedContent, 'utf-8');
  }

  /**
   * 迁移旧的扁平文件到结构化布局
   *
   * 旧布局:
   *   planning.md, outline_*.md, chapter-*.md, final-report.md
   *
   * 新布局:
   *   PHASES/1-planning.md, PHASES/2-outlining.md, PHASES/4-writing/chapter-*.md, final-report.md
   */
  migrateExistingFiles(): void {
    // 检查是否已经迁移 (如果 PHASES/ 里有文件就不迁移)
    const phasesDir = join(this.baseDir, 'PHASES');
    if (existsSync(phasesDir)) {
      const files = readdirSync(phasesDir);
      if (files.length > 0) {
        console.log(`[ReportStructure] Already migrated, skipping.`);
        return;
      }
    }

    const files = existsSync(this.baseDir) ? readdirSync(this.baseDir) : [];

    // 迁移 planning.md
    if (files.includes('planning.md')) {
      const oldPath = join(this.baseDir, 'planning.md');
      const newPath = join(this.baseDir, 'PHASES', '1-planning.md');
      if (!existsSync(newPath)) {
        renameSync(oldPath, newPath);
        console.log(`[ReportStructure] Migrated planning.md → PHASES/1-planning.md`);
      }
    }

    // 迁移 outline_*.md
    const outlineFiles = files.filter(f => f.startsWith('outline_') && f.endsWith('.md'));
    if (outlineFiles.length > 0) {
      const mergedOutline = outlineFiles
        .map(f => readFileSync(join(this.baseDir, f), 'utf-8'))
        .join('\n\n---\n\n');
      writeFileSync(join(this.baseDir, 'PHASES', '2-outlining.md'), mergedOutline, 'utf-8');
      console.log(`[ReportStructure] Migrated ${outlineFiles.length} outline files → PHASES/2-outlining.md`);
    }

    // 迁移 chapter-*.md
    const chapterFiles = files.filter(f => f.startsWith('chapter-') && f.endsWith('.md'));
    if (chapterFiles.length > 0) {
      const writingDir = join(this.baseDir, 'PHASES', '4-writing');
      chapterFiles.forEach(f => {
        const oldPath = join(this.baseDir, f);
        const newPath = join(writingDir, f);
        if (!existsSync(newPath)) {
          renameSync(oldPath, newPath);
        }
      });
      console.log(`[ReportStructure] Migrated ${chapterFiles.length} chapter files → PHASES/4-writing/`);
    }

    // final-report.md 保持在根目录
  }

  /**
   * 获取报告目录路径
   */
  getBaseDir(): string {
    return this.baseDir;
  }
}

/**
 * CLI 入口 (可选，用于测试)
 */
if (import.meta.main) {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log('Usage: bun report-template-writer.ts <session_id> [action]');
    console.log('Actions: init, migrate, test');
    process.exit(1);
  }

  const sessionId = args[0];
  const action = args[1] || 'init';
  const report = new ReportStructure(sessionId);

  switch (action) {
    case 'init':
      console.log(`[OK] Initialized report structure at ${report.getBaseDir()}`);
      break;
    case 'migrate':
      report.migrateExistingFiles();
      console.log(`[OK] Migrated existing files`);
      break;
    case 'test':
      // 测试写入
      report.writeSources([
        { title: 'Test Source 1', summary: 'Summary 1', source: 'cortex', relevance: 0.9 },
        { title: 'Test Source 2', summary: 'Summary 2', source: 'web-search', relevance: 0.7 }
      ]);
      report.writeState({
        topic: 'Test Topic',
        currentPhase: 'PLANNING',
        progress: { done: ['CREATED'], inProgress: 'PLANNING', blocked: [] },
        nextActions: ['Complete planning', 'Generate outline']
      });
      report.writePhase({ phaseNum: 1, phaseName: 'planning', content: 'Test planning content' });
      console.log(`[OK] Test files written to ${report.getBaseDir()}`);
      break;
    default:
      console.error(`Unknown action: ${action}`);
      process.exit(1);
  }
}
