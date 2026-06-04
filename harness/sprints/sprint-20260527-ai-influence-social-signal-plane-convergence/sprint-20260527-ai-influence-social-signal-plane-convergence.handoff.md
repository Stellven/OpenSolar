# solar-harness Handoff — AI Influence Insight / Social Signal Plane Convergence

## Goal

把现有社交/X/YouTube 相关切片正式收口为唯一 Influence Source 主线，并产出可直接派 builder 的统一设计、切片和迁移图。

## Read First

- `/Users/lisihao/Solar/harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260527-ai-influence-social-signal-plane-convergence.prd.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260527-ai-influence-social-signal-plane-convergence.contract.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.prd.md`
- YouTube transcript / ASR 相关 sprint 产物

## Planner Deliverables

1. 统一 Influence 主线 design
2. 7 个 MVP operator 的 builder slice plan
3. 现有 X / YouTube 线迁移 DAG
4. 与 HF / GitHub 的三源共振 contract
5. quality gate matrix

## Mandatory Migration DAG

```text
X / Browser backend line
  -> source collection slice

YouTube transcript / ASR line
  -> long-form statement evidence slice

Unified Social Signal Plane
  -> seed registry
  -> statement collection
  -> normalization
  -> thesis extraction
  -> mapping
  -> packet compiler
  -> insight compiler
```

## Constraints

- 不允许把 X backend 采集线继续当完整洞察系统
- 不允许绕过 `Statement -> Thesis -> EvidencePacket` 主链
- 不允许高模型直接吃 raw social posts

## Acceptance

- design 明确统一 Epic 名
- plan 明确 7 个 builder slices
- migration DAG 可执行
- HF/GitHub resonance contract 明确
- quality gates 明确
