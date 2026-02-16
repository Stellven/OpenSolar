#!/usr/bin/env bun
/**
 * Message Executor - 消息执行器
 *
 * 从队列取任务 → 关联上下文 → 执行 → 回复
 */

import Database from 'bun:sqlite';
import { ReplySender } from '../reply/reply-sender';
import { sendNtfy } from '../notify/ntfy';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

interface QueuedTask {
  task_id: string;
  source: string;
  source_id: string;
  sender: string;
  content: string;
  parsed_intent: string;
  priority: string;
  status: string;
  metadata: string;
}

export class MessageExecutor {
  private db: Database;
  private replySender: ReplySender;
  private running: boolean = false;

  constructor(dbPath: string = DB_PATH) {
    this.db = new Database(dbPath);
    this.replySender = new ReplySender();
  }

  /**
   * 启动执行器 (轮询模式)
   */
  async start(pollInterval: number = 10000): Promise<void> {
    if (this.running) return;
    this.running = true;

    console.log(`[Executor] 启动，轮询间隔 ${pollInterval / 1000}s`);

    while (this.running) {
      await this.processNext();
      await Bun.sleep(pollInterval);
    }
  }

  stop(): void {
    this.running = false;
    console.log('[Executor] 已停止');
  }

  /**
   * 处理下一个待执行任务
   */
  async processNext(): Promise<boolean> {
    // 1. 获取最高优先级的待处理任务 (只处理监护人的邮件)
    const task = this.db.prepare(`
      SELECT * FROM bl_message_tasks
      WHERE status = 'pending'
        AND source IN ('gmail', 'imessage', 'telegram')
        AND (sender LIKE '%lisihao@gmail.com%' OR sender LIKE '%Sean Lee%')
      ORDER BY
        CASE priority
          WHEN 'high' THEN 1
          WHEN 'scheduled' THEN 2
          ELSE 3
        END,
        CAST(priority AS INTEGER) DESC,
        created_at ASC
      LIMIT 1
    `).get() as QueuedTask | undefined;

    if (!task) {
      return false;
    }

    console.log(`[Executor] 处理任务: ${task.task_id} - ${task.content.slice(0, 50)}...`);

    // 2. 标记为处理中
    this.db.prepare(`
      UPDATE bl_message_tasks
      SET status = 'running', started_at = datetime('now')
      WHERE task_id = ?
    `).run(task.task_id);

    try {
      // 3. 检查是否是深度洞察请求
      const insightResult = await this.checkAndRunInsight(task);
      if (insightResult) {
        // 深度洞察已执行，更新状态并返回
        this.db.prepare(`
          UPDATE bl_message_tasks
          SET status = 'done',
              result = ?,
              completed_at = datetime('now')
          WHERE task_id = ?
        `).run(insightResult, task.task_id);

        await sendNtfy({
          title: `🔬 深度洞察完成`,
          message: insightResult.slice(0, 100),
          tags: ['brain'],
        });

        console.log(`[Executor] ✓ 深度洞察完成: ${task.task_id}`);
        return true;
      }

      // 4. 获取线程上下文 (如果是回复邮件)
      const context = await this.getThreadContext(task);

      // 5. 执行任务
      const result = await this.executeTask(task, context);

      // 5. 发送 ntfy 通知
      const preview = result.slice(0, 100).replace(/\n/g, ' ');
      await sendNtfy({
        title: `📬 ${task.source} 任务完成`,
        message: preview + (result.length > 100 ? '...' : ''),
        tags: ['white_check_mark'],
      });

      // 6. 更新状态
      this.db.prepare(`
        UPDATE bl_message_tasks
        SET status = 'done',
            result = ?,
            completed_at = datetime('now')
        WHERE task_id = ?
      `).run(result, task.task_id);

      console.log(`[Executor] ✓ 完成: ${task.task_id}`);
      return true;

    } catch (error: any) {
      this.db.prepare(`
        UPDATE bl_message_tasks
        SET status = 'failed',
            error = ?,
            completed_at = datetime('now')
        WHERE task_id = ?
      `).run(error.message, task.task_id);

      console.error(`[Executor] ✗ 失败: ${task.task_id} - ${error.message}`);
      return false;
    }
  }

  /**
   * 获取邮件线程上下文 (包括之前的对话和回复)
   */
  private async getThreadContext(task: QueuedTask): Promise<string> {
    // 检查是否是回复邮件 (Re: 前缀)
    const isReply = task.content.includes('Subject: Re:') ||
                    task.content.toLowerCase().startsWith('re:');

    if (!isReply || task.source !== 'gmail') {
      return '';
    }

    // 提取原始邮件主题
    const subjectMatch = task.content.match(/Subject: Re: (.+?)(?:\n|$)/);
    if (!subjectMatch) {
      return '';
    }

    const originalSubject = subjectMatch[1].trim();

    // 查找整个线程的所有邮件和回复 (按时间顺序)
    const threadTasks = this.db.prepare(`
      SELECT task_id, content, result, created_at FROM bl_message_tasks
      WHERE source = 'gmail'
        AND (content LIKE ? OR content LIKE ?)
        AND task_id != ?
        AND status = 'done'
      ORDER BY created_at ASC
    `).all(
      `%Subject: ${originalSubject}%`,
      `%Subject: Re: ${originalSubject}%`,
      task.task_id
    ) as { task_id: string; content: string; result: string; created_at: string }[];

    if (threadTasks.length === 0) {
      return '';
    }

    console.log(`[Executor] 关联到线程: ${originalSubject.slice(0, 30)}... (${threadTasks.length}条历史)`);

    // 构建完整的对话历史
    let context = '\n\n=== 邮件线程历史 ===\n';

    for (const prev of threadTasks) {
      // 提取邮件正文 (去掉 header)
      const bodyMatch = prev.content.match(/\n\n([\s\S]*)/);
      const body = bodyMatch ? bodyMatch[1].slice(0, 500) : prev.content.slice(0, 500);

      context += `\n--- 用户邮件 (${prev.created_at}) ---\n${body}\n`;

      if (prev.result) {
        context += `\n--- Solar 回复 ---\n${prev.result.slice(0, 1000)}\n`;
      }
    }

    return context;
  }

  /**
   * 执行任务 - 调用 Claude 处理
   */
  private async executeTask(task: QueuedTask, context: string): Promise<string> {
    // 提取用户指令 (邮件正文第一行通常是指令)
    const lines = task.content.split('\n');
    let instruction = '';
    let content = task.content;

    // 对于邮件，提取 Subject 后的正文
    const subjectIndex = task.content.indexOf('Subject:');
    if (subjectIndex !== -1) {
      const afterSubject = task.content.slice(subjectIndex);
      const bodyStart = afterSubject.indexOf('\n\n');
      if (bodyStart !== -1) {
        instruction = afterSubject.slice(bodyStart + 2).split('\n')[0].trim();
      }
    }

    // 如果没提取到指令，用整个内容
    if (!instruction) {
      instruction = lines[0];
    }

    // 构建 prompt - 根据是否有上下文调整
    const isThreadReply = context.includes('=== 邮件线程历史 ===');

    const prompt = isThreadReply
      ? `这是一个邮件对话的后续回复。用户对之前的回复有反馈，请基于之前的对话继续深入。

${context}

--- 用户最新回复 ---
${instruction}

完整邮件:
${content}

重要：
1. 仔细阅读之前的对话历史，理解上下文
2. 用户的最新回复是对之前回复的反馈/追问
3. 基于之前的分析结果继续深入，不要重新开始
4. 如果用户说"继续"、"深入"、"再分析"，就在之前基础上扩展`
      : `用户通过邮件发来指令，请处理并给出回复。

用户指令: ${instruction}

邮件内容:
${content}
${context}

请根据用户指令处理，给出简洁的回复。如果是分析任务，给出分析结果；如果是设计任务，给出设计方案。`;

    // 调用 OpenClaw (小爱) 处理，让小爱调度老专家
    try {
      // 优先使用 OpenClaw，让小爱调用老专家分析
      const result = await Bun.spawn([
        'openclaw', 'agent', '--local', '--agent', 'main',
        '--message', prompt
      ], {
        stdout: 'pipe',
        stderr: 'pipe',
        env: { ...process.env, PATH: '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/lisihao/n/bin' }
      });

      const output = await new Response(result.stdout).text();
      const errorOutput = await new Response(result.stderr).text();

      if (output.trim()) {
        console.log(`[Executor] OpenClaw 处理成功`);
        return output.trim();
      }

      // OpenClaw 失败，降级到 Claude
      console.warn('[Executor] OpenClaw 返回空，尝试 Claude');
      const claudeResult = await Bun.spawn(['claude', '-p', prompt], {
        stdout: 'pipe',
        stderr: 'pipe',
      });

      const claudeOutput = await new Response(claudeResult.stdout).text();
      return claudeOutput.trim() || '任务已处理';

    } catch (e: any) {
      // 降级: 返回简单确认
      console.warn('[Executor] 模型调用失败:', e.message);
      return `收到您的消息: "${instruction.slice(0, 50)}..."\n\n已记录，稍后处理。`;
    }
  }

  /**
   * 检查并执行深度洞察分析
   * @returns 如果匹配并执行了深度洞察，返回结果；否则返回 null
   */
  private async checkAndRunInsight(task: QueuedTask): Promise<string | null> {
    // 深度洞察触发关键词
    const insightKeywords = [
      '深度洞察', '洞察分析', '深入分析', '深度分析',
      '帮我研究', '深入洞察', '洞察一下', '调研一下'
    ];

    // 检查是否匹配
    const content = task.content.toLowerCase();
    const matched = insightKeywords.some(kw => content.includes(kw.toLowerCase()));

    if (!matched) {
      return null;
    }

    console.log(`[Executor] 🔬 检测到深度洞察请求`);

    // 提取主题
    let topic = task.content;
    // 尝试从邮件格式中提取
    const subjectMatch = task.content.match(/Subject: (.+?)(?:\n|$)/);
    if (subjectMatch) {
      topic = subjectMatch[1];
    }
    // 去掉触发关键词
    for (const kw of insightKeywords) {
      topic = topic.replace(new RegExp(kw, 'gi'), '').replace(/[：:]/g, '').trim();
    }

    console.log(`[Executor] 🧠 启动深度洞察分析: ${topic.slice(0, 50)}...`);

    // 直接调用 insight-runner.sh（绕过分发器，因为主题已不含关键词）
    const insightRunnerPath = `${process.env.HOME}/.claude/core/xiaoai-insight/insight-runner.sh`;

    try {
      const result = Bun.spawn([insightRunnerPath, topic, '昊哥'], {
        stdout: 'pipe',
        stderr: 'pipe',
        env: {
          ...process.env,
          PATH: '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/lisihao/.bun/bin:/Users/lisihao/n/bin',
          HOME: process.env.HOME
        }
      });

      const output = await new Response(result.stdout).text();
      const exitCode = await result.exited;

      if (exitCode === 0 && output.trim()) {
        return output.trim();
      }

      // 如果失败，返回简单确认
      const errOutput = await new Response(result.stderr).text();
      console.warn('[Executor] 深度洞察执行失败:', errOutput.slice(0, 200));
      return `🔬 已收到您的深度洞察请求: "${topic.slice(0, 50)}"

深度洞察分析已启动，预计需要 5-15 分钟。
完成后会发送通知。

提示：您也可以直接对我说"深度洞察：${topic}"来启动分析。`;

    } catch (e: any) {
      console.error('[Executor] 深度洞察执行错误:', e.message);
      return null; // 降级为普通处理
    }
  }

  /**
   * 发送回复
   */
  private async sendReply(task: QueuedTask, result: string): Promise<void> {
    const channel = task.source as 'gmail' | 'imessage' | 'telegram';

    // 提取收件人
    let recipient = task.sender;
    if (task.sender.includes('<')) {
      const match = task.sender.match(/<(.+?)>/);
      if (match) recipient = match[1];
    }

    // 提取主题 (用于邮件回复)
    let subject: string | undefined;
    const subjectMatch = task.content.match(/Subject: (.+?)(?:\n|$)/);
    if (subjectMatch) {
      subject = subjectMatch[1].startsWith('Re:')
        ? subjectMatch[1]
        : `Re: ${subjectMatch[1]}`;
    }

    await this.replySender.send({
      channel,
      recipient,
      replyType: 'quick_answer',
      content: result,
      subject,
      inReplyTo: task.source_id,
    });
  }

  /**
   * 手动处理单个任务
   */
  async processTask(taskId: string): Promise<string> {
    const task = this.db.prepare(
      'SELECT * FROM bl_message_tasks WHERE task_id = ?'
    ).get(taskId) as QueuedTask | undefined;

    if (!task) {
      throw new Error(`Task not found: ${taskId}`);
    }

    const context = await this.getThreadContext(task);
    const result = await this.executeTask(task, context);

    // 更新状态
    this.db.prepare(`
      UPDATE bl_message_tasks
      SET status = 'done', result = ?, completed_at = datetime('now')
      WHERE task_id = ?
    `).run(result, taskId);

    return result;
  }
}

// CLI
if (import.meta.main) {
  const executor = new MessageExecutor();
  const [cmd, ...args] = process.argv.slice(2);

  switch (cmd) {
    case 'start':
      const interval = parseInt(args[0]) || 10000;
      process.on('SIGINT', () => {
        executor.stop();
        process.exit(0);
      });
      executor.start(interval);
      break;

    case 'process':
      if (!args[0]) {
        console.error('Usage: message-executor.ts process <task_id>');
        process.exit(1);
      }
      executor.processTask(args[0]).then(result => {
        console.log('Result:', result);
        process.exit(0);
      }).catch(e => {
        console.error('Error:', e.message);
        process.exit(1);
      });
      break;

    case 'next':
      executor.processNext().then(processed => {
        console.log(processed ? '处理了一个任务' : '队列为空');
        process.exit(0);
      });
      break;

    default:
      console.log(`Usage: message-executor.ts <start|process|next> [args]

  start [interval]  - 启动轮询执行器 (默认 10s)
  process <task_id> - 处理指定任务
  next              - 处理下一个待处理任务
`);
  }
}
