-- ============================================================
-- 自动知识捕获系统 - 数据库 Schema
-- 目标：捕获所有搜索、专家输出、开发产物为知识抽取做储备
-- ============================================================

-- 1. 搜索结果缓存表
CREATE TABLE IF NOT EXISTS sys_search_cache (
    search_id TEXT PRIMARY KEY,
    search_type TEXT NOT NULL,           -- 'grep' | 'glob' | 'websearch' | 'webfetch' | 'read'
    query TEXT NOT NULL,                 -- 查询内容
    context TEXT,                        -- 查询上下文（用户意图）
    results TEXT,                        -- 搜索结果（JSON）
    result_count INTEGER,                -- 结果数量
    tool_params TEXT,                    -- 工具参数（JSON）
    session_id TEXT,                     -- 会话ID
    synced_to_graph INTEGER DEFAULT 0,  -- 是否已同步到知识图谱（0/1）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- 索引
    CHECK (search_type IN ('grep', 'glob', 'websearch', 'webfetch', 'read'))
);

CREATE INDEX IF NOT EXISTS idx_search_cache_type ON sys_search_cache(search_type);
CREATE INDEX IF NOT EXISTS idx_search_cache_synced ON sys_search_cache(synced_to_graph);
CREATE INDEX IF NOT EXISTS idx_search_cache_created ON sys_search_cache(created_at DESC);

-- 2. 专家输出缓存表
CREATE TABLE IF NOT EXISTS sys_expert_outputs (
    output_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,                 -- 模型名称（glm-5, gemini-2.5-pro等）
    expert_role TEXT,                    -- 专家角色（稳健派、探索派等）
    system_prompt TEXT,                  -- system prompt
    user_prompt TEXT NOT NULL,           -- 用户提示
    output TEXT NOT NULL,                -- 专家输出内容
    task_type TEXT,                      -- 任务类型（analysis, code, review等）
    context TEXT,                        -- 任务上下文
    tokens_input INTEGER,                -- 输入token数
    tokens_output INTEGER,               -- 输出token数
    latency_ms INTEGER,                  -- 延迟（毫秒）
    session_id TEXT,                     -- 会话ID
    synced_to_graph INTEGER DEFAULT 0,  -- 是否已同步到知识图谱（0/1）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_expert_outputs_model ON sys_expert_outputs(model);
CREATE INDEX IF NOT EXISTS idx_expert_outputs_synced ON sys_expert_outputs(synced_to_graph);
CREATE INDEX IF NOT EXISTS idx_expert_outputs_created ON sys_expert_outputs(created_at DESC);

-- 3. 开发产物缓存表
CREATE TABLE IF NOT EXISTS sys_dev_artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,         -- 'code' | 'design' | 'analysis' | 'decision' | 'test'
    title TEXT NOT NULL,                 -- 产物标题
    content TEXT NOT NULL,               -- 产物内容
    file_path TEXT,                      -- 关联文件路径（如果有）
    tags TEXT,                           -- 标签（JSON数组）
    context TEXT,                        -- 产生上下文
    related_task TEXT,                   -- 关联任务
    importance INTEGER DEFAULT 5,        -- 重要性（1-10）
    session_id TEXT,                     -- 会话ID
    synced_to_graph INTEGER DEFAULT 0,  -- 是否已同步到知识图谱（0/1）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- 索引
    CHECK (artifact_type IN ('code', 'design', 'analysis', 'decision', 'test', 'refactor', 'architecture'))
);

CREATE INDEX IF NOT EXISTS idx_dev_artifacts_type ON sys_dev_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_dev_artifacts_synced ON sys_dev_artifacts(synced_to_graph);
CREATE INDEX IF NOT EXISTS idx_dev_artifacts_importance ON sys_dev_artifacts(importance DESC);
CREATE INDEX IF NOT EXISTS idx_dev_artifacts_created ON sys_dev_artifacts(created_at DESC);

-- 4. 统一待抽取视图
CREATE VIEW IF NOT EXISTS v_pending_extraction AS
SELECT
    'search' as source_type,
    search_id as source_id,
    query as title,
    results as content,
    created_at
FROM sys_search_cache
WHERE synced_to_graph = 0

UNION ALL

SELECT
    'expert' as source_type,
    output_id as source_id,
    COALESCE(expert_role, model) as title,
    output as content,
    created_at
FROM sys_expert_outputs
WHERE synced_to_graph = 0

UNION ALL

SELECT
    'artifact' as source_type,
    artifact_id as source_id,
    title,
    content,
    created_at
FROM sys_dev_artifacts
WHERE synced_to_graph = 0

ORDER BY created_at DESC;

-- 5. 统计视图
CREATE VIEW IF NOT EXISTS v_capture_stats AS
SELECT
    'Search Cache' as category,
    COUNT(*) as total,
    SUM(CASE WHEN synced_to_graph = 1 THEN 1 ELSE 0 END) as synced,
    COUNT(*) - SUM(CASE WHEN synced_to_graph = 1 THEN 1 ELSE 0 END) as pending
FROM sys_search_cache

UNION ALL

SELECT
    'Expert Outputs' as category,
    COUNT(*) as total,
    SUM(CASE WHEN synced_to_graph = 1 THEN 1 ELSE 0 END) as synced,
    COUNT(*) - SUM(CASE WHEN synced_to_graph = 1 THEN 1 ELSE 0 END) as pending
FROM sys_expert_outputs

UNION ALL

SELECT
    'Dev Artifacts' as category,
    COUNT(*) as total,
    SUM(CASE WHEN synced_to_graph = 1 THEN 1 ELSE 0 END) as synced,
    COUNT(*) - SUM(CASE WHEN synced_to_graph = 1 THEN 1 ELSE 0 END) as pending
FROM sys_dev_artifacts;
