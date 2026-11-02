#!/usr/bin/env python3
"""Validate feature requirements.md or bugfix.md contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path


HEADING_ID = re.compile(
    r"^###\s+((?:US-F\d{2,3}-\d{2,3}|REQ-F\d{2,3}-\d{2,3}|AC-F\d{2,3}-\d{2,3}|NFR-\d{3}|BUG-\d{3}|REPRO-\d{3}|CUR-\d{3}|EXP-\d{3}|UNCH-\d{3}|CON-\d{3}))\b",
    re.MULTILINE,
)
EXTERNAL_CONFIGURATION_SECTION = "## External capability configuration"
CAPABILITY_PREREQUISITES_SECTION = "## Capability prerequisites"
PRODUCT_CONFIGURATION_SURFACES = {"onboarding", "settings", "admin"}
CONFIGURATION_SURFACES = PRODUCT_CONFIGURATION_SURFACES | {
    "deployment-secret",
    "none",
}
CONFIGURATION_SCOPES = {"system", "tenant", "user", "project", "none"}
REQ_ID_RE = re.compile(r"REQ-F\d{2,3}-\d{2,3}")
EXTERNAL_CAPABILITY_SIGNAL_RE = re.compile(
    r"\bLLM\b|大模型|OpenAI|Anthropic|Claude|DeepSeek|Qwen|Gemini|"
    r"API[\s_-]*Key|外部\s*(?:API|服务)|第三方\s*(?:API|服务)|"
    r"支付网关|短信(?:服务|验证码|通道)|邮件(?:服务|验证码|发送通道)|地图服务|对象存储",
    re.IGNORECASE,
)
CAPABILITY_PREREQUISITE_SIGNAL_RE = re.compile(
    EXTERNAL_CAPABILITY_SIGNAL_RE.pattern
    + r"|第三方登录|OAuth|微信登录|Apple\s*登录|邮箱验证码|邮件登录链接|"
    r"App\s*Store|TestFlight|Google\s*Play|"
    r"(?:iOS|Android|安卓).{0,20}(?:发布|上架|分发)|"
    r"(?:发布|上架|分发).{0,20}(?:iOS|Android|安卓)|"
    r"推送证书|APNs|FCM|行业资质|硬件设备",
    re.IGNORECASE,
)
PREREQUISITE_STATUSES = {"ready", "committed"}
FUTURE_PREREQUISITE_STATUSES = PREREQUISITE_STATUSES | {"planned", "unknown"}
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}|^_?(?:TBD|TODO|PLACEHOLDER)_?$|^(?:\.{3}|…+|-)$", re.IGNORECASE)
PREREQUISITE_ROW_RULES = (
    (
        "短信通道",
        re.compile(r"短信|\bSMS\b", re.IGNORECASE),
        re.compile(r"短信|SMS", re.IGNORECASE),
    ),
    (
        "iOS 分发账号/签名",
        re.compile(
            r"App\s*Store|TestFlight|"
            r"iOS.{0,20}(?:发布|上架|分发)|"
            r"(?:发布|上架|分发).{0,20}iOS",
            re.IGNORECASE,
        ),
        re.compile(r"Apple|iOS|App\s*Store|开发者账号|签名|证书", re.IGNORECASE),
    ),
)


def blocks(text: str) -> dict[str, str]:
    matches = list(HEADING_ID.finditer(text))
    result: dict[str, str] = {}
    for match in matches:
        following = re.search(r"^#{1,3}\s+", text[match.end():], re.MULTILINE)
        end = match.end() + following.start() if following else len(text)
        identifier = match.group(1)
        if identifier in result:
            raise ValueError(f"重复定义 ID: {identifier}")
        result[identifier] = text[match.start():end]
    return result


def section(text: str, title: str) -> str | None:
    matches = list(re.finditer(rf"^## {re.escape(title)}[^\S\n]*$", text, re.MULTILINE))
    if len(matches) != 1:
        return None
    start = matches[0].end()
    following = re.search(r"^#{1,2}\s+", text[start:], re.MULTILINE)
    return text[start:start + following.start()] if following else text[start:]


def field(block: str, name: str) -> str | None:
    match = re.search(rf"^- {re.escape(name)}:[^\S\n]*(.*?)[^\S\n]*$", block, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().strip("`") if match else None


def require_field(block: str, name: str, label: str, errors: list[str]) -> str:
    value = field(block, name) or ""
    if not value or PLACEHOLDER_RE.fullmatch(value):
        errors.append(f"{label} 缺少有效 {name}（不能留空或使用模板占位）")
    if len(re.findall(rf"^- {re.escape(name)}:", block, re.MULTILINE | re.IGNORECASE)) > 1:
        errors.append(f"{label} 重复声明 {name}")
    return value


def validate_revision(block: str, label: str, errors: list[str]) -> str:
    value = require_field(block, "Revision", label, errors)
    if not re.fullmatch(r"[1-9]\d*", value):
        errors.append(f"{label} Revision 必须为正整数")
    return value


def normalize_stage(value: str) -> str | None:
    """Normalize numbered aliases and retain confirmed names as exact identities."""
    value = value.strip().strip("`")
    if not value or re.search(
        r"\{\{|\}\}|^\{[^{}]*\}$|[,，]|^(?:_?(?:TBD|TODO|PLACEHOLDER|unknown|missing)_?|待定|待确认|未知|缺失|\.{3}|…+|-)$",
        value, re.IGNORECASE,
    ):
        return None
    if value.upper() == "MVP":
        return "阶段1"
    match = re.fullmatch(
        r"阶段\s*([0-9]+|[一二三四五六七八九十])\s*(?:[（(]\s*MVP\s*[）)]|MVP)?",
        value, re.IGNORECASE,
    )
    if not match:
        return value
    number = match.group(1)
    stage = int(number) if number.isascii() and number.isdecimal() else "一二三四五六七八九十".index(number) + 1
    if stage < 1 or ("MVP" in value.upper() and stage != 1):
        return None
    return f"阶段{stage}"


def parse_scope(value: str | None, label: str, errors: list[str]) -> set[str]:
    stages: set[str] = set()
    for item in re.split(r"[,，]", value or ""):
        stage = normalize_stage(item)
        if stage is None:
            errors.append(f"{label} 含空白或未知 Stage: {item.strip() or '(空)'}")
        else:
            stages.add(stage)
    return stages


def validate_metadata(text: str, errors: list[str]) -> tuple[str, str, set[str]]:
    metadata = section(text, "Metadata")
    if metadata is None:
        errors.append("必须有且只有一个 Metadata 章节")
        metadata = ""
    metadata = re.split(r"^###\s+", metadata, maxsplit=1, flags=re.MULTILINE)[0]
    work_type = require_field(metadata, "work_type", "Metadata", errors)
    if work_type not in {"feature", "bugfix"}:
        errors.append("Metadata work_type 只允许 feature/bugfix")
    revision = validate_revision(metadata, "Metadata", errors)
    status = require_field(metadata, "status", "Metadata", errors)
    allowed_statuses = {"confirmed", "unconfirmed"} if work_type == "bugfix" else {"active"}
    if status not in allowed_statuses:
        errors.append(f"Metadata status 非法: {status}")
    if work_type == "bugfix":
        require_field(metadata, "affected_version", "Metadata", errors)
        return work_type, revision, set()
    mode = require_field(metadata, "workflow_mode", "Metadata", errors)
    if mode not in {"standard", "tech-constrained"}:
        errors.append("Metadata workflow_mode 只允许 standard/tech-constrained")
    require_field(metadata, "source_prd", "Metadata", errors)
    scope_value = field(metadata, "scope")
    if scope_value is not None:
        require_field(metadata, "scope", "Metadata", errors)
    scope = parse_scope("MVP" if scope_value is None else scope_value, "Metadata scope", errors)
    return work_type, revision, scope


def row_is_current(stage: str, requirement_cell: str, current_reqs: set[str], scope: set[str], errors: list[str], label: str) -> bool:
    stages = parse_scope(stage, f"{label} Stage", errors)
    requirement_ids = set(REQ_ID_RE.findall(requirement_cell))
    # References are authoritative; a future label cannot hide a current dependency.
    return bool(requirement_ids & current_reqs) if requirement_ids else bool(stages & scope)


def table_cells(line: str) -> list[str]:
    """Keep escaped pipes inside Markdown cells."""
    cells: list[str] = []
    start = 0
    backslashes = 0
    stripped = line.strip()
    for index, character in enumerate(stripped):
        if character == "|" and backslashes % 2 == 0:
            cells.append(stripped[start:index].strip().strip("`"))
            start = index + 1
        backslashes = backslashes + 1 if character == "\\" else 0
    cells.append(stripped[start:].strip().strip("`"))
    if stripped.startswith("|"):
        cells.pop(0)
    if cells and not cells[-1] and stripped.endswith("|"):
        cells.pop()
    return cells


def capability_table_rows(text: str, heading: str, header: list[str], errors: list[str]) -> list[list[str]]:
    title = heading.removeprefix("## ")
    body = section(text, title)
    if body is None:
        errors.append(f"必须有且只有一个 {title} 章节" if heading in text else f"缺少 {title} 章节")
        return []
    rows: list[list[str]] = []
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = table_cells(line)
        if cells == header or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) != len(header):
            errors.append(f"{title} {cells[0] if cells else '(空行)'} 列数错误：应为 {len(header)} 列，实际 {len(cells)} 列")
            continue
        rows.append(cells)
    if not rows:
        errors.append(f"{title} 没有合法责任行")
    return rows


def without_section(text: str, heading: str) -> str:
    if heading not in text:
        return text
    before, after = text.split(heading, 1)
    following = re.search(r"\n##\s+", after)
    return before + (after[following.start():] if following else "")


def validate_external_configuration(
    rows: list[list[str]],
    reqs: set[str],
    current_reqs: set[str],
    selected_stages: set[str],
    errors: list[str],
) -> None:
    if not rows:
        return

    none_rows = [row for row in rows if row[0].lower() == "none"]
    if none_rows:
        if len(rows) != 1 or none_rows[0][1:] != ["-"] * 7:
            errors.append("没有外部能力时只能保留一行 none，其他列必须为 -")
        return

    for capability, owner, actor, surface, scope, lifecycle, stage, requirement_cell in rows:
        label = f"外部能力 {capability}"
        requirement_ids = set(REQ_ID_RE.findall(requirement_cell))
        for requirement_id in sorted(requirement_ids - reqs):
            errors.append(f"{label} 引用未定义需求 {requirement_id}")
        if surface in PRODUCT_CONFIGURATION_SURFACES and not requirement_ids:
            errors.append(f"{label} 通过 {surface} 配置，必须关联至少一个真实 REQ")
        if not row_is_current(stage, requirement_cell, current_reqs, selected_stages, errors, label):
            continue
        for field_name, value in (
            ("Credential owner", owner),
            ("Configuration actor", actor),
            ("Surface", surface),
            ("Scope", scope),
            ("Lifecycle", lifecycle),
            ("Stage", stage),
        ):
            if not value or PLACEHOLDER_RE.fullmatch(value):
                errors.append(f"{label} 缺少 {field_name}")
        if surface not in CONFIGURATION_SURFACES:
            errors.append(
                f"{label} 的 Surface 非法: {surface}；"
                "只允许 deployment-secret/onboarding/settings/admin/none"
            )
        if scope not in CONFIGURATION_SCOPES:
            errors.append(
                f"{label} 的 Scope 非法: {scope}；"
                "只允许 system/tenant/user/project/none"
            )

def validate_capability_prerequisites(
    rows: list[list[str]],
    configuration_rows: list[list[str]],
    reqs: set[str],
    current_reqs: set[str],
    scope: set[str],
    errors: list[str],
) -> None:
    if not rows:
        return

    current_configurations = [
        row for row in configuration_rows
        if row[0].lower() != "none"
        and row_is_current(row[6], row[7], current_reqs, scope, errors, f"外部能力 {row[0]}")
    ]
    none_rows = [row for row in rows if row[0].lower() == "none"]
    if none_rows:
        if len(rows) != 1 or none_rows[0][1:] != ["-"] * 6:
            errors.append("没有方案前置能力时只能保留一行 none，其他列必须为 -")
        if current_configurations:
            errors.append("外部能力配置表已声明本期依赖，前置能力不能填写 none")
        return

    current_rows: list[list[str]] = []
    for prerequisite, status, owner, evidence, fallback, stage, requirement_cell in rows:
        label = f"方案前置能力 {prerequisite}"
        current = row_is_current(stage, requirement_cell, current_reqs, scope, errors, label)
        allowed = PREREQUISITE_STATUSES if current else FUTURE_PREREQUISITE_STATUSES
        if status not in allowed:
            errors.append(
                f"{label} 的 Status 非法: {status}；本期只允许 ready/committed，后续可用 planned/unknown"
            )
        if current:
            current_rows.append([prerequisite, status, owner, evidence, fallback, stage, requirement_cell])
        if current or status in PREREQUISITE_STATUSES:
            for field_name, value in (("Owner", owner), ("Evidence or deadline", evidence), ("Fallback", fallback)):
                if not value or PLACEHOLDER_RE.fullmatch(value):
                    errors.append(f"{label} 缺少 {field_name}")

        requirement_ids = set(REQ_ID_RE.findall(requirement_cell))
        if not requirement_ids:
            errors.append(f"{label} 必须关联至少一个真实 REQ")
        for requirement_id in sorted(requirement_ids - reqs):
            errors.append(f"{label} 引用未定义需求 {requirement_id}")

    for configuration in current_configurations:
        capability, *_, requirement_cell = configuration
        requirement_ids = set(REQ_ID_RE.findall(requirement_cell)) & current_reqs
        relevant_rows = [row for row in current_rows if not requirement_ids or requirement_ids & set(REQ_ID_RE.findall(row[6]))]
        if not relevant_rows:
            errors.append(f"外部能力 {capability} 没有对应本期需求的方案前置能力")
        for label, signal_re, prerequisite_re in PREREQUISITE_ROW_RULES:
            if signal_re.search(capability) and not any(prerequisite_re.search(row[0]) for row in relevant_rows):
                errors.append(f"配置表声明依赖{label}，但方案前置能力表没有对应行")


def validate_ears(block: str, identifier: str, result_marker: str, errors: list[str]) -> None:
    match = re.search(rf"\bWHEN\b(.*?)\b{re.escape(result_marker)}\b(.*)", block, re.DOTALL)
    if match:
        condition = match.group(1).strip()
        result = re.split(r"^\s*(?:```|#{1,6}\s|- [A-Za-z][A-Za-z -]*:)", match.group(2), maxsplit=1, flags=re.MULTILINE)[0].strip()
    else:
        condition = result = ""
    if not condition or not result or PLACEHOLDER_RE.fullmatch(condition) or PLACEHOLDER_RE.fullmatch(result):
        errors.append(f"{identifier} 缺少完整 WHEN ... {result_marker} ... EARS 行为（条件和结果均须填写）")


def validate_title(block: str, identifier: str, errors: list[str]) -> None:
    title = block.splitlines()[0].split("·")[-1].strip()
    if PLACEHOLDER_RE.fullmatch(title):
        errors.append(f"{identifier} 标题仍含模板占位内容")


def validate_feature(text: str, items: dict[str, str], scope: set[str], errors: list[str]) -> None:
    for identifier, block in items.items():
        if identifier.startswith(("US-", "REQ-", "NFR-")):
            status = require_field(block, "Status", identifier, errors)
            if status not in {"active", "retired"}:
                errors.append(f"{identifier} Status 只允许 active/retired")
        elif field(block, "Status") not in {None, "active", "retired"}:
            errors.append(f"{identifier} Status 只允许 active/retired")
        if field(block, "Status") != "retired":
            validate_title(block, identifier, errors)

    active_items = {key: block for key, block in items.items() if field(block, "Status") != "retired"}
    stories = {key for key in active_items if key.startswith("US-")}
    reqs = {key for key in active_items if key.startswith("REQ-")}
    all_reqs = {key for key in items if key.startswith("REQ-")}
    acs = {key for key in active_items if key.startswith("AC-")}
    if not stories:
        errors.append("缺少 US 用户故事定义")
    if not reqs:
        errors.append("缺少 REQ 定义")
    if not acs:
        errors.append("缺少 AC 定义")

    for story in sorted(stories):
        require_field(items[story], "Role", story, errors)
        for name in ("Goal", "Value"):
            if field(items[story], name) is not None:
                require_field(items[story], name, story, errors)

    current_reqs: set[str] = set()
    declared_stages: set[str] = set()
    for req in sorted(reqs):
        validate_revision(items[req], req, errors)
        stage = require_field(items[req], "Stage", req, errors)
        stage_id = normalize_stage(stage)
        if stage_id is None:
            errors.append(f"{req} Stage 非法: {stage}")
        else:
            declared_stages.add(stage_id)
            if stage_id in scope:
                current_reqs.add(req)
        story = require_field(items[req], "Story", req, errors)
        if not re.fullmatch(r"US-F\d{2,3}-\d{2,3}", story):
            errors.append(f"{req} 缺少合法 Story")
        elif story not in stories:
            errors.append(f"{req} 引用未定义或 retired 用户故事 {story}")

    for stage_id in sorted(scope - declared_stages):
        errors.append(f"Metadata scope 的 {stage_id} 没有 active REQ")

    referenced_reqs: set[str] = set()
    for ac in sorted(acs):
        block = items[ac]
        parent = require_field(block, "Parent", ac, errors)
        if not re.fullmatch(r"REQ-F\d{2,3}-\d{2,3}", parent):
            errors.append(f"{ac} 缺少合法 Parent")
        else:
            referenced_reqs.add(parent)
            if parent not in reqs:
                errors.append(f"{ac} 引用未定义或 retired 需求 {parent}")
        if require_field(block, "Priority", ac, errors) not in {"P0", "P1", "P2"}:
            errors.append(f"{ac} Priority 只允许 P0/P1/P2")
        if field(block, "Revision") is not None:
            validate_revision(block, ac, errors)
        validate_ears(block, ac, "THE SYSTEM SHALL", errors)

    for req in sorted(reqs - referenced_reqs):
        errors.append(f"{req} 没有任何 AC 覆盖")
    for identifier, block in active_items.items():
        if identifier.startswith("NFR-"):
            validate_revision(block, identifier, errors)
            require_field(block, "Measure", identifier, errors)
            applies_to = field(block, "Applies-to")
            if applies_to is not None:
                related = set(REQ_ID_RE.findall(applies_to))
                if not related or related - reqs:
                    errors.append(f"{identifier} Applies-to 必须引用真实 active REQ；全局约束可省略此字段")
    configuration_rows = capability_table_rows(
        text, EXTERNAL_CONFIGURATION_SECTION,
        ["Capability", "Credential owner", "Configuration actor", "Surface", "Scope", "Lifecycle", "Stage", "Requirement IDs"],
        errors,
    )
    prerequisite_rows = capability_table_rows(
        text, CAPABILITY_PREREQUISITES_SECTION,
        ["Prerequisite", "Status", "Owner", "Evidence or deadline", "Fallback", "Stage", "Requirement IDs"],
        errors,
    )
    validate_external_configuration(configuration_rows, all_reqs, current_reqs, scope, errors)
    validate_capability_prerequisites(prerequisite_rows, configuration_rows, all_reqs, current_reqs, scope, errors)


def validate_bugfix(items: dict[str, str], errors: list[str]) -> None:
    items = {key: block for key, block in items.items() if field(block, "Status") != "retired"}
    for prefix in ("BUG-", "REPRO-", "CUR-", "EXP-", "UNCH-", "CON-"):
        if not any(key.startswith(prefix) for key in items):
            errors.append(f"缺少 {prefix[:-1]} 定义")
    for key, block in items.items():
        validate_title(block, key, errors)
        if field(block, "Revision") is not None:
            validate_revision(block, key, errors)
        if field(block, "Status") not in {None, "active"}:
            errors.append(f"{key} Status 只允许 active/retired")
        required = ("Severity", "Scope") if key.startswith("BUG-") else (
            ("Environment", "Preconditions", "Steps", "Evidence") if key.startswith("REPRO-") else (
                ("Must-not-change", "Reason") if key.startswith("CON-") else ()
            )
        )
        for name in required:
            require_field(block, name, key, errors)
        marker = "THE SYSTEM SHALL CONTINUE TO" if key.startswith("UNCH-") else (
            "THE SYSTEM SHALL" if key.startswith("EXP-") else ("THE SYSTEM" if key.startswith("CUR-") else None)
        )
        if marker:
            validate_ears(block, key, marker, errors)


def validate_analysis(text: str, revision: str, items: dict[str, str], errors: list[str]) -> None:
    scope = section(text, "Scope")
    if scope is None:
        errors.append("正确性分析必须有且只有一个 Scope 章节")
        scope = ""
    for name in ("contract", "revision", "analyzed_at"):
        require_field(scope, name, "正确性分析 Scope", errors)
    if field(scope, "revision") != revision:
        errors.append("正确性分析 revision 与当前需求契约不一致")

    findings = section(text, "Findings")
    if findings is None:
        errors.append("正确性分析必须有且只有一个 Findings 章节")
        findings = ""
    unresolved = {"P0": 0, "P1": 0}
    closed_statuses = {"resolved", "closed", "dismissed", "rejected", "已解决", "已关闭", "已驳回"}
    seen: set[str] = set()
    has_header = False
    for line in findings.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = table_cells(line)
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if cells == ["ID", "Severity", "Involved IDs", "Category", "Failure Mode", "Resolution", "Status"]:
            has_header = True
            continue
        if len(cells) != 7:
            errors.append("正确性分析 Findings 行必须有 7 列")
            continue
        identifier, severity, involved, category, failure, resolution, status = cells
        if not re.fullmatch(r"RA-\d+", identifier) or identifier in seen:
            errors.append(f"正确性分析发现 ID 非法或重复: {identifier}")
        seen.add(identifier)
        if severity not in {"P0", "P1", "P2"}:
            errors.append(f"{identifier} Severity 只允许 P0/P1/P2")
        for label, value in (("Involved IDs", involved), ("Category", category), ("Failure Mode", failure), ("Status", status)):
            if not value or PLACEHOLDER_RE.fullmatch(value):
                errors.append(f"{identifier} 缺少有效 {label}")
        involved_ids = set(re.findall(r"(?:US|REQ|AC)-F\d{2,3}-\d{2,3}|NFR-\d{3}", involved))
        if not involved_ids or involved_ids - items.keys():
            errors.append(f"{identifier} Involved IDs 必须指向当前契约中真实存在的 ID")
        if status.lower() in closed_statuses:
            if not resolution or PLACEHOLDER_RE.fullmatch(resolution):
                errors.append(f"{identifier} 已关闭但缺少具体 Resolution")
        elif severity in unresolved:
            unresolved[severity] += 1
        if resolution != "-" and PLACEHOLDER_RE.fullmatch(resolution):
            errors.append(f"{identifier} Resolution 仍含模板占位内容")
    if not has_header:
        errors.append("正确性分析 Findings 缺少固定的 7 列表头；无发现时保留空表")

    summary = section(text, "Summary")
    if summary is None:
        errors.append("正确性分析必须有且只有一个当前 Summary 章节")
        summary = ""
    for severity, actual in unresolved.items():
        matches = re.findall(rf"^{severity} unresolved:[^\S\n]*(\d+)[^\S\n]*$", summary, re.MULTILINE)
        if len(matches) != 1:
            errors.append(f"正确性分析 Summary 必须唯一声明 {severity} unresolved 计数")
            continue
        count = int(matches[0])
        if count != actual:
            errors.append(f"正确性分析 {severity} 汇总与 Findings 不一致: {count} != {actual}")
        if count or actual:
            errors.append(f"正确性分析未清零: {severity} unresolved: {max(count, actual)}")


def capability_warnings(text: str) -> list[str]:
    """Free-text signals are review hints, never proof of a current dependency."""
    prose = without_section(without_section(text, EXTERNAL_CONFIGURATION_SECTION), CAPABILITY_PREREQUISITES_SECTION)
    signal = CAPABILITY_PREREQUISITE_SIGNAL_RE.search(prose)
    if not signal:
        return []
    return [f"正文出现可能的外部能力词“{signal.group(0)}”；按已确认范围核对依赖表，关键词本身不阻断交付，也不证明需要新增配置或提问。"]


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("用法: py check_requirements_contract.py <requirements.md|bugfix.md> [requirements-analysis.md]")
        return 2

    contract = Path(sys.argv[1])
    if not contract.is_file():
        print(f"❌ 文件不存在: {contract}")
        return 2

    text = contract.read_text(encoding="utf-8")
    errors: list[str] = []
    title = text.splitlines()[0].removeprefix("# ") if text.splitlines() else ""
    title = re.sub(r"\s+(?:Requirements|Bugfix) Contract$", "", title)
    if PLACEHOLDER_RE.fullmatch(title):
        errors.append("契约标题仍含模板占位内容")
    try:
        items = blocks(text)
    except ValueError as exc:
        errors.append(str(exc))
        items = {}

    work_type, revision, scope = validate_metadata(text, errors)
    if work_type == "bugfix":
        validate_bugfix(items, errors)
    else:
        validate_feature(text, items, scope, errors)
        if len(sys.argv) != 3:
            errors.append("Feature 契约必须同时提供 requirements-analysis.md")
        else:
            analysis = Path(sys.argv[2])
            if not analysis.is_file():
                errors.append(f"分析文件不存在: {analysis}")
            else:
                validate_analysis(analysis.read_text(encoding="utf-8"), revision, items, errors)

    for warning in capability_warnings(text) if work_type == "feature" else []:
        print(f"⚠️ {warning}")

    if errors:
        print(f"❌ 需求契约校验失败（{len(errors)}）")
        for error in errors:
            print(f"  - {error}")
        return 2

    print(f"✅ 需求契约结构校验通过：{work_type}，稳定对象 {len(items)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
