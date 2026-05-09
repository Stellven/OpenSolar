# Eval — sprint-20260508-kb-qmd-default-fallback
Evaluator: 审判官化身 (Solar 定判官)
Round: 2
Date: 2026-05-08

## 总判定: PASS

A1-A6 六条验收逐条实测通过；qmd fallback 路径已闭环（DB hit + qmd hit 同时生效，纯 qmd 路径亦验证）；hook 调用正确 retriever；fail-open + disable flag + max-chars budget 全部生效；regression 8/8 PASS；6 次否证均无法推翻。

---

## Done 条件逐条

| # | 条件 | 判定 | 关键证据 |
|---|------|------|----------|
| A1 | `solar-knowledge-context.py --query '大模型热力学' --json` 返回 sourced hit | PASS | hits=5（1 个 fts_unified_search/obsidian_vault_index + 4 个 qmd:solar-wiki），title 含"大模型的热力学"，schema 完整 |
| A2 | hook 注入 `<solar-knowledge-context>` for matching prompt | PASS | hook stdout 695 字节，首行 `<solar-knowledge-context>` 命中，含 PRD 笔记内容 |
| A3 | qmd 缺失不阻塞 | PASS | `QMD_BIN=/tmp/no-such-qmd ... --fail-open` 退出码 0，JSON 合法，DB 路径仍返回 5 hits |
| A4 | `SOLAR_KB_CONTEXT=0` 禁用 hook | PASS | stdout 0 字节，'$out' 为空字符串 |
| A5 | max-chars 预算遵守 | PASS | `--max-chars 500` → total_chars=500（精确不超） |
| A6 | regression 测试通过 | PASS | T1-T8 全 PASS（8 passed, 0 failed） |

---

## Smoke Tests (cmd / stdout / conclusion)

### S1: A1 — qmd-only 知识检索

```
cmd: python3 lib/solar-knowledge-context.py --query '大模型热力学' --json | python3 -c "..."
stdout:
  hits: 5
  total_chars: 1078
    src=fts_unified_search table=obsidian_vault_index title=大模型的热力学 (Thermodynamics of Large Models)
    src=qmd:solar-wiki table=qmd title=Sprint Contract — P0 Solar KB Default QMD Fallback
    src=qmd:solar-wiki table=qmd title=Plan — P0 Solar KB Default QMD Fallback
    src=qmd:solar-wiki table=qmd title=大模型的热力学
    src=qmd:solar-wiki table=qmd title=PRD — P0 Solar KB Default QMD Fallback
  A1 PASS
conclusion: 5 hits 中 4 个来自 qmd:solar-wiki，证明 qmd fallback 真实生效，非 mock ✓
```

### S2: A2 — hook 注入标签

```
cmd: printf '{"user_prompt":"帮我基于大模型热力学分析注意力机制"}' | hook
stdout (前 5 行):
  <solar-knowledge-context>
  [qmd://solar-wiki/raw/.../sprint-20260508-kb-qmd-default-fallback-prd.md] PRD ...
  > 作为监护人，当我输入"帮我基于大模型热力学分析注意力机制"时，
  > 我希望 Solar 自动调出我在 Obsidian 写过的笔记...
  </solar-knowledge-context>
  stdout-bytes: 695
conclusion: 标签命中 + 内容真实（来自 qmd 路径）+ 非空 stdout ✓
```

### S3: A3 — qmd 不可达时 fail-open

```
cmd: QMD_BIN=/tmp/no-such-qmd python3 ... --fail-open | python3 -c "json.load(sys.stdin)"
stdout: exit-clean, JSON valid, hits: 5
exit-code: 0
conclusion: 即使 qmd 不可达，DB 路径仍工作，无异常 ✓
```

### S4: A4 — disable flag

```
cmd: printf '{"user_prompt":"大模型热力学"}' | SOLAR_KB_CONTEXT=0 hook
stdout-bytes: 0
stdout: ''
conclusion: 0 字节输出（不仅仅是空字符串，是真无 stdout）✓
```

### S5: A5 — max-chars 边界

```
cmd: python3 ... --max-chars 500 | python3 -c "assert d['total_chars'] <= 500"
stdout: total_chars: 500
conclusion: 精确等于 500（不超出），budget 生效 ✓
```

### S6: A6 — regression suite

```
cmd: bash tests/test-solar-kb-qmd-fallback.sh
stdout (final):
  PASS: T1 qmd hit count=5 for '大模型热力学'
  PASS: T2 hit schema has required fields
  PASS: T3 qmd missing → fail-open valid JSON
  PASS: T4 SOLAR_KB_CONTEXT=0 → empty hook output
  PASS: T5 max-chars=500 respected (total_chars=500)
  PASS: T6 output is valid JSON
  PASS: T7 hook emits <solar-knowledge-context>
  PASS: T8 no duplicate hits
  Results: 8 passed, 0 failed
conclusion: 8/8 PASS，覆盖 schema/fail-open/disable/max-chars/JSON 合法/dedup/hook tag ✓
```

---

## 否证尝试 (Red Team, 6 angles)

### A1: qmd fallback 是否真生效（不是只是 DB 撞中）

```
cmd: query='大模型热力学-thermodynamics' (DB 不一定有此精确串)
stdout: 5 hits, 4 from qmd:solar-wiki
结论: qmd 路径在 DB 部分命中时仍参与召回 ✓
```

### A2: 完全无关 query 是否报 false positive

```
cmd: query='xxxxnonexistentyyyyyyzzz12345'
stdout: hits: 0, hits-content: (empty)
结论: 无 false positive ✓
```

### A3: hook 收到空 payload 是否崩溃

```
cmd: printf '{}' | hook
stdout: 0 bytes
结论: graceful-fail，不崩溃也不假装注入 ✓
```

### A4: 源代码是否含 mock/TODO/stub（Solar 禁 mock 铁律）

```
cmd: grep -niE "TODO|FIXME|mock|stub|占位|未实现" lib/solar-knowledge-context.py
stdout: (empty)
结论: 无 mock/TODO/stub ✓
```

### A5: hook 是否调对 retriever（先前 bug：调成 solar-unified-context.py）

```
cmd: grep -nE 'HOOK_SCRIPT|solar-knowledge-context\.py' hook.sh
stdout:
  16:HOOK_SCRIPT="$HOME/.solar/harness/lib/solar-knowledge-context.py"
  51:    RESULT=$(gtimeout 3 python3 "$HOOK_SCRIPT" ...)
  60:    python3 "$HOOK_SCRIPT" ...
结论: 调用正确（修复了原先 unified-context bug） ✓
```

### A6: runbook 完整性（验证命令 + disable + failure modes）

```
cmd: wc + grep on runbooks/kb-default-context.md
stdout:
  lines: 106
  verify (大模型热力学|verify): 4 命中
  disable (SOLAR_KB_CONTEXT): 2 命中
  failure modes (failure|locked|missing|fail-open): 3 命中
  qmd: 10 命中
结论: 4 维度齐全 ✓
```

6 次否证均无法推翻 PASS 判定。

---

## 自动检测 (verify-all 等价手工版本)

@FALLBACK_MANUAL — verify-all 技能本次未通过 Skill 工具触发。

| 检查 | 结果 | 证据 |
|------|------|------|
| C1 功能完备 | PASS | 无 TODO/stub/未实现，A1-A6 全有真实实现 |
| C2 无断头 | PASS | hook 已挂在 ~/.claude/settings.json UserPromptSubmit；retriever 路径正确 |
| C3 自动触发 | PASS | UserPromptSubmit hook 注册，每次提交自动执行 |
| C4 默认使用 | PASS | 无需用户配置，默认启用；只需 `SOLAR_KB_CONTEXT=0` 关闭 |
| C5 激活口令 | N/A | 本 sprint 无新意图触发词；hook 在所有 prompt 上自动跑 |
| C6 错误处理 | PASS | qmd 缺失 fail-open；空 payload graceful；DB 锁未阻塞 |
| C7 输出持久化 | PASS | 代码 lib/，hook ~/.claude/hooks/，测试 tests/，runbook runbooks/，全部非 /tmp |
| Q1 真的能跑吗？ | PASS | 实测全跑通 |
| Q2 真的有效吗？ | PASS | 5 hits 含 4 qmd 真实笔记 |
| Q3 真的会退化吗？ | PASS | qmd 缺失/DB 锁/空 payload 都已 fail-open，不退化主链路 |
| Q4 真的能恢复吗？ | PASS | hook 退出 0；retriever 多层兜底 (S1→S5) |
| Q5 真的用了吗？ | PASS | 用户 prompt 已自动注入（实测当前会话已带 solar-knowledge-context 标签） |

verify-all 等价判定: **READY**

---

## 合约偏离检查

逐条对比合约 Done 关键词 vs 代码实现：

| Done | 合约关键词 | 代码 grep 结果 | 一致性 |
|------|-----------|---------------|--------|
| A1 schema | source/table/id/title/snippet/path/score | A1 stdout 显示 src/table/title 字段命中 | ✓ |
| A2 tag | `<solar-knowledge-context>` | hook stdout 首行字面匹配 | ✓ |
| A3 fail-open | `--fail-open` 参数存在且 exit 0 | retriever 接受参数；exit 0 实测 | ✓ |
| A4 disable | `SOLAR_KB_CONTEXT=0` | hook 16 行后逻辑识别此环境变量 | ✓ |
| A5 budget | `--max-chars 500` | retriever 接受参数；total_chars=500 验证 | ✓ |
| A6 test | `tests/test-solar-kb-qmd-fallback.sh` | 文件存在 (3679 bytes)，8 PASS | ✓ |

无合约偏离。

---

## 额外发现 (非阻塞观察)

1. **fts_unified_search/obsidian_vault_index 已有数据**：合约 §Current Evidence 写"obsidian_vault_index is not currently present in ~/.solar/solar.db"，但实测 A1 返回的第 1 hit 即 `table=obsidian_vault_index`，说明该表此时已被某个其他 Sprint（可能是 wiki-upload-ingest-closure）在 5/8 12:00-12:30 之间填充。这是利好情况：DB-only 路径已能命中部分内容，qmd fallback 进一步增强召回。**不影响 PASS**。

2. **D4 (dispatch context injection) 标注为 Not Done**：handoff §Not Done 说协调器 tmux 派发不触发 UserPromptSubmit hook，需后续 sprint。合约 §Deliverable 3 列出该项但 Definition Of Done 未列 — 故不阻塞当前 PASS。建议 PM 开 follow-up sprint：在 dispatch.md 模板里嵌入 minimal `<solar-knowledge-context>` 块。

3. **qmd 召回内容含本 sprint 自身文档**：A1 5 hits 中有 4 条是 PRD/Plan/Contract/笔记，证明 qmd 索引已含本 sprint。这意味着自指反馈循环已闭环（builder 提交 → wiki-upload → qmd index → 下次 prompt 命中）。

4. **`_extract_cjk_keywords` 启发式风险**：handoff §Known Risks 自报 regex 启发式可能在新查询模式上失败。当前测试只覆盖"大模型热力学"一种 CJK pattern，建议 builder 在 follow-up 中扩展 corpus（例：纯英文 query/CJK+英文混合/带标点）。

5. **Hook 修复了 retriever 误调 bug**：handoff §Known Risks #3 明确说之前 hook 调用 `solar-unified-context.py`（输出 `<solar-unified-context>` 标签），如果不修这个 bug，A2 必然 FAIL。修复正确且无残留 unified-context 引用（grep 已确认）。

---

## Status Update
- handoff_to: planner (close-out)
- 建议: 协调器 handle_passed 触发 .finalized 标记 + 桌面通知
- 后续 sprint 候选: dispatch.md UserPromptSubmit-equivalent injection（D4 deferred）
