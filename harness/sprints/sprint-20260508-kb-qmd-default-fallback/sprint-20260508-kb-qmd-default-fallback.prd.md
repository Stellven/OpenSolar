# PRD — P0 Solar KB Default QMD Fallback

**Source**: codex-manual-2026-05-08 (codex_pm 起草合约) + 监护人显性需求 ("我已经写在 Obsidian 里了，你为什么找不到")
**Priority**: P0
**Lane**: reliability
**Handoff To**: planner
**Created**: 2026-05-08T15:30:00Z
**Sprint ID**: sprint-20260508-kb-qmd-default-fallback

---

## 背景 / Context

Solar 的「默认知识上下文注入」机制是这样的:

```
用户在 Claude Code 输入 prompt
    ↓
UserPromptSubmit hook 触发 (~/.claude/settings.json 已注册)
    ↓
~/.claude/hooks/solar-knowledge-context.sh
    ↓
~/.solar/harness/lib/solar-knowledge-context.py --query <text>
    ↓
查 ~/.solar/solar.db (Cortex / FTS)
    ↓
[当前问题: 命中为空时直接返回 hits=[]]
    ↓
hook 不注入 <solar-knowledge-context>
    ↓
Solar 完全不知道 Obsidian 库里有相关笔记
```

监护人的实际工作流是:
- 在 Obsidian (`/Users/lisihao/Knowledge`) 写笔记
- 通过 qmd CLI (`qmd search "X" -c solar-wiki`) 能搜到这些笔记
- **但 Solar 默认上下文注入不走 qmd**, 只走 Solar DB

所以监护人感受到的是: "我把『大模型热力学』的笔记写在 Obsidian 里了，让 Solar 帮我分析，结果它装作没看过这个笔记。"

技术现状: `obsidian_vault_index` 表当前不在 `~/.solar/solar.db` 里, 单靠 DB/FTS 必然漏命中 vault 内容。

## 用户问题 / Problem

**核心问题**: Solar 的默认上下文注入只查 SQLite，不会自动 fallback 到 qmd，导致监护人的 Obsidian 笔记在 Solar 工作时长期不可见。

**触发场景**:
- 监护人随手输入"基于大模型热力学分析注意力机制"
- Solar 应当看到他在 Obsidian 写过的同名笔记 → 实际看不到
- 他得显式说"先 qmd 搜一下"，体验等于失去默认上下文

**根因**:
1. `solar-knowledge-context.py` 的 retriever 只接了 DB / FTS / vault-index 三个源
2. `obsidian_vault_index` 没建/没同步 → 三源全失效
3. qmd 已经能找到，但没有作为 fallback 接进 retriever
4. dispatch panes 是否走 `UserPromptSubmit` hook 也是未知 (planner 需澄清)

## 用户目标 / Goals

1. **G1 — 默认上下文恢复**: 监护人输入和 Obsidian 笔记相关的 prompt 时，Solar 默认就能看到笔记内容（不需要他显式说"查 qmd"）
2. **G2 — 失败安全**: qmd 缺失/超时/DB 锁不能阻塞 prompt 提交（fail-open 不能改）
3. **G3 — 预算可控**: 注入上下文不能爆量，必须遵守 max-chars 预算
4. **G4 — 可验证**: 给一个监护人可以直接跑的 verify 命令，证明"现在 Solar 能看见我的笔记了"
5. **G5 — 可禁用**: `SOLAR_KB_CONTEXT=0` 一键关掉整个机制（已有，不能回归）
6. **G6 — Dispatch 通路澄清**: 必须给监护人讲清楚 — coordinator 派单到 builder/evaluator pane 时这套机制是不是也走通的；如果不走通，方案是什么

## 用户故事 / User Stories

**US1 — 监护人视角 (默认体验)**
> 作为监护人，当我输入"帮我基于大模型热力学分析注意力机制"时，
> 我希望 Solar 自动调出我在 Obsidian 写过的笔记作为上下文，
> 这样我就不用每次都重复"先 qmd 搜一下"。

**US2 — 监护人视角 (失败安全)**
> 作为监护人，当我换了一台没装 qmd 的机器，或者 DB 正在被另一个进程锁住时，
> 我希望我的 prompt 还是能正常发送，
> 这样我不会因为 KB 系统故障而被卡住。

**US3 — Solar 视角 (规划者)**
> 作为 Solar 的规划者，当我决定一个新 sprint 的方案时，
> 我希望默认上下文里就有 Obsidian 相关笔记，
> 这样我不会重复设计监护人已经研究过的东西。

**US4 — Solar 视角 (建设者)**
> 作为 Solar 的建设者，在 dispatch pane 里收到任务时，
> 我希望能看到和任务相关的 Obsidian 笔记 (如果有)，
> 这样我不会写一遍监护人已经在笔记里讨论过的实现。

**US5 — 运维视角**
> 作为运维者，当 KB 默认注入出问题时，
> 我希望有一份 runbook 告诉我"如何验证、如何禁用、常见故障模式"，
> 这样我能快速定位问题或临时关掉机制。

## 功能需求 / Requirements

### R1 — qmd Fallback in Retriever
- 在 `solar-knowledge-context.py` 中：DB/FTS/vault-index 全部命中为空或部分命中后，**bounded** 调用 qmd
- 默认 collection: `solar-wiki`
- qmd 二进制定位顺序: `$QMD_BIN` → `/Users/lisihao/.npm-global/bin/qmd` → `command -v qmd`
- 解析 qmd `--json` 输出
- 转成现有 hit schema: `source / table / id / title / snippet / path / score`
- `source` 字段标注为 `qmd:solar-wiki` (区别于 DB 来源)
- 严格遵守剩余 timeout 和 max-chars 预算

### R2 — Hook 默认行为
- `~/.claude/hooks/solar-knowledge-context.sh` 必须保持 fail-open
- qmd fallback 命中时，hook 必须发出 `<solar-knowledge-context>` 块
- 全程不抛异常导致 prompt 阻塞
- `SOLAR_KB_CONTEXT=0` 必须能短路整个机制

### R3 — Dispatch Pane 通路明确
- 调研: solar-harness coordinator 派发任务到 pane 1/2/3 时，目标 Claude 实例是否走 `UserPromptSubmit` hook
- 输出 ADR 或 design note 一份, 给出三选一结论:
  - (A) dispatch 走 hook → 不需额外动作
  - (B) dispatch 不走 hook → 在 dispatch text 中追加 sourced context 块 (查询 = sprint title + 合约关键句)
  - (C) 不确定 → 验证步骤 + 临时方案
- 若选 (B), 实现"安全最小注入路径": 查询 sprint title + 合约文本 → bounded sourced context → fail open

### R4 — 防注入与去重
- qmd 返回内容视为不可信文本，**不能** 当指令执行
- DB 命中和 qmd 命中按 path / title 去重 (避免同一笔记两份)
- snippet 截断到合理长度 (e.g. ≤ 300 字符)，不塞整篇文档

### R5 — Schema 不破坏兼容
- retriever 返回的 JSON schema 必须保持现有契约不变
- hook 端无需任何 breaking change

### R6 — 测试
- 新增 `~/.solar/harness/tests/test-solar-kb-qmd-fallback.sh`
- 必覆盖:
  - DB miss + qmd hit → 注入成功
  - qmd 不可用 → fail-open 空 hits, 不阻塞
  - `SOLAR_KB_CONTEXT=0` → 完全不注入
  - max-chars 不超 (含 JSON overhead 不算超)
  - 输出始终是合法 JSON

### R7 — Runbook
- 一份操作员文档，至少含:
  - 默认 KB 上下文怎么工作 (DB → vault index → qmd 三段 fallback)
  - DB 路径、qmd 路径、collection 名称
  - 用 `大模型热力学` 验证的具体命令
  - 如何禁用 (`SOLAR_KB_CONTEXT=0`)
  - 常见故障: `database is locked` / qmd 缺失 / 0 hits

### R8 — 实现规约
- 用 `subprocess.run(..., timeout=remaining_budget)` 跑 qmd
- 剩余预算不够时直接跳过 qmd (不能 hang prompt)
- argv 数组传参，禁止字符串拼接 query (防 shell injection)

## 验收标准 / Acceptance Criteria

直接采用合约 A1–A6 (verify 命令照搬，不重写):

### A1 — Retriever 找到 qmd-only 知识
```bash
python3 /Users/lisihao/.solar/harness/lib/solar-knowledge-context.py \
  --query '大模型热力学' --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"], d; assert any("大模型" in (h.get("title","")+h.get("snippet","")) for h in d["hits"]), d'
```

### A2 — Hook 注入 `<solar-knowledge-context>`
```bash
printf '{"user_prompt":"帮我基于大模型热力学分析注意力机制"}' \
  | /Users/lisihao/.claude/hooks/solar-knowledge-context.sh \
  | grep -q '<solar-knowledge-context>'
```

### A3 — qmd 缺失 fail-open
```bash
QMD_BIN=/tmp/no-such-qmd \
python3 /Users/lisihao/.solar/harness/lib/solar-knowledge-context.py \
  --query '大模型热力学' --json --fail-open \
  | python3 -c 'import json,sys; json.load(sys.stdin)'
```

### A4 — Disable Flag 生效
```bash
out=$(printf '{"user_prompt":"大模型热力学"}' \
  | SOLAR_KB_CONTEXT=0 /Users/lisihao/.claude/hooks/solar-knowledge-context.sh)
test -z "$out"
```

### A5 — Max-Chars 预算遵守
```bash
python3 /Users/lisihao/.solar/harness/lib/solar-knowledge-context.py \
  --query '大模型热力学' --json --max-chars 500 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["total_chars"] <= 500, d'
```

### A6 — 回归测试通过
```bash
bash /Users/sihaori/.solar/harness/tests/test-solar-kb-qmd-fallback.sh
```

(注: 上一行 path typo `solar-harness` 应为 `solar/harness`，以合约原文为准)

### A7 (PM 加) — Dispatch 通路文档
- 必须有一份 markdown 说明 dispatch pane 是否触发 hook
- 若走 (B), 必须给至少一个验证命令证明 dispatch 文本被注入了 context

## 非目标 / Non-Goals

- **不**重写 Solar 整套 memory 架构 (本 sprint 只动 retriever + hook + 测试 + 文档)
- **不**要求把 Obsidian vault 全量索引到 SQLite 后才工作 (那是 data-plane 系列 sprint 的事)
- **不**把整篇文档塞进 prompt (snippet 截断必须存在)
- **不**在 qmd / DB 锁住时阻塞用户 prompt 提交
- **不**执行 retrieved 内容里的任何指令文本
- **不**改 retriever 现有 JSON schema (兼容现有 hook 调用方)
- **不**新引入 ChromaDB / MemPalace 作为 fallback (那是另一个 sprint)
- **不**对 dispatch text 做大改动 (即使选方案 B, 也仅"追加" sourced context 块)

## 约束 / Constraints

1. 写盘范围仅限:
   - `/Users/lisihao/.solar/harness/lib/solar-knowledge-context.py`
   - `/Users/lisihao/.claude/hooks/solar-knowledge-context.sh` (如需微调)
   - `/Users/lisihao/.solar/harness/tests/test-solar-kb-qmd-fallback.sh` (新文件)
   - `/Users/lisihao/.solar/harness/runbooks/kb-default-context.md` (新文件 或追加到现有 runbook)
   - 选方案 (B) 时还允许动 dispatch 注入位置 (具体由 planner 指明)
2. 不动 `solar.db` schema (不创建新表)
3. 不引入新 Python 依赖 (只用 stdlib + 现有依赖)
4. 不改 `~/.claude/settings.json` 的 hook 注册块 (已注册过)
5. fail-open 是绝对的 — retriever / hook 任何路径下都不能让 prompt 提交失败
6. qmd 调用必须 bounded (timeout < 整体 budget 的 1/3)
7. 全部 commit 必须保持 A4 (`SOLAR_KB_CONTEXT=0`) 行为不回归
8. 不在 retriever / hook 里输出任何 secret 值 (即使日志)

## 风险 / Risks

| 风险 | 严重度 | 说明 | 缓解 |
|------|--------|------|------|
| qmd 调用 hang 导致 prompt 卡住 | 高 | qmd 内部走文件系统索引，遇到大 vault 可能慢 | 严格 timeout + 预算检查；超预算直接跳过 qmd 走 fail-open |
| qmd 输出非预期 JSON 形态 | 中 | qmd 升级可能改 schema | retriever 加 try/except + 字段缺省值；解析失败视同空命中 |
| 同一笔记 DB+qmd 双命中 | 中 | DB 已索引一半 + qmd 也找到 → 重复注入挤占预算 | path/title 去重 |
| dispatch pane 实际不走 hook | 中 | 监护人可能误以为已经修好，实际 builder 看不到上下文 | R3 必须明确给出 dispatch 通路结论；若不走 hook 必须给方案 B 的实现 |
| qmd 返回内容被当指令执行 | 高 | retrieved 文本可能含 `Ignore previous instructions...` | 始终标注 `source=qmd:solar-wiki`, snippet 包在 `<solar-knowledge-context>` 块中, 明确"不可信" |
| 默认 query 抓回不相关的 vault 内容 | 中 | qmd 命中度不一定高 | 限制注入条数 (建议 ≤ 3) + score 阈值 + max-chars 兜底 |
| `SOLAR_KB_CONTEXT=0` 被 R1/R2 改动意外破坏 | 高 | A4 是回归红线 | 测试 R6 必须包含 disable flag 用例 |

## 开放问题 / Open Questions

1. **Q1**: qmd CLI 实际是否支持 `--json -n N --collection X` 多参数组合？（合约假设支持，需要 planner 跑一次 `qmd search --help` 确认）
2. **Q2**: dispatch pane 里的 builder/evaluator Claude 实例是否实际触发 `UserPromptSubmit` hook？（这是 R3 的核心未知，决定方案是 A 还是 B）
3. **Q3**: 是否需要给 qmd hits 设最小 score 阈值？（合约没说，但 score 太低的命中可能是噪音）
4. **Q4**: `obsidian_vault_index` 是要在本 sprint 顺手建一下，还是完全留给后续 data-plane sprint？（PM 倾向后者，本 sprint 只做 qmd fallback）
5. **Q5**: qmd 命中条数上限 N=? (默认 3? 5?) — 影响 max-chars 预算分配
6. **Q6**: 如果 retriever 同时收到 DB 命中和 qmd 命中, 优先级如何排？(建议 DB 优先, qmd 补位; planner 拍板)
7. **Q7**: A6 verify 命令中的路径疑似 typo (`solar-harness/tests` 写成 `solar-haress/tests`?), 已在 A6 上面备注; planner 实现时以本 PRD 路径为准

## 架构交接 / Planner Handoff

### 给 Planner 的 6 个具体问题

1. **方案 A/B 决断**: dispatch pane 是否走 hook？请用一条命令验证, 给出三选一结论。
2. **去重策略**: DB/qmd 双命中时, 用 `path` 还是 `title` 还是 `(path, title)` 联合做主键?
3. **超时预算分配**: hook 总 budget 默认多少? qmd 子调用占多少? 给出具体数字 (建议 hook 1500ms, qmd 500ms)。
4. **score 阈值**: qmd hits 是否设最小 score? 默认值多少?
5. **runbook 落地位置**: 新建 `~/.solar/harness/runbooks/kb-default-context.md` 还是追加到现有文档? 列出现有候选。
6. **方案 (B) 注入位置**: 若 dispatch 不走 hook, 在哪个文件/函数里注入 dispatch context? (coordinator.sh 的 dispatch_to_pane? generate_dispatch?) 给具体行号。

### 推荐执行顺序 (Planner 参考)

1. 先验 Q1 (qmd CLI 接口) + Q2 (dispatch hook) → 决定整体方案
2. 写 retriever qmd fallback (R1 + R8)
3. 写测试 (R6) — 用 mock qmd 跑通后再接真 qmd
4. 跑 A1/A3/A4/A5 → 全过再做 A2
5. 写 dispatch 通路文档/方案 (R3 → A7)
6. 写 runbook (R7)
7. 全量 verify A1–A7 → handoff

### 不让 Planner 浪费时间的事

- 不要从头设计新的 indexer
- 不要碰 ChromaDB / MemPalace
- 不要重新设计 hook 注册
- 不要为了"完美"扩展 schema (兼容是硬约束)

---

**双签**: 战略家 (推动落地: 监护人体验问题, P0 不能拖) + 治理官 (审计: fail-open 是红线, max-chars 是红线, 注入安全是红线)

**PM 备注**: 本 sprint 范围控制极严, 实现路径已经被合约写得很清楚, planner 主要任务是回答 6 个开放问题 + 把 R1–R8 编排成 plan.md。预估 builder 工作量 ~1 个 round 即可 PASS。
