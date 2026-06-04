# Design — TH Social Browser Backend for X S02 Architecture

epic_id: `epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控`
sprint_id: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s02-architecture`
slice: `architecture`
role: planner
status: planning_complete
generated_at: 2026-05-28T18:18:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
upstream: S01 (4 N-nodes, 10 outcomes O1-O10 from 10 AC) — active/builder_parallel
hard_dependency_blocker: `sprint-20260525-browser-agent-global-operator-cutover` (本 epic 任何实施 sprint 不得启动直到该上游 PASS)
downstream: S03 core-runtime (本 sprint passed 后启动, 但 S03 实施仍受 hard_blocker 阻塞)

## 0. 切片定位

S01 把 PRD 10 AC 拆为 10 outcome (O1-O10) 跨 N1-N4。S02 在 S01 基础上产出**架构设计**: control plane / data plane / 接口契约 / 数据模型 / 兼容迁移策略。本 sprint 仍是**规约层**, 不实施代码, 不真跑 browser agent (上游 hard_blocker 未 PASS)。

**与其他 epic S02 同款 A1-A5 5-node 模式**:
- A1 critical (control plane + data plane + 7 interface) — sonnet
- A4 OQ resolutions (open question 决议表) — sonnet, 与 A1 并行
- A2 data model (extended schema + dedup) — glm-5.1, depends A1
- A3 compat & migration plan — glm-5.1, depends A1
- A5 join (traceability + handoff) — sonnet, depends A1-A4

## 1. S01 outcome 消费 → S02 architecture 决议

| S01 outcome | 来自 PRD | S02 决议项 (映射到 A1/A2/A3) |
|-------------|---------|------------------------------|
| O1 Backend order (browser > rss > manual > x_api optional) | AC-1, AC-3 | A1 control plane "BackendSelector" + 4-tier fallback chain |
| O2 Browser physical operator 6 capabilities | AC-2 | A1 interface "BrowserLeaseClient" + 6-method API |
| O3 Rate limiting 5 子项 (per-account cooldown / global concurrency=1 / jittered / exp backoff / tier1/tier2) | AC-5 | A1 control plane "RateLimiter" + 5-knob spec |
| O4 Post extraction 11 字段 + raw DOM hash + screenshot fallback | AC-2 | A2 data model: post_record schema (11 fields + DOM hash + collection_backend) |
| O5 Dedup (canonical URL or sha256 fallback) | AC-4 | A2 data model: dedup_key generator + uniqueness check |
| O6 Downstream integration (social_posts → 10-step chain) | AC-6/7/8 | A1 data plane: 10-step pipeline + 3 ledger writes |
| O7 CLI (collect-social --backend browser/auto --limit-accounts N) | AC-2 | A1 interface "CLI subcommand" + arg/exit-code spec |
| O8 WebUI/Status (7 indicators) | (隐含) | A1 interface "StatusSurface" + 7 indicator schema |
| O9 Hard blocker enforcement | AC-1 | A3 migration: blocker check at sprint dispatch + bypass guard |
| O10 Non-goals aggregate (10 条 含不全网爬虫 / 不绕风控 / 不重复实例) | AC-9, AC-10 | A5 join: non-goals re-asserted in traceability |

## 2. 5-Node DAG (S02 同款 A1-A5)

```
                  ┌─→ A1 control_plane_data_plane_interfaces (sonnet, 关键路径)
   (上游 S01 ok) ─┤                                    │
                  │                                    ├─→ A2 data_model_schema (glm-5.1) ─┐
                  │                                    └─→ A3 compat_migration (glm-5.1) ──┼─→ A5 traceability_handoff (sonnet, join)
                  └─→ A4 oq_resolutions (sonnet, parallel) ────────────────────────────────┘
```

**Wave 1 (2 并行 write_scope 互斥)**: A1 + A4
**Wave 2 (2 并行)**: A2 + A3 (both depends A1)
**Wave 3 (join)**: A5 (depends A1+A2+A3+A4)

## 3. A1-A5 内容大纲

### A1 control_plane_data_plane_interfaces.md (critical)

#### §1 Control Plane
- **BackendSelector**: 4-tier fallback chain `browser_agent → rss_public → manual_curated → x_api_optional`; selector 决策签名 `pick_backend(accounts, ctx) → (backend_id, reason)`; 上游 hard_blocker 未 PASS → 强制 fallback 到 rss/manual + 显式 warn
- **RateLimiter** (per O3 5 子项):
  - per_account_cooldown_seconds: tier1=180, tier2=600
  - global_concurrency: 1 (硬性)
  - jitter_range_seconds: ±5..15
  - exponential_backoff: base=2, max=300s, on (login_fail/rate_429/parse_fail)
  - tier_frequency_separation: tier1 (P0 大咖) 每 6h, tier2 每 24h
- **OperatorLeaseManager**: 申请/释放 Browser lease via `solar.physical_operator.browser.lease(...)`; 上游 hard_blocker 未 PASS → manager 立即 raise `OperatorNotReady`

#### §2 Data Plane (10-step pipeline per O6)
```
collect-social
  → BackendSelector.pick
  → BrowserLeaseClient.acquire → 6 ops → DOM extract → release
  → PostExtractor (11 fields per O4)
  → DedupQueue (24h, key per O5)
  → social_posts.insert
  → metrics_snapshots.write
  → ThunderOMLX semantic extract (复用现有 instance, **不新起**)
  → social_links + big_name_viewpoints + propagation_chains
  → GitHub/YouTube/paper dispatch
  → Knowledge/_raw/social/<ts>/
  → AI Influence social trend report
  → model_call_ledger (3 writes: lease cost + extract cost + premium reasoning if applicable)
```

#### §3 Interfaces (7 contract per O7+O8+O2)
1. **BrowserLeaseClient API** (6 methods: open/wait/scroll/dom_extract/screenshot/release) — per O2
2. **PostExtractor API** (input: DOM tree, output: post_record 11 字段) — per O4
3. **BackendSelector API** — per O1
4. **RateLimiter API** — per O3
5. **CLI subcommand spec** — `collect-social --backend {browser|rss|manual|x_api|auto} --limit-accounts N`; exit codes 0/1/2/3 — per O7
6. **StatusSurface schema** — 7 indicators (total/enabled/scanned_today/browser_ready/scan_state/parse_fail/fallback_count/by_backend_count) — per O8
7. **HardBlockerGuard** — sprint dispatch 前必须 check `browser-agent-global-operator-cutover:passed`, 否则 raise `BlockerNotResolved` — per O9

#### §4 Failure recovery & observability
- per-account isolation (per AC-5): 失败仅影响自身, batch 继续
- 5 failure modes: lease_fail / login_required / parse_fail / rate_429 / dom_change
- screenshot fallback path: `~/.solar/screenshots/<sprint_id>/<handle>-<ts>.png`
- log redaction: 严禁打印 cookie / token / session

#### §5 Acceptance (≥6)
- 4-tier fallback chain 锁定 + selector 签名
- RateLimiter 5 子项参数表
- 10-step data plane 完整
- 7 interface 全部签名 + acceptance
- 5 failure mode + observation hook
- HardBlockerGuard 强制 check 显式定义

### A4 oq_resolutions.md (parallel)
- **OQ-01** Browser Agent lease 申请失败时是否允许 selector 升级到 rss? → 决议: yes, **per O9 hard_blocker_未_pass 时强制走 rss/manual**; 但若仅暂时 quota 满, 等 5min retry, 不立即降级
- **OQ-02** ThunderOMLX semantic extract 是否复用现有 instance? → **复用** (per AC-10 not start additional instance); 通过 `~/.thunderomlx/socket` 共享
- **OQ-03** premium reasoning (ChatGPT 5.5 Thinking) 触发条件? → 与 paper/YouTube epic 一致: tier1 P0 大咖 + 高 entity recall 才触发 (复用 HF Paper Insight S02 OQ-03 路由)
- **OQ-04** dedup key 冲突处理? → canonical URL 优先, fallback 才走 sha256; 若 URL 不一致但 sha256 同 → 视为同 post (按 sha256 dedup), URL 取 latest
- **OQ-05** Knowledge ingest 写入顺序? → 复用 HF Paper Insight S02 OQ-05: raw 同步写入, extracted/QMD/graph 异步并行
- **OQ-06** rate_429 时 backoff 是否 per-account 或 global? → **per-account** (per AC-5 失败仅影响自身)
- **OQ-07** screenshot fallback path 是否进 Knowledge raw? → **是**, 但只存 path + DOM hash, 不存 image binary (节省 vault 体积)

#### A4 Acceptance (≥6)
- 7 OQ 全部决议表 (含 yes/no + 理由 + 引用 PRD §/AC)
- 任一未决 OQ 必须显式 `defer_to: S0X` 而非空缺
- 与 HF Paper Insight + YouTube epic 同款决议 (OQ-02/OQ-03/OQ-05) 显式 cross-reference

### A2 data_model_schema.md (depends A1)
- **post_record schema** (11 字段 per O4): post_id / author_handle / text / created_at / post_url / metrics_{reply,repost,like,view} / urls / dom_hash / screenshot_path / collection_backend
- **dedup_key generator** (per O5): canonical URL or sha256; key 写入新表 `social_post_dedup_keys (key TEXT PRIMARY KEY, first_seen_at, last_seen_at, post_pk INT FK)`
- **collection_backend enum**: browser_agent / rss_public / manual_curated / x_api
- **DDL diff** vs 现有 social_posts: 新增 `dom_hash TEXT`, `screenshot_path TEXT`, `collection_backend TEXT NOT NULL`, `dedup_key TEXT REFERENCES social_post_dedup_keys`
- **migration safe**: ADD COLUMN with default NULL, 兼容旧 X API token 数据
- **acceptance ≥4**: 11 字段表 + dedup_key 生成函数 + DDL diff + migration safe

### A3 compat_migration.md (depends A1)
- **legacy X API token path 保留**: 仅 optional, 不绕 selector; 若 user 显式 enable 且 token 存在则可用
- **migration 3 phase**:
  - Phase 1: 双写 (X API + browser agent 并行采集, 比对 dedup)
  - Phase 2: browser agent 优先 + X API fallback (仅 token 存在时)
  - Phase 3: X API deprecated, 仅 advanced user opt-in
- **rollback env**: `SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE=1` 回到 X API 唯一 backend
- **依赖 / 降级 / 冲突清单** (per contract Acceptance "列出冲突、依赖和降级策略"):
  - 依赖: browser-agent-global-operator-cutover (hard_blocker)
  - 依赖: ThunderOMLX 现有 instance (不新起)
  - 降级 1: browser lease 暂时 unavail → rss
  - 降级 2: rss 不可用 → manual curated import
  - 降级 3: ThunderOMLX socket 不可用 → 跳过 semantic extract, 仅 raw 入 vault
  - 冲突: 与 X API 老路径 dedup (per O5 sha256 兜底解决)
- **acceptance ≥5**: 3 phase + rollback flag + 3 降级路径 + 1 冲突 + 老 X API token 显式保留路径

### A5 traceability_handoff.md (join)
- traceability.json 12 字段 (sprint/epic/gate/REQ→outcome→node 完整映射)
- handoff 含 A1-A4 摘要 + S03 启动包 (但 S03 实施仍受 hard_blocker 阻塞)
- **non-goals 10 条 显式复述** (per O10): 不全网爬虫 / 不绕风控 / 不绕登录 / 不把 X API 默认 / 不实施 browser operator 本身 (仅消费) / 不新起第二套 browser system / 不新起 ThunderOMLX / 不主动 close epic / 不绕 planner 直派 builder / 不用乐观词
- **hard_blocker 显式传递**: `s03_blocked_until: sprint-20260525-browser-agent-global-operator-cutover:passed`
- acceptance ≥5: traceability 12 字段 + S03 启动包 + non-goals 10 条 + hard_blocker 字段 + 不主动 close

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| A1 | sonnet | control plane + 7 interface + failure recovery 需 reasoning |
| A4 | sonnet | 7 OQ 决议含 cross-epic reference |
| A2 | glm-5.1 | schema/DDL 模板化 |
| A3 | glm-5.1 | migration phase 表填空 |
| A5 | sonnet | join + traceability 12 字段 + non-goals 复述需 reasoning |

## 5. Stop Rules

- 不实施代码 (S02 是规约层)
- 不真跑 browser agent (上游 hard_blocker 未 PASS)
- 不真调 X API (本 sprint 是规约)
- 不绕过 X 风控 / 登录限制
- 不启动第二套 Browser/DeepResearch 系统 (复用 Solar 全局 browser operator)
- 不启动额外 ThunderOMLX 实例 (per AC-10)
- 不打印 cookie / token / session
- 不主动 close 父 epic
- 不用乐观词
- **Hard blocker**: S03 实施 sprint 必须等 `sprint-20260525-browser-agent-global-operator-cutover` PASS

## 6. Knowledge Context

S01 4-node design + plan + task_graph + planning.html + PRD 7-section + contract = self-contained。mirage degraded → QMD + Obsidian + Solar DB fallback。
