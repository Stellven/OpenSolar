# Plan — YouTube Transcript Epic S05 Verification-Release

gate: `G_YT_S05_PASSED`
knowledge_context: solar-harness context inject used
upstream: S03 passed (6 acceptance ok=True) + S04 passed (C1-C4 spec)
downstream: epic close (parent_check_ready=true)

## 0. DAG (6 节点)

```
V1_real_dashboard_cli_e2e (sonnet, 关键)
   ├─→ V2_premium_asr_real_e2e (sonnet, OpenAI + budget)
   ├─→ V3_production_pollution_cleanup (sonnet, 165 真清理)
   └─→ V4_regression_aggregation (glm-5.1, 93 条全验证)
                                  └─→ V5_release_docs (sonnet)
                                        └─→ V6_join_epic_ready (sonnet)
```

## 1. 节点验收

| 节点 | 关键验收 |
|------|----------|
| **V1** dashboard+CLI E2E | `transcript-status --json` 9 字段 + HTML/TUI 渲染 + 6 CLI dry-run + legacy 兼容 (6 evidence JSON) |
| **V2** premium E2E | 5 phase (prep/trigger/call/verify/fallback) + secret scan + cost $0.006/min + $20/day cap (5 evidence JSON) |
| **V3** 165 cleanup | dry-run 验 165 → SQLite 备份 → --apply → count_after=0 (3 evidence + 备份路径) |
| **V4** regression | 67 AC + 13 决议 + 4 OQ + 6 acceptance + 3 OQ-C5 = 93 条全 PASS/FAIL (regression_report.json) |
| **V5** release docs | RELEASE.md (epic 总览 + 5 sprint 摘要 + evidence + rollback + ATLAS hook + OQ-C5 carried) + eval |
| **V6** join | traceability parent_check_ready=true + handoff; **不主动 close epic** |

## 2. 写范围 + STRICT

| 操作 | 路径 |
|------|------|
| V1-V6 | `reports/youtube/s05-acceptance/` + `docs/youtube-transcript/RELEASE.md` + sprint artifacts |
| V3 backup | `~/.solar/harness/backups/youtube/<ts>/` |
| **严格禁止** | OpenAI API key 泄露 / 超 $20 budget / 不备份直接清理 / 删 Knowledge accepted / 重启服务进程 / 主动 close epic / 改 S03 lib 源码 / 用乐观词 |

## 3. 并发边界

- Wave 1: V1 (关键路径)
- Wave 2 (3 并行 depends_on V1): V2, V3, V4
- Wave 3: V5 (join V2+V3+V4)
- Wave 4 (join): V6

## 4. 验证命令

### V2 premium ASR (sample)
```bash
# Phase 1 准备
export SOLAR_YOUTUBE_PREMIUM_OPENAI_KEY="sk-..."  # 从 secret store
grep -i 'sk-' ~/.solar/harness/logs/  # 应空
# Phase 2-3 触发+调用
python3 -c "from harness.lib.youtube.premium_escape import call_gpt4o; call_gpt4o(...)"
# Phase 4 验证
sqlite3 ~/.solar/harness/youtube.db "SELECT SUM(cost) FROM youtube_premium_asr_calls WHERE date(created_at)=date('now')"
# 应 ≤ 20.00
```

### V3 165 cleanup (sample)
```bash
# 备份
cp ~/.solar/harness/youtube.db ~/.solar/harness/backups/youtube/$(date +%Y%m%dT%H%M%S)/youtube.db.backup
# dry-run
solar-harness wiki tech-hotspot-radar audit-transcript-quality --repair-pollution --dry-run --json
# apply
solar-harness wiki tech-hotspot-radar audit-transcript-quality --repair-pollution --apply --json
# 验证
sqlite3 ~/.solar/harness/youtube.db "SELECT COUNT(*) FROM youtube_transcripts WHERE transcript_status='missing' AND transcript_clean IS NOT NULL"
# 应 = 0
```

## 5. no-live-pane-mutation 保护

- 绝不 tmux send-keys 任何生产 pane (依赖 TUI S05 治理)
- 绝不重启 harness / coordinator / chain-watcher / ThunderOMLX / 7 个 non-multi_task Python 服务
- 绝不删 Knowledge vault accepted artifacts
- V3 必须先 SQLite 备份再 --apply

## 6. Rollback / Stop Rules

### Rollback
- V1 失败 → S03 接口偏离 round-2
- V2 失败 → OpenAI fallback 验证 + ATLAS; key 泄露 → sprint FAIL + 撤回 key
- V3 失败 → SQLite 回滚 (复制 backup over)
- V4 任一 AC FAIL → 对应 sprint round-2
- V5/V6 失败 → 单节点重派

### Stop Rules
- OpenAI key 泄露 → 立即 FAIL + incident
- 超 $20 budget → 立即 FAIL + ATLAS
- V3 未备份直接清理 → 立即 FAIL
- V3 清理后 count 不为 0 → S03 round-2
- V6 主动 close epic → 立即 FAIL
- 不重启 service / 删 Knowledge / 改 S03 lib / 用乐观词

## 7. SLO

| 指标 | hard | soft |
|------|------|------|
| 6 V 节点全 PASS | < 6 → sprint FAIL | n/a |
| OpenAI key 泄露 | > 0 → 立即 FAIL + incident | n/a |
| budget 超限 | > $20 → 立即 FAIL | n/a |
| 165 清理后 count | > 0 → S03 round-2 | n/a |
| 67 S01 AC PASS | < 67 → FAIL → round-2 | n/a |
| V6 主动 close epic | > 0 → 立即 FAIL (违规) | n/a |
| 乐观词 | > 0 → FAIL | n/a |

## 8. 给后续接力

V6 traceability `parent_check_ready=true` → coordinator parent-check → epic auto-close:
- S01 ✅ S02 ✅ S03 ✅ S04 ✅ S05 (本)
- AI Influence digest 消费 YouTube transcript 输出 (跨 epic)
- 与 HF Paper Insight + Social Signal Plane 共振 Influence Source

## 9. Knowledge Context

50K+ upstream evidence self-contained. mirage degraded → QMD + Obsidian + Solar DB.
