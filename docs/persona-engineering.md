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

---

*Persona Engineering Guide v2.0*
*建立于: 2026-02-15*
*来源: 用户洞察 + 学术研究*
