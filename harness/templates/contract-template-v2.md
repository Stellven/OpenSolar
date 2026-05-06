---
name: {{name}}
description: {{description}}
triggers: [{{triggers}}]
---

# Sprint Contract — {{sprint_id}}
Created: {{created_at}}
Status: drafting
Phase: spec
Project: {{project_dir}}

## When to Use

### Use When
- (condition 1)
- (condition 2)
- (condition 3)

### Do NOT Use When
- (exclusion 1)
- (exclusion 2)
- (exclusion 3)

## Requirements

{{requirements}}

## Process

1. **Spec**: Define requirements and acceptance criteria
2. **Plan**: Design implementation approach
3. **Build**: Implement the code
4. **Test**: Verify functionality
5. **Review**: Evaluator checks against Done criteria
6. **Ship**: Finalize and deliver

## Definition of Done

- [ ] D1: (criterion)
  <!-- verify: cmd="" expected_exit=0 output_pattern="" -->
- [ ] D2: (criterion)
  <!-- verify: cmd="" expected_exit=0 output_pattern="" -->
- [ ] D3: (criterion)
  <!-- verify: cmd="" expected_exit=0 output_pattern="" -->

## Scope

### In Scope
- (item 1)
- (item 2)

### Out of Scope
- (item 1)
- (item 2)

## Red Flags

- **No mock/stub/TODO**: `grep -rE 'TODO|FIXME|mock|stub|模拟'` in implementation files must return empty
- **No hardcoded secrets**: `grep -rE 'password|secret|token|api.key' --include='*.sh' --include='*.ts' --include='*.py'` must return empty (excluding template placeholders)
- **No temp artifacts**: No important outputs stored in /tmp

## Constraints

> Planner fills in

## Implementation Files

> Builder fills in after completion

## Evaluation Dimensions

1. **Functional completeness**: Each Done criterion checked
2. **Code quality**: Error handling, edge cases, security
3. **Contract compliance**: Within scope
4. **Maintainability**: Naming, structure
