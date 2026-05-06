#!/bin/bash
# Solar Harness — 模型路由配置
# 全部化身用 Zhipu GLM (Anthropic OAuth 在 tmux 里因 macOS Keychain 限制不可用)

export ZHIPU_BASE_URL="https://open.bigmodel.cn/api/anthropic"
export ZHIPU_MODEL="glm-5.1"

# Token 从 secrets 文件读取,不硬编码
SECRETS_FILE="$HOME/.solar/secrets/zhipu.env"
if [[ -f "$SECRETS_FILE" ]]; then
  source "$SECRETS_FILE"
fi

# 缺失凭据时 loud-fail
if [[ -z "${ZHIPU_AUTH_TOKEN:-}" ]]; then
  echo "FATAL: ZHIPU_AUTH_TOKEN not set. Create $SECRETS_FILE or export ZHIPU_AUTH_TOKEN" >&2
  exit 1
fi
