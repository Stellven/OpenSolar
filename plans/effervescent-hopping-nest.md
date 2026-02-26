# 知识库大修方案 - Knowledge Base Overhaul

## Context

Solar 知识库当前存在严重质量问题：
- **98.7% 的关系是 co_occurs_in 垃圾数据**（1730/1753），源于 knowledge-extractor.ts 对 wikilinks 做笛卡尔积
- **cortex_claims 仅 3 条**（vs 490 条 sources），知识沉淀严重不足
- **104 个孤立实体**（38.8%），无任何有意义关联
- **抽取逻辑是正则模式**，`callExpert()` 函数是 MOCK（返回空数组），未真正使用 LLM

监护人要求：① 用好 LLM 做抽取 ② 体现人物师承/时空演变等有意义关联 ③ 有价值语义而非共现词表 ④ 补充 claims

## 实施计划（4 个交付物 + 5 个阶段）

### Phase 1: 清理垃圾数据 — `knowledge-cleanup.ts`

**文件**: `~/.claude/core/cortex/knowledge-cleanup.ts`（新建）

**操作**:
1. 删除全部 1730 条 `co_occurs_in` 关系
2. 删除 704 条 knowledge_claims（全是从 co_occurs_in 派生的低质量 claims）
3. 删除孤立实体（无任何有意义关系的实体，约 104 个）
4. 保留 cortex_sources（490 条）、cortex_artifacts（134 条）、cortex_claims（3 条）
5. 保留有意义的非 co_occurs_in 关系（约 23 条）

**SQL 核心**:
```sql
-- 1. 删垃圾关系
DELETE FROM knowledge_relations WHERE relation_type = 'co_occurs_in';
-- 2. 删低质量 claims
DELETE FROM knowledge_claims WHERE domain = 'general' AND confidence < 0.5;
-- 3. 删孤立实体（清理后无关系的）
DELETE FROM knowledge_entities WHERE entity_id NOT IN (
  SELECT DISTINCT from_entity FROM knowledge_relations
  UNION SELECT DISTINCT to_entity FROM knowledge_relations
);
```

**执行**: `bun ~/.claude/core/cortex/knowledge-cleanup.ts`
**验证**: 清理前后记录数对比表

---

### Phase 2: LLM 知识抽取器 — `knowledge-llm-extractor.ts`

**文件**: `~/.claude/core/cortex/knowledge-llm-extractor.ts`（新建）

**核心设计**:
- 使用 brain-router HTTP API（参考 `lesson-llm-extractor.ts` 的 `fetch('http://localhost:15721/v1/complete')` 模式）
- 注入 D&D KNOBS 人格（从 `niumao-anchors.json` 读取）
- 默认用 `glm-5`（日常抽取），复杂内容用 `deepseek-r1`（深度推理）

**LLM Prompt 设计**（关键！）:
```
你是一名知识图谱专家。从以下文本中抽取结构化知识。

要求：
1. 实体：人名、技术、概念、组织、框架、工具
2. 关系（必须是以下 22 种语义类型之一）：
   - 人物关系: mentor_of, student_of, collaborator_with, founded_by
   - 技术关系: evolved_from, enables, requires, alternative_to, component_of, extends
   - 时间关系: preceded_by, succeeded_by, concurrent_with
   - 因果关系: caused_by, leads_to, mitigates
   - 学术关系: cited_by, builds_upon, contradicts, validates
   - 层级关系: part_of, instance_of
3. Claims：从文本中提炼 2-5 条核心论断，标注置信度和支持证据

输出 JSON 格式：
{
  "entities": [{ "name": "...", "type": "person|technology|concept|org|framework|tool", "description": "..." }],
  "relations": [{ "from": "...", "to": "...", "type": "上述22种之一", "evidence": "原文依据", "confidence": 0.0-1.0 }],
  "claims": [{ "text": "核心论断", "confidence": 0.0-1.0, "supporting_entities": ["..."], "evidence": "..." }]
}
```

**函数签名**:
```typescript
extractKnowledge(text: string, options?: {
  model?: string;        // 默认 glm-5
  sourceId?: string;     // 关联 cortex_source
  favoriteId?: number;   // 关联 sys_favorites
}): Promise<ExtractionResult>
```

**写入逻辑**:
- 实体 → `knowledge_entities`（UPSERT，合并 aliases）
- 关系 → `knowledge_relations`（去重，type 必须在 22 种内）
- Claims → `knowledge_claims`（domain 标注来源领域）
- 同时生成 `cortex_claims`（高置信度 ≥ 0.7 的 claims 自动升级）

**参考文件**:
- `~/.claude/core/cortex/lesson-llm-extractor.ts` — brain-router HTTP 调用模式
- `~/.claude/core/solar-farm/niumao-anchors.json` — D&D KNOBS 人格定义
- `~/.claude/core/cortex/knowledge-network.ts` — addEntity/addRelation/addClaim 方法

---

### Phase 3: 批量处理器 — `knowledge-batch-extract.ts`

**文件**: `~/.claude/core/cortex/knowledge-batch-extract.ts`（新建）

**数据源**: `sys_favorites`（94 条，42 条 importance ≥ 8，14 条未同步到知识库）

**处理流程**:
```
1. 查询 sys_favorites WHERE importance >= 7 ORDER BY importance DESC
2. 跳过已处理的（通过 source_favorite_id 关联判断）
3. 对每条 favorite 调用 extractKnowledge()
4. 记录处理进度（断点续传）
5. 输出统计报告
```

**特性**:
- 断点续传：记录已处理的 favorite_id 到 `~/.solar/knowledge-batch-progress.json`
- 速率控制：每条间隔 2 秒，避免 API 过载
- 错误处理：失败记录跳过并记录，不阻塞全流程
- 增量模式：只处理新增/未处理的 favorites

**执行**: `bun ~/.claude/core/cortex/knowledge-batch-extract.ts [--limit 10] [--min-importance 7]`

---

### Phase 4: Claims 富化器 — `claims-enricher.ts`

**文件**: `~/.claude/core/cortex/claims-enricher.ts`（新建）

**目标**: 从 490 条 cortex_sources 生成高质量 cortex_claims

**处理逻辑**:
```
1. 读取 cortex_sources（按 credibility DESC）
2. 按 task_id 分组（同一洞察任务的多条 source 合并分析）
3. 调用 LLM 提炼核心 claims：
   - 每组 source 提炼 3-5 条 claims
   - 交叉引用多个 sources 的 supporting_sources
   - 寻找 counter_claims（不同 source 间的矛盾观点）
4. 写入 cortex_claims 表
5. 与 knowledge_entities 建立关联
```

**LLM Prompt**:
```
你是一名学术评审专家。从以下多条研究发现中提炼核心论断。

要求：
1. 每条 claim 必须有明确的支持证据（引用 source_id）
2. 标注置信度（基于 source 的 credibility 加权）
3. 主动寻找矛盾观点（counter_claims）
4. 关联相关实体

输出 JSON：
{
  "claims": [{
    "claim_text": "...",
    "supporting_sources": ["source_id_1", "source_id_2"],
    "counter_claims": ["如果有反面证据..."],
    "confidence": 0.85,
    "domain": "AI_engineering|system_design|..."
  }]
}
```

**执行**: `bun ~/.claude/core/cortex/claims-enricher.ts [--limit 50]`

---

### Phase 5: 验证与统计

**验证方式**:

```bash
# 1. 数据量验证
sqlite3 ~/.solar/solar.db "
SELECT 'entities' as type, COUNT(*) FROM knowledge_entities
UNION ALL SELECT 'relations', COUNT(*) FROM knowledge_relations
UNION ALL SELECT 'claims', COUNT(*) FROM knowledge_claims
UNION ALL SELECT 'cortex_claims', COUNT(*) FROM cortex_claims;
"

# 2. 关系类型多样性
sqlite3 ~/.solar/solar.db "
SELECT relation_type, COUNT(*) as cnt
FROM knowledge_relations
GROUP BY relation_type ORDER BY cnt DESC;
"

# 3. 无 co_occurs_in 垃圾
sqlite3 ~/.solar/solar.db "
SELECT COUNT(*) FROM knowledge_relations WHERE relation_type='co_occurs_in';
"
# 期望: 0

# 4. 抽样检查关系质量
sqlite3 ~/.solar/solar.db "
SELECT e1.name, r.relation_type, e2.name, r.evidence
FROM knowledge_relations r
JOIN knowledge_entities e1 ON r.from_entity = e1.entity_id
JOIN knowledge_entities e2 ON r.to_entity = e2.entity_id
ORDER BY r.confidence DESC LIMIT 20;
"
```

**预期结果**:

| 指标 | 清理前 | 目标 |
|------|--------|------|
| relations 总数 | 1753 | 200-400（100% 有意义） |
| co_occurs_in 占比 | 98.7% | 0% |
| relation_type 种类 | 7 | 15-20 |
| cortex_claims | 3 | 200-500 |
| 孤立实体比例 | 38.8% | < 10% |

## 实施顺序

```
Phase 1 (清理) → Phase 2 (核心抽取器) → Phase 3 (批量处理) → Phase 4 (Claims 富化) → Phase 5 (验证)
```

每个 Phase 完成后 checkpoint + 验证，确保可回滚。

## 关键文件参考

| 文件 | 用途 |
|------|------|
| `~/.claude/core/cortex/lesson-llm-extractor.ts` | brain-router HTTP 调用模板 |
| `~/.claude/core/solar-farm/niumao-anchors.json` | D&D KNOBS 人格注入 |
| `~/.claude/core/cortex/knowledge-network.ts` | addEntity/addRelation/addClaim |
| `~/.claude/core/cortex/knowledge-extractor.ts` | 旧抽取器（需修复/替换） |
| `~/.solar/solar.db` | 知识库数据库 |
