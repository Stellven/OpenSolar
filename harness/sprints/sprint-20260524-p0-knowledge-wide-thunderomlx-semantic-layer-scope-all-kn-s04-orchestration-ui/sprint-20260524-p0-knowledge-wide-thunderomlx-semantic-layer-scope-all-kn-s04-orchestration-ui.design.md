# Design — S04 Orchestration, Automation & Visualization

> **Sprint**: `sprint-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn-s04-orchestration-ui`
> **Epic**: `epic-20260524-p0-knowledge-wide-thunderomlx-semantic-layer-scope-all-kn`
> **Slice**: `orchestration-ui` (builder sprint)
> **Knowledge Context: solar-harness context inject used**
> **Harness Modules Used: harness-knowledge, harness-graph**

## 0. Slice Posture

本切片是 **builder sprint**：把 S02/S03 交付的核心能力接入 autopilot 调度、实现 A5 GroundingHook、构建 dashboard UI、以及 status server 的可视化增强。

## 1. Upstream Dependencies

| 来源 | 消费内容 |
|---|---|
| S02 design §A5 | GroundingHook 接口契约 (input/output/fallback) |
| S02 design §3.1 | 6 层系统架构 (Layer 5-6 是本 sprint scope) |
| S01 outcomes O3/O10/O12 | 本 sprint 的 3 个主要 outcomes |
| S01 handoff U3/U8/U9 | GroundingHook (U3), Tech Hotspot (U8), Dashboard (U9) |
| S03 core-runtime | schema v2 + 新 adapters + 新状态 (S04 依赖 S03 产出) |

## 2. Implementation Scope

### C1: GroundingHook Implementation (A5 → O10, U3)

**改什么**: 新建 `lib/knowledge_grounding_hook.py`，修改 `lib/solar-knowledge-context.py`

**GroundingHook 实现**:

```python
class GroundingHook:
    def __init__(self, db_path: Path, timeout_s: float = 2.0):
        self.db_path = db_path
        self.timeout_s = timeout_s

    def ground(self, query: str, extracted_hits: list[dict]) -> list[dict]:
        """Resolve extracted hits to raw/vault evidence spans."""
        grounded = []
        for hit in extracted_hits:
            doc_id = hit["doc_id"]
            candidate = self._load_candidate(hit["candidate_json_path"])
            for claim in candidate.get("core_facts", []):
                spans = self._resolve_spans(claim.get("evidence", []))
                if not spans:
                    # no span → confidence=0.5, semantic only
                    grounded.append({
                        "claim_text": claim["text"],
                        "evidence_spans": [],
                        "confidence": 0.5,
                        "source_layer": "semantic"
                    })
                else:
                    # resolved → raw/vault grounding
                    grounded.append({
                        "claim_text": claim["text"],
                        "evidence_spans": spans,
                        "confidence": 0.9,
                        "source_layer": "raw"
                    })
        return grounded

    def _resolve_spans(self, span_ids: list[str]) -> list[dict]:
        """Look up spans in registry; drop missing ones with warning."""
        ...

    def _load_candidate(self, path: str) -> dict:
        """Load candidate JSON with timeout."""
        ...
```

**集成点**:
1. `solar-knowledge-context.py`: 在 context inject 路径中，当 extracted hits 存在时调用 `GroundingHook.ground()`, 用 grounded context 替代 raw extracted text
2. 超时 2s → fallback 到 raw/vault only
3. 只读操作，不修改 registry

**测试**: 给定 mock extracted_hits + spans → 验证 grounding 输出格式正确

### C2: Dashboard CLI & Status Server (O12, U9)

**改什么**: 新建 `lib/knowledge_dashboard.py`，增强 `knowledge_ingest_health.py`

**Dashboard CLI 命令**:

```bash
solar-harness wiki knowledge-ingest dashboard --json
```

**输出格式**:
```json
{
  "watermarks": {
    "raw": {"last_indexed_ts": "...", "pending": 0, "failed": 0},
    "vault": {"last_indexed_ts": "...", "pending": 0, "failed": 0},
    "semantic": {"last_indexed_ts": "...", "pending": 0, "failed": 0}
  },
  "state_counts": {
    "NEW": 0, "SOURCE_CAPTURED": 5, "RAW_MATERIALIZED": 10,
    "EXTRACT_ELIGIBLE": 3, "THUNDEROMLX_EXTRACT_RUNNING": 1,
    "EXTRACT_FAILED_RETRYABLE": 0, "DONE_RAW_ONLY_WARN": 2,
    "EXTRACTED_VALIDATED": 15, "QUARANTINED": 0, "DONE": 20
  },
  "source_coverage": {
    "obsidian_vault": 12, "raw_chatgpt": 8, "raw_web": 5,
    "youtube_transcript": 3, "github_trends": 2, "pdf_manual": 1,
    "accepted_sprint": 4, "solar_artifact": 6
  },
  "circuit_breaker": {"paused": false, "fail_rate": 0.05, "consecutive": 0},
  "extract_metrics": {
    "avg_latency_ms": 3200, "validation_pass_rate": 0.92
  }
}
```

**Status Server 端点** (如果 status server 已存在则扩展，否则新建简单 HTTP):
- `GET /api/knowledge/dashboard` → 返回上述 JSON
- `GET /api/knowledge/watermarks` → 三层水位
- `GET /api/knowledge/coverage` → source_kind 覆盖率

**HTML Dashboard**: 渲染一个简单 HTML 页面 `knowledge-dashboard.html`，用纯 HTML+CSS（无 JS framework），显示上述数据。通过 `solar-harness wiki knowledge-ingest dashboard --html` 输出。

### C3: Tech Hotspot Report Semantic Preference (U8)

**改什么**: 检查 Tech Hotspot report reader 逻辑，优先读取 `*.semantic.md`，fallback 到 transcript/raw。

**实施**:
1. 在 report reader 中，对每个 source path 先检查 `{path}.semantic.md` 是否存在
2. 存在 → 读取 semantic.md 的 summary + core_facts
3. 不存在 → fallback 到原始 transcript/raw
4. 通过 GroundingHook 回源 raw/vault 做 grounding

### C4: Coverage Report CLI (O11 supplement)

**改什么**: 新增 CLI 命令 `coverage-report`

```bash
solar-harness wiki knowledge-ingest coverage-report --json
```

输出 8 类 source_kind 的 document count + per-state breakdown，标记哪些 source_kind 未达 20 样本。

### C5: Autopilot Integration

**改什么**: 把 knowledge ingest dispatcher 的状态接入 autopilot 调度

**实施**:
1. autopilot 的 periodic scan 增加对 knowledge ingest 的检查
2. 检查项目: circuit breaker 是否 paused, EXTRACT_FAILED_RETRYABLE 是否堆积, DONE_RAW_ONLY_WARN 是否异常增长
3. 异常 → 生成 health event 写入 sprint events.jsonl
4. 不自动修复，只告警

### C6: Verification

**执行**:
1. `solar-harness wiki knowledge-ingest dashboard --json` → exit 0, 输出合法 JSON
2. `solar-harness wiki knowledge-ingest dashboard --html` → 生成 HTML 文件
3. `solar-harness wiki knowledge-ingest coverage-report --json` → exit 0
4. GroundingHook unit test pass
5. 旧命令无回归

## 3. Write Scope

| Node | 文件 |
|---|---|
| C1 | `lib/knowledge_grounding_hook.py` (new), `lib/solar-knowledge-context.py` (extend) |
| C2 | `lib/knowledge_dashboard.py` (new), `lib/knowledge_ingest_health.py` (extend), `lib/knowledge_ingest_dispatcher.py` (new CLI commands) |
| C3 | Tech Hotspot report reader (extend) |
| C4 | `lib/knowledge_ingest_dispatcher.py` (new command) |
| C5 | autopilot 配置/脚本 (extend) |
| C6 | 无写 (verification only) |

## 4. Parallelization

C1 (grounding) 和 C2 (dashboard) 可并行 (write_scope 不冲突)。
C3 依赖 C1 (grounding hook)。
C4 和 C5 可并行。
C6 依赖全部。

## 5. Testing Strategy

- C1: GroundingHook unit test (mock registry data → verify output format)
- C2: dashboard --json 输出 JSON schema 验证; --html 输出文件存在
- C3: report reader smoke test
- C4: coverage-report 命令 exit 0
- C5: autopilot scan 不报错

## 6. Risks

| Risk | Mitigation |
|---|---|
| solar-knowledge-context.py 改动影响 context inject | 只 extend，不改现有路径；GroundingHook 作为可选增强 |
| Dashboard HTML 过于简陋 | 接受 MVP: 数据完整 > 美观 |
| GroundingHook 超时影响查询延迟 | 2s timeout + async fallback |
| Status server 可能不存在 | 先做 CLI-only dashboard; HTTP endpoint 作为 optional |

## 7. Stop Rules

- GroundingHook 无 input/output/fallback 实现 → C1 不算 done
- dashboard --json 不输出合法 JSON → C2 不算 done
- 旧命令回归 → C6 不算 done
- 缺 task_graph.json → 不派 builder
