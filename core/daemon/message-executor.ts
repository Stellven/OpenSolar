/**
 * Message Executor Module - 消息驱动执行器
 * 集成到现有 SolarDaemon，添加消息监听和配额调度功能
 */

import { iMessageListener } from '../listeners/imessage-listener';
import { GmailListener } from '../listeners/gmail-listener';
import { TelegramListener } from '../listeners/telegram-listener';
import { QuotaScheduler } from '../executor/quota-scheduler';
import { BacklogManager } from '../backlog/backlog-manager';
import { ReplySender, Channel } from '../reply/reply-sender';
import { $ } from 'bun';
import Database from 'bun:sqlite';

export interface MessageExecutorConfig {
  listeners: {
    imessage: boolean;
    gmail: boolean;
    telegram: boolean;
  };
  scheduler: {
    interval: number;
    maxWorkers: number;
  };
  telegramBotToken?: string;
}

const DEFAULT_CONFIG: MessageExecutorConfig = {
  listeners: {
    imessage: true,
    gmail: true,
    telegram: false
  },
  scheduler: {
    interval: 5000,
    maxWorkers: 4
  }
};

/**
 * MessageExecutor - 消息驱动任务执行器
 * 可作为独立服务运行，或集成到 SolarDaemon
 */
export class MessageExecutor {
  private config: MessageExecutorConfig;
  private iMessageListener?: iMessageListener;
  private gmailListener?: GmailListener;
  private telegramListener?: TelegramListener;
  private scheduler: QuotaScheduler;
  private backlog: BacklogManager;
  private replySender: ReplySender;
  private db: Database;
  private running: boolean = false;
  private workerInterval?: Timer;

  constructor(config: Partial<MessageExecutorConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.scheduler = new QuotaScheduler();
    this.backlog = new BacklogManager();
    this.replySender = new ReplySender();
    this.db = new Database(`${process.env.HOME}/.solar/solar.db`);
  }

  /**
   * 启动消息执行器
   */
  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;

    console.log('[MessageExecutor] Starting...');

    // 启动监听器
    await this.startListeners();

    // 启动调度器
    this.scheduler.start(this.config.scheduler.interval);

    // 启动 Worker 循环
    this.workerInterval = setInterval(
      () => this.processNextTask(),
      this.config.scheduler.interval
    );

    console.log('[MessageExecutor] Running');
  }

  /**
   * 停止消息执行器
   */
  stop(): void {
    if (!this.running) return;
    this.running = false;

    console.log('[MessageExecutor] Stopping...');

    // 停止监听器
    this.iMessageListener?.stop();
    this.gmailListener?.stop();
    this.telegramListener?.stop();

    // 停止调度器
    this.scheduler.stop();

    // 停止 Worker 循环
    if (this.workerInterval) {
      clearInterval(this.workerInterval);
      this.workerInterval = undefined;
    }

    // 清理资源
    this.scheduler.close();
    this.backlog.close();

    console.log('[MessageExecutor] Stopped');
  }

  /**
   * 启动所有配置的监听器
   */
  private async startListeners(): Promise<void> {
    if (this.config.listeners.imessage) {
      this.iMessageListener = new iMessageListener();
      await this.iMessageListener.start();
      console.log('[MessageExecutor] iMessage listener started');
    }

    if (this.config.listeners.gmail) {
      this.gmailListener = new GmailListener();
      await this.gmailListener.start();
      console.log('[MessageExecutor] Gmail listener started');
    }

    if (this.config.listeners.telegram && this.config.telegramBotToken) {
      this.telegramListener = new TelegramListener();
      await this.telegramListener.start();
      console.log('[MessageExecutor] Telegram listener started');
    }
  }

  /**
   * 处理下一个任务
   */
  private async processNextTask(): Promise<void> {
    if (!this.running) return;

    const decision = this.scheduler.getSchedulerDecision();

    if (!decision.canExecute) {
      return;
    }

    const tasks = this.scheduler.getNextTasks(1);

    if (tasks.length === 0) {
      return;
    }

    const task = tasks[0];
    const execution = this.scheduler.startTask(task.id);

    if (!execution) {
      return;
    }

    try {
      const result = await this.executeTask(task);
      this.scheduler.completeTask(task.id, result, result.tokensUsed || 0);

      // 发送回复给用户
      await this.sendReplyToUser(task.id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      this.scheduler.failTask(task.id, errorMsg);
    }
  }

  /**
   * 执行任务
   */
  private async executeTask(task: {
    id: number | string;
    content: string;
    parsedIntent: string;
    estimatedTokens: number;
  }): Promise<any> {
    console.log(`[MessageExecutor] Executing task ${task.id}: ${task.content.slice(0, 50)}...`);

    const intent = task.parsedIntent;

    // 根据意图路由到不同的执行器
    if (intent.startsWith('/')) {
      return this.executeSkill(intent, task.content);
    } else if (intent.startsWith('@')) {
      return this.queueForAgent(intent, task.content);
    } else if (intent.startsWith('solar_')) {
      return this.executeShortcut(intent, task.content);
    } else {
      return this.queueForManual(task.content);
    }
  }

  /**
   * 执行 Skill
   */
  private async executeSkill(skill: string, content: string): Promise<any> {
    const skillName = skill.slice(1);
    const skillPath = `${process.env.HOME}/.claude/skills/${skillName}/${skillName}.ts`;

    try {
      const result = await $`bun run ${skillPath} ${content}`.text();
      return { type: 'skill', skill: skillName, output: result, tokensUsed: 100 };
    } catch (error) {
      throw new Error(`Skill execution failed: ${error}`);
    }
  }

  /**
   * 执行 Shortcut
   */
  private async executeShortcut(shortcut: string, content: string): Promise<any> {
    try {
      let params = '{}';
      const jsonMatch = content.match(/\{.*\}/s);
      if (jsonMatch) {
        params = jsonMatch[0];
      }

      const result = await $`shortcuts run ${shortcut} -i ${params}`.text();
      return { type: 'shortcut', shortcut, output: result, tokensUsed: 0 };
    } catch (error) {
      throw new Error(`Shortcut execution failed: ${error}`);
    }
  }

  /**
   * 排队等待 Agent 处理
   */
  private async queueForAgent(agent: string, content: string): Promise<any> {
    console.log(`[MessageExecutor] Queuing for agent ${agent}: ${content.slice(0, 50)}`);
    return { type: 'agent', agent, status: 'queued_for_claude_session', tokensUsed: 0 };
  }

  /**
   * 排队等待手动处理
   */
  private async queueForManual(content: string): Promise<any> {
    console.log(`[MessageExecutor] Queuing for manual: ${content.slice(0, 50)}`);
    return { type: 'general', status: 'queued_for_manual', tokensUsed: 0 };
  }

  /**
   * 发送回复给用户
   */
  private async sendReplyToUser(taskId: number | string, result: any): Promise<void> {
    try {
      // 获取任务的发送者和来源信息
      const task = this.db.prepare(`
        SELECT sender, source FROM bl_message_tasks WHERE task_id = ?
      `).get(taskId) as { sender: string; source: string } | null;

      if (!task || !task.sender) {
        console.log(`[MessageExecutor] No sender info for task ${taskId}, skipping reply`);
        return;
      }

      // 格式化回复内容
      const content = result.output || result.answer ||
                      (typeof result === 'string' ? result : JSON.stringify(result, null, 2));

      // 发送回复
      const reply = await this.replySender.send({
        channel: task.source as Channel,
        recipient: task.sender,
        replyType: 'quick_answer',
        content: content.slice(0, 2000) // 限制长度
      });

      if (reply.success) {
        console.log(`[MessageExecutor] ✓ Reply sent to ${task.sender} via ${task.source}`);
      } else {
        console.log(`[MessageExecutor] ✗ Reply failed: ${reply.error}`);
      }
    } catch (error) {
      console.error(`[MessageExecutor] Error sending reply:`, error);
    }
  }

  /**
   * 获取状态
   */
  getStatus(): {
    running: boolean;
    listeners: Record<string, boolean>;
    scheduler: ReturnType<QuotaScheduler['getStats']>;
  } {
    return {
      running: this.running,
      listeners: {
        imessage: !!this.iMessageListener,
        gmail: !!this.gmailListener,
        telegram: !!this.telegramListener
      },
      scheduler: this.scheduler.getStats()
    };
  }
}

// CLI / Standalone 模式
if (import.meta.main) {
  const configPath = `${process.env.HOME}/.solar/config.json`;
  let config: Partial<MessageExecutorConfig> = {};

  try {
    const configFile = Bun.file(configPath);
    if (await configFile.exists()) {
      config = await configFile.json();
    }
  } catch {}

  const executor = new MessageExecutor(config);

  process.on('SIGINT', () => {
    executor.stop();
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    executor.stop();
    process.exit(0);
  });

  const cmd = process.argv[2];

  switch (cmd) {
    case 'start':
    case undefined:
      executor.start().then(() => {
        console.log('[MessageExecutor] Press Ctrl+C to stop');
      });
      break;
    case 'status':
      console.log(JSON.stringify(executor.getStatus(), null, 2));
      process.exit(0);
      break;
    default:
      console.log(`
Message Executor

Usage:
  bun run message-executor.ts [start]  Start the executor
  bun run message-executor.ts status   Show status

Configuration: ~/.solar/config.json
`);
  }
}
