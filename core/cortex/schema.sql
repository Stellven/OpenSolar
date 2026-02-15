-- ============================================================
-- Cortex v0.1 - 统一记忆与状态系统
-- 解决失忆 + 支撑 AI 管 AI
-- SQLite (WAL) + 文件系统
-- ============================================================

PRAGMA journal_mode=WAL;

-- ============================================================
-- 核心表: tasks - 任务追踪
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,              -- 'insight' | 'analysis' | 'report'
    topic TEXT NOT NULL,                  -- 任务主题
    requester TEXT,                       -- 请求人
    status TEXT DEFAULT 'pending',        -- pending → phase1 → phase2 → ... → completed
    current_phase INTEGER DEFAULT 0,      -- 当前阶段 (0-7)
    phase_status JSON,                    -- 每个阶段的状态 {"phase1": "done", "phase2": "in_progress", ...}
    config JSON,                          -- 任务配置 (专家列表、章节数等)
    metadata JSON,                        -- 额外元数据
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- ============================================================
-- 核心表: artifacts - 产物存储 (大纲、草稿、提示词等)
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_artifacts (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    phase INTEGER NOT NULL,               -- 属于哪个阶段
    artifact_type TEXT NOT NULL,          -- 'prompt' | 'outline' | 'draft' | 'review' | 'final'
    expert_model TEXT,                    -- 生成此产物的专家
    content_json JSON NOT NULL,           -- 结构化内容 (JSON格式)
    file_path TEXT,                       -- 持久化的文件路径
    token_count INTEGER,                  -- 消耗的 token
    latency_ms INTEGER,                   -- 生成延迟
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id)
);

-- ============================================================
-- 核心表: sources - 引用源
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    citation_key TEXT NOT NULL,           -- 引用键 (如 "smith2024")
    title TEXT NOT NULL,
    url TEXT,
    finding TEXT,                         -- 一句话发现
    credibility REAL DEFAULT 0.5,         -- 可信度 0-1
    expert_model TEXT,                    -- 哪个专家引用的
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id)
);

-- ============================================================
-- 核心表: claims - 论点/声明
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_claims (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    supporting_sources JSON,              -- 支持此论点的引用 ["source_id1", "source_id2"]
    counter_sources JSON,                 -- 反对此论点的引用
    expert_model TEXT,                    -- 提出此论点的专家
    confidence REAL DEFAULT 0.5,          -- 置信度 0-1
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id)
);

-- ============================================================
-- 核心表: evals - 互评矩阵
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_evals (
    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    phase INTEGER NOT NULL,               -- 评估阶段
    artifact_id INTEGER,                  -- 被评估的产物
    reviewer_model TEXT NOT NULL,         -- 评审专家
    target_model TEXT NOT NULL,           -- 被评审专家
    rubric JSON,                          -- 评分标准 {"accuracy": 8, "depth": 7, ...}
    score REAL NOT NULL,                  -- 综合分数 0-10
    verdict TEXT,                         -- 评审意见
    suggestions JSON,                     -- 改进建议
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id),
    FOREIGN KEY (artifact_id) REFERENCES cortex_artifacts(artifact_id)
);

-- ============================================================
-- 核心表: outline - 大纲结构
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_outline (
    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    section_order INTEGER NOT NULL,       -- 章节顺序
    section_title TEXT NOT NULL,
    goal TEXT,                            -- 章节目标
    required_claims JSON,                 -- 需要的论点 ["claim_id1", "claim_id2"]
    prompt TEXT,                          -- 章节提示词
    status TEXT DEFAULT 'pending',        -- pending | writing | reviewing | completed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id)
);

-- ============================================================
-- 核心表: draft_sections - 分段草稿
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_draft_sections (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    section_id INTEGER NOT NULL,
    expert_model TEXT NOT NULL,           -- 撰写专家
    version INTEGER DEFAULT 1,            -- 版本号
    content TEXT NOT NULL,                -- 草稿内容
    word_count INTEGER,
    is_final BOOLEAN DEFAULT FALSE,       -- 是否为最终版
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id),
    FOREIGN KEY (section_id) REFERENCES cortex_outline(section_id)
);

-- ============================================================
-- 核心表: cost - 成本追踪
-- ============================================================
CREATE TABLE IF NOT EXISTS cortex_cost (
    cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    phase INTEGER,
    expert_model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,              -- 估算成本 (美元)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES cortex_tasks(task_id)
);

-- ============================================================
-- 视图: 任务进度总览
-- ============================================================
CREATE VIEW IF NOT EXISTS v_cortex_task_progress AS
SELECT
    t.task_id,
    t.topic,
    t.status,
    t.current_phase,
    (SELECT COUNT(*) FROM cortex_artifacts WHERE task_id = t.task_id) as artifact_count,
    (SELECT COUNT(*) FROM cortex_sources WHERE task_id = t.task_id) as source_count,
    (SELECT COUNT(*) FROM cortex_claims WHERE task_id = t.task_id) as claim_count,
    (SELECT COUNT(*) FROM cortex_evals WHERE task_id = t.task_id) as eval_count,
    (SELECT SUM(cost_usd) FROM cortex_cost WHERE task_id = t.task_id) as total_cost,
    t.created_at,
    t.completed_at
FROM cortex_tasks t;

-- ============================================================
-- 视图: 专家绩效
-- ============================================================
CREATE VIEW IF NOT EXISTS v_cortex_expert_performance AS
SELECT
    e.target_model as expert_model,
    COUNT(*) as eval_count,
    AVG(e.score) as avg_score,
    (SELECT SUM(output_tokens) FROM cortex_cost WHERE expert_model = e.target_model) as total_tokens,
    (SELECT SUM(cost_usd) FROM cortex_cost WHERE expert_model = e.target_model) as total_cost
FROM cortex_evals e
GROUP BY e.target_model;

-- ============================================================
-- 视图: 最近任务
-- ============================================================
CREATE VIEW IF NOT EXISTS v_cortex_recent AS
SELECT
    task_id,
    task_type,
    topic,
    status,
    current_phase,
    created_at
FROM cortex_tasks
ORDER BY created_at DESC
LIMIT 20;

-- ============================================================
-- 索引优化
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_cortex_artifacts_task ON cortex_artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_cortex_sources_task ON cortex_sources(task_id);
CREATE INDEX IF NOT EXISTS idx_cortex_claims_task ON cortex_claims(task_id);
CREATE INDEX IF NOT EXISTS idx_cortex_evals_task ON cortex_evals(task_id);
CREATE INDEX IF NOT EXISTS idx_cortex_outline_task ON cortex_outline(task_id);
CREATE INDEX IF NOT EXISTS idx_cortex_cost_task ON cortex_cost(task_id);

-- ============================================================
-- 触发器: 自动更新 updated_at
-- ============================================================
CREATE TRIGGER IF NOT EXISTS tr_cortex_tasks_updated
AFTER UPDATE ON cortex_tasks
BEGIN
    UPDATE cortex_tasks SET updated_at = datetime('now') WHERE task_id = NEW.task_id;
END;

-- ============================================================
-- Cortex Query v0.2 扩展
-- 统一查询入口: Tantivy (召回) → SQLite (门禁) → FS (装配)
-- ============================================================

-- 扩展 cortex_artifacts 表字段 (安全添加，忽略已存在错误)
-- 注意: SQLite ALTER TABLE 不支持 IF NOT EXISTS，需要用 IGNORE 忽略错误
-- 以下字段可能已存在，执行时会报错，可忽略

-- 新增 cortex_artifact_edges 表 (引用链)
CREATE TABLE IF NOT EXISTS cortex_artifact_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_id INTEGER NOT NULL,           -- 源 artifact_id
    dst_id INTEGER NOT NULL,           -- 目标 artifact_id
    edge_type TEXT NOT NULL,           -- 'cites' | 'supports' | 'contradicts' | 'derives_from'
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (src_id) REFERENCES cortex_artifacts(artifact_id),
    FOREIGN KEY (dst_id) REFERENCES cortex_artifacts(artifact_id),
    UNIQUE(src_id, dst_id, edge_type)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_cortex_edge_src ON cortex_artifact_edges(src_id);
CREATE INDEX IF NOT EXISTS idx_cortex_edge_dst ON cortex_artifact_edges(dst_id);
CREATE INDEX IF NOT EXISTS idx_cortex_edge_type ON cortex_artifact_edges(edge_type);

-- Cortex 查询主视图 (门禁过滤)
CREATE VIEW IF NOT EXISTS v_cortex_search AS
SELECT
    a.artifact_id,
    a.task_id,
    COALESCE(NULL, a.artifact_type) as kind,
    a.phase,
    a.ts_ms,
    a.score,
    a.status,
    a.source_type,
    a.content_path,
    a.hash,
    a.citation_key,
    a.expert_model,
    t.topic as task_topic,
    a.created_at
FROM cortex_artifacts a
LEFT JOIN cortex_tasks t ON a.task_id = t.task_id
WHERE COALESCE(a.status, 'active') != 'deprecated';

-- Artifact 引用链视图
CREATE VIEW IF NOT EXISTS v_cortex_citation_chain AS
SELECT
    e.edge_id,
    e.src_id,
    e.dst_id,
    e.edge_type,
    e.confidence,
    src.citation_key as src_citation,
    src.title as src_title,
    dst.citation_key as dst_citation,
    dst.title as dst_title
FROM cortex_artifact_edges e
JOIN cortex_artifacts src ON e.src_id = src.artifact_id
JOIN cortex_artifacts dst ON e.dst_id = dst.artifact_id;

-- 来源可信度汇总视图
CREATE VIEW IF NOT EXISTS v_cortex_source_credibility AS
SELECT
    task_id,
    AVG(credibility) as avg_credibility,
    COUNT(*) as source_count,
    SUM(CASE WHEN credibility >= 0.8 THEN 1 ELSE 0 END) as high_cred_count
FROM cortex_sources
GROUP BY task_id;
