# 项目状态管理与恢复协议

每个项目目录维护一个 `state.json`，跟踪当前阶段、工作类型、流程模式、契约 revision、未解决问题和上次行动，用于可靠恢复中断流程。

Feature 首次接管或恢复前，必须按 `SKILL.md` 核实同项目真实、已确认且仍有效的 Solution 方案及其状态/确认来源。未通过时不创建或推进 PRD 阶段，说明具体缺口并读取 Solution Skill，由 Solution 补齐；不能从现有 PRD、代码或下游产物倒填解题完成。复杂 Bugfix 仍走既有专用规格路径。

---

## 项目目录与产物位置

已有明确项目目录时直接复用。新项目名称能从用户给定名称确定时直接沿用；确实缺失才询问。新建时**在当前工作区根目录创建以项目名命名的目录** `{项目名}/`，后续所有产出从一开始就直接落在这个目录里：

```bash
mkdir -p "{项目名}/output" "{项目名}/evidence" "{项目名}/drafts"
```

目录最终长这样（产物从生成那一刻就在最终位置，无需结尾整理）：

```
{项目名}/
├── output/          ← 最终交付：最完整的是 PRD详细版.md
│   ├── PRD详细版.md   ← ⭐ 人类主文档：业务全貌、关键规则与取舍
│   ├── requirements.md ← ⭐ 稳定 ID + EARS 的机器需求契约
│   ├── requirements-analysis.md ← 跨需求冲突、歧义、假设与边界分析
│   ├── PRD-summary.md ← 按汇报/阅读用途提炼
│   ├── PRD-dev.md     ← 按开发交接用途提炼
│   ├── ppt.md       ← 用户需要汇报时生成的方案 PPT 大纲
│   └── ppt/         ← 用户需要汇报时生成的幻灯片 p01.html … pNN.html
│   # Bugfix 模式用 bugfix.md 取代上述 PRD/PPT 主产物
├── assumptions.md
├── scene-anchor.md / proposal-v0.md / proposal-v1.md
├── debate-log.md
├── conversation.md  ← 仅已有存档或用户明确要求时保留
├── state.json
├── evidence/        ← 调研数据
└── drafts/          ← 协同写作过程稿
```

## state.json 结构

```json
{
  "state_schema_version": 1,
  "project_name": "fba-smart-restock",
  "project_started_at_utc": "2026-05-23T10:00:00Z",
  "last_updated_at_utc": "2026-05-23T14:32:00Z",

  "work_type": "feature",
  "workflow_mode": "standard",
  "delivery_target": "tdd",
  "stage_confirmations": {
    "stage1_shared_understanding": {"status": "confirmed", "confirmed_at_utc": "2026-05-23T11:00:00Z"},
    "stage4_5_v1": {"status": "pending", "confirmed_at_utc": null},
    "stage4_6_mvp": {"status": "pending", "confirmed_at_utc": null}
  },
  "contract_revision": 3,
  "source_ids_changed": ["AC-F03-01"],
  
  "current_stage": "4.5",
  "current_substep": "v1-user-decision",
  "completed_stages": ["0", "1", "2", "3", "4.1", "4.2", "4.3", "4.4"],
  "skipped_stages": [],
  
  "next_action": {
    "type": "user_decision",
    "description": "等企业家决定：批量导出是否进入本次交付？",
    "askuserquestion_options": ["后置批量导出（推荐）", "本次交付批量导出"]
  },
  
  "open_questions": [
    {"id": "OQ-7", "title": "批量导出是否进入本次交付", "kind": "decision", "category": "scope", "priority": "P1", "depends_on": [], "owner": "user", "status": "pending_user"}
  ],
  
  "key_decisions_made": [
    {"id": "D-1", "decision": "v1 用虚拟数据集 + 影子真实 SKU", "stage": "1", "rationale": "..."},
    {"id": "D-2", "decision": "每日决策（不是每周）", "stage": "1"}
  ],
  
  "category": "saas",
  
  "deliverables": {
    "scene_anchor": "scene-anchor.md",
    "proposal_v0": "proposal-v0.md",
    "proposal_v1": "proposal-v1.md",
    "debate_log": "debate-log.md",
    "assumptions": "assumptions.md",
    "conversation": null,
    "evidence": ["evidence/competitors.md", "evidence/benchmark.md"],
    "drafts": [],
    "final_prd": null,
    "requirements_contract": null,
    "requirements_analysis": null,
    "bugfix_contract": null,
    "prd_summary": null,
    "prd_dev": null,
    "ppt_outline": null,
    "ppt_pages": []
  }
}
```

### 阶段 1 前沿如何保存

`open_questions` 是未决节点和依赖关系的唯一事实源，不另建第二棵树。每个未决节点必须包含：

- `depends_on`：它依赖的未决节点 ID；依赖节点仍在 `open_questions` 时，本节点不能进入前沿；
- `owner`：`agent` 表示 AI 应自行查证；`user` 或具体的用户侧角色表示需要用户本人或其组织提供证据；
- `status`：用户节点用 `pending_user`；AI 事实节点用 `pending_research` 或 `researching`。已解决节点直接移出 `open_questions`。

阻塞方向的事实节点还要保存 `evidence_needed`、`acceptance_threshold`；用户已提出外部硬截止时再保存 `due_by`，未提出时可省略；`owner` 必须指向真正能取得证据的人或 Agent。这样“需要验证”才是可执行任务，而不是一句悬空备注。

事实查证节点严格使用下面的字段名和值，不得自行改成 `type`、`evidence_required`、`deadline`、`awaiting_evidence` 等近义字段：

```json
{
  "id": "OQ-8",
  "title": "夜间 CSV 是否满足审批前检查的数据新鲜度",
  "kind": "fact",
  "category": "system_dependency",
  "priority": "P1",
  "depends_on": [],
  "owner": "企业 IT 数据负责人",
  "status": "pending_user",
  "evidence_needed": "一周导出时间戳与审批入队时间样本",
  "acceptance_threshold": "95% 的数据延迟不超过 2 小时",
  "due_by": "3 个工作日内"
}
```

阶段 1 的 `next_action` 保存**本轮实际前沿快照**，用于中断后原样恢复，不替代 `open_questions`：

```json
"next_action": {
  "type": "stage1_frontier",
  "description": "等待用户回答当前前沿；事实查证并行进行",
  "question_ids": ["OQ-7", "OQ-9"],
  "research_ids": ["OQ-8"]
}
```

`question_ids` 只包含本轮实际问给用户的节点；`research_ids` 包含已经派发、尚未完成的事实查证，不论负责人是 AI 还是用户侧角色。即使当前只是在等待事实查证，`next_action.type` 仍使用 `stage1_frontier`，不得发明另一种类型。每次用户回答或查证返回后，先更新 `open_questions`，再按依赖关系重算并覆盖 `next_action`。用户要求分批回答时，`question_ids` 可以是完整可问前沿的子集；不得加入依赖仍未解决的节点。

恢复阶段 1 时，从 `open_questions` 重算当前前沿并覆盖 `next_action`，不向用户重复已解决的问题。

## Controller 何时更新 state.json

本文件的 `state.json` 指项目根目录的 PRD 状态。Solution 的 `solution/state.json` 按其原 Skill 维护，不迁移、不覆盖；Feature 通过接管门禁后，读取有效 `output/解题方案书.md` 及确认来源，将适用的产品层未决项和决定纳入既有字段，不复制一份 Solution 决策树，也不把解题阶段号当作 PRD 阶段号。既有 PRD 状态可以记录等待补齐的前置，但不能替 Solution 标记完成或确认。

以下状态实际变化时更新对应字段，同一轮的变化合并写回；在发出下一轮问题、切换阶段或暂停交接时保存必要增量。未变内容不重写，不按每个输出文件或工具调用单独登记。

- 每次阶段切换（如 0→1、4.6→5.1）
- 每次负责人拍板或 AI 在已有授权内决定、且满足「关键决策闸门」时（写入 key_decisions_made 并保留授权/确认来源；普通选择不写）
- 每次用户确认实际业务选择时，更新对应 `stage_confirmations` 并在场景/方案保留确认来源；普通确认虽不进入 `key_decisions_made`，但不能只留在聊天记录。继承已有明确确认时恢复其记录，不为补字段再次提问
- 阶段 1 每次回答后重算决策树：新增未决节点、移除已解决节点，并为 OQ 标记 `kind=fact|decision`、依赖、优先级和责任人
- 用户暂停时，把本轮 `question_ids` 和仍在运行的 `research_ids` 写入 `next_action`；只要仍有阻塞阶段 2 的 P0/P1 OQ，就不得把阶段 1 标记完成
- 产物位置或交付状态变化时，在同一检查点更新 `deliverables`，不随文件内容的每次编辑重复登记
- 每次切换 work_type/workflow_mode 或需求 revision（更新 contract_revision/source_ids_changed）

### 请求终点与历史状态兼容

`delivery_target` 默认 `tdd`，只记录交付目标，不代表前置已通过。字段缺失，或旧值 `prd` 只是历史默认、没有用户明确停止边界时，按当前默认补写为 `tdd`。用户明确暂停、终止或只修改当前阶段时，在现有 `next_action` 中保留该指示，不自动启动后续阶段，也不放行缺失输入。PRD 核心完成与整条链路完成分开判断：前置核实有效后，按 `references/连续执行.md` 从实际产物定位后续缺口并更新 `next_action`，不能在阶段 5 把整条链标为完成，也不重做仍有效的产物。

旧项目中的 `value_confirmation`、`stage3_research_sufficiency` 和旧价值章节可保留为历史记录，不再作为继续、恢复或完成的门槛；不要要求补写旧金额判断，也不要因这些字段缺失回退重问。阶段编号继续沿用，旧阶段 2 停留项目在 Solution 前置核实有效后整理已有目标与收益，再按真实未决问题继续。`state_schema_version` 保持不变，不新增状态文件。

### Feature 按实际依赖恢复

每次切换或恢复，先核对当前请求、真实 Solution 方案及其状态/确认来源；前置缺失、未完成、未确认或过时，先切换 Solution 补齐，不因下游文件存在而豁免。前置有效后，再处理当前阶段的实际缺口：

| 要继续的工作 | 必须已有 |
| :--- | :--- |
| 整理目标、写方案 | 已确认的共同理解；缺状态标记但场景锚点/对话有明确确认时恢复记录，不重复询问 |
| 定向查证 | 会改变当前判断的具体未知；已有证据足够或没有外部研究问题时不强制竞品报告、benchmark 或调研确认 |
| PRD 终稿 | 已确认的方案与本次范围、完整多端/渠道/接口边界和完成定义；沿用原确认，只问新增或改变的业务决定 |
| PRD 核心完成 / Design 接管 | `PRD详细版.md`、`requirements.md`、`requirements-analysis.md` 内容齐备，P0/P1 清零，必要校验通过 |
| 生成 PPT | 用户有汇报需要或明确请求，且核心 PRD 已定稿 |
| PPT 请求完成 | `ppt.md` 与声明的全部 `ppt/pNN.html` 已生成并完成全局自校验；不影响 PRD 核心完成或 Design |

PRD 核心三份齐备、范围已确认且必要校验通过后，Controller 才实际读取 Design Skill 并交付同版输入；设计及追溯齐备后再调度 TDD。可先做不依赖缺项的只读事实核查，但不能提前生成下游设计或验收产物，也不能由 PRD 代写。

方案和本次范围确认分别复用 `stage4_5_v1`、`stage4_6_mvp`，可以来自阶段 1 的整体方案或既有明确指令；后者沿用历史字段名，不表示本次只能做 MVP。恢复时从实际方案与 `requirements.md` 的 `Metadata.scope` 读取当前范围及各项 `Stage`，不得把后续阶段或多阶段请求缩成 MVP。文档中的范围确认章节用于记录结果，不把标题或历史字段缺失当成业务未确认；先从原记录补齐。确实找不到业务决定时才提出该问题。

可选调研和 PPT 未触发时，在现有 `skipped_stages` 记录对应阶段，并在 `next_action.description` 或已有记录中说明缘由；不得据此省略已确认范围。`tech-constrained` 只补查实际决定范围的技术约束并保存 `evidence/technical-feasibility.md`，不追加普遍的人工确认。

前置有效且核心三份文件通过必要检查后，将 `5` 记入 `completed_stages`，再读取对应 Skill、调度 Design/TDD 的实际缺口；用户明确暂停、终止或只修改当前阶段时按其指示处理，不放行缺失输入。浓缩版按用户用途从核心文件提炼并列明实际状态，未产出时不能声称已交付，但不挡 Design。存在已请求的 PPT 时继续处理该汇报任务，同时保留核心完成事实。文件存在本身不等于内容齐备或检查通过。

**写入方式**：先读现有内容并合并本次变化，再使用当前环境支持的原子替换方式写回；单纯先读再覆盖不等于原子写入。

## 启动与恢复协议

当用户说"启动 PRD 大师"或"继续上次的 PRD"时，Controller：

### Step 0: 扫描已有项目

```bash
ls -d */  # 找出所有项目（每个项目=工作区下一个以项目名命名的目录）
```

每个项目读 `state.json`，按 `last_updated_at_utc` 倒序。

### Step 1: 确定项目

用户已指定项目或当前上下文唯一明确时直接继续；只有多个候选且无法判断时，才用 AskUserQuestion 让用户选择：

```
question: "我看到你有几个进行中的项目"
options:
  - "继续 fba-smart-restock（上次到阶段 4.5，2 天前）"
  - "继续 xxx-xxx（上次到阶段 1.3，1 周前）"
  - "开始新项目"
```

### Step 2a: 选"继续"

Controller 读对应 state.json 的 `next_action`，先按上述当前规则核对依赖与已确认来源，再执行仍有效的 action。旧价值确认、固定调研数量、重复方案/MVP 确认或默认 PPT 的 action 不直接重放。

简述已有成果和下一步；用户需要展开时按下方「进度说明」展示，引用实际文件和仍有效的未决节点。

### Step 2b: 选"开始新项目"

普通请求按 Feature 路由，先执行 Solution 接管门禁，未通过时切换 Solution，不新建 PRD 阶段状态。通过后写入 `work_type=feature`、`delivery_target=tdd`，不得询问 Feature / Bugfix 二选一。默认写入 `workflow_mode=standard`；只有既有架构、严格性能/合规或迁移约束已有证据并会决定范围时，才自动写入 `tech-constrained`，且不让用户选择流程模式。只有用户明确提出“做 bugfix 规格”“整理复杂缺陷”或等价意图时，才改走 `work_type=bugfix` 专用链路。

## 恢复后继续

先核查当前阶段的有效输入，再执行仍适用的 `next_action`。用户提出变化使 Solution 方案失效时，切换 Solution 核实并更新受影响部分；前置仍有效时沿用已有范围和产物，不重问已确认事项。

## 进度说明

阶段变化时简述已有成果与下一步；用户主动询问或需要回顾时才展示完整进度卡。普通访谈消息以当前问题收尾，不追加卡片或教学；等待回答时仍可继续无依赖的已授权工作。

```text
📍 当前进度：{当前已完成的工作与剩余依赖}

已有成果：{实际文件、已确认范围或查证结论}
仍待解决：{具体业务决定/证据缺口；没有则不列}
接下来：{能直接继续的工作；需要用户时写清具体决定}
```

调研和 PPT 按需触发，不用“完成 N/7”制造固定完成度；时间只有存在可靠依据时才提供，不根据固定阶段或 Agent 数量估计。

PRD 核心交付时列出三份核心文件、必要检查的实际结果和未完成项，并给修改入口、下一阶段 Design 和接续句“继续，进入 Design”。链路尚未完成时不能把 PRD 核心完成说成全部完成；接续句供中断后恢复，正在执行时直接继续。摘要、开发交接版按用途生成；PPT 仅在汇报需要或明确请求时制作，与核心完成分别说明。只提供实际可查看的文件入口；PPT 交付时列出大纲、页面入口和已检查页数，未完成页面如实说明。

---

## 状态与确认来源

`state.json` 保存恢复所需的当前阶段、未决节点和下一步。实际业务确认在对应场景或方案中保留结论、必要原话或可定位的确认来源，其他记录引用同一处，不反复抄写。

默认不另存完整对话，也不继续累加 `conversation.md`；已有存档保留，只有用户明确需要对话存档时才维护它。`deliverables.conversation` 未产出时为 `null`，已有真实路径沿用；不因缺少全文存档回退流程或重问已确认事项。

## 兜底机制

`state.json` 损坏或缺失时，从实际产物、校验记录及已有业务确认来源重建现有字段；`conversation.md` 仅在真实存在且包含所需信息时作为补充，不是必需输入：

1. 由 `bugfix.md` / `requirements.md` 及用户请求确定 `work_type`；`delivery_target` 默认恢复为 `tdd`，同时保留用户明确暂停、终止或只修改当前阶段的指示。
2. Feature 先核查同项目真实 Solution 方案、状态及确认来源；缺失、未完成或过时则切换 Solution 补齐，禁止由 PRD/代码/下游文件追认解题完成。Bugfix 沿用专用规格路径。
3. 前置有效后，核查核心三份文件、稳定 ID、当前 revision、P0/P1 和已有校验证据；缺少有效检查时补当前必要检查，不因文件存在直接标完成。
4. 核心已完成则读取对应 Skill、调度 Design/TDD 的实际缺口；用户明确限制本轮工作时按其指示执行，但不豁免缺失输入。已有有效下游产物直接沿用，不补造或重做已完成内容；PPT 仅在已有明确请求时恢复未完成页面。
5. 核心未完成则读取场景锚点、方案、实际问题记录及其确认来源，恢复已确认业务选择及最早受影响的缺口；不能从没有记录的内容猜测用户已确认。旧价值字段或可选调研/PPT 缺失不触发回退。
6. 重算 `open_questions` 与 `next_action`，只询问确实未决定且影响当前交付的问题，不重问已解决事项。
