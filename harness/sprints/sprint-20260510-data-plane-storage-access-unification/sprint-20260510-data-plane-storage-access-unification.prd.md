# PRD — Solar Data Plane Storage And Access Unification

## Goal

把 Solar 知识库从“_raw 长期堆原件”修成产品级数据层：canonical source library、统一访问层、后台处理层、检索索引层、冷备镜像层各司其职。

## User Stories

- 作为用户，我上传 PDF 后，原件进入 `_sources/papers`，`_raw` 只保留 staging/alias，不再变成长期仓库。
- 作为 agent，我可以通过 Mirage `/papers`、`/sources`、`/qmd` 访问同一份知识，不需要猜真实路径。
- 作为检索系统，QMD 能同时命中原件、抽取页和 Obsidian references。
- 作为处理系统，MinerU 只在 idle/background 深抽取，不阻塞当前 shell。
- 作为备份系统，Drive 只做镜像/冷备，不当本地 agent 的主工作目录。

## Constraints

- 先 manifest 和 dry-run，再 copy/link，不做破坏性移动。
- 兼容旧 `_raw/file-uploads` 引用。
- 本 sprint 不清理 `.solar` 24G，只记录后续审计项。
- 最终必须由 evaluator 复核，不允许 builder 自宣 passed。

## Risks

- QMD index、Obsidian pages、dispatch provenance 可能引用旧路径。
- PDF 文件名含中文、空格、特殊符号，迁移必须安全处理。
- Drive File Provider 可能有在线/离线状态差异。
- MinerU 深抽取可能耗时，必须 idle/background。

## DoD

- D1-D6 全部有机器可读证据。
- `Knowledge/_sources` 成为 canonical source library。
- Mirage `/sources` `/papers` 指向 Knowledge 而不是 harness 内部 `_sources`。
- `_raw/file-uploads` 不再是唯一长期原件库，但旧路径不被破坏。
