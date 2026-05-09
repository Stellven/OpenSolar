# Sprint 2 Implementation Plan
**Sprint**: sprint-20260507-symphony2
**Builder**: 建设者化身
**Date**: 2026-05-07

---

## 变更文件

### 新建文件
| 文件 | 说明 |
|------|------|
| `~/.solar/harness/lib/symphony/hooks.sh` | run_hook 核心实现：env 隔离 + timeout + 日志 |
| `~/.solar/harness/test-symphony-hooks.sh` | 6 个 hook 测试用例 |
| `~/.solar/harness/test-symphony-d6-guard.sh` | 2 个 D6 guard 测试用例 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `~/.solar/harness/lib/symphony/workflow-loader.py` | 新增 hooks: 段解析 + list 支持 + validation + `--validate` CLI |
| `~/.solar/harness/lib/symphony/workspace-manager.sh` | create 接 pre/post_claim；clean 接 pre/post_release |
| `~/.solar/harness/lib/symphony/runner.sh` | 删 CLAUDECODE Guard 2；改用 SOLAR_SYMPHONY_DRY_RUN=1 |
| `~/.solar/harness/templates/WORKFLOW.solar.md` | front matter 增 hooks: 4 个示例 |
| `~/.solar/harness/docs/symphony-integration-adr.md` | 新增 §Hook Lifecycle Design (≥200 字) |

---

## 技术方案

### D6 优先 — runner.sh Guard 2 修复（第一步）

**问题**：Guard 2 检查 `CLAUDECODE` 环境变量，在 Claude Code 嵌套终端里 --dry-run 也会 exit 1。

**修复方案**：
```python
# 旧逻辑 (删除)
for var in $(env | grep -iE '^(CLAUDECODE|CLAUDE_CODE_)' ...):
    echo "Guard FAIL: polluted env var: $var" && exit 1

# 新逻辑
# --dry-run 时设置 SOLAR_SYMPHONY_DRY_RUN=1，不检查 CLAUDECODE
# --unsafe-run-codex 时若未设 SOLAR_SYMPHONY_REAL=1 则 guard exit 1
```

逻辑变更：
```bash
# 在 parse args 时
--dry-run) DRY_RUN=1; export SOLAR_SYMPHONY_DRY_RUN=1; shift ;;
--unsafe-run-codex) DRY_RUN=0; shift ;;

# Guard 2 改为 (仅在 non-dry-run 时生效)
if [[ $DRY_RUN -eq 0 && -z "${SOLAR_SYMPHONY_REAL:-}" ]]; then
  echo "Guard FAIL: real execution requires SOLAR_SYMPHONY_REAL=1" >&2
  exit 1
fi
```

验证：`bash runner.sh --dry-run --sprint-id test-xxx` → exit 0，即使在 Claude Code 内。

---

### D1 — workflow-loader.py hooks: 解析

**现状**：`_parse_simple_yaml` 不支持 YAML inline list `["FOO"]`，无 validation，无 `--validate` CLI。

**改动**：

1. **增加 list 解析**（inline 格式 `["a","b"]`）：
```python
def _parse_list_value(value: str) -> list:
    """Parse inline YAML list: ["a","b"] → ["a","b"]"""
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1]
        items = [i.strip().strip('"').strip("'") for i in inner.split(',') if i.strip()]
        return items
    return None
```

2. **hooks: 段 schema 定义**：
```python
HOOK_LIFECYCLE_KEYS = {
    "pre_claim_workspace", "post_claim_workspace",
    "pre_release_workspace", "post_release_workspace"
}
HOOK_ON_FAILURE = {"fail", "continue"}

def validate_hooks(hooks_config: dict) -> list[str]:
    """Returns list of error strings, empty = valid."""
    errors = []
    for hook_name, hook_cfg in hooks_config.items():
        if hook_name == "global_timeout_ms":
            if not isinstance(hook_cfg, int):
                errors.append(f"hooks.global_timeout_ms must be int")
            continue
        if hook_name not in HOOK_LIFECYCLE_KEYS:
            errors.append(f"hooks.{hook_name}: unknown lifecycle hook")
            continue
        if not isinstance(hook_cfg, dict):
            errors.append(f"hooks.{hook_name}: must be a mapping")
            continue
        if "command" not in hook_cfg:
            errors.append(f"hooks.{hook_name}.command: required")
        on_fail = hook_cfg.get("on_failure", "fail")
        if on_fail not in HOOK_ON_FAILURE:
            errors.append(f"hooks.{hook_name}.on_failure: must be fail|continue")
    return errors
```

3. **`--validate` CLI flag**：
```bash
python3 workflow-loader.py --validate path/to/WORKFLOW.md
# exit 0 + "hooks ok" if valid
# exit 1 + error details if invalid
```

4. **WorkflowValidationError** 异常类：
```python
class WorkflowValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Workflow validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
```

---

### D4 + D5 — hooks.sh 核心实现

**hooks.sh 主函数**：
```bash
run_hook() {
  local hook_name="$1"        # e.g. pre_claim_workspace
  local sprint_id="$2"        # sprint ID
  local command="$3"          # shell command to run
  local timeout_ms="${4:-60000}"
  local on_failure="${5:-fail}"
  shift 5
  local env_allow=("$@")      # additional env vars to pass through

  local log_file="$SPRINTS_DIR/${sprint_id}.hook-${hook_name}.log"
  local timeout_sec=$(( timeout_ms / 1000 ))

  # Build sanitized environment
  local safe_env=()
  safe_env+=("SPRINT_ID=${sprint_id}")
  safe_env+=("WORKSPACE_DIR=${WORKSPACE_DIR:-}")
  safe_env+=("WORKSPACE_ROOT=${WORKSPACE_ROOT:-}")
  safe_env+=("SOLAR_SYMPHONY_HOOK_NAME=${hook_name}")
  safe_env+=("PATH=${PATH}")

  # Allow extra vars via env_allow
  for var in "${env_allow[@]}"; do
    if [[ -n "${!var:-}" ]]; then
      safe_env+=("${var}=${!var}")
    fi
  done

  # Execute in sanitized env with timeout
  # Uses env -i to start fresh, then adds only safe_env
  local exit_code=0
  if command -v gtimeout &>/dev/null; then
    env -i "${safe_env[@]}" gtimeout --signal=TERM --kill-after=5 "${timeout_sec}" \
      bash -c "$command" >> "$log_file" 2>&1 || exit_code=$?
  else
    # perl alarm fallback (macOS compatible)
    env -i "${safe_env[@]}" \
      perl -e "alarm $timeout_sec; exec @ARGV" -- bash -c "$command" >> "$log_file" 2>&1 || exit_code=$?
  fi

  if [[ $exit_code -ne 0 ]]; then
    echo "[hook:${hook_name}] FAILED (exit=${exit_code}), on_failure=${on_failure}" >> "$log_file"
    if [[ "$on_failure" == "fail" ]]; then
      echo "[run_hook] ${hook_name} failed with on_failure=fail → aborting" >&2
      return 1
    fi
    # on_failure=continue: log and proceed
    echo "[run_hook] ${hook_name} failed but on_failure=continue → proceeding" >&2
  fi
  return 0
}
```

**关键设计点**：
- `env -i` 完全清空宿主 env（包括 `*_TOKEN`, `*_KEY`），再注入白名单
- 白名单默认 5 个 var（SPRINT_ID / WORKSPACE_DIR / WORKSPACE_ROOT / SOLAR_SYMPHONY_HOOK_NAME / PATH）
- `env_allow` 扩展：从宿主读取对应 var 值，仅在有值时注入
- gtimeout（brew install coreutils）→ perl alarm fallback（macOS 无需安装）
- 超时后 SIGTERM，5s 后 SIGKILL
- 日志落到 `~/.solar/harness/sprints/<sid>.hook-<name>.log`

**timeout 超时检测**（特殊 exit 码）：
- gtimeout 超时: exit 124
- perl alarm: SIGALRM caught by shell → exit 142
- log 里追加 "timeout" 关键词供测试断言

---

### D2 + D3 — workspace-manager.sh hook 接入

**workspace-manager.sh source hooks.sh** 并在 create/clean 里调用：

```bash
# 顶部
HOOKS_SH="$HARNESS_DIR/lib/symphony/hooks.sh"
[[ -f "$HOOKS_SH" ]] && source "$HOOKS_SH"

# 从 WORKFLOW.md 读取 hook config 的辅助函数
get_hook_config() {
  local ws_dir="$1" hook_name="$2" field="$3"
  local workflow="$ws_dir/WORKFLOW.md"
  [[ -f "$workflow" ]] || { echo ""; return; }
  python3 "$HARNESS_DIR/lib/symphony/workflow-loader.py" "$workflow" 2>/dev/null \
    | grep "^  hooks\.${hook_name}\.${field}:" | awk '{print $2}'
}

# do_create 改动
do_create() {
  local sprint_id="$1"
  # ... 现有代码 ...
  
  # run pre_claim_workspace if configured
  local pre_cmd pre_timeout pre_on_fail pre_env_allow
  pre_cmd=$(get_hook_config "$ws_dir" "pre_claim_workspace" "command")
  if [[ -n "$pre_cmd" ]]; then
    pre_timeout=$(get_hook_config "$ws_dir" "pre_claim_workspace" "timeout_ms")
    pre_on_fail=$(get_hook_config "$ws_dir" "pre_claim_workspace" "on_failure")
    run_hook "pre_claim_workspace" "$sprint_id" "$pre_cmd" \
      "${pre_timeout:-60000}" "${pre_on_fail:-fail}" || return 1
  fi
  
  # ... mkdir, 写文件 ...
  
  # run post_claim_workspace if configured
  post_cmd=$(get_hook_config "$ws_dir" "post_claim_workspace" "command")
  if [[ -n "$post_cmd" ]]; then
    post_timeout=$(get_hook_config "$ws_dir" "post_claim_workspace" "timeout_ms")
    post_on_fail=$(get_hook_config "$ws_dir" "post_claim_workspace" "on_failure")
    run_hook "post_claim_workspace" "$sprint_id" "$post_cmd" \
      "${post_timeout:-60000}" "${post_on_fail:-fail}" || true
  fi
  
  echo "$ws_dir"
}

# do_clean 类似，pre_release → rm -rf → post_release
```

**无 WORKFLOW 时**：`get_hook_config` 返回空，hook 跳过（no-op，exit 0）

---

### D8 — 文档 + ADR

**symphony-integration-adr.md 新增 §Hook Lifecycle Design**（≥200 字）：

内容包含：
1. 4 个生命周期 hook 时序图（ASCII）
2. on_failure 语义表（fail vs continue）
3. env 白名单机制说明（env -i 清空 + 白名单注入）
4. timeout 实现（gtimeout/perl alarm 双路）
5. 日志格式与存储路径

**WORKFLOW.solar.md** front matter 增 hooks: 示例（4 个 hook 各 1 例）。

---

## 实现顺序（对应合约 Day 1-7）

```
Day 1 (今天): D6 修复 → D1 workflow-loader hooks 解析
Day 2:        D4 hooks.sh → D2 pre/post_claim → Gate A (D1+D2+D6)
Day 3:        D3 pre/post_release → D5 env_allow 白名单扩展
Day 4:        test-symphony-hooks.sh (≥5 用例) + test-symphony-d6-guard.sh (2 用例) → Gate B
Day 5:        D8 ADR §Hook Lifecycle Design + WORKFLOW.solar.md 示例
Day 6:        D7 Sprint 1 14/14 回归验证 + 端到端 smoke
Day 7:        handoff.md + eval 准备
```

---

## 风险点

### R1: workflow-loader.py list 解析碎片化
- **问题**: 现有 `_parse_simple_yaml` 只支持扁平 k-v，`env_allow: ["FOO"]` 是 inline list，当前会被解析为普通字符串
- **缓解**: 在 value 解析阶段先检测 `startswith('[')` → 调 `_parse_list_value`；同时测试 env_allow 实际注入是否生效

### R2: macOS 无 gtimeout，perl alarm 行为差异
- **问题**: perl alarm 在 SIGALRM 时父进程不会 SIGKILL 子进程
- **缓解**: perl alarm 只支持一级进程限制；hook command 建议用 `bash -c "..."` 包裹；合约要求 SIGTERM→5s→SIGKILL，perl 路径仅做 SIGTERM，5s 后主动 wait+kill
- **替代**: `brew install coreutils` 提供 gtimeout；如果测试环境有 gtimeout 优先走它

### R3: workspace-manager.sh source hooks.sh 时 hooks.sh 不存在
- **问题**: `source` 失败导致 create/clean 报错
- **缓解**: `[[ -f "$HOOKS_SH" ]] && source "$HOOKS_SH"` 条件 source；`run_hook` 调用前检查函数是否已定义 (`declare -f run_hook >/dev/null`)

### R4: env -i 清空环境后 PATH 不够用
- **问题**: env -i 重置后 hook 脚本找不到 bash/python3
- **缓解**: safe_env 里包含 `PATH=${PATH}` (宿主 PATH)；hook command 用绝对路径或依赖 PATH

### R5: hook log 目录不存在（ws 尚未创建时 pre_claim 失败）
- **问题**: pre_claim_workspace 在 mkdir 之前执行，ws_dir 不存在，log 写不进去
- **缓解**: log 路径改为 `SPRINTS_DIR/<sid>.hook-<name>.log`（不依赖 ws_dir），SPRINTS_DIR 一定存在

### R6: Sprint 1 回归
- **问题**: 修改 workspace-manager.sh 和 runner.sh 可能破坏 Sprint 1 的 14 个测试
- **缓解**: 修改前记录 Sprint 1 测试现状；每个文件改动后立即跑对应测试；不改 do_info/do_show/root

### R7: get_hook_config 调 python3 workflow-loader 性能
- **问题**: create/clean 里每个 hook 字段都调一次 python3，共 ~6 次 fork
- **缓解**: P0 只有 4 hook × 3 field = 12 次，毫秒级，可接受；后续可 cache
- **实现**: 提取 `load_workflow_hooks <ws_dir>` 一次调用返回所有 hooks config，workspace-manager.sh 解析输出

---

## 关键接口

### hooks.sh API
```bash
source hooks.sh
run_hook <hook_name> <sprint_id> <command> <timeout_ms> <on_failure> [env_allow_vars...]
# Returns: 0=success/skipped, 1=failed(fail mode)
```

### workflow-loader.py --validate
```bash
python3 workflow-loader.py --validate WORKFLOW.md
# exit 0: "hooks ok valid"
# exit 1: error details
```

### test-symphony-hooks.sh --case
```bash
bash test-symphony-hooks.sh --case pre_claim_post_claim
bash test-symphony-hooks.sh --case pre_release_post_release
bash test-symphony-hooks.sh --case env_isolation
bash test-symphony-hooks.sh --case env_allow_extension
bash test-symphony-hooks.sh  # run all
```

### test-symphony-d6-guard.sh
```bash
bash test-symphony-d6-guard.sh  # 2 cases: --dry-run exit 0, --unsafe-run-codex guard
```
