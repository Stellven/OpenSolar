-- ============================================================
-- Persona Bank 竞技场机制 - Database Schema
-- 用途: 记录"人格配置→rubric得分"，ELO排名，自动选择最优人格
-- ============================================================

-- 1. 人格配置库
CREATE TABLE IF NOT EXISTS sys_persona_configs (
    persona_id TEXT PRIMARY KEY,           -- 人格ID (如 gemini_pro_analyst_v1)
    model TEXT NOT NULL,                   -- 模型名 (gemini-2.5-pro, deepseek-r1)
    role TEXT NOT NULL,                    -- 角色 (分析师、审核员、作家)
    big_five_json TEXT NOT NULL,           -- Big Five 参数 JSON: {O,C,E,A,N}
    behavioral_guidelines TEXT,            -- 行为准则 (做什么/不做什么)
    language_style TEXT,                   -- 语言风格 (正式度/情感基调)
    forbidden_patterns TEXT,               -- 禁止模式
    required_patterns TEXT,                -- 必须模式
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'solar',       -- 创建者
    status TEXT DEFAULT 'active',          -- 状态: active/archived
    notes TEXT                             -- 备注
);

-- 2. 人格评分记录（每次使用后记录）
CREATE TABLE IF NOT EXISTS sys_persona_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id TEXT NOT NULL,              -- 人格ID
    task_id TEXT NOT NULL,                 -- 任务ID (insight session)
    phase TEXT NOT NULL,                   -- 阶段 (collect/fill_gaps/peer_review/compose)
    rubric_json TEXT NOT NULL,             -- 评分细项 JSON: {clarity,evidence,logic,accuracy,language}
    overall_score REAL NOT NULL,           -- 综合得分 (1-10)
    evaluator_persona_id TEXT,             -- 评估者人格ID (互评时)
    evaluated_by TEXT,                     -- 评估者类型 (self/peer/user)
    problems_json TEXT,                    -- 问题列表 JSON
    suggestions_json TEXT,                 -- 建议列表 JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (persona_id) REFERENCES sys_persona_configs(persona_id),
    FOREIGN KEY (evaluator_persona_id) REFERENCES sys_persona_configs(persona_id)
);

-- 3. ELO 排名系统
CREATE TABLE IF NOT EXISTS sys_persona_elo (
    persona_id TEXT PRIMARY KEY,           -- 人格ID
    elo_rating REAL DEFAULT 1500.0,        -- ELO 分数 (初始1500)
    total_matches INTEGER DEFAULT 0,       -- 总对局数
    wins INTEGER DEFAULT 0,                -- 胜利次数
    losses INTEGER DEFAULT 0,              -- 失败次数
    draws INTEGER DEFAULT 0,               -- 平局次数
    win_rate REAL DEFAULT 0.0,             -- 胜率 (wins/total_matches)
    avg_score REAL DEFAULT 0.0,            -- 平均得分
    last_match_at DATETIME,                -- 最后对局时间
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (persona_id) REFERENCES sys_persona_configs(persona_id)
);

-- 4. 对局记录（A评B、B评A）
CREATE TABLE IF NOT EXISTS sys_persona_matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,                 -- 任务ID
    persona_a TEXT NOT NULL,               -- 人格A
    persona_b TEXT NOT NULL,               -- 人格B
    score_a REAL NOT NULL,                 -- A的得分 (B给的)
    score_b REAL NOT NULL,                 -- B的得分 (A给的)
    winner TEXT,                           -- 胜者 (persona_a/persona_b/draw)
    elo_change_a REAL,                     -- A的ELO变化
    elo_change_b REAL,                     -- B的ELO变化
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (persona_a) REFERENCES sys_persona_configs(persona_id),
    FOREIGN KEY (persona_b) REFERENCES sys_persona_configs(persona_id)
);

-- 5. 索引优化
CREATE INDEX IF NOT EXISTS idx_persona_scores_persona ON sys_persona_scores(persona_id);
CREATE INDEX IF NOT EXISTS idx_persona_scores_task ON sys_persona_scores(task_id);
CREATE INDEX IF NOT EXISTS idx_persona_scores_phase ON sys_persona_scores(phase);
CREATE INDEX IF NOT EXISTS idx_persona_matches_task ON sys_persona_matches(task_id);
CREATE INDEX IF NOT EXISTS idx_persona_elo_rating ON sys_persona_elo(elo_rating DESC);

-- 6. 视图：当前排行榜
CREATE VIEW IF NOT EXISTS v_persona_leaderboard AS
SELECT
    e.persona_id,
    c.model,
    c.role,
    e.elo_rating,
    e.win_rate,
    e.total_matches,
    e.wins,
    e.losses,
    e.avg_score,
    c.status,
    RANK() OVER (ORDER BY e.elo_rating DESC) as rank
FROM sys_persona_elo e
JOIN sys_persona_configs c ON e.persona_id = c.persona_id
WHERE c.status = 'active'
ORDER BY e.elo_rating DESC;

-- 7. 视图：人格详细统计
CREATE VIEW IF NOT EXISTS v_persona_stats AS
SELECT
    c.persona_id,
    c.model,
    c.role,
    e.elo_rating,
    e.win_rate,
    e.total_matches,
    COUNT(DISTINCT s.task_id) as task_count,
    AVG(s.overall_score) as avg_rubric_score,
    MAX(s.overall_score) as best_score,
    MIN(s.overall_score) as worst_score,
    c.created_at,
    e.last_match_at
FROM sys_persona_configs c
LEFT JOIN sys_persona_elo e ON c.persona_id = e.persona_id
LEFT JOIN sys_persona_scores s ON c.persona_id = s.persona_id
WHERE c.status = 'active'
GROUP BY c.persona_id
ORDER BY e.elo_rating DESC;

-- 8. 视图：最近对局
CREATE VIEW IF NOT EXISTS v_recent_matches AS
SELECT
    m.match_id,
    m.task_id,
    ca.model || ' (' || ca.role || ')' as persona_a_name,
    cb.model || ' (' || cb.role || ')' as persona_b_name,
    m.score_a,
    m.score_b,
    m.winner,
    m.elo_change_a,
    m.elo_change_b,
    m.created_at
FROM sys_persona_matches m
JOIN sys_persona_configs ca ON m.persona_a = ca.persona_id
JOIN sys_persona_configs cb ON m.persona_b = cb.persona_id
ORDER BY m.created_at DESC
LIMIT 50;

-- 9. 触发器：自动更新 ELO 表
CREATE TRIGGER IF NOT EXISTS tr_persona_scores_insert
AFTER INSERT ON sys_persona_scores
BEGIN
    -- 更新平均得分
    UPDATE sys_persona_elo
    SET avg_score = (
        SELECT AVG(overall_score)
        FROM sys_persona_scores
        WHERE persona_id = NEW.persona_id
    ),
    updated_at = CURRENT_TIMESTAMP
    WHERE persona_id = NEW.persona_id;

    -- 如果没有记录，插入初始记录
    INSERT OR IGNORE INTO sys_persona_elo (persona_id)
    VALUES (NEW.persona_id);
END;

-- 10. 触发器：自动更新对局统计
CREATE TRIGGER IF NOT EXISTS tr_persona_matches_insert
AFTER INSERT ON sys_persona_matches
BEGIN
    -- 更新人格A的统计
    UPDATE sys_persona_elo
    SET total_matches = total_matches + 1,
        wins = wins + CASE WHEN NEW.winner = NEW.persona_a THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN NEW.winner = NEW.persona_b THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN NEW.winner = 'draw' THEN 1 ELSE 0 END,
        win_rate = CAST(wins + CASE WHEN NEW.winner = NEW.persona_a THEN 1 ELSE 0 END AS REAL) /
                   (total_matches + 1),
        elo_rating = elo_rating + COALESCE(NEW.elo_change_a, 0),
        last_match_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE persona_id = NEW.persona_a;

    -- 更新人格B的统计
    UPDATE sys_persona_elo
    SET total_matches = total_matches + 1,
        wins = wins + CASE WHEN NEW.winner = NEW.persona_b THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN NEW.winner = NEW.persona_a THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN NEW.winner = 'draw' THEN 1 ELSE 0 END,
        win_rate = CAST(wins + CASE WHEN NEW.winner = NEW.persona_b THEN 1 ELSE 0 END AS REAL) /
                   (total_matches + 1),
        elo_rating = elo_rating + COALESCE(NEW.elo_change_b, 0),
        last_match_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE persona_id = NEW.persona_b;
END;

-- ============================================================
-- 种子数据：初始人格配置
-- ============================================================

-- 技术宅 (Gemini 2.5 Pro) - 严谨审核
INSERT OR IGNORE INTO sys_persona_configs
(persona_id, model, role, big_five_json, behavioral_guidelines, language_style, status)
VALUES (
    'gemini_pro_analyst_strict',
    'gemini-2.5-pro',
    '严谨分析师',
    '{"O": 0.2, "C": 1.0, "E": 0.5, "A": 0.4, "N": 0.2}',
    '必须：事实验证、引用来源、逻辑一致性。禁止：猜测、夸大、模糊表述。',
    '正式、精确、客观',
    'active'
);

-- 思考驼 (DeepSeek R1) - 深度推理
INSERT OR IGNORE INTO sys_persona_configs
(persona_id, model, role, big_five_json, behavioral_guidelines, language_style, status)
VALUES (
    'deepseek_r1_reasoner_deep',
    'deepseek-r1',
    '深度推理师',
    '{"O": 0.8, "C": 0.8, "E": 0.4, "A": 0.6, "N": 0.5}',
    '必须：多角度分析、反驳自己、显示推理过程。禁止：仓促结论、忽略反例。',
    '逻辑、反思、层次化',
    'active'
);

-- 鬼才码农 (DeepSeek V3) - 创意实现
INSERT OR IGNORE INTO sys_persona_configs
(persona_id, model, role, big_five_json, behavioral_guidelines, language_style, status)
VALUES (
    'deepseek_v3_writer_creative',
    'deepseek-v3',
    '创意作家',
    '{"O": 1.0, "C": 0.6, "E": 0.6, "A": 0.5, "N": 0.4}',
    '必须：生动表达、多元视角、创新观点。禁止：陈词滥调、刻板叙述。',
    '灵活、生动、中文优先',
    'active'
);

-- 千里马 (Gemini 3 Pro) - 创新探索
INSERT OR IGNORE INTO sys_persona_configs
(persona_id, model, role, big_five_json, behavioral_guidelines, language_style, status)
VALUES (
    'gemini_3_explorer_innovative',
    'gemini-3-pro-preview',
    '创新探索者',
    '{"O": 0.9, "C": 0.7, "E": 0.9, "A": 0.7, "N": 0.3}',
    '必须：前沿视角、跨领域联想、大胆假设。禁止：保守、墨守成规。',
    '热情、创新、前瞻',
    'active'
);

-- 初始化 ELO 表
INSERT OR IGNORE INTO sys_persona_elo (persona_id, elo_rating)
SELECT persona_id, 1500.0 FROM sys_persona_configs WHERE status = 'active';
