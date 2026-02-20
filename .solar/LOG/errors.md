# 错误日志 (Error Log)

> 错误码、堆栈、复现步骤

---

## 2026-02-12

### E001: OpenClaw GLM-5 Unknown Model

**错误信息:**
```
Error: Unknown model: zai/glm-5
```

**复现步骤:**
```bash
# 1. 配置 primary 为 glm-5
openclaw config set agents.defaults.model.primary "zai/glm-5"

# 2. 运行 agent
openclaw agent --local --message "test"
```

**原因分析:**
- OpenClaw 模型库 (2026.2.2-3) 未收录 GLM-5
- GLM-5 于 2026-02-11 发布，OpenClaw 尚未更新

**解决方案:**
- 短期: 使用 glm-4.7
- 长期: 等待 OpenClaw 更新模型库

**状态:** ⏳ 等待上游更新
