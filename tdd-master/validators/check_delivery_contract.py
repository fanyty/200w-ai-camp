#!/usr/bin/env python3
"""Validate the compact TDD acceptance contract and its upstream coverage."""

from __future__ import annotations

import hashlib
import re
import struct
import sys
from pathlib import Path


SOURCE_ID_PATTERN = r"(?:REQ-F\d{2,3}-\d{2,3}|AC-F\d{2,3}-\d{2,3}|NFR-\d{3}|REPRO-\d{3}|CUR-\d{3}|EXP-\d{3}|UNCH-\d{3}|CON-\d{3})"
SOURCE_ID_RE = re.compile(SOURCE_ID_PATTERN)
SOURCE_HEADING_RE = re.compile(r"^###\s+(" + SOURCE_ID_PATTERN + r")\b", re.MULTILINE)
DESIGN_ID_PATTERN = r"(?:PAGE-F\d{2,3}-\d{2,3}|CMP-F\d{2,3}-\d{2,3}|API-F\d{2,3}-\d{2,3}|DATA-F\d{2,3}-\d{2,3}|SEQ-F\d{2,3}-\d{2,3}|DEC-\d{3}|FIX-BUG-\d{3})"
DESIGN_ID_RE = re.compile(DESIGN_ID_PATTERN)
PAGE_ID_RE = re.compile(r"PAGE-F\d{2,3}-\d{2,3}")
PAGE_ARTIFACT_RE = re.compile(
    r"(?:output/)?pages/[^\s;|`]+?\.(?:md|html)", re.IGNORECASE
)
TEST_ID_RE = re.compile(
    r"(?:SMOKE|FLOW|RULE|DESIGN)-\d{2,3}|BUG-(?:REPRO|FIX|REG|RULE)-\d{2,3}"
)
PLACEHOLDER_RE = re.compile(r"\{\{|\b(?:TBD|TODO)\b|待定|占位", re.IGNORECASE)
PLACEHOLDER_VALUE_RE = re.compile(r"(?:missing|缺失)", re.IGNORECASE)
FIDELITY_ANCHORS = ("结构", "组件", "内容", "交互", "视觉", "原生适配")
VISUAL_EVIDENCE_KEYS = ("actual", "reviewer", "review", "blocking")
REQUIRED_SECTIONS = (
    "## 0. 契约元信息",
    "## 1. 完成定义",
    "## 2. 冒烟门禁",
    "## 3. 功能与流程验收",
    "## 4. 设计落地验收",
    "## 5. 风险触发验收",
    "## 6. 本期不阻塞项",
)


def field(block: str, name: str) -> str | None:
    match = re.search(rf"^- {re.escape(name)}:[^\S\n]*(.*?)[^\S\n]*$", block, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().strip("`") if match else None


def source_blocks(text: str) -> dict[str, str]:
    matches = list(SOURCE_HEADING_RE.finditer(text))
    blocks: dict[str, str] = {}
    defined: set[str] = set()
    for match in matches:
        following = re.search(r"^#{1,3}\s+", text[match.end():], re.MULTILINE)
        end = match.end() + following.start() if following else len(text)
        block = text[match.start():end]
        source_id = match.group(1)
        if source_id in defined:
            raise ValueError(f"上游重复定义 Source ID: {source_id}")
        defined.add(source_id)
        if (field(block, "Status") or "").lower() != "retired":
            blocks[source_id] = block
    return blocks


def source_metadata(text: str) -> str:
    metadata = re.search(r"^## Metadata[^\S\n]*\n(.*?)(?=^#{2,3} |\Z)", text, re.MULTILINE | re.DOTALL)
    return metadata.group(1) if metadata else ""


def source_revision(text: str) -> str | None:
    return field(source_metadata(text), "revision")


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
        value,
        re.IGNORECASE,
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


def scoped_requirements(blocks: dict[str, str], stages: set[str]) -> set[str]:
    return {
        source_id
        for source_id, block in blocks.items()
        if source_id.startswith("REQ-") and normalize_stage(field(block, "Stage") or "") in stages
    }


def scoped_sources(blocks: dict[str, str], stages: set[str]) -> set[str]:
    requirements = scoped_requirements(blocks, stages)
    selected = set(requirements)
    for source_id, block in blocks.items():
        if source_id.startswith("AC-") and field(block, "Parent") in requirements:
            selected.add(source_id)
        elif source_id.startswith("NFR-"):
            applies_to = set(SOURCE_ID_RE.findall(field(block, "Applies-to") or ""))
            if not applies_to or applies_to & requirements:
                selected.add(source_id)
    return selected


def required_sources(text: str, work_type: str, stages: set[str]) -> set[str]:
    blocks = source_blocks(text)
    if work_type == "bugfix":
        return set(blocks)

    requirements = scoped_requirements(blocks, stages)
    required = set(requirements)

    for source_id, block in blocks.items():
        if source_id.startswith("AC-"):
            parent = field(block, "Parent")
            priority = (field(block, "Priority") or "").upper()
            if parent in requirements and priority in {"P0", "P1"}:
                required.add(source_id)
        elif source_id.startswith("NFR-"):
            applies_to = set(SOURCE_ID_RE.findall(field(block, "Applies-to") or ""))
            if not applies_to or applies_to & requirements:
                required.add(source_id)

    return required


def table_cells(line: str) -> list[str]:
    """Split Markdown cells without treating an escaped pipe as a delimiter."""
    cells: list[str] = []
    start = 0
    backslashes = 0
    stripped = line.strip()
    for index, character in enumerate(stripped):
        if character == "|" and backslashes % 2 == 0:
            cells.append(stripped[start:index].strip())
            start = index + 1
        backslashes = backslashes + 1 if character == "\\" else 0
    cells.append(stripped[start:].strip())
    if stripped.startswith("|"):
        cells.pop(0)
    if cells and not cells[-1] and stripped.endswith("|"):
        cells.pop()
    return cells


def identified_table_rows(
    text: str, id_pattern: re.Pattern[str], columns: int, label: str, errors: list[str],
    *, strict_ids: bool = False,
) -> list[list[str]]:
    rows: list[list[str]] = []
    in_id_table = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            in_id_table = False
            continue
        cells = table_cells(line)
        if cells and cells[0].strip("`").lower() in {"id", "tdd id"}:
            in_id_table = True
            continue
        if cells and all(re.fullmatch(r":?-+:?", cell.strip()) for cell in cells):
            continue
        if not cells or not id_pattern.fullmatch(cells[0].strip("`")):
            if strict_ids and cells and (
                in_id_table or re.match(r"(?:SMOKE|FLOW|RULE|DESIGN|BUG)(?:[-_\s]|$)", cells[0].strip("`"), re.IGNORECASE)
            ):
                errors.append(f"{label}第 {line_number} 行验收 ID 非法: {cells[0] or '(空)'}")
            continue
        row_id = cells[0].strip("`")
        if len(cells) != columns:
            errors.append(
                f"{label}第 {line_number} 行 {row_id} 列数错误：应为 {columns} 列，"
                f"实际 {len(cells)} 列；单元格内的竖线请写成 \\|"
            )
            continue
        cells[0] = row_id
        rows.append(cells)
    return rows


def validate_source_trace(
    source_text: str, trace_text: str, contract: str, work_type: str, stages: set[str], output: Path
) -> list[str]:
    """Keep the final acceptance contract on the current, complete design source."""
    errors: list[str] = []
    blocks = source_blocks(source_text)
    revision = source_revision(source_text)
    if invalid_detail(revision or ""):
        errors.append("上游 Metadata 缺少有效 revision")
    if field(contract, "source_revision") != revision or not revision:
        errors.append("TDD source_revision 与上游 Metadata revision 不一致")
    if not blocks:
        errors.append("上游没有 active Source，无法核对设计与验收范围")

    if work_type == "feature":
        for source_id, block in blocks.items():
            if source_id.startswith("REQ-") and not field(block, "Stage"):
                errors.append(f"{source_id} 缺少 Stage，无法判断当前范围")
            elif source_id.startswith("REQ-") and normalize_stage(field(block, "Stage") or "") is None:
                errors.append(f"{source_id} 的 Stage 无法识别: {field(block, 'Stage')}")
            if source_id.startswith("AC-"):
                parent = field(block, "Parent") or ""
                if not parent.startswith("REQ-") or parent not in blocks:
                    errors.append(f"{source_id} 的 Parent 缺失或不是 active REQ")

    selected = scoped_sources(blocks, stages) if work_type == "feature" else set(blocks)
    traced: set[str] = set()
    for cells in identified_table_rows(trace_text, SOURCE_ID_RE, 7, "设计追溯矩阵", errors):
        source_id = cells[0]
        if source_id not in blocks:
            errors.append(f"设计矩阵包含未定义或 retired Source: {source_id}")
            continue
        traced.add(source_id)
        block = blocks[source_id]
        expected_revision = field(block, "Revision")
        if not expected_revision and source_id.startswith("AC-"):
            expected_revision = field(blocks.get(field(block, "Parent") or "", ""), "Revision")
        expected_revision = expected_revision or revision
        if cells[1].strip("`") != expected_revision:
            errors.append(
                f"设计矩阵 {source_id} Source Revision 不一致: "
                f"{cells[1]} != {expected_revision}"
            )
        status = cells[6].strip("`").lower()
        allowed = {"covered", "preserved"} if source_id in selected else {"covered", "preserved", "planned"}
        if status not in allowed:
            errors.append(f"设计矩阵 {source_id} 状态不可交付: {status}（应为 {'/'.join(sorted(allowed))}）")
        if not DESIGN_ID_RE.search(cells[2]):
            errors.append(f"设计矩阵 {source_id} 缺少合法 Design ID")
        for index, label in ((3, "Artifact"), (4, "Error/Invariant"), (5, "Verification Surface")):
            if invalid_detail(cells[index]):
                errors.append(f"设计矩阵 {source_id} 的 {label} 未完成")
        planning_artifact = False
        # Link labels may themselves name files; only their destinations are artifacts.
        artifact_text = re.sub(r"\[[^\]\n]*\](?=\()", "", cells[3])
        for raw_path in re.findall(r"[^\s;；|`<>]+?\.(?:md|html|css)\b", artifact_text, re.IGNORECASE):
            raw_path = raw_path.rsplit("](", 1)[-1].lstrip("(").removeprefix("./")
            if "://" in raw_path:
                continue
            relative = Path(raw_path.replace("\\", "/").removeprefix("output/"))
            if relative.parts and relative.parts[0] == "pages":
                if status == "planned":
                    errors.append(f"设计矩阵 {source_id} 为 planned，不得引用页面详细产物: {raw_path}")
                continue  # Page identity/path recovery is checked below.
            if relative.is_absolute() or ".." in relative.parts or not (output / relative).is_file():
                errors.append(f"设计矩阵 {source_id} 的 Artifact 文件不存在或路径无效: {raw_path}")
            elif relative.name in {"页面清单.md", "设计决策蓝图.md", "技术方案.md"}:
                planning_artifact = True
        if status == "planned" and not planning_artifact:
            errors.append(f"设计矩阵 {source_id} 的 planned Artifact 必须指向真实的页面清单/蓝图/技术方案骨架")

    for source_id in sorted(set(blocks) - traced):
        errors.append(f"设计矩阵缺少 active Source 行: {source_id}")
    return errors


def acceptance_rows(text: str, errors: list[str]) -> list[list[str]]:
    return identified_table_rows(text, TEST_ID_RE, 6, "验收契约", errors, strict_ids=True)


def result_rows(text: str, errors: list[str]) -> list[list[str]]:
    return identified_table_rows(text, TEST_ID_RE, 4, "验收结果", errors, strict_ids=True)


def structured_fields(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in re.split(r"[;；]", value.strip().strip("`")):
        key, separator, detail = part.partition("=")
        if separator:
            fields[key.strip()] = detail.strip().strip("`")
    return fields


def scoped_page_specs(page_list_text: str, stages: set[str] | None, errors: list[str]) -> dict[str, tuple[set[str], str, str]]:
    pages: dict[str, tuple[set[str], str, str]] = {}
    defined: set[str] = set()
    for cells in identified_table_rows(page_list_text, PAGE_ID_RE, 6, "页面清单", errors):
        if cells[0] in defined:
            errors.append(f"页面清单重复定义 PAGE ID: {cells[0]}")
            continue
        defined.add(cells[0])
        page_stages = parse_scope(cells[2].strip("`"), f"页面清单 {cells[0]}", errors)
        if stages is None or page_stages & stages:
            pages[cells[0]] = (page_stages, cells[3], cells[4])
    return pages


def artifact_paths(value: str) -> list[Path]:
    paths: list[Path] = []
    for raw_path in PAGE_ARTIFACT_RE.findall(value):
        normalized = raw_path.removeprefix("output/")
        path = Path(normalized)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "pages":
            continue
        paths.append(path)
    return paths


def page_identity_score(path: Path, page_id: str, page_name: str) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    if path.suffix.lower() == ".html":
        declared_ids: set[str] = set()
        for meta_tag in re.findall(r"<meta\b[^>]*>", text, re.IGNORECASE):
            name = re.search(r'name=["\']([^"\']+)', meta_tag, re.IGNORECASE)
            content = re.search(r'content=["\']([^"\']+)', meta_tag, re.IGNORECASE)
            if (
                name
                and content
                and name.group(1).strip().lower() == "page-id"
            ):
                declared_ids.add(content.group(1).strip())
        if declared_ids:
            return 100 if declared_ids == {page_id} else 0
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        if title and page_name and page_name in re.sub(r"<[^>]+>", "", title.group(1)):
            return 60
    else:
        declared_ids = {
            value.strip().strip("`")
            for value in re.findall(
                r"^\|\s*页面\s*ID\s*\|\s*([^|]+)\|",
                text,
                re.MULTILINE | re.IGNORECASE,
            )
        }
        if declared_ids:
            return 100 if declared_ids == {page_id} else 0
        heading = re.search(r"^#\s+.*$", text, re.MULTILINE)
        if heading and page_name and page_name in heading.group(0):
            return 60

    if page_name and page_name in path.stem:
        return 40
    if page_name and page_name in text:
        return 10
    return 0


def declared_page_name(output: Path, explicit_paths: list[Path]) -> str:
    """A legacy Bugfix pair may have a page title but no page-list entry."""
    markdown_paths = {output / path for path in explicit_paths if path.suffix.lower() == ".md"}
    if len(markdown_paths) != 1:
        return ""
    path = next(iter(markdown_paths))
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    heading = re.search(r"^#\s+(?:页面名称\s*[:：]\s*)?(.+?)\s*$", text, re.MULTILINE)
    return heading.group(1) if heading else ""


def select_page_artifact(
    output: Path,
    explicit_paths: list[Path],
    suffix: str,
    page_id: str,
    page_name: str,
) -> tuple[Path | None, str | None]:
    pages_root = output / "pages"
    candidates = {
        output / relative
        for relative in explicit_paths
        if relative.suffix.lower() == suffix and (output / relative).is_file()
    }
    if pages_root.is_dir():
        candidates.update(path for path in pages_root.rglob(f"*{suffix}") if path.is_file())

    scored = [(page_identity_score(path, page_id, page_name), path) for path in candidates]
    scored = [(score, path) for score, path in scored if score > 0]
    if not scored:
        return None, f"{page_id} 找不到内容可确认的 {suffix} 产物"

    best_score = max(score for score, _ in scored)
    best = sorted(path for score, path in scored if score == best_score)
    if len(best) != 1:
        choices = ", ".join(str(path.relative_to(output)) for path in best)
        return None, f"{page_id} 的 {suffix} 内容匹配不唯一: {choices}"
    return best[0], None


def invalid_detail(value: str, allow_dash: bool = False) -> bool:
    stripped = value.strip().strip("`")
    if not stripped or PLACEHOLDER_RE.search(stripped) or PLACEHOLDER_VALUE_RE.fullmatch(stripped):
        return True
    return stripped == "-" and not allow_dash


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def visual_artifact_path(output: Path, raw_path: str) -> tuple[Path | None, str | None]:
    normalized = raw_path.strip().strip("`\"'").removeprefix("output/")
    relative = Path(normalized)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) < 3
        or relative.parts[:2] != ("tests", "visual")
        or relative.suffix.lower() != ".png"
    ):
        return None, f"视觉证据必须是 output/tests/visual/ 下的相对 PNG 路径: {raw_path}"
    return output / relative, None


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if (
        len(data) < 45
        or data[:8] != b"\x89PNG\r\n\x1a\n"
        or data[12:16] != b"IHDR"
        or not data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")
    ):
        return None
    width, height = struct.unpack(">II", data[16:24])
    return (width, height) if width > 0 and height > 0 else None


def validate_design_result(
    output: Path,
    test_id: str,
    require_pair: bool,
    action: str,
    evidence: str,
) -> list[str]:
    errors: list[str] = []
    view_targets = "actual|成品|截图" + ("|baseline|原型" if require_pair else "")
    not_viewed = re.search(
        rf"(?:未|没有|尚未|并未|无法|不能)(?:实际)?(?:查看|看图)(?:\s*(?:{view_targets})|(?=[，；。]|$))",
        action,
        re.IGNORECASE,
    )
    only_code_or_automation = re.fullmatch(
        r"(?:只做代码审查|仅运行\s*UI\s*自动化)[。.]?",
        action.strip(" `"),
        re.IGNORECASE,
    )
    if not_viewed or only_code_or_automation:
        target = "baseline+actual" if require_pair else "actual 成品截图"
        errors.append(f"{test_id} 的实际验证动作没有证明验收官查看了 {target}")
    fields = structured_fields(evidence)
    required_keys = VISUAL_EVIDENCE_KEYS + (("baseline",) if require_pair else ())
    missing = [key for key in required_keys if invalid_detail(fields.get(key, ""))]
    if missing:
        errors.append(f"{test_id} 缺少视觉证据字段: {', '.join(missing)}")
        return errors

    if fields["reviewer"].lower() != "independent-visual":
        errors.append(f"{test_id} 必须由 independent-visual 独立看图验收，不能自我签字")
    if fields["review"].lower() != "pass":
        errors.append(f"{test_id} 的独立视觉复核未通过: {fields['review']}")
    if fields["blocking"] != "0":
        errors.append(f"{test_id} 仍有阻塞视觉差异: {fields['blocking']}")

    resolved: dict[str, tuple[Path, tuple[int, int]]] = {}
    for key in ("actual", "baseline"):
        if key not in fields:
            continue
        path, path_error = visual_artifact_path(output, fields[key])
        if path_error:
            errors.append(f"{test_id}: {path_error}")
            continue
        assert path is not None
        if not path.is_file():
            errors.append(f"{test_id} 的 {key} 截图不存在: {path}")
            continue
        dimensions = png_dimensions(path)
        if dimensions is None:
            errors.append(f"{test_id} 的 {key} 不是有效 PNG: {path}")
            continue
        resolved[key] = (path, dimensions)

    if "baseline" in resolved and "actual" in resolved:
        baseline_path, baseline_size = resolved["baseline"]
        actual_path, actual_size = resolved["actual"]
        if baseline_path == actual_path:
            errors.append(f"{test_id} 的 baseline 与 actual 不能指向同一文件")
        if require_pair and baseline_size != actual_size:
            errors.append(
                f"{test_id} 的原型/成品截图尺寸不同: {baseline_size} != {actual_size}"
            )
    return errors


def validate_result_ledger(
    output: Path,
    result_path: Path,
    contract_path: Path,
    contract_rows: list[list[str]],
) -> list[str]:
    if not result_path.is_file():
        return []

    text = result_path.read_text(encoding="utf-8")
    errors: list[str] = []
    if field(text, "contract_sha256") != sha256(contract_path):
        errors.append("TDD验收结果的 contract_sha256 与当前契约不一致，请核对变更影响、使受影响结果失效并更新哈希；未核对前不得宣称完成")
    if invalid_detail(field(text, "run_started_at") or ""):
        errors.append("TDD验收结果缺少有效 run_started_at")

    rows = result_rows(text, errors)
    if not rows:
        errors.append("TDD验收结果没有合法结果行")
        return errors

    contract_ids = [row[0] for row in contract_rows]
    contract_by_id = {row[0]: row for row in contract_rows}
    ledger_ids = [row[0] for row in rows]
    duplicates = sorted({test_id for test_id in ledger_ids if ledger_ids.count(test_id) > 1})
    if duplicates:
        errors.append("TDD验收结果 ID 重复: " + ", ".join(duplicates))

    missing = sorted(set(contract_ids) - set(ledger_ids))
    extra = sorted(set(ledger_ids) - set(contract_ids))
    if missing:
        errors.append("TDD验收结果漏项: " + ", ".join(missing))
    if extra:
        errors.append("TDD验收结果包含契约外 ID: " + ", ".join(extra))

    for test_id, status_cell, action, evidence in rows:
        status = status_cell.strip().strip("`").lower()
        if status not in {"pending", "pass", "fail"}:
            errors.append(f"{test_id} 的状态非法: {status_cell}")
        elif status != "pass":
            errors.append(f"{test_id} 尚未通过: {status}")
        if invalid_detail(action):
            errors.append(f"{test_id} 缺少本轮实际验证动作")
        if invalid_detail(evidence):
            errors.append(f"{test_id} 缺少本轮验证证据")
        if status == "pass" and not test_id.startswith("DESIGN-"):
            errors.extend(validate_execution_evidence(test_id, action, evidence))
        if test_id.startswith("DESIGN-") and test_id in contract_by_id:
            errors.extend(
                validate_design_result(
                    output,
                    test_id,
                    any(
                        marker in cell
                        for cell in contract_by_id[test_id][3:]
                        for marker in ("截图对", "严格对照")
                    ),
                    action,
                    evidence,
                )
            )

    return errors


def execution_result_text(evidence: str) -> str:
    """Exclude explicit command fields, keeping quoted semicolons inside commands."""
    text = evidence.strip()
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    # Unbalanced quotes cannot establish a field boundary, so keep that text.
    return re.sub(
        r'''(?:^|(?<=[;；]))\s*command\s*=\s*(?:[^;；'"`\\]|\\.|'[^']*'|"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`)*(?=[;；]|$)''',
        "", text, flags=re.IGNORECASE,
    )


def validate_execution_evidence(test_id: str, action: str, evidence: str) -> list[str]:
    """Reject explicit contradictions; this does not establish evidence authenticity."""
    errors: list[str] = []
    if re.search(r"^(?:只做代码审查|仅做代码审查)(?:[，,；;。]|$)", action.strip(" `")) or re.search(
        r"(?:^|[，,；;。])\s*(?:尚未|没有|未)(?:实际|真实)?执行(?:测试|验收|验证|命令|E2E)?\s*(?:[，,；;。]|$)", action
    ) or re.match(r"(?:应该通过|预计通过|功能已实现|代码已完成)(?:[，,；;。]|$)", evidence.strip(" `")):
        errors.append(f"{test_id} 标为 pass，但动作或证据明确表示未执行或仅推测通过")

    result_text = execution_result_text(evidence)
    exit_codes = [int(value) for value in re.findall(
        r"(?:\bexit_code\b|\bexit\b|退出码)\s*(?:[=:：]\s*)?(-?\d+)\b", result_text, re.IGNORECASE
    )]
    failed_counts = [int(value) for match in re.findall(
        r"\bfailed\s*[=:]\s*(\d+)\b|\b(\d+)\s+failed\b", result_text, re.IGNORECASE
    ) for value in match if value]
    # Evidence describes this assertion's current verification results. A
    # later success must not conceal another command/test failure in the row.
    fields = {key.lower(): value.upper() for key, value in structured_fields(result_text).items()}
    expected_exit_matches = False
    if "expected_exit_code" in fields or "actual_exit_code" in fields:
        expected_exit = fields.get("expected_exit_code", "")
        actual_exit = fields.get("actual_exit_code", "")
        if not re.fullmatch(r"-?\d+", expected_exit) or not re.fullmatch(r"-?\d+", actual_exit):
            errors.append(f"{test_id} 的 expected_exit_code / actual_exit_code 必须成对填写整数")
        elif int(expected_exit) != int(actual_exit):
            errors.append(f"{test_id} 的实际退出码与预期不一致: {actual_exit} != {expected_exit}")
        else:
            expected_exit_matches = all(code == int(actual_exit) for code in exit_codes)
    expected_red = (
        test_id.startswith("BUG-REPRO-")
        and fields.get("expected") == "RED"
        and fields.get("observed") == "RED"
    )
    failed_exit = any(code != 0 for code in exit_codes) and not expected_exit_matches
    failed_tests = any(count > 0 for count in failed_counts)
    if (failed_exit or failed_tests) and not expected_red:
        errors.append(f"{test_id} 标为 pass，但证据包含失败退出码或失败测试；预期 RED 仅用于 BUG-REPRO 且须写 expected=RED; observed=RED")
    return errors


def main() -> int:
    args = sys.argv[1:]
    validate_results = bool(args and args[0] == "--result")
    if validate_results:
        args = args[1:]
    if len(args) != 1:
        print("用法: py check_delivery_contract.py [--result] <项目/output>")
        return 2

    output = Path(args[0])
    contract_path = output / "tests" / "TDD验收契约.md"
    if not contract_path.is_file():
        print(f"❌ 文件不存在: {contract_path}")
        return 2

    contract = contract_path.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in contract:
            errors.append(f"契约缺少章节: {section}")

    source_contract = field(contract, "source_contract")
    work_type = field(contract, "work_type")
    if source_contract not in {"requirements.md", "bugfix.md"}:
        errors.append("source_contract 必须为 requirements.md|bugfix.md")
    if work_type not in {"feature", "bugfix"}:
        errors.append("work_type 必须为 feature|bugfix")
    if (source_contract == "requirements.md") != (work_type == "feature"):
        errors.append("work_type 与 source_contract 不一致")

    source_path = output / source_contract if source_contract else output / "requirements.md"
    design_trace_path = output / "设计追溯矩阵.md"
    for path in (source_path, design_trace_path):
        if not path.is_file():
            errors.append(f"文件不存在: {path}")
    if errors:
        print(f"❌ 精简 TDD 契约校验失败（{len(errors)}）")
        for error in errors:
            print(f"  - {error}")
        return 2

    source_text = source_path.read_text(encoding="utf-8")
    try:
        blocks = source_blocks(source_text)
    except ValueError as exc:
        print("❌ 精简 TDD 契约校验失败（1）")
        print(f"  - {exc}")
        return 2
    all_sources = set(blocks)
    stages: set[str] = set()
    if work_type == "feature":
        stages = parse_scope(field(contract, "scope"), "TDD scope", errors)
        source_scope = field(source_metadata(source_text), "scope")
        source_stages = parse_scope("MVP" if source_scope is None else source_scope, "上游 scope", errors)
        if stages != source_stages:
            errors.append("TDD scope 与上游 Metadata scope 不一致，须沿用用户已确认范围")
        for stage in sorted(stages):
            if not scoped_requirements(blocks, {stage}):
                errors.append(f"scope {stage} 没有匹配的 active REQ，不得按空范围通过")
    required = required_sources(source_text, work_type or "feature", stages)
    design_trace = design_trace_path.read_text(encoding="utf-8")
    errors.extend(validate_source_trace(source_text, design_trace, contract, work_type or "feature", stages, output))
    known_design_ids = set(DESIGN_ID_RE.findall(design_trace))

    rows = acceptance_rows(contract, errors)
    if not rows:
        errors.append("契约没有合法验收行")

    page_specs: dict[str, tuple[set[str], str, str]] = {}
    all_page_specs: dict[str, tuple[set[str], str, str]] = {}
    if work_type == "feature":
        selected_sources = scoped_sources(blocks, stages)
        # Trace structure has already been validated; include current source mappings
        # even if the acceptance author omitted all DESIGN rows.
        referenced_pages = {
            page_id
            for row in identified_table_rows(design_trace, SOURCE_ID_RE, 7, "设计追溯矩阵", [])
            if row[0] in selected_sources
            for page_id in PAGE_ID_RE.findall(row[2])
        }
        referenced_pages.update(page_id for row in rows for page_id in PAGE_ID_RE.findall(row[2]))
        page_list_path = output / "页面清单.md"
        if not page_list_path.is_file():
            if referenced_pages:
                errors.append(f"本次来源或验收引用了页面，文件不存在: {page_list_path}")
        else:
            all_page_specs = scoped_page_specs(page_list_path.read_text(encoding="utf-8"), None, errors)
            page_specs = {
                page_id: spec for page_id, spec in all_page_specs.items()
                if spec[0] & stages
            }
            known_design_ids.update(all_page_specs)
            for page_id in sorted(referenced_pages - set(all_page_specs)):
                errors.append(f"页面清单遗漏本次来源或验收引用的页面: {page_id}")

    ids = [row[0] for row in rows]
    duplicates = sorted({test_id for test_id in ids if ids.count(test_id) > 1})
    if duplicates:
        errors.append("验收 ID 重复: " + ", ".join(duplicates))

    covered_sources: set[str] = set()
    covered_pages: set[str] = set()
    resolved_pages: set[str] = set()
    artifact_page_owners: dict[Path, str] = {}
    for row in rows:
        test_id, source_cell, design_cell, scenario, expected, method = row
        row_sources = set(SOURCE_ID_RE.findall(source_cell))
        row_design_ids = set(DESIGN_ID_RE.findall(design_cell))
        covered_sources.update(row_sources)
        if test_id.startswith("DESIGN-"):
            row_pages = set(PAGE_ID_RE.findall(design_cell))
            covered_pages.update(row_pages)
            if len(row_pages) != 1:
                errors.append(f"{test_id} 必须且只能对应一个 PAGE ID")
            anchor_fields = structured_fields(expected)
            missing_anchors = [
                anchor
                for anchor in FIDELITY_ANCHORS
                if invalid_detail(anchor_fields.get(anchor, ""))
            ]
            if missing_anchors:
                errors.append(
                    f"{test_id} 的通过标准缺少具体视觉锚点: {', '.join(missing_anchors)}"
                )
            if "截图" not in method or "独立" not in method:
                errors.append(f"{test_id} 的验证方式必须包含真实成品截图和独立视觉复核")
            explicit_paths = artifact_paths(design_cell)
            for page_id in sorted(row_pages - resolved_pages):
                _, _, page_name = all_page_specs.get(
                    page_id, (set(), "", declared_page_name(output, explicit_paths))
                )
                md_path, md_error = select_page_artifact(
                    output, explicit_paths, ".md", page_id, page_name
                )
                html_path, html_error = select_page_artifact(
                    output, explicit_paths, ".html", page_id, page_name
                )
                if md_error:
                    errors.append(f"{test_id}: {md_error}")
                if html_error:
                    errors.append(f"{test_id}: {html_error}")
                if md_path is None or html_path is None:
                    continue

                for artifact_path in (md_path, html_path):
                    real_path = artifact_path.resolve()
                    owner = artifact_page_owners.get(real_path)
                    if owner is not None and owner != page_id:
                        errors.append(
                            f"{page_id} 与 {owner} 共用同一页面产物: "
                            f"{artifact_path.relative_to(output)}；每份 MD/HTML 只能归属一个 PAGE ID"
                        )
                    else:
                        artifact_page_owners[real_path] = page_id

                resolved_pages.add(page_id)
                md_relative = md_path.relative_to(output)
                html_relative = html_path.relative_to(output)
                if md_relative not in explicit_paths or html_relative not in explicit_paths:
                    warnings.append(
                        f"{test_id} 未准确记录 {page_id} 的实际 MD/HTML 路径；"
                        f"已按内容唯一匹配为 {md_relative} + {html_relative}"
                    )

                if work_type == "bugfix":
                    continue
                canonical_pair = (
                    md_relative.parent == Path("pages")
                    and html_relative.parent == Path("pages")
                    and md_relative.stem == html_relative.stem == page_id
                )
                if not canonical_pair:
                    warnings.append(
                        f"{page_id} 页面产物命名/目录不规范，但内容身份唯一，继续使用实际路径："
                        f"{md_relative} + {html_relative}"
                    )

        for source_id in row_sources - all_sources:
            errors.append(f"{test_id} 引用未知 Source ID: {source_id}")
        for design_id in row_design_ids - known_design_ids:
            errors.append(f"{test_id} 引用未出现在设计产物中的 Design ID: {design_id}")

        if not test_id.startswith("SMOKE-") and not row_sources and "design-derived" not in source_cell:
            errors.append(f"{test_id} 缺少 Source ID 或 design-derived 来源")
        if test_id.startswith("DESIGN-") and not PAGE_ID_RE.search(design_cell):
            errors.append(f"{test_id} 缺少 PAGE ID")
        for label, value in (("场景与操作", scenario), ("可观察通过标准", expected), ("验证方式", method)):
            if invalid_detail(value):
                errors.append(f"{test_id} 的{label}为空或仍是占位内容")
        if invalid_detail(design_cell, allow_dash=test_id.startswith("SMOKE-")):
            errors.append(f"{test_id} 的 Design IDs/产物为空或仍是占位内容")

    if not any(test_id.startswith("SMOKE-") for test_id in ids):
        errors.append("缺少 SMOKE 冒烟门禁")
    if work_type == "feature" and not any(test_id.startswith("FLOW-") for test_id in ids):
        errors.append("Feature 缺少 FLOW 核心用户旅程")
    if work_type == "bugfix":
        for prefix, label in (("BUG-REPRO-", "稳定复现"), ("BUG-FIX-", "修复结果"), ("BUG-REG-", "关键回归")):
            if not any(test_id.startswith(prefix) for test_id in ids):
                errors.append(f"Bugfix 缺少{label}验收")

    for source_id in sorted(required - covered_sources):
        errors.append(f"required Source 未被验收覆盖: {source_id}")
    for page_id in sorted(set(page_specs) - covered_pages):
        errors.append(f"当前 scope 页面未进入 DESIGN 验收: {page_id}")

    behavior_count = sum(
        test_id.startswith(("FLOW-", "RULE-", "BUG-")) for test_id in ids
    )
    if behavior_count > 25:
        warnings.append(f"行为/风险验收共 {behavior_count} 条（体量提示；必要覆盖不受条数限制，不增加复审轮次）")

    result_path = output / "tests" / "TDD验收结果.md"
    if validate_results:
        if not result_path.is_file():
            errors.append(f"文件不存在: {result_path}")
        else:
            errors.extend(validate_result_ledger(output, result_path, contract_path, rows))

    if errors:
        print(f"❌ 精简 TDD 契约校验失败（{len(errors)}）")
        for error in errors:
            print(f"  - {error}")
        for warning in warnings:
            print(f"  ⚠️ {warning}")
        return 2

    for warning in warnings:
        print(f"⚠️ {warning}")
    result_summary = " / execution ledger all pass" if validate_results else ""
    print(
        "✅ 精简 TDD 契约校验通过："
        f"{len(required)} required source / {len(page_specs)} scope pages / {len(rows)} acceptance rows"
        f"{result_summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
