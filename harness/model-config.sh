#!/bin/bash
# Solar Harness — 模型路由配置
# 按需用 Zhipu GLM 或 Claude OAuth
# 注：tmux 内 Claude OAuth 实测可用 (2026-05-08 验证 planner+evaluator+builder pane 均跑 Claude Max)
# persona 模型选择见 lib/persona-config.sh, 默认: planner/evaluator/pm=Opus, builder=GLM-5.1→Sonnet fallback

export ZHIPU_BASE_URL="https://api.z.ai/api/anthropic"
export ZHIPU_MODEL="GLM-5.1"

# Token 从 secrets 文件读取,不硬编码
SECRETS_FILE="$HOME/.solar/secrets/zhipu.env"
if [[ -f "$SECRETS_FILE" ]]; then
  source "$SECRETS_FILE"
fi

# Coding Plan 包月 token (与 cc-switch DB 同源, 2026-05-06 修复 1210)
# shell env 里的旧 Pay-as-you-go token (1a8b9adc...) 不能用,必须强覆盖
CODING_PLAN_TOKEN="cee4edb0bb554b709623d2c2d63c4065.q0unUsiCytMqBo07"
if [[ -z "${ZHIPU_AUTH_TOKEN:-}" || "${ZHIPU_AUTH_TOKEN:0:12}" == "1a8b9adce224" ]]; then
  export ZHIPU_AUTH_TOKEN="$CODING_PLAN_TOKEN"
fi
# 兼容旧命名 ZHIPU_API_KEY
export ZHIPU_API_KEY="$ZHIPU_AUTH_TOKEN"

# 缺失凭据时不要直接 exit。
# 启动链会在 persona-config.sh 内决定是否回退到 Claude 默认模型。

# SOLAR_NO_ZHIPU 持久化 flag (2026-05-07): tmux respawn-pane 时一次性 env 会丢失,
# 改用 flag 文件,每次 source model-config.sh 自动恢复.
# 删除 flag 即可恢复 GLM 优先: rm ~/.solar/secrets/no-zhipu.flag
if [[ -f "$HOME/.solar/secrets/no-zhipu.flag" ]]; then
  export SOLAR_NO_ZHIPU=1
fi
