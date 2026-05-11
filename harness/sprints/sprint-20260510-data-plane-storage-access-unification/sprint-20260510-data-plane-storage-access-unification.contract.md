---
id: sprint-20260510-data-plane-storage-access-unification
title: Solar Data Plane Storage And Access Unification
priority: P0
lane: data-plane
bypass_pm: true
handoff_to: builder_main
target_role: builder
owner: solar-harness
---

# Contract — Solar Data Plane Storage And Access Unification

## Intent

把 Solar 知识库的数据职责修正为两层：统一数据存储层和统一数据访问层。`_raw` 只做 inbox/staging；`Knowledge/_sources` 做 canonical source library；Mirage 做统一访问层；QMD 做索引检索；MinerU 做后台深抽取；Google Drive 只做 mirror/cold backup。

## Current Facts

- `Knowledge/_sources` 不存在。
- `Knowledge/_meta` 不存在。
- `Knowledge/_raw/file-uploads` 约 659M，正在承担长期原件库职责。
- Knowledge vault 约 681M。
- `.solar` 约 24G，需单独审计，但本 sprint 不清理 `.solar`。
- Mirage 当前 `/sources` 和 `/papers` 存在，但挂到 `~/.solar/harness/_sources`，不是 `~/Knowledge/_sources`。
- QMD 和已有 wiki/provenance 很可能仍引用 `_raw/file-uploads` 旧路径，不能破坏性移动。

## Target Architecture

```text
Application / Agent Layer
  PM / Planner / Builder / Evaluator / Codex / Claude / Skills

Data Access Layer
  Mirage VFS: /knowledge /raw /sources /papers /qmd /solar-db /cortex /sprints /drive
  QMD adapter: semantic search / grep / doc get / vectors
  Policy: ACL / redaction / provenance / lease / audit

Data Processing Layer
  MinerU: PDF deep extraction
  Wiki ingest: concept/entity/claim/summary extraction
  Indexer: QMD update/embed

Unified Data Storage Layer
  Knowledge/_sources / Obsidian vault / Solar DB / QMD index / Events / Sprints / Cortex / Drive mirror
```

## Done

- D1: 建 `~/Knowledge/_sources/{papers,webpages,apple-notes,chatgpt,other}` 和 `~/Knowledge/_meta/`，生成 `source-manifest.jsonl`。每个 `_raw/file-uploads` 原件必须有 `sha256, size, original_path, canonical_path, media_type, status`。
- D2: 实现安全迁移命令，默认 dry-run；正式执行只允许 copy/link，不允许破坏性 `mv`；旧 `_raw/file-uploads` 路径必须保留 symlink/redirect 或 manifest alias，避免打断 QMD/provenance。
- D3: 修 Mirage 配置：`/sources` 和 `/papers` 指向 `~/Knowledge/_sources` 和 `~/Knowledge/_sources/papers`；`mirage doctor` 必须显示正确 physical_root。
- D4: QMD reindex 计划与执行：重建或增量刷新后，搜索必须能命中 canonical source 和 Obsidian reference page；旧路径命中不能丢。
- D5: MinerU idle deep extraction 接入 canonical papers：PDF → markdown/extracted artifacts → references/concepts provenance；不能前台阻塞 shell。
- D6: Google Drive mirror/cold backup 对账：能生成 checksum 对账报告；Drive 不作为主运行目录；未配置或不可用时状态必须 `degraded|warn`，不能假 `ok`。

## Safety Rules

- 禁止删除 `_raw/file-uploads` 原件，除非 manifest、checksum、canonical copy、QMD/provenance redirect 全部通过且用户另行确认。
- 禁止移动导致 Obsidian/QMD/Solar DB 引用断裂。
- 禁止同步 `.env`、API key、token、Google credentials 到 Drive 报告或 manifest。
- 大任务必须 background/idle/rate-limited，不能阻塞用户 shell。
- 任何 D1-D6 未完成，最终状态只能 `warn|failed`，不能 `passed`。

## Verify Commands

```bash
test -d /Users/sihaoli/Knowledge/_sources/papers
test -d /Users/sihaoli/Knowledge/_meta
test -s /Users/sihaoli/Knowledge/_meta/source-manifest.jsonl
solar-harness mirage doctor --json
solar-harness wiki qmd-search "KV cache" --json
solar-harness mineru doctor --json
```

## Required Evidence

- `sprint-20260510-data-plane-storage-access-unification.handoff.md`
- `sprint-20260510-data-plane-storage-access-unification.eval.md`
- `reports/data-plane-storage-access-unification/<timestamp>/source-manifest-stats.json`
- `reports/data-plane-storage-access-unification/<timestamp>/migration-dry-run.md`
- `reports/data-plane-storage-access-unification/<timestamp>/qmd-reindex.md`
- `reports/data-plane-storage-access-unification/<timestamp>/drive-mirror-checksum.md`
