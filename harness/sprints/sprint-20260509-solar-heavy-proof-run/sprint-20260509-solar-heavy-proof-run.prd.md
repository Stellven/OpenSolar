# PRD — Solar Heavy Runtime Proof Run

## Goal

证明前面声称的 Solar/Solar-Harness 集成不是只看文件存在，而是能由真实 Solar builder pane 运行重型 runtime proof 并留下可审计证据。

## User Problem

用户怀疑 benchmark 是静态自检、没有消耗 pane/token、没有调用 Solar。需要真实 pane 执行并写 handoff，且报告中必须区分“可用”和“结构接入”。

## Required Proof

1. MemPalace / ChromaDB：加载 embedding model，查询 live collection，返回 top hits。
2. Apple Notes / WeChat ingest：使用 mock note 隔离运行，导出 markdown，并生成 wiki ingest dispatch。
3. Accepted artifacts 入库：用真实 finalized sprint 导出 accepted knowledge package，并生成 wiki ingest dispatch。
4. Browser-use MCP：调用本地 MCP server module，打开本地网页，读取 marker，并保存截图。

## Non-Goals

- 不污染真实 Obsidian vault。
- 不运行 24GB remote migration。
- 不做 token-consuming Browser-use AI extraction。

## DoD

- `bash solar-harness.sh integrations heavy-proof --threshold 100` exit 0。
- `reports/heavy-proof-benchmark-latest.json` 为 `ok=true`、`score=100`。
- builder handoff 写明命令、结果、证据目录、残留限制。
