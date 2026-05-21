# Dispatch: headless pane agent routing replan

Run on Mac mini:

```bash
solar-harness multi-task start \
  --graph /Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.task_graph.json \
  --max-workers 2 \
  --once \
  --no-clear \
  --renderer plain
```

Monitor:

```bash
solar-harness multi-task status --no-clear --renderer plain
```
