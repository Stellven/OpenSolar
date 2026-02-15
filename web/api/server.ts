#!/usr/bin/env bun
/**
 * Solar Web Dashboard - API Server
 *
 * 提供页面管理 API 和静态文件服务
 *
 * @version 1.0.0
 */

import { Database } from 'bun:sqlite';
import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { join, extname, basename } from 'path';

// ============================================================================
// 配置
// ============================================================================

const PORT = 8800;
const WEB_ROOT = join(import.meta.dir, '..');
const DB_PATH = join(process.env.HOME!, '.claude/solar.db');

// MIME 类型映射
const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

// ============================================================================
// 数据库初始化
// ============================================================================

function initDatabase(db: Database): void {
  // 读取并执行 schema
  const schemaPath = join(WEB_ROOT, 'schema.sql');
  if (existsSync(schemaPath)) {
    const schema = readFileSync(schemaPath, 'utf-8');
    db.exec(schema);
  }
}

// 注册页面到数据库
function registerPage(
  db: Database,
  page: {
    page_id: string;
    title: string;
    icon?: string;
    category?: string;
    description?: string;
    source_type: 'file' | 'url' | 'html';
    source_path: string;
    sort_order?: number;
    pinned?: boolean;
  }
): void {
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO sys_web_pages
    (page_id, title, icon, category, description, source_type, source_path, sort_order, pinned)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  stmt.run(
    page.page_id,
    page.title,
    page.icon || '📄',
    page.category || 'general',
    page.description || '',
    page.source_type,
    page.source_path,
    page.sort_order || 100,
    page.pinned ? 1 : 0
  );
}

// 扫描并注册 pages 目录下的 HTML 文件
function scanAndRegisterPages(db: Database): void {
  const pagesDir = join(WEB_ROOT, 'pages');

  if (!existsSync(pagesDir)) {
    return;
  }

  const files = readdirSync(pagesDir);

  for (const file of files) {
    if (!file.endsWith('.html')) continue;

    const filePath = join(pagesDir, file);
    const stat = statSync(filePath);

    if (!stat.isFile()) continue;

    // 从文件名生成 page_id
    const pageId = basename(file, '.html');

    // 尝试从 HTML 读取标题
    const content = readFileSync(filePath, 'utf-8');
    const titleMatch = content.match(/<title>([^<]+)<\/title>/i);
    const title = titleMatch ? titleMatch[1] : pageId;

    // 根据文件名推断分类
    let category = 'general';
    let icon = '📄';

    if (pageId.includes('architecture') || pageId.includes('design')) {
      category = 'architecture';
      icon = '🏗️';
    } else if (pageId.includes('report') || pageId.includes('analysis')) {
      category = 'report';
      icon = '📊';
    } else if (pageId.includes('tool') || pageId.includes('util')) {
      category = 'tool';
      icon = '🔧';
    } else if (pageId.includes('system') || pageId.includes('status')) {
      category = 'system';
      icon = '⚙️';
    }

    registerPage(db, {
      page_id: pageId,
      title,
      icon,
      category,
      source_type: 'file',
      source_path: `/pages/${file}`,
    });
  }
}

// ============================================================================
// API 处理器
// ============================================================================

interface PageInfo {
  page_id: string;
  title: string;
  icon: string;
  category: string;
  category_name: string;
  category_icon: string;
  category_color: string;
  description: string;
  source_type: string;
  source_path: string;
  sort_order: number;
  pinned: boolean;
  view_count: number;
  last_viewed_at: string | null;
}

function handleApiRequest(db: Database, path: string, method: string, body?: any): Response {
  // GET /api/pages - 获取所有页面
  if (path === '/api/pages' && method === 'GET') {
    const pages = db.query('SELECT * FROM v_web_pages').all() as PageInfo[];
    return Response.json({
      success: true,
      data: pages,
    });
  }

  // GET /api/pages/pinned - 获取固定页面
  if (path === '/api/pages/pinned' && method === 'GET') {
    const pages = db.query('SELECT * FROM v_pinned_pages').all() as PageInfo[];
    return Response.json({
      success: true,
      data: pages,
    });
  }

  // GET /api/pages/recent - 获取最近访问
  if (path === '/api/pages/recent' && method === 'GET') {
    const pages = db.query('SELECT * FROM v_recent_pages').all() as PageInfo[];
    return Response.json({
      success: true,
      data: pages,
    });
  }

  // GET /api/categories - 获取分类
  if (path === '/api/categories' && method === 'GET') {
    const categories = db.query('SELECT * FROM sys_web_categories ORDER BY sort_order').all();
    return Response.json({
      success: true,
      data: categories,
    });
  }

  // POST /api/pages/:id/view - 记录访问
  const viewMatch = path.match(/^\/api\/pages\/([^/]+)\/view$/);
  if (viewMatch && method === 'POST') {
    const pageId = decodeURIComponent(viewMatch[1]);

    // 更新或插入统计
    db.exec(`
      INSERT INTO sys_web_page_stats (page_id, view_count, last_viewed_at)
      VALUES ('${pageId}', 1, datetime('now'))
      ON CONFLICT(page_id) DO UPDATE SET
        view_count = view_count + 1,
        last_viewed_at = datetime('now')
    `);

    return Response.json({ success: true });
  }

  // POST /api/pages - 注册新页面
  if (path === '/api/pages' && method === 'POST') {
    if (!body || !body.page_id || !body.title || !body.source_type || !body.source_path) {
      return Response.json({ success: false, error: 'Missing required fields' }, { status: 400 });
    }

    registerPage(db, body);
    return Response.json({ success: true, page_id: body.page_id });
  }

  // DELETE /api/pages/:id - 删除页面
  const deleteMatch = path.match(/^\/api\/pages\/([^/]+)$/);
  if (deleteMatch && method === 'DELETE') {
    const pageId = decodeURIComponent(deleteMatch[1]);
    db.exec(`DELETE FROM sys_web_pages WHERE page_id = '${pageId}'`);
    return Response.json({ success: true });
  }

  return Response.json({ success: false, error: 'Not found' }, { status: 404 });
}

// ============================================================================
// 静态文件服务
// ============================================================================

function serveStaticFile(path: string): Response {
  // 默认 index.html
  if (path === '/' || path === '') {
    path = '/index.html';
  }

  const filePath = join(WEB_ROOT, path);

  // 安全检查：防止目录遍历
  if (!filePath.startsWith(WEB_ROOT)) {
    return new Response('Forbidden', { status: 403 });
  }

  if (!existsSync(filePath)) {
    return new Response('Not Found', { status: 404 });
  }

  const stat = statSync(filePath);
  if (!stat.isFile()) {
    return new Response('Not Found', { status: 404 });
  }

  const content = readFileSync(filePath);
  const ext = extname(filePath);
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  return new Response(content, {
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache',
    },
  });
}

// ============================================================================
// 主服务器
// ============================================================================

function startServer(): void {
  // 初始化数据库
  const db = new Database(DB_PATH);
  initDatabase(db);
  scanAndRegisterPages(db);

  console.log('╭─ 🌐 Solar Web Dashboard ─────────────────────╮');
  console.log('│                                              │');
  console.log(`│  URL: http://localhost:${PORT}                  │`);
  console.log('│                                              │');
  console.log('│  API Endpoints:                              │');
  console.log('│    GET  /api/pages          - 所有页面       │');
  console.log('│    GET  /api/pages/pinned   - 固定页面       │');
  console.log('│    GET  /api/pages/recent   - 最近访问       │');
  console.log('│    GET  /api/categories     - 分类列表       │');
  console.log('│    POST /api/pages/:id/view - 记录访问       │');
  console.log('│    POST /api/pages          - 注册页面       │');
  console.log('│                                              │');
  console.log('╰──────────────────────────────────────────────╯');

  Bun.serve({
    port: PORT,

    async fetch(req) {
      const url = new URL(req.url);
      const path = url.pathname;
      const method = req.method;

      // CORS 头
      const corsHeaders = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      };

      // OPTIONS 预检请求
      if (method === 'OPTIONS') {
        return new Response(null, { headers: corsHeaders });
      }

      // API 请求
      if (path.startsWith('/api/')) {
        let body;
        if (method === 'POST' || method === 'PUT') {
          try {
            body = await req.json();
          } catch {
            body = {};
          }
        }

        const response = handleApiRequest(db, path, method, body);

        // 添加 CORS 头
        const headers = new Headers(response.headers);
        Object.entries(corsHeaders).forEach(([k, v]) => headers.set(k, v));

        return new Response(response.body, {
          status: response.status,
          headers,
        });
      }

      // 静态文件
      return serveStaticFile(path);
    },

    error(error) {
      console.error('Server error:', error);
      return new Response('Internal Server Error', { status: 500 });
    },
  });
}

// ============================================================================
// 启动
// ============================================================================

startServer();
