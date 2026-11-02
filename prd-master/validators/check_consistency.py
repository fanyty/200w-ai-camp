#!/usr/bin/env python3
"""
check_consistency.py - PRD 跨章节一致性 PASS/FAIL 校验
(吸收自 senior-pm-prompt 的一致性检查块)

扫描 PRD 文件：
1. 每个稳定 User Story (US-Fnn-nn) 是否有 ≥1 个真实功能/需求实现
   历史项目的 US-N / FR-N 原样兼容，不要求重编号
2. 每个 Business Goal 是否有 ≥1 个 Metric
3. 每个 User Goal 是否有 ≥1 个 Metric
4. Persona / Goal / User Story 的角色一致性（启发式）

用法: py check_consistency.py path/to/PRD.md

输出一段可直接附在 PRD 末尾的 PASS/FAIL 报告
"""
import re
import sys
from pathlib import Path


def extract_ids(text: str, pattern: str) -> list[str]:
    """提取所有匹配 pattern 的 ID（如 US-1, FR-2）"""
    return re.findall(pattern, text)


STORY_ID = r"(?:US-F\d{2,}-\d{2,}|US[-_]?\d+)"
REQUIREMENT_ID = r"(?:REQ-F\d{2,}-\d{2,}|F\d{2,}|FR[-_]?\d+)"
RECORD_ID = rf"(?:{STORY_ID}|{REQUIREMENT_ID}|AC-F\d{{2,}}-\d{{2,}}|NFR-\d+)"


def normalize_id(value: str) -> str:
    value = value.upper()
    legacy = re.fullmatch(r"(US|FR)[-_]?(\d+)", value)
    return f"{legacy.group(1)}-{legacy.group(2)}" if legacy else value


def declared_record_id(line: str) -> str | None:
    """只认标题、列表或表格首列中的定义，不把正文里的引用当定义。"""
    cleaned = re.sub(r"[*`]", "", line).strip()
    if cleaned.startswith("|"):
        first_cell = cleaned.strip("|").split("|", 1)[0].strip()
        return normalize_id(first_cell) if re.fullmatch(RECORD_ID, first_cell, re.I) else None
    if re.match(r"^#{1,6}\s", cleaned):
        heading_id = re.search(rf"(?<![A-Z0-9_-])({RECORD_ID})(?![A-Z0-9_-])", cleaned, re.I)
        return normalize_id(heading_id.group(1)) if heading_id else None
    match = re.match(
        rf"^(?:#{{1,6}}\s+)?(?:[-+]\s+)?(?:Feature\s+)?({RECORD_ID})(?=$|\s|[:：.·（(])",
        cleaned,
        re.I,
    )
    return normalize_id(match.group(1)) if match else None


def extract_records(text: str, wanted_id: str) -> dict[str, str]:
    """保留记录自身内容，到下一条定义或下一章节为止，避免借用相邻记录。"""
    lines = text.splitlines()
    records = {}
    for index, line in enumerate(lines):
        record_id = declared_record_id(line)
        if not record_id or not re.fullmatch(wanted_id, record_id, re.I):
            continue
        if record_id in records:
            continue
        end = index + 1
        # 表格行的下一行不是它的正文。
        if not line.lstrip().startswith("|"):
            while end < len(lines):
                if declared_record_id(lines[end]) or re.match(r"^\s*#{1,6}\s", lines[end]):
                    break
                end += 1
        records[record_id] = "\n".join(lines[index:end])
    return records


def extract_user_stories(text: str) -> dict[str, str]:
    return extract_records(text, STORY_ID)


def extract_functional_reqs(text: str) -> dict[str, str]:
    """提取稳定 Fnn / REQ-Fnn-nn，兼容历史 FR-N。"""
    return extract_records(text, REQUIREMENT_ID)


def normalize_role(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[*_`]", "", value)
    return re.sub(r"\s+", "", value).strip("：:，,。.;；")


def extract_role_alias_groups(text: str) -> list[set[str]]:
    section = re.search(
        r"###\s*2\.1[^\n]*(?:角色|用户)[^\n]*\n(.*?)(?=\n###\s|\n##\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section:
        return []

    groups: list[set[str]] = []
    for line in section.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [normalize_role(cell) for cell in line.strip().strip("|").split("|")]
        if (
            len(cells) < 2
            or cells[0] in {"角色", "用户角色"}
            or all(re.fullmatch(r":?-+:?", cell) for cell in cells)
        ):
            continue
        aliases = {cell for cell in cells[:2] if cell and cell != "-"}
        if aliases:
            groups.append(aliases)
    return groups


def extract_user_story_role(content: str) -> str | None:
    match = re.search(
        r"作为\s*(.+?)\s*[,，]\s*我希望",
        content,
        re.IGNORECASE,
    )
    if match:
        return normalize_role(match.group(1))
    role_field = re.search(r"^\s*-?\s*Role:\s*(.+)$", content, re.M | re.I)
    return normalize_role(role_field.group(1)) if role_field else None


def role_is_declared(role: str, groups: list[set[str]]) -> bool:
    for aliases in groups:
        for alias in aliases:
            if role == alias or (len(role) >= 2 and (role in alias or alias in role)):
                return True
    return False


def find_fr_references_in_us(us_content: str) -> list[str]:
    """找完整功能/需求 ID，不能把 US-F01-01 里的 F01 当功能引用。"""
    return [normalize_id(value) for value in re.findall(
        rf"(?<![A-Z0-9_-])({REQUIREMENT_ID})(?![A-Z0-9_-])", us_content, re.I
    )]


def extract_goals_and_metrics(text: str) -> tuple[list[str], list[str], list[str]]:
    """提取业务目标、用户目标、成功指标"""
    business_goals = []
    user_goals = []
    metrics = []

    # 启发式：找"业务目标"/"商业目标"/"Business Goal" 等章节后的列表项
    bg_section = re.search(
        r"(?:业务目标|商业目标|Business Goal[s]?)[^\n]*\n(.*?)(?=\n#+\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if bg_section:
        # 提取 - 或 * 开头的行
        for line in bg_section.group(1).split("\n"):
            line = line.strip()
            if line.startswith(("-", "*", "•")) and len(line) > 5:
                business_goals.append(line[1:].strip())

    ug_section = re.search(
        r"(?:用户目标|User Goal[s]?)[^\n]*\n(.*?)(?=\n#+\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if ug_section:
        for line in ug_section.group(1).split("\n"):
            line = line.strip()
            if line.startswith(("-", "*", "•")) and len(line) > 5:
                user_goals.append(line[1:].strip())

    metric_section = re.search(
        r"(?:成功指标|成功度量|Success Metric[s]?|度量指标)[^\n]*\n(.*?)(?=\n#+\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if metric_section:
        ms_text = metric_section.group(1)
        # 表格行
        for line in ms_text.split("\n"):
            line = line.strip()
            if "|" in line and not re.match(r"^[\s\|:\-]+$", line):
                metrics.append(line)
            elif line.startswith(("-", "*", "•")) and len(line) > 5:
                metrics.append(line[1:].strip())

    return business_goals, user_goals, metrics


def check_us_to_fr(
    user_stories: dict[str, str], functional_reqs: dict[str, str], text: str
) -> list[tuple[str, str, str]]:
    """返回 [(US-id, 实际实现 ID, status)]；悬空引用不可通过。"""
    results = []
    fr_ids_set = set(functional_reqs.keys())

    for us_id, us_content in user_stories.items():
        # 找 US 内容里直接引用的 FR
        fr_refs = find_fr_references_in_us(us_content)
        # 也检查功能/需求定义中的反向 Story 引用。
        referencing_frs = []
        for fr_id, fr_content in functional_reqs.items():
            story_refs = {normalize_id(value) for value in re.findall(
                rf"(?<![A-Z0-9_-])({STORY_ID})(?![A-Z0-9_-])", fr_content, re.I
            )}
            if us_id in story_refs:
                referencing_frs.append(fr_id)

        missing_refs = set(fr_refs) - fr_ids_set
        all_refs = sorted((set(fr_refs) & fr_ids_set) | set(referencing_frs))
        if missing_refs:
            status = "FAIL"
            ref_str = "undefined: " + ", ".join(sorted(missing_refs))
        elif all_refs:
            status = "PASS"
            ref_str = ", ".join(all_refs)
        else:
            status = "FAIL"
            ref_str = "(no defined feature/requirement implements it)"
        results.append((us_id, ref_str, status))

    return results


def check_goal_to_metric(goals: list[str], metrics: list[str]) -> list[tuple[str, str]]:
    """启发式：检查每个目标是否在 metrics 章节有相关条目"""
    results = []
    for goal in goals:
        # 提取目标的关键词
        keywords = [
            w for w in re.findall(r"[一-龥a-zA-Z]{2,}", goal) if len(w) > 1
        ][:3]
        if not keywords:
            results.append((goal, "FAIL (no keywords to match)"))
            continue
        # 看 metrics 里有没有任一关键词
        matched = False
        for metric in metrics:
            if any(kw in metric for kw in keywords):
                matched = True
                break
        status = "PASS" if matched else "FAIL"
        results.append((goal[:50], status))
    return results


def main():
    if len(sys.argv) < 2:
        print("用法: py check_consistency.py <PRD.md 文件路径>")
        sys.exit(2)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        sys.exit(2)

    text = file_path.read_text(encoding="utf-8", errors="replace")

    user_stories = extract_user_stories(text)
    functional_reqs = extract_functional_reqs(text)
    business_goals, user_goals, metrics = extract_goals_and_metrics(text)
    role_groups = extract_role_alias_groups(text)

    print(f"\n=== 一致性校验 PASS/FAIL: {file_path.name} ===\n")

    print(f"📊 提取统计:")
    print(f"  - User Stories: {len(user_stories)}")
    print(f"  - Functional Requirements: {len(functional_reqs)}")
    print(f"  - Business Goals: {len(business_goals)}")
    print(f"  - User Goals: {len(user_goals)}")
    print(f"  - Success Metrics: {len(metrics)}")
    print()

    fail_count = 0

    # US → FR 映射
    print("## User Stories → 功能/需求映射")
    print()
    if user_stories:
        us_results = check_us_to_fr(user_stories, functional_reqs, text)
        for us_id, refs, status in us_results:
            marker = "✅" if status == "PASS" else "❌"
            print(f"  {marker} {us_id} → {refs} [{status}]")
            if status == "FAIL":
                fail_count += 1
    else:
        print("  ❌ 未识别到 User Stories 定义（使用现有稳定 US-Fnn-nn；历史 US-N 兼容）[FAIL]")
        fail_count += 1
    print()

    # Persona / Role → User Story 一致性
    print("## 角色矩阵 → User Stories 一致性")
    print()
    if user_stories and not role_groups:
        print("  ❌ 未识别到 §2.1 用户角色矩阵 [FAIL]")
        fail_count += 1
    elif user_stories:
        for us_id, content in user_stories.items():
            role = extract_user_story_role(content)
            if not role:
                print(f"  ❌ {us_id} 没有可识别的“作为某角色，我希望” [FAIL]")
                fail_count += 1
            elif not role_is_declared(role, role_groups):
                print(f"  ❌ {us_id} 的角色“{role}”未出现在 §2.1 角色矩阵 [FAIL]")
                fail_count += 1
            else:
                print(f"  ✅ {us_id} → {role} [PASS]")
    else:
        print("  ⚠️  没有 User Stories，无法检查角色一致性")
    print()

    # Business Goals → Metrics
    print("## Business Goals → Metrics 映射")
    print()
    if business_goals:
        bg_results = check_goal_to_metric(business_goals, metrics)
        for goal, status in bg_results:
            marker = "✅" if status == "PASS" else "❌"
            print(f'  {marker} "{goal}..." → [{status}]')
            if status == "FAIL":
                fail_count += 1
    else:
        print("  ⚠️  未识别到 Business Goals 章节")
    print()

    # User Goals → Metrics
    print("## User Goals → Metrics 映射")
    print()
    if user_goals:
        ug_results = check_goal_to_metric(user_goals, metrics)
        for goal, status in ug_results:
            marker = "✅" if status == "PASS" else "❌"
            print(f'  {marker} "{goal}..." → [{status}]')
            if status == "FAIL":
                fail_count += 1
    else:
        print("  ⚠️  未识别到 User Goals 章节")
    print()

    # 总结
    if fail_count == 0:
        print("✅ 全部 PASS — PRD 一致性 OK")
        sys.exit(0)
    else:
        print(f"❌ {fail_count} 个 FAIL — 需修复后才能定稿")
        print("\n建议处理：")
        print("  - US 没有实际实现或引用未定义 ID → 补齐真实功能/需求映射，不重编号")
        print("  - Goal 没有 Metric → 立即追问：怎么衡量？基线？目标？时间窗？")
        sys.exit(2)


if __name__ == "__main__":
    main()
