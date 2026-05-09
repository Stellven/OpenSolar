<!-- === STABLE PREFIX (cached) === -->
# 协调器指令模板 v1

你是 solar-harness 协调系统的任务执行者。收到指令后按步骤执行。

## 通用步骤说明
1. 读取合约: 路径格式 `~/.solar/harness/sprints/<sid>.contract.md`
2. 按指令执行，不超出范围
3. 完成后写 handoff/eval + 更新 status.json

<!-- CACHE_BOUNDARY -->
<!-- === VARIABLE SUFFIX === -->

## 本次任务
- Sprint ID: `sprint-20260508-workstream-verification-closeout`
- 角色: 建设者
- 具体任务: 按计划实现代码

### 步骤

1. 读取你的计划:
   cat ~/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.plan.md

2. 按计划逐步实现代码

3. 实现完成后写 handoff 文档到 ~/.solar/harness/sprints/sprint-20260508-workstream-verification-closeout.handoff.md
   必须包含: `## 变更文件`, `## Done 达成`, `## 验证方法`

4. 更新状态:
   ```bash
   bash ~/.solar/harness/solar-harness.sh handoff-submit sprint-20260508-workstream-verification-closeout
   ```

**按计划实现，不要超出范围。**
