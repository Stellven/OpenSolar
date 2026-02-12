/**
 * Solar Dashboard Server
 *
 * 简单的本地服务器，提供：
 * 1. 静态文件服务 (dashboard HTML)
 * 2. 状态 API (/api/state)
 * 3. 状态更新 API (/api/update)
 */

const STATE_FILE = import.meta.dir + '/state.json';
const DASHBOARD_FILE = Bun.file(import.meta.dir + '/../../demos/solar-dashboard.html');
const PORT = 3721;

// 读取状态
async function getState() {
  const file = Bun.file(STATE_FILE);
  if (await file.exists()) {
    return await file.json();
  }
  return { error: 'State file not found' };
}

// 更新状态
async function updateState(updates: any) {
  const state = await getState();
  const newState = { ...state, ...updates, lastUpdate: new Date().toISOString() };
  await Bun.write(STATE_FILE, JSON.stringify(newState, null, 2));
  return newState;
}

// 添加对话
async function addConversation(role: string, content: string) {
  const state = await getState();
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  state.conversations = [
    { role, content: content.slice(0, 100) + (content.length > 100 ? '...' : ''), time },
    ...(state.conversations || []).slice(0, 19)
  ];

  await Bun.write(STATE_FILE, JSON.stringify(state, null, 2));
  return state;
}

// 添加/更新任务
async function updateTask(task: any) {
  const state = await getState();

  // 将其他 in_progress 任务标记为 completed
  state.tasks = state.tasks.map((t: any) =>
    t.status === 'in_progress' && t.id !== task.id
      ? { ...t, status: 'completed' }
      : t
  );

  // 添加或更新任务
  const existingIndex = state.tasks.findIndex((t: any) => t.id === task.id);
  if (existingIndex >= 0) {
    state.tasks[existingIndex] = task;
  } else {
    state.tasks = [task, ...state.tasks.slice(0, 4)];
  }

  state.lastUpdate = new Date().toISOString();
  await Bun.write(STATE_FILE, JSON.stringify(state, null, 2));
  return state;
}

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);

    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (req.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // API: 获取状态
    if (url.pathname === '/api/state') {
      const state = await getState();
      return Response.json(state, { headers: corsHeaders });
    }

    // API: 更新状态
    if (url.pathname === '/api/update' && req.method === 'POST') {
      const updates = await req.json();
      const state = await updateState(updates);
      return Response.json(state, { headers: corsHeaders });
    }

    // API: 添加对话
    if (url.pathname === '/api/conversation' && req.method === 'POST') {
      const { role, content } = await req.json();
      const state = await addConversation(role, content);
      return Response.json(state, { headers: corsHeaders });
    }

    // API: 更新任务
    if (url.pathname === '/api/task' && req.method === 'POST') {
      const task = await req.json();
      const state = await updateTask(task);
      return Response.json(state, { headers: corsHeaders });
    }

    // 主页面
    if (url.pathname === '/' || url.pathname === '/dashboard') {
      return new Response(DASHBOARD_FILE, {
        headers: { 'Content-Type': 'text/html' },
      });
    }

    return new Response('Not Found', { status: 404 });
  },
});

console.log(`
┌─ ☀️ Solar Dashboard Server ─────────────────────────────────────┐
│                                                                 │
│  URL: http://localhost:${PORT}                                    │
│                                                                 │
│  Endpoints:                                                     │
│    GET  /              Dashboard 页面                           │
│    GET  /api/state     获取当前状态                             │
│    POST /api/update    更新状态                                 │
│    POST /api/conversation  添加对话                             │
│    POST /api/task      更新任务                                 │
│                                                                 │
│  刷新周期: 3秒 (页面自动刷新)                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
`);
