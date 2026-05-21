/**
 * Solar Harness — Webhook 触发器
 *
 * 轻量 HTTP server，接收外部请求自动创建 Sprint
 *
 * 启动: bun ~/.solar/harness/webhook-server.ts
 * 端口: 9876 (可通过 HARNESS_PORT 环境变量修改)
 *
 * API:
 *   POST /sprint         — 创建新 Sprint
 *   POST /sprint/status  — 更新 Sprint 状态
 *   GET  /status          — 查看当前状态
 *   GET  /health          — 健康检查
 *
 * 触发方式:
 *   curl -X POST localhost:9876/sprint -d '{"title":"实现XX功能","description":"详细描述"}'
 *   Slack webhook → 转发到本 server
 *   GitHub webhook (issue created) → 自动创建 Sprint
 */

import { execFileSync, execSync } from "child_process";
import { readFileSync, writeFileSync, existsSync, readdirSync } from "fs";

const PORT = parseInt(process.env.HARNESS_PORT || "9876");
const HARNESS_DIR = `${process.env.HOME}/.solar/harness`;
const SPRINTS_DIR = `${HARNESS_DIR}/sprints`;
const SESSION_NAME = "solar-harness";

// --- Helpers ---

function resolvePmPane(): string | null {
  if (process.env.SOLAR_WEBHOOK_PM_PANE) return process.env.SOLAR_WEBHOOK_PM_PANE;

  try {
    const panes = execFileSync(
      "tmux",
      ["list-panes", "-t", `${SESSION_NAME}:0`, "-F", "#{pane_index}\t#{pane_title}"],
      { encoding: "utf-8", timeout: 2000 }
    );
    for (const line of panes.split("\n")) {
      const [paneIndex, title = ""] = line.split("\t");
      if (!paneIndex) continue;
      if (/(PM|产品经理)/i.test(title) && !/(Planner|规划者|Builder|建设者|Evaluator|审判官)/i.test(title)) {
        return `${SESSION_NAME}:0.${paneIndex}`;
      }
    }
  } catch {
    return null;
  }

  return null;
}

function notifyPmPane(sid: string): void {
  const targetPane = resolvePmPane();
  if (!targetPane) return;

  execFileSync(
    "tmux",
    [
      "send-keys",
      "-t",
      targetPane,
      `收到外部需求，Sprint 已创建: ${sid}。请读取 ~/.solar/harness/sprints/${sid}.contract.md 展开 Done 定义，完成后更新 status 为 active。`,
      "Enter",
    ],
    { timeout: 3000 }
  );
}

function getLatestSprint(): { id: string; status: string; title: string; round: number } | null {
  const files = readdirSync(SPRINTS_DIR).filter(f => f.endsWith(".status.json")).sort();
  if (files.length === 0) return null;
  const data = JSON.parse(readFileSync(`${SPRINTS_DIR}/${files[files.length - 1]}`, "utf-8"));
  return data;
}

function createSprint(title: string, description: string): string {
  const sid = `sprint-${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)}`;
  const now = new Date().toISOString();

  // 写合约
  const contract = `# Sprint Contract — ${sid}
Created: ${now}
Status: drafting

## 需求

${description || title}

## Done 定义

> 规划者填写：把"做好"变成具体可检查的条件

- [ ] (条件1)
- [ ] (条件2)
- [ ] (条件3)

## 范围

- 包含: (规划者填写)
- 不包含: (规划者填写)

## 约束

> 规划者填写

## 实现文件清单 (建设者完成后填写)

> (files)

## 审判官评估维度

1. 功能完整性: Done 定义逐条检查
2. 代码质量: 错误处理、边界、安全
3. 合约合规: 在范围内
4. 可维护性: 命名、结构
`;

  writeFileSync(`${SPRINTS_DIR}/${sid}.contract.md`, contract);

  // 写状态
  const status = {
    id: sid,
    title: title.slice(0, 60),
    status: "drafting",
    created_at: now,
    round: 0,
    source: "webhook",
    history: [{ ts: now, event: "contract_created", by: "webhook" }],
  };
  writeFileSync(`${SPRINTS_DIR}/${sid}.status.json`, JSON.stringify(status, null, 2));

  // 通知 PM pane；目标按 pane title 解析，避免布局变化后错投 Planner/Builder。
  try {
    notifyPmPane(sid);
  } catch {
    // tmux 可能没运行，静默
  }

  return sid;
}

// --- Server ---

const server = Bun.serve({
  port: PORT,

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const headers = { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" };

    // CORS preflight
    if (req.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: { ...headers, "Access-Control-Allow-Methods": "GET,POST", "Access-Control-Allow-Headers": "Content-Type" } });
    }

    // GET /health
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ status: "ok", port: PORT }), { headers });
    }

    // GET /status
    if (url.pathname === "/status" && req.method === "GET") {
      const sprint = getLatestSprint();
      const tmuxRunning = (() => {
        try { execSync(`tmux has-session -t ${SESSION_NAME}`, { timeout: 2000 }); return true; } catch { return false; }
      })();
      return new Response(JSON.stringify({ harness_running: tmuxRunning, current_sprint: sprint }), { headers });
    }

    // POST /sprint — 创建新 Sprint
    if (url.pathname === "/sprint" && req.method === "POST") {
      try {
        const body = await req.json() as { title?: string; description?: string; text?: string };

        // 支持多种格式: {title, description} 或 Slack 格式 {text}
        const title = body.title || body.text || "Untitled Sprint";
        const description = body.description || body.text || title;

        const sid = createSprint(title, description);
        return new Response(JSON.stringify({ ok: true, sprint_id: sid, message: `Sprint created: ${sid}` }), { headers });
      } catch (e: any) {
        return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 400, headers });
      }
    }

    // POST /sprint/status — 更新状态 (外部控制)
    if (url.pathname === "/sprint/status" && req.method === "POST") {
      try {
        const body = await req.json() as { sprint_id?: string; status: string };
        const sprint = getLatestSprint();
        const sid = body.sprint_id || sprint?.id;
        if (!sid) return new Response(JSON.stringify({ ok: false, error: "no sprint found" }), { status: 404, headers });

        const sf = `${SPRINTS_DIR}/${sid}.status.json`;
        if (!existsSync(sf)) return new Response(JSON.stringify({ ok: false, error: "sprint not found" }), { status: 404, headers });

        const data = JSON.parse(readFileSync(sf, "utf-8"));
        data.status = body.status;
        data.updated_at = new Date().toISOString();
        data.history.push({ ts: data.updated_at, event: `status_changed_to_${body.status}`, by: "webhook" });
        writeFileSync(sf, JSON.stringify(data, null, 2));

        return new Response(JSON.stringify({ ok: true, sprint_id: sid, status: body.status }), { headers });
      } catch (e: any) {
        return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 400, headers });
      }
    }

    // POST /github — GitHub webhook (issue opened)
    if (url.pathname === "/github" && req.method === "POST") {
      try {
        const body = await req.json() as any;
        if (body.action === "opened" && body.issue) {
          const title = body.issue.title;
          const description = `${body.issue.title}\n\n${body.issue.body || ""}\n\nSource: ${body.issue.html_url}`;
          const sid = createSprint(title, description);
          return new Response(JSON.stringify({ ok: true, sprint_id: sid }), { headers });
        }
        return new Response(JSON.stringify({ ok: true, skipped: true, reason: "not an issue.opened event" }), { headers });
      } catch (e: any) {
        return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 400, headers });
      }
    }

    return new Response(JSON.stringify({ error: "not found" }), { status: 404, headers });
  },
});

console.log(`Solar Harness Webhook Server listening on http://localhost:${PORT}`);
console.log(`  POST /sprint         — 创建 Sprint`);
console.log(`  POST /sprint/status  — 更新状态`);
console.log(`  POST /github         — GitHub issue webhook`);
console.log(`  GET  /status         — 查看状态`);
console.log(`  GET  /health         — 健康检查`);
