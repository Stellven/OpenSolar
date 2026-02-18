-- Knowledge Ontology v1.0
-- 参考 graph_maker 设计，用于指导知识提取

-- Ontology 定义表：实体类型 + 提取指令
CREATE TABLE IF NOT EXISTS knowledge_ontology_labels (
    label_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 实体类型名称，如 'person', 'technology'
    description TEXT,                     -- 类型描述
    extraction_prompt TEXT NOT NULL,      -- 提取指令（给 LLM 的指导）
    examples JSON,                        -- 提取示例
    priority INTEGER DEFAULT 50,          -- 匹配优先级
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Ontology 关系定义表
CREATE TABLE IF NOT EXISTS knowledge_ontology_relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 关系名称，如 'uses', 'created_by'
    description TEXT,
    extraction_prompt TEXT,              -- 如何识别这种关系
    source_labels JSON,                  -- 源实体类型限制，如 ['person']
    target_labels JSON,                  -- 目标实体类型限制，如 ['technology']
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 默认 Ontology 数据
INSERT OR REPLACE INTO knowledge_ontology_labels (name, description, extraction_prompt, priority) VALUES
-- 人物类
('person', '人物实体', '人名，不包含任何形容词。记住一个人可能被名字或代词引用。提取完整姓名，不要头衔如"博士""教授"。', 90),
('organization', '组织机构', '公司、团队、机构、社区名称。包含完整的组织名，不包含"the"等冠词。', 80),

-- 技术类
('technology', '技术/框架/库', '技术名称、编程框架、库、工具。使用官方名称，不包含版本号。如 React, Kubernetes, BERT', 85),
('framework', '开发框架', '软件开发框架。如 Django, Spring, React', 75),
('tool', '工具/软件', '开发工具、软件产品。如 VS Code, Docker, Git', 70),
('language', '编程语言', '编程语言名称。如 Python, JavaScript, Rust', 70),
('algorithm', '算法', '算法名称。如 QuickSort, Transformer, Dijkstra', 65),

-- 概念类
('concept', '抽象概念', '重要的抽象概念、理论、方法论。如 微服务, 函数式编程, CAP定理', 60),
('method', '方法/技术方案', '解决问题的具体方法或方案。如 TDD, CI/CD, 知识图谱', 55),

-- 产品类
('product', '产品/服务', '软件产品、在线服务。如 GPT-4, Claude, GitHub Copilot', 70),

-- 内容类
('document', '文档/论文', '技术文档、学术论文、书籍。提取标题', 50),
('paper', '学术论文', '学术论文标题。包含完整的论文标题', 50),

-- 其他
('event', '事件', '涉及多个人物的事件。不包含动词如"举办了""参加了"', 45),
('place', '地点', '地理位置、城市、国家', 40),
('metric', '指标/数据', '性能指标、数据单位。如 QPS, 延迟, 吞吐量', 35),
('other', '其他重要概念', '无法归类到其他类型的重要概念', 10);

-- 默认关系定义
INSERT OR REPLACE INTO knowledge_ontology_relations (name, description, extraction_prompt, source_labels, target_labels) VALUES
-- 创建/发明关系
('created_by', '由...创建', 'X 是由 Y 创建/发明/开发的', '["technology", "framework", "tool", "product"]', '["person", "organization"]'),
('developed_by', '由...开发', 'X 是由 Y 开发的', '["technology", "product"]', '["person", "organization"]'),

-- 使用关系
('uses', '使用', 'X 使用 Y', NULL, NULL),
('depends_on', '依赖于', 'X 依赖于 Y', '["technology", "framework"]', '["technology", "framework", "tool"]'),
('based_on', '基于', 'X 基于 Y 构建', '["technology", "framework", "algorithm"]', '["technology", "framework", "algorithm"]'),

-- 包含关系
('contains', '包含', 'X 包含 Y', NULL, NULL),
('part_of', '是...的一部分', 'X 是 Y 的一部分', NULL, NULL),

-- 竞争/替代关系
('competes_with', '竞争关系', 'X 与 Y 竞争', NULL, NULL),
('alternative_to', '替代方案', 'X 是 Y 的替代方案', NULL, NULL),

-- 相关关系
('related_to', '相关', 'X 与 Y 相关', NULL, NULL),
('similar_to', '相似', 'X 与 Y 相似', NULL, NULL),

-- 优势关系
('better_than', '优于', 'X 优于 Y（在某个方面）', NULL, NULL),
('improves', '改进', 'X 改进了 Y', NULL, NULL),

-- 属于关系
('category_of', '是...的类别', 'X 是 Y 的一个类别/类型', NULL, NULL),
('type_of', '是...的一种', 'X 是 Y 的一种类型', NULL, NULL),

-- 文档关系
('documented_in', '记录于', 'X 在 Y 中被记录/描述', NULL, '["document", "paper"]'),
('cites', '引用', 'X 引用了 Y', '["document", "paper"]', '["document", "paper"]'),

-- 人物关系
('works_for', '工作于', 'X 在 Y 工作', '["person"]', '["organization"]'),
('member_of', '成员', 'X 是 Y 的成员', '["person"]', '["organization"]');

-- 视图：获取启用的 Ontology
CREATE VIEW IF NOT EXISTS v_active_ontology_labels AS
SELECT name, description, extraction_prompt, priority
FROM knowledge_ontology_labels
WHERE enabled = TRUE
ORDER BY priority DESC;

CREATE VIEW IF NOT EXISTS v_active_ontology_relations AS
SELECT name, description, extraction_prompt, source_labels, target_labels
FROM knowledge_ontology_relations
WHERE enabled = TRUE;
