#!/bin/bash
# ============================================
# Solar 自演进闭环系统 - 定时任务安装脚本
# 创建时间: 2026-02-19
# ============================================

set -e

LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
SOLAR_CORE="$HOME/.claude/core/cortex"

echo "🚀 Solar 自演进闭环系统 - 定时任务安装"
echo "=========================================="

# 创建 LaunchAgents 目录（如果不存在）
mkdir -p "$LAUNCH_AGENTS"

# ============================================
# 任务1: 数据关联 (每小时)
# ============================================
cat > "$LAUNCH_AGENTS/com.solar.data-linker.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.data-linker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/bun</string>
        <string>/Users/lisihao/.claude/core/cortex/data-linker.ts</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/solar-data-linker.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/solar-data-linker.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "✅ 创建 data-linker.plist (每小时)"

# ============================================
# 任务2: 路由评分更新 (每4小时)
# ============================================
cat > "$LAUNCH_AGENTS/com.solar.routing-score-updater.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.routing-score-updater</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/bun</string>
        <string>/Users/lisihao/.claude/core/cortex/routing-score-updater.ts</string>
    </array>
    <key>StartInterval</key>
    <integer>14400</integer>
    <key>StandardOutPath</key>
    <string>/tmp/solar-routing-score-updater.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/solar-routing-score-updater.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "✅ 创建 routing-score-updater.plist (每4小时)"

# ============================================
# 任务3: 反馈写记忆 (每6小时)
# ============================================
cat > "$LAUNCH_AGENTS/com.solar.feedback-to-memory.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.feedback-to-memory</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/bun</string>
        <string>/Users/lisihao/.claude/core/cortex/feedback-to-memory.ts</string>
    </array>
    <key>StartInterval</key>
    <integer>21600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/solar-feedback-to-memory.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/solar-feedback-to-memory.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "✅ 创建 feedback-to-memory.plist (每6小时)"

echo ""
echo "📋 定时任务清单:"
echo "  1. data-linker           - 每小时"
echo "  2. routing-score-updater - 每4小时"
echo "  3. feedback-to-memory    - 每6小时"
echo ""
echo "🔧 启动任务:"
echo "  launchctl load ~/Library/LaunchAgents/com.solar.data-linker.plist"
echo "  launchctl load ~/Library/LaunchAgents/com.solar.routing-score-updater.plist"
echo "  launchctl load ~/Library/LaunchAgents/com.solar.feedback-to-memory.plist"
echo ""
echo "📊 查看日志:"
echo "  tail -f /tmp/solar-*.log"
echo ""
echo "✅ 安装完成！"
