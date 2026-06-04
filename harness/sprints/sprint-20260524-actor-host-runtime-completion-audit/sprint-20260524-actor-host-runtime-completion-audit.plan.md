# Plan — Actor Host Runtime Completion Audit 执行计划

sprint_id: `sprint-20260524-actor-host-runtime-completion-audit`
generated_at: `2026-05-24T02:10:00Z`
knowledge_context: `solar-harness context inject used (mirage timeout -> qmd/obsidian/solar_db fallback)`
parent: `sprint-20260523-pane-as-physical-operator-architecture`（read-only）
related: taxonomy-truthification / compatibility-cutover / lease-fleet-runtime（read-only）

## 1. 交付切片顺序（2 wave）

| Wave | Node | 覆盖升级点 | 写入 |
|------|------|-----------|------|
| W1 | N1, N2, N3, N4, N5 | 1 / 2 / 3 / 4-6 / 7-10（5 节点并行） | 5 个 audit md |
| W2 | N6 | 11 / 12 / 13 + 13-row completion matrix + remediation backlog + final report（join） | 4 个产物 |

合计 6 节点；2 layer。

## 2. 文件级写入范围（强制 write_scope）

| Node | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| N1 | `<sid>.audit-Q1-actor-vs-host.md` | NEW |
| N2 | `<sid>.audit-Q2-task-protocol.md` | NEW |
| N3 | `<sid>.audit-Q3-lease.md` | NEW |
| N4 | `<sid>.audit-Q4-Q6-profiles-logical-score.md` | NEW |
| N5 | `<sid>.audit-Q7-Q10-verification-ledger-context-token.md` | NEW |
| N6 | `<sid>.audit-Q11-Q13-antigravity-fingerprint-gap.md` + `<sid>.completion-matrix.md` + `<sid>.remediation-backlog.md` + `monitor-reports/actor-host-runtime-completion-audit.md` | NEW |
| Planner（本轮） | `<sid>.{design, plan, task_graph, planning_html}.{md,json,html}` | NEW |

`<sid>` = `sprint-20260524-actor-host-runtime-completion-audit`

**严格禁止 write_scope 外**：
- 任何被审计的 `lib/*.py` / `tools/*.py` / `config/*.json` / `run/**` / `docs/**`（audit = read-only）
- 父 / related sprint 任何 artifact（仅引用）
- `~/.solar/STATE.md` / epic.* / 其他 sprint artifact

## 3. 并发边界

- L0: N1..N5 全并行（5 路；各 audit 不同 code path / Q 子集；write_scope 互不重叠）
- L1: N6 join（必须等 N1..N5 全 passed）
- max-parallel 建议 3（pane lease 限制）

## 4. 每节点 audit md 段落契约

每 N1..N6 必含：

1. **已完成**：本节点覆盖的升级点 + Q 编号 + judgment 行数
2. **Inputs From PRD**：明引 PRD Q 段 + FR/G/A 编号
3. **Audit Method**：本节点遵循 design §4 6 步流程（必须显式记录每步执行的命令）
4. **Evidence Collected**：含 grep/cat/ls/sqlite 等命令 + 输出摘录（read-only，全文不可省略命令）
5. **Judgment Row(s)**：6 列完整（per design §5）+ confidence 0-100
6. **Self-Audit (FR3)**：明示「未把 contract_only 错标 implemented」+ 任何降级理由
7. **Stop-Rule Compliance**：未修改被审计文件 / 未做 repair / 未含 raw secret

N6 必须额外含：

- **completion-matrix.md**：13 行（4 档 status × 6 列）
- **remediation-backlog.md**：P0/P1/P2 分档 + 每项含升级点引用 + action + owner + effort
- **monitor-reports/actor-host-runtime-completion-audit.md**：top gaps 综合（≥5）+ remediation backlog 摘要 + 当前生产真值 vs contract 真值差异 chart

## 5. 验证命令

```bash
SID=sprint-20260524-actor-host-runtime-completion-audit
H=/Users/lisihao/.solar/harness

# A. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. 6 audit md 齐全
for q in Q1 Q2 Q3 "Q4-Q6" "Q7-Q10" "Q11-Q13"; do
  test -f $H/sprints/$SID.audit-$q-*.md || echo "MISSING audit-$q"
done
test -f $H/sprints/$SID.completion-matrix.md
test -f $H/sprints/$SID.remediation-backlog.md
test -f $H/monitor-reports/actor-host-runtime-completion-audit.md

# D. 段落契约 7 段
for f in $H/sprints/$SID.audit-*.md; do
  for sec in "## 已完成" "Inputs From PRD" "Audit Method" "Evidence Collected" "Judgment Row" "Self-Audit" "Stop-Rule"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $(basename $f)"
  done
done

# E. 13 行 matrix 完整
grep -cE "^\| [0-9]+\." $H/sprints/$SID.completion-matrix.md
# 期望 ≥ 13

# F. 4 档 status 全在用
for st in implemented partial contract_only missing; do
  grep -q "$st" $H/sprints/$SID.completion-matrix.md || echo "WARN status $st 未出现"
done

# G. 每行 6 列（upgrade_point / status / confidence / evidence_paths / blockers / remediation_hint）
python3 -c "
with open('$H/sprints/$SID.completion-matrix.md') as f:
    lines = [l for l in f if l.startswith('|') and not l.startswith('|--')]
    for l in lines[1:]:  # skip header
        cols = [c.strip() for c in l.split('|') if c.strip()]
        if len(cols) < 6: print(f'WARN row 缺列: {l[:80]}')
"

# H. evidence_paths 含真实文件路径（不是抽象语）
grep -E "(lib/|tools/|config/|run/|docs/).*\.(py|json|md|yaml)" \
  $H/sprints/$SID.completion-matrix.md | head -10
# 期望 ≥ 10 个真路径引用

# I. 每条 'implemented' 必须有 runtime evidence（不能仅 code+config）
python3 -c "
import re
text = open('$H/sprints/$SID.completion-matrix.md').read()
for m in re.finditer(r'^\| \d+\..+?\|\s*implemented\s*\|.+', text, re.MULTILINE):
    row = m.group(0)
    if not re.search(r'run/|runtime|sqlite|state\.json|heartbeat|ledger', row):
        print(f'WARN implemented 行缺 runtime evidence: {row[:120]}')
"

# J. remediation backlog 3 档全分
for level in "## P0" "## P1" "## P2"; do
  grep -q "$level" $H/sprints/$SID.remediation-backlog.md || echo "MISSING $level in backlog"
done

# K. backlog 每条含升级点 + owner + effort
python3 -c "
import re
text = open('$H/sprints/$SID.remediation-backlog.md').read()
items = re.findall(r'- \[ \] (.+)', text)
for it in items:
    if not re.search(r'升级点|upgrade_point|#\d+|Q\d+', it):
        print(f'WARN backlog 缺升级点引用: {it[:100]}')
    if 'owner' not in it.lower():
        print(f'WARN backlog 缺 owner: {it[:100]}')
    if 'effort' not in it.lower() and not re.search(r'\b[SML]\b', it):
        print(f'WARN backlog 缺 effort: {it[:100]}')
"

# L. monitor-report 含 top gaps + 差异 chart
grep -E "top gaps|生产真值|contract 真值|差异|gap" $H/monitor-reports/actor-host-runtime-completion-audit.md | head -5

# M. 未修改被审计文件
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^tools/|^config/|^run/|^docs/|^solar-harness\.sh|^hooks/|^skills/"

# N. 未修改父 / related sprint artifact
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "sprint-20260523-(pane-as-physical-operator-architecture|physical-operator-taxonomy-truthification|operator-class-compatibility-cutover|lease-based-model-fleet-runtime)\.(design|plan|task_graph)\.(md|json)$"

# O. 无 raw secret
! grep -rE "(api[_-]?key|bearer\s+|sk-|ANTHROPIC.*=\s*['\"][A-Za-z])" $H/sprints/$SID.*.md $H/monitor-reports/actor-host-runtime-completion-audit.md 2>/dev/null

# P. PRD A1..A10 全集映射
for a in A1 A2 A3 A4 A5 A6 A7 A8 A9 A10; do
  count=$(grep -lE "\b$a\b" $H/sprints/$SID.audit-*.md $H/sprints/$SID.completion-matrix.md $H/sprints/$SID.remediation-backlog.md 2>/dev/null | wc -l)
  test "$count" -ge 1 || echo "WARN $a 未映射"
done

# Q. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止修改任何被审计文件（`lib/` / `tools/` / `config/` / `run/` / `docs/` / `solar-harness.sh` / `hooks/` / `skills/`）
- 禁止修改父 / related sprint artifact
- 禁止改 `~/.solar/STATE.md` / epic.* / 其他 sprint
- 禁止做 repair（审计与 repair 分离 — FR5）
- 禁止把 contract_only 标 implemented（FR3）
- 禁止 raw secret 落盘
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N1..N5 任一节点未覆盖其负责的升级点（Q 编号）→ FAIL
- N6 completion-matrix.md 不足 13 行 → FAIL
- N6 缺 4 档 status 任一在使用 → FAIL
- N6 任一行缺 6 列 → FAIL
- N6 任一 `implemented` 行缺 runtime evidence → FAIL（FR3 强制降级）
- N6 remediation-backlog.md 缺 P0/P1/P2 任一档 → FAIL
- N6 backlog 任一项缺升级点引用 / owner / effort → FAIL
- monitor-report 缺 top gaps 或 生产真值 vs contract 真值差异 → FAIL
- 任何节点修改被审计文件 → FAIL + ATLAS（audit 必须 read-only）
- 任何节点修改父 / related sprint artifact → FAIL + ATLAS
- 任何节点做 repair → FAIL + ATLAS（FR5 violation）
- 任何节点把 contract_only 错标 implemented → FAIL（FR3 violation）
- raw secret 落盘 → FAIL + 立即删除
- PRD A1..A10 任一未映射 → FAIL
- 乐观词 → FAIL
- PRD/contract mtime 变化 → 重跑 planner

## 8. 模型路由建议

| Node | Writer class | Verifier class | Model |
|------|-------------|----------------|-------|
| N1 (Actor vs Host) | ImplementationWorker (code 审计) | Verifier | sonnet |
| N2 (Task Protocol) | ImplementationWorker | Verifier | sonnet |
| N3 (Lease) | ImplementationWorker | Verifier | sonnet |
| N4 (Profiles + Logical + Score) | ImplementationWorker | Verifier | sonnet |
| N5 (Verification + Ledger + Context + Token) | ImplementationWorker | Critic | sonnet |
| N6 (Antigravity + Fingerprint + Gap synthesis + matrix + backlog + report) | DeepArchitect | Verifier | opus（全局综合）|

writer ≠ verifier class（per parent sprint contract）。

## 9. 时间预算

- N1 Actor vs Host：~30 min
- N2 Task Protocol：~25 min（与 N1/N3/N4/N5 并行）
- N3 Lease：~30 min
- N4 Profiles/Logical/Score（3 升级点）：~45 min
- N5 Verification/Ledger/Context/Token（4 升级点）：~50 min
- N6 Antigravity/Fingerprint/Gap synthesis + 13-row matrix + backlog + report：~60 min
- 整 sprint 目标 2-3 个 dispatch round 内 passed

## 10. 完成定义（DoD 7 条 + Planner Done Definition + Acceptance Gates）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`
3. **已完成**：planning.html 注册
4. **未验证**：N1..N6 builder 节点未执行；6 audit md + completion-matrix + remediation-backlog + monitor-report 未产
5. **未验证**：PRD A1..A10 全集对照、13 行 matrix、4 档 status 分布、runtime evidence 完整性未由 evaluator 复跑
6. **风险**：
   - False green：plan §7 stop rule + N* Self-Audit 段 + FR3
   - 遗漏升级点：N6 acceptance 强制 13 行
   - 审计变 repair：plan §6 + §7 stop rule + FR5
   - 凭印象判定：plan §5 grep 校验 evidence_paths 真实性
   - runtime evidence 缺失：plan §5 step I 自动降级 implemented → partial
   - 修改被审计文件：plan §6 + §7 stop rule + git diff 校验
7. **后续待办**：
   - coordinator 派 N1..N5 并行 → N6 join
   - evaluator 跑 §5 验证 A..Q 全 PASS → sprint passed
   - PM 从 remediation-backlog P0/P1 项中选择具体 follow-up sprint
   - monitor-report 作为 PM 决策输入
