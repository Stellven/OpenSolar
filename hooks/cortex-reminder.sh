#!/bin/bash
# Cortex First 提醒 - 每次会话开始时自动提醒

# 统计知识库数据
TOTAL_SOURCES=$(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM cortex_sources" 2>/dev/null || echo "0")
THUNDER_MLX=$(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM cortex_sources WHERE citation_key LIKE 'thundermlx_%'" 2>/dev/null || echo "0")
THUNDER_DUCK=$(sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM cortex_sources WHERE citation_key LIKE 'thunderduck_%'" 2>/dev/null || echo "0")

cat << EOF

┌─────────────────────────────────────────────────────────────────┐
│  🧠 Cortex First - 设计/开发前必查知识库                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  知识库状态:                                                    │
│  • 总计: ${TOTAL_SOURCES} 条知识点                                         │
│  • ThunderMLX 优化: ${THUNDER_MLX} 条 (TTFT/量化/投机解码/...)              │
│  • ThunderDuck 优化: ${THUNDER_DUCK} 条 (SIMD/Bitmap/UMA/...)               │
│                                                                 │
│  触发词: 设计/实现/优化/开发/写个/做个 xxx                      │
│  → 必须先查 Cortex，再设计方案                                  │
│                                                                 │
│  快速查询:                                                      │
│  sqlite3 ~/.solar/solar.db "SELECT title FROM cortex_sources   │
│    WHERE finding LIKE '%关键词%' LIMIT 5;"                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

EOF
