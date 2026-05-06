#!/bin/bash
# ================================================================
# Solar Harness — Persona 配置共享函数 (单一真相源)
# Sprint sprint-20260502-191700 D1
#
# 用法:
#   source "$HARNESS_DIR/lib/persona-config.sh"
#   get_persona_config <planner|builder|evaluator>
#   # 输出 KEY=VALUE 行, caller 用 eval 解析
#
#   # CLI 调试接口:
#   bash persona-config.sh --print-config planner
#
# @module solar-farm/harness/lib/persona-config
# ================================================================

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"

# 从 model-config.sh 读 ZHIPU_* 变量
_source_model_config() {
  source "$HARNESS_DIR/model-config.sh" 2>/dev/null || true
}

get_persona_config() {
  local persona="$1"
  _source_model_config

  local model_flag="" base_url="" auth_token="" tool_flag="" display_model="" startup_token="" proxy_check="0"
  local cn=""

  case "$persona" in
    planner)
      cn="规划者"
      model_flag="--model opus"
      # planner 直连 Anthropic, 清掉 Zhipu env
      base_url=""
      auth_token=""
      tool_flag="--allowedTools Read Bash Grep Glob"
      display_model="Claude Opus (Anthropic)"
      startup_token="solar"
      proxy_check="1"
      ;;
    builder)
      cn="建设者"
      model_flag="--model ${ZHIPU_MODEL:-glm-5.1}"
      base_url="${ZHIPU_BASE_URL:-}"
      auth_token="${ZHIPU_AUTH_TOKEN:-}"
      tool_flag=""
      display_model="GLM-5.1 (智谱)"
      startup_token=""
      proxy_check="0"
      ;;
    evaluator)
      cn="审判官"
      model_flag="--model ${ZHIPU_MODEL:-glm-5.1}"
      base_url="${ZHIPU_BASE_URL:-}"
      auth_token="${ZHIPU_AUTH_TOKEN:-}"
      tool_flag="--allowedTools Read Bash Grep Glob Write"
      display_model="GLM-5.1 (智谱)"
      startup_token=""
      proxy_check="0"
      ;;
    pm)
      cn="产品经理"
      model_flag="--model opus"
      base_url=""
      auth_token=""
      tool_flag="--allowedTools Read Bash Grep Glob Write"
      display_model="Claude Opus (Anthropic)"
      startup_token=""
      proxy_check="1"
      ;;
    architect)
      cn="架构师"
      model_flag="--model opus"
      base_url=""
      auth_token=""
      tool_flag="--allowedTools Read Bash Grep Glob Write Edit"
      display_model="Claude Opus (Anthropic)"
      startup_token=""
      proxy_check="1"
      ;;
    second-builder)
      cn="架构师(opus)"
      model_flag="--model opus"
      base_url=""
      auth_token=""
      tool_flag="--allowedTools Read Bash Grep Glob Write Edit"
      display_model="Claude Opus (Anthropic)"
      startup_token=""
      proxy_check="1"
      ;;
    lab-builder)
      cn="实验建设者"
      model_flag="--model ${ZHIPU_MODEL:-glm-5.1}"
      base_url="${ZHIPU_BASE_URL:-}"
      auth_token="${ZHIPU_AUTH_TOKEN:-}"
      tool_flag=""
      display_model="GLM-5.1 (智谱)"
      startup_token=""
      proxy_check="0"
      ;;
    lab-evaluator)
      cn="实验审判官"
      model_flag="--model ${ZHIPU_MODEL:-glm-5.1}"
      base_url="${ZHIPU_BASE_URL:-}"
      auth_token="${ZHIPU_AUTH_TOKEN:-}"
      tool_flag="--allowedTools Read Bash Grep Glob Write"
      display_model="GLM-5.1 (智谱)"
      startup_token=""
      proxy_check="0"
      ;;
    observer)
      cn="观察者"
      model_flag="--model ${ZHIPU_MODEL:-glm-5.1}"
      base_url="${ZHIPU_BASE_URL:-}"
      auth_token="${ZHIPU_AUTH_TOKEN:-}"
      tool_flag="--allowedTools Read Bash Grep Glob"
      display_model="GLM-5.1 (智谱)"
      startup_token=""
      proxy_check="0"
      ;;
    *)
      cn="$persona"
      model_flag="--model ${ZHIPU_MODEL:-glm-5.1}"
      base_url="${ZHIPU_BASE_URL:-}"
      auth_token="${ZHIPU_AUTH_TOKEN:-}"
      tool_flag=""
      display_model="GLM-5.1 (智谱)"
      startup_token=""
      proxy_check="0"
      ;;
  esac

  # sprint-20260502-191700 follow-up: 输出加引号 (修 eval bug) + AUTH_TOKEN 不泄漏明文
  # 旧 bug 1: MODEL_FLAG=--model glm-5.1 → eval 时被 bash 当 "VAR=val command" 临时 env 跑 glm-5.1 → not found
  # 旧 bug 2: AUTH_TOKEN=明文 → --print-config 直接打印到屏幕 → 泄漏隐患
  # 修复: 单引号包裹 + AUTH_TOKEN 输出 mask (真值仍由 apply_persona_env 从 env 设置)
  local masked_token=""
  [[ -n "$auth_token" ]] && masked_token="<from-env:ZHIPU_AUTH_TOKEN>"
  echo "CN='$cn'"
  echo "MODEL_FLAG='$model_flag'"
  echo "BASE_URL='$base_url'"
  echo "AUTH_TOKEN='$masked_token'"
  echo "TOOL_FLAG='$tool_flag'"
  echo "DISPLAY_MODEL='$display_model'"
  echo "STARTUP_TOKEN='$startup_token'"
  echo "PROXY_CHECK='$proxy_check'"
}

apply_persona_env() {
  local persona="$1"
  # sprint-20260502-191700 follow-up: AUTH_TOKEN 不再从 get_persona_config 传(已 mask)
  # 直接从环境变量取真值 (model-config.sh source secrets/zhipu.env 时已设置 ZHIPU_AUTH_TOKEN)
  _source_model_config

  local config
  config=$(get_persona_config "$persona")

  # 解析 KV 对 (现在带单引号,需 strip)
  local base_url proxy_check
  base_url=$(echo "$config" | grep '^BASE_URL=' | sed "s/^BASE_URL='//;s/'$//")
  proxy_check=$(echo "$config" | grep '^PROXY_CHECK=' | sed "s/^PROXY_CHECK='//;s/'$//")

  # 设置/清除环境变量
  if [[ -n "$base_url" ]]; then
    export ANTHROPIC_BASE_URL="$base_url"
    # AUTH_TOKEN 直接从已 source 的 ZHIPU_AUTH_TOKEN 取真值,绝不从 stdout 解析
    if [[ -z "${ZHIPU_AUTH_TOKEN:-}" ]]; then
      echo "FATAL: persona '$persona' 需要 ZHIPU_AUTH_TOKEN, 但未设置" >&2
      return 1
    fi
    export ANTHROPIC_AUTH_TOKEN="$ZHIPU_AUTH_TOKEN"
  else
    unset ANTHROPIC_BASE_URL
    unset ANTHROPIC_AUTH_TOKEN
  fi

  # 代理
  if [[ "$proxy_check" == "1" ]]; then
    if curl -s --connect-timeout 1 http://127.0.0.1:1082 >/dev/null 2>&1; then
      export HTTPS_PROXY="http://127.0.0.1:1082"
      export HTTP_PROXY="http://127.0.0.1:1082"
      export ALL_PROXY="http://127.0.0.1:1082"
    else
      unset HTTPS_PROXY HTTP_PROXY ALL_PROXY
    fi
  else
    unset HTTPS_PROXY HTTP_PROXY ALL_PROXY
  fi
}

# ── Brain Whisper: 从 lessons.jsonl 注入历史教训到 persona system prompt ──
inject_whisper() {
  local persona="$1"
  local lessons_file="$HOME/.solar/harness/brain/lessons.jsonl"
  [[ ! -f "$lessons_file" ]] && return 0

  python3 -c "
import json, sys

persona = sys.argv[1]
lessons_file = sys.argv[2]
results = []

persona_map = {
    'planner': ['规划者', 'planner'],
    'builder': ['建设者', 'builder'],
    'evaluator': ['审判官', 'evaluator'],
    'second-builder': ['建设者(并行)', 'second-builder', '建设者'],
    'pm': ['产品经理', 'pm'],
    'architect': ['架构师', 'architect'],
    'lab-builder': ['实验建设者', 'lab-builder'],
    'lab-evaluator': ['实验审判官', 'lab-evaluator'],
    'observer': ['观察者', 'observer'],
}

match_set = set(persona_map.get(persona, [persona]))

with open(lessons_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        conf = d.get('confidence', 0)
        if conf < 0.7:
            continue
        tags = d.get('tags', [])
        # role match: persona name or CN name in tags
        if match_set.intersection(tags):
            results.append(d)
        elif conf >= 0.85:
            results.append(d)

# dedupe by lesson text, keep most recent
seen = set()
deduped = []
for r in reversed(results):
    txt = r.get('lesson', '')
    if txt not in seen:
        seen.add(txt)
        deduped.append(r)

if not deduped:
    sys.exit(0)

print()
print('## 历史教训 (Brain Whisper)')
for item in reversed(deduped[:3]):
    conf = item.get('confidence', 0)
    tags_str = ','.join(item.get('tags', []))
    print(f'- [{conf:.1f}] {item.get(\"lesson\", \"\")} ({tags_str})')
" "$persona" "$lessons_file" 2>/dev/null
}

# --print-config CLI 接口
if [[ "${1:-}" == "--print-config" ]]; then
  persona="${2:?Usage: $0 --print-config <planner|builder|evaluator>}"
  get_persona_config "$persona"
fi
