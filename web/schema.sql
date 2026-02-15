-- ============================================================================
-- Solar Web Dashboard - Database Schema
-- 动态标签页管理系统
-- ============================================================================

-- 页面注册表
CREATE TABLE IF NOT EXISTS sys_web_pages (
    page_id TEXT PRIMARY KEY,           -- 唯一标识
    title TEXT NOT NULL,                 -- 标签标题
    icon TEXT DEFAULT '📄',              -- 标签图标 (emoji)
    category TEXT DEFAULT 'general',     -- 分类: system/architecture/report/tool
    description TEXT,                    -- 页面描述
    source_type TEXT NOT NULL,           -- file/url/html
    source_path TEXT NOT NULL,           -- 文件路径/URL/内联HTML
    sort_order INTEGER DEFAULT 100,      -- 排序顺序 (越小越前)
    pinned BOOLEAN DEFAULT false,        -- 是否固定标签
    enabled BOOLEAN DEFAULT true,        -- 是否启用
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 页面访问统计
CREATE TABLE IF NOT EXISTS sys_web_page_stats (
    page_id TEXT PRIMARY KEY REFERENCES sys_web_pages(page_id),
    view_count INTEGER DEFAULT 0,
    last_viewed_at DATETIME,
    avg_view_duration_sec REAL DEFAULT 0
);

-- 页面分类
CREATE TABLE IF NOT EXISTS sys_web_categories (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '📁',
    sort_order INTEGER DEFAULT 100,
    color TEXT DEFAULT '#00d4ff'
);

-- 默认分类
INSERT OR REPLACE INTO sys_web_categories VALUES
    ('system', '系统', '⚙️', 10, '#00d4ff'),
    ('architecture', '架构', '🏗️', 20, '#ff79c6'),
    ('report', '报告', '📊', 30, '#50fa7b'),
    ('tool', '工具', '🔧', 40, '#ffaa00'),
    ('general', '通用', '📄', 100, '#888888');

-- ============================================================================
-- 视图
-- ============================================================================

-- 启用的页面列表 (按分类和排序)
CREATE VIEW IF NOT EXISTS v_web_pages AS
SELECT
    p.*,
    c.name as category_name,
    c.icon as category_icon,
    c.color as category_color,
    COALESCE(s.view_count, 0) as view_count,
    s.last_viewed_at
FROM sys_web_pages p
LEFT JOIN sys_web_categories c ON p.category = c.category_id
LEFT JOIN sys_web_page_stats s ON p.page_id = s.page_id
WHERE p.enabled = true
ORDER BY p.pinned DESC, c.sort_order, p.sort_order, p.title;

-- 固定的标签页
CREATE VIEW IF NOT EXISTS v_pinned_pages AS
SELECT * FROM v_web_pages WHERE pinned = true;

-- 最近访问的页面
CREATE VIEW IF NOT EXISTS v_recent_pages AS
SELECT * FROM v_web_pages
WHERE last_viewed_at IS NOT NULL
ORDER BY last_viewed_at DESC
LIMIT 10;

-- ============================================================================
-- 触发器
-- ============================================================================

-- 更新时间戳
CREATE TRIGGER IF NOT EXISTS tr_web_pages_updated
AFTER UPDATE ON sys_web_pages
BEGIN
    UPDATE sys_web_pages SET updated_at = datetime('now')
    WHERE page_id = NEW.page_id;
END;
