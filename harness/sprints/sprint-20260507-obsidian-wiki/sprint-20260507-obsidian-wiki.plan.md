# Sprint Plan — sprint-20260507-obsidian-wiki

Source: contract.md + product-brief.md + design.md (2026-05-07T20:31:16Z)
Author: planner (claude-opus)
Created: 2026-05-07T20:36:00Z (planning_complete)
Concurrent Sprint: sprint-20260507-symphony3 (active, planning_complete)

## 0. Plan 总览

**集成对象**: Ar9av/obsidian-wiki (markdown skill framework for Obsidian LLM Wiki)
**集成性质**: thin integration layer, NOT 重写 / NOT vendor copy upstream skills
**核心约束**:
- 总实现 ≤ 900 行 (≥ 即触发 STOP rule, 拆 sprint)
- shell + Python stdlib only (无 pip / 无 npm)
- 非交互安装 (上游 setup.sh 是交互式, 必须绕过)
- 安全 symlink (绝不覆盖真实目录)
- 温和降级 (status-server 在 wiki 未配置时 warn, 不 fatal)
- **绝不污染 live solar-harness session**, 也不抢占 symphony3 builder pane

**5 切片排序** (与 contract D1-D8 对齐):
| Slice | Day | DoD 映射 | 风险等级 |
|-------|-----|----------|---------|
| S1 安装器 + 健康检查 | Day 1 | D1 (lint), D2 (install), D3 (status), D7 (safety) | 中 (symlink 边界) |
| S2 导出 sprint | Day 2 上午 | D4 (export-sprint redact) | 低 (纯文本生成) |
| S3 update/query 桥接 | Day 2 下午 | D5 (bridge refuse empty) | 低 (生成 dispatch 指令文件) |
| S4 status-server 集成 | Day 3 上午 | D6 (status server wiki block) | 中 (不破坏 symphony3 S4-S5) |
| S5 文档 + 测试收尾 | Day 3 下午 | D8 (≥5 examples), 全测试 | 低 |

**与 symphony3 的协同**:
- symphony3 正在做 status-server (S4-S5), 本 sprint 在 status-server 完成后再插 wiki readiness 块
- 如 symphony3 status-server 还没合入主干 → 本 sprint S4 用 stub (写 wiki readiness JSON 文件, 等 symphony3 合并后由 builder 接入 server)
- builder pane 抢占协议: 本 sprint 派工到 builder_main (sonnet), 但 sonnet 必须先 check `solar-harness coord-status` 看 symphony3 是否在 reviewing 阶段; 若 reviewing → wait or queue, 不抢

## 1. 交付切片顺序 (S1-S5, Day-aligned)

### S1 — 安装器 + 健康检查 + 安全 symlink (Day 1, 6h)
**目标**: 非交互安装, 配置 vault 骨架, 安全装 skills 软链.
**文件**:
- 新增 `~/.solar/harness/integrations/obsidian-wiki.sh` (~280 行)
- 新增 `~/.solar/harness/schemas/obsidian-wiki-status.schema.json` (~40 行 JSON Schema)
- 修改 `~/.solar/harness/solar-harness.sh` (添加 `wiki` 子命令路由, ~30 行 dispatch table)

**S1 实现要点**:
1. `wiki install --vault <path> [--repo <path>] [--refresh]`:
   - `--vault` 必填; `--repo` 默认 `~/.solar/harness/vendor/obsidian-wiki`
   - 如 `--repo` 不存在 → `git clone https://github.com/Ar9av/obsidian-wiki <repo>`
   - 如 `--refresh` → `git -C <repo> pull --ff-only` (失败容错: 不阻塞 install)
   - 写 `~/.obsidian-wiki/config`:
     ```
     OBSIDIAN_VAULT_PATH=<vault>
     OBSIDIAN_WIKI_REPO=<repo>
     ```
   - 创建 vault 骨架: `index.md / log.md / hot.md / .manifest.json / _raw/ / projects/ / concepts/ / entities/ / skills/ / references/ / synthesis/ / journal/`
   - **safe_symlink** 函数 (核心安全边界):
     ```bash
     safe_symlink() {
       local src="$1" dst="$2"
       if [[ -L "$dst" ]]; then ln -sfn "$src" "$dst"; return 0; fi
       if [[ -e "$dst" ]]; then echo "REFUSE: $dst exists as real dir/file"; return 1; fi
       mkdir -p "$(dirname "$dst")"
       ln -s "$src" "$dst"
     }
     ```
   - skill 目标: `~/.codex/skills`, `~/.claude/skills`, `~/.agents/skills` (各自下挂 `<repo>/.skills/wiki-*`)
2. `wiki status [--json]`:
   - 检查: repo 存在 / config 文件 / vault 骨架完整 / skills symlink 有效
   - JSON 输出: `{configured, repo_path, vault_path, config_path, skills_installed: {codex, claude, agents}, last_exported_sprint, last_checked_at}`
   - JSON schema validate: 用 schemas/obsidian-wiki-status.schema.json
3. **D7 safety**: install 测试用例必须 mock `~/.codex/skills` 为 real dir, 验证 install 拒绝写入并 return 非零

**验证**:
```bash
bash -n ~/.solar/harness/integrations/obsidian-wiki.sh
bash -n ~/.solar/harness/solar-harness.sh    # D1
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh install   # D2
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh status    # D3
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh safety    # D7
```

### S2 — Export Sprint (Day 2 上午, 3h)
**目标**: 把 sprint 工件提取为 wiki raw markdown, 默认 redact.
**文件**: `integrations/obsidian-wiki.sh` (扩展 export-sprint 函数, ~120 行)

**S2 实现要点**:
- `wiki export-sprint <sid> [--redact|--full]` (默认 --redact)
- 输入: sprint dir 下的 `<sid>.{contract,plan,handoff,eval,status,events.jsonl}.md|json`
- 输出: `$OBSIDIAN_VAULT_PATH/_raw/solar-harness/<sid>.md`
- Frontmatter:
  ```yaml
  ---
  source: solar-harness
  sprint_id: <sid>
  exported_at: ISO8601
  redacted: true|false
  visibility: internal
  ---
  ```
- 内容段: contract 摘要 + plan 摘要 + handoff 摘要 + eval verdict + status 当前态 + events 计数(by event type) + 选定结构化事件 (max 20)
- **Redact 规则** (--redact 模式):
  - 凭证模式: `(token|key|secret|password|api[_-]?key)\s*[=:]\s*\S+` → `<REDACTED>`
  - Bearer/Basic Auth header → `<REDACTED>`
  - 长度 ≥ 32 hex/base64 串 → `<REDACTED>`
  - 终端 transcript 段 (events payload 中 stdout/stderr) → 仅保留头 200 字 + `[...truncated, see live log]`
- `--full` 模式: 跳过 redact, 但仍删 .events.jsonl 中 binary blob (>10KB payload 截断)
- 写完后 status.json 的 `last_exported_sprint` 更新

**验证**:
```bash
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh export   # D4
# 手动验证 redact:
solar-harness wiki export-sprint sprint-20260507-symphony3 --redact
grep -E "(token|secret|api_key)\s*[=:]" "$OBSIDIAN_VAULT_PATH/_raw/solar-harness/sprint-20260507-symphony3.md" | grep -v REDACTED   # 必须空
```

### S3 — Update/Query Bridge (Day 2 下午, 3h)
**目标**: 生成 agent-readable 指令文件 (不直接调用上游 skill, 让 agent skill 系统跑).
**文件**: `integrations/obsidian-wiki.sh` (扩展 update/query 函数, ~80 行)

**S3 实现要点**:
- `wiki update [--project <path>] [--mode append|full]`:
  - 写指令文件 `$OBSIDIAN_VAULT_PATH/_raw/solar-harness/.dispatch/wiki-update-<ts>.md`
  - 内容: instructs agent (claude/codex) 调 `wiki-update` skill, 含 project path + mode 参数
  - 不直接派发到 tmux pane (避免抢占 symphony3 builder)
  - 输出指令文件路径 + 提示: "Run via: claude --skill wiki-update < <path>" 或类似
- `wiki query "<question>" [--quick]`:
  - **拒绝空字符串**: `[[ -z "$question" ]] && { echo "REFUSE: empty query"; exit 2; }`
  - 写指令文件 `<vault>/_raw/solar-harness/.dispatch/wiki-query-<ts>.md`
  - --quick: 加 `mode=quick` 标记 (限制深度搜索)
  - 输出文件路径

**验证**:
```bash
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh bridge   # D5
# 拒绝空 query:
solar-harness wiki query ""; echo $?   # 必须非零 (2)
```

### S4 — Status Server 集成 (Day 3 上午, 3h)
**目标**: HTTP /status 加 obsidian_wiki readiness 块, 缺失时 warn 不 fatal.
**文件**:
- 修改 `lib/symphony/status-server.py` (添加 wiki readiness handler, ~50 行)
- 依赖: symphony3 status-server (S4-S5) 已合入

**S4 实现要点**:
- 在 `/status` JSON 返回中加:
  ```json
  {
    "obsidian_wiki": {
      "ready": true|false,
      "configured": true|false,
      "vault_path": "...",
      "issues": ["repo missing", "vault skeleton incomplete", ...]
    }
  }
  ```
- 实现路径:
  - 调用 `solar-harness wiki status --json` (subprocess), 解析其输出
  - 如 wiki integration 文件不存在 → `{ready: false, configured: false, issues: ["integration not installed"]}`, 状态 200 (不 500)
  - subprocess timeout 2s, 超时 → `{ready: false, issues: ["status check timeout"]}`
- HTML 仪表盘: 在 panes 块下方加 wiki status 一行 (绿/黄/红 dot)
- **降级铁律**: status-server 主流程绝不因 wiki 不存在而崩, 任何异常都回落到 `ready: false + issues`

**关键依赖检测**:
```bash
# 进入 S4 前检查 symphony3 status-server 是否已合入主干
test -f ~/.solar/harness/lib/symphony/status-server.py && grep -q "GET /status" ~/.solar/harness/lib/symphony/status-server.py
# 如未合入: 写 stub `~/.solar/harness/run/wiki-readiness.json`, 文档说明等 symphony3 落地后由 builder 二次接入
```

**验证**:
```bash
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh status_server   # D6
# 缺失场景验证:
# 故意未 install wiki, status-server 仍能返回, obsidian_wiki.ready = false
curl -s http://127.0.0.1:8765/status | jq '.obsidian_wiki.ready'   # false (不报错)
```

### S5 — 文档 + 测试 + 收尾 (Day 3 下午, 3h)
**目标**: 文档 + 全测试 + 审判官 eval-ready.
**文件**:
- 新增 `~/.solar/harness/test-obsidian-wiki-integration.sh` (~250 行, 7 子命令: install/status/export/bridge/status_server/safety/all)
- 新增 `~/.solar/harness/docs/obsidian-wiki-integration.md` (≥ 5 examples, ~150 行)

**S5 实现要点**:
1. **测试脚本** `test-obsidian-wiki-integration.sh`:
   - HARNESS_TEST=1 + temp vault (`mktemp -d -t solar-wiki-test`)
   - 子命令分发: `install / status / export / bridge / status_server / safety / all`
   - **绝不动真实 vault**: 强制检查 `[[ "$OBSIDIAN_VAULT_PATH" == /tmp/* || "$OBSIDIAN_VAULT_PATH" == /var/* ]]`, 否则 REFUSE
   - **绝不动真实 skill 目标**: mock 用 `$TMPDIR/test-codex/skills` 等
   - trap EXIT 清 temp 目录
2. **文档** `docs/obsidian-wiki-integration.md`:
   - §概述 (集成动机)
   - §先决条件 (git, Python 3.10+, Obsidian app 可选)
   - §快速开始 (3 步: clone / install / status)
   - §### Example 1: 首次安装到默认路径
   - §### Example 2: 自定义 vault + 自定义上游 repo
   - §### Example 3: 导出当前 sprint 到 wiki (redacted)
   - §### Example 4: 触发 wiki update 给 codex 处理
   - §### Example 5: 查询 wiki (--quick 模式)
   - §故障排查 (symlink 拒绝 / repo clone 失败 / vault skeleton 修复)
   - §安全模型 (redact 规则 / temp vault / no real dir overwrite)
   - §与 symphony status-server 集成

**验证**:
```bash
test -f ~/.solar/harness/docs/obsidian-wiki-integration.md
grep -c '^### Example' ~/.solar/harness/docs/obsidian-wiki-integration.md   # >= 5 (D8)
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh all   # 全 PASS
# 行数检查 (Stop rule):
wc -l ~/.solar/harness/integrations/obsidian-wiki.sh ~/.solar/harness/lib/symphony/status-server.py | tail -1   # < 900
```

## 2. 文件级写入范围 (File-level Write Scope)

**新增 (5 文件, ~840 行)**:
| 文件 | 估计行数 | 切片 |
|------|---------|------|
| `integrations/obsidian-wiki.sh` | ~480 (S1: 280 + S2: 120 + S3: 80) | S1/S2/S3 |
| `schemas/obsidian-wiki-status.schema.json` | ~40 | S1 |
| `test-obsidian-wiki-integration.sh` | ~250 | S5 |
| `docs/obsidian-wiki-integration.md` | ~150 | S5 |
| `lib/symphony/status-server.py` (S4 添加块) | +50 | S4 |

**修改 (1 文件)**:
| 文件 | 改动范围 | 切片 |
|------|---------|------|
| `solar-harness.sh` | 添加 `wiki` 子命令路由 (~30 行 case 分支), 镜像现有 webhook/symphony 子命令模式 | S1 |

**Stop rule check**: 总新增/修改 ≈ 480 + 40 + 250 + 50 + 30 = 850 行, 留 50 行余量, 不触发 ≥900 行拆分.

## 3. 验证命令 (Verification Commands)

每个切片完成后必须能本地复现:

```bash
# === S1 (D1/D2/D3/D7) ===
# D1: lint
bash -n ~/.solar/harness/integrations/obsidian-wiki.sh
bash -n ~/.solar/harness/solar-harness.sh
echo "exit=$?"   # 0

# D2: install
TMPVAULT=$(mktemp -d -t solar-wiki-test)
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh install
test -f ~/.obsidian-wiki/config.test    # 测试用 .test 后缀避开真实 config
test -d "$TMPVAULT/_raw/solar-harness"
echo "exit=$?"   # 0

# D3: status JSON 合法
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh status
HARNESS_TEST=1 OBSIDIAN_VAULT_PATH="$TMPVAULT" \
  ~/.solar/harness/integrations/obsidian-wiki.sh status --json | \
  python3 -c 'import sys, json, jsonschema; \
    schema=json.load(open("/Users/sihaoli/.solar/harness/schemas/obsidian-wiki-status.schema.json")); \
    data=json.load(sys.stdin); jsonschema.validate(data, schema); print("OK")'
# 预期: "OK"

# D7: safety
TMPSKILLS=$(mktemp -d)
mkdir -p "$TMPSKILLS/codex/skills"   # mock real dir
HARNESS_TEST=1 SKILL_TARGETS_OVERRIDE="$TMPSKILLS/codex/skills" \
  bash ~/.solar/harness/test-obsidian-wiki-integration.sh safety
# 预期: install REFUSE + 测试 PASS

# === S2 (D4) ===
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh export
# 真实 sprint export (用现成 sprint):
HARNESS_TEST=1 OBSIDIAN_VAULT_PATH="$TMPVAULT" \
  ~/.solar/harness/integrations/obsidian-wiki.sh export-sprint sprint-20260507-symphony3 --redact
test -f "$TMPVAULT/_raw/solar-harness/sprint-20260507-symphony3.md"
head -20 "$TMPVAULT/_raw/solar-harness/sprint-20260507-symphony3.md" | grep -q "^source: solar-harness"
# Redact 验证:
grep -nE "(token|secret|api_key|password)[=:][^[:space:]]+" "$TMPVAULT/_raw/solar-harness/sprint-20260507-symphony3.md" | \
  grep -v "REDACTED" | wc -l   # = 0

# === S3 (D5) ===
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh bridge
# 拒绝空 query:
~/.solar/harness/integrations/obsidian-wiki.sh query ""; echo "exit=$?"   # 必须非零

# === S4 (D6) ===
# 前置: symphony3 status-server 已合入或 stub 模式
HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh status_server
# 真实 server 验证 (如已启动):
~/.solar/harness/solar-harness status-server start
sleep 2
curl -s http://127.0.0.1:8765/status | jq -e '.obsidian_wiki | has("ready")'   # true
# 缺失场景:
mv ~/.obsidian-wiki/config /tmp/config.bak 2>/dev/null
curl -s http://127.0.0.1:8765/status | jq '.obsidian_wiki.ready'   # false (server 不崩)
mv /tmp/config.bak ~/.obsidian-wiki/config 2>/dev/null

# === S5 (D8) + 全测试 ===
test -f ~/.solar/harness/docs/obsidian-wiki-integration.md
grep -c '^### Example' ~/.solar/harness/docs/obsidian-wiki-integration.md
# 预期: >= 5

HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh all
# 预期: 7/7 PASS

# 行数 stop rule
wc -l ~/.solar/harness/integrations/obsidian-wiki.sh \
      ~/.solar/harness/test-obsidian-wiki-integration.sh \
      ~/.solar/harness/docs/obsidian-wiki-integration.md \
      ~/.solar/harness/schemas/obsidian-wiki-status.schema.json
# 总和 < 900 (新增) + 50 (status-server.py 增量) + 30 (solar-harness.sh) ≈ 950 边界
# 实际 must check: integrations/obsidian-wiki.sh ≤ 600 lines
```

## 4. No-Live-Pane-Mutation Protection

**铁律**: 测试 / 调试 / 烟测 **绝不动 live solar-harness session**, 也不抢 symphony3 builder.

**HARNESS_TEST 模式契约**:
```bash
# 所有 test-*.sh 头部强制
[[ -z "$HARNESS_TEST" ]] && { echo "REFUSE: HARNESS_TEST=1 required"; exit 1; }
[[ "$SESSION_NAME" == "solar-harness" ]] && { echo "REFUSE: live session"; exit 1; }

# Vault 必须 temp
TMPVAULT=$(mktemp -d -t solar-wiki-test)
trap "rm -rf '$TMPVAULT'" EXIT
export OBSIDIAN_VAULT_PATH="$TMPVAULT"

# Config 必须 .test 后缀避开真实 ~/.obsidian-wiki/config
export OBSIDIAN_WIKI_CONFIG="$HOME/.obsidian-wiki/config.test"
trap "rm -f '$OBSIDIAN_WIKI_CONFIG'" EXIT

# Skill 目标必须 override 到 temp
TMPSKILLS=$(mktemp -d)
trap "rm -rf '$TMPSKILLS'" EXIT
export SKILL_TARGETS_OVERRIDE_CODEX="$TMPSKILLS/codex/skills"
export SKILL_TARGETS_OVERRIDE_CLAUDE="$TMPSKILLS/claude/skills"
export SKILL_TARGETS_OVERRIDE_AGENTS="$TMPSKILLS/agents/skills"
```

**HTTP server 隔离**:
- 测试 status-server 用临时端口 (8800-8899), 避开 8765 live
- 测试结束 trap EXIT 调 stop, 不留遗骸

**Repo clone 隔离**:
- 测试用 `--repo $TMPDIR/test-obsidian-wiki-clone`, 避开默认 `vendor/obsidian-wiki`
- 测试若需要离线: 提供 `OBSIDIAN_WIKI_OFFLINE=1` 跳过 clone, 用预置 fixture 目录

**Symphony3 builder pane 抢占防护**:
- 本 sprint **builder dispatch 必须 check** `solar-harness coord-status` (JSON), 解析 active sprints:
  ```bash
  active_sprints=$(solar-harness coord-status | jq -r '.active_sprints[]')
  for sid in $active_sprints; do
    phase=$(jq -r .phase ~/.solar/harness/sprints/$sid.status.json)
    [[ "$phase" == "reviewing" ]] && { echo "WAIT: $sid in reviewing, queue this sprint"; exit 0; }
  done
  ```
- 替代方案: 派工到 builder_parallel slot (glm-5.1+sonnet), 与 symphony3 main builder 不抢 pane
- 紧急 fallback: builder 拒绝接单 → 协调器进入 backoff, 30 分钟后重试

## 5. Rollback / Stop Rules

### 全局 Stop Rules (来自 contract)
- installer 能覆盖真实目录 → 立即 STOP, 重设计 symlink 逻辑
- 测试需要真实 user vault → 立即 STOP, 加 temp-vault mode
- 实现 > 900 行 → 立即 STOP, 拆 sprint
- status-server 因 wiki 缺失而 fail → 立即 STOP, 修降级路径

### Per-Slice Rollback
| 切片 | Rollback 策略 |
|------|--------------|
| S1 | `integrations/obsidian-wiki.sh` 整文件删除; `solar-harness.sh` wiki 子命令 case 段 git diff revert; schema 文件删除 — 不影响主路径 |
| S2 | export-sprint 函数段 revert (单文件单函数), unsetting last_exported_sprint — 不影响 install/status |
| S3 | update/query 函数段 revert, 无副作用 (没有真正执行, 只生成指令文件) — 删 dispatch 文件即可 |
| S4 | status-server.py wiki readiness handler 段 git diff revert; symphony3 status-server 主路径不受影响 |
| S5 | docs/test 单文件删除 — 不影响功能 |

### 紧急 Rollback (生产污染场景)
- **真实 ~/.obsidian-wiki/config 被覆写**: `mv ~/.obsidian-wiki/config.bak ~/.obsidian-wiki/config`; 测试中应使用 `.test` 后缀
- **真实 skill 目录被覆盖**: 不该发生 (safe_symlink 拒绝); 若发生 → 立即 STOP + 上报 + 从 git/iCloud 恢复
- **真实 vault 被写入**: 仅 `_raw/solar-harness/<sid>.md` 受影响; 删除该子目录即可

### Gate / Eval Failure
- D1-D8 任一 verify 命令 exit ≠ 0 → 失败回路返回 builder, 不直接 fail sprint
- 审判官 eval verdict ≠ PASS → 进入 round 2, 最多 3 轮; 第 3 轮仍 fail → planner 介入收缩范围

## 6. Master Brain 升级触发条件

任一触发立即 STOP, 写 `.solar/inbox/escalate-obsidian-wiki-<reason>.md` 上报:

1. **真实目录被覆盖** (D7 safety 测试 fail) — 系统性 symlink 逻辑错
2. **上游 obsidian-wiki repo URL 失效或 clone 失败** — 改用 vendored fixture
3. **redact 规则漏过 secret** — 立即修 + 已导出文件全部 sanitize
4. **总实现 > 900 行 (硬上限)** — 拆 sprint
5. **symphony3 status-server 设计 ≠ 本 sprint 假设** (端点路径/JSON schema 不兼容) — 重对齐
6. **builder pane 抢占 symphony3** — 立即停, 改 queue 模式
7. **Python stdlib 不够用** (eg. 需要 yaml 解析) — 评估是否引入纯 Python yaml.py 单文件 vs 改 JSON
8. **测试中真实 user vault 被写入** (HARNESS_TEST 失效) — 立即停, 加二级 guard
9. **temp dir cleanup 失败导致 /tmp 占满** — 加 ulimit + 严格 trap

## 7. 实施者提示 (建设者必读)

### 关键代码位置参考
- `solar-harness.sh` line ~1813: 镜像 webhook 子命令 case 段, 添加 wiki 子命令路由
- 现有 `lib/symphony/status-server.py` (symphony3 输出): 在 `/status` handler 内 build_status() 函数添加 obsidian_wiki 块
- 现有 sprint event 持久化: `~/.solar/harness/sprints/<sid>.events.jsonl` (S2 export 时读取)

### 上游 obsidian-wiki 关键观察
- `setup.sh` 是交互式 (会 prompt vault 路径) → **本集成必须 bypass**, 直接写 config 文件
- 上游 `.skills/` 目录下有 `wiki-setup`, `wiki-update`, `wiki-ingest`, `wiki-query` 等 skill 子目录
- vault 骨架文件可参考上游 `wiki-setup/SKILL.md` 中的描述, 但本集成 **不抄上游代码**, 只复用结构定义
- **不要 require QMD** — design 明示 (Non-Goal #2)

### Python stdlib only 提示
- HTTP: `from http.server import BaseHTTPRequestHandler, HTTPServer`
- JSON: `import json`
- Subprocess: `import subprocess` (调 wiki status --json 时 timeout=2)
- File: `pathlib.Path`
- **禁止**: `import requests`, `import flask`, `import yaml`, `import jsonschema` (jsonschema 测试可用, 但实现层不依赖)

### Schema validate 实现选择
- 实现层: 不强制 jsonschema validate (避免 pip 依赖)
- 测试层: 用 `python3 -c "import jsonschema"` (开发机已有), 失败时 skip 该测试用例并 warn

### Idempotency 要求
- `wiki install` 重复跑 → 不破坏已有 vault, 不重复克隆 repo (除非 --refresh), 不重复 symlink
- `wiki export-sprint` 重复跑 → 覆盖同 sid 输出文件, 不抛错
- `wiki status` 纯读, 无副作用

## 8. Definition of Done (Sprint 总验收)

| 项 | 验收标准 | DoD 映射 |
|---|---------|---------|
| Lint | bash -n 全 PASS | D1 |
| Install | install 创建 config + vault skeleton + safe symlinks | D2 |
| Status JSON | schema validate PASS, 含 6 字段 | D3 |
| Export Sprint | _raw/solar-harness/<sid>.md 含 frontmatter + redact | D4 |
| Bridge | update/query 生成指令文件, 拒绝空 query | D5 |
| Status Server | obsidian_wiki block + 缺失时 ready=false 不崩 | D6 |
| Safety | 真实目录覆盖测试 PASS (拒绝写入) | D7 |
| Docs | docs/obsidian-wiki-integration.md ≥ 5 examples | D8 |
| 行数 | 总实现 < 900 行 | Stop rule |
| 非干扰 | symphony3 active 期间 builder 不抢占, coord-status 检测就绪 | brief risk #4 |
| 审判官 eval | deepseek-r1 verdict=PASS | round 1-3 |

## 9. Builder Dispatch Plan (不干扰 active reviewing sprint)

**派工模型**:
- builder_main: claude-sonnet (主路, 处理全部 5 切片)
- builder_parallel: glm-5.1+sonnet (并行槽, 紧急时分担, 但本 sprint 默认单建设者顺序跑)
- evaluator: claude-opus (我自己, 兼任 evaluator)

**派工时序**:
```
Day 1 morning   → S1 (install/status/safety) → builder_main
Day 1 evening   → S1 evaluator round 1
Day 2 morning   → S2 (export-sprint) → builder_main
Day 2 afternoon → S3 (update/query bridge) → builder_main
Day 3 morning   → S4 (status-server integration) → builder_main
                  ↑ 前置依赖: symphony3 S4-S5 已合入主干
Day 3 afternoon → S5 (docs/test) → builder_main
Day 3 evening   → 全测试 + evaluator round 1
```

**抢占防护**:
1. 派工前 builder 必须 check: `solar-harness coord-status | jq '.active_sprints[]'`
2. 如发现 symphony3 在 reviewing 阶段 → wait 30 min retry
3. 如 symphony3 builder pane 0.2 在 in-progress → 用 builder_parallel pane (如有空闲), 否则 queue
4. 测试期间 status-server 用临时端口 (8800-8899), 避免与 symphony3 8765 冲突

**Sprint 间通信**:
- 本 sprint 完成后, S2 的 export-sprint 可用于把 symphony3 的工件归档到 wiki (闭环)
- 本 sprint S4 依赖 symphony3 S4-S5; 如 symphony3 S4-S5 fail → 本 sprint S4 退化为 stub 模式

---

**Plan 完成时间**: 2026-05-07T20:36:00Z
**Status 转换**: drafting → active, phase: spec → planning_complete
**下一步**: 协调器自动派发到 builder_main (claude-sonnet) 启动 S1 实施
**预计完成**: Day 3 evening (约 3 个工作日)
