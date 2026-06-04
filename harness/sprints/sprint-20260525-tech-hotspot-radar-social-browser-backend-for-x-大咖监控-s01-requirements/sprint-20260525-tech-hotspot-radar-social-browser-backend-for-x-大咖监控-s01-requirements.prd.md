# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控`
sprint_id: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements`
slice: `requirements`

## 用户原始需求

# Tech Hotspot Radar: Social Browser Backend for X 大咖监控

## Intent
为 AI Influence Social Signal & Viewpoint Engine 增加 `collect-social --backend browser` 后端，用已开发/待完成的 Browser Agent 全局物理算子替代付费 X API，作为 200 个 X/Twitter 大咖账号的默认低成本采集方式。

## Hard Dependency / Blocker
本单不得立即进入实现，必须等待以下上游完成并验收：

- `sprint-20260525-browser-agent-global-operator-cutover`
- 或等价的 Browser Agent 全局物理算子完成状态：可通过 Solar scheduler / operator runtime 申请 browser lease，并能执行 open / wait / scroll / dom extract / screenshot / close 等物理动作。

在上游未完成前，本单状态应保持 blocked / pending，不派发 Builder 实现。

## Background
X API 读取接口当前存在付费/usage pricing 成本，不适合作为个人本地系统默认采集后端。已有 Tech Hotspot Radar 社交模块具备：

- `social_accounts` 200 个账号 seed
- `social_posts`
- `social_semantic_extracts`
- `social_links`
- `big_name_viewpoints`
- `propagation_chains`
- `model_call_ledger`
- AI Influence 社交趋势报告产物

缺口是：采集后端不应依赖 X API token，应新增 Browser Agent 物理算子后端，并把 X API 降级为 optional backend。

## Required Behavior

### Backend order
默认采集策略改为：

1. `browser_agent_x_profile_scan`
2. `rss_public_fallback`
3. `manual_curated_import`
4. `x_api` optional only when token exists and user explicitly enables

### CLI
在 `scripts/tech_hotspot_radar.py` 中支持：

```bash
solar-harness wiki tech-hotspot-radar collect-social --backend browser --limit-accounts N
solar-harness wiki tech-hotspot-radar collect-social --backend auto
```

`--backend auto` 默认行为：

```text
browser if browser operator ready
else rss fallback
else manual/no-op with clear warning
```

### Browser physical operator contract
不得直接另起一套 Playwright/Chrome 常驻系统。必须通过 Solar Browser Agent 全局物理算子申请 lease。需要使用的能力：

- open URL: `https://x.com/<handle>`
- wait for content / login state
- small controlled scroll
- DOM extraction for visible posts
- screenshot fallback on parse failure
- close/release lease

### Rate limiting
必须实现：

- per-account cooldown
- global concurrency = 1 by default
- jittered delay
- exponential backoff on login/rate/parse failures
- tier1/tier2 scan frequency separation
- no aggressive scraping / no bypass behavior

### Data extraction
每个可见 post 尽量抽取：

- post_id if visible or inferable
- author_handle
- text
- created_at or visible relative time
- post_url
- reply/repost/like/view visible metrics if available, otherwise `N/A`
- urls / github repos / arxiv / youtube links
- raw DOM hash
- screenshot path on fallback
- collection_backend = `browser_agent`

### Deduplication
必须基于以下 key 去重：

- canonical post URL if available
- else `sha256(author_handle + normalized_text + visible_time)`

不得重复进入 `social_posts`、`social_semantic_extracts`、`big_name_viewpoints`。

### Downstream integration
Browser 后端采集的 posts 必须继续进入现有链路：

```text
social_posts
  -> metrics snapshots
  -> local semantic extract via ThunderOMLX/Qwen3.6
  -> social_links
  -> big_name_viewpoints
  -> propagation_chains
  -> GitHub/YouTube/paper dispatch
  -> Knowledge/_raw/social
  -> AI Influence report
  -> model_call_ledger
```

### WebUI / Status
在 Tech Hotspot Radar / Knowledge 页面显示：

- social accounts total / enabled / scanned today
- browser backend ready/not ready
- browser scan pending/running/failed
- last scan time
- parse failure count
- fallback count
- posts collected by backend

## Acceptance Criteria

1. 上游 Browser Agent 全局物理算子未完成时，本单不会启动实现，只记录 blocked reason。
2. Browser operator ready 后，`collect-social --backend browser --limit-accounts 5` 能扫描 5 个账号并写入 posts 或明确 fallback/warn。
3. 不需要 X API token 即可完成 smoke。
4. 同一账号重复扫描不重复写旧 posts。
5. 失败账号只影响自身，不影响整批。
6. social semantic pipeline 能处理 browser 采集的 posts。
7. 采集产物写入 Knowledge raw，并进入知识库抽取队列。
8. model_call_ledger 记录 local semantic extract / premium reasoning 调用。
9. 不启动第二套 Browser/DeepResearch 系统，不新增重复物理算子。
10. 不启动额外 ThunderOMLX 实例。

## Non-goals

- 不做全网 X 搜索爬虫。
- 不做风控绕过。
- 不绕开登录或访问限制。
- 不把 X API 作为默认依赖。
- 不在本单实现 Browser Agent 物理算子本身；只消费上游算子。

## Suggested Sprint Name
`sprint-tech-hotspot-social-browser-backend-after-browser-operator`

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控.epic.md`、`epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.design.md`
- `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.plan.md`
- `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.task_graph.json`
- `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.handoff.md`
- `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.eval.md` 或 `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.eval.json`
