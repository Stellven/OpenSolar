-- Cortex Query v0.2 数据库迁移
-- 安全添加新字段到 cortex_artifacts 表
-- 执行方式: sqlite3 ~/.solar/solar.db < migrate-v0.2.sql

-- 添加新列 (每个单独执行，忽略已存在错误)
-- SQLite 不支持 IF NOT EXISTS for ADD COLUMN，所以用异常处理

-- 如果需要手动执行，可以逐条运行：
-- ALTER TABLE cortex_artifacts ADD COLUMN kind TEXT;
-- ALTER TABLE cortex_artifacts ADD COLUMN ts_ms INTEGER;
-- ALTER TABLE cortex_artifacts ADD COLUMN score REAL;
-- ALTER TABLE cortex_artifacts ADD COLUMN status TEXT DEFAULT 'active';
-- ALTER TABLE cortex_artifacts ADD COLUMN source_type TEXT;
-- ALTER TABLE cortex_artifacts ADD COLUMN content_path TEXT;
-- ALTER TABLE cortex_artifacts ADD COLUMN hash TEXT;
-- ALTER TABLE cortex_artifacts ADD COLUMN citation_key TEXT;

-- 扩展 cortex_sources 表
-- ALTER TABLE cortex_sources ADD COLUMN content_path TEXT;
-- ALTER TABLE cortex_sources ADD COLUMN hash TEXT;
-- ALTER TABLE cortex_sources ADD COLUMN fetched_at DATETIME;

-- 创建新表和视图（已包含在 schema.sql 中，这里是备份）
-- CREATE TABLE IF NOT EXISTS cortex_artifact_edges (...);
-- CREATE VIEW IF NOT EXISTS v_cortex_search AS ...;
