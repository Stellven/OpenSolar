#!/bin/bash
# 启动 Chrome 调试模式
# 用于 ChatGPT 网页自动化

echo "🚀 启动 Chrome 调试模式..."
echo ""
echo "⚠️  请先完全关闭所有 Chrome 窗口"
echo ""
read -p "按 Enter 继续..."

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome/Profile 1" \
  https://chatgpt.com &

echo ""
echo "✅ Chrome 已启动"
echo "📌 调试端口: 9222"
echo ""
echo "请在 Chrome 中确认已登录 ChatGPT，然后回来继续"
