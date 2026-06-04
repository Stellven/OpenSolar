# Planner Handoff: S04 Deep / Verifier / Repair Orchestration Surface

## 状态

- PRD: ready
- Design: ready
- Plan: ready
- Task graph: ready
- Handoff target: builder
- Parent epic: still active

## 上游已满足

- S01 requirements: passed
- S02 architecture: passed / eval_passed
- S03 core-runtime: passed / eval_passed / task_graph passed

## Builder 入口

从 `task_graph.json` 的 O1-O6 执行：

- O1: Deep Writer proof policy
- O2: Chapter Verifier
- O3: Repair Loop
- O4: Quality Score
- O5: Status / Pane Surface
- O6: Regression / handoff / eval

## 必须保持的安全约束

- 不允许用 Codex/direct GPT/local Qwen 替代最终 Planner、Chapter Writer 或 Deep Writer。
- 不允许普通 ChatGPT 输出冒充 Deep Research proof。
- 缺 proof、缺 evidence、unsupported claim、内部字段泄漏必须暴露为 `warn/error`。
- C/D 质量等级不能公开发布。
- S04 完成后只能解锁 S05 verification-release，不能声称父 Epic 完成。

## 推荐验证

```bash
python3 -m py_compile harness/scripts/tech_hotspot_radar.py harness/tools/report_ir.py harness/tools/report_evidence.py harness/tools/report_synthesis.py
python3 -m pytest -q harness/tests/test_report_pipeline.py
python3 -m pytest -q harness/tests/test_report_deep_verifier_repair.py
python3 -m pytest -q harness/tests/test_ai_influence_youtube_report_status_surface.py
```

## 未闭环项

- S04 尚未实现 builder 代码。
- S04 尚未产生 eval sidecar。
- S05 verification-release 仍处于 drafting/spec。
