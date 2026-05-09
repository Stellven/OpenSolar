# Implementation Plan — Solar KB Default Retrieval + Obsidian Seamless Sync

Sprint: sprint-20260508-solar-kb-obsidian-autouse
Source Design: sprint-20260508-solar-kb-obsidian-autouse.design.md
Source Contract: sprint-20260508-solar-kb-obsidian-autouse.contract.md
Created: 2026-05-08T07:05:00Z
Phase: planning_complete

## 0. 计划总览

- 三个独立切片 S1/S2/S3
- S1 + S2 **并行** 派给两个 builder，S3 串行（依赖 S1/S2 产物）
- 行数预算: ≤ 1100 行新增/修改 (单文件最大 ≤350 行，避免 Stop Rule "全 DB/vault 重写")
- p95 延迟硬上限: 800ms (UserPromptSubmit hook 路径)
- 默认上下文上限: 2000 chars
- 总工时估计: 6-8h（builder 并行下）

## 1. 交付切片顺序

### Slice 1 — Retrieval Hook + memory-influence Fix (并行，builder #1)

| Day | Step | 产出 | 验证 |
|-----|------|------|------|
| D1 | S1.1 创建 `solar-knowledge-context.py` 骨架 (CLI 解析 + JSON 输出) | `~/.solar/harness/lib/solar-knowledge-context.py` (≤300 行) | `python3 file --query x --json` 返回合法 JSON |
| D1 | S1.2 接 DB 检索 (fts_unified_search → cortex_sources LIKE 兜底 → evo_memory_semantic.value) | 同上扩展 | A1 verify 命令 |
| D1 | S1.3 加 `--fail-open` + 缺 DB 走空 hits | 同上扩展 | A6 verify |
| D1 | S1.4 写 hook wrapper `solar-knowledge-context.sh` (启发式 + timeout 0.8 + 静默 fail-open) | `~/.claude/hooks/solar-knowledge-context.sh` | `SOLAR_KB_CONTEXT=0 bash file` 输出空; 默认输出 `<solar-knowledge-context>` |
| D1 | S1.5 修 `memory-influence.sh` (`content`→`value` + SQL parens) | `~/.claude/hooks/memory-influence.sh` | A4 verify |
| D1 | S1.6 注册 hook 到 `~/.claude/settings.json` UserPromptSubmit (低优先级) | settings 增量补丁 | 新会话 prompt 注入可见 |

**S1 验收门**: A1 + A4 + A6 全过 → 报 builder #2 的 S2 已可独立合并。

### Slice 2 — Obsidian-to-Solar Indexing + Export Hardening (并行，builder #2)

| Day | Step | 产出 | 验证 |
|-----|------|------|------|
| D1 | S2.1 创建 `obsidian-vault-indexer.py` (frontmatter 解析 + manifest + sha1) | `~/.solar/harness/lib/obsidian-vault-indexer.py` (≤350 行) | `python3 file --vault /tmp/test --once` 写表 |
| D1 | S2.2 加表 `obsidian_vault_index` (CREATE IF NOT EXISTS) + 注册 fts_unified_search | 同上 + idempotent migration | `sqlite3 ... ".schema obsidian_vault_index"` |
| D1 | S2.3 改 `knowledge-sync.ts`: 加 `/Users/sihaoli/Knowledge` 为 first-class，调用 indexer.py | `~/.claude/core/cortex/knowledge-sync.ts` (diff ≤80 行) | A2 verify |
| D1 | S2.4 强化 `obsidian-wiki-bridge.sh`: 文档化 `--no-dispatch` `--since`，加 `.export-manifest.json` cursor，加 secret redaction (sk-/Bearer/api_key=) | `~/.solar/harness/integrations/obsidian-wiki-bridge.sh` (diff ≤120 行) | A3 verify |
| D1 | S2.5 提供 `solar-harness wiki sync-vault` 子命令 (一次性手动同步) | wiki cli 增量补丁 | `solar-harness wiki sync-vault --once` 输出 indexed_count |

**S2 验收门**: A2 + A3 全过 + 与 S1 无文件冲突。

### Slice 3 — Status + Automation + Tests/Docs (串行，依赖 S1+S2)

| Day | Step | 产出 | 验证 |
|-----|------|------|------|
| D2 | S3.1 扩展 `wiki-capture-server.py`: 加 `/healthz` + 在 `/status` 返回 `solar_kb` 和 `obsidian_sync` payload | `~/.solar/harness/integrations/wiki-capture-server.py` (diff ≤150 行) | A5 verify |
| D2 | S3.2 加内嵌 scheduler: 每 60s 调用 indexer (idle-only，不阻塞 capture/upload) | 同上扩展 | `tail -f` log 看到 60s tick |
| D2 | S3.3 写测试 `test-solar-kb-obsidian-autouse.sh` 覆盖 A1-A7，全部 mktemp 临时 DB/vault | `~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh` (≤250 行) | A7 verify |
| D2 | S3.4 写 runbook `solar-kb-obsidian-autouse.md` (install/verify/disable/repair/troubleshoot) | `~/.solar/harness/docs/solar-kb-obsidian-autouse.md` (≤180 行) | grep '## Disable\|## Repair' 命中 |

**S3 验收门**: A5 + A7 + 文档完整 → 整 sprint Done。

## 2. 文件级写入范围 (Disjoint Write Set)

| Builder | 拥有的文件 | 严禁触碰的文件 |
|---------|------------|----------------|
| **Builder #1 (Slice 1)** | `~/.solar/harness/lib/solar-knowledge-context.py`<br>`~/.claude/hooks/solar-knowledge-context.sh`<br>`~/.claude/hooks/memory-influence.sh`<br>`~/.claude/settings.json` (增量补丁) | `knowledge-sync.ts`、`obsidian-wiki-bridge.sh`、`wiki-capture-server.py`、`obsidian-vault-indexer.py` |
| **Builder #2 (Slice 2)** | `~/.solar/harness/lib/obsidian-vault-indexer.py`<br>`~/.claude/core/cortex/knowledge-sync.ts`<br>`~/.solar/harness/integrations/obsidian-wiki-bridge.sh`<br>`~/.solar/harness/solar-harness.sh` (wiki sync-vault 子命令) | `solar-knowledge-context.py`、`*.hooks/*`、`wiki-capture-server.py` |
| **Builder #3 / 续接 (Slice 3)** | `~/.solar/harness/integrations/wiki-capture-server.py`<br>`~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh`<br>`~/.solar/harness/docs/solar-kb-obsidian-autouse.md` | S1/S2 已交付的文件（仅读，不改） |

**冲突协议**: 两个 builder 不得同时修改 `~/.solar/harness/solar-harness.sh`。S2 拿写权（添加 `wiki sync-vault`），S3 阶段如需暴露 `kb-status` CLI，加在 S2 builder 完成 commit 之后。

## 3. 并发边界

- S1 + S2 同时跑：write set disjoint，各自独立 commit。
- S3 等 S1+S2 都返回 PASS 后启动（依赖 S1 的 lib 和 S2 的表才能完整测试）。
- DB 写入：所有 INSERT/UPDATE 走 `PRAGMA busy_timeout=200` + 单写者，避免 BUSY。
- FTS 表注册：S2 indexer 是唯一写 `obsidian_vault_index` 的进程；S1 router 只读。
- 测试 (S3) 用 `mktemp -d` 临时 DB/vault，**绝不**碰 `~/.solar/solar.db` 或 `/Users/sihaoli/Knowledge`。

## 4. 验证命令 (合约 A1-A7 对应)

```bash
# A1 — Default Solar KB Context Is Real
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "Solar 记忆系统" --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"] and d["elapsed_ms"] < 800, d'

# A2 — Obsidian Vault Indexed Into Solar Search
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "orbital data center Lumen Orbit" --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert any("Knowledge" in (h.get("source","")+h.get("path","")) for h in d["hits"]), d'

# A3 — DB → Obsidian Incremental
solar-harness wiki import-solar-db --scope solar --per-table-limit 3 --no-dispatch
test -d /Users/sihaoli/Knowledge/_raw/solar-db-export

# A4 — memory-influence.sh fix
bash -n ~/.claude/hooks/memory-influence.sh
sqlite3 ~/.solar/solar.db "select value from evo_memory_semantic limit 1;" >/dev/null

# A5 — Status JSON
curl -fsS http://127.0.0.1:8765/healthz >/dev/null
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "solar_kb" in d and "obsidian_sync" in d'

# A6 — Fail-Open
SOLAR_DB=/tmp/missing-solar.db \
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "test" --fail-open --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"] == []'

# A7 — Regression Suite
bash ~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh
```

辅助验证（推荐，不强制）:

```bash
# 延迟回归: p95 < 800ms (跑 50 次)
for i in $(seq 50); do
  python3 ~/.solar/harness/lib/solar-knowledge-context.py --query "Solar" --json \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["elapsed_ms"])'
done | sort -n | awk 'NR==48 {print "p95:", $1}'

# Schema 兼容
sqlite3 ~/.solar/solar.db ".schema obsidian_vault_index"
sqlite3 ~/.solar/solar.db "select count(*) from obsidian_vault_index;"

# Hook 注入可见 (新 Claude 会话)
echo "Solar 记忆系统怎么工作的？" | bash ~/.claude/hooks/solar-knowledge-context.sh
```

## 5. No-Live-Pane-Mutation 保护

测试与开发**绝不**碰真实 tmux session、真实 DB、真实用户 vault：

| 资源 | 测试期替代 | 保护机制 |
|------|------------|----------|
| `~/.solar/solar.db` | `mktemp -d`/test.db (CREATE TABLE + 注入 fixture) | env `SOLAR_DB=$TMPDB` 重定向；router 读此 env |
| `/Users/sihaoli/Knowledge` | `mktemp -d`/vault | env `OBSIDIAN_VAULT_PATH=$TMP` 重定向 |
| tmux pane (solar-harness:0.x) | `SESSION_NAME=mock-kb-${RANDOM}` mock session | dispatch 调用必须 `DISPATCH_MOCK=1` |
| port 8765 (status server) | port 8800-8899 范围 (临时端口) | env `WIKI_CAPTURE_PORT=$port` 重定向；测试结束 kill |
| `~/.solar/state/knowledge-manifest.json` | `$TMPDIR/manifest.json` | env `SOLAR_KB_MANIFEST=$path` 重定向 |
| capture-server scheduler | `--once` 模式或 `SCHEDULER_DISABLED=1` | 测试用一次性扫描，不开 60s 循环 |

**测试自检清单** (`test-solar-kb-obsidian-autouse.sh` 必须包含):
```bash
trap 'rm -rf "$TMPDIR" 2>/dev/null; pkill -f "$TEST_SCHED_PID" 2>/dev/null' EXIT
test -z "$SOLAR_DB" && export SOLAR_DB="$TMPDIR/solar.db"
test -z "$OBSIDIAN_VAULT_PATH" && export OBSIDIAN_VAULT_PATH="$TMPDIR/vault"
[[ "$SOLAR_DB" == "$HOME/.solar/solar.db" ]] && { echo "REFUSE: pointing at real DB"; exit 1; }
[[ "$OBSIDIAN_VAULT_PATH" == "/Users/sihaoli/Knowledge" ]] && { echo "REFUSE: pointing at real vault"; exit 1; }
```

## 6. Rollback / Stop Rules

### 6.1 Per-Slice Rollback

| Slice | 回滚命令 | 恢复点 |
|-------|----------|--------|
| S1 | `rm ~/.solar/harness/lib/solar-knowledge-context.py ~/.claude/hooks/solar-knowledge-context.sh` + 恢复 `memory-influence.sh.bak` + 改 settings.json 删 hook 注册 | hook 不再注入，回到当前行为 |
| S2 | `sqlite3 ~/.solar/solar.db "DROP TABLE obsidian_vault_index"` + git checkout `knowledge-sync.ts obsidian-wiki-bridge.sh` | vault 不再被索引；导出仍可用旧路径 |
| S3 | git checkout `wiki-capture-server.py`; 删 tests/docs 文件 | status JSON 回退到旧字段；scheduler 关闭 |

每个 slice 完成前先 `cp <file> <file>.bak.$(date +%s)`，保留 7 天。

### 6.2 一键紧急回滚

```bash
# 关 hook，不影响 sprint 结构
echo "SOLAR_KB_CONTEXT=0" >> ~/.zshrc

# 关 scheduler 不重启 capture-server
curl -X POST http://127.0.0.1:8765/_internal/scheduler/disable

# 完整回滚（保留数据，仅停服务）
~/.solar/harness/docs/solar-kb-obsidian-autouse.md  # 见 ## Disable 段落
```

### 6.3 Stop Rules (来自合约 + 加固)

合约原则:
1. UserPromptSubmit hook 增加 >800ms p95 延迟 → STOP
2. 默认注入 >2000 chars → STOP
3. 生成 Obsidian 页面含 secrets → STOP
4. Builder 提议全 DB/vault 重写 → STOP
5. status server 引外部依赖或绑非 127.0.0.1 → STOP

规划者补充:
6. 单文件 >350 行 → 拆，否则 STOP（避免维护负担）
7. 跑 A7 测试期间触碰真实 DB/vault → 立即 STOP + git reset
8. S1+S2 出现写文件交集 → STOP，规划者重新切片
9. 任何 hook 在干净环境（缺 DB）下 exit code != 0 → STOP（违反 fail-open）

## 7. Master Brain Escalation Conditions

任一触发 → builder 暂停，回报规划者：

1. `obsidian_vault_index` 字段争议 (新增列 vs 现有字段复用)
2. FTS5 中文分词不命中 `Lumen Orbit` 等中英混合查询 (A2 失败)
3. p95 延迟超 800ms 且无法通过 timeout 切断
4. capture-server scheduler 与 raw scanner 时序冲突
5. settings.json hook 注册顺序导致循环或重复注入
6. `evo_memory_semantic.value` 是 JSON，需要确定提取键策略
7. Obsidian 页缺 frontmatter 时降级策略不明
8. 与未结 sprint (Sprint 2 D6) pane 冲突
9. GLM 1210 复发挡住 builder（沿用 SOLAR_NO_ZHIPU=1 + Sonnet）

## 8. 实现者提醒 (Builder Hints)

### 8.1 Python 部分
- **stdlib only**: `sqlite3`, `json`, `argparse`, `re`, `time`, `pathlib`, `hashlib`, `os`, `sys`
- **不引** `chromadb`, `sentence-transformers`, `tantivy`, `whoosh`
- **冷启动优化**: 避免 import 重型模块；解析 frontmatter 用正则不用 `python-frontmatter`
- **DB 连接**: `sqlite3.connect(db, timeout=0.2)` + `PRAGMA query_only=1` (router) 防意外写

### 8.2 Bash 部分
- **shebang**: `#!/usr/bin/env bash` 走 PATH 优先 5.x（昊哥已装 5.3.9 在 /opt/homebrew/bin）
- **fail-open**: 所有 hook 用 `set +e` + 显式 `exit 0`
- **timeout**: macOS 用 `gtimeout` (coreutils) 或 `( cmd & PID=$!; sleep 0.8; kill $PID 2>/dev/null )` 兜底
- **stderr 静默**: hook stderr 必须 `2>/dev/null`，prompt 流不允许出现栈

### 8.3 TypeScript 部分
- `knowledge-sync.ts` 已存在 16KB，仅扩展不重写
- 用现有 `bun` runtime（已在 STATE 配置）
- 调用 `obsidian-vault-indexer.py` 走 `Bun.spawn` 或 `child_process.spawn`，不内联实现

### 8.4 SQL 部分
- `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` 幂等
- FTS5 注册用 `INSERT OR REPLACE INTO fts_unified_search`
- 删除用软删（`deleted_at` 标记）而非 DELETE，便于回放

## 9. Definition of Done 映射

| 合约 Done | Plan 步骤 | 验收命令 |
|-----------|-----------|----------|
| A1 默认检索 | S1.1 + S1.2 + S1.4 | `solar-knowledge-context.py --query "Solar 记忆系统" --json` |
| A2 vault 索引 | S2.1 + S2.2 + S2.3 | `solar-knowledge-context.py --query "Lumen Orbit" --json` 含 Knowledge 路径 |
| A3 DB→vault 增量 | S2.4 | `solar-harness wiki import-solar-db --no-dispatch` |
| A4 memory-influence 修 | S1.5 | `bash -n` + 字段 select |
| A5 status JSON | S3.1 + S3.2 | `curl /healthz` + `/status` payload |
| A6 fail-open | S1.3 + 全 hook | `SOLAR_DB=/tmp/missing` 测 |
| A7 回归测试 | S3.3 | `bash test-*.sh` |

## 10. Builder Dispatch Plan (协调器协同)

**前置检查** (规划者写完 plan 后协调器自动跑):
```bash
solar-harness coord-status --json | jq '.active_panes'
# 若 pane 0.1/0.2 仍被 sprint-20260507-symphony3 / sprint-20260507-obsidian-wiki / mlsys 占着 → 等待 finalize
```

**派发顺序**:
1. 协调器读 status.json (status=active, handoff_to=builder_main, phase=planning_complete)
2. 派 dispatch.md 到 pane 0.1 (builder #1) — 只允许碰 S1 文件集
3. 派 dispatch.md 到 pane 0.2 (builder #2) — 只允许碰 S2 文件集
4. S1 + S2 全 PASS + commit → 派 dispatch.md 到 pane 0.1 或 0.2 (builder #3) 跑 S3
5. S3 PASS → handoff_to=evaluator → 审判官 (deepseek-r1) 跑 A1-A7 全套
6. eval verdict=PASS → status=passed → 协调器写 brain-whisper

**Builder 接到 dispatch 必须**:
- 读 `plan.md` 完整 7-9 节
- 确认自己的 write set（不许越界）
- 用 `--accept-edits on` 自驱完成 slice
- commit 信息格式: `feat(kb): S<n> <step-id> — <一句话>`
- 完成后写 `<sid>.handoff.md` 给评估者

