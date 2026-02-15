# Persona Bank 集成方案 - 固化到 /Insight Skill

> **核心原则**: 不靠 Claude 主脑临时起意，固定 DAG 自动执行

## 一、架构修正

### ❌ 错误理解

```
Claude 主脑 → PersonaBankEngine.runArenaFlow() → 返回结果
              ↑
          临时起意，主脑控制
```

### ✅ 正确架构

```
用户请求
    ↓
Claude 主脑: /insight "主题" (仅发起，不管内部)
    ↓
insight-agent-v2.ts 内部固定 DAG:
    ├─ collect: 自动从 Persona Bank 选 3-4 个人格
    ├─ fill_gaps: 自动选最合适人格补缺口
    ├─ peer_review: 自动选 2-4 个互评，更新 ELO
    └─ compose: 自动选最佳人格合成
    ↓
返回最终报告
    ↓
Claude 主脑: 展示给用户 (不参与决策)
```

## 二、阶段映射

### 当前七阶段 → 四步 DAG 映射

```
当前七阶段                        固定四步 DAG
───────────────────────────────────────────────────────
PLANNING (1)           ─┐
OUTLINE (2)            ─┼→  1. collect (收集证据)
SCHEDULING (3)         ─┘       - 多模型并行收集 SOURCES + NOTES
                                - 包含反例和多元视角

                        →  2. fill_gaps (补全缺口)
                                - 分析 OUTLINE 与 SOURCES 的 gap
                                - 补充缺失证据
                                - 补充反方观点

WRITING (4)            ─┐
REVIEW (5)             ─┼→  3. peer_review (交叉互评)
                        ─┘       - A评B、B评A 生成 EVAL 矩阵
                                - 记录对局，更新 ELO
                                - 选出最佳草稿

SYNTHESIS (6)           →  4. compose (合成最终稿)
CLOSING (7)                     - 基于最佳草稿 + 评审意见
                                - 生成最终报告
```

### 保持兼容性

为了不破坏现有逻辑，采用**渐进式重构**：

```typescript
class InsightAgentV2 {
  private usePersonaBank: boolean;  // 特性开关

  constructor(usePersonaBank = true) {
    this.usePersonaBank = usePersonaBank;
  }

  async execute() {
    if (this.usePersonaBank) {
      // 新流程: 固定 DAG
      return this.executeFixedDAG();
    } else {
      // 旧流程: 七阶段
      return this.executeSevenPhases();
    }
  }
}
```

## 三、具体集成点

### 文件结构

```
/Users/sihaoli/.claude/core/solar-farm/
├── insight-agent-v2.ts           # 主入口 (需修改)
├── persona-bank-schema.sql       # 数据库结构 (已完成)
├── persona-bank-selector.ts      # Persona 选择器 (新建)
├── persona-bank-recorder.ts      # 得分记录器 (新建)
└── persona-bank-elo.ts            # ELO 计算器 (新建)
```

### 1. Persona 选择器 (persona-bank-selector.ts)

```typescript
export class PersonaSelector {
  private db: Database;

  /**
   * 为指定阶段选择最优人格
   * @param phase - collect | fill_gaps | peer_review | compose
   * @param count - 需要的人格数量
   * @returns 选中的人格配置列表
   */
  async selectForPhase(
    phase: 'collect' | 'fill_gaps' | 'peer_review' | 'compose',
    count: number
  ): Promise<PersonaConfig[]> {
    // 1. 确定该阶段需要的主导特质
    const traitMapping = {
      'collect': 'O',        // 开放性 - 广泛收集
      'fill_gaps': 'C',      // 尽责性 - 补全细节
      'peer_review': 'A',    // 宜人性 - 客观评价
      'compose': 'E'         // 外向性 - 表达能力
    };

    const requiredTrait = traitMapping[phase];

    // 2. 从数据库选择候选人格 (ELO 高 + 特质匹配)
    const candidates = await this.db.query(`
      SELECT
        c.*,
        e.elo_rating,
        e.win_rate,
        e.total_matches,
        json_extract(c.big_five_json, '$.${requiredTrait}') as trait_score
      FROM sys_persona_configs c
      JOIN sys_persona_elo e ON c.persona_id = e.persona_id
      WHERE c.status = 'active'
        AND json_extract(c.big_five_json, '$.${requiredTrait}') > 0.6
      ORDER BY
        e.elo_rating DESC,
        e.win_rate DESC,
        trait_score DESC
      LIMIT ?
    `).all(count * 2) as PersonaConfig[];

    // 3. 多样性过滤 (避免全选同一模型)
    const selected = this.diversityFilter(candidates, count);

    // 4. 新手保护 (10% 概率给新人格机会)
    if (Math.random() < 0.1 && selected.length > 0) {
      const newbie = await this.selectNewbie();
      if (newbie) {
        selected[selected.length - 1] = newbie;
      }
    }

    return selected;
  }

  private diversityFilter(candidates: PersonaConfig[], count: number): PersonaConfig[] {
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

    return selected;
  }

  private async selectNewbie(): Promise<PersonaConfig | null> {
    const newbies = await this.db.query(`
      SELECT c.*
      FROM sys_persona_configs c
      JOIN sys_persona_elo e ON c.persona_id = e.persona_id
      WHERE c.status = 'active'
        AND e.total_matches < 5
      ORDER BY RANDOM()
      LIMIT 1
    `).all() as PersonaConfig[];

    return newbies.length > 0 ? newbies[0] : null;
  }
}
```

### 2. 得分记录器 (persona-bank-recorder.ts)

```typescript
export class PersonaRecorder {
  private db: Database;

  /**
   * 记录人格在某阶段的表现
   */
  async recordScore(
    personaId: string,
    taskId: string,
    phase: string,
    rubric: RubricScores,
    evaluatedBy: 'self' | 'peer' | 'user',
    evaluatorPersonaId?: string
  ): Promise<void> {
    const overallScore = this.calculateOverallScore(rubric);

    await this.db.run(`
      INSERT INTO sys_persona_scores
      (persona_id, task_id, phase, rubric_json, overall_score, evaluated_by, evaluator_persona_id)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `, [
      personaId,
      taskId,
      phase,
      JSON.stringify(rubric),
      overallScore,
      evaluatedBy,
      evaluatorPersonaId
    ]);
  }

  /**
   * 记录对局 (A评B、B评A)
   */
  async recordMatch(
    taskId: string,
    personaA: string,
    personaB: string,
    scoreA: number,  // B给A的分数
    scoreB: number,  // A给B的分数
    eloRatingA: number,
    eloRatingB: number
  ): Promise<void> {
    // 1. 判断胜负
    const winner = scoreA > scoreB ? personaA : (scoreB > scoreA ? personaB : 'draw');

    // 2. 计算 ELO 变化
    const { deltaA, deltaB } = this.calculateEloChange(
      eloRatingA,
      eloRatingB,
      scoreA,
      scoreB
    );

    // 3. 记录对局
    await this.db.run(`
      INSERT INTO sys_persona_matches
      (task_id, persona_a, persona_b, score_a, score_b, winner, elo_change_a, elo_change_b)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `, [taskId, personaA, personaB, scoreA, scoreB, winner, deltaA, deltaB]);

    // 触发器会自动更新 sys_persona_elo 表
  }

  private calculateEloChange(
    ratingA: number,
    ratingB: number,
    scoreA: number,
    scoreB: number
  ): { deltaA: number, deltaB: number } {
    const K = 32;  // ELO K-factor
    const expectedA = 1 / (1 + Math.pow(10, (ratingB - ratingA) / 400));
    const actualA = scoreA > scoreB ? 1 : (scoreA === scoreB ? 0.5 : 0);
    const deltaA = K * (actualA - expectedA);

    return { deltaA, deltaB: -deltaA };
  }

  private calculateOverallScore(rubric: RubricScores): number {
    const { clarity, evidence, logic, accuracy, language } = rubric;
    return (clarity + evidence + logic + accuracy + language) / 5;
  }
}
```

### 3. 修改 insight-agent-v2.ts

在 `InsightAgentV2` 类中添加：

```typescript
import { PersonaSelector } from './persona-bank-selector';
import { PersonaRecorder } from './persona-bank-recorder';

class InsightAgentV2 {
  private personaSelector: PersonaSelector;
  private personaRecorder: PersonaRecorder;

  constructor() {
    // ... 现有初始化 ...
    this.personaSelector = new PersonaSelector();
    this.personaRecorder = new PersonaRecorder();
  }

  // ========== 固定 DAG 执行 ==========

  async executeFixedDAG(): Promise<string> {
    console.log('🎯 执行固定 DAG: collect → fill_gaps → peer_review → compose');

    // Phase 1: Collect
    const collectResult = await this.phaseCollect();

    // Phase 2: Fill Gaps
    const filledResult = await this.phaseFillGaps(collectResult);

    // Phase 3: Peer Review
    const reviewResult = await this.phasePeerReview(filledResult);

    // Phase 4: Compose
    const finalDraft = await this.phaseCompose(reviewResult);

    return finalDraft;
  }

  // ========== Phase 1: Collect ==========

  async phaseCollect(): Promise<CollectResult> {
    console.log('📥 Phase 1: Collect - 多模型并行收集证据');

    // 1. 从 Persona Bank 自动选择 3-4 个人格
    const personas = await this.personaSelector.selectForPhase('collect', 4);

    console.log(`  选中人格: ${personas.map(p => p.model).join(', ')}`);

    // 2. 并行调用收集
    const results = await Promise.all(
      personas.map(async (persona, idx) => {
        const focus = ['evidence', 'counter_examples', 'cross_domain', 'edge_cases'][idx];
        const prompt = this.buildCollectPrompt(this.topic, focus);

        // 调用 brain-router
        const response = await this.callBrainRouter({
          model: persona.model,
          system: this.buildPersonaSystemPrompt(persona),
          prompt
        });

        const parsed = this.parseCollectResponse(response);

        // 记录得分 (自评)
        await this.personaRecorder.recordScore(
          persona.persona_id,
          this.taskId,
          'collect',
          { clarity: 8, evidence: 8, logic: 8, accuracy: 8, language: 8 },  // 临时自评
          'self'
        );

        return parsed;
      })
    );

    // 3. 合并结果
    return {
      sources: this.deduplicateSources(results.flatMap(r => r.sources)),
      notes: results.flatMap(r => r.notes),
      counter_examples: results.flatMap(r => r.counter_examples),
      coverage_gaps: this.identifyGaps(results)
    };
  }

  // ========== Phase 2: Fill Gaps ==========

  async phaseFillGaps(collected: CollectResult): Promise<FilledResult> {
    console.log('🔧 Phase 2: Fill Gaps - 补全缺口');

    // 1. 生成大纲
    const outline = await this.generateOutline(this.topic, 5);

    // 2. 分析缺口
    const gaps = this.analyzeGaps(collected, outline);

    if (gaps.length === 0) {
      console.log('  ✓ 无缺口，跳过');
      return { additional_sources: [], counter_arguments: [], strengthened_claims: [] };
    }

    console.log(`  发现 ${gaps.length} 个缺口`);

    // 3. 为每个缺口选择人格
    const tasks = gaps.map(gap => ({
      gap,
      persona: this.selectPersonaForGap(gap)  // 基于 gap 类型匹配
    }));

    // 4. 并行补全
    const filled = await Promise.all(
      tasks.map(async ({ gap, persona }) => {
        const prompt = this.buildFillGapPrompt(gap, collected);

        const response = await this.callBrainRouter({
          model: persona.model,
          system: this.buildPersonaSystemPrompt(persona),
          prompt
        });

        const parsed = this.parseFillGapResponse(response);

        // 记录得分
        await this.personaRecorder.recordScore(
          persona.persona_id,
          this.taskId,
          'fill_gaps',
          { clarity: 8, evidence: 9, logic: 8, accuracy: 9, language: 7 },
          'self'
        );

        return parsed;
      })
    );

    return {
      additional_sources: filled.flatMap(f => f.sources),
      counter_arguments: filled.flatMap(f => f.counter_args),
      strengthened_claims: filled.flatMap(f => f.claims)
    };
  }

  // ========== Phase 3: Peer Review ==========

  async phasePeerReview(filled: FilledResult): Promise<ReviewResult> {
    console.log('🔍 Phase 3: Peer Review - 交叉互评');

    // 1. 选择 2-4 个互评专家
    const reviewers = await this.personaSelector.selectForPhase('peer_review', 3);

    console.log(`  互评专家: ${reviewers.map(p => p.model).join(', ')}`);

    // 2. 每个专家生成初稿
    const drafts = await Promise.all(
      reviewers.map(async (persona) => {
        const prompt = this.buildDraftPrompt(filled, persona);

        const response = await this.callBrainRouter({
          model: persona.model,
          system: this.buildPersonaSystemPrompt(persona),
          prompt
        });

        return { persona, draft: response };
      })
    );

    // 3. 交叉评估: A评B、B评A
    const evalMatrix: EvalEntry[][] = [];

    for (let i = 0; i < reviewers.length; i++) {
      const row: EvalEntry[] = [];

      for (let j = 0; j < drafts.length; j++) {
        if (i === j) {
          row.push(null);  // 不自评
          continue;
        }

        const reviewer = reviewers[i];
        const target = drafts[j];

        // 让 reviewer 评价 target 的草稿
        const rubric = await this.evaluateDraft(reviewer, target.draft);
        const score = this.calculateOverallScore(rubric);

        row.push({
          reviewer_id: reviewer.persona_id,
          target_id: target.persona.persona_id,
          rubric,
          score
        });

        // 记录评分
        await this.personaRecorder.recordScore(
          target.persona.persona_id,
          this.taskId,
          'peer_review',
          rubric,
          'peer',
          reviewer.persona_id
        );
      }

      evalMatrix.push(row);
    }

    // 4. 记录对局并更新 ELO
    for (let i = 0; i < reviewers.length; i++) {
      for (let j = i + 1; j < reviewers.length; j++) {
        const scoreA = evalMatrix[j][i]?.score || 0;  // j评i
        const scoreB = evalMatrix[i][j]?.score || 0;  // i评j

        await this.personaRecorder.recordMatch(
          this.taskId,
          reviewers[i].persona_id,
          reviewers[j].persona_id,
          scoreA,
          scoreB,
          reviewers[i].elo_rating,
          reviewers[j].elo_rating
        );
      }
    }

    // 5. 选出最佳草稿
    const bestDraft = this.selectBestDraft(drafts, evalMatrix);

    return {
      eval_matrix: evalMatrix,
      best_draft: bestDraft,
      all_drafts: drafts
    };
  }

  // ========== Phase 4: Compose ==========

  async phaseCompose(review: ReviewResult): Promise<string> {
    console.log('✍️  Phase 4: Compose - 合成最终稿');

    // 1. 选择最擅长合成的人格
    const composers = await this.personaSelector.selectForPhase('compose', 1);
    const composer = composers[0];

    console.log(`  合成专家: ${composer.model}`);

    // 2. 构建合成提示
    const prompt = this.buildComposePrompt(review);

    // 3. 生成最终草稿
    const final = await this.callBrainRouter({
      model: composer.model,
      system: this.buildPersonaSystemPrompt(composer),
      prompt
    });

    // 4. 记录得分
    await this.personaRecorder.recordScore(
      composer.persona_id,
      this.taskId,
      'compose',
      { clarity: 9, evidence: 9, logic: 9, accuracy: 9, language: 9 },
      'self'
    );

    return final;
  }

  // ========== 辅助方法 ==========

  private buildPersonaSystemPrompt(persona: PersonaConfig): string {
    return `你是 ${persona.role}。

Big Five 性格参数:
${JSON.stringify(persona.big_five_json, null, 2)}

行为准则:
${persona.behavioral_guidelines}

语言风格:
${persona.language_style}

${persona.forbidden_patterns ? `禁止: ${persona.forbidden_patterns}` : ''}
${persona.required_patterns ? `必须: ${persona.required_patterns}` : ''}
`;
  }
}
```

## 四、数据库初始化

在 /Insight skill 启动时自动执行：

```typescript
async initPersonaBank() {
  const schemaPath = join(__dirname, 'persona-bank-schema.sql');
  if (existsSync(schemaPath)) {
    const schema = readFileSync(schemaPath, 'utf-8');
    this.db.exec(schema);
    console.log('✅ Persona Bank 初始化完成');
  }
}
```

## 五、CLI 接口保持不变

```bash
# 用户调用方式完全不变
bun insight-agent-v2.ts "AI Agent的记忆机制" 3

# 内部自动执行固定 DAG
# Claude 主脑不参与决策
```

## 六、验证方式

```bash
# 1. 执行一次洞察分析
bun insight-agent-v2.ts "测试主题" 3

# 2. 查看 Persona Bank 排行榜
sqlite3 ~/.solar/solar.db "SELECT * FROM v_persona_leaderboard"

# 3. 查看对局历史
sqlite3 ~/.solar/solar.db "SELECT * FROM v_recent_matches LIMIT 10"

# 4. 查看 ELO 更新
sqlite3 ~/.solar/solar.db "
SELECT
  persona_id,
  elo_rating,
  win_rate,
  total_matches
FROM sys_persona_elo
ORDER BY elo_rating DESC
"
```

## 七、核心优势

✅ **固化到 /Insight 内部** - 不依赖 Claude 主脑临时起意
✅ **固定 DAG 拓扑** - collect→fill_gaps→peer_review→compose
✅ **自动选择最优人格** - 基于 ELO 排名 + 专长匹配
✅ **自动记录得分** - 每次执行后更新 sys_persona_scores
✅ **自动更新 ELO** - peer_review 阶段触发对局
✅ **真正的 AI 管 AI** - 人格配置→rubric得分→ELO排名→自动演化

---

*Persona Bank Integration Plan v2.0*
*修正于: 2026-02-14*
*核心: 固化到 /Insight skill，不靠主脑临时起意*
