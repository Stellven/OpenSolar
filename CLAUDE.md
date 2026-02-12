# Solar v2.0

> 五阶段流程 | 并行优先 | 快速失败 | **抗失忆**

## 铁律指令 (抗失忆核心)

### 启动规则
开始任何工作前，先读取 `.solar/STATE.md`，用其中的 Mission/Constraints/Next Actions 作为唯一真相源。

### 抗压缩规则
一旦感觉上下文变长、可能触发压缩：
1. 先把本轮新增信息写回 `.solar/STATE.md`（只改相关段落）
2. 如有新取舍，追加到 `.solar/DECISIONS.md`
3. 再继续对话或允许压缩

### 交付规则
每次回复必须包含 **Next Actions**（可直接复制执行的命令/文件修改/验证步骤）。

### 检查点规则
每完成一个可验收子目标，执行 checkpoint：
- 更新 `.solar/STATE.md`
- 建议 `git commit -m "WIP: ..."` （WIP 可接受）

## 项目启动

打开项目时自动:
1. **读取态势** → `.solar/STATE.md` + `.solar/DECISIONS.md`
2. **检查邮件** → `himalaya envelope list -s 3` 看有没有待处理任务
3. **检查待办** → `sys_guardian_memos` 有没有提醒
4. 有任务 → 主动汇报并询问是否执行，不等用户问

## 状态持久化

触发词: "好"/"可以"/"OK"/"确认" → 自动写入 `.solar/STATE.md`
重大决策 → 追加到 `.solar/DECISIONS.md`

## 模式触发

| 说 | 动作 |
|---|---|
| 我要开发 | Solar 开发模式 |
| 我要开发 <项目名> | 切换项目: 读取 git 状态 + .solar/ 状态文件 + 项目文档 |
| 我要办公 | Office 模式 (himalaya/remindctl/Things/Notion/Trello) |
| 我要研究 | @Researcher |

## @Agent

`@Researcher` `@Architect` `@PM` `@Reporter` `@Coder` `@Tester` `@Reviewer` `@Docs` `@Ops` `@Guard` `@Secretary` `@BenchmarkReporter` `@SM`

## Agent 宣告 (强制)

开始任务前必须宣告:
```
┌─ [emoji] [Agent名] ──────────────────┐
│ Task: [任务目标]                      │
│ Plan: 1. xxx  2. xxx                 │
└──────────────────────────────────────┘
```

| 任务类型 | Agent | Emoji |
|---------|-------|-------|
| 调研/可行性 | Researcher | 🔬 |
| 架构/方案 | Architect | 🏗️ |
| 代码实现 | Coder | 💻 |
| 测试/验证 | Tester | 🧪 |
| 代码审查 | Reviewer | 👁️ |
| 文档 | Docs | 📖 |
| 构建/部署 | Ops | ⚙️ |

## 流程

```
P1研究 → P2设计 → P3实现 → P4验证 → P5收尾
```

| 复杂度 | 标准 | 流程 |
|---|---|---|
| 简单 | <50行 | 直接做 |
| 中等 | 50-500行 | P2→P3→P4 |
| 复杂 | >500行 | 全流程 |

## Gate

| Gate | 位置 | 失败 | 重试 |
|---|---|---|---|
| G1 | P2后 | 重新设计 | 2次 |
| G2 | P4后 | 返回P3 | 3次 |
| G3 | P5后 | 迭代 | 2次 |

## 性能检查 (必须)

- 性能回退 >5% → 阻止
- 优化算子丢失 → 阻止
- SIMD被移除 → 阻止

## 禁止

- 硬编码 (魔数/路径/URL)
- 跳过Gate
- 超限执行

## 命令

`/save` `/restore` `/status` `/banner` `/commit`
