# Cortex Query v0.2 实现计划

## Context

**问题**: 现有 Cortex 系统缺少统一查询入口，无法高效检索 artifact、source、claim 等知识资产。

**解决方案**: 实现 Cortex Query 统一入口，采用三件套架构：
```
Tantivy (召回) → SQLite (门禁) → FS (装配) → CapsuleView/QA
```

**设计原则**: 兼容现有系统、最小改动、分阶段落地

---

## Phase 1: 基础查询 (1-2天)

### 1.1 扩展 Tantivy Schema

**文件**: `/Users/lisihao/Solar/core/search/src/schema.rs`

**改动**:
```rust
// 1. 扩展 DocType 枚举
pub enum DocType {
    Conversation, Memory, Code, Document, Registry, Stats,
    // 新增
    Artifact, Source, Claim, Knowledge,
}

// 2. 新增字段
schema_builder.add_f64_field("score", STORED | FAST);        // 可信度
schema_builder.add_text_field("kind", STRING | STORED);      // 类型
schema_builder.add_text_field("tags", TEXT | STORED);        // 标签
schema_builder.add_text_field("task_id", STRING | STORED);   // 任务ID
schema_builder.add_text_field("citation_key", STRING | STORED); // 引用键
```

### 1.2 扩展 SQLite 表

**文件**: `/Users/lisihao/.claude/core/cortex/schema.sql`

**改动**:
```sql
-- 1. 扩展 cortex_artifacts 表
ALTER TABLE cortex_artifacts ADD COLUMN kind TEXT;
ALTER TABLE cortex_artifacts ADD COLUMN ts_ms INTEGER;
ALTER TABLE cortex_artifacts ADD COLUMN score REAL;
ALTER TABLE cortex_artifacts ADD COLUMN status TEXT;
ALTER TABLE cortex_artifacts ADD COLUMN source_type TEXT;
ALTER TABLE cortex_artifacts ADD COLUMN content_path TEXT;
ALTER TABLE cortex_artifacts ADD COLUMN hash TEXT;
ALTER TABLE cortex_artifacts ADD COLUMN citation_key TEXT;

-- 2. 新增 artifact_edges 表
CREATE TABLE cortex_artifact_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_id INTEGER NOT NULL,
    dst_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. 新增视图
CREATE VIEW v_cortex_search AS ...;
```

### 1.3 创建 cortex-query.ts

**文件**: `/Users/lisihao/.claude/core/cortex/cortex-query.ts` (新建)

**核心 API**:
```typescript
interface CortexQueryParams {
  q: string;                    // 查询文本
  task_scope?: string[];        // task_id 过滤
  k?: number;                   // 返回数量
  gate_policy?: 'loose' | 'strict' | 'none';
  need?: ('snippets' | 'evidence' | 'trace')[];
}

interface CortexQueryResult {
  hits: CortexHit[];
  evidence_pack?: EvidencePack;
  trace?: QueryTrace;
  meta: { latency_ms, tantivy_docs, sqlite_filtered, final_count };
}

class CortexQuery {
  async query(params: CortexQueryParams): Promise<CortexQueryResult>;
  private async tantivySearch(params): Promise<TantivyHit[]>;
  private async sqliteGate(hits, params): Promise<SqliteHit[]>;
  private async enrichFromFS(hits, params): Promise<CortexHit[]>;
}
```

**CLI 入口**:
```bash
bun cortex-query.ts search "GPU optimization" 10
bun cortex-query.ts sync  # 同步 Cortex 数据到 Tantivy
bun cortex-query.ts stats
```

### 1.4 测试

**文件**: `/Users/lisihao/.claude/core/cortex/cortex-query.test.ts` (新建)

**测试用例**:
- 基础搜索返回结果
- 门禁策略过滤低分
- task_scope 限制结果
- evidence_pack 构建

---

## Phase 2: 门禁强化 (1天)

### 2.1 门禁策略实现

- `loose`: 只过滤 deprecated
- `strict`: 要求 validated + score >= 0.7
- `none`: 不过滤

### 2.2 Evidence Pack

返回 sources, claims, edges 的完整引用链

### 2.3 性能优化

目标: P50 延迟 < 100ms

---

## Phase 3: 证据闭环 (1天)

### 3.1 自动同步

Cortex 变更 → 自动同步到 Tantivy

### 3.2 Hash 校验

验证 content_hash 一致性

### 3.3 meta.json 生成

保存产物时自动生成元数据

---

## 关键文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `Solar/core/search/src/schema.rs` | 修改 | 扩展 DocType + 新增字段 |
| `.claude/core/cortex/schema.sql` | 修改 | 扩展表 + 新增视图 |
| `.claude/core/cortex/index.ts` | 修改 | 扩展 saveArtifact |
| `.claude/core/cortex/cortex-query.ts` | 新建 | 核心 API |
| `.claude/core/cortex/cortex-query.test.ts` | 新建 | 测试 |

---

## 验证方案

```bash
# 1. 重新编译 Tantivy
cd ~/Solar/core/search && cargo build --release

# 2. 运行数据库迁移
sqlite3 ~/.solar/solar.db < schema.sql

# 3. 同步现有数据
bun cortex-query.ts sync

# 4. 测试查询
bun cortex-query.ts search "memory architecture" 5

# 5. 运行测试
bun test cortex-query.test.ts
```

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Tantivy schema 变更需要重建索引 | 保留旧索引，增量添加 |
| SQLite ALTER TABLE 可能有兼容问题 | 使用 IF NOT EXISTS 兜底 |
| FS 路径迁移成本高 | 保持现有路径，增量添加 meta.json |
