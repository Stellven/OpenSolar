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
LAB_SESSION_NAME="solar-harness-lab"

# --- JSON 模式 (默认) ---
doctor_json() {
  python3 << 'PYEOF'
import json, subprocess, os, re, sys

SESSION_NAME = "solar-harness"
LAB_SESSION_NAME = "solar-harness-lab"
HARNESS_DIR = os.path.expanduser("~/.solar/harness")

result = {
    "tmux_session_alive": False,
    "lab_session_alive": False,
    "coordinator_pid": 0,
    "coordinator_alive": False,
    "watchdog_pid": 0,
    "watchdog_alive": False,
    "bash_version": "",
    "bash_path": "",
    "panes": [],
    "warnings": [],
    "repairs_available": [],
    "gateway_compat": {
        "checked": False,
        "ok": False,
        "script": os.path.join(os.path.expanduser("~/.solar/harness"), "test-gateway-compat.sh")
    }
}

layout_personas = {}
layout_path = os.path.join(HARNESS_DIR, "farm-layout.json")
if os.path.isfile(layout_path):
    try:
        layout = json.load(open(layout_path))
        default_session = layout.get("session_name", SESSION_NAME)
        for w in layout.get("windows", []):
            session = w.get("session") or default_session
            win = w.get("index", 0)
            for p in w.get("panes", []):
                target = f"{session}:{win}.{p.get('pane_index')}"
                layout_personas[target] = p.get("persona") or p.get("role") or ""
    except Exception:
        pass

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

# tmux sessions
for key, session in [("tmux_session_alive", SESSION_NAME), ("lab_session_alive", LAB_SESSION_NAME)]:
    r = subprocess.run(["tmux", "has-session", "-t", session],
                       capture_output=True, timeout=5)
    result[key] = (r.returncode == 0)

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

def scan_session(session):
    panes = []
    try:
        r = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F",
             "#{session_name}\t#{window_index}.#{pane_index}\t#{pane_pid}\t#{pane_current_command}\t#{pane_dead}"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            pane = {
                "session": parts[0],
                "target": f"{parts[0]}:{parts[1]}",
                "index": parts[1],
                "pid": int(parts[2]),
                "cmd": parts[3],
                "alive": parts[4] != "1",
                "last_activity_ts": "",
                "persona": "",
                "persona_source": "",
                "layout_persona": layout_personas.get(f"{parts[0]}:{parts[1]}", ""),
                "claude_alive": False
            }
            # Prefer the launch wrapper argv. Pane scrollback can lose the
            # Persona header after long conversations; argv remains reliable.
            try:
                queue = [pane["pid"]]
                seen = set()
                while queue:
                    pid = queue.pop(0)
                    if pid in seen:
                        continue
                    seen.add(pid)
                    args = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "args="],
                        capture_output=True, text=True, timeout=2
                    ).stdout.strip()
                    if re.search(r"(^|/)(claude|claude\.exe)(\s|$)", args):
                        pane["claude_alive"] = True
                    m = re.search(r"start-(?:incarnation|launcher)\.sh\s+([A-Za-z0-9_-]+)", args)
                    if m and not pane["persona"]:
                        pane["persona"] = m.group(1)
                        pane["persona_source"] = "process"
                    kids = subprocess.run(
                        ["pgrep", "-P", str(pid)],
                        capture_output=True, text=True, timeout=2
                    ).stdout.strip().splitlines()
                    queue.extend(int(k) for k in kids if k.strip().isdigit())
            except Exception:
                pass
            # detect persona from pane content
            if not pane["persona"]:
                try:
                    content = subprocess.run(
                        ["tmux", "capture-pane", "-t",
                         pane["target"], "-p", "-S", "-80"],
                        capture_output=True, text=True, timeout=5
                    ).stdout
                    matches = re.findall(r"Persona:\s*([A-Za-z0-9_-]+)", content)
                    if matches:
                        pane["persona"] = matches[-1]
                        pane["persona_source"] = "scrollback"
                except Exception:
                    pass
            if not pane["persona"]:
                pane["persona"] = pane["layout_persona"]
                pane["persona_source"] = "layout" if pane["persona"] else ""
            panes.append(pane)
    except Exception as e:
        result["warnings"].append(f"pane scan failed for {session}: {e}")
    return panes

# panes
if result["tmux_session_alive"]:
    result["panes"].extend(scan_session(SESSION_NAME))
if result["lab_session_alive"]:
    result["panes"].extend(scan_session(LAB_SESSION_NAME))

# dead pane warnings
for p in result["panes"]:
    if not p["alive"]:
        result["warnings"].append(f"pane {p.get('target', p.get('index'))} is dead (persona={p.get('persona','?')})")
    layout_persona = p.get("layout_persona", "")
    actual_persona = p.get("persona", "")
    if layout_persona and actual_persona and layout_persona != actual_persona:
        result["warnings"].append(
            f"pane {p['target']} persona mismatch: layout={layout_persona}, actual={actual_persona}, source={p.get('persona_source','?')}"
        )
    if layout_persona and not p.get("claude_alive"):
        result["warnings"].append(
            f"pane {p['target']} has no live claude child (layout={layout_persona}, actual={actual_persona or '?'})"
        )

# repairs available
if os.path.isfile(pidfile) and not result["coordinator_alive"]:
    result["repairs_available"].append("coordinator-down: run solar-harness wake")
if os.path.isfile(wpidfile) and not result["watchdog_alive"]:
    result["repairs_available"].append("watchdog-down: run watchdog start")

# symphony section
symphony_dir = os.path.join(HARNESS_DIR, "lib", "symphony")
scheduler_path = os.path.join(symphony_dir, "scheduler.py")
state_dir = os.path.join(HARNESS_DIR, "state", "symphony")
symphony = {
    "installed": os.path.isfile(scheduler_path),
    "workspace_root": "",
    "claimed": 0,
    "running": 0,
    "retry": 0,
    "repairs_available": []
}
if symphony["installed"]:
    # Resolve workspace root
    try:
        ws_r = subprocess.run(
            ["bash", os.path.join(symphony_dir, "workspace-manager.sh"), "root"],
            capture_output=True, text=True, timeout=5
        )
        symphony["workspace_root"] = ws_r.stdout.strip()
    except Exception:
        pass
    # Count state files
    for sub in ["claimed", "running", "retry", "completed"]:
        sub_dir = os.path.join(state_dir, sub)
        if os.path.isdir(sub_dir):
            count = len([f for f in os.listdir(sub_dir) if f.endswith(".json")])
            symphony[sub] = count
    # Check for stale claimed
    claimed_dir = os.path.join(state_dir, "claimed")
    if os.path.isdir(claimed_dir):
        for f in os.listdir(claimed_dir):
            if not f.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(claimed_dir, f)))
                claimed_at = d.get("claimed_at", "")
                if claimed_at:
                    from datetime import datetime, timezone
                    claimed_time = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - claimed_time).total_seconds() / 3600
                    if age_hours > 1:
                        symphony["repairs_available"].append(f"stale-claimed: {d.get('sprint_id', '?')} claimed {age_hours:.1f}h ago")
            except Exception:
                pass
result["symphony"] = symphony

# Third-party Anthropic-compatible gateway guard. This is read-only and catches
# regressions where z.ai/DeepSeek panes would launch with the full MCP payload.
gateway_script = result["gateway_compat"]["script"]
if os.path.isfile(gateway_script):
    try:
        r = subprocess.run(
            ["bash", gateway_script],
            capture_output=True, text=True, timeout=15
        )
        result["gateway_compat"]["checked"] = True
        result["gateway_compat"]["ok"] = (r.returncode == 0)
        if r.returncode != 0:
            result["warnings"].append("gateway compatibility check failed; run test-gateway-compat.sh")
    except Exception as e:
        result["gateway_compat"]["checked"] = True
        result["gateway_compat"]["ok"] = False
        result["warnings"].append(f"gateway compatibility check failed: {e}")
else:
    result["warnings"].append("gateway compatibility check missing: test-gateway-compat.sh")

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF
}

# --- Summary 模式 (人类可读) ---
doctor_summary() {
  local json_output
  json_output=$(doctor_json)

  local tmux_alive lab_alive coord_alive watchdog_alive gateway_ok bash_ver panes_count warnings_count
  tmux_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin)['tmux_session_alive'])" 2>/dev/null)
  lab_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin).get('lab_session_alive', False))" 2>/dev/null)
  coord_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin)['coordinator_alive'])" 2>/dev/null)
  watchdog_alive=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin)['watchdog_alive'])" 2>/dev/null)
  gateway_ok=$(echo "$json_output" | python3 -c "import json,sys; print(json.load(sys.stdin).get('gateway_compat',{}).get('ok', False))" 2>/dev/null)
  bash_ver=$(echo "$json_output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('bash_version','?'))" 2>/dev/null)
  panes_count=$(echo "$json_output" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['panes']))" 2>/dev/null)
  warnings_count=$(echo "$json_output" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['warnings']))" 2>/dev/null)

  echo ""
  echo "  ┌─ Doctor Summary ─────────────────────────┐"
  echo "  │ bash:   ${bash_ver:0:30}"
  echo "  │ tmux:   $([ "$tmux_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ lab:    $([ "$lab_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ coord:  $([ "$coord_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ watch:  $([ "$watchdog_alive" == "True" ] && echo "✅ alive" || echo "❌ down")"
  echo "  │ gateway:$([ "$gateway_ok" == "True" ] && echo " ✅ compat" || echo " ❌ check")"
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
