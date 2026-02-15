-- ============================================================
-- 小爱洞察调度系统 - 数据表结构
-- 设计目标：小爱调度老专家，Solar CEO 做考评
-- ============================================================

-- 任务表：小爱发起的分析任务
CREATE TABLE IF NOT EXISTS xiaoai_insight_tasks (
    task_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,                    -- 分析主题
    requester TEXT DEFAULT 'email',         -- 来源: email/chat
    requester_email TEXT,                   -- 请求人邮箱
    status TEXT DEFAULT 'pending',          -- pending/analyzing/reviewing/done/failed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- 专家分配表：每个任务分配哪些专家
CREATE TABLE IF NOT EXISTS xiaoai_expert_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    expert_model TEXT NOT NULL,             -- glm-4-plus, gemini-2.5-pro, deepseek-r1, etc.
    expert_role TEXT NOT NULL,              -- author/reviewer/challenger
    assigned_chapter TEXT,                  -- 分配的章节
    status TEXT DEFAULT 'pending',          -- pending/working/done/failed
    started_at DATETIME,
    completed_at DATETIME,
    FOREIGN KEY (task_id) REFERENCES xiaoai_insight_tasks(task_id)
);

-- 专家输出表：老专家们的具体产出
CREATE TABLE IF NOT EXISTS xiaoai_expert_outputs (
    output_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    assignment_id INTEGER,
    expert_model TEXT NOT NULL,
    output_type TEXT NOT NULL,              -- analysis/review/challenge/synthesis
    content TEXT NOT NULL,                  -- 完整输出内容
    token_count INTEGER,                    -- 消耗的 token 数
    latency_ms INTEGER,                     -- 响应延迟
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES xiaoai_insight_tasks(task_id),
    FOREIGN KEY (assignment_id) REFERENCES xiaoai_expert_assignments(assignment_id)
);

-- 互评表：专家之间的评价
CREATE TABLE IF NOT EXISTS xiaoai_peer_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    reviewer_model TEXT NOT NULL,           -- 评价者
    reviewee_model TEXT NOT NULL,           -- 被评价者
    output_id INTEGER NOT NULL,             -- 被评价的输出
    score REAL NOT NULL,                    -- 0-10 分
    dimensions JSON,                        -- 各维度评分 {"accuracy": 8, "depth": 7, "clarity": 9}
    feedback TEXT,                          -- 文字反馈
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES xiaoai_insight_tasks(task_id),
    FOREIGN KEY (output_id) REFERENCES xiaoai_expert_outputs(output_id)
);

-- CEO 考评表：Solar CEO 对专家的综合评分
CREATE TABLE IF NOT EXISTS ceo_expert_evaluations (
    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    expert_model TEXT NOT NULL,
    period_start DATE NOT NULL,             -- 考评周期开始
    period_end DATE NOT NULL,               -- 考评周期结束
    task_count INTEGER DEFAULT 0,           -- 参与任务数
    avg_peer_score REAL,                    -- 平均互评分
    avg_quality_score REAL,                 -- 平均质量分
    completion_rate REAL,                   -- 完成率
    efficiency_score REAL,                  -- 效率分 (token/质量)
    overall_grade TEXT,                     -- A/B/C/D/F
    ceo_comments TEXT,                      -- CEO 点评
    evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(expert_model, period_start, period_end)
);

-- CEO 调度建议表：基于考评的调度策略
CREATE TABLE IF NOT EXISTS ceo_scheduling_policy (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    expert_model TEXT NOT NULL,
    task_type TEXT NOT NULL,                -- research/analysis/review/code
    priority_score REAL DEFAULT 0.5,        -- 0-1 优先级
    recommended BOOLEAN DEFAULT true,       -- 是否推荐使用
    reason TEXT,                            -- 推荐/不推荐原因
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(expert_model, task_type)
);

-- 视图：专家综合绩效
CREATE VIEW IF NOT EXISTS v_expert_performance AS
SELECT
    eo.expert_model,
    COUNT(DISTINCT eo.task_id) as task_count,
    COUNT(eo.output_id) as output_count,
    AVG(pr.score) as avg_peer_score,
    SUM(eo.token_count) as total_tokens,
    AVG(eo.latency_ms) as avg_latency,
    -- 效率分 = 质量分 / (token消耗/1000)
    CASE WHEN SUM(eo.token_count) > 0
         THEN AVG(pr.score) * 1000 / (SUM(eo.token_count) / COUNT(eo.output_id))
         ELSE 0 END as efficiency_score
FROM xiaoai_expert_outputs eo
LEFT JOIN xiaoai_peer_reviews pr ON eo.output_id = pr.output_id
GROUP BY eo.expert_model;

-- 视图：任务进度
CREATE VIEW IF NOT EXISTS v_xiaoai_task_progress AS
SELECT
    t.task_id,
    t.topic,
    t.status,
    t.requester_email,
    COUNT(DISTINCT ea.assignment_id) as expert_count,
    SUM(CASE WHEN ea.status = 'done' THEN 1 ELSE 0 END) as completed_count,
    t.created_at,
    t.completed_at
FROM xiaoai_insight_tasks t
LEFT JOIN xiaoai_expert_assignments ea ON t.task_id = ea.task_id
GROUP BY t.task_id;

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_xiaoai_outputs_task ON xiaoai_expert_outputs(task_id);
CREATE INDEX IF NOT EXISTS idx_xiaoai_reviews_task ON xiaoai_peer_reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_xiaoai_outputs_model ON xiaoai_expert_outputs(expert_model);
