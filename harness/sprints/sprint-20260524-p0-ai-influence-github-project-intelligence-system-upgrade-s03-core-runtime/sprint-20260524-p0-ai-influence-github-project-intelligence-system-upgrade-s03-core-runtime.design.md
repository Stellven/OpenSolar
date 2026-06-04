# Design: GitHub Intelligence Core Runtime

## 目标

把 S02 已确认的发现、快照、评分、证据、卡片、brief、report、pipeline 能力整理成可执行核心 runtime。

## 结构

- `harness/lib/github_intelligence/schema.py`: 共享 schema / dataclass / row contract。
- `harness/lib/github_intelligence/adapters/`: tracked/topic/trending/cross-source discovery adapter。
- `harness/lib/github_intelligence/snapshots.py`: repo snapshot 和 delta。
- `harness/lib/github_intelligence/detectors.py`: sudden-hot / early-potential / risk detector。
- `harness/lib/github_intelligence/evidence.py`: README/release/issues evidence atoms。
- `harness/lib/github_intelligence/cards.py`: analysis cards。
- `harness/lib/github_intelligence/briefs.py`: planning briefs。
- `harness/lib/github_intelligence/reports/`: daily/weekly report。
- `harness/lib/github_intelligence/pipeline.py`: orchestration entrypoint。

## 边界

本切片只做核心库和数据模型，不关闭父 epic，不做 UI。
