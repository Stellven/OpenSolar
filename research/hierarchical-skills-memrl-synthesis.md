# Hierarchical Skills × MemSkill × MemRL × Skill-RAG：架构综合分析

> **来源**: 2026-02-18 Solar 架构研究
> **背景**: 分析 Hierarchical Skills 论文，结合 ChatGPT 补充分析，与 Solar 已实现的 MemSkill+MemRL 整合评估
> **目标**: 评估该体系能否让 Agent 在精准度和 Long-horizon 任务上产生结构性提升

---

## 一、问题的起点：扁平工具列表的三个病

当前主流 Agent（AutoGPT、LangChain）把所有工具平铺成一个列表，带来三个根本性问题：

### 1.1 路由熵（Routing Entropy）

当 Agent 面对 94 个 skills，每次选工具的决策熵约为：

```
H = log₂(94) ≈ 6.5 bits
```

即使每次只选一个工具，注意力机制需要同时"比较" `ls` 和 `deploy-k8s`。这两者的语义距离极远，但在 attention 权重计算里处于同等地位。

**后果**：
- Token 预算被工具描述吃掉 30-40%
- 模型在低相关工具上产生幻觉参数
- 选错工具的概率随工具数量增加而非线性上升

### 1.2 上下文污染

扁平列表里 `curl` 和 `kubectl rollback` 同时出现，模型对"现在应该用什么"的上下文判断被稀释。正确工具被错误上下文"噪声"淹没。

### 1.3 没有时序抽象

模型必须在 primitive action 层面规划所有步骤。20 步任务就是规划 20 个原子操作，中间任何一步的错误会导致整个链条崩溃，且没有恢复机制。

---

## 二、Hierarchical Skills 的核心提案

论文提出了一套基于文件系统的技能分层架构。

### 2.1 双层技能分类

| 类型 | 特性 | 作用 |
|------|------|------|
| **Atomic Skills** | 无状态、幂等、不可修改 | 原始操作，系统底层 |
| **Composite Skills** | 有状态、封装控制流/错误处理 | 时序抽象，高阶操作 |

Composite Skill 的关键元数据（Frontmatter）：

```yaml
name: k8s-deploy-service
risk_level: high
idempotency: no
rollback: k8s-rollback-service
blast_radius: cluster
dependencies: [kubectl, jq, curl]
```

### 2.2 动态 $PATH 挂载（最有价值的概念）

Agent 不是"持有所有工具"，而是"按上下文挂载相关命名空间"：

```
任务类型: Kubernetes 运维
→ 挂载: ~/.agent/skills/kubernetes/
→ 暴露给模型: 8个 k8s 相关 skills
→ 路由熵从 6.5 bits 降至 3.0 bits
```

实现方式类似 kubectl plugin 模式：扫描 $PATH 中符合命名规则的二进制/脚本，无需中央注册表。

### 2.3 论文的三个致命缺陷

**缺陷一：谁来决定挂载哪个命名空间？**
论文描述了"动态挂载"，但没有说明 Orchestrator 如何判断当前任务属于哪个域。这是架构设计的最大空缺。

**缺陷二：Composite Skill 的自我修改权限过于危险**
论文允许 Agent 写入 Composite Skills（"自我进化"）。但 Agent 对自身代码有写权限，在生产环境中是不可接受的安全风险。

**缺陷三：MCP 集成方案欠具体**
论文提到 MCP 混合架构，但未说明文件系统技能如何与 MCP server 在接口层统一对外暴露。

---

## 三、ChatGPT 分析的增量贡献

独立看了 ChatGPT 对同一篇论文的分析，几个真正有价值的新增概念：

### 3.1 两级路由架构（解决致命缺陷一）

```
Router (检索层)
  └─ 根据任务语义，选择挂载哪个命名空间/skill set
  └─ 实现: 向量检索 + 历史成功率加权

Executor (执行层)
  └─ 在已挂载的 skill set 内选择具体工具执行
  └─ 路由空间已收窄，决策质量更高
```

Router 把"挂载什么"和"用什么"解耦，Orchestrator 不再需要同时解决两个问题。

### 3.2 Skill-RAG（最有价值的新概念）

本质上是把工具选择问题转化为检索问题：

```
传统方式: 任务描述 → 生成工具调用参数（从零生成，hallucination 风险高）
Skill-RAG: 任务描述 → 检索历史成功 playbook → 参数化复用（填空题）
```

"先检索成功率最高的 playbook，再让模型做少量参数化"——这把创作题变成填空题，精准度提升明显。

### 3.3 三层物理架构（统一了文件系统和 MCP）

```
FS Layer (真相层)
  └─ ~/.agent/skills/ 存储实际脚本和 Frontmatter
  └─ 人类可读、可 git 管理、可 audit

Index Layer (检索层)
  └─ SQLite + 向量索引（如 Tantivy）
  └─ 存储元数据、成功率、embedding

MCP Layer (接口层)
  └─ 对 LLM 暴露统一工具接口
  └─ 屏蔽底层是文件还是服务的差异
```

### 3.4 生产级安全字段（我遗漏的部分）

`idempotency`（能否重试）、`blast_radius`（影响范围）、`rollback` 指针、`risk_level` 分级——这些字段对生产环境至关重要，原论文提及不够，ChatGPT 的补充有实质价值。

---

## 四、MemSkill + MemRL 的集成可能性

Solar 之前实现了 MemSkill 和 MemRL。把这两个和上面的架构放在一起看，发现它们天然互补：

### 4.1 MemRL 解决的是致命缺陷一

MemRL = 学习路由策略的强化学习机制。

```
Router 层怎么实现？
→ MemRL 就是 Router

MemRL 学习的是:
  state(任务上下文) → action(挂载哪个命名空间) → reward(任务成功率)
```

这不是巧合——这正是 HRL（Hierarchical Reinforcement Learning）的 Options Framework 在描述的东西：
- Sutton/Precup/Singh（1999）定义 Option = `(I, π, β)`（初始条件、内部策略、终止条件）
- Composite Skill = Option
- MemRL = 学习"何时启动哪个 Option"的高层策略 `π_high`

论文描述的是架构形态，MemRL 提供的是学习机制。两者是同一个问题的不同层次。

### 4.2 MemSkill 是 Skill-RAG 的数据层

```
Skill-RAG 需要: 历史 playbook + 成功率
MemSkill 记录:  每次 skill 调用的输入/输出/成功/失败/上下文

→ MemSkill 的数据直接作为 Skill-RAG 的检索库
```

MemSkill 产出的执行记录，经过 embedding 索引后，就是 Skill-RAG 的检索目标。

### 4.3 完整架构闭环

```
MemRL (学习路由策略)
     ↓ 决定挂载哪个命名空间
Hierarchical Skills (结构化技能文件系统)
     ↓ 提供有组织的动作空间
Skill-RAG (检索最优 playbook)
     ↓ 参数化复用而非从零生成
MemSkill (带记忆的执行)
     ↓ 记录每次执行的输入/输出/结果
执行结果 → 反馈回 MemRL（更新路由策略）+ MemSkill（扩充检索库）
```

这是一个自强化的闭环：执行越多，路由越准，检索越好。

### 4.4 安全的自我进化

论文的"Agent 写入 Composite Skills"被这套架构优雅地绕过：

- **Skills 代码层**: 只读，不允许 Agent 修改（消除安全风险）
- **Memory 层**: Agent 可以写（MemSkill 记录调用模式）
- **进化的本质**: 不是修改代码，而是更新调用策略和参数

这完全符合 Solar 的"改自己必须专家团队审核"铁律——Skills 是只读的，Memory 是可学习的。

---

## 五、Solar 现有能力对照

Solar 已经有了大量相关数据和基础设施：

| 层 | 需要什么 | Solar 现有什么 | 缺口 |
|----|---------|----------------|------|
| **FS Layer** | 结构化技能目录 + Frontmatter | `~/.claude/skills/`（94个，平铺）| 缺层级结构和元数据字段 |
| **Index Layer** | 向量索引 + 成功率 | `sys_skills` + Tantivy（15K+ docs）| 缺 `context_tags`、`idempotency`、`blast_radius` 字段 |
| **MemSkill 记录** | 执行历史 | `sroe_requests`、`evo_memory_procedural` | 数据在，需要连接到检索层 |
| **Skill-RAG** | 检索 → 参数化 | Tantivy 已可检索 | 缺"检索 playbook → 参数化"的推理链 |
| **MemRL 路由** | 学习 state→namespace 映射 | MemRL 已实现 | 需要将 namespace 挂载作为 action 空间 |
| **MCP Layer** | 统一接口 | brain-router | 缺"按 mount-set 过滤暴露"机制 |

**结论**：Solar 有所有数据层，缺的是连接逻辑。

---

## 六、自我评估：精准度与 Long-horizon 任务

如果上述架构全部落地，诚实评估提升幅度：

### 6.1 精准度（按任务类型）

| 场景 | 当前估算 | 实现后预期 | 主要贡献机制 |
|------|---------|-----------|-------------|
| 熟悉任务（有历史记录）| ~70% | ~85-90% | Skill-RAG 贡献最大 |
| 新任务（冷启动）| ~55% | ~60% | 基本无改善 |
| 精确参数运维任务 | ~50% | ~80% | MemSkill 记忆成功参数 |
| Long-horizon (>15步) | ~45% | ~70% | 时序抽象贡献最大 |

### 6.2 Long-horizon 任务的结构性改善

当前规划 20 步任务：线性规划，中间断了全崩。

有 Composite Skills + MemRL 之后：

```
规划空间压缩：
20 个 atomic steps → 4-5 个 Options (Composite Skills)
规划 horizon 从 20 压缩到 4-5
```

这是量级性的改变，不是边际优化。对 context 的利用效率大幅提升。

### 6.3 诚实的局限（不能回避）

**局限一：冷启动问题**
MemRL 在历史数据稀少时是近似随机策略。需要 500-1000 次高质量执行记录后，路由策略才有实质意义。

**局限二：训练信号是关键变量**
如果 reward signal 是稀疏的（只看最终任务成败），RL 学习会很慢。需要 dense reward shaping——每个 namespace 选择对不对、每个 Composite Skill 执行成没成，都要有即时反馈。

**局限三：语义理解错误，路由再准也没用**
如果在 L0（理解用户意图）就错了，精准路由不能纠正根本性的语义理解失败。

**局限四：context window 物理限制依然存在**
时序抽象压缩了规划 horizon，但单个 Option 内的执行依然消耗 context。超长任务依然会触碰 context 上限。

---

## 七、待研究的关键问题

1. **训练信号设计**：MemRL 的 reward 应该是 task-level（稀疏）还是 step-level（dense）？如何避免 reward hacking？

2. **命名空间粒度**：如何确定合适的 namespace 粒度？太细（每个 skill 一个 namespace）失去收益，太粗（只有 `dev/` 和 `ops/`）路由熵下降有限。

3. **Composite Skill 的组合爆炸**：Composite Skill 可以嵌套 Atomic Skill，那 Composite Skill 可以嵌套 Composite Skill 吗？嵌套深度怎么控制？

4. **冷启动解法**：在历史数据不足时，如何用 meta-learning 或 transfer learning 加速 MemRL 收敛？

5. **Skill-RAG 的相似度定义**：任务相似度应该基于语义（embedding）还是结构（任务类型+参数模式）？两者如何加权？

---

## 八、结论

Hierarchical Skills × MemSkill × MemRL × Skill-RAG 四者构成一个自洽的架构闭环。核心价值在于：

1. **路由熵下降**：动态命名空间挂载 + MemRL，把工具选择从嘈杂市场变成精准分拣
2. **时序抽象**：Composite Skills 把 20 步 atomic 规划压缩为 4-5 步 Option 选择
3. **从创作题到填空题**：Skill-RAG 用历史成功 playbook 替代从零生成，减少 hallucination
4. **安全进化**：进化发生在 memory 层而非 code 层，保留 Skills 的不变性

Solar 已具备所有数据基础，缺的是把这些层连接起来的逻辑。

---

*作者: Solar (战略家 + 治理官 双签)*
*日期: 2026-02-18*
*状态: 研究草稿，待四专家会审*
