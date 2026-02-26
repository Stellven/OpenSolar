# 自演进闭环系统实现计划

> **目标**: 让 Q-scores 同时影响 Model + Skill + Tool 的选择决策
> **日期**: 2026-02-19

---

## Context (为什么做这个)

监护人在 2026-02-19 的对话中指出：

1. 已创建的三个定时任务（轨迹提取、反馈挖掘、Q值计算）形成了数据采集层
2. 但是数据"有采集无使用"——Q值计算出来了，但没有影响任何决策
3. 监护人明确要求："不仅仅是q值决定大模型使用啊，还要决定skill和工具"

**问题本质**: OODA 循环在 Orient 和 Decide 阶段断裂

```
Observe (✓)  →  Orient (✗)  →  Decide (✗)  →  Act (✓)
数据已采集       数据不关联      Q值不影响      执行正常
```

---

## 六个断点

| # | 断点 | 影响 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | Traces 没有模型归因 | 不知道哪个模型干得好 | P0 | 待修复 |
| 2 | Q-scores 不影响路由 | 评分白算 | P0 | 待修复 |
| 3 | 反馈不写入记忆 | 学不到教训 | P1 | 待修复 |
| 4 | 没有意图分类 | 不理解用户需求 | P1 | 待修复 |
| 5 | 反馈信号误分类 | 数据噪音大 | P2 | 待修复 |
| 6 | 没有自动参数更新 | 不能持续优化 | P0 | 待修复 |

---

## Phase 1: 数据关联 (P0 - 最高优先级)

### 目标
将 Trace 与 Model/Skill/Tool 关联，解决断点 #1

### 实现步骤

1. **创建 Data Linker 脚本**
   - 文件: `~/.claude/core/cortex/data-linker.ts`
   - 功能:
     - 通过 session_id + timestamp 匹配 evo_traces 和 sroe_requests
     - 从 sroe_requests 提取 selected_model 写入 evo_traces
   - 关键代码:
     ```typescript
     // 匹配逻辑: 同一 session 内，trace.started_at 接近 request.timestamp
     async linkTracesToRequests() {
       const query = `
         UPDATE evo_traces
         SET selected_model = r.selected_model,
             sroe_request_id = r.request_id
         FROM sroe_requests r
         WHERE evo_traces.session_id = r.session_id
           AND ABS(julianday(evo_traces.started_at) - julianday(r.timestamp)) < 0.0001
       `;
     }
     ```

2. **扩展 evo_traces 表结构**
   ```sql
   ALTER TABLE evo_traces ADD COLUMN selected_model TEXT;
   ALTER TABLE evo_traces ADD COLUMN selected_skill TEXT;
   ALTER TABLE evo_traces ADD COLUMN selected_tools TEXT;
   ALTER TABLE evo_traces ADD COLUMN sroe_request_id TEXT;
   ```

3. **创建 launchd 定时任务**
   - 文件: `~/Library/LaunchAgents/com.solar.data-linker.plist`
   - 间隔: 1 小时

---

## Phase 2: 路由表扩展 (P0)

### 目标
创建 Skill 和 Tool 的路由表，并关联 Q-scores，解决断点 #2 和 #6

### 实现步骤

1. **创建 sys_routing_skill 表**
   ```sql
   CREATE TABLE IF NOT EXISTS sys_routing_skill (
       routing_id TEXT PRIMARY KEY,
       skill_id TEXT NOT NULL,
       intent_pattern TEXT,
       q_score_id TEXT,
       base_weight REAL DEFAULT 0.5,
       effective_score REAL DEFAULT 0.5,
       enabled INTEGER DEFAULT 1,
       created_at DATETIME DEFAULT CURRENT_TIMESTAMP
   );
   ```

2. **创建 sys_routing_tool 表**
   ```sql
   CREATE TABLE IF NOT EXISTS sys_routing_tool (
       routing_id TEXT PRIMARY KEY,
       tool_name TEXT NOT NULL,
       task_type TEXT,
       q_score_id TEXT,
       base_weight REAL DEFAULT 0.5,
       effective_score REAL DEFAULT 0.5,
       enabled INTEGER DEFAULT 1,
       created_at DATETIME DEFAULT CURRENT_TIMESTAMP
   );
   ```

3. **修改 sys_routing_model 表**
   ```sql
   ALTER TABLE sys_routing_model ADD COLUMN q_score_id TEXT;
   ALTER TABLE sys_routing_model ADD COLUMN effective_score REAL DEFAULT 0.5;
   ```

4. **创建关联视图**
   ```sql
   CREATE VIEW v_routing_model_with_score AS
   SELECT r.*, COALESCE(q.satisfaction, 0.5) as q_score
   FROM sys_routing_model r
   LEFT JOIN sys_quality_scores q ON r.q_score_id = q.score_id;

   -- 同理创建 v_routing_skill_with_score, v_routing_tool_with_score
   ```

---

## Phase 3: 路由逻辑修改 (P0)

### 目标
修改 Brain Router 使用 Q-scores 进行决策

### 实现步骤

1. **创建 Routing Score Updater 脚本**
   - 文件: `~/.claude/core/cortex/routing-score-updater.ts`
   - 功能:
     - 从 sys_quality_scores 读取最新评分
     - 更新 sys_routing_model/agent/tool 的 effective_score
   - 关键逻辑:
     ```typescript
     // effective_score = base_weight × q_score × recency_factor
     async updateRoutingScores() {
       await this.db.run(`
         UPDATE sys_routing_model
         SET effective_score = base_weight * COALESCE(
           (SELECT satisfaction FROM sys_quality_scores
            WHERE entity_id = model_id AND entity_type = 'model'),
           0.5
         )
       `);
     }
     ```

2. **修改 Brain Router 决策逻辑**
   - 文件: Brain Router MCP (需确认位置)
   - 修改:
     - Model 选择: 按 effective_score DESC 排序
     - Skill 选择: 按 effective_score DESC 排序
     - Tool 选择: 按 effective_score DESC 排序

3. **创建 launchd 定时任务**
   - 文件: `~/Library/LaunchAgents/com.solar.routing-score-updater.plist`
   - 间隔: 4 小时（在 q-score-updater 之后运行）

---

## Phase 4: 反馈写记忆 (P1)

### 目标
将反馈信号写入记忆系统，解决断点 #3

### 实现步骤

1. **创建 Feedback to Memory 脚本**
   - 文件: `~/.claude/core/cortex/feedback-to-memory.ts`
   - 功能:
     - 显式负向反馈 → 写入 evo_memory_semantic 作为教训
     - 显式正向反馈 → 写入 evo_memory_semantic 作为成功经验
     - 更新 evo_memory_procedural 的熟练度

2. **记忆写入格式**
   ```typescript
   // 负向反馈
   {
     namespace: 'lessons',
     key: `lesson_${timestamp}`,
     value: JSON.stringify({
       context: '任务场景',
       mistake: '错误描述',
       correction: '正确做法',
       source_trace: trace_id
     })
   }
   ```

3. **创建 launchd 定时任务**
   - 间隔: 6 小时

---

## Phase 5: 意图分类 (P1)

### 目标
在 Trace 中记录用户意图，按意图统计 Q-scores，解决断点 #4

### 实现步骤

1. **集成 Intent Engine**
   - 现有文件: `~/.claude/core/intent-engine/engine.ts`
   - 修改 trajectory-extractor.ts，调用 Intent Engine

2. **扩展 evo_traces 表**
   ```sql
   ALTER TABLE evo_traces ADD COLUMN intent TEXT;
   ALTER TABLE evo_traces ADD COLUMN intent_confidence REAL;
   ```

3. **按意图统计 Q-scores**
   - 修改 q-score-updater.ts
   - 按 intent 分组计算评分

---

## 详细实现步骤

### Step 1: Schema 扩展 (closed-loop-schema.sql)

```sql
-- 1. evo_traces 添加模型归因
ALTER TABLE evo_traces ADD COLUMN selected_model TEXT;
ALTER TABLE evo_traces ADD COLUMN selected_skill TEXT;
ALTER TABLE evo_traces ADD COLUMN selected_tools TEXT;
ALTER TABLE evo_traces ADD COLUMN sroe_request_id TEXT;
ALTER TABLE evo_traces ADD COLUMN intent TEXT;
ALTER TABLE evo_traces ADD COLUMN intent_confidence REAL;

-- 2. 路由表添加 Q-score 关联
ALTER TABLE sys_routing_model ADD COLUMN q_score_id TEXT;
ALTER TABLE sys_routing_model ADD COLUMN effective_score REAL DEFAULT 0.5;
ALTER TABLE sys_routing_model ADD COLUMN base_weight REAL DEFAULT 0.5;

ALTER TABLE sys_routing_agent ADD COLUMN q_score_id TEXT;
ALTER TABLE sys_routing_agent ADD COLUMN effective_score REAL DEFAULT 0.5;
ALTER TABLE sys_routing_agent ADD COLUMN base_weight REAL DEFAULT 0.5;

ALTER TABLE sys_routing_tool ADD COLUMN q_score_id TEXT;
ALTER TABLE sys_routing_tool ADD COLUMN effective_score REAL DEFAULT 0.5;
ALTER TABLE sys_routing_tool ADD COLUMN base_weight REAL DEFAULT 0.5;

-- 3. 创建 Q-score 关联视图
CREATE VIEW IF NOT EXISTS v_routing_model_qscore AS
SELECT
    rm.id,
    rm.rule_name,
    rm.target_model,
    rm.priority,
    rm.enabled,
    COALESCE(qs.satisfaction, 0.5) as q_score,
    rm.base_weight * COALESCE(qs.satisfaction, 0.5) as effective_score
FROM sys_routing_model rm
LEFT JOIN sys_quality_scores qs ON qs.entity_id = rm.target_model AND qs.entity_type = 'model';

CREATE VIEW IF NOT EXISTS v_routing_agent_qscore AS
SELECT
    ra.id,
    ra.rule_name,
    ra.target_agent,
    ra.priority,
    ra.enabled,
    COALESCE(qs.satisfaction, 0.5) as q_score,
    ra.base_weight * COALESCE(qs.satisfaction, 0.5) as effective_score
FROM sys_routing_agent ra
LEFT JOIN sys_quality_scores qs ON qs.entity_id = ra.target_agent AND qs.entity_type = 'agent';

CREATE VIEW IF NOT EXISTS v_routing_tool_qscore AS
SELECT
    rt.id,
    rt.rule_name,
    rt.target_tool,
    rt.priority,
    rt.enabled,
    COALESCE(qs.satisfaction, 0.5) as q_score,
    rt.base_weight * COALESCE(qs.satisfaction, 0.5) as effective_score
FROM sys_routing_tool rt
LEFT JOIN sys_quality_scores qs ON qs.entity_id = rt.target_tool AND qs.entity_type = 'skill';
```

### Step 2: Data Linker (data-linker.ts)

```typescript
#!/usr/bin/env bun
/**
 * 数据关联器 - 将 Trace 与 Model/Skill/Tool 关联
 * 解决断点 #1: Traces 没有模型归因
 */

import { Database } from 'bun:sqlite';
import path from 'path';

class DataLinker {
  private db: Database;

  constructor() {
    const dbPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath);
  }

  /**
   * 关联 evo_traces 与 sroe_requests
   * 通过 session_id + 时间戳匹配
   */
  async linkTracesToRequests(): Promise<{ linked: number; total: number }> {
    // 匹配逻辑:
    // 1. 同一 session_id
    // 2. trace.started_at 与 request.timestamp 时间差 < 5秒
    const query = `
      UPDATE evo_traces
      SET
        selected_model = r.selected_model,
        sroe_request_id = r.request_id
      FROM sroe_requests r
      WHERE evo_traces.session_id = r.session_id
        AND evo_traces.selected_model IS NULL
        AND ABS(julianday(evo_traces.started_at) - julianday(r.timestamp)) < 0.0001
    `;

    const result = this.db.run(query);
    return { linked: result.changes, total: 0 };
  }

  async run(): Promise<void> {
    console.log('🔗 开始关联数据...');

    const stats = await this.linkTracesToRequests();
    console.log(`✅ 关联了 ${stats.linked} 条轨迹`);

    // 验证归因率
    const attribution = this.db.query(`
      SELECT
        COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as rate
      FROM evo_traces
    `).get() as { rate: number };

    console.log(`📊 当前归因率: ${attribution.rate.toFixed(1)}%`);

    this.db.close();
  }
}

if (import.meta.main) {
  new DataLinker().run();
}
```

### Step 3: Routing Score Updater (routing-score-updater.ts)

```typescript
#!/usr/bin/env bun
/**
 * 路由评分更新器 - 将 Q-scores 同步到路由表
 * 解决断点 #2: Q-scores 不影响路由决策
 */

import { Database } from 'bun:sqlite';
import path from 'path';

class RoutingScoreUpdater {
  private db: Database;

  constructor() {
    const dbPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath);
  }

  /**
   * 更新 Model 路由表的有效评分
   * effective_score = base_weight × q_score
   */
  updateModelScores(): number {
    const result = this.db.run(`
      UPDATE sys_routing_model
      SET effective_score = COALESCE(base_weight, 0.5) * COALESCE(
        (SELECT satisfaction FROM sys_quality_scores
         WHERE entity_id = target_model AND entity_type = 'model'),
        0.5
      )
    `);
    return result.changes;
  }

  /**
   * 更新 Agent 路由表的有效评分
   */
  updateAgentScores(): number {
    const result = this.db.run(`
      UPDATE sys_routing_agent
      SET effective_score = COALESCE(base_weight, 0.5) * COALESCE(
        (SELECT satisfaction FROM sys_quality_scores
         WHERE entity_id = target_agent AND entity_type = 'agent'),
        0.5
      )
    `);
    return result.changes;
  }

  /**
   * 更新 Tool 路由表的有效评分
   */
  updateToolScores(): number {
    const result = this.db.run(`
      UPDATE sys_routing_tool
      SET effective_score = COALESCE(base_weight, 0.5) * COALESCE(
        (SELECT satisfaction FROM sys_quality_scores
         WHERE entity_id = target_tool AND entity_type = 'skill'),
        0.5
      )
    `);
    return result.changes;
  }

  async run(): Promise<void> {
    console.log('📊 开始更新路由评分...');

    const models = this.updateModelScores();
    const agents = this.updateAgentScores();
    const tools = this.updateToolScores();

    console.log(`✅ Model: ${models} 条`);
    console.log(`✅ Agent: ${agents} 条`);
    console.log(`✅ Tool: ${tools} 条`);

    this.db.close();
  }
}

if (import.meta.main) {
  new RoutingScoreUpdater().run();
}
```

### Step 4: Feedback to Memory (feedback-to-memory.ts)

```typescript
#!/usr/bin/env bun
/**
 * 反馈写记忆 - 将反馈信号写入记忆系统
 * 解决断点 #3: 反馈不写入记忆
 */

import { Database } from 'bun:sqlite';
import path from 'path';

class FeedbackToMemory {
  private db: Database;

  constructor() {
    const dbPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath);
  }

  /**
   * 将高价值反馈写入语义记忆
   */
  writeToSemanticMemory(): number {
    // 提取负面反馈作为教训
    const negativeFeedback = this.db.query(`
      SELECT feedback_id, trigger_text, signal_type, related_model
      FROM evo_feedback_v2
      WHERE signal_type IN ('explicit_negative', 'task_failure')
        AND feedback_id NOT IN (
          SELECT json_extract(value, '$.source') FROM evo_memory_semantic
          WHERE namespace = 'lessons'
        )
      LIMIT 50
    `).all() as any[];

    const insert = this.db.prepare(`
      INSERT INTO evo_memory_semantic (namespace, key, value, credibility)
      VALUES ('lessons', ?, ?, 0.7)
    `);

    let count = 0;
    for (const fb of negativeFeedback) {
      const key = `lesson_${fb.feedback_id}`;
      const value = JSON.stringify({
        source: fb.feedback_id,
        context: fb.trigger_text,
        type: fb.signal_type,
        model: fb.related_model,
        lesson: '待分析提取'
      });
      try {
        insert.run(key, value);
        count++;
      } catch (e) {
        // 忽略重复
      }
    }
    return count;
  }

  async run(): Promise<void> {
    console.log('📝 开始写入记忆...');

    const lessons = this.writeToSemanticMemory();
    console.log(`✅ 写入 ${lessons} 条教训`);

    this.db.close();
  }
}

if (import.meta.main) {
  new FeedbackToMemory().run();
}
```

---

## 定时任务清单 (完整)

| 任务 | 脚本 | 间隔 | 依赖 |
|------|------|------|------|
| 轨迹提取 | trajectory-extractor.ts | 1h | - |
| 数据关联 | data-linker.ts | 1h | 轨迹+SROE |
| 反馈挖掘 | feedback-miner.ts | 2h | 轨迹 |
| Q值计算 | q-score-updater.ts | 4h | 反馈+关联 |
| 路由评分同步 | routing-score-updater.ts | 4h | Q值 |
| 反馈写记忆 | feedback-to-memory.ts | 6h | 反馈 |

---

## 验证方案

### 1. Trace 模型归因率验证
```bash
sqlite3 ~/.solar/solar.db "
SELECT
  COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) as linked,
  COUNT(*) as total,
  ROUND(COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as rate
FROM evo_traces;
"
# 目标: rate > 80%
```

### 2. Q-scores 影响路由验证
```bash
# 检查路由表是否有 effective_score
sqlite3 ~/.solar/solar.db "
SELECT 'model' as type, COUNT(*) as cnt, AVG(effective_score) as avg_score
FROM sys_routing_model WHERE effective_score IS NOT NULL
UNION ALL
SELECT 'agent', COUNT(*), AVG(effective_score)
FROM sys_routing_agent WHERE effective_score IS NOT NULL
UNION ALL
SELECT 'tool', COUNT(*), AVG(effective_score)
FROM sys_routing_tool WHERE effective_score IS NOT NULL;
"
```

### 3. 闭环验证 (故意测试)
```bash
# 1. 查看当前 Q-scores
sqlite3 ~/.solar/solar.db "
SELECT entity_id, satisfaction, completion_rate
FROM sys_quality_scores
WHERE entity_type = 'model'
ORDER BY satisfaction DESC;
"

# 2. 等待数据采集 → 反馈挖掘 → Q-score 更新 → 路由评分同步
# 3. 观察 Brain Router 是否优先选择高 Q-score 的模型
```

### 4. 记忆增长验证
```bash
sqlite3 ~/.solar/solar.db "
SELECT namespace, COUNT(*) as cnt
FROM evo_memory_semantic
GROUP BY namespace;
"
# lessons namespace 应该随时间增长
```

### 5. 端到端闭环测试
```bash
# 运行所有脚本
bun ~/.claude/core/cortex/trajectory-extractor.ts
bun ~/.claude/core/cortex/data-linker.ts
bun ~/.claude/core/cortex/feedback-miner.ts
bun ~/.claude/core/cortex/q-score-updater.ts
bun ~/.claude/core/cortex/routing-score-updater.ts
bun ~/.claude/core/cortex/feedback-to-memory.ts

# 检查数据流是否正常
sqlite3 ~/.solar/solar.db "SELECT * FROM v_routing_model_qscore LIMIT 5;"
```

---

## 实施顺序

1. **Phase 1**: data-linker.ts (解决断点 #1)
2. **Phase 2**: 数据库扩展 + routing-score-updater.ts (解决断点 #2, #6)
3. **Phase 3**: Brain Router 集成 (让 Q-scores 生效)
4. **Phase 4**: feedback-to-memory.ts (解决断点 #3)
5. **Phase 5**: 意图分类 (解决断点 #4)

**预计工作量**: 3-4 个小时
