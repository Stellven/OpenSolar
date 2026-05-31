# Design — TH Social Browser Backend for X S03 Core-Runtime

epic_id: `epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控`
sprint_id: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s03-core-runtime`
slice: `core-runtime`
role: planner
status: planning_complete
generated_at: 2026-05-29T02:00:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
upstream: S01 (4 N-nodes, O1-O10 outcomes) + S02 (5 A-nodes, control plane + data plane + 7 interfaces + 5 OQ resolutions + data model + compat migration)
hard_dependency_blocker: `sprint-20260525-browser-agent-global-operator-cutover` — **本 S03 实施允许进行, 但真 lease 调用必须 mock 直到上游 PASS**
downstream: S04 orchestration-ui + S05 verification-release (S05 真 e2e 需 hard_blocker PASS)

## 0. 切片定位 — 实施层带 mock-mode

S03 是 epic **核心实施 sprint**, 把 S02 architecture 7 interface + data model + control/data plane 落地为可运行 Python 子包 `lib/social_browser_backend_x/`。

**关键决策 — mock-mode policy**: 因 hard_blocker (browser-agent-global-operator-cutover) 未 PASS, S03 必须采用**两阶段实施**:
- **阶段 A (本 sprint 范围)**: 实现全部代码 + 真单测 + mock browser_agent 集成测试; `HardBlockerGuard` 在运行时检测 lease 不可用 → 自动走 mock 返回固定 DOM fixture
- **阶段 B (S05 verification)**: hard_blocker PASS 后, 切换 `BROWSER_AGENT_MOCK_MODE=0`, V1 真 e2e 跑

mock-mode 让 S03 能 PASS 而不绕开 hard_blocker; S03 之后 epic 实际进展由 hard_blocker 决定。

**复用 GHPI S03 / HF Paper S03 / YouTube S03 同款 6-node C1-C6 phase pattern**:
- C1 schema + persistence (no_code=false)
- C2 BrowserLeaseClient + RateLimiter + OperatorLeaseManager (mock fixture path)
- C3 PostExtractor + DedupQueue
- C4 BackendSelector + 10-step pipeline + HardBlockerGuard
- C5 CLI + StatusSurface
- C6 tests + integration

## 1. S02 决议消费 → S03 实施单元

| S02 节点 | S02 产出 | S03 落地节点 |
|----------|----------|--------------|
| A1 control+data+interface | 7 interface 签名 (BrowserLeaseClient/PostExtractor/BackendSelector/RateLimiter/CLI/StatusSurface/HardBlockerGuard) + 10-step pipeline + 5 failure mode | C2 (lease+ratelimit) + C3 (extract+dedup) + C4 (selector+pipeline+guard) + C5 (CLI+status) |
| A2 data model | 11 字段 schema + dedup_key generator + DDL diff + migration safe | C1 (schema+persistence) + C3 (DedupQueue) |
| A3 compat migration | 3-phase + rollback env + 3 degradation | C1 (schema migration safe) + C4 (selector 4-tier fallback) |
| A4 7 OQ | OQ-01..07 决议 | 全部分布到 C2/C3/C4 (e.g., OQ-02 ThunderOMLX reuse 落地 C4; OQ-04 dedup conflict 落地 C3) |
| A5 traceability | 12 字段 + non-goals 10 条 | C6 (handoff 复述 + integration) |

## 2. 6-Node DAG (S03 同款 phase-based)

```
C1 schema_persistence (sonnet, foundation)
   ├─→ C2 browser_lease_client_ratelimiter (sonnet, 真 interface + mock fixture)
   ├─→ C3 post_extractor_dedup (glm-5.1)
   └─→ C5 cli_status_surface (glm-5.1)
         (C2 + C3 + C5 完成后)
                  └─→ C4 backend_selector_pipeline_guard (sonnet, 集成 lease+extract+dedup+CLI)
                            └─→ C6 tests_integration (sonnet, 单测 + mock 集成测 + hard_blocker mode)
```

**Wave 1**: C1 (foundation, no deps)
**Wave 2 (3 并行)**: C2 + C3 + C5 (all depends C1, write_scope 互斥)
**Wave 3**: C4 (depends C2+C3+C5; 集成 lease+extract+selector+CLI 到 10-step pipeline)
**Wave 4 (join)**: C6 (depends C4; tests + integration + handoff)

## 3. C1-C6 内容大纲

### C1 schema_persistence (foundation)
- 子包初始化: `harness/lib/social_browser_backend_x/__init__.py`
- `schema.py`: 11-field post_record dataclass + DDL (SQLite) per A2; ADD COLUMN migration safe vs existing `social_posts`
- `dedup_keys_table.py`: 新表 `social_post_dedup_keys` (key PRIMARY KEY + first/last_seen_at + post_pk FK)
- `migrations/001_add_browser_backend_columns.sql`: ADD COLUMN dom_hash/screenshot_path/collection_backend NOT NULL DEFAULT 'unknown'/dedup_key
- 单测: schema round-trip + DDL idempotent + migration safety (legacy X API row 不破坏)
- 验收 ≥5

### C2 browser_lease_client_ratelimiter (真 interface + mock fixture)
- `browser_lease_client.py`: 实现 BrowserLeaseClient 6 method (open/wait/scroll/dom_extract/screenshot/release), 通过 `solar.physical_operator.browser.lease(...)` 调用
- `mock_browser_fixture.py`: 当 `BROWSER_AGENT_MOCK_MODE=1` (or HardBlockerGuard 检测 lease 不可用), 返回固定 DOM fixture (3 个真 X profile HTML 样本)
- `ratelimiter.py`: 实现 5 knob (per_account_cooldown tier1=180/tier2=600 + global_concurrency=1 + jitter ±5..15s + exp_backoff base=2/max=300 + tier1_freq=6h/tier2_freq=24h)
- `operator_lease_manager.py`: 实现 lease 申请/释放 + 失败 raise `OperatorNotReady`; mock-mode 自动转 `MockLease`
- 单测: 6 method signature + 5 knob 边界 + lease retry + mock fallback
- 验收 ≥6

### C3 post_extractor_dedup
- `post_extractor.py`: DOM tree → 11-field post_record per A2 (post_id/handle/text/created_at/url/metrics_{reply,repost,like,view}/urls/dom_hash/screenshot_path/collection_backend='browser_agent')
- `dedup_queue.py`: 24h dedup window, canonical URL 优先 + sha256(handle+text+time) fallback per OQ-04
- 单测: 11 字段覆盖 + 缺字段 N/A 占位 + dedup canonical 优先 + sha256 fallback + URL 冲突 sha256 wins
- 验收 ≥5

### C5 cli_status_surface
- `cli.py`: `collect-social --backend {browser|rss|manual|x_api|auto} --limit-accounts N` + exit codes 0/1/2/3 per O7
- `status_surface.py`: 7 indicator (total/enabled/scanned_today/browser_ready/scan_state/parse_fail/fallback_count/by_backend_count) per O8
- 单测: CLI arg parse + exit code + status surface JSON output
- 验收 ≥4

### C4 backend_selector_pipeline_guard (集成关键路径)
- `backend_selector.py`: 4-tier fallback (browser_agent > rss_public > manual_curated > x_api_optional) per O1; hard_blocker 未 PASS → 自动 fallback rss/manual
- `pipeline.py`: 10-step end-to-end orchestration per O6 (collect-social → selector → lease 6 ops → extract → dedup → social_posts → metrics → ThunderOMLX semantic (reuse, **不新起 instance** per AC-10 + OQ-02) → social_links + viewpoints + propagation → dispatch → Knowledge raw → AI Influence report → model_call_ledger)
- `hard_blocker_guard.py`: 实现 `check_blocker(sprint_id='browser-agent-global-operator-cutover') → bool`; sprint dispatch 时 mandatory check; mock-mode 时返回 mock_ready=True; 真模式时若未 PASS raise `BlockerNotResolved`
- 单测: selector 4-tier + 10-step 全链路 mock + HardBlockerGuard 两态
- 验收 ≥6

### C6 tests_integration (join)
- `tests/test_social_browser_backend_x.py`: 跨 C1-C5 pytest 集成 (覆盖 11 字段 / 5 RateLimiter knob / 5 failure mode / 3 gate fallback)
- `tests/test_pipeline_mock.py`: 10-step pipeline mock 集成测 (BROWSER_AGENT_MOCK_MODE=1)
- `tests/test_hard_blocker_guard.py`: HardBlockerGuard 两态 (mock + real fail)
- secret scan: 全 src+test grep 0 cookie/token/session/auth header
- handoff.md: C1-C5 evidence 汇总 + S04 启动包 (Dashboard/CLI/Config 复用 S04 spec) + S05 启动包 (V2 真 e2e 需 hard_blocker PASS)
- eval.{md,json}: 整 sprint verdict + 显式 mock_mode caveat
- 验收 ≥5

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| C1 | sonnet | schema + DDL + migration safety 需 reasoning |
| C2 | sonnet | lease + ratelimit + mock fixture 需 reasoning |
| C3 | glm-5.1 | extract + dedup 相对模板化 |
| C5 | glm-5.1 | CLI + status surface 模板化 |
| C4 | sonnet | 10-step pipeline 集成 + HardBlockerGuard 关键路径 |
| C6 | sonnet | join + 集成测 + handoff |

## 5. Stop Rules

- 不真跑 browser_agent (hard_blocker 未 PASS, mock-mode 强制)
- 不绕过 HardBlockerGuard (任何 production code 必须经过 guard 检查)
- 不真调 X API (本 sprint 是 mock-mode 实施, X API 路径仅 optional 保留)
- 不绕 X 风控 / 登录限制
- 不启动第二套 Browser/DeepResearch 系统
- 不启动额外 ThunderOMLX 实例 (per AC-10 + OQ-02)
- 不打印 cookie / token / session / auth header
- 不主动 close 父 epic
- 不绕 planner 直派 builder (已在 planner)
- 不修改 `lib/social/`, `lib/scheduler/` 等其他已有子包 (write_scope 严格限于 `lib/social_browser_backend_x/`)
- 不用乐观词

## 6. 与 GHPI S03 / HF Paper S03 / YouTube S03 复用

- pattern 完全复用 (6 C-node phase-based + foundation + parallel + integration + tests join)
- HardBlockerGuard 模式新增 (其他 epic S03 无此约束); 可被未来其他 hard-blocked sprint 复用
- mock fixture 文件可被未来 X scraper 测试复用

## 7. 给下游 S04 / S05

- **S04 启动包**: 复用 S04 同款 C1-C4 (Dashboard 7 cards / CLI 命令树 / Config YAML / High Model E2E plan) 模式, 本 epic 特化为 X 大咖监控 dashboard
- **S05 启动包**: V1-V6 verification 同款; **V1 真 e2e 必须等 hard_blocker PASS, 否则 mock-mode 验证**; V2 high model E2E 不适用 (本 epic 无 ChatGPT 5.5 调用, 仅 ThunderOMLX semantic extract)
- **epic close gate**: 必须 S03 PASS + S04 PASS + S05 PASS + hard_blocker PASS 才能 close

## 8. Knowledge Context

S02 5 A-node design (control+data+7 interface + 5 OQ + data model + compat) + S01 4 N-node (10 outcomes) + PRD 10 AC + contract = self-contained。mirage degraded → QMD/Obsidian/Solar DB fallback。
