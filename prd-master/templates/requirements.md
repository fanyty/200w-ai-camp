# {{产品名}} Requirements Contract

## Metadata

- work_type: feature
- workflow_mode: standard
- revision: 1
- scope: {{本次已确认范围}}
- source_prd: PRD详细版.md
- status: active

> scope 沿用本次明确请求，填写实际包含的 Stage 名称；多阶段范围逐项列出。各 US/REQ 的 Stage 使用相同名称，不因套用模板改成 MVP 或后置已确认功能。

## External capability configuration

| Capability | Credential owner | Configuration actor | Surface | Scope | Lifecycle | Stage | Requirement IDs |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| none | - | - | - | - | - | - | - |

## Capability prerequisites

| Prerequisite | Status | Owner | Evidence or deadline | Fallback | Stage | Requirement IDs |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| none | - | - | - | - | - | - |

## Feature F01 · {{功能名}}

### US-F01-01 · {{用户故事}}

- Role: {{角色}}
- Goal: {{目标}}
- Value: {{价值}}
- Stage: {{所属阶段}}
- Status: active

### REQ-F01-01 · {{行为需求}}

- Story: US-F01-01
- Stage: {{所属阶段}}
- Revision: 1
- Status: active

### AC-F01-01 · {{可观察结果}}

- Parent: REQ-F01-01
- Priority: P0
- EARS:

```text
WHEN {{明确条件或事件}}
THE SYSTEM SHALL {{单一、可验证、带阈值的结果}}
```

## Non-functional requirements

### NFR-001 · {{非功能指标}}

- Applies-to: REQ-F01-01
- Revision: 1
- Status: active
- Measure: {{指标、阈值、单位、采样与时间窗}}
