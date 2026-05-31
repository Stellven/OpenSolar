# Design — s02-architecture: AI Influence 算子固化架构设计

## 设计目标

为 5 条 AI Influence 主线（9 个 operator 文件）设计统一的注册/路由/产物/展示架构，产出接口契约和兼容迁移方案，供 S03 (core-runtime) 和 S04 (orchestration-ui) 实现。

## 系统分层

```
┌─────────────────────────────────────────────────────────┐
│                   Control Plane                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Operator Registry (operator_registry.json)       │  │
│  │  - 5 lines × {primary, executor[], fallback[]}    │  │
│  │  - role: primary | executor | fallback | control  │  │
│  │  - scheduling: cron / event / manual              │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Router / Dispatcher                              │  │
│  │  - select primary by line                         │  │
│  │  - fallback on primary failure                    │  │
│  │  - enforce: no duplicate final report             │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    Data Plane                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Unified Output Schema                            │  │
│  │  report.md  raw/  metadata.json  log/diagnostic   │  │
│  │  (每条主线必须产出这 4 类产物)                      │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Operator Execution                               │  │
│  │  PRIMARY ──→ final report                         │  │
│  │  EXECUTOR ──→ intermediate data (被 primary 调用)  │  │
│  │  FALLBACK ──→ only on primary failure             │  │
│  │  CONTROL ──→ parallel experiment (GitHub legacy)  │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Presentation Plane                     │
│  ┌───────────────────────────────────────────────────┐  │
│  │  /ai-influence Status Page                        │  │
│  │  6 cards: X | GitHub New | GitHub Legacy |        │  │
│  │           HF Papers | YouTube | Gemini            │  │
│  │  Each card: run_status, artifacts, stats, errors  │  │
│  │  GitHub: side-by-side comparison view             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Operator Registry Schema

```json
{
  "schema_version": "solar.operator_registry.v1",
  "lines": {
    "x_social": {
      "primary": "scripts/ai_influence_daily.py",
      "executors": ["tools/playwright_twitter_scraper.py"],
      "fallback": [],
      "schedule": "daily",
      "output_dir": "reports/x-social/"
    },
    "github_trends": {
      "primary": "scripts/github_trends_pipeline.py",
      "executors": [],
      "fallback": [],
      "control": ["github_intelligence (legacy)"],
      "schedule": "daily",
      "output_dir": "reports/github/",
      "dual_run": { "enabled": true, "comparison_view": true }
    },
    "hf_papers": {
      "primary": "scripts/tech_hotspot_radar.py",
      "executors": [],
      "fallback": [],
      "helper": ["scripts/run_tech_hotspot_radar.sh"],
      "schedule": "daily",
      "output_dir": "reports/hf-papers/"
    },
    "gemini_research": {
      "primary": "tools/gemini_deep_research_operator.py",
      "executors": ["scripts/browser_agent_gemini_deep_research_wrapper.py"],
      "fallback": [],
      "schedule": "on_demand",
      "output_dir": "reports/gemini/"
    },
    "youtube": {
      "primary": "scripts/youtube_influence_digest.py",
      "executors": ["scripts/browser_agent_youtube_transcript_wrapper.py"],
      "fallback": [],
      "schedule": "daily",
      "output_dir": "reports/youtube/"
    }
  }
}
```

## Unified Output Schema

每条主线必须产出的 4 类产物：

| 产物 | 格式 | 说明 |
|------|------|------|
| `report.md` | Markdown | 最终人类可读报告 |
| `raw/` | JSON/CSV | 原始数据、证据原子 |
| `metadata.json` | JSON | 运行状态、时间戳、统计摘要 |
| `diagnostic.log` | text | 运行日志、错误信息 |

`metadata.json` 最小 schema:
```json
{
  "line": "x_social",
  "operator": "ai_influence_daily.py",
  "role": "primary",
  "run_id": "20260530-001",
  "started_at": "ISO8601",
  "finished_at": "ISO8601",
  "status": "success|partial|failed",
  "stats": { "items_processed": 0, "report_sections": 0 },
  "artifacts": ["report.md", "raw/data.json"],
  "errors": []
}
```

## /ai-influence 页面数据模型

6 个 card，每个 card 消费对应 line 的 `metadata.json`:
- `run_status`: 从 metadata.status 读取
- `last_run`: 从 metadata.finished_at 读取
- `artifacts`: 链接到 report.md + raw/
- `stats`: 从 metadata.stats 读取
- `errors`: 从 metadata.errors 读取
- GitHub 特殊: New 和 Legacy 两列并排，diff 视图

## 兼容策略

| 组件 | 策略 | 说明 |
|------|------|------|
| github_intelligence (旧版) | CONTROL 角色保留 | 短期并行对照，7 天后评估退役 |
| playwright_twitter_scraper | EXECUTOR 内化 | 不再暴露为独立入口 |
| browser_agent_*_wrapper | EXECUTOR 内化 | 仅被 primary 内部调用 |
| run_tech_hotspot_radar.sh | HELPER 保留 | 调度辅助，不产出最终报告 |

## 风险矩阵

| 风险 | 等级 | 缓解 |
|------|------|------|
| 旧 operator 接口不一致需适配 | 中 | S03 实现适配层 |
| metadata.json 格式各 operator 差异大 | 中 | 定义最小公共 schema + 渐进适配 |
| GitHub 双跑可能导致资源翻倍 | 低 | 对照期限 7 天，仅报告层双跑 |
| 部分 operator 文件可能已不存在 | 中 | N1 先做文件存在性审计 |
