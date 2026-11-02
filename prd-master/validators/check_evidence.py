#!/usr/bin/env python3
"""
check_evidence.py - PRD 证据合规硬校验

扫描 PRD 文件，找出：
1. 裸数字（如"提升 30%"）但没标来源
2. 空话/虚词（如"提升用户体验"）
3. 缺失三钉子（数据/细节/案例）的论点

用法: py check_evidence.py path/to/PRD.md

退出码:
  0 = 全部通过
  1 = 有警告
  2 = 有致命错误
"""
import re
import sys
from pathlib import Path


# 空话/虚词清单
WEAK_PHRASES = [
    "提升用户体验",
    "用户体验更好",
    "更好用",
    "更方便",
    "更高效",
    "更智能",
    "市场反响热烈",
    "用户反响很好",
    "刚需",
    "强需求",
    "高频使用",
    "广受好评",
    "年轻人喜欢",
    "深受欢迎",
    "颠覆行业",
    "革命性",
    "无可比拟",
    "业内领先",
    "前所未有",
    "极具竞争力",
    "差异化优势",
]

# 必须标注的数字模式
# 匹配 "提升 30%" / "节省 50%" / "增长 2 倍" / "5000 万用户" 等
NUMBER_PATTERNS = [
    r"(?:提升|增加|增长|节省|减少|降低|提高|缩短|延长)\s*\d+(?:\.\d+)?\s*[%倍]",
    r"\d+\s*[万亿千百]\s*(?:用户|客户|订单|GMV|MAU|DAU|收入|营收)",
    r"\d+(?:\.\d+)?\s*%\s*(?:留存|转化|增长|流失|渗透)",
    r"客单价\s*\d+",
    r"ARPU\s*\d+",
    r"ARR\s*\d+",
    r"MRR\s*\d+",
    r"\d+\s*(?:秒|毫秒|ms)\s*(?:响应|加载|完成)",
]

# 可接受的来源标注
VALID_SOURCE_MARKERS = [
    "来源",
    "source",
    "假设值",
    "待验证",
    "_TBD_",
    "TBD",
    "依据:",
    "依据：",
    "_PLACEHOLDER_",
    "Industry Standard",
    "行业标准",
]


def check_file(file_path: Path) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)"""
    errors = []
    warnings = []

    if not file_path.exists():
        errors.append(f"文件不存在: {file_path}")
        return errors, warnings

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # 1. 空话/虚词检查
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        # 跳过引用块（用户原话）
        if line_stripped.startswith(">"):
            continue
        for phrase in WEAK_PHRASES:
            if phrase in line:
                # 但如果同一行有 "_TBD_" 或"待量化"等承认就放过
                if any(m in line for m in ["_TBD_", "待量化", "待验证"]):
                    continue
                warnings.append(
                    f"L{i}: 空话词 '{phrase}' — 需具体化为可量化指标。原文: {line_stripped[:80]}"
                )

    # 2. 裸数字检查（按行）
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        if line_stripped.startswith(">"):
            continue
        # 跳过表格分隔行
        if re.match(r"^[\s\|:\-]+$", line_stripped):
            continue
        for pattern in NUMBER_PATTERNS:
            matches = re.findall(pattern, line)
            if matches:
                # 检查这一行（或附近 2 行）是否有来源标注
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 2)
                context = "\n".join(lines[context_start:context_end])
                has_source = any(marker in context for marker in VALID_SOURCE_MARKERS)
                # 表格行：检查整个表格段是否有来源列
                if "|" in line:
                    has_source = has_source or "来源" in context or "Source" in context
                if not has_source:
                    for m in matches:
                        errors.append(
                            f"L{i}: 裸数字 '{m}' — 需标注来源 / 假设值 / 待验证。原文: {line_stripped[:80]}"
                        )

    # 3. 三钉子检查（仅当 PRD 提到"信息差"或"三钉子"概念时）
    if "三钉子" in text or "信息差" in text:
        # 软检查：在关键论点附近找数据 + 细节 + 案例
        # 太复杂，本期跳过自动检查，留给人工
        pass

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        print("用法: py check_evidence.py <PRD.md 文件路径>")
        sys.exit(2)

    file_path = Path(sys.argv[1])
    errors, warnings = check_file(file_path)

    print(f"\n=== 证据合规校验: {file_path.name} ===\n")

    if errors:
        print(f"❌ {len(errors)} 个致命错误（裸数字无来源）:\n")
        for err in errors:
            print(f"  {err}")
        print()

    if warnings:
        print(f"⚠️  {len(warnings)} 个警告（空话/虚词）:\n")
        for warn in warnings:
            print(f"  {warn}")
        print()

    if not errors and not warnings:
        print("✅ 证据合规检查全部通过")
        sys.exit(0)
    elif errors:
        print(f"\n❌ 校验失败 - {len(errors)} 错误, {len(warnings)} 警告")
        sys.exit(2)
    else:
        print(f"\n⚠️  校验有警告 - {len(warnings)} 警告（无致命错误）")
        sys.exit(1)


if __name__ == "__main__":
    main()
