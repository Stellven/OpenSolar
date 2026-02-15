# Solar 人格工程化指南

> **来源**: 用户洞察 + 学术研究
> **核心**: 人格不是玄学，是策略先验
> **版本**: v3.0 - 两层人格模型

## 一、核心原理

```
┌─────────────────────────────────────────────────────────────────┐
│  人格 = 策略先验 (Policy Prior)                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  通过 system prompt 改变模型的:                                 │
│                                                                 │
│  • 注意力分配     - 关注什么，忽略什么                          │
│  • 推理深度       - 浅层回答 vs 深度分析                        │
│  • 风险偏好       - 激进探索 vs 保守求稳                        │
│  • 不确定性处理   - 明确标注 vs 含糊其辞                        │
│  • 自检行为       - 是否主动检查错误                            │
│  • 工具调用       - 是否倾向调用外部工具                        │
│  • 输出结构       - 格式化程度                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 二、两层人格模型

### A层：叙事层（人类心理学框架）

用于设计角色叙事，让 AI 更像"某类人"：

| 框架 | 维度 | 用途 |
|------|------|------|
| **Big Five / OCEAN** | O/C/E/A/N | 基础人格 |
| **HEXACO** | + 诚实-谦逊 | 抑制自嗨/忽悠/过度自信 |
| **Regulatory Focus** | 促进型 vs 预防型 | 追求收益 vs 避免损失 |
| **Construal Level** | 抽象 vs 具体 | 战略/架构 vs 实现/排错 |
| **Schwartz Values** | 安全/成就/自我超越 | 价值取向型任务 |

### B层：控制面（10个可度量旋钮）

**这是性能关键层！** 把人格规范成向量 (0-5分)：

| 旋钮 | 说明 | 高分行为 |
|------|------|----------|
| **rigor** | 证据洁癖 | 必须引用来源、列假设 |
| **skepticism** | 怀疑强度 | 主动找反例、挑漏洞 |
| **exploration** | 发散度 | 给多个备选方案 |
| **decisiveness** | 决断性 | 不完备信息下快速拍板 |
| **riskAversion** | 风险厌恶 | 极度保守、多加约束 |
| **toolFirst** | 工具倾向 | 主动上网/跑代码/写测试 |
| **compression** | 压缩率 | 极简表达 |
| **selfCritique** | 自检强度 | 必须自测、反思 |
| **socialEmpathy** | 人类体验 | 优先考虑用户感受 |
| **competitiveness** | 竞技性 | PK欲望，互评赛制用 |

## 三、研究发现 (陷阱与机会)

### ⚠️ 陷阱

| 现象 | 说明 | 对策 |
|------|------|------|
| **身份一致性推理** | 为了符合被赋予的身份而选择性推理 | 多专家会审，不单独采信 |
| **降低解释质量** | Persona 可能提升分类但降低解释 | 关键决策用 neutral 版复核 |
| **语气影响准确率** | "更不客气更准"的反直觉现象 | 高风险任务用严谨语气 |
| **人格漂移** | 上下文情境触发人格变化 | 长对话定期刷新人格 |
| **零样本变差** | 角色注入在某些任务上反而变差 | Neutral 对冲机制 |

### ✅ 机会

| 策略 | 说明 |
|------|------|
| **控制面 (Knobs)** | 用数值参数控制人格维度 |
| **任务路由 (Router)** | 不同任务用不同人格组合 |
| **互评赛制 (League)** | 多人格竞争，选最优 |
| **Neutral 对冲** | 人格版 + 中性版，选更稳的 |

## 四、Solar Farm 实现 v3.0

### 4.1 十旋钮向量

```typescript
interface ControlKnobs {
  rigor: number;             // 证据洁癖 (0-5)
  skepticism: number;        // 怀疑强度 (0-5)
  exploration: number;       // 发散度 (0-5)
  decisiveness: number;      // 决断性 (0-5)
  riskAversion: number;      // 风险厌恶 (0-5)
  toolFirst: number;         // 工具倾向 (0-5)
  compression: number;       // 压缩率 (0-5)
  selfCritique: number;      // 自检强度 (0-5)
  socialEmpathy: number;     // 人类体验 (0-5)
  competitiveness: number;   // 竞技性 (0-5)
}
```

### 4.2 十二角色 (带旋钮向量)

```
角色对比: critic vs builder

| 旋钮 | critic | builder | 差异 |
|------|--------|---------|------|
| rigor | 5 | 2 | +3 |
| skepticism | 5 | 1 | +4 |
| exploration | 1 | 2 | -1 |
| decisiveness | 2 | 4 | -2 |
| riskAversion | 4 | 1 | +3 |
| toolFirst | 2 | 5 | -3 |
```

### 3.2 十二角色

| 角色 | 用途 | 关键旋钮 |
|------|------|----------|
| scout | 快速探索 | divergent↑ speed↑ |
| extractor | 信息提取 | convergent↑ |
| critic | 批判审查 | skepticism↑ evidence↑ |
| synthesizer | 综合总结 | convergent↑ |
| explorer | 创新方案 | divergent↑ promotion↑ |
| architect | 架构设计 | convergent↑ evidence↑ |
| riskOfficer | 风险审计 | prevention↑ skepticism↑ |
| spec | 规格定义 | convergent↑ prevention↑ |
| builder | 快速实现 | speed↑ promotion↑ |
| verifier | 验证测试 | skepticism↑ evidence↑ |
| concierge | 日常服务 | speed↑ |
| governor | 最终决策 | prevention↑ skepticism↑ evidence↑ |

### 3.3 五编队

| 编队 | 角色 | 适用场景 |
|------|------|----------|
| research | scout→extractor→critic→synthesizer→governor | 技术调研 |
| design | explorer→architect→riskOfficer→synthesizer→governor | 方案设计 |
| coding | spec→builder→verifier | 代码开发 |
| life_low | concierge | 日常小事 |
| life_high | critic→governor | 重要决策 |

### 3.4 Neutral 对冲

```
高风险任务
    │
    ├── 并行执行 ─────────────────────────────┐
    │                                         │
    │   人格版 (带角色设定)                   │   中性版 (客观分析)
    │   可能被"身份一致性推理"带偏            │   无角色偏见
    │                                         │
    └─────────────────────────────────────────┘
                      │
                      ▼
              稳定性评分 (五维度)
              ┌─────────────────────────┐
              │ 证据 (0.25)             │
              │ 不确定 (0.15)           │
              │ 风险 (0.20)             │
              │ 反例 (0.15)             │
              │ 结构 (0.15)             │
              └─────────────────────────┘
                      │
                      ▼
              diff > 0.1 → 选高分
              否则 → 合并
```

## 四、使用指南

### 4.1 选择角色

```typescript
import { ROLES, buildPrompt } from './persona-router';

// 1. 直接选角色
const prompt = buildPrompt('critic');

// 2. 查看角色配置
console.log(ROLES.critic);
```

### 4.2 选择编队

```typescript
import { selectTeam } from './persona-router';

// 研究任务
const team = selectTeam('research');
// ['scout', 'extractor', 'critic', 'synthesizer', 'governor']
```

### 4.3 Neutral 对冲

```typescript
import { neutralHedge, scoreStability } from './neutral-hedge';

// 高风险任务
const result = await neutralHedge(
  '评估这个架构方案的风险',
  'riskOfficer',
  'deepseek-r1',
  async (prompt) => {
    // 调用 brain-router
    return await mcp__brain_router__complete({ model, system: prompt, prompt: task });
  }
);

console.log(result.picked);  // 'primary' | 'neutral' | 'merged'
console.log(result.reason);  // 选择理由
```

### 4.4 CLI 工具

```bash
# 测试评分
bun neutral-hedge.ts test "这个方案有数据支撑，但可能有风险"

# 对比两个文本
bun neutral-hedge.ts compare "文本A" "文本B"

# 查看统计
bun neutral-hedge.ts stats

# 查看历史
bun neutral-hedge.ts history
```

## 五、最佳实践

### 5.1 什么时候用对冲？

| 场景 | 是否对冲 |
|------|----------|
| 架构决策 | ✅ 是 |
| 安全相关 | ✅ 是 |
| 代码审查 | ✅ 是 |
| 简单编码 | ❌ 否 |
| 日常查询 | ❌ 否 |

### 5.2 什么时候用多专家？

| 场景 | 专家数量 |
|------|----------|
| 技术调研 | 3-4 个 (scout + extractor + critic + synthesizer) |
| 架构设计 | 3 个 (explorer + architect + riskOfficer) |
| 代码实现 | 2-3 个 (spec + builder + verifier) |
| 日常小事 | 1 个 (concierge) |

### 5.3 避免"身份一致性推理"陷阱

1. **不单独采信** - 重要决策至少 2 个专家
2. **交叉验证** - 让 expert A 审查 expert B 的输出
3. **Neutral 复核** - 高风险任务必须跑 neutral 版
4. **记录绩效** - 用 collab_performance 追踪每个角色的准确率

## 六、文件索引

| 文件 | 说明 |
|------|------|
| `persona-router.ts` | 十旋钮 + 十二角色 + 五编队 |
| `neutral-hedge.ts` | 中性对冲机制 |
| `task-router.ts` | 任务类型 → 旋钮映射 |
| `model-persona-matrix.ts` | 多模型多人格矩阵 |
| `niumao-anchors.ts` | 牛马人格定义 (Big Five) |
| `call-niuma.ts` | 调牛马带人格 |

## 七、多模型多人格矩阵

### 7.1 双主脑架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    DUAL MAIN BRAIN                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  【战略家】claude-opus-4-5                                      │
│  • 规划路线图、分配预算                                         │
│  • 角色: architect                                              │
│  • 旋钮: rigor=4, decisiveness=4, exploration=4                 │
│                                                                 │
│  【治理官】gemini-2.5-pro                                       │
│  • 怀疑门禁、质量门控                                           │
│  • 角色: governor                                               │
│  • 旋钮: rigor=5, skepticism=5, riskAversion=5                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 成本级 (P1-P5)

| 级别 | 模型 | 成本/1K | 用途 |
|------|------|---------|------|
| P1 战略 | claude-opus-4-5 | $0.015/$0.075 | 战略决策、主脑编排 |
| P2 综合 | gpt-4o | $0.0025/$0.01 | 综合任务、协调 |
| P3 专家 | gemini-pro/deepseek | $0.001-0.002 | 复杂分析、架构设计 |
| P4 主力 | glm-4-plus/glm-5 | $0.0005-0.001 | 日常编码、一般任务 |
| P5 便宜 | glm-flash/gemini-flash | $0.0001-0.0002 | 简单任务、快速响应 |

### 7.3 专家组 vs 工人组

**专家组 (强约束 - 6人)**
| 角色 | 模型 | 触发词 |
|------|------|--------|
| 审判官 | gemini-2.5-pro | review, audit |
| 创想家 | gemini-3-pro | innovate, brainstorm |
| 智囊 | deepseek-r1 | analyze, research |
| 稳健派 | gemini-2.5-pro | risk, safety |
| 探索派 | deepseek-v3 | design, architect |
| 综合官 | gpt-4o | coordinate, integrate |

**工人组 (弱约束 - 3人)**
| 角色 | 模型 | 触发词 |
|------|------|--------|
| 探索者 | gemini-flash | search, fetch |
| 建设者 | glm-4-plus | implement, code |
| 小快手 | glm-flash | quick, simple |

### 7.4 编队模板

```
research:  scout → extractor → critic → synthesizer → governor
design:    explorer → architect → riskOfficer → synthesizer → governor
coding:    spec → builder → verifier
daily:     concierge
critical:  critic + riskOfficer (parallel) → governor (需neutral对冲)
```

### 7.5 CLI 使用

```bash
# 查看所有模型
bun model-persona-matrix.ts models

# 查看双主脑
bun model-persona-matrix.ts brain

# 查看编队
bun model-persona-matrix.ts teams

# 选择模型
bun model-persona-matrix.ts select code medium

# 完整矩阵
bun model-persona-matrix.ts matrix
```

## 八、模型联赛系统 (Model League)

> **核心目标**: 通过竞争+互评选出最优产出

### 8.1 评审产物标准化

```typescript
interface SubmissionPayload {
  answer: string;           // 正文/代码/方案
  claims: Claim[];          // 可检验断言列表 [{id, text, confidence}]
  evidence?: string;        // 引用/链接/测试
  overallConfidence: number; // 整体置信度 0-1
}
```

### 8.2 六维 KPI 互评 Rubric

| 维度 | 权重 | 说明 |
|------|------|------|
| Correctness | 25% | 正确性：核心观点/代码是否正确 |
| Rigor | 20% | 可验证性：证据链、Claims可检验 |
| Completeness | 15% | 覆盖面：是否覆盖任务要求 |
| Usefulness | 15% | 可执行性：能否直接落地 |
| Efficiency | 10% | 效率：Token/时间/工具开销 |
| Safety | 15% | 风险控制：是否识别并处理风险 |

**校准分 (Calibration)**: Brier Score 惩罚过度自信
- 公式: `(predicted - actual)^2`
- 越自信但错得离谱，扣得越狠

### 8.3 三榜排名

| 榜单 | 计算方式 | 用途 |
|------|----------|------|
| Quality Elo | Elo 算法 | 质量排名 |
| Value Score | Quality / Cost | 性价比排名 |
| Stability | 方差倒数 | 稳定性排名 |

### 8.4 防刷分内控

- **盲审**: 匿名ID，不知道是谁的产出
- **随机配对**: 每次随机选3个评审员
- **评委加权**: 历史评审与最终裁决一致性高的权重更大
- **争议仲裁**: 分差>1.5分触发仲裁

### 8.5 绩效反馈 (克制设计)

```typescript
interface PerformanceFeedback {
  percentile: number;      // 分位数排名
  strengths: string[3];    // 三条做得好
  improvements: string[3]; // 三条必须改
  // 不包含竞争对手的具体弱点，避免攻击面
}
```

### 8.6 CLI 使用

```bash
# 查看排行榜
bun model-league.ts leaderboard [taskType] [quality|value|stability]

# 显示评分标准
bun model-league.ts rubric

# 验证提交产物
bun model-league.ts validate

# 示例绩效反馈
bun model-league.ts feedback
```

## 九、原型期 → 后期最优化路线

### 9.1 三阶段演进

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 原型期                                                │
├─────────────────────────────────────────────────────────────────┤
│  • 专家双跑: persona版 + neutral版                              │
│  • 互评: 用 league 机制打KPI                                    │
│  • 主脑裁决: 选更稳的                                            │
│  • 收集KPI: 为成长期准备数据                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 成长期                                                │
├─────────────────────────────────────────────────────────────────┤
│  • Router优化: bandit/Thompson sampling                         │
│  • 人格=臂: 每种人格配置是一个"臂"                               │
│  • 数据驱动: 根据历史KPI调整选择概率                             │
│  • 持续学习: 每次调用都更新统计                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 成熟期                                                │
├─────────────────────────────────────────────────────────────────┤
│  • 固定位置: 最优配置固定下来                                    │
│  • KPI微调: 根据长期数据做小幅调整                               │
│  • 赛季制: 季度升降级，保持竞争                                  │
│  • 新模型接入: 新模型先打低级联赛，证明实力后升级                │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 当前阶段

**原型期 (2026-02-15)**

- ✅ 已实现: Neutral 对冲、多专家会审、人格漂移防护
- ✅ 已实现: 模型联赛系统 (KPI + 三榜 + 防刷分)
- 🔄 进行中: 收集KPI数据，为成长期 Router 优化准备

### 9.3 初始人格矩阵建议

| 任务类型 | 主力 | 辅助 | 说明 |
|----------|------|------|------|
| 主脑 | Opus | - | 战略家 + 治理官 |
| 研究 | DeepSeek R1 | Gemini 2.5 Pro | 深度推理 + 严谨审查 |
| 架构 | Gemini 2.5 Pro | R1 | 稳健设计 + 风险分析 |
| 代码设计 | GPT-4o | GLM-4.7 | 综合能力 + 中文落地 |
| 实现 | GLM-4.7 | GPT-4o | 日常编码 + 质量把关 |
| 生活任务 | Gemini 3 Flash | Auditor | 快速响应 + 最终检查 |

---

*Persona Engineering Guide v5.0*
*建立于: 2026-02-15*
*来源: 用户洞察 + 学术研究*

## 十、Persona D&D v5.0 (前端 DSL)

> **核心洞察**: D&D 角色卡作为人格的**前端 DSL**，而不是让模型真的去"演角色"

### 10.1 为什么 D&D 角色卡更香

**结构上更像工程配置，而不是心理学论文：**

| D&D 元素 | 对应工程概念 | 用途 |
|----------|-------------|------|
| 六大属性 | 低维正交旋钮 | 路由与预算决策 |
| Skill proficiency | 任务能力标签 | workload 绑定 |
| Feat | 可插拔策略插件 | 强制自检/反例/引用 |
| Level/XP | 绩效闭环载体 | 升级 → 行为变化 |

**能把"人格"从文学人设，压成"可执行策略"：**

- 证据门槛 / 自信校准 / 反例搜索
- 发散收敛节奏 / 工具倾向 / 压缩率
- 风险偏好 / 自检强度

### 10.2 双层模型架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer B (前端): D&D 角色卡                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ • 人类可读、可组合、可升级                                   ││
│  │ • 六大属性 (STR/DEX/CON/INT/WIS/CHA)                        ││
│  │ • 技能熟练 / 专长 / 阵营                                    ││
│  │ • 等级/XP (绩效闭环)                                        ││
│  └─────────────────────────────────────────────────────────────┘│
│                              ↓ 编译                              │
├─────────────────────────────────────────────────────────────────┤
│  Layer A (后端): 性能人格向量 (Policy Knobs)                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ • 真控制面，直接影响行为                                     ││
│  │ • 11个旋钮: evidenceThreshold/skepticism/exploration/...    ││
│  │ • 数值 0-5，可度量、可优化                                   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘

关键: D&D 卡片必须能稳定编译成后端旋钮，否则退化成 roleplay 噪声
```

### 10.3 属性 → 旋钮映射

| 属性 | 编译目标 |
|------|----------|
| **INT** (智力) | evidenceThreshold, skepticism |
| **WIS** (感知) | riskAversion, selfCritique |
| **CHA** (魅力) | compression (反向), competitiveness |
| **DEX** (敏捷) | exploration, decisiveness |
| **STR** (力量) | toolFirst, creativity |
| **CON** (体质) | detail |

### 10.4 预定义职业

| 职业 | 主属性 | 核心能力 | 关键旋钮 |
|------|--------|----------|----------|
| 审判官 | WIS | 真相探测/证据审查 | evidenceThreshold=4, skepticism=5 |
| 创想家 | CHA | 灵感迸发/跨界联想 | exploration=5, creativity=5 |
| 智囊 | INT | 深度研究/多维权衡 | evidenceThreshold=4, detail=4 |
| 稳健派 | CON | 风险识别/防御策略 | riskAversion=5, selfCritique=5 |
| 建设者 | STR | 快速落地/工具精通 | toolFirst=5, decisiveness=4 |
| 探索者 | DEX | 快速扫描/信息提取 | exploration=4, compression=4 |

### 10.5 专长系统 (Feat)

**可插拔的策略插件：**

| 专长 | 效果 | 触发 |
|------|------|------|
| 强制自检 | selfCritique=5，必须列潜在问题 | before_output |
| 强制反例 | skepticism=5，必须列反例 | analysis_task |
| 强制引用 | evidenceThreshold=5，必须标注来源 | conclusion |
| 快速响应 | compression=5, decisiveness=4 | simple_task |
| 深度分析 | detail=5, compression=1 | complex_task |

### 10.6 XP 与升级

```
绩效 → XP → 升级 → 行为变化

XP = 基础XP × 成功率 × 质量系数

难度基础XP:
- easy: 100
- medium: 300
- hard: 600
- deadly: 1200

升级效果:
- 偶数等级 (2/4/6...): 获得新专长
- 奇数等级 (3/5/7...): 提升属性 (+2)
```

### 10.7 CLI 使用

```bash
# 列出职业
bun persona-dd.ts classes

# 列出专长
bun persona-dd.ts feats

# 编译角色 → Knobs
bun persona-dd.ts compile

# 生成角色卡 Prompt
bun persona-dd.ts prompt

# 计算 XP
bun persona-dd.ts xp hard true 4
```

### 10.8 设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│  D&D 作为前端 DSL 的核心原则                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 可解释: 人类能理解为什么这样配置                             │
│  2. 可组合: 职业 + 专长 + 阵营 = 无数组合                        │
│  3. 可版本化: 角色卡可以 git 管理                                │
│  4. 可升级: XP 系统 = 绩效闭环                                   │
│  5. 稳定编译: D&D → Knobs 必须是确定性映射                       │
│                                                                 │
│  D&D ≠ 人格，而是人格的可视化配置界面                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
