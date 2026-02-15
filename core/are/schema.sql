-- ============================================
-- Agentic Runtime Engine (ARE) - Database Schema
-- ============================================

-- Plan Cache: Store compiled plans for reuse
CREATE TABLE IF NOT EXISTS are_plan_cache (
    plan_id TEXT PRIMARY KEY,
    intent_hash TEXT NOT NULL,
    intent_text TEXT,
    intent_embedding BLOB,              -- Semantic vector for similarity matching
    plan_ir TEXT NOT NULL,              -- JSON: Full PlanIR

    -- Statistics
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    total_executions INTEGER DEFAULT 0,
    avg_latency_ms REAL,

    -- Metadata
    version TEXT DEFAULT '1.0',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME,
    expires_at DATETIME,

    -- Compilation mode
    compile_mode TEXT DEFAULT 'jit',    -- 'jit', 'aot', 'hybrid'
    compiled_artifact BLOB              -- For AOT: pre-compiled execution plan
);

CREATE INDEX IF NOT EXISTS idx_are_plan_intent ON are_plan_cache(intent_hash);
CREATE INDEX IF NOT EXISTS idx_are_plan_last_used ON are_plan_cache(last_used_at);

-- Result Cache: Cache task execution results
CREATE TABLE IF NOT EXISTS are_result_cache (
    cache_key TEXT PRIMARY KEY,         -- task_id + params_hash
    plan_id TEXT,
    task_id TEXT,
    result TEXT NOT NULL,               -- JSON: execution result
    result_type TEXT,                   -- Return type

    -- Metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    hit_count INTEGER DEFAULT 0,
    last_hit DATETIME,
    size_bytes INTEGER,

    -- Dependency tracking for invalidation
    dependency_keys TEXT,               -- JSON array of dependent cache keys

    FOREIGN KEY (plan_id) REFERENCES are_plan_cache(plan_id)
);

CREATE INDEX IF NOT EXISTS idx_are_result_plan ON are_result_cache(plan_id);
CREATE INDEX IF NOT EXISTS idx_are_result_expires ON are_result_cache(expires_at);

-- Execution Log: Record all plan executions
CREATE TABLE IF NOT EXISTS are_execution_log (
    execution_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    session_id TEXT,

    -- Status
    status TEXT NOT NULL,               -- 'pending', 'running', 'completed', 'failed', 'cancelled'

    -- Timing
    start_time DATETIME,
    end_time DATETIME,
    duration_ms INTEGER,

    -- Results
    task_results TEXT,                  -- JSON array of TaskResult
    final_outputs TEXT,                 -- JSON: final variable values

    -- Metrics
    total_tasks INTEGER,
    completed_tasks INTEGER,
    failed_tasks INTEGER,
    cached_tasks INTEGER,
    parallel_efficiency REAL,

    -- Error info
    error_code TEXT,
    error_message TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (plan_id) REFERENCES are_plan_cache(plan_id)
);

CREATE INDEX IF NOT EXISTS idx_are_exec_plan ON are_execution_log(plan_id);
CREATE INDEX IF NOT EXISTS idx_are_exec_session ON are_execution_log(session_id);
CREATE INDEX IF NOT EXISTS idx_are_exec_time ON are_execution_log(start_time);

-- Task Execution Details: Per-task metrics
CREATE TABLE IF NOT EXISTS are_task_execution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    task_id TEXT NOT NULL,

    -- Status
    status TEXT NOT NULL,               -- 'success', 'failed', 'skipped', 'cached'
    tier TEXT,                          -- 'cache', 'primitive', 'script', 'sandbox'

    -- Timing
    start_time DATETIME,
    end_time DATETIME,
    duration_ms INTEGER,
    queue_time_ms INTEGER,              -- Time waiting for dependencies

    -- Data
    input_bytes INTEGER,
    output_bytes INTEGER,

    -- Cache
    cached BOOLEAN DEFAULT FALSE,
    cache_key TEXT,

    -- Error
    error_code TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    FOREIGN KEY (execution_id) REFERENCES are_execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_are_task_exec ON are_task_execution(execution_id);
CREATE INDEX IF NOT EXISTS idx_are_task_status ON are_task_execution(status);

-- Optimization Log: Track optimization decisions
CREATE TABLE IF NOT EXISTS are_optimization_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- What was optimized
    optimization_type TEXT NOT NULL,    -- 'cache_ttl', 'parallel_degree', 'timeout', 'jit_to_aot', 'sandbox'
    target TEXT NOT NULL,               -- task pattern or plan_id

    -- Change
    old_value TEXT,
    new_value TEXT,

    -- Evidence
    evidence TEXT,                      -- JSON: metrics that triggered this
    expected_improvement REAL,
    confidence REAL,

    -- Result
    applied BOOLEAN DEFAULT FALSE,
    actual_improvement REAL,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    applied_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_are_opt_type ON are_optimization_log(optimization_type);

-- Hotspot Analysis: Track frequently executed patterns
CREATE TABLE IF NOT EXISTS are_hotspots (
    pattern_hash TEXT PRIMARY KEY,
    task_pattern TEXT NOT NULL,         -- Normalized task action pattern

    -- Frequency
    execution_count INTEGER DEFAULT 0,
    last_executed DATETIME,

    -- Performance
    avg_latency_ms REAL,
    p95_latency_ms REAL,
    cache_hit_rate REAL,

    -- Optimization status
    compile_mode TEXT DEFAULT 'jit',
    promoted_to_aot BOOLEAN DEFAULT FALSE,
    promotion_date DATETIME,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Views for Analysis
-- ============================================

-- Plan performance overview
CREATE VIEW IF NOT EXISTS v_are_plan_performance AS
SELECT
    p.plan_id,
    p.intent_text,
    p.success_count,
    p.fail_count,
    p.total_executions,
    p.avg_latency_ms,
    ROUND(CAST(p.success_count AS REAL) / NULLIF(p.total_executions, 0) * 100, 2) as success_rate,
    p.compile_mode,
    p.last_used_at
FROM are_plan_cache p
ORDER BY p.total_executions DESC;

-- Cache hit rate by task pattern
CREATE VIEW IF NOT EXISTS v_are_cache_analysis AS
SELECT
    substr(cache_key, 1, instr(cache_key, '_') - 1) as task_pattern,
    COUNT(*) as total_entries,
    SUM(hit_count) as total_hits,
    ROUND(AVG(hit_count), 2) as avg_hits_per_entry,
    ROUND(AVG((julianday('now') - julianday(created_at)) * 24 * 60), 2) as avg_age_minutes
FROM are_result_cache
GROUP BY task_pattern
ORDER BY total_hits DESC;

-- Recent execution summary
CREATE VIEW IF NOT EXISTS v_are_recent_executions AS
SELECT
    e.execution_id,
    p.intent_text,
    e.status,
    e.duration_ms,
    e.total_tasks,
    e.completed_tasks,
    e.cached_tasks,
    ROUND(CAST(e.cached_tasks AS REAL) / NULLIF(e.total_tasks, 0) * 100, 2) as cache_rate,
    e.parallel_efficiency,
    e.start_time
FROM are_execution_log e
LEFT JOIN are_plan_cache p ON e.plan_id = p.plan_id
ORDER BY e.start_time DESC
LIMIT 100;

-- Hotspots needing optimization
CREATE VIEW IF NOT EXISTS v_are_optimization_candidates AS
SELECT
    pattern_hash,
    task_pattern,
    execution_count,
    avg_latency_ms,
    cache_hit_rate,
    compile_mode,
    CASE
        WHEN execution_count > 100 AND compile_mode = 'jit' AND avg_latency_ms > 50
        THEN 'promote_to_aot'
        WHEN cache_hit_rate < 0.3 AND avg_latency_ms > 100
        THEN 'increase_cache_ttl'
        WHEN avg_latency_ms > 500
        THEN 'investigate_bottleneck'
        ELSE 'none'
    END as suggestion
FROM are_hotspots
WHERE execution_count > 10
ORDER BY execution_count * avg_latency_ms DESC;

-- Integration with existing telemetry
CREATE VIEW IF NOT EXISTS v_are_telemetry_summary AS
SELECT
    category,
    operation,
    COUNT(*) as total_ops,
    ROUND(AVG(duration_ms), 2) as avg_duration_ms,
    ROUND(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate,
    SUM(input_bytes + output_bytes) as total_bytes
FROM tel_operations
WHERE timestamp > datetime('now', '-7 days')
GROUP BY category, operation
ORDER BY total_ops DESC;
