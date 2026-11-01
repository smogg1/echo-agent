#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py —— 静态自检闸门（零第三方依赖）

扫描仓库，拦三类硬伤（FAIL），报一类嫌疑（WARN）：

  FAIL  密钥特征    sk- 形钥匙；硬编码的 api_key / secret / token / password
  FAIL  明文卡号    16–19 位连续数字（"6222 0202 0011 1234" 分组写法、****1234 不算）
  FAIL  占位实现    TODO / FIXME / 待实现 / 待补充 / 待完善（只扫代码文件）
  WARN  浮点金额    金额应一律整数分（Day 1 目标：WARN 清零）

用法：
  python scripts/check.py         # 有 FAIL 则退出码 1
  python scripts/check.py -v      # 附加打印全部 WARN 明细
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

CODE_EXT = {".py", ".js", ".mjs", ".html", ".htm", ".css", ".json", ".yml", ".yaml"}
TEXT_EXT = CODE_EXT | {".md", ".txt", ".ps1", ".sh", ".sql"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".releases", ".venv", ".tmp"}

SECRET_RULES = [
    ("sk- 形密钥", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("硬编码凭证", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|passwd|password)\b\s*[=:]\s*[\"'][^\"'\s]{12,}[\"']")),
    ("Bearer 明文", re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}")),
]
CARD_RULE = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
PLACEHOLDER_RULE = re.compile(r"(?i)\b(TODO|FIXME)\b|待实现|待补充|待完善")
# 只抓"把金额当浮点处理"的写法，不抓 1,000.00 这类显示字符串
FLOAT_HINT = re.compile(r"\b(?:parseFloat|toFixed)\s*\(|\bfloat\s*\(|:\s*float\b|->\s*float\b")


def iter_files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.resolve() == SELF:
            continue
        if p.suffix.lower() not in TEXT_EXT:
            continue
        yield p


def redact(s: str, keep: int = 6) -> str:
    s = s.strip()
    return s[:keep] + "…" if len(s) > keep else s


def main() -> int:
    verbose = "-v" in sys.argv
    fails, warns = [], []

    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            fails.append(("读取失败", rel, str(exc)[:60]))
            continue

        is_code = path.suffix.lower() in CODE_EXT
        for no, line in enumerate(text.splitlines(), 1):
            for name, rule in SECRET_RULES:
                hit = rule.search(line)
                if hit:
                    fails.append((name, f"{rel}:{no}", redact(hit.group(0))))
            hit = CARD_RULE.search(line)
            if hit:
                fails.append(("明文卡号", f"{rel}:{no}", redact(hit.group(0), 4)))
            if is_code:
                hit = PLACEHOLDER_RULE.search(line)
                if hit:
                    fails.append(("占位实现", f"{rel}:{no}", hit.group(0)))
                hit = FLOAT_HINT.search(line)
                if hit:
                    warns.append(("浮点金额", f"{rel}:{no}", hit.group(0)))

    print("=" * 62)
    print("check.py · 静态闸门")
    print("=" * 62)
    for name, where, snippet in fails:
        print(f"  [FAIL] {name:<8} {where:<34} {snippet}")
    if verbose:
        for name, where, snippet in warns:
            print(f"  [WARN] {name:<8} {where:<34} {snippet}")
    print("-" * 62)
    print(f"  FAIL {len(fails)}   WARN {len(warns)}"
          + ("" if verbose else "   （-v 查看 WARN 明细）"))
    if fails:
        print("  结果：不通过 —— 先修 FAIL 再提交")
        return 1
    print("  结果：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
