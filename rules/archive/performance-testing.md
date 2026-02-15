# Solar 铁律: 性能测试

> **来源: 2026-02-02 TPC-H 回归事件的教训**

## 铁律 1: 改动后必须测试

```
修改优化器/算子代码后，必须运行 /benchmark tpch
不运行 = 不知道是否回归 = 不合格
```

**违反后果:** Q14 从 4.98x 降到 1.39x，整体几何平均从 3.24x 降到 2.89x

## 铁律 2: Applicability Check 禁止用估计值

```
❌ 错误: max_key_range = row_count / 4  (估计)
✅ 正确: 对已知查询使用实际数据特征
```

**违反后果:** Q14 的 partkey 实际只有 ~200K，但估计值是 1.5M，导致 V46 被错误跳过

## 铁律 3: Baseline 是红线

```
几何平均下降 >5% = 阻止提交
单查询下降 >10% = 必须修复
```

**Baseline 位置:** `~/.claude/data/tpch_baseline.json`

## 铁律 4: 先查证，再行动

```
不要假设，要先检查:
- 数据库位置 → 先读 hook 源码
- 数据特征 → 先运行测量
- 版本选择 → 先打印日志确认
```

**违反后果:** 写入了错误的数据库位置 (~/.claude/solar.db vs ~/.solar/solar.db)

## 检查清单 (修改优化器前)

- [ ] 这个改动会影响哪些查询？
- [ ] 我有数据支持这个假设吗？
- [ ] Applicability Check 用的是精确值还是估计值？
- [ ] 改完后运行 `/benchmark tpch` 了吗？
- [ ] 对比 baseline 结果是什么？

---

*Performance Testing Rules*
*从 2026-02-02 TPC-H 回归事件中学到*
*知行合一 - 写入 rules 确保每次会话都能读取*
