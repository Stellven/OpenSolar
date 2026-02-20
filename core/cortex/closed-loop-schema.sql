-- ============================================
-- Solar 自演进闭环系统 Schema 扩展
-- 创建时间: 2026-02-19
-- 目标: 让 Q-scores 同时影响 Model + Skill + Tool 的选择决策
-- ============================================

-- ============================================
-- Phase 1: 数据关联 - evo_traces 添加归因字段
-- 解决断点 #1: Traces 没有模型归因
-- ============================================

-- 添加模型/技能/工具归因
ALTER TABLE evo_traces ADD COLUMN selected_model TEXT;
ALTER TABLE evo_traces ADD COLUMN selected_skill TEXT;
ALTER TABLE evo_traces ADD COLUMN selected_tools TEXT;  -- JSON array
ALTER TABLE evo_traces ADD COLUMN sroe_request_id TEXT;

-- 添加意图置信度 (intent 字段已存在)
ALTER TABLE evo_traces ADD COLUMN intent_confidence REAL DEFAULT 0.0;

-- ============================================
-- Phase 2: 路由表扩展 - 添加 Q-score 关联
-- 解决断点 #2 和 #6: Q-scores 不影响路由 + 没有自动参数更新
-- ============================================

-- sys_routing_model: 添加 Q-score 关联
ALTER TABLE sys_routing_model ADD COLUMN q_score_id TEXT;
ALTER TABLE sys_routing_model ADD COLUMN effective_score REAL DEFAULT 0.5;
ALTER TABLE sys_routing_model ADD COLUMN base_weight REAL DEFAULT 0.5;

-- sys_routing_agent: 添加 Q-score 关联
ALTER TABLE sys_routing_agent ADD COLUMN q_score_id TEXT;
ALTER TABLE sys_routing_agent ADD COLUMN effective_score REAL DEFAULT 0.5;
ALTER TABLE sys_routing_agent ADD COLUMN base_weight REAL DEFAULT 0.5;

-- sys_routing_tool: 添加 Q-score 关联
ALTER TABLE sys_routing_tool ADD COLUMN q_score_id TEXT;
ALTER TABLE sys_routing_tool ADD COLUMN effective_score REAL DEFAULT 0.5;
ALTER TABLE sys_routing_tool ADD COLUMN base_weight REAL DEFAULT 0.5;

-- ============================================
-- Phase 3: 创建 Q-score 关联视图
-- 方便查询带评分的路由决策
-- ============================================

-- Model 路由 + Q-score 视图
CREATE VIEW IF NOT EXISTS v_routing_model_qscore AS
SELECT
    rm.id,
    rm.rule_name,
    rm.target_model,
    rm.priority,
    rm.enabled,
    rm.base_weight,
    COALESCE(qs.satisfaction, 0.5) as q_score,
    rm.base_weight * COALESCE(qs.satisfaction, 0.5) as effective_score,
    qs.updated_at as score_updated_at
FROM sys_routing_model rm
LEFT JOIN sys_quality_scores qs
    ON qs.entity_id = rm.target_model
    AND qs.entity_type = 'model';

-- Agent 路由 + Q-score 视图
CREATE VIEW IF NOT EXISTS v_routing_agent_qscore AS
SELECT
    ra.id,
    ra.rule_name,
    ra.target_agent,
    ra.priority,
    ra.enabled,
    ra.base_weight,
    COALESCE(qs.satisfaction, 0.5) as q_score,
    ra.base_weight * COALESCE(qs.satisfaction, 0.5) as effective_score,
    qs.updated_at as score_updated_at
FROM sys_routing_agent ra
LEFT JOIN sys_quality_scores qs
    ON qs.entity_id = ra.target_agent
    AND qs.entity_type = 'agent';

-- Tool 路由 + Q-score 视图
CREATE VIEW IF NOT EXISTS v_routing_tool_qscore AS
SELECT
    rt.id,
    rt.rule_name,
    rt.target_tool,
    rt.priority,
    rt.enabled,
    rt.base_weight,
    COALESCE(qs.satisfaction, 0.5) as q_score,
    rt.base_weight * COALESCE(qs.satisfaction, 0.5) as effective_score,
    qs.updated_at as score_updated_at
FROM sys_routing_tool rt
LEFT JOIN sys_quality_scores qs
    ON qs.entity_id = rt.target_tool
    AND qs.entity_type = 'skill';

-- ============================================
-- Phase 4: 创建综合路由决策视图
-- 展示所有路由选项 + Q-scores
-- ============================================

CREATE VIEW IF NOT EXISTS v_routing_all_with_scores AS
SELECT
    'model' as routing_type,
    id,
    rule_name,
    target_model as target,
    priority,
    enabled,
    base_weight,
    q_score,
    effective_score
FROM v_routing_model_qscore

UNION ALL

SELECT
    'agent' as routing_type,
    id,
    rule_name,
    target_agent as target,
    priority,
    enabled,
    base_weight,
    q_score,
    effective_score
FROM v_routing_agent_qscore

UNION ALL

SELECT
    'tool' as routing_type,
    id,
    rule_name,
    target_tool as target,
    priority,
    enabled,
    base_weight,
    q_score,
    effective_score
FROM v_routing_tool_qscore

ORDER BY routing_type, effective_score DESC;

-- ============================================
-- Phase 5: 创建统计视图
-- 监控闭环系统健康度
-- ============================================

-- Trace 归因率统计
CREATE VIEW IF NOT EXISTS v_trace_attribution_stats AS
SELECT
    DATE(started_at) as date,
    COUNT(*) as total_traces,
    COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) as model_linked,
    COUNT(CASE WHEN selected_skill IS NOT NULL THEN 1 END) as skill_linked,
    COUNT(CASE WHEN selected_tools IS NOT NULL THEN 1 END) as tools_linked,
    ROUND(COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as model_attribution_rate
FROM evo_traces
GROUP BY DATE(started_at)
ORDER BY date DESC
LIMIT 30;

-- Q-score 分布统计
CREATE VIEW IF NOT EXISTS v_qscore_distribution AS
SELECT
    entity_type,
    entity_id,
    COUNT(*) as sample_count,
    ROUND(AVG(satisfaction), 3) as avg_satisfaction,
    ROUND(MIN(satisfaction), 3) as min_satisfaction,
    ROUND(MAX(satisfaction), 3) as max_satisfaction,
    ROUND(AVG(completion_rate), 3) as avg_completion_rate
FROM sys_quality_scores
GROUP BY entity_type, entity_id
ORDER BY entity_type, avg_satisfaction DESC;

-- ============================================
-- Phase 6: 创建索引优化查询
-- ============================================

-- evo_traces 查询优化
CREATE INDEX IF NOT EXISTS idx_traces_session_model
ON evo_traces(session_id, selected_model);

CREATE INDEX IF NOT EXISTS idx_traces_started_at
ON evo_traces(started_at);

-- Q-scores 查询优化
CREATE INDEX IF NOT EXISTS idx_qscores_entity
ON sys_quality_scores(entity_type, entity_id);

-- 路由表查询优化
CREATE INDEX IF NOT EXISTS idx_routing_model_score
ON sys_routing_model(effective_score DESC);

CREATE INDEX IF NOT EXISTS idx_routing_agent_score
ON sys_routing_agent(effective_score DESC);

CREATE INDEX IF NOT EXISTS idx_routing_tool_score
ON sys_routing_tool(effective_score DESC);

-- ============================================
-- 完成
-- ============================================
-- 执行完成后，运行验证:
--   sqlite3 ~/.solar/solar.db "SELECT * FROM v_routing_model_qscore LIMIT 5;"
--   sqlite3 ~/.solar/solar.db "SELECT * FROM v_trace_attribution_stats LIMIT 5;"
-- ============================================
