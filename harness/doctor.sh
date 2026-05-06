#!/usr/bin/env bash
# ================================================================
# Solar Harness — Doctor (纯只读健康诊断)
#
# 输出 JSON 含: tmux_session_alive, coordinator_*, watchdog_*,
#   bash_version, bash_path, panes[], warnings[], repairs_available[]
#
# --summary: 人类可读摘要 (用于启动首屏)
#
# @module solar-farm/harness/doctor
# ================================================================
set -eu

HARNESS_DIR="$HOME/.solar/harness"
SESSION_NAME="solar-harness"

# --- JSON 模式 (默认) ---
doctor_json() {
  python3 << 'PYEOF'
import json, subprocess, os, sys

SESSION_NAME = "solar-harness"
HARNESS_DIR = os.path.expanduser("~/.solar/harness")

result = {
    "tmux_session_alive": False,
    "coordinator_pid": 0,
    "coordinator_alive": False,
    "watchdog_pid": 0,
    "watchdog_alive": False,
    "bash_version": "",
    "bash_path": "",
    "panes": [],
    "warnings": [],
    "repairs_available": []
}

# bash version
for b in ["/opt/homebrew/bin/bash", "/usr/local/bin/bash"]:
    if os.path.isfile(b):
        try:
            r = subprocess.run([b, "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                result["bash_version"] = r.stdout.split("\n")[0]
                result["bash_path"] = b
                break
        except Exception:
            pass

# tmux session
r = subprocess.run(["tmux", "has-session", "-t", SESSION_NAME],
                   capture_output=True, timeout=5)
result["tmux_session_alive"] = (r.returncode == 0)

# coordinator pid
pidfile = os.path.join(HARNESS_DIR, ".coordinator.pid")
if os.path.isfile(pidfile):
    try:
        pid = int(open(pidfile).read().strip())
        result["coordinator_pid"] = pid
        os.kill(pid, 0)
        result["coordinator_alive"] = True
    except (ValueError, ProcessLookupError):
        result["warnings"].append(f"coordinator pidfile stale: {pidfile}")
    except PermissionError:
        result["coordinator_alive"] = True

# watchdog pid
wpidfile = os.path.join(HARNESS_DIR, ".watchdog.pid")
if os.path.isfile(wpidfile):
    try:
        wpid = int(open(wpidfile).read().strip())
        result["watchdog_pid"] = wpid
        os.kill(wpid, 0)
        result["watchdog_alive"] = True
    except (ValueError, ProcessLookupError):
        result["warnings"].append(f"watchdog pidfile stale: {wpidfile}")
    except PermissionError:
        result["watchdog_alive"] = True

# panes
if result["tmux_session_alive"]:
    try:
        r = subprocess.run(
            ["tmux", "list-panes", "-t", SESSION_NAME, "-F",
             "#{pane_index}\t#{pane_pid}\t#{pane_current_command}\t#{pane_dead}"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            pane = {
                "index": int(parts[0]),
                "pid": int(parts[1]),
                "cmd": parts[2],
                "alive": parts[3] != "1",
                "last_activity_ts": "",
                "persona": ""
            }
            # detect persona from pane content
            try:
                content = subprocess.run(
                    ["tmux", "capture-pane", "-t",
                     f"{SESSION_NAME}:0.{parts[0]}", "-p"],
                    capture_output=True, text=True, timeout=5
                ).stdout
                for p in ["planner", "builder", "evaluator"]:
                    if p in content.lower():
                        pane["persona"] = p
                        break
            except Exception:
                pass
            result["panes"].append(pane)
    except Exception as e:
        result["warnings"].append(f"pane scan failed: {e}")

    # dead pane warnings
    for p in result["panes"]:
        if not p["alive"]:
            result["warnings"].append(f"pane {p['index']} is dead (persona={p.get('persona','?')})")

# repairs available
if os.path.isfile(pidfile) and not result["coordinator_alive"]:
    result["repairs_available"].append("coordinator-down: run solar-harness wake")
if os.path.isfile(wpidfile) and not result["watchdog_alive"]:
    result["repairs_available"].append("watchdog-down: run watchdog start")

# D5: L3 MemPalace check
result["l3_mempalace"] = {"ok": False, "total_docs": 0, "status": "not initialized"}
mempalace_dir = os.path.expanduser("~/.solar/mempalace")
if os.path.isdir(mempalace_dir):
    try:
        sys.path.insert(0, mempalace_dir)
        from mempalace_init import MemPalaceInit
        init = MemPalaceInit()
        init.init_chromadb()
        total = init.collection.count()
        result["l3_mempalace"] = {
            "ok": True,
            "total_docs": total,
            "status": f"{total} docs"
        }
    except Exception as e:
        result["l3_mempalace"] = {"ok": False, "total_docs": 0, "status": f"error: {str(e)}"}

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF
}

# --- Summary 模式 (人类可读) ---
doctor_summary() {
  local json_output
  json_output=$(doctor_json)

  local tmux_alive coord_alive watchdog_alive bash_ver panes_count warnings_count
  tmux_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin)['tmux_session_alive'])" 2>/dev/null)
  coord_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin)['coordinator_alive'])" 2>/dev/null)
  watchdog_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin)['watchdog_alive'])" 2>/dev/null)
  bash_ver=$(echo "$json_output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('bash_version','?'))" 2>/dev/null)
  panes_count=$(echo "$json_output" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['panes']))" 2>/dev/null)
  warnings_count=$(echo "$json_output" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['warnings']))" 2>/dev/null)

  echo ""
  echo "  ┌─ Doctor Summary ─────────────────────────┐"
  echo "  │ bash:   ${bash_ver:0:30}"
  echo "  │ tmux:   $([ "$tmux_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ coord:  $([ "$coord_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ watch:  $([ "$watchdog_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ L3:     $(echo "$json_output" | python3 -c "import json,sys; d=json.load(sys.stdin); l3=d.get('l3_mempalace',{}); print('✅ ' + l3.get('status', '?') if l3.get('ok') else '❌ ' + l3.get('status', 'N/A'))" 2>/dev/null || echo "⚠ N/A")"
  echo "  │ panes:  ${panes_count}"
  echo "  │ warns:  ${warnings_count}"
  echo "  └────────────────────────────────────────────┘"

  # Show warnings if any
  if [[ "$warnings_count" != "0" ]]; then
    echo "$json_output" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('warnings', []):
    print(f'  ⚠ {w}')
" 2>/dev/null
  fi
  echo ""
}

# --- 入口 ---
case "${1:-}" in
  --summary|-s)
    doctor_summary
    ;;
  --json|"")
    doctor_json
    ;;
  --help|-h)
    echo "solar-harness doctor — 纯只读健康诊断"
    echo ""
    echo "用法:"
    echo "  solar-harness doctor           输出 JSON"
    echo "  solar-harness doctor --summary 人类可读摘要"
    echo ""
    echo "纯只读，不修改任何状态或重启进程。"
    ;;
  *)
    echo "未知参数: $1" >&2
    exit 1
    ;;
esac
