# PRD: ThunderOMLX + Qwen3.6 Pane Overhead Analysis

## 背景

Mac mini 第二个四分屏第 4 pane 已接入 ThunderOMLX + Qwen3.6。

当前已验证：

- 裸 OpenAI-compatible API：6/6 cache hit，`cached_tokens=1536`，平均 TTFT `0.472s`，平均 total `1.003s`，bad_chars=0。
- 真实 tmux pane 交互：端到端 `8.302s`，输出正常，无乱码。
- 结论：ThunderOMLX cache 主路径有效，真实 pane 慢主要可能来自 Claude CLI thinking/render、tool/hook、terminal UI 或请求包装层。

## 目标

1. 拆解 ThunderOMLX + Qwen3.6 在 pane 真实链路中的端到端开销。
2. 区分模型推理、缓存 prefill、Claude CLI 包装、thinking/render、tmux 输入/输出捕获、harness hook 等开销。
3. 产出可执行优化建议，并只落地低风险、可回滚、可验证的优化。
4. 保持现有缓存安全边界，不重新启用导致乱码/空回复的危险特性。

## 非目标

- 不重新启用 partial block cache。
- 不重新启用 full skip / approximate skip。
- 不启用 KVTC 主路径。
- 不替换 Qwen3.6 模型。
- 不删除或清空现有缓存。
- 不打印或持久化 token。

## 用户价值

- 明确 8.3s 真实 pane 延迟到底花在哪里。
- 避免错误优化 ThunderOMLX cache，而忽略 Claude CLI / UI 层开销。
- 给后续“让 pane 交互更快”提供可验证路径。

## 输入证据

- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-pane4-perf-20260520T195355Z.md`
- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-pane4-e2e-20260520T200037Z.md`
- `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-cache-advisor-20260520T194510Z.md`
- ThunderOMLX log: `/Users/lisihao/ThunderOMLX/omlx-8002.log`
- target pane: `solar-harness-lab:0.3`

## 验收标准

- 输出一张分层延迟表：API/model/cache、Claude CLI wrapper、thinking/render、tmux/UI、harness hooks。
- 至少跑 3 类测试：
  1. 裸 API 重复 query。
  2. Claude CLI pane 真实 query。
  3. 最小包装/旁路 query（如果可行，用同 token/base_url 模拟 CLI 请求）。
- 每个测试包含：TTFT、total、cached_tokens、bad_chars、错误/空回复检查。
- 提出 Top 3 优化项，按收益/风险/实施成本排序。
- 若实现优化，只允许低风险项，并提供 before/after 对比。

Knowledge Context: solar-harness context inject used
