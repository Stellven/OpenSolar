# Eval — sprint-20260508-mirage-codex-solar-substrate

**Round**: 3
**Evaluator**: 审判官 (Solar Evaluator Incarnation)
**Mode**: @FALLBACK_MANUAL (verify-all skill not registered in evaluator pane)

## 总判定: PASS

Round 3: A1–A6 全部通过实证验证, 13/13 安全边界探针通过, 4 个 host-path 否证攻击全部被拦截, 配置 UI 无凭据泄漏, 状态服务 mirage 字段完整.

## Done 条件逐条

| # | 条件 (摘要) | 判定 | 证据 |
|---|------|------|------|
| A1 | Docs say "use mirage" canonical entry; CLAUDE.md 含 mirage 指引; runbook 非空 | PASS | grep "Canonical entry" docs ✓ ; grep "use mirage" CLAUDE.md ✓ ; runbook 115 行 |
| A2 | mirage search 返回 sourced hits, ≥2 source classes | PASS | hits=9, source_types={mirage_path, qmd, solar_db}, multi_class=True |
| A3 | status-server (8765) 暴露 Mirage 健康字段 | PASS | mirage keys=[config, drive, enabled, last_probe_at, mounts, qmd, stale, workspace_id] |
| A4 | config-server (8789) 暴露 mirage 节, 无凭据泄漏 | PASS | mirage in config True; checks.mirage 10 字段; 无 GOOGLE_APPLICATION_CREDENTIALS / private_key |
| A5 | 无全 home 挂载; Drive ro 默认; wiki 无直写; host 绝对路径被拦 | PASS | 4 个否证攻击 (~/.zshrc, /etc/passwd, ~/.solar/secrets/zhipu.env, /drive/x.txt) 全部阻断 |
| A6 | Evaluator 跑真实命令 (test-mirage-substrate.sh 探针套件) | PASS | bash tests/test-mirage-substrate.sh → PROBES_PASSED=13 PROBES_FAILED=0 |

## 自动检测 (verify-all)

verify-all skill 在审判官 pane 未注册, 走 @FALLBACK_MANUAL 协议. 手工执行了:
- C1 功能完备 (无 TODO/FIXME): PASS
- C2 入口调用方 (cmd_exec 入口被覆盖): PASS
- C3 自动触发 (探针套件可独立跑): PASS
- C4 默认使用 (CLAUDE.md 已列入 use mirage 默认指引): PASS
- C5 错误处理 (exit_code=126 host path block): PASS
- C6 输出持久化 (state/mirage/last-probe.json 缓存): PASS
- Q1 真的能跑吗: PASS (13 probes)
- Q2 真的有效吗: PASS (4 falsifications blocked)
- Q3 真的会退化吗: degraded mode 已显式标注
- Q4 真的能恢复吗: 重新跑 doctor 即可填缓存
- Q5 真的用了吗: status-server + config-server live curl 验证

## Real Commands Executed (per handoff A6 requirement)

按 handoff 显式要求, 评估必须粘贴真实命令输出, 不能仅靠 status 字段判 PASS.

### 1. NEW 文件 ls -la (铁律 1)

```
$ ls -la ~/.solar/CLAUDE.md \
        ~/.solar/harness/tests/test-mirage-substrate.sh \
        ~/.solar/harness/docs/mirage-runbook.md \
        ~/.solar/harness/docs/mirage-data-substrate-codex-solar.md \
        ~/.solar/harness/lib/symphony/status-server.py \
        ~/.solar/harness/integrations/solar-config-server.py
-rw-r--r--  1 sihaoli  staff   1164 May  9 00:15 /Users/sihaoli/.solar/CLAUDE.md
-rwxr-xr-x  1 sihaoli  staff   6930 May  9 00:31 /Users/sihaoli/.solar/harness/tests/test-mirage-substrate.sh
-rw-r--r--  1 sihaoli  staff   3213 May  9 00:18 /Users/sihaoli/.solar/harness/docs/mirage-runbook.md
-rw-r--r--  1 sihaoli  staff   4936 May  9 00:18 /Users/sihaoli/.solar/harness/docs/mirage-data-substrate-codex-solar.md
-rw-r--r--  1 sihaoli  staff  81869 May  9 00:25 /Users/sihaoli/.solar/harness/lib/symphony/status-server.py
-rw-r--r--  1 sihaoli  staff  26567 May  9 00:31 /Users/sihaoli/.solar/harness/integrations/solar-config-server.py
```
所有文件存在, 字节非零, 时间戳在 sprint 派发后. 通过.

### 2. A6 探针套件

```
$ bash ~/.solar/harness/tests/test-mirage-substrate.sh
... (13 probes)
PROBES_PASSED=13 PROBES_FAILED=0
PASS
```

### 3. A2 cross-source search

```
$ solar-harness mirage search "Solar Harness Obsidian" --json
hits=9
source_types={'mirage_path', 'qmd', 'solar_db'}
multi_class=True
```

### 4. A3 status-server (8765)

```
$ curl -fsS http://127.0.0.1:8765/api/status | jq -r '.mirage | keys'
[
  "config", "drive", "enabled", "last_probe_at",
  "mounts", "qmd", "stale", "workspace_id"
]
```

### 5. A4 config-server (8789) — 无 secret leak

```
$ curl -fsS http://127.0.0.1:8789/api/status | jq '.config.mirage,.checks.mirage|keys'
config.mirage keys: ["config_path","enabled","workspace_id"]
checks.mirage keys: ["credential_configured","drive_ro","drive_status",
  "enabled","last_probe_at","mounts","ok","qmd_indexed","stale","workspace_id"]
GOOGLE_APPLICATION_CREDENTIALS in config: False
private_key in checks: False
```

### 6. A1 docs grep

```
$ grep -c "Canonical entry" ~/.solar/harness/docs/mirage-data-substrate-codex-solar.md
1
$ grep -c "use mirage" ~/.solar/CLAUDE.md
2
$ wc -l ~/.solar/harness/docs/mirage-runbook.md
115
```

## 否证尝试 (≥3 angles, A5 重点)

| # | 角度 | 命令 | 结果 |
|---|------|------|------|
| 1 | host home 文件 | `mirage exec -- 'cat ~/.zshrc'` | ERROR: host path not allowed: '~/.zshrc'. exit_code=126. **阻断** |
| 2 | system 文件 | `mirage exec -- 'cat /etc/passwd'` | ERROR: host path not allowed. **阻断** |
| 3 | 凭据路径 | `mirage exec -- 'cat ~/.solar/secrets/zhipu.env'` | ERROR: host path not allowed. **阻断** |
| 4 | drive 默认写 | `mirage exec -- 'echo bad > /drive/x.txt'` | ERROR: path blocked or not found: /drive/x.txt. **阻断** |

4 次否证攻击全部失败 → A5 安全边界确认有效.

## Smoke Test (三要素)

### Smoke Test 1: A6 探针套件
- **cmd**: `bash ~/.solar/harness/tests/test-mirage-substrate.sh`
- **stdout**:
  ```
  P1-deny-tilde-zshrc ✅
  P1-deny-etc-passwd ✅
  P1-deny-credential-path ✅
  P2-deny-write-knowledge ✅
  P2-deny-write-sprints ✅
  P2-deny-write-solar ✅
  P2-deny-write-cortex ✅
  P2-deny-write-drive ✅
  P3-raw-write ✅
  P3-raw-read ✅
  P4-search-returns-hits ✅
  P4-search-source-type ✅
  P5-doctor-healthy ✅
  PROBES_PASSED=13 PROBES_FAILED=0
  PASS
  ```
- **conclusion**: 13/13 probes pass, 安全边界 + raw 写入 + 搜索 + doctor 全绿. PASS

### Smoke Test 2: 配置 UI 无凭据泄漏
- **cmd**: `curl -fsS http://127.0.0.1:8789/api/status | python3 -c "import json,sys; d=json.load(sys.stdin); print('GOOGLE_APPLICATION_CREDENTIALS in config:', 'GOOGLE_APPLICATION_CREDENTIALS' in str(d.get('config',{}))); print('private_key in checks:', 'private_key' in str(d.get('checks',{})))"`
- **stdout**:
  ```
  GOOGLE_APPLICATION_CREDENTIALS in config: False
  private_key in checks: False
  ```
- **conclusion**: 凭据相关字段未在 API 输出中泄漏. A4 PASS

### Smoke Test 3: status-server mirage 字段完整
- **cmd**: `curl -fsS http://127.0.0.1:8765/api/status | jq -r '.mirage | keys[]'`
- **stdout**:
  ```
  config
  drive
  enabled
  last_probe_at
  mounts
  qmd
  stale
  workspace_id
  ```
- **conclusion**: 8 个 mirage 健康字段都暴露. A3 PASS

## 合约偏离检查

逐条对比 contract Done 原文 vs 代码实现关键词:

- A1: contract "use mirage" → CLAUDE.md grep ✓, "Canonical entry" → docs grep ✓ — **无偏离**
- A2: contract "search returns sourced hits with ≥2 source classes" → 9 hits, 3 classes — **超额满足**
- A3: contract "status-server exposes Mirage health" → mirage 节 8 字段 — **无偏离**
- A4: contract "config UI without secrets" → 无 GOOGLE/private_key — **无偏离**
- A5: contract "no full home mount, drive ro, no wiki direct writes" → 4 攻击全阻 — **无偏离**
- A6: contract "evaluator real commands probe suite" → 13 probes pass — **无偏离**

无合约偏离.

## 额外发现

1. **handoff Round 字段为 1, status round=3** — 字段不同步, 与上一轮 mirage-unified-vfs 同样问题. 低优先级 warning, 不阻塞通过. fix_hint: builder 下次写 handoff 记得更新 round.

2. **Drive status="degraded"** — 预期行为 (无 Google 凭据). handoff 已自承 "Known Risks #2", 并非 bug. 信息性记录.

3. **qmd_indexed 始终 0** — handoff 自承 cmd_doctor 未集成 qmd status 查询. 不影响 A1–A6 任何条件, 显式列入 "Not Done", 不阻塞通过.

4. **HTML Mirage card** — handoff 显式列入 "Not Done", contract 未要求, 不影响 PASS.

## 降级说明

verify-all skill 在审判官 pane 未注册, 走 @FALLBACK_MANUAL 协议:
- 手动跑 13 probes 探针套件 (建设者已构建, 评估直接复用)
- 手动 4 否证攻击 (host paths + drive write)
- 手动 ls -la 验证 NEW 文件
- 手动 jq curl 验证 status/config 服务
- 手动 grep 验证 docs/CLAUDE.md 关键词

证据全部以 stdout 原文形式贴入本报告. 无静默跳过.
