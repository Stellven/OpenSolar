#!/bin/bash
# ============================================
# Solar 自演进闭环系统 - 端到端验证
# 创建时间: 2026-02-19
# ============================================

DB="$HOME/.solar/solar.db"

echo "🧪 Solar 自演进闭环系统 - 端到端验证"
echo "=========================================="
echo ""

# ============================================
# 1. Trace 归因率验证
# ============================================
echo "📊 1. Trace 归因率验证"
echo "─────────────────────────────"

ATTRIBUTION=$(sqlite3 "$DB" "
SELECT
  COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) || '/' || COUNT(*) as ratio,
  ROUND(COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as rate
FROM evo_traces
")

echo "  Model 归因: $ATTRIBUTION%"

# ============================================
# 2. Q-scores 影响路由验证
# ============================================
echo ""
echo "📊 2. Q-scores 影响路由验证"
echo "─────────────────────────────"

ROUTING_STATS=$(sqlite3 "$DB" "
SELECT
  'Model' as type, COUNT(*) as total
FROM sys_routing_model WHERE effective_score IS NOT NULL
UNION ALL
SELECT 'Agent', COUNT(*) FROM sys_routing_agent WHERE effective_score IS NOT NULL
UNION ALL
SELECT 'Tool', COUNT(*) FROM sys_routing_tool WHERE effective_score IS NOT NULL
")

echo "$ROUTING_STATS" | while read type total; do
  echo "  $type 路由: $total 条"
done

# ============================================
# 3. 记忆增长验证
# ============================================
echo ""
echo "📊 3. 记忆增长验证"
echo "─────────────────────────────"

MEMORY_STATS=$(sqlite3 "$DB" "
SELECT namespace, COUNT(*) as count
FROM evo_memory_semantic
WHERE namespace IN ('lessons', 'experiences')
GROUP BY namespace
")

echo "$MEMORY_STATS" | while read ns count; do
  echo "  $ns: $count 条"
done

# ============================================
# 4. Q-scores 分布验证
# ============================================
echo ""
echo "📊 4. Q-scores 分布验证"
echo "─────────────────────────────"

QSCORE_STATS=$(sqlite3 "$DB" "
SELECT
  entity_type,
  COUNT(*) as count,
  ROUND(AVG(satisfaction), 3) as avg_satisfaction,
  ROUND(MIN(satisfaction), 3) as min_satisfaction,
  ROUND(MAX(satisfaction), 3) as max_satisfaction
FROM sys_quality_scores
GROUP BY entity_type
ORDER BY entity_type
")

echo "$QSCORE_STATS" | column -t -s '|'

# ============================================
# 5. 数据流验证
# ============================================
echo ""
echo "📊 5. 数据流验证"
echo "─────────────────────────────"

echo "  Traces: $(sqlite3 "$DB" "SELECT COUNT(*) FROM evo_traces")"
echo "  Feedback: $(sqlite3 "$DB" "SELECT COUNT(*) FROM evo_feedback_v2")"
echo "  Q-scores: $(sqlite3 "$DB" "SELECT COUNT(*) FROM sys_quality_scores")"
echo "  Memory: $(sqlite3 "$DB" "SELECT COUNT(*) FROM evo_memory_semantic WHERE namespace IN ('lessons', 'experiences')")"

# ============================================
# 6. 定时任务状态
# ============================================
echo ""
echo "📊 6. 定时任务状态"
echo "─────────────────────────────"

launchctl list | grep com.solar | grep -E "(data-linker|routing-score|feedback-to-memory)" | while read pid status label; do
  if [ "$status" = "0" ]; then
    echo "  ✅ $label (运行中)"
  else
    echo "  ⚠️  $label (退出码: $status)"
  fi
done

# ============================================
# 7. 闭环健康度评分
# ============================================
echo ""
echo "📊 7. 闭环健康度评分"
echo "─────────────────────────────"

# 计算各项得分
TRACE_SCORE=$(sqlite3 "$DB" "
SELECT CASE
  WHEN COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) > 50 THEN 100
  WHEN COUNT(CASE WHEN selected_model IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) > 20 THEN 50
  ELSE 0
END
FROM evo_traces
")

QSCORE_SCORE=$(sqlite3 "$DB" "
SELECT CASE
  WHEN COUNT(*) > 10 THEN 100
  WHEN COUNT(*) > 0 THEN 50
  ELSE 0
END
FROM sys_quality_scores
")

MEMORY_SCORE=$(sqlite3 "$DB" "
SELECT CASE
  WHEN COUNT(*) > 20 THEN 100
  WHEN COUNT(*) > 0 THEN 50
  ELSE 0
END
FROM evo_memory_semantic
WHERE namespace IN ('lessons', 'experiences')
")

HEALTH_SCORE=$(( ($TRACE_SCORE + $QSCORE_SCORE + $MEMORY_SCORE) / 3 ))

echo "  Trace 归因: $TRACE_SCORE / 100"
echo "  Q-scores:   $QSCORE_SCORE / 100"
echo "  记忆增长:   $MEMORY_SCORE / 100"
echo "  ─────────────────────"
echo "  综合健康度: $HEALTH_SCORE / 100"

if [ $HEALTH_SCORE -ge 80 ]; then
  echo "  状态: ✅ 优秀"
elif [ $HEALTH_SCORE -ge 60 ]; then
  echo "  状态: ⚠️  良好"
else
  echo "  状态: ❌ 需改进"
fi

echo ""
echo "✅ 验证完成！"
