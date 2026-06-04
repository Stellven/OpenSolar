# solar-harness Handoff — GitHub Hotspot Radar / Code Signal Plane Convergence

## Goal

把现有两条 GitHub 线正式收口成唯一主线，并产出后续 builder 可直接执行的统一设计、切片和迁移图。

## Read First

- `/Users/lisihao/Solar/harness/docs/architecture/github-hotspot-radar-code-signal-plane.adr.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260527-github-hotspot-radar-code-signal-plane-convergence.prd.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260527-github-hotspot-radar-code-signal-plane-convergence.contract.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture.prd.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260525-p0-ai-influence-github-trend-action-analyzer-ultimate-s01-requirements.prd.md`

## Planner Deliverables

1. 统一主线 design
2. 6 个 MVP operator 的 builder slice plan
3. 现有两条线迁移 DAG
4. 与 HF / Social Signal Plane 的共振 contract

## Mandatory Migration DAG

```text
Project Intelligence Upgrade
  -> Discovery / Enrichment / Scoring baseline / Report baseline

Trend & Action Analyzer Ultimate
  -> Actionability logic / packet compiler / intervention outputs

Unified GitHub Hotspot Radar
  -> single naming
  -> single object model
  -> single output asset contract
```

## Constraints

- 不允许新建第三条 GitHub 主线
- 不允许继续并行维护两套 schema / 两套 output assets
- 高模型输入必须经 `GitHubEvidencePacketCompiler`

## Acceptance

- design 明确统一 Epic 名
- plan 明确 6 个 builder slices
- migration DAG 可执行
- resonance contract 明确
