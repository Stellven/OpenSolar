# Eval — sprint-20260509-solar-capability-plane-unification

**Round**: 2
**Evaluator**: 审判官 (Solar Evaluator Incarnation)
**Mode**: @FALLBACK_MANUAL (verify-all skill not registered in evaluator pane)

## 总判定: PASS

D1–D10 全部通过 contract 内嵌 verify 命令实证. 38 个 solar-native skill 全列, 1600 总 skills, doctor 无凭据泄漏, inject 幂等且保留原内容, coordinator 已挂接 inject_dispatch_context, graph 18 节点 18 边全 valid, 重复 case 已清理, status-server 代码包含 capability/skills/mcp_mode/kb_context 关键词且 py_compile 通过, pane-launcher --print-config 暴露 STRICT MCP, 静态语法全绿.

## Done 条件逐条

| # | 条件 (摘要) | 判定 | 证据 |
|---|------|------|------|
| D1 | inventory 返回所有 skill roots + Solar native skills (≥1600 + 38) | PASS | totals.skills=1600, sources.solar-native.count=38 |
| D2 | doctor pane 级 capability 无 secret | PASS | re.search(ZHIPU/ANTHROPIC/DEEPSEEK/sk-) → None; panes/overall keys present |
| D3 | inject 幂等 + 双 context 块 | PASS | tests/test-skills-inject-idempotent.sh → PROBES_PASSED=3 PROBES_FAILED=0 |
| D4 | coordinator 派发路径调用 injection | PASS | rg → 6 hits at coordinator.sh:1202,1204,1207,1209,1213,1426 (1426 inside dispatch_to_pane) |
| D5 | graph JSON + Mermaid 含核心依赖 | PASS | tests/test-harness-graph.sh → PROBES_PASSED=3 PROBES_FAILED=0; nodes=18 edges=18 missing=0 invalid=0 |
| D6 | 无 mirage/data-plane 重复 top-level case | PASS | check-top-level-case-duplicates.py → no duplicate (31 unique labels); mirage/ at line 2354 only, data-plane/ at line 1920 only |
| D7 | status UI/API 暴露 pane capability 摘要 | PASS | py_compile OK; 25 keyword hits (capabilit/skills/mcp_mode/kb_context); _pane_capability_summary 在 836 行, /api/capability 路由在 2153 行 |
| D8 | pane-launcher --print-config 暴露 MCP mode | PASS | EXTRA_FLAGS='--bare --tools default --strict-mcp-config --mcp-config /Users/lisihao/.solar/harness/config/empty-mcp.json' |
| D9 | solar-native skill 抽取产出分类 cache | PASS | state/solar-native-skills.json 存在; len(skills)=38; 全部含 status 字段 |
| D10 | bash -n + py_compile 全绿 | PASS | solar-harness.sh / coordinator.sh / pane-launcher.sh / solar_skills.py / harness_graph.py 全过 |

## 自动检测 (verify-all)

verify-all skill 未在审判官 pane 注册, 走 @FALLBACK_MANUAL. 手工执行:
- C1 功能完备: PASS (无 TODO/FIXME 在新模块)
- C2 入口调用方: PASS (D4 验证 coordinator 已挂接, solar-harness skills/graph 子命令已注册)
- C3 自动触发: PASS (coordinator dispatch_to_pane 内调用, fail-open)
- C4 默认使用: PASS (D8 print-config 暴露 STRICT MCP, 默认行为可见)
- C5 错误处理: PASS (inject_dispatch_context fail-open + degraded KB block)
- C6 输出持久化: PASS (state/solar-native-skills.json + state/skills-inventory.json 永久缓存)
- Q1 真的能跑吗: PASS (all 10 verify cmds 实测通过)
- Q2 真的有效吗: PASS (inject 双 block 写入 + 幂等)
- Q3 真的会退化吗: PASS (KB unavailable → degraded warn block)
- Q4 真的能恢复吗: PASS (重新跑 inventory/extract 即重建 cache)
- Q5 真的用了吗: PASS (coordinator.sh:1426 已挂接, dispatch_to_pane 路径上)

## Real Commands Executed (per contract Evaluation Requirements)

合约 "Evaluator must inspect real command output. A PASS is invalid if it only checks files exist." 已严格遵循.

### 1. NEW 文件 ls -la (铁律 1)

```
$ ls -la lib/solar_skills.py lib/harness_graph.py \
        tests/test-skills-inject-idempotent.sh tests/test-harness-graph.sh \
        tests/check-top-level-case-duplicates.py \
        state/solar-native-skills.json state/skills-inventory.json
-rw-r--r--  1 sihaoli  staff   8374 May  8 20:39 lib/harness_graph.py
-rw-r--r--  1 sihaoli  staff  14407 May  8 20:37 lib/solar_skills.py
-rw-r--r--  1 sihaoli  staff   1226 May  8 20:41 state/skills-inventory.json
-rw-r--r--  1 sihaoli  staff  10034 May  8 20:37 state/solar-native-skills.json
-rw-r--r--  1 sihaoli  staff   2763 May  8 20:40 tests/check-top-level-case-duplicates.py
-rwxr-xr-x  1 sihaoli  staff   2794 May  8 20:39 tests/test-harness-graph.sh
-rwxr-xr-x  1 sihaoli  staff   2484 May  8 20:38 tests/test-skills-inject-idempotent.sh
```
全部存在, 字节非零, mtime 在 sprint 派发后. 通过.

### 2. D1 inventory 输出摘要

```
$ solar-harness skills inventory --json
{
  "totals": { "skills": 1600, "agents_skills": 1562, "solar_native": 38 },
  "sources": {
    "agents-skills": { "path": "/Users/lisihao/.agents/skills", "count": 1562 },
    "solar-native": { "path": "/Users/lisihao/Solar/skills", "count": 38,
      "skills": ["a2a-hub", "agent", "agent-orchestrator", "apple-calendar",
        "banner", "benchmark", "browser-automation", "build", "clawdwork",
        "commit", "docs", "email-to-calendar", "fast-browser-use",
        "mcp-builder", "mode", "obsidian-daily", ...] }
  }
}
```

### 3. D2 doctor pane capability 摘要

```
$ solar-harness skills doctor --json
{
  "panes": [
    {"pane": "lab-builder", "model": "opus", "auth_source": "zhipu",
     "mcp_mode": "STRICT", "mcp_config": "...empty-mcp.json",
     "kb_context": false, "skills_accessible": false, "auth_token_present": true},
    {"pane": "builder", "model": "sonnet", "auth_source": "",
     "mcp_mode": "DEFAULT", "kb_context": true, "skills_accessible": true},
    ...
  ],
  "overall": {"total_panes": 5, "strict_mcp_panes": 1, "default_mcp_panes": 4,
              "status": "ok"}
}
```
secret leak grep: re.search(r"ZHIPU_AUTH_TOKEN|ANTHROPIC_AUTH_TOKEN|DEEPSEEK_API_KEY|sk-[A-Za-z0-9]") → None ✓

### 4. D3 注入后双 context 块 dispatch 摘要

```
$ python3 lib/solar_skills.py inject /tmp/test-existing.dispatch.md  # 第二次调用
$ cat /tmp/test-existing.dispatch.md
# Existing dispatch
## Some content
existing line 1
existing line 2

<solar-skills-context>
<!-- auto-generated by solar_skills.py at 2026-05-09T00:45:55Z -->
Solar has 1562 general skills and 38 solar-native skills.
Solar-native skills: a2a-hub, agent, agent-orchestrator, ...
</solar-skills-context>

<solar-knowledge-context>
<!-- warn: KB context unavailable at 2026-05-09T00:45:55Z -->
KB context could not be loaded. Proceed with available information.
</solar-knowledge-context>
```
两次调用 → block count = 1 each ✓ ; 原内容保留 ✓

### 5. D4 coordinator 调用点 (rg)

```
$ rg -n 'skills inject|solar_skills.py|inject_dispatch_context' coordinator.sh
1202:# inject_dispatch_context — idempotently inject skills+KB context into a dispatch file
1204:inject_dispatch_context() {
1207:  local skills_py="$HARNESS_DIR/lib/solar_skills.py"
1209:    log "${Y}[dispatch] solar_skills.py not found, skipping context injection${N}"
1213:    log "${Y}[dispatch] skills inject warn (fail-open): $dispatch_file${N}"
1426:  inject_dispatch_context "$instruction_file" || true
```
1426 行在 `dispatch_to_pane` 内, 派发前调用. ✓

### 6. D5 graph Mermaid 摘要

```
$ solar-harness graph --format mermaid
graph LR
  subgraph config
    persona-config["persona-config\nPer-persona model/MCP/auth config provid"]
    empty-mcp-config["empty-mcp-config\nEmpty MCP config used by STRICT mode pan"]
  end
  subgraph entrypoint
    solar-harness["solar-harness\nMain CLI entrypoint — routes all subcoma"]
  end
  ...
```
JSON stats: nodes=18, existing=18, missing=0, edges=18, invalid=0

### 7. D6 重复 case 清理

```
$ python3 tests/check-top-level-case-duplicates.py solar-harness.sh
PASS: no duplicate top-level case branches (31 unique labels)

$ grep -n "^  mirage)" solar-harness.sh
2354:  mirage)

$ grep -n "^  data-plane)" solar-harness.sh
1920:  data-plane)
```
mirage/data-plane 各出现一次, 重复版本已删除. ✓

## 否证尝试 (≥3 angles)

| # | 角度 | 命令 | 结果 |
|---|------|------|------|
| 1 | inject 三次 → 是否仍只 1 个 block | `inject 3 次后 grep -c '<solar-skills-context>'` | 1 (idempotent) |
| 2 | inject 是否破坏原内容 | `inject 后 grep "existing line 1"` | 1 (preserved) |
| 3 | doctor 输出加密查 secret | `re.search(r"sk-[A-Za-z0-9]\|ZHIPU_AUTH_TOKEN\|ANTHROPIC_AUTH_TOKEN\|DEEPSEEK_API_KEY", out)` | None (no leak) |
| 4 | 重复 case 是否真的删了 (双向验证) | `grep -c "^  mirage)" + grep -c "^  data-plane)"` | 1 + 1 (各 1 处) |
| 5 | inventory cache 是否真有 38 native | `len(state/solar-native-skills.json.skills) == 38 && all has status` | True |

5 次否证全部失败 → Done 条件确认 PASS.

## Smoke Test (三要素)

### Smoke Test 1: D1+D2 inventory + doctor 联合
- **cmd**: `solar-harness skills inventory --json | python3 -c '...assert d["totals"]["skills"] >= 1600...'` 接 `solar-harness skills doctor --json | python3 -c '...assert "panes" in d...'`
- **stdout**: D1 PASS / D2 PASS
- **conclusion**: 两子命令 wired up 且输出符合契约 schema. PASS

### Smoke Test 2: D3 注入幂等 + 内容保留
- **cmd**: `cat > /tmp/x.dispatch.md <<EOF...EOF; python3 lib/solar_skills.py inject /tmp/x.dispatch.md (×2); grep -c '<solar-skills-context>'`
- **stdout**: 1 (双 inject 后块数仍为 1); existing line 1/2 + Some content 各 1 (原内容未被覆盖)
- **conclusion**: inject 幂等且非破坏性. PASS

### Smoke Test 3: D5 graph 跑通
- **cmd**: `bash tests/test-harness-graph.sh`
- **stdout**: `JSON validation OK / nodes: 18, edges: 18 / existing: 18, missing: 0 / PROBES_PASSED=3 PROBES_FAILED=0`
- **conclusion**: 18 节点 18 边全 valid 全 existing. PASS

## 合约偏离检查

逐条对比 contract Done verify cmd 关键词 vs 实际代码:

- D1: 关键词 `d["totals"]["skills"] >= 1600` + `count == 38` → 实测 1600 + 38, **完全匹配**
- D2: 关键词 `not re.search(ZHIPU|ANTHROPIC|DEEPSEEK|sk-)` + `panes` + `overall` → 实测无泄漏 + 双键存在, **完全匹配**
- D3: 关键词 `tests/test-skills-inject-idempotent.sh` exit 0 → 实测 PROBES_FAILED=0, **完全匹配**
- D4: 关键词 `skills inject|solar_skills.py|inject_dispatch_context` → 6 hits, **完全匹配**
- D5: 关键词 `tests/test-harness-graph.sh` exit 0 → 实测 PROBES_FAILED=0, **完全匹配**
- D6: 关键词 `tests/check-top-level-case-duplicates.py` exit 0 → 实测 PASS, **完全匹配**
- D7: 关键词 `py_compile` + `rg 'capabilit|skills|mcp_mode|kb_context'` → 25 hits, **完全匹配** (注: contract 要求代码级检查, 不要求 live curl)
- D8: 关键词 `pane-launcher.sh --print-config` 含 `MCP|STRICT|empty|EXTRA_FLAGS|mcp-config` → 实测 EXTRA_FLAGS 行含全部关键词, **完全匹配**
- D9: 关键词 `len == 38 && all status` → 实测匹配, **完全匹配**
- D10: 关键词 `bash -n` + `py_compile` → 全绿, **完全匹配**

无合约偏离.

## 额外发现 (informational, 不阻塞 PASS)

1. **status-server 8765 进程是旧版** — 当前运行 PID 91696 已 elapsed 6h35m, 启动时间在 D7 patch (file mtime 2026-05-08 20:41) 之前. live `curl /api/capability` 返回 HTTP 404 (旧代码无此路由). **但合约 D7 verify cmd 是 py_compile + rg 代码级检查, 不要求 live curl**, 严格按合约判定通过. 建议下轮 sprint 加上 status-server 重启以刷新路由, 或在 coordinator 内置 SIGHUP reload.

2. **handoff Round 字段为 1, status round=2** — 与历史 sprint (mirage-unified-vfs / mirage-codex-solar-substrate) 同样问题. 低优先级 warning, builder 下次更新 handoff round.

3. **lab-builder pane 默认 STRICT MCP, kb_context=false, skills_accessible=false** — 这是预期行为 (handoff 已说明 lab-builder 用 empty-mcp.json). 若后续有需求让 lab-builder 也能读 KB, 需另起 sprint.

## 降级说明

verify-all skill 在审判官 pane 未注册, 走 @FALLBACK_MANUAL 协议:
- 手动跑 contract 内嵌 10 条 verify cmds, 全 PASS
- 手动 5 否证 (3 次 inject / 内容保留 / secret 双向 grep / 重复 case 双向 grep / cache 完整性)
- 手动 ls -la 验证 7 个 NEW/GENERATED 文件
- 手动 3 个 smoke tests
- 手动检查 coordinator 调用点真在 dispatch_to_pane 内 (line 1426)

证据全部以 stdout 原文形式贴入本报告. 无静默跳过.
