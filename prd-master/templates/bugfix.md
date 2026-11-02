# {{缺陷名}} Bugfix Contract

## Metadata

- work_type: bugfix
- revision: 1
- status: confirmed
- affected_version: {{版本}}

### BUG-001 · {{缺陷摘要}}

- Severity: {{级别}}
- Scope: {{影响范围}}

### REPRO-001 · {{最小复现}}

- Environment: {{环境}}
- Preconditions: {{前置条件}}
- Steps: {{可执行步骤}}
- Evidence: {{日志/截图/失败测试路径}}

### CUR-001 · {{当前错误行为}}

```text
WHEN {{触发条件}}
THE SYSTEM {{实际错误结果}}
```

### EXP-001 · {{预期正确行为}}

```text
WHEN {{同一触发条件}}
THE SYSTEM SHALL {{正确且可验证的结果}}
```

### UNCH-001 · {{必须保持的既有行为}}

```text
WHEN {{相邻但不应受影响的条件}}
THE SYSTEM SHALL CONTINUE TO {{既有结果}}
```

### CON-001 · {{修复约束}}

- Must-not-change: {{接口/数据/兼容行为}}
- Reason: {{证据或用户决策}}
