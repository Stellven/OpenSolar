/**
 * Solar Daemon - The Beating Heart
 * 系统心脏 - 驱动工作流、调度 Agent、管理消息队列
 */

import {
  StateManager,
  SolarQueries,
  getStateManager,
} from "../nerve/state-manager";
import { Scheduler } from "./scheduler";
import { MessageQueue } from "./message-queue";
import { WorkflowEngine } from "./workflow";
import { PluginHost } from "../plugin/host";
import { watch } from "fs";
import { unlinkSync, existsSync } from "fs";

// ==================== 配置 ====================

export interface DaemonConfig {
  socketPath: string;
  dbPath: string;
  cacheDir: string;
  pluginDir: string;
  syncInterval: number; // 消息同步间隔 (ms)
  healthCheckInterval: number;
}

const DEFAULT_CONFIG: DaemonConfig = {
  socketPath: "/tmp/solar.sock",
  dbPath: `${process.env.HOME}/.solar/solar.db`,
  cacheDir: `${process.env.HOME}/.solar/cache`,
  pluginDir: `${process.env.HOME}/.solar/plugins`,
  syncInterval: 1000,
  healthCheckInterval: 5000,
};

// ==================== Daemon 主类 ====================

export class SolarDaemon {
  private config: DaemonConfig;
  private state: StateManager;
  private queries: SolarQueries;
  private scheduler: Scheduler;
  private messageQueue: MessageQueue;
  private workflowEngine: WorkflowEngine;
  private pluginHost: PluginHost;
  private server: ReturnType<typeof Bun.serve> | null = null;
  private startedAt: Date | null = null;
  private isShuttingDown = false;

  constructor(config: Partial<DaemonConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    // 初始化状态管理
    this.state = getStateManager({ dbPath: this.config.dbPath });
    this.queries = new SolarQueries(this.state);

    // 初始化子系统
    this.scheduler = new Scheduler();
    this.messageQueue = new MessageQueue(this.state, this.queries);
    this.workflowEngine = new WorkflowEngine(this.state, this.queries);
    this.pluginHost = new PluginHost(this.config.pluginDir, this.state);
  }

  // ==================== 生命周期 ====================

  async start(): Promise<void> {
    console.log("☀️  Solar Daemon starting...");

    // 清理旧的 socket 文件
    if (existsSync(this.config.socketPath)) {
      unlinkSync(this.config.socketPath);
    }

    // 确保缓存目录存在
    await Bun.spawn(["mkdir", "-p", this.config.cacheDir]).exited;

    // 启动定时任务
    this.startScheduledTasks();

    // 启动文件监听
    this.startFileWatcher();

    // 启动 Socket 服务
    await this.startSocketServer();

    // 加载插件
    await this.pluginHost.loadAll();

    // 更新状态
    this.startedAt = new Date();
    this.state.set("daemon.status", "running");
    this.state.set("daemon.started_at", this.startedAt.toISOString());
    this.state.set("daemon.pid", process.pid);

    // 记录启动消息
    this.queries.logMessage(
      "system",
      "daemon",
      { event: "started", pid: process.pid },
      "info",
    );

    console.log(`☀️  Solar Daemon running (PID: ${process.pid})`);
    console.log(`   Socket: ${this.config.socketPath}`);
    console.log(`   Database: ${this.config.dbPath}`);
  }

  async stop(): Promise<void> {
    if (this.isShuttingDown) return;
    this.isShuttingDown = true;

    console.log("\n☀️  Solar Daemon shutting down...");

    // 停止调度器
    this.scheduler.stopAll();

    // 刷新消息队列
    await this.messageQueue.flush();

    // 卸载插件
    await this.pluginHost.unloadAll();

    // 关闭 Socket 服务
    if (this.server) {
      this.server.stop();
    }

    // 更新状态
    this.state.set("daemon.status", "stopped");
    this.state.set("daemon.stopped_at", new Date().toISOString());

    // 记录停止消息
    this.queries.logMessage("system", "daemon", { event: "stopped" }, "info");

    // 关闭数据库
    this.state.close();

    // 清理 socket 文件
    if (existsSync(this.config.socketPath)) {
      unlinkSync(this.config.socketPath);
    }

    console.log("☀️  Solar Daemon stopped");
  }

  // ==================== 定时任务 ====================

  private startScheduledTasks(): void {
    // 消息同步 - 每秒
    this.scheduler.interval(
      "message-sync",
      this.config.syncInterval,
      async () => {
        await this.messageQueue.sync();
      },
    );

    // 工作流状态检查 - 每 5 秒
    this.scheduler.interval(
      "workflow-check",
      this.config.healthCheckInterval,
      async () => {
        await this.workflowEngine.checkState();
      },
    );

    // 缓存清理 - 每小时
    this.scheduler.interval("cache-cleanup", 3600000, async () => {
      await this.cleanupCache();
    });

    // 插件健康检查 - 每分钟
    this.scheduler.interval("plugin-health", 60000, async () => {
      await this.pluginHost.healthCheck();
    });

    // 统计汇总 - 每天凌晨
    this.scheduler.daily("daily-stats", 0, 0, async () => {
      await this.aggregateDailyStats();
    });
  }

  // ==================== 文件监听 ====================

  private startFileWatcher(): void {
    const cacheDir = this.config.cacheDir;

    try {
      watch(cacheDir, { recursive: true }, async (event, filename) => {
        if (!filename || !filename.endsWith(".msg.json")) return;

        const filePath = `${cacheDir}/${filename}`;
        if (!existsSync(filePath)) return;

        try {
          const content = await Bun.file(filePath).json();
          await this.messageQueue.enqueue(content);
          unlinkSync(filePath);
        } catch (e) {
          console.error(`Error processing message file ${filename}:`, e);
        }
      });
    } catch (e) {
      console.error("Failed to start file watcher:", e);
    }
  }

  // ==================== Socket 服务 ====================

  private async startSocketServer(): Promise<void> {
    this.server = Bun.serve({
      unix: this.config.socketPath,
      fetch: async (req) => {
        try {
          return await this.handleRequest(req);
        } catch (e) {
          console.error("Request error:", e);
          return Response.json({ error: String(e) }, { status: 500 });
        }
      },
    });
  }

  private async handleRequest(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;
    const method = req.method;

    // ========== 状态 API ==========

    if (path === "/status" && method === "GET") {
      return Response.json(this.getStatus());
    }

    if (path === "/health" && method === "GET") {
      return Response.json({ status: "ok", uptime: this.getUptime() });
    }

    // ========== 状态管理 API ==========

    if (path === "/state" && method === "GET") {
      const key = url.searchParams.get("key");
      if (key) {
        return Response.json({ value: this.state.get(key) });
      }
      return Response.json(this.state.export());
    }

    if (path === "/state" && method === "POST") {
      const { key, value } = await req.json();
      this.state.set(key, value);
      return Response.json({ ok: true });
    }

    // ========== 消息 API ==========

    if (path === "/message" && method === "POST") {
      const msg = await req.json();
      await this.messageQueue.enqueue(msg);
      return Response.json({ ok: true });
    }

    if (path === "/messages" && method === "GET") {
      const limit = parseInt(url.searchParams.get("limit") || "50");
      const type = url.searchParams.get("type") || undefined;
      return Response.json(this.queries.getRecentMessages(limit, type));
    }

    // ========== 工作流 API ==========

    if (path === "/workflow/start" && method === "POST") {
      const data = await req.json();
      const result = await this.workflowEngine.start(data);
      return Response.json(result);
    }

    if (path === "/workflow/transition" && method === "POST") {
      const data = await req.json();
      const result = await this.workflowEngine.transition(data);
      return Response.json(result);
    }

    if (path === "/workflow/current" && method === "GET") {
      return Response.json(this.workflowEngine.getCurrent());
    }

    // ========== 任务 API ==========

    if (path === "/tasks" && method === "GET") {
      const project = url.searchParams.get("project") || undefined;
      return Response.json(this.queries.getActiveTasks(project));
    }

    if (path === "/tasks" && method === "POST") {
      const data = await req.json();
      const id = this.queries.createTask(data);
      return Response.json({ id });
    }

    // ========== 插件 API ==========

    if (path === "/plugins" && method === "GET") {
      const type = url.searchParams.get("type") || undefined;
      return Response.json(this.queries.getEnabledPlugins(type));
    }

    if (path === "/plugin/load" && method === "POST") {
      const { name } = await req.json();
      const result = await this.pluginHost.load(name);
      return Response.json(result);
    }

    if (path === "/plugin/unload" && method === "POST") {
      const { name } = await req.json();
      await this.pluginHost.unload(name);
      return Response.json({ ok: true });
    }

    // ========== Token 统计 API ==========

    if (path === "/stats/tokens" && method === "GET") {
      const days = parseInt(url.searchParams.get("days") || "7");
      return Response.json(this.queries.getTokenUsage(days));
    }

    if (path === "/stats/today" && method === "GET") {
      return Response.json({
        cost: this.state.get("token_usage.today_cost", 0),
        tokens: this.state.get("token_usage.today_tokens", 0),
        details: this.queries.getTodayUsage(),
      });
    }

    // ========== 渲染 API ==========

    if (path === "/render" && method === "POST") {
      const { template, context } = await req.json();
      // TODO: 调用渲染引擎
      return Response.json({ output: `Rendered: ${template}` });
    }

    return new Response("Not Found", { status: 404 });
  }

  // ==================== 辅助方法 ====================

  private getStatus() {
    return {
      status: "running",
      pid: process.pid,
      startedAt: this.startedAt?.toISOString(),
      uptime: this.getUptime(),
      socket: this.config.socketPath,
      database: this.config.dbPath,
      workflow: this.workflowEngine.getCurrent(),
      plugins: {
        loaded: this.pluginHost.getLoadedCount(),
      },
      stats: {
        todayCost: this.state.get("token_usage.today_cost", 0),
        todayTokens: this.state.get("token_usage.today_tokens", 0),
      },
    };
  }

  private getUptime(): number {
    if (!this.startedAt) return 0;
    return Math.round((Date.now() - this.startedAt.getTime()) / 1000);
  }

  private async cleanupCache(): Promise<void> {
    // 清理超过 24 小时的消息
    this.state.run(`
      DELETE FROM messages
      WHERE processed = TRUE AND timestamp < datetime('now', '-1 day')
    `);

    // 清理临时文件
    // TODO: 实现缓存文件清理
  }

  private async aggregateDailyStats(): Promise<void> {
    // 记录每日统计
    this.queries.logMessage(
      "system",
      "daemon",
      {
        event: "daily_stats",
        date: new Date().toISOString().split("T")[0],
        cost: this.state.get("token_usage.today_cost", 0),
        tokens: this.state.get("token_usage.today_tokens", 0),
      },
      "info",
    );

    // 重置今日统计
    this.state.set("token_usage.today_cost", 0);
    this.state.set("token_usage.today_tokens", 0);
  }
}

// ==================== 入口 ====================

if (import.meta.main) {
  const daemon = new SolarDaemon();

  // 优雅退出
  process.on("SIGINT", async () => {
    await daemon.stop();
    process.exit(0);
  });

  process.on("SIGTERM", async () => {
    await daemon.stop();
    process.exit(0);
  });

  // 启动
  await daemon.start();
}
