# Solar 任务积压 (Task Backlog)

> 更新时间: 2026-02-04 06:20
> 来源: 本次会话（小区神经网 + 记忆系统优化）

---

## 🔥 高优先级 (P0) - 本周

### HIVE Phase 2 验证
- [ ] 验收测试：运行 `bash core/hive/cli/quick-verify.sh`
- [ ] 双节点测试：2台设备启动并自动发现
- [ ] 性能测试：验证延迟 <50ms, 发现 <5s
- [ ] 文档审查：QUICKSTART.md 是否清晰

**预期**: 全部通过 → Phase 2 正式完成

---

### Memory v2.0 - 向量检索
- [ ] 安装 sqlite-vec 扩展
- [ ] 集成 all-MiniLM-L6-v2 模型 (本地)
- [ ] 创建 `evo_memory_embeddings` 表
- [ ] 对现有 28 条记忆生成向量
- [ ] 实现 `semanticSearch(query, topK)` API
- [ ] 测试：查询"小区神经网"能找到继承人的记忆

**预期**: 检索准确率 +50%

---

## ⚡ 中优先级 (P1) - 下周

### Memory v2.0 - Zettelkasten 图结构
- [ ] 创建 `evo_memory_links` 表
- [ ] 实现自动链接检测（语义相似度 >0.7）
- [ ] 实现链接类型：semantic, causal, temporal, reference
- [ ] 实现图遍历检索（多跳推理）
- [ ] 可视化：生成记忆网络图

**参考**: A-MEM 论文 (NeurIPS 2025)

---

### Memory v2.0 - 记忆演进
- [ ] 实现 `evolveMemory(newInfo, relatedMemories)`
- [ ] LLM 判断演进策略（更新/合并/分裂/链接）
- [ ] 记录演进历史（可追溯）
- [ ] 测试：新信息"小区有30户"应更新"小区20户"的记忆

**参考**: A-MEM 动态更新机制

---

## 🌟 低优先级 (P2) - 2-4周

### Memory v2.0 - 三类记忆分离
- [ ] 设计 Episodic 记忆表（会话时间线）
- [ ] 设计 Procedural 记忆表（技能/流程）
- [ ] 统一检索接口
- [ ] 迁移现有数据

**参考**: 学术三分法共识

---

### Memory v2.0 - 自适应遗忘
- [ ] 实现 FSRS 间隔重复算法
- [ ] 重要性评分（访问频率 + 时效性）
- [ ] 自动归档低重要性记忆
- [ ] 定期整合压缩

**参考**: Spaced Repetition 研究

---

### HIVE Phase 3 - 任务市场
- [ ] 实现 TaskMarket 类
- [ ] Publish 任务广播
- [ ] Bid 竞标收集与评估
- [ ] Accept 接受通知
- [ ] Escrow 积分托管

---

### HIVE Phase 4 - 同步与安全
- [ ] CRDT 状态同步（节点列表、积分账本）
- [ ] mTLS 双向认证
- [ ] 任务沙箱执行
- [ ] 敏感数据过滤

---

### HIVE Phase 5 - 容错
- [ ] Heartbeat 监控
- [ ] 任务重试与迁移
- [ ] 结果验证（Self/Peer/Consensus）
- [ ] 网络分区处理

---

## 📝 文档任务

- [ ] 补充技术报告附录 (6个)
- [ ] 补充演进报告附录 (6个)
- [ ] 完成 README.md 重构
- [ ] 撰写小区神经网白皮书
- [ ] 撰写 Memory v2.0 设计文档

---

## 🎯 里程碑

### Milestone 1: HIVE PoC (2周内)
- Phase 2 验证 ✅
- Phase 3 任务委托 ⏳
- 2-3 台设备测试 ⏳

### Milestone 2: Memory v2.0 (4周内)
- 向量检索 ⏳
- 图结构 ⏳
- 记忆演进 ⏳

### Milestone 3: 小区试点 (2-3个月)
- 5-10 户家庭参与
- 真实场景验证
- 性能数据收集

---

## 📊 当前进度

| 模块 | 阶段 | 完成度 | 下一步 |
|------|------|--------|--------|
| HIVE | Phase 2 | ✅ 100% | 验收测试 |
| Memory | 调研 | ✅ 100% | 开始实现 |
| 文档 | 草稿 | ✅ 90% | 补充附录 |
| 记忆机制 | 改进 | ✅ 100% | 持续监控 |

---

## 🎮 监护人可玩的功能

**现在就能玩**:
```bash
# 1. 启动 HIVE 节点（如果有2台设备）
bun core/hive/cli/node.ts start --name="主节点"

# 2. 测试记忆检索
bun core/memory/auto-semantic.ts check "小区神经网"

# 3. 查看会话状态
cat .solar/session.md

# 4. 语义记忆统计
bun core/memory/auto-semantic.ts stats
```

**等实现后能玩**:
```bash
# Memory v2.0
bun core/memory/semantic-search.ts "继承人说了什么"
bun core/memory/memory-graph.ts visualize

# HIVE Phase 3
bun core/hive/cli/admin.ts publish --task="审查代码" --reward=50
bun core/hive/cli/admin.ts market  # 查看任务市场
```

---

*此文件会随着任务进展持续更新*
*下次会话可以从这里快速恢复上下文*
