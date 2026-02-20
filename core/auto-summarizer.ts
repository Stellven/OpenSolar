#!/usr/bin/env bun
/**
 * Auto Summarizer - 自动摘要器
 *
 * 功能：
 * 1. 读取最近 N 条对话记录
 * 2. 调用牛马生成五段式摘要
 * 3. 写入 STATE.md (增量更新)
 * 4. 写入 sys_favorites (重要结论)
 *
 * 触发方式：
 * - Hook 触发: context-monitor.sh
 * - 手动触发: bun auto-summarizer.ts
 * - 外部监控: launchd 定时调用
 */

import { execSync } from 'child_process';
import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'fs';
import { join } from 'path';

const HOME = process.env.HOME || '/Users/sihaoli';
const SOLAR_DB = `${HOME}/.solar/solar.db`;
const STATE_FILE = `${HOME}/.claude/.solar/STATE.md`;
const LOG_DIR = `${HOME}/.claude/.solar/LOG`;

// 配置
const CONFIG = {
  maxMessages: 50,           // 读取最近多少条消息
  summaryModel: 'deepseek-v3', // 用 DeepSeek V3 做摘要（便宜中文好）
  contextThreshold: 0.8,      // 80% 阈值
  minInterval: 10 * 60 * 1000, // 最少间隔 10 分钟
};

// 五段式摘要 Prompt
const SUMMARY_PROMPT = `你是一个专业的对话摘要助手。请分析以下对话，生成结构化的五段式摘要。

输出格式（严格按此格式）：

## Mission
[一句话目标，可验收口径]

## Constraints
- [约束1]
- [约束2]

## Current Plan
1) [计划1]
2) [计划2]
3) [计划3]

## Decisions
- [日期] [决策内容]：[原因]

## Progress
- Done:
  - [已完成事项1]
  - [已完成事项2]
- In-Progress: [当前进行中]
- Blocked: [阻塞项，无则写"无"]

## Next Actions
- [ ] [具体可执行命令1]
- [ ] [具体可执行命令2]

## 恢复指令
Compact后请执行: cat ~/.claude/.solar/STATE.md

---

对话内容：
{{CONVERSATION}}

请生成五段式摘要：`;

interface Message {
  role: string;
  content: string;
  timestamp?: string;
}

interface Summary {
  mission: string;
  constraints: string[];
  plan: string[];
  decisions: string[];
  progress: {
    done: string[];
    inProgress: string;
    blocked: string;
  };
  nextActions: string[];
}

/**
 * 获取最近的会话文件
 */
function getLatestSessionFile(): string | null {
  const projectDir = `${HOME}/.claude/projects/-Users-sihaoli`;
  try {
    const files = execSync(`ls -t "${projectDir}"/*.jsonl 2>/dev/null | head -1`, {
      encoding: 'utf-8'
    }).trim();
    return files || null;
  } catch {
    return null;
  }
}

/**
 * 读取最近 N 条消息
 */
function readRecentMessages(sessionFile: string, maxMessages: number): Message[] {
  const messages: Message[] = [];

  try {
    // 读取文件最后部分（更高效）
    const content = execSync(`tail -n ${maxMessages * 3} "${sessionFile}"`, {
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024 // 10MB buffer
    });

    // 解析 JSONL
    const lines = content.split('\n').filter(l => l.trim());
    for (const line of lines) {
      try {
        const json = JSON.parse(line);
        if (json.message?.content) {
          const role = json.message.role || 'unknown';
          let content = '';

          if (typeof json.message.content === 'string') {
            content = json.message.content;
          } else if (Array.isArray(json.message.content)) {
            content = json.message.content
              .filter((c: any) => c.type === 'text')
              .map((c: any) => c.text)
              .join('\n');
          }

          if (content && content.length > 10) {
            messages.push({
              role,
              content: content.slice(0, 2000), // 截断长消息
              timestamp: json.timestamp
            });
          }
        }
      } catch {
        // 解析失败，跳过
      }
    }

    // 只保留最近 N 条
    return messages.slice(-maxMessages);
  } catch (error) {
    console.error('读取会话文件失败:', error);
    return [];
  }
}

/**
 * 调用牛马生成摘要
 */
async function generateSummary(messages: Message[]): Promise<string | null> {
  if (messages.length === 0) {
    console.log('没有消息可摘要');
    return null;
  }

  // 构建对话文本
  const conversationText = messages.map(m => {
    const role = m.role === 'user' ? '👤 用户' : '🤖 Solar';
    return `${role}:\n${m.content.slice(0, 1000)}\n`;
  }).join('\n---\n');

  const prompt = SUMMARY_PROMPT.replace('{{CONVERSATION}}', conversationText);

  try {
    // 使用 brain-router 调用牛马
    // 注意：需要传递环境变量
    const env = {
      ...process.env,
      GLM_API_KEY: process.env.GLM_API_KEY || '',
      GEMINI_API_KEY: process.env.GEMINI_API_KEY || '',
      DEEPSEEK_API_KEY: process.env.DEEPSEEK_API_KEY || '',
      OPENAI_API_KEY: process.env.OPENAI_API_KEY || '',
    };

    const result = execSync(
      `bun "${HOME}/.claude/core/brain-router/call.ts" "${CONFIG.summaryModel}" "${encodeURIComponent(prompt.slice(0, 8000))}"`,
      { encoding: 'utf-8', timeout: 60000, maxBuffer: 1024 * 1024, env }
    );

    // 解析结果
    const jsonMatch = result.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const json = JSON.parse(jsonMatch[0]);
      return json.content || json.response || result;
    }

    return result;
  } catch (error) {
    console.error('调用牛马失败:', error);

    // 降级方案：生成简单摘要
    return generateFallbackSummary(messages);
  }
}

/**
 * 降级方案：简单摘要（不用牛马）
 */
function generateFallbackSummary(messages: Message[]): string {
  const userMessages = messages.filter(m => m.role === 'user');
  const lastUserMsg = userMessages[userMessages.length - 1]?.content || '无';

  return `## Mission
${lastUserMsg.slice(0, 100)}

## Constraints
- 自动生成（降级模式）

## Current Plan
1) 继续当前任务

## Decisions
- [${new Date().toISOString().split('T')[0]}] 触发自动摘要

## Progress
- Done:
  - [自动记录的任务]
- In-Progress: 当前任务
- Blocked: 无

## Next Actions
- [ ] 继续执行任务`;
}

/**
 * 解析五段式摘要
 */
function parseSummary(text: string): Summary | null {
  try {
    const sections = {
      mission: '',
      constraints: [] as string[],
      plan: [] as string[],
      decisions: [] as string[],
      progress: { done: [] as string[], inProgress: '', blocked: '' },
      nextActions: [] as string[]
    };

    // 解析 Mission
    const missionMatch = text.match(/## Mission\s*\n([\s\S]*?)(?=\n##|$)/i);
    if (missionMatch) sections.mission = missionMatch[1].trim();

    // 解析 Constraints
    const constraintsMatch = text.match(/## Constraints\s*\n([\s\S]*?)(?=\n##|$)/i);
    if (constraintsMatch) {
      sections.constraints = constraintsMatch[1]
        .split('\n')
        .filter(l => l.trim().startsWith('-'))
        .map(l => l.replace(/^-\s*/, '').trim());
    }

    // 解析 Plan
    const planMatch = text.match(/## Current Plan\s*\n([\s\S]*?)(?=\n##|$)/i);
    if (planMatch) {
      sections.plan = planMatch[1]
        .split('\n')
        .filter(l => /^\d+\)/.test(l.trim()))
        .map(l => l.replace(/^\d+\)\s*/, '').trim());
    }

    // 解析 Decisions
    const decisionsMatch = text.match(/## Decisions\s*\n([\s\S]*?)(?=\n##|$)/i);
    if (decisionsMatch) {
      sections.decisions = decisionsMatch[1]
        .split('\n')
        .filter(l => l.trim().startsWith('-'))
        .map(l => l.replace(/^-\s*/, '').trim());
    }

    // 解析 Progress
    const progressMatch = text.match(/## Progress\s*\n([\s\S]*?)(?=\n##|$)/i);
    if (progressMatch) {
      const progressText = progressMatch[1];

      const doneMatch = progressText.match(/Done:\s*([\s\S]*?)(?=In-Progress|Blocked|- In-Progress|$)/i);
      if (doneMatch) {
        sections.progress.done = doneMatch[1]
          .split('\n')
          .filter(l => l.trim().startsWith('-'))
          .map(l => l.replace(/^-\s*/, '').trim());
      }

      const inProgressMatch = progressText.match(/In-Progress:\s*([^\n]+)/i);
      if (inProgressMatch) sections.progress.inProgress = inProgressMatch[1].trim();

      const blockedMatch = progressText.match(/Blocked:\s*([^\n]+)/i);
      if (blockedMatch) sections.progress.blocked = blockedMatch[1].trim();
    }

    // 解析 Next Actions
    const actionsMatch = text.match(/## Next Actions\s*\n([\s\S]*?)(?=\n##|$)/i);
    if (actionsMatch) {
      sections.nextActions = actionsMatch[1]
        .split('\n')
        .filter(l => l.trim().startsWith('- [ ]'))
        .map(l => l.replace(/^- \[ \]\s*/, '').trim());
    }

    return sections;
  } catch {
    return null;
  }
}

/**
 * 合并摘要到 STATE.md
 */
function mergeToState(summary: Summary): boolean {
  if (!existsSync(STATE_FILE)) {
    console.log('STATE.md 不存在，创建新文件');
    writeFileSync(STATE_FILE, formatSummaryAsMarkdown(summary));
    return true;
  }

  try {
    const existing = readFileSync(STATE_FILE, 'utf-8');

    // 解析现有 STATE.md
    const existingSummary = parseSummary(existing);

    // 合并策略：
    // - Mission: 保留现有的（更准确）
    // - Constraints: 合并去重
    // - Plan: 保留现有的（可能已更新）
    // - Decisions: 合并去重
    // - Progress: 更新（摘要中有新进展）
    // - Next Actions: 更新

    const merged: Summary = {
      mission: existingSummary?.mission || summary.mission,
      constraints: [...new Set([...(existingSummary?.constraints || []), ...summary.constraints])],
      plan: existingSummary?.plan || summary.plan,
      decisions: [...new Set([...(existingSummary?.decisions || []), ...summary.decisions])],
      progress: {
        done: [...new Set([...(existingSummary?.progress.done || []), ...summary.progress.done])],
        inProgress: summary.progress.inProgress || existingSummary?.progress.inProgress || '',
        blocked: summary.progress.blocked || existingSummary?.progress.blocked || ''
      },
      nextActions: summary.nextActions.length > 0 ? summary.nextActions : (existingSummary?.nextActions || [])
    };

    // 写入
    writeFileSync(STATE_FILE, formatSummaryAsMarkdown(merged));
    console.log('✅ STATE.md 已更新');
    return true;
  } catch (error) {
    console.error('合并 STATE.md 失败:', error);
    return false;
  }
}

/**
 * 格式化摘要为 Markdown
 */
function formatSummaryAsMarkdown(summary: Summary): string {
  const now = new Date().toISOString().split('T')[0];

  return `# Mission
${summary.mission || '待定义'}

# Constraints
${summary.constraints.map(c => `- ${c}`).join('\n') || '- 无特殊约束'}

# Current Plan (Top-5)
${summary.plan.slice(0, 5).map((p, i) => `${i + 1}) ${p}`).join('\n') || '1) 待规划'}

# Decisions (Why)
${summary.decisions.map(d => `- ${d}`).join('\n') || `- [${now}] 初始状态`}

# Progress
- Done:
${summary.progress.done.map(d => `  - ${d}`).join('\n') || '  - 无'}
- In-Progress: ${summary.progress.inProgress || '无'}
- Blocked: ${summary.progress.blocked || '无'}

# Next Actions (Exact)
${summary.nextActions.map(a => `- [ ] ${a}`).join('\n') || '- [ ] 待定义'}

---

## 🔄 恢复指令 (Compact 后必读)

\`\`\`bash
# 如果是 compact 后或新会话，执行以下命令恢复态势：
cat ~/.claude/.solar/STATE.md
\`\`\`

**关键记忆点：**
- Mission = 当前目标
- Next Actions = 下一步要做什么
- 上次进度 = Progress.Done

---
*Last updated: ${new Date().toISOString()}*
*Auto-generated by auto-summarizer.ts*
`;
}

/**
 * 写入日志
 */
function logOperation(action: string, details: string): void {
  const logFile = join(LOG_DIR, 'cmd.md');
  const timestamp = new Date().toISOString();
  const entry = `\n### ${timestamp}\n**${action}**: ${details}\n`;

  try {
    if (!existsSync(LOG_DIR)) {
      execSync(`mkdir -p "${LOG_DIR}"`);
    }
    appendFileSync(logFile, entry);
  } catch (error) {
    console.error('写入日志失败:', error);
  }
}

/**
 * 估算上下文使用率
 */
function estimateContextUsage(): number {
  const sessionFile = getLatestSessionFile();
  if (!sessionFile) return 0;

  try {
    const stats = execSync(`wc -c < "${sessionFile}"`, { encoding: 'utf-8' });
    const size = parseInt(stats.trim());

    // Claude Opus 4: 200K tokens ≈ 600K chars (中英文混合)
    // 80% = 480K chars
    const maxContext = 600000;
    return Math.min(size / maxContext, 1);
  } catch {
    return 0;
  }
}

/**
 * 检查是否应该执行摘要
 */
function shouldSummarize(): { should: boolean; reason: string } {
  // 检查上下文使用率
  const usage = estimateContextUsage();
  if (usage < CONFIG.contextThreshold) {
    return { should: false, reason: `上下文使用率 ${(usage * 100).toFixed(1)}% < 80%` };
  }

  // 检查最小间隔
  const lastSummaryMarker = '/tmp/solar_last_auto_summary';
  if (existsSync(lastSummaryMarker)) {
    try {
      const lastTime = parseInt(readFileSync(lastSummaryMarker, 'utf-8'));
      const elapsed = Date.now() - lastTime;
      if (elapsed < CONFIG.minInterval) {
        return { should: false, reason: `距离上次摘要仅 ${Math.floor(elapsed / 60000)} 分钟` };
      }
    } catch {}
  }

  return { should: true, reason: `上下文使用率 ${(usage * 100).toFixed(1)}%` };
}

/**
 * 主函数
 */
async function main() {
  const args = process.argv.slice(2);
  const force = args.includes('--force') || args.includes('-f');
  const dryRun = args.includes('--dry-run');

  console.log('🤖 Auto Summarizer 启动');
  console.log('━'.repeat(50));

  // 检查是否应该执行
  if (!force) {
    const check = shouldSummarize();
    if (!check.should) {
      console.log(`⏭️  跳过: ${check.reason}`);
      return;
    }
    console.log(`✅ 触发条件满足: ${check.reason}`);
  } else {
    console.log('⚡ 强制模式');
  }

  if (dryRun) {
    console.log('🔍 Dry-run 模式，不实际写入');
  }

  // 获取会话文件
  const sessionFile = getLatestSessionFile();
  if (!sessionFile) {
    console.log('❌ 未找到会话文件');
    return;
  }
  console.log(`📄 会话文件: ${sessionFile.split('/').pop()}`);

  // 读取消息
  const messages = readRecentMessages(sessionFile, CONFIG.maxMessages);
  console.log(`📝 读取 ${messages.length} 条消息`);

  if (messages.length === 0) {
    console.log('❌ 没有消息可摘要');
    return;
  }

  // 生成摘要
  console.log(`🔄 调用 ${CONFIG.summaryModel} 生成摘要...`);
  const summaryText = await generateSummary(messages);

  if (!summaryText) {
    console.log('❌ 生成摘要失败');
    return;
  }

  console.log('✅ 摘要生成完成');

  // 解析摘要
  const summary = parseSummary(summaryText);
  if (!summary) {
    console.log('⚠️  解析摘要失败，使用原始文本');
    console.log(summaryText.slice(0, 500));
    return;
  }

  if (dryRun) {
    console.log('\n📋 生成的摘要预览:');
    console.log('━'.repeat(50));
    console.log(formatSummaryAsMarkdown(summary));
    return;
  }

  // 合并到 STATE.md
  const merged = mergeToState(summary);
  if (!merged) {
    console.log('❌ 合并到 STATE.md 失败');
    return;
  }

  // 记录执行时间
  writeFileSync('/tmp/solar_last_auto_summary', Date.now().toString());

  // 写入日志
  logOperation('AUTO_SUMMARY', `生成摘要，${messages.length} 条消息，上下文 ${estimateContextUsage().toFixed(1)}%`);

  console.log('\n✅ 自动摘要完成！');
  console.log(`📊 摘要内容:`);
  console.log(`   Mission: ${summary.mission?.slice(0, 50)}...`);
  console.log(`   Done: ${summary.progress.done.length} 项`);
  console.log(`   Next Actions: ${summary.nextActions.length} 项`);
}

// 导出供其他模块使用
export {
  estimateContextUsage,
  generateSummary,
  mergeToState,
  parseSummary,
  shouldSummarize,
  type Summary,
  type Message,
  CONFIG
};

// 运行
main().catch(console.error);
