# Architect Design — chain-watcher 全文件扫描 + 通知机制 Done 定义

**架构师**: pane 3 (opus)
**用途**: 规划者 copy-paste 到新 sprint contract.md 的 `## Definition of Done` 段
**来源**: 监护人发现 chain-watcher 漏看 review-* 文件, 导致 Codex 11:01 写完 review 11:11 才发现 (10 分钟漏看)
**Sprint 估时**: 1h 40min (D1-D8 必做) / 2h (含 D9 / D10 可选)

---

## 现状根因 (写在前面, 让规划者审合约时心里有数)

`~/.solar/harness/chain-watcher.sh:11` 的 `ingest_codex_contracts` 只 find:
```bash
\( -name "contract-*.md" -o -name "execution-contract-*.md" \)
```
其他类型 (`review-*` / `research-*` / `verdict-*` / 任意未命名格式) 全部漏扫. 导致:
- Codex → Solar 链路只半通 (Codex 写其他文件 Solar 完全不知道)
- 没有 PID file 防多开 (双开会重复处理 contract 起 2 个 sprint)

---

## Definition of Done

- [ ] D1: 扫描扩展到全类型 — `chain-watcher.sh` 新增函数 `ingest_codex_all_files`, `find` 范围改为 `~/.solar/codex-bridge/from-codex/` 下**所有 .md 文件** (排除 `*.template.md` 与 `.processed/` 子目录). 按文件名前缀分发处理: `contract-*` / `execution-contract-*` 走起 sprint 路径 (复用 `ingest_codex_contracts` 既有逻辑); `review-*` / `research-*` / 其它走通知路径 (D2). 实现完成后 `bash -n chain-watcher.sh` 通过且 `grep -cE 'review-\\\*\|research-\\\*\|ingest_codex_all_files' chain-watcher.sh` ≥ 4.
  <!-- verify: cmd="bash -n ${HARNESS_DIR}/chain-watcher.sh && grep -cE 'review-\\*|research-\\*|ingest_codex_all_files' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[4-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 20 min

- [ ] D2: 通知机制写入 PLANNER-INBOX.md — 实现 `notify_planner_codex_file <type> <basename>` 函数, 追加一行到 `~/.solar/harness/PLANNER-INBOX.md`, 格式严格如下 (含 ISO8601 UTC 时间戳, type 大写带方括号, 文件名引用相对路径):
  ```
  - [ ] [2026-05-03T15:11Z] [CODEX-REVIEW] review-094659-architect-plan-20260503-110101.md (~/.solar/codex-bridge/from-codex/)
  ```
  type 映射: `review-*`→`CODEX-REVIEW`, `research-*`→`CODEX-RESEARCH`, 其他→`CODEX-UNKNOWN`. 函数必须用 `>>` 追加防覆盖, 写入前 `mkdir -p` 父目录防失败.
  <!-- verify: cmd="grep -cE 'notify_planner_codex_file|CODEX-REVIEW|CODEX-RESEARCH|PLANNER-INBOX\\.md.*>>' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[4-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 15 min

- [ ] D3: 去重 dedup 用 .processed/ — 通知路径与起 sprint 路径**共用** `~/.solar/codex-bridge/from-codex/.processed/` dedup 目录. 通知后必须 `cp <orig> .processed/<basename>` 且 `rm <orig>` (与现有 ingest_codex_contracts line 28-29 行为一致). 启动时已 `mkdir -p .processed` 不变. 已通知文件再次出现 (理论不会, 但兜底): 检测 `[ -f $PROCESSED/$basename ]` 跳过.
  <!-- verify: cmd="grep -cE 'CODEX_PROCESSED.*\\$base|\\.processed/\\$base|cp.*processed' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[3-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 10 min

- [ ] D4: PID file + flock 防多开 — chain-watcher.sh 启动早期 (主 while 循环之前) acquire `~/.solar/harness/.chain-watcher.pid` 用 `flock -n`, 拿不到锁立即 echo "[chain-watcher] already running, exit" 并 `exit 0` (不算异常). 锁 fd 保持到进程结束自动释放. 实现路径: `exec 200>"$PID_FILE"; flock -n 200 || { echo "..."; exit 0; }; echo $$ > "$PID_FILE"` (注: 这个写法 echo 后 fd 仍持锁).
  <!-- verify: cmd="grep -cE 'flock -n|chain-watcher\\.pid|already running' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[3-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 15 min

- [ ] D5: 模板文件不通知 — find 必须排除 `*.template.md` (已存在如 `execution-contract.template.md` / `review-verdict.template.md` / `research-brief.template.md` / `handoff-receipt.template.md`). find 表达式加 `! -name "*.template.md"`. 验证: 当 `from-codex/` 下只剩模板文件时, 一轮扫描后 PLANNER-INBOX 不增加任何 CODEX-* 行.
  <!-- verify: cmd="grep -cE 'template\\.md|! -name.*template' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[2-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 5 min

- [ ] D6: 端到端实测 review-* 通知 — 编写 `~/.solar/harness/test-chain-watcher-notify.sh`: (a) 备份 PLANNER-INBOX.md mtime + 行数; (b) 在 `from-codex/` 写一个 disposable `review-test-$$-$(date +%s).md` 含 `## verdict: TEST_NOTIFY`; (c) 跑 chain-watcher 一个迭代 (mock 模式或 timeout 35s); (d) 验证 PLANNER-INBOX.md 多 1 行含 `[CODEX-REVIEW]` 与该 disposable 文件名; (e) 验证 disposable 文件被移到 `.processed/`; (f) 清理 disposable. 测试输出含 "PASS" 字样.
  <!-- verify: cmd="bash ${HARNESS_DIR}/test-chain-watcher-notify.sh" expected_exit=0 output_pattern="PASS" -->
  - **预计实施时间**: 25 min

- [ ] D7: 不破坏既有 contract 起 sprint 流程 — 现有 `contract-*.md` 投递行为不能回归: 投一个 disposable `contract-test-$$.md` 含完整 frontmatter (title/topology/...), chain-watcher 必须仍然 (a) 起新 sprint, (b) 移到 `.processed/`, (c) **不写** PLANNER-INBOX (因为它走起 sprint 路径不走通知路径). 编写 `~/.solar/harness/test-chain-watcher-contract-regression.sh`.
  <!-- verify: cmd="bash ${HARNESS_DIR}/test-chain-watcher-contract-regression.sh" expected_exit=0 output_pattern="PASS" -->
  - **预计实施时间**: 20 min

- [ ] D8: 启动日志含扫描统计 — chain-watcher.sh 主循环每个 iter 末尾 (sleep 之前) log 一行: `[chain-watcher] scan: contracts=N1 reviews=N2 research=N3 unknown=N4 templates_skipped=N5`. N 都是本轮新处理的数量, 0 也要打 (方便诊断 "扫了但全是已处理"). 现有 echo 统计可保留.
  <!-- verify: cmd="grep -cE 'contracts=|reviews=|templates_skipped' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[2-9]|^[1-9][0-9]" -->
  - **预计实施时间**: 10 min

- [ ] D9 **(可选)**: 通知去重防风暴 — 同一文件名只通知**一次** (.processed/ dedup 已防), 但同一**类型** (e.g. review-*) 在同一分钟内多个文件到达时, 仍写多行. 加可选 throttle: `~/.solar/harness/.chain-watcher-notify-throttle` 记录 `<type>:<last_ts>`, 同 type 60s 内合并为 1 行通知 + 计数 (e.g. `[CODEX-REVIEW] (3 files in last 60s) review-a.md, review-b.md, review-c.md`).
  <!-- verify: cmd="grep -cE 'throttle|last_ts|files in last' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[1-9]" -->
  - **预计实施时间**: 15 min (可选, 防风暴, 不做不影响主功能)

- [ ] D10 **(可选)**: 启动恢复扫一次 — chain-watcher.sh 启动时 (拿到 flock 后, 进 while 循环之前) 立即跑一次完整 `ingest_codex_all_files`, 处理所有当前已存在的未处理文件. 不等 30s 第一轮 sleep. 这样监护人重启 chain-watcher 后能立即清积压.
  <!-- verify: cmd="grep -cE 'startup.*ingest|recovery.*scan|first sweep' ${HARNESS_DIR}/chain-watcher.sh" expected_exit=0 output_pattern="^[1-9]" -->
  - **预计实施时间**: 5 min (可选, UX 改进)

---

## 总预算

| 范围 | 时间 |
|------|------|
| D1-D5 (核心扫描 + 通知) | 65 min |
| D6 (review 端到端测试) | 25 min |
| D7 (contract 回归测试) | 20 min |
| D8 (扫描统计 log) | 10 min |
| **必做总计** (D1-D8) | **2h** |
| **完整含 D9+D10** | **2h 20min** |

---

## 实施顺序建议

```
D4 (PID 防多开) → D5 (模板排除) → D1 (扫描扩展) → D2 (通知机制) → D3 (dedup) → D8 (log) → D6 (review e2e) → D7 (contract 回归) → [D9 / D10 可选]
```

**理由**:
- D4 (PID file) 先做, 防止开发期间不小心起多 instance 互踩
- D5 (模板排除) 比 D1 优先, 否则 D1 上线立刻刷屏 (4 个模板文件全被通知)
- D1 + D2 + D3 是核心三件套, 必须连续做避免半上线状态 (D1 扫到了但 D2 没通知)
- D8 (log) 紧跟核心, 方便测试时观察行为
- D6 (review 通知) 在主功能上线后立即测, 不要等 D7
- D7 (contract 回归) 最后跑, 验证未破坏既有

---

## 关键风险提示 (供规划者审核合约时参考)

1. **D4 flock 写法陷阱**: `exec 200>$PID_FILE; flock -n 200` 必须 fd 200 在整个 while 循环里保持打开, **不能** `flock -u` 释放 (释放就让多开了). 进程退出 fd 自动关 OS 释放锁
2. **D2 PLANNER-INBOX 并发写**: chain-watcher 与 coordinator-watchdog 都可能写 PLANNER-INBOX. 当前实现 `>>` 是 POSIX append 原子 (单行 < PIPE_BUF 4KB 时安全), 但若一行超过 4KB 可能交错. 实践中通知行 < 200 字符, 不需要 flock
3. **D3 .processed 路径一致**: ingest_codex_contracts (现有) 与 ingest_codex_all_files (D1) 必须用同一个 `CODEX_PROCESSED` 变量, 不能 hardcode 两遍路径分歧
4. **D6 测试隔离**: disposable review 文件名加 `$$` (PID) + 时间戳, 避免并发跑测试时互踩
5. **D7 contract 回归**: 测试创建的 disposable contract.md frontmatter 必须**最小完整** (title 必填), 否则 `solar-harness sprint` 命令可能拒收, 导致测试 false-fail

---

## 配套行为约束 (合约 Constraints 段建议)

- **不**改 `~/.solar/codex-bridge/CODEX-PROTOCOL.md` (协议层, 范围外)
- **不**改 `from-codex/` 已有文件 (只读消费)
- **不**改 PLANNER-INBOX.md 已有格式 (只追加, 兼容 watchdog 等其它写入者)
- **必须**保证 chain-watcher 单实例 (D4)
- **必须**保证模板文件永不进入 sprint 或通知 (D5)

---

**完成**: 8 必做 + 2 可选 Done, 共 10 条, 全部含 verify cmd / expected_exit / output_pattern. 总行数 ~165 (≤200 ✓).
**规划者下一步**: copy `## Definition of Done` 段进新 sprint contract, 推 active. 这单与 sprint-104819 (dispatch fix) / sprint-102743 (scanner fix) 完全正交, 可并行实施.
