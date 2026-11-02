#!/usr/bin/env python3
"""
check_format.py - PRD 正文实现边界检查

扫描 PRD 文件：
1. HTTP 方法 + API 路径（提示核对外部契约与实现细节，不阻断）
2. 明确的 SQL 字段声明（普通文件格式、字段含义不属于此类）
3. 信号路径 / CAN总线 / 硬件型号（提示核对已确认的硬件约束）

退出码: 0 = 无硬错误（可能有供人工判断的提示）；2 = 硬错误或输入缺失。

用法: py check_format.py path/to/PRD.md
"""
import re
import sys
from pathlib import Path


# HTTP 方法 + API 路径
API_PATTERN = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+/\S+")

# 识别字段前缀和明确 SQL 语法，不穷举整行方言后缀；普通 JSON / text 文案不算声明。
SQL_FIELD_PATTERN = re.compile(
    r"^\s*(?:[-*]\s+)?`?[A-Za-z_][A-Za-z_0-9]*`?\s+"
    r"(?P<type>(?:varchar|char)\s*\(\s*\d+\s*\)|"
    r"(?:int|bigint|smallint|integer|boolean|timestamp|datetime|text|jsonb?))"
    r"(?=\s|[,;]|$)"
    r"(?P<constraints>\s+(?:NOT\s+NULL|NULL|PRIMARY\s+KEY|UNIQUE|"
    r"DEFAULT|REFERENCES|AUTO_INCREMENT|UNSIGNED|COMMENT|GENERATED|CHECK|COLLATE)\b)?"
    r"\s*(?P<terminator>[,;]?)",
    re.IGNORECASE,
)

# 硬件/技术细节模式
HW_PATTERNS = [
    r"\bCAN\s*(总线|bus|\d+kbps)\b",
    r"\bLIN\s*总线\b",
    r"\bSoC\s*(型号|路由)\b",
    r"\b\d+kbps\b.*(信号|总线)",
    r"\bECU\s*固件\b",
    r"\bMQTT\s*topic\s*/",
    r"\bWebSocket\s*messageType\s*:",
    r"\bgRPC\s+",
    r"\bprotobuf\s+",
]

# 技术 SDK/库直接引用
SDK_PATTERN = re.compile(r"\b(import|require|using|from)\s+['\"]?[\w\.]+", re.IGNORECASE)


def check_file(file_path: Path) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)"""
    errors = []
    warnings = []

    if not file_path.exists():
        errors.append(f"文件不存在: {file_path}")
        return errors, warnings

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    in_code_block = False

    for i, line in enumerate(lines, 1):
        # 代码块内不检查（开发者参考可保留）
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # HTTP 方法 + API 路径
        m = API_PATTERN.search(line)
        if m:
            warnings.append(
                f"L{i}: 接口路径 '{m.group()}' — 核对是否为已确认的外部契约或兼容约束；"
                f"属于约束则保留，未确认的内部实现留给设计。原文: {line[:80]}"
            )

        # 明确的 SQL 字段声明
        m = SQL_FIELD_PATTERN.match(line)
        if m and (
            "(" in m.group("type")
            or m.group("constraints")
            or m.group("terminator")
        ):
            errors.append(
                f"L{i}: SQL 字段声明 '{m.group().strip()}' — PRD 正文保留字段含义和已确认约束，"
                f"存储声明放到设计或代码参考。原文: {line[:80]}"
            )

        # 硬件/技术细节
        for pattern in HW_PATTERNS:
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                warnings.append(
                    f"L{i}: 硬件/技术细节 '{m.group()}' — 已确认的设备或协议约束保留，"
                    f"其余内部实现留给设计。原文: {line[:80]}"
                )

        # SDK/import 直接引用
        if SDK_PATTERN.search(line) and not line.strip().startswith("//") and not line.strip().startswith("#"):
            warnings.append(
                f"L{i}: SDK/import 引用 — 核对是否为已确认的来源或兼容约束，"
                f"内部实现留给设计。原文: {line[:80]}"
            )

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        print("用法: py check_format.py <PRD.md 文件路径>")
        sys.exit(2)

    file_path = Path(sys.argv[1])
    errors, warnings = check_file(file_path)

    print(f"\n=== 格式校验: {file_path.name} ===\n")

    if errors:
        print(f"❌ {len(errors)} 个致命错误（技术细节越界）:\n")
        for err in errors:
            print(f"  {err}")
        print()

    if warnings:
        print(f"⚠️  {len(warnings)} 个警告:\n")
        for warn in warnings:
            print(f"  {warn}")
        print()

    if not errors and not warnings:
        print("✅ 格式检查全部通过")
        sys.exit(0)
    elif errors:
        print(f"\n❌ 校验失败 - {len(errors)} 错误, {len(warnings)} 警告")
        sys.exit(2)
    else:
        print(f"\n⚠️  以上为需结合需求判断的提示，不阻断交付；不代表存在需求错误")
        sys.exit(0)


if __name__ == "__main__":
    main()
