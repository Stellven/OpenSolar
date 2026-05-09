# Eval — sprint-20260508-solar-kb-obsidian-autouse

**Round**: 3
**Evaluator**: Solar 审判官 (Claude Opus 4.7)
**Mode**: Manual bash verification (@FALLBACK_MANUAL — verify-all skill not invoked in evaluator pane)
**Verdict**: **PASS — Round 2 FAIL items A2/A5 fixed at root; A1/A3/A4/A6/A7 regression-clean**

---

## 总判定: PASS

**Round 2 → Round 3 修复对照**:
- **A2 (Round 2 FAIL → Round 3 PASS)**: `_vault_hits()` 现返回绝对路径 `source=str(VAULT_PATH)='/Users/sihaoli/Knowledge'`, `path=str(VAULT_PATH/fpath)='/Users/sihaoli/Knowledge/references/...'`. 多 token 查询 ("orbital data center Lumen Orbit") 返回 8 hits, 其中 5 个来自 vault 含 "Knowledge" 路径
- **A5 (Round 2 FAIL → Round 3 PASS)**: 修改正确文件 `lib/symphony/status-server.py` (port 8765). Round 2 误改 `integrations/wiki-capture-server.py` (port 8788) 已不再是问题路径
- **回归**: A1/A3/A4/A6/A7 全部保持 PASS

---

## Done 条件逐条 (A1-A7)

| # | 条件 | 判定 | Live cmd 输出 |
|---|------|------|--------------|
| A1 | Default Solar KB Context Is Real | PASS | `A1_HITS: 6 ELAPSED_MS: 582.2` (< 800ms 限制) |
| A2 | Obsidian Vault Is Indexed Into Solar Search | PASS | 8 hits 中 5 个来自 Knowledge vault, source/path 均为绝对 `/Users/sihaoli/Knowledge/...` |
| A3 | Solar DB Exports To Obsidian Incrementally | PASS | `/Users/sihaoli/Knowledge/_raw/solar-db-export/` 存在, 含 5 个表 (cortex_sources, evo_memory_semantic, knowledge_claims, knowledge_entities, solar_kb_entries) |
| A4 | memory-influence.sh No Longer Silently Misses Semantic Memory | PASS | `bash -n` 通过 + `evo_memory_semantic` 查询返回 |
| A5 | Sync Is Automatic And Observable | PASS | `curl /status` 包含 `solar_kb` (ok=true, indexed=156) + `obsidian_sync` (ok=true, vault_exists=true) |
| A6 | Fail-Open Safety | PASS | SOLAR_DB=/tmp/missing 时返回 `hits: []` (graceful) |
| A7 | Regression Tests Cover The Full Path | PASS | tests/test-solar-kb-obsidian-autouse.sh: **10/10 PASS** |

---

## Smoke Tests (cmd / stdout / conclusion 三要素)

### Smoke 1: A1 默认 KB 检索

```
cmd: python3 lib/solar-knowledge-context.py --query 'Solar 记忆系统' --json
stdout:
  A1_HITS: 6 ELAPSED_MS: 582.2163330000001
  A1_PASS
conclusion: 6 hits 返回, 582ms < 800ms 阈值 → PASS
```

### Smoke 2: A2 Vault 绝对路径 + 多 token

```
cmd: python3 lib/solar-knowledge-context.py --query 'orbital data center Lumen Orbit' --json
stdout (节选):
  HITS_COUNT: 8
  VAULT_HITS_WITH_KNOWLEDGE_PATH: 5
    source='/Users/sihaoli/Knowledge' | path='/Users/sihaoli/Knowledge/references/lumen-orbit-why-train-ai-in-space-2024.md'
    source='/Users/sihaoli/Knowledge' | path='/Users/sihaoli/Knowledge/references/hot-chips-9yr-ai-chip-evolution-next-1000x.md'
    [...更多 vault hits...]
  A2_PASS: True
conclusion: 多 token 查询命中 5 个 vault 文件, source 和 path 均为绝对路径包含 Knowledge → PASS (Round 2 根因已修)
```

### Smoke 3: A3 solar-db-export 目录

```
cmd: test -d /Users/sihaoli/Knowledge/_raw/solar-db-export && ls
stdout:
  A3_DIR_EXISTS
  cortex_sources / evo_memory_semantic / knowledge_claims / knowledge_entities / solar_kb_entries
conclusion: export 目录存在, 5 个表已导出 → PASS
```

### Smoke 4: A5 status 端点双 key 注入

```
cmd: curl -fsS http://127.0.0.1:8765/healthz >/dev/null && curl -fsS http://127.0.0.1:8765/status | python3 -c 'assert solar_kb+obsidian_sync in d'
stdout:
  A5_PASS solar_kb: True obsidian_sync: True
  solar_kb keys: ['indexed_count', 'last_indexed_at', 'ok']
  obsidian_sync keys: ['last_sync_at', 'ok', 'pending_raw_export', 'vault_exists', 'vault_path']
conclusion: live status server (port 8765) 返回完整 schema → PASS (Round 2 误改文件根因已修, helpers 现位于 lib/symphony/status-server.py:884/904, payload 注入在 line 938-939)
```

### Smoke 5: A6 fail-open

```
cmd: SOLAR_DB=/tmp/missing-solar.db python3 lib/solar-knowledge-context.py --query test --fail-open --json
stdout: A6_PASS empty hits, fail-open OK
conclusion: 缺失 DB 时返回空 hits 数组而非异常 → PASS
```

### Smoke 6: A7 完整测试套件

```
cmd: bash tests/test-solar-kb-obsidian-autouse.sh
stdout (尾部):
  [PASS] T1 A6 fail-open: missing DB returns empty hits
  [PASS] T2 A4 memory-influence.sh: syntax valid
  [PASS] T3 A1 Solar KB retrieval: hits found, elapsed<800ms
  [PASS] T4 A2 Obsidian vault: Lumen Orbit indexed and retrievable
  [PASS] T5 obsidian_vault_index schema: correct columns
  [PASS] T6 solar-harness.sh: syntax valid
  [PASS] T6 solar-harness wiki sync-vault: subcommand registered
  [PASS] T7 A5 capture server /healthz: ok
  [PASS] T7 A5 capture server /status: solar_kb+obsidian_sync present
  [PASS] T8 A6 SOLAR_KB_CONTEXT=0: hook outputs nothing
  === Results: 10 PASS / 0 FAIL ===
conclusion: 10/10 → PASS
```

---

## 否证 (Falsification) Attempts (≥3)

| # | 角度 | 操作 | 结果 |
|---|------|------|------|
| 1 | 多 token split 是否破坏单 token 查询 | `--query 'lumen'` | SINGLE_TOKEN_HITS=4 → 不破坏 ✅ |
| 2 | VAULT_PATH 缺失时 source 字段是否暴露空字符串 | OBSIDIAN_VAULT_PATH=/tmp/nonexistent-xyz | VAULT_PATH 正确覆盖, exists=False, 优雅降级 ✅ |
| 3 | status 响应 schema 是否完整不漏字段 | curl /status 后检查 keys | solar_kb 3 keys + obsidian_sync 5 keys 全齐 ✅ |
| 4 | 垃圾 query 是否产生假阳性 | `--query 'asdfqwerzxcv-no-such-thing-xyz123'` | 0 hits → 无假阳性 ✅ |

**结论**: 4 次否证均按预期处理, 无意外行为, 修复可信。

---

## 合约偏离检查

| 项 | 合约 Done 原文 | 建设者实现 | 判定 |
|----|--------------|-----------|------|
| A2 source 字段 | "vault path 出现在 source 或 path 中" | source=str(VAULT_PATH) (line 169) | 合约一致 ✅ |
| A2 path 字段 | "/Users/sihaoli/Knowledge 出现" | path=str(VAULT_PATH / fpath) (line 167) | 合约一致 ✅ |
| A5 端点 | port 8765 (合约 verify cmd) | lib/symphony/status-server.py port 8765 ✅ | 合约一致 ✅ |

无合约偏离。

---

## 自动检测 (verify-all FALLBACK_MANUAL)

verify-all skill 未在 evaluator pane 调用。手动 12 项替代 (C1-C7 + Q1-Q5):

| # | 检查项 | 结果 |
|---|--------|------|
| C1 功能完备 | 7/7 verify cmds + 10/10 tests | OK |
| C2 无断头 | _vault_hits 在 line 381 被调用; _solar_kb_status/_obsidian_sync_status 在 _status_payload 注入 | OK |
| C3 自动触发 | status 端点对所有 GET 请求自动返回新 key; vault hits 在 retrieve fallback chain 中 | OK |
| C4 默认使用 | OBSIDIAN_VAULT_PATH 默认 /Users/sihaoli/Knowledge, 无需配置 | OK |
| C5 激活口令 | curl /status 即触发, 无需特殊 query | OK |
| C6 错误处理 | _solar_kb_status 用 timeout=0.3 防 DB 锁; _obsidian_sync_status 容错 manifest 缺失 | OK |
| C7 持久化 | obsidian_vault_index 156 行落 ~/.solar/solar.db (非 /tmp) | OK |
| Q1 能跑吗 | 7/7 cmds + 10/10 tests live | YES |
| Q2 有效吗 | 多 token 查询命中 5 vault docs, status 返回 indexed=156, ok=true | YES |
| Q3 会退化吗 | 单 token 查询 4 hits 不退化, 缺失 DB 不抛异常 | NO regression |
| Q4 能恢复吗 | SOLAR_DB=/tmp/missing fail-open, vault 缺失也不报错 | YES |
| Q5 用了吗 | live status 端点已包含 key, vault hits 已注入 retrieve | YES |

**FALLBACK 原因**: verify-all 技能未挂载到 evaluator pane (skill 注册表未加载)。已用手动 12 检查点 + 6 smoke + 4 否证 替代。

---

## Round 2 → Round 3 根因修复确认

| Round 2 FAIL 现象 | Round 2 根因 | Round 3 修复 | Round 3 验证 |
|------------------|------------|------------|------------|
| A2 source 返回 "obsidian" 字面值 | DB 列 source 直接返回, 未替换 | line 169 `"source": str(VAULT_PATH)` | live: source='/Users/sihaoli/Knowledge' ✅ |
| A2 path 返回相对路径 | 未拼 VAULT_PATH | line 167 `abs_path = str(VAULT_PATH / fpath)` | live: path='/Users/sihaoli/Knowledge/references/...' ✅ |
| A2 多 token 查询不命中 | LIKE 对整个字符串单次匹配 | 按空格分割每 token 生成独立 OR 子句 | live: 4 token query 命中 5 vault docs ✅ |
| A5 改了错误文件 | wiki-capture-server.py port 8788 ≠ harness status server | helpers 改入 lib/symphony/status-server.py port 8765 | live: curl 8765/status 返回双 key ✅ |

---

## 安全要点

✅ **隔离测试**: A7 测试用 mktemp 临时目录 + 独立 SOLAR_DB/OBSIDIAN_VAULT_PATH env, 不污染 live
✅ **fail-open 设计**: 缺失 DB / 缺失 manifest / 缺失 vault 全部 graceful, 永不阻塞 status 端点
✅ **timeout 保护**: _solar_kb_status 用 timeout=0.3 防 DB lock 阻塞 status 响应
✅ **never raises**: 两个 helper 异常时返回 `ok: False, error: <msg>` 而非抛出

---

## 关键文件清单

| # | 文件 | 状态 | 关键行 |
|---|------|------|------|
| 1 | `lib/solar-knowledge-context.py` | UPDATED | line 167-169 (vault hits 绝对路径), line 136 (_vault_hits 多 token split) |
| 2 | `lib/symphony/status-server.py` | UPDATED | line 884 (_solar_kb_status), line 904 (_obsidian_sync_status), line 938-939 (payload 注入) |
| 3 | `tests/test-solar-kb-obsidian-autouse.sh` | (carry-over) | 10 测试用例 |
| 4 | `obsidian_vault_index` (DB table) | (carry-over) | 156 已索引行 |
| 5 | `/Users/sihaoli/Knowledge/_raw/solar-db-export/` | (carry-over) | 5 表导出目录 |

---

## 最终判定

**PASS — 7/7 acceptance criteria empirically satisfied; Round 2 root causes for A2/A5 confirmed fixed; A1/A3/A4/A6/A7 regression-clean.**

监护人可以放心收 sprint。Solar KB 默认检索链 + Obsidian seamless sync 闭环已经在 live (port 8765) 上观测到正确行为。

---

*Eval written: 2026-05-08T18:00Z*
*Total smoke tests: 6 / falsification attempts: 4 / verify-all: SKIPPED → FALLBACK_MANUAL*
*Test suite: 10/10 PASS*
