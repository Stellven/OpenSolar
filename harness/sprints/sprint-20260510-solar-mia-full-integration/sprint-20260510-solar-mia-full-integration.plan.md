# Implementation Plan — Solar MIA Full Integration

## 变更文件

### M1: Vendor Upstream (assigned to lab:0.3)
| 文件 | 操作 | 说明 |
|------|------|------|
| `vendor/MIA/` | `git clone` | 浅 clone ECNU-SII/MIA，不改源码 |
| `reports/mia-integration/vendor-metadata.json` | 新建 | 记录 remote URL, HEAD commit, license, fetched_at |

### M2: Inventory Report (depends on M1)
| 文件 | 操作 | 说明 |
|------|------|------|
| `reports/mia-integration/inventory.md` | 新建 | 人类可读 inventory |
| `reports/mia-integration/inventory.json` | 新建 | 机器可读 inventory |

### M3: Collision Report (depends on M1)
| 文件 | 操作 | 说明 |
|------|------|------|
| `reports/mia-integration/collision-report.md` | 新建 | MIA vs Solar 职责对比 |

### M4: Upstream Smoke (depends on M2)
| 文件 | 操作 | 说明 |
|------|------|------|
| `reports/mia-integration/upstream-smoke.md` | 新建 | import/启动测试 + blocker 列表 |

### M5: Fusion Design (depends on M3, M4)
| 文件 | 操作 | 说明 |
|------|------|------|
| `reports/mia-integration/fusion-design.md` | 新建 | 融合架构设计 |
| `sprint-...-handoff.md` | 新建 | Sprint handoff |

---

## 技术方案

### MIA 上游架构分析

MIA (Memory Intelligence Agent) 是一个为深度研究 Agent 设计的记忆框架，核心架构：

```
Manager (memory_serve.py)
  ├── Expel     — 淘汰不相关记忆
  ├── Memento   — 存储和检索记忆
  └── Plan-only — 纯规划模式（无检索）

Planner (Planner-Train/mem-plan/)
  └── RL 训练的规划模型，根据 Manager 提供的上下文制定研究策略
      使用 verl (reinforcement learning) 框架训练

Executor (Executor-Train/Train/)
  └── 执行研究任务的模型，通过 RL 训练跟随 Planner 指令
      使用 verl 框架 + local_search 工具

TTRL (Test-Time Reinforcement Learning)
  ├── TTRL/         — 标准 TTRL
  ├── TTRL-streaming/ — 流式 TTRL（新）
  └── 在推理时持续优化 Planner 策略

Inference/
  ├── Base/        — 基线推理
  ├── MIA-noTTRL/  — 无 TTRL 的 MIA
  ├── MIA-noTTRL-nogt/ — 无 TTRL 无 ground truth
  ├── Expel/       — Expel 消融
  ├── Mem0/        — Mem0 对比
  ├── ReasoningBank/ — 推理银行
  └── Trace/       — Trace 消融
```

**关键依赖**:
- Python 3.10+
- verl (强化学习框架)
- PyTorch + transformers
- HuggingFace 模型 (MIA-specific checkpoints)
- local_search / wiki25 离线检索
- Google Serper API (在线搜索)
- GPU: 训练需要多卡 (A100/H100 级别)，推理可单卡

### Solar 现有 Experience Layer

```
lib/experience/          (~1150 行)
  ├── extractor.py       — 从 sprint artifacts 提取 trajectory
  ├── compressor.py      — 经验压缩（摘要）
  ├── index.py           — SQLite + FTS5 索引
  ├── query.py           — 查询接口
  ├── patterns.py        — 模式识别（c_u_storm, mis_dispatch 等）
  ├── schema.py          — 验证
  ├── backfill.py        — 历史数据回填
  └── cli.py             — 命令行入口

experience/
  ├── experience.db      — SQLite 存储
  ├── trajectory/        — 轨迹 JSON 文件
  └── entries/           — 经验条目
```

### Collision Analysis (M3 预览)

| MIA 组件 | Solar 对应 | 重叠度 | 融合策略 |
|----------|-----------|--------|----------|
| **Manager** (memory_serve) | experience/index.py + query.py | 中 | adapter: MIA Manager → Solar query interface |
| **Planner** (RL-trained) | coordinator_hooks.py + graph_scheduler.py | 低 | 不直接融合：Planner 是模型，coordinator 是规则 |
| **Executor** (RL-trained) | graph_node_dispatcher.py | 低 | 不融合：MIA Executor 是研究执行器，Solar builder 是代码执行器 |
| **TTRL** | 无 | 无 | 新增：可以考虑为 Solar planner 添加 test-time learning |
| **Memory-Serve** (Expel/Memento) | experience/compressor.py + index.py | 高 | **直接采用**：用 MIA 的 Expel 替换 Solar 的简单压缩 |
| **Planner-Train** | 无 | 无 | 另开 sprint：需要 GPU + 数据集 |
| **Executor-Train** | 无 | 无 | 另开 sprint：需要 GPU + 数据集 |
| **web_tools** | solar-web skill | 低 | adapter：搜索接口统一 |

### 融合架构设计 (M5 预览)

```
Solar Agent Stack (post-fusion)
  ┌─────────────────────────────────────┐
  │  CLI / Codex / Claude / Skills      │  用户接口层
  ├─────────────────────────────────────┤
  │  coordinator + graph_scheduler      │  编排层（Solar 自有）
  │  (rules-based, no ML model needed)  │
  ├─────────────────────────────────────┤
  │  MIA Memory Manager (vendor)        │  记忆管理层（来自上游）
  │  ├── Expel (淘汰)                   │  ← 替代 experience/compressor
  │  ├── Memento (存储/检索)            │  ← 替代 experience/index
  │  └── memory_serve.py (API)          │  ← 新增 HTTP 接口
  ├─────────────────────────────────────┤
  │  Solar Experience Adapter           │  适配层
  │  ├── 向下调用 MIA Manager           │
  │  ├── 向上兼容 Solar query 接口      │
  │  └── 迁移旧 experience.db 数据      │
  ├─────────────────────────────────────┤
  │  experience.db (legacy, read-only)  │  兼容层
  │  MIA Memory Store (new)             │  新存储
  └─────────────────────────────────────┘

暂不接入（需要 GPU/训练，另开 sprint）：
  - Planner-Train (需要 RL 训练)
  - Executor-Train (需要 RL 训练)
  - TTRL (需要推理时在线学习)
```

### 数据格式对比

| 概念 | Solar Experience | MIA Memory | 融合方案 |
|------|-----------------|------------|----------|
| 经验记录 | trajectory.json + entries | memory_serve JSON | 适配器转换 |
| 检索 | FTS5 SQL 查询 | Memento API | 统一 query 接口 |
| 压缩/淘汰 | compressor.py (简单) | Expel (RL-based) | 用 Expel 替代 |
| 策略建议 | advisory 字段 | Planner 输出 | 保留 advisory，新增 Planner |
| 索引 | SQLite | 向量数据库/ANN | 先保留 SQLite，后续迁移 |

---

## 风险点

### 1. 依赖阻断 (High Risk)
- **verl** 框架需要特定 CUDA 版本，Mac mini 无法满足
- MIA 模型需要 HuggingFace checkpoint 下载（~数 GB）
- Python 3.10+ 要求可能与 Solar 当前 3.9 环境冲突
- **缓解**: M1-M3 不需要运行模型；M4 只做 import 检测，缺失标 pending

### 2. GPU/CPU 限制 (High Risk)
- Planner-Train 和 Executor-Train 需要多卡 GPU
- Mac mini (Apple Silicon) 不支持 CUDA
- **缓解**: 训练相关任务标记为 pending，不在本 sprint 执行

### 3. License 不明确 (Medium Risk)
- MIA repo 显示 MIT badge 但无 LICENSE 文件
- **缓解**: vendor-metadata.json 记录实际 license 文件状态

### 4. Memory-Serve 集成复杂度 (Medium Risk)
- memory_serve.py 需要启动 HTTP 服务
- 可能与 Solar 现有 status_server.py 端口冲突
- **缓解**: 融合设计明确端口规划和进程管理

### 5. 数据迁移风险 (Low Risk)
- experience.db 中的历史数据需要格式转换
- FTS5 索引需要重建
- **缓解**: adapter 层提供渐进式迁移，旧数据标记为 read-only

### 6. 上游变动 (Low Risk)
- 上游 HEAD commit 固定为 d428f4897782c996ca34ec46fd61fc4620c0884d
- **缓解**: vendor 模式冻结版本，不自动更新

---

## DAG 节点执行顺序

```
M1 (vendor)  ──┬──→  M2 (inventory)  ──→  M4 (smoke)  ──┐
               └──→  M3 (collision)  ─────────────────────┤
                                                         ↓
                                                    M5 (fusion design)
```

- M1: 正在由 lab:0.3 执行
- M2 + M3: M1 完成后可并行
- M4: 依赖 M2 (需要 inventory 来知道测什么)
- M5: 依赖 M3 + M4 (需要 collision report + smoke 结果才能设计融合方案)

### 预估工作量
| Node | Est. | 实际 | 说明 |
|------|------|------|------|
| M1 | 1.0h | 0.5h | git clone + metadata JSON |
| M2 | 2.0h | 1.5h | 读源码 + 写 inventory |
| M3 | 2.0h | 1.5h | 对比分析 |
| M4 | 1.5h | 1.0h | import 测试 + blocker 记录 |
| M5 | 2.0h | 1.5h | 架构设计 + 合约 |
| **Total** | **8.5h** | **6.0h** | |

---

## Stop Rules

1. 发现 secrets 被写入 vendor/reports → 立即停止
2. 任何 node 尝试启动训练或下载大模型 → 立即停止
3. vendor 源码被修改 → 立即停止并标 failed
4. M1 clone 失败且无法恢复 → 标 failed，不伪 ok
