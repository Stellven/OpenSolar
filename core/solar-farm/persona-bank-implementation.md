# Persona Bank 竞技场机制 - 实现方案

> **目标**: 实现"AI管AI"的核心机制 - 基于 ELO/胜率自动选择最优人格配置

## 一、架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│              Persona Bank Arena (竞技场)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   固定 DAG 拓扑: 四步流水线                                     │
│                                                                 │
│   collect (收集证据)                                            │
│      │                                                          │
│      ▼                                                          │
│   fill_gaps (补全缺口)                                          │
│      │                                                          │
│      ▼                                                          │
│   peer_review (A评B、B评A)                                     │
│      │                                                          │
│      ▼                                                          │
│   compose (合成草稿)                                            │
│                                                                 │
│   每一步都记录: persona_id → rubric_score → ELO更新            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 二、四步 DAG 详细设计

### Step 1: collect (收集证据)

**目标**: 多模型并行收集 SOURCES + NOTES + 反例

**流程**:
```typescript
async collectPhase(topic: string): Promise<CollectResult> {
  // 1. 自动选择 3-4 个最优人格 (基于 ELO 排名)
  const personas = await this.selectTopPersonas('collect', 4);

  // 2. 并行调用，每个收集不同角度的证据
  const results = await Promise.all(
    personas.map(async (persona) => {
      const prompt = this.buildCollectPrompt(topic, persona.focus);
      const response = await this.callWithPersona(persona, prompt);
      return this.parseCollectResponse(response);
    })
  );

  // 3. 合并结果
  const collected = {
    sources: results.flatMap(r => r.sources),      // 去重
    notes: results.flatMap(r => r.notes),
    counter_examples: results.flatMap(r => r.counter_examples),
    coverage_gaps: this.identifyGaps(results)      // 识别缺口
  };

  // 4. 记录每个 persona 的表现
  await this.recordCollectPerformance(personas, results);

  return collected;
}
```

**输出结构**:
```typescript
interface CollectResult {
  sources: Source[];              // 引用来源
  notes: Note[];                  // 分析笔记
  counter_examples: string[];     // 反例
  coverage_gaps: {                // 发现的缺口
    missing_topics: string[];
    weak_evidence: string[];
    counter_arguments_needed: string[];
  };
}
```

### Step 2: fill_gaps (补全缺口)

**目标**: 根据 OUTLINE/CLAIMS 缺口，补充证据和反方观点

**流程**:
```typescript
async fillGapsPhase(
  collected: CollectResult,
  outline: Outline
): Promise<FillGapsResult> {
  // 1. 分析缺口
  const gaps = this.analyzeGaps(collected, outline);

  // 2. 为每个缺口选择最合适的人格
  const tasks = gaps.map(gap => ({
    gap,
    persona: this.selectPersonaForGap(gap)  // 基于 gap 类型和 persona 专长
  }));

  // 3. 并行补全
  const filled = await Promise.all(
    tasks.map(async ({ gap, persona }) => {
      const prompt = this.buildFillGapPrompt(gap, collected);
      const response = await this.callWithPersona(persona, prompt);
      return this.parseFillGapResponse(response, gap);
    })
  );

  // 4. 记录表现
  await this.recordFillGapsPerformance(tasks, filled);

  return {
    additional_sources: filled.flatMap(f => f.sources),
    counter_arguments: filled.flatMap(f => f.counter_args),
    strengthened_claims: filled.flatMap(f => f.claims),
    remaining_gaps: this.identifyRemainingGaps(filled)
  };
}
```

**Gap 类型与 Persona 匹配**:
```typescript
const GAP_PERSONA_MAPPING = {
  'missing_evidence': 'gemini_pro_analyst_strict',     // 严谨找证据
  'weak_logic': 'deepseek_r1_reasoner_deep',           // 深度推理
  'counter_needed': 'deepseek_v3_writer_creative',     // 多元视角
  'innovative_angle': 'gemini_3_explorer_innovative'   // 创新探索
};
```

### Step 3: peer_review (A评B、B评A)

**目标**: 交叉评估，生成 EVAL 矩阵，触发 ELO 对局

**流程**:
```typescript
async peerReviewPhase(
  sources: Source[],
  claims: Claim[],
  outline: Outline
): Promise<PeerReviewResult> {
  // 1. 选择 2-4 个互评专家
  const reviewers = await this.selectTopPersonas('peer_review', 4);

  // 2. 每个专家生成初稿
  const drafts = await Promise.all(
    reviewers.map(async (persona) => {
      const prompt = this.buildDraftPrompt(sources, claims, outline, persona);
      const response = await this.callWithPersona(persona, prompt);
      return { persona, draft: response };
    })
  );

  // 3. 交叉评估: A评B、B评A (全连接图)
  const evalMatrix: EvalEntry[][] = [];
  for (const reviewer of reviewers) {
    const row: EvalEntry[] = [];
    for (const target of drafts) {
      if (reviewer.persona_id === target.persona.persona_id) {
        row.push(null);  // 不自评
        continue;
      }
      const rubric = await this.evaluateDraft(
        reviewer,
        target.draft,
        outline
      );
      row.push({
        reviewer_id: reviewer.persona_id,
        target_id: target.persona.persona_id,
        rubric,
        overall_score: this.calculateOverallScore(rubric)
      });
    }
    evalMatrix.push(row);
  }

  // 4. 记录对局并更新 ELO
  await this.recordMatches(evalMatrix);

  // 5. 选出最佳草稿
  const bestDraft = this.selectBestDraft(drafts, evalMatrix);

  return {
    eval_matrix: evalMatrix,
    best_draft: bestDraft,
    all_drafts: drafts,
    elo_updates: this.getEloUpdates()
  };
}
```

**EvalEntry 结构**:
```typescript
interface EvalEntry {
  reviewer_id: string;
  target_id: string;
  rubric: {
    clarity: number;      // 1-10
    evidence: number;     // 1-10
    logic: number;        // 1-10
    accuracy: number;     // 1-10
    language: number;     // 1-10
  };
  overall_score: number;  // 平均分
  problems: string[];
  suggestions: string[];
}
```

**ELO 计算**:
```typescript
calculateEloChange(scoreA: number, scoreB: number): { deltaA: number, deltaB: number } {
  const K = 32;  // ELO K-factor
  const expectedA = 1 / (1 + Math.pow(10, (scoreB - scoreA) / 400));
  const actualA = scoreA > scoreB ? 1 : (scoreA === scoreB ? 0.5 : 0);
  const deltaA = K * (actualA - expectedA);
  return {
    deltaA,
    deltaB: -deltaA
  };
}
```

### Step 4: compose (合成草稿)

**目标**: 基于最佳草稿 + EVAL 反馈，生成最终报告

**流程**:
```typescript
async composePhase(
  peerReview: PeerReviewResult,
  outline: Outline
): Promise<string> {
  // 1. 选择最擅长合成的人格
  const composer = await this.selectTopPersonas('compose', 1)[0];

  // 2. 构建合成提示（包含所有草稿 + 评审意见）
  const prompt = this.buildComposePrompt(
    peerReview.all_drafts,
    peerReview.eval_matrix,
    outline
  );

  // 3. 生成最终草稿
  const final = await this.callWithPersona(composer, prompt);

  // 4. 记录表现
  await this.recordComposePerformance(composer, final);

  return final;
}
```

## 三、Persona Bank 自动选择逻辑

### 选择算法

```typescript
async selectTopPersonas(
  phase: 'collect' | 'fill_gaps' | 'peer_review' | 'compose',
  count: number
): Promise<PersonaConfig[]> {
  // 1. 从排行榜中选择 (优先 ELO 高 + 专长匹配)
  const candidates = await this.db.query(`
    SELECT
      c.*,
      e.elo_rating,
      e.win_rate,
      e.avg_score,
      e.total_matches
    FROM sys_persona_configs c
    JOIN sys_persona_elo e ON c.persona_id = e.persona_id
    WHERE c.status = 'active'
      AND json_extract(c.big_five_json, '$.${PHASE_TRAIT_MAPPING[phase]}') > 0.7
    ORDER BY
      e.elo_rating DESC,
      e.win_rate DESC
    LIMIT ?
  `, [count * 2]);  // 选两倍候选

  // 2. 多样性过滤 (避免全选同一模型)
  const selected = this.diversityFilter(candidates, count);

  // 3. 新手保护 (给新人格机会)
  if (Math.random() < 0.1) {  // 10% 概率
    selected[selected.length - 1] = this.selectNewbie();
  }

  return selected;
}
```

**Phase 与 Big Five 映射**:
```typescript
const PHASE_TRAIT_MAPPING = {
  'collect': 'O',       // 开放性 - 广泛收集
  'fill_gaps': 'C',     // 尽责性 - 补全细节
  'peer_review': 'A',   // 宜人性 - 客观评价
  'compose': 'E'        // 外向性 - 表达能力
};
```

### 多样性过滤

```typescript
diversityFilter(candidates: PersonaConfig[], count: number): PersonaConfig[] {
  const selected: PersonaConfig[] = [];
  const usedModels = new Set<string>();

  for (const candidate of candidates) {
    if (selected.length >= count) break;

    // 优先选不同模型
    if (!usedModels.has(candidate.model)) {
      selected.push(candidate);
      usedModels.add(candidate.model);
    } else if (selected.length < count - 1) {
      // 如果还有空位，可以重复模型
      selected.push(candidate);
    }
  }

  // 如果不够，从候选中补
  while (selected.length < count && candidates.length > selected.length) {
    selected.push(candidates[selected.length]);
  }

  return selected;
}
```

## 四、API 接口设计

### PersonaBankEngine 类

```typescript
export class PersonaBankEngine {
  private db: Database;
  private cortex: Cortex;

  constructor(dbPath?: string) {
    this.db = new Database(dbPath || `${homedir()}/.solar/solar.db`);
    this.cortex = new Cortex();
  }

  // ========== 核心流程 ==========

  /**
   * 执行完整的竞技场流程
   */
  async runArenaFlow(topic: string, chapterCount: number = 5): Promise<ArenaResult> {
    const taskId = this.cortex.createTask('arena', topic, 'persona-bank');

    // Step 1: Collect
    this.cortex.updateTaskPhase(taskId, 1, 'in_progress');
    const collected = await this.collectPhase(topic);
    this.cortex.saveArtifact(taskId, 1, 'collect_result', collected);

    // Step 2: Fill Gaps
    this.cortex.updateTaskPhase(taskId, 2, 'in_progress');
    const outline = await this.generateOutline(topic, chapterCount);
    const filled = await this.fillGapsPhase(collected, outline);
    this.cortex.saveArtifact(taskId, 2, 'fill_gaps_result', filled);

    // Step 3: Peer Review
    this.cortex.updateTaskPhase(taskId, 3, 'in_progress');
    const allSources = [...collected.sources, ...filled.additional_sources];
    const peerReview = await this.peerReviewPhase(allSources, [], outline);
    this.cortex.saveArtifact(taskId, 3, 'peer_review_result', peerReview);

    // Step 4: Compose
    this.cortex.updateTaskPhase(taskId, 4, 'in_progress');
    const finalDraft = await this.composePhase(peerReview, outline);
    this.cortex.saveArtifact(taskId, 4, 'final_draft', { content: finalDraft });

    this.cortex.completeTask(taskId);

    return {
      taskId,
      topic,
      finalDraft,
      evalMatrix: peerReview.eval_matrix,
      eloUpdates: peerReview.elo_updates,
      performance: await this.getPerformanceSummary(taskId)
    };
  }

  // ========== Persona 管理 ==========

  /**
   * 注册新的人格配置
   */
  async registerPersona(config: PersonaConfigInput): Promise<string> {
    const personaId = `${config.model.replace(/[^a-z0-9]/g, '_')}_${config.role.toLowerCase()}_${Date.now()}`;

    this.db.run(`
      INSERT INTO sys_persona_configs
      (persona_id, model, role, big_five_json, behavioral_guidelines, language_style, status)
      VALUES (?, ?, ?, ?, ?, ?, 'active')
    `, [
      personaId,
      config.model,
      config.role,
      JSON.stringify(config.bigFive),
      config.behavioralGuidelines,
      config.languageStyle
    ]);

    // 初始化 ELO
    this.db.run(`
      INSERT INTO sys_persona_elo (persona_id, elo_rating)
      VALUES (?, 1500.0)
    `, [personaId]);

    return personaId;
  }

  /**
   * 查看排行榜
   */
  async getLeaderboard(limit: number = 20): Promise<PersonaRanking[]> {
    return this.db.query(`
      SELECT * FROM v_persona_leaderboard
      LIMIT ?
    `).all(limit) as PersonaRanking[];
  }

  /**
   * 查看对局历史
   */
  async getMatchHistory(personaId?: string, limit: number = 50): Promise<Match[]> {
    let sql = 'SELECT * FROM v_recent_matches';
    const params: any[] = [];

    if (personaId) {
      sql += ` WHERE persona_a_name LIKE ? OR persona_b_name LIKE ?`;
      params.push(`%${personaId}%`, `%${personaId}%`);
    }

    sql += ` LIMIT ?`;
    params.push(limit);

    return this.db.query(sql).all(...params) as Match[];
  }

  // ========== 内部方法 (上面已定义) ==========
  // private async collectPhase(...)
  // private async fillGapsPhase(...)
  // private async peerReviewPhase(...)
  // private async composePhase(...)
  // private async selectTopPersonas(...)
  // ...
}
```

### CLI 接口

```bash
# 执行竞技场流程
bun persona-bank.ts run "AI Agent的记忆机制" --chapters 5

# 查看排行榜
bun persona-bank.ts leaderboard --limit 20

# 查看对局历史
bun persona-bank.ts matches --persona gemini_pro_analyst_strict

# 注册新人格
bun persona-bank.ts register \
  --model "deepseek-v3" \
  --role "批判性思考者" \
  --big-five '{"O":0.9,"C":0.7,"E":0.5,"A":0.3,"N":0.6}' \
  --guidelines "必须：质疑假设、寻找反例。禁止：盲目接受、确认偏见。"

# 查看人格详细统计
bun persona-bank.ts stats gemini_pro_analyst_strict
```

## 五、与现有系统集成

### 1. 替换 insight-agent-v2.ts 的专家选择

**修改位置**: `insight-agent-v2.ts` 第 2924-2929 行

```typescript
// 旧代码 (硬编码)
const reviewExperts = [
  { model: 'gemini-2.5-pro', role: '一致性审核' },
  { model: 'deepseek-r1', role: '深度审核' }
];

// 新代码 (Persona Bank 自动选择)
import { PersonaBankEngine } from './persona-bank-engine';
const personaBank = new PersonaBankEngine();
const reviewExperts = await personaBank.selectTopPersonas('peer_review', 2);
```

### 2. 记录互评结果到 Persona Bank

**修改位置**: `insight-agent-v2.ts` 交叉评估逻辑

```typescript
// 在 crossEvaluateDispatch 函数中添加
async crossEvaluateDispatch(...) {
  // ... 现有逻辑 ...

  // 新增: 记录到 Persona Bank
  await personaBank.recordPeerReview(
    reviewerPersonaId,
    targetPersonaId,
    rubric,
    overallScore,
    this.taskId
  );
}
```

### 3. Cortex 集成

Persona Bank 的所有数据自动同步到 Cortex:
- `sys_persona_scores` → Cortex 评分记录
- `sys_persona_matches` → Cortex 对局历史
- `sys_persona_elo` → Cortex 排名追踪

## 六、验证与测试

### 测试用例

```typescript
// 测试 1: 注册新人格
test('register new persona', async () => {
  const engine = new PersonaBankEngine();
  const personaId = await engine.registerPersona({
    model: 'gemini-3-pro-preview',
    role: '创新探索者',
    bigFive: { O: 0.9, C: 0.7, E: 0.9, A: 0.7, N: 0.3 },
    behavioralGuidelines: '必须：大胆假设、跨领域联想。禁止：保守、墨守成规。',
    languageStyle: '热情、创新、前瞻'
  });
  expect(personaId).toContain('gemini_3');
});

// 测试 2: 自动选择
test('select top personas by ELO', async () => {
  const engine = new PersonaBankEngine();
  const personas = await engine.selectTopPersonas('peer_review', 3);
  expect(personas.length).toBe(3);
  expect(personas[0].elo_rating).toBeGreaterThanOrEqual(personas[1].elo_rating);
});

// 测试 3: 完整流程
test('run full arena flow', async () => {
  const engine = new PersonaBankEngine();
  const result = await engine.runArenaFlow('AI Agent的记忆机制', 3);
  expect(result.finalDraft).toBeTruthy();
  expect(result.evalMatrix.length).toBeGreaterThan(0);
  expect(result.eloUpdates.length).toBeGreaterThan(0);
});
```

## 七、性能指标

### 追踪指标

```sql
-- 人格平均质量
SELECT
  persona_id,
  AVG(overall_score) as avg_quality,
  COUNT(*) as task_count
FROM sys_persona_scores
GROUP BY persona_id
ORDER BY avg_quality DESC;

-- ELO 变化趋势
SELECT
  persona_id,
  elo_rating,
  win_rate,
  total_matches
FROM sys_persona_elo
ORDER BY elo_rating DESC;

-- 阶段表现对比
SELECT
  phase,
  AVG(overall_score) as avg_score,
  COUNT(DISTINCT persona_id) as unique_personas
FROM sys_persona_scores
GROUP BY phase;
```

## 八、下一步工作

1. **实现 PersonaBankEngine 类** (persona-bank-engine.ts)
2. **创建 CLI 工具** (persona-bank.ts)
3. **集成到 insight-agent-v2.ts**
4. **编写测试用例**
5. **执行初始化 SQL**:
   ```bash
   sqlite3 ~/.solar/solar.db < persona-bank-schema.sql
   ```
6. **运行首次测试**:
   ```bash
   bun persona-bank.ts run "测试主题" --chapters 3
   ```
7. **验证 ELO 更新**:
   ```bash
   bun persona-bank.ts leaderboard
   ```

---

*Persona Bank Arena Implementation Plan v1.0*
*设计完成: 2026-02-14*
*核心机制: collect→fill_gaps→peer_review→compose*
*真正实现: AI 管理 AI*
