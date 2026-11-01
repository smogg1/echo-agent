#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snapshot.py —— 版本快照（本机没有 git，用它替代 commit）

产出：
  .releases/<tag>/            源码副本
  .releases/<tag>/MANIFEST.sha256   每个文件的 SHA256，用于判断"到底改了什么"

用法：
  python scripts/snapshot.py v0.1.0
  python scripts/snapshot.py v0.1.0 --diff     # 顺带与上一版对比增删改
"""
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / ".releases"
EXCLUDE = {".releases", "__pycache__", "node_modules", ".git", ".venv", ".tmp"}


def collect() -> list:
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        if any(part in EXCLUDE for part in p.parts):
            continue
        out.append(p)
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def latest_previous(tag: str):
    if not STORE.exists():
        return None
    dirs = [d for d in STORE.iterdir() if d.is_dir() and d.name != tag and (d / "MANIFEST.sha256").exists()]
    return sorted(dirs, key=lambda d: d.stat().st_mtime)[-1] if dirs else None


def read_manifest(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        data[rel.strip()] = digest.strip()
    return data


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_diff = "--diff" in sys.argv
    if not args:
        print("用法：python scripts/snapshot.py <tag>  例：python scripts/snapshot.py v0.1.0")
        return 2
    tag = args[0]
    dest = STORE / tag
    if dest.exists():
        print(f"快照已存在：{dest}（要重做请先删除该目录）")
        return 2

    files = collect()
    dest.mkdir(parents=True)
    manifest = []
    total = 0
    for p in files:
        rel = p.relative_to(ROOT)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        total += p.stat().st_size
        manifest.append(f"{sha256(p)}  {rel.as_posix()}")
    (dest / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    print(f"快照 {tag}：{len(files)} 个文件，{total / 1024:.1f} KB → {dest}")

    if want_diff:
        prev = latest_previous(tag)
        if not prev:
            print("对比：无上一版")
            return 0
        old = read_manifest(prev / "MANIFEST.sha256")
        new = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in manifest}
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(k for k in set(new) & set(old) if new[k] != old[k])
        print(f"对比 {prev.name}：+{len(added)} / -{len(removed)} / ~{len(changed)}")
        for k in added:
            print(f"  + {k}")
        for k in changed:
            print(f"  ~ {k}")
        for k in removed:
            print(f"  - {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
