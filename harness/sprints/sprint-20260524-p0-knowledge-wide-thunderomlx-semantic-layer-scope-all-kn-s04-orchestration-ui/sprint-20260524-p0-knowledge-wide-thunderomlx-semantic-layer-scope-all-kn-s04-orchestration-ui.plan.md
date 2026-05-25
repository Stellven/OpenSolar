# Plan — S04 Orchestration, Automation & Visualization

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s04-orchestration-ui`
> **Slice**: `orchestration-ui` (builder sprint)

## Goal

实现 A5 GroundingHook、dashboard CLI/UI、Tech Hotspot semantic preference、coverage report、autopilot 集成。

## Parallelization

```text
C1 (grounding hook) ──► C3 (tech hotspot)
C2 (dashboard) ──────► C6 (verification)
C4 (coverage report) ─► C6
C5 (autopilot) ──────► C6
```

C1, C2, C4, C5 可并行。C3 依赖 C1。C6 依赖全部。

## Execution Plan

### C1: GroundingHook (O10, A5)
- 新建 `lib/knowledge_grounding_hook.py`
- 集成到 `lib/solar-knowledge-context.py`
- **verify**: unit test pass

### C2: Dashboard CLI & UI (O12)
- 新建 `lib/knowledge_dashboard.py`
- 新 CLI: `dashboard --json`, `dashboard --html`
- 新 HTTP: `/api/knowledge/dashboard` (optional)
- **verify**: `dashboard --json` exits 0

### C3: Tech Hotspot Semantic Preference (U8)
- 修改 report reader 优先读 `*.semantic.md`
- **verify**: report 读取 semantic 优先

### C4: Coverage Report (O11)
- 新 CLI: `coverage-report --json`
- **verify**: exits 0, 8 source_kind 全列

### C5: Autopilot Integration
- 把 knowledge health 检查接入 autopilot scan
- **verify**: scan 运行无报错

### C6: Verification
- 全部命令 exit 0
- 旧命令无回归
- **verify**: complete pass

## Verification Commands

```bash
# C1
python3 -c "from knowledge_grounding_hook import GroundingHook; print('OK')"

# C2
solar-harness wiki knowledge-ingest dashboard --json
solar-harness wiki knowledge-ingest dashboard --html

# C3
# (需要实际 report reader 测试)

# C4
solar-harness wiki knowledge-ingest coverage-report --json

# C5
solar-harness wiki knowledge-ingest status --json

# C6 — regression
solar-harness wiki knowledge-ingest status --json
solar-harness wiki knowledge-ingest qmd-watermarks --json
solar-harness wiki knowledge-ingest circuit-breaker status --json
```
