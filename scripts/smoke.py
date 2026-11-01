#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke.py —— 端到端冒烟（零第三方依赖）

四段：
  1. 语法     app/hello_agent.py 能否编译
  2. 链路     app/hello_agent.py --mock 是否真的走了「意图 → 工具 → 回复」
  3. 结构     app/index.html 是否还留着三色分级、确认兜底、审计导出的骨架
  4. 行为     用 Node 跑 app/index.html 的脚本，12 项断言（见 scripts/js_harness.mjs）

用法：python scripts/smoke.py            # 任一 FAIL 则退出码 1
"""
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
HARNESS = ROOT / "scripts" / "js_harness.mjs"

results = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def child_env() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def find_node():
    env = os.environ.get("NODE_BIN")
    if env and Path(env).is_file():
        return env
    found = shutil.which("node")
    if found:
        return found
    for cand in (
        Path.home() / ".dsh" / "dsh-runtimes" / "dsh-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "node.exe",
    ):
        if cand.is_file():
            return str(cand)
    return None


def step_syntax() -> None:
    target = APP / "hello_agent.py"
    try:
        py_compile.compile(str(target), doraise=True)
        record("PASS", "语法.hello_agent.py 可编译")
    except py_compile.PyCompileError as exc:
        record("FAIL", "语法.hello_agent.py 可编译", str(exc).splitlines()[-1][:100])


def step_mock() -> None:
    target = APP / "hello_agent.py"
    proc = subprocess.run(
        [sys.executable, str(target), "--mock"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=child_env(), timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    record("PASS" if proc.returncode == 0 else "FAIL",
           "链路.mock 退出码为 0", f"rc={proc.returncode}")
    record("PASS" if "[工具调用] transfer" in out else "FAIL",
           "链路.真的调用了工具", "输出里没出现 [工具调用] transfer")
    record("PASS" if "balance_cents" in out else "FAIL",
           "链路.回复来自工具结果", "输出里没有工具返回的 balance_cents")
    record("PASS" if "990000" in out else "FAIL",
           "链路.扣款精确到分", "转账 100.00 元后余额应为 990000 分")


def step_structure() -> None:
    html = (APP / "index.html").read_text(encoding="utf-8", errors="replace")
    required = {
        "互动区": 'id="messages"',
        "审计面板": 'id="audit-list"',
        "输入框": 'id="user-input"',
        "脱敏函数": "function mask(",
        "审计函数": "function audit(",
        "确认兜底(确认前不执行)": "let pending = null",
        "自动执行决策": "auto_execute",
        "拦截决策": "blocked_mfa_required",
        "用户取消决策": "cancelled_by_user",
        "审计导出": "exportAuditLog",
        "语音播报": "toSpeechText",
        "语音引擎": "speechSynthesis",
        "语音输入": "startVoiceInput",
        "大字模式": "big-text",
        "单条朗读": "speakMessage",
        "逐步引导": "startGuide",
        "图标确认": "big-icon",
        "电话通道": "ivrKey",
        "语音实时转写": "voice-live",
        "审计筛选": "setAuditFilter",
        "挂断": "closeIvr",
        "重听": "speakAsk",
        "焦点可达": "focus-visible",
    }
    missing = [name for name, token in required.items() if token not in html]
    record("PASS" if not missing else "FAIL",
           "结构.index.html 骨架完整",
           f"缺少：{'、'.join(missing)}" if missing else "")


def step_family() -> None:
    """家属端存在，且两端回执算法逐字一致——不一致就等于第二通道形同虚设。"""
    fam = APP / "family.html"
    if not fam.is_file():
        record("FAIL", "结构.家属端存在", "缺 app/family.html")
        return

    def block(text: str):
        i = text.find("function shortHash(text) {")
        if i < 0:
            return None
        j = text.find("\n}", i)
        return re.sub(r"\s+", "", text[i:j]) if j > i else None

    a = block((APP / "index.html").read_text(encoding="utf-8", errors="replace"))
    b = block(fam.read_text(encoding="utf-8", errors="replace"))
    record("PASS" if a and a == b else "FAIL",
           "结构.两端回执算法一致",
           "" if a and a == b else "index.html 与 family.html 的 shortHash 实现不一致")


def step_framework() -> None:
    """框架闸门：docs/capabilities.json 必须与代码里的工具表/权限表/规则表逐项一致。"""
    node = find_node()
    if not node:
        record("SKIP", "框架.能力清单与代码一致", "未找到 node")
        return
    proc = subprocess.run(
        [node, str(ROOT / "scripts" / "js_harness.mjs"), "--capabilities"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=child_env(), timeout=60,
    )
    try:
        code_caps = json.loads((proc.stdout or "").strip())
    except json.JSONDecodeError:
        record("FAIL", "框架.能力清单与代码一致", f"导出失败：{(proc.stderr or '')[:100]}")
        return

    doc_path = ROOT / "docs" / "capabilities.json"
    try:
        doc = json.loads(doc_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        record("FAIL", "框架.能力清单与代码一致", f"读不到 docs/capabilities.json：{exc}")
        return

    problems = []
    doc_tools = set(doc.get("tools", {}))
    if doc_tools != set(code_caps["tools"]):
        problems.append(f"工具不一致：文档多 {sorted(doc_tools - set(code_caps['tools']))}，代码多 {sorted(set(code_caps['tools']) - doc_tools)}")
    for name, meta in doc.get("tools", {}).items():
        if code_caps["levels"].get(name) != meta.get("level"):
            problems.append(f"{name} 级别不一致：文档 {meta.get('level')} / 代码 {code_caps['levels'].get(name)}")
    for name in doc.get("red_only", {}):
        if code_caps["levels"].get(name) != "red":
            problems.append(f"{name} 应为 red，代码是 {code_caps['levels'].get(name)}")
        if name in code_caps["tools"]:
            problems.append(f"{name} 判红却实现了工具，等于给了绕过路径")
    if list(doc.get("rules", [])) != code_caps["rules"]:
        problems.append(f"规则表不一致：文档 {doc.get('rules')} / 代码 {code_caps['rules']}")

    record("PASS" if not problems else "FAIL",
           "框架.能力清单与代码一致",
           "；".join(problems) if problems else "")


def step_intent() -> None:
    """意图评测集：量化"落对工具率"，防止宽规则抢答窄意图。"""
    node = find_node()
    cases_path = ROOT / "docs" / "intent_cases.json"
    if not node:
        record("SKIP", "意图.评测集全部落对", "未找到 node")
        return
    if not cases_path.is_file():
        record("FAIL", "意图.评测集全部落对", "缺 docs/intent_cases.json")
        return
    proc = subprocess.run(
        [node, str(HARNESS), "--intent"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=child_env(), timeout=60,
    )
    try:
        rows = json.loads((proc.stdout or "").strip())
    except json.JSONDecodeError:
        record("FAIL", "意图.评测集全部落对", f"评测输出不可解析：{(proc.stderr or '')[:80]}")
        return
    bad = [r for r in rows if not r.get("ok")]
    detail = "；".join(f"{r['say']}→期望 {r['expect']} 实得 {r['got']}" for r in bad[:3])
    record("PASS" if rows and not bad else "FAIL",
           f"意图.评测集 {len(rows)} 条全部落对", detail)


def step_intent_service() -> None:
    """意图服务联调：起服务 → 问三句 → 校验 schema / 白名单 / 低置信度 → 关掉。"""
    node = find_node()
    if not node:
        record("SKIP", "适配器.服务联调", "未找到 node")
        return
    port = 8797
    proc = subprocess.Popen(
        [node, str(ROOT / "scripts" / "intent_service.mjs"), str(port)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    problems = []

    def post(text: str) -> dict:
        import urllib.request
        req = urllib.request.Request(
            f"{base}/intent",
            data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        import time
        import urllib.request
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=1) as resp:
                    health = json.loads(resp.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(0.2)
        else:
            record("FAIL", "适配器.服务联调", "服务 6 秒内没起来")
            return

        if not health.get("ok"):
            problems.append("health 不正常")
        # ① 回放命中：规则认不出的长尾句子
        r1 = post("卡里还有多少")
        if not (r1.get("ok") and r1.get("tool") == "query_balance" and r1.get("source") == "mock"):
            problems.append(f"回放未命中：{r1}")
        # ② 低置信度：必须拒绝，交给调用方反问
        r2 = post("帮我把那笔钱转给老李")
        if r2.get("ok") or r2.get("reason") != "low_confidence":
            problems.append(f"低置信度未拦：{r2}")
        # ③ 完全不认识：ok:false
        r3 = post("今天天气怎么样")
        if r3.get("ok"):
            problems.append(f"未知句子被瞎猜：{r3}")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"联调异常：{exc}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    record("PASS" if not problems else "FAIL", "适配器.服务联调", "；".join(problems) if problems else "")


def step_behavior() -> None:
    node = find_node()
    if not node:
        record("SKIP", "行为.JS 断言", "未找到 node，跳过（可用 NODE_BIN 指定）")
        return
    proc = subprocess.run(
        [node, str(HARNESS)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=child_env(), timeout=60,
    )
    raw = (proc.stdout or "").strip()
    try:
        cases = json.loads(raw)
    except json.JSONDecodeError:
        record("FAIL", "行为.JS 断言", f"harness 输出不可解析：{raw[:120] or (proc.stderr or '')[:120]}")
        return
    for case in cases:
        record("PASS" if case.get("ok") else "FAIL",
               f"行为.{case.get('name', '?')}", str(case.get("err", ""))[:100])


def main() -> int:
    step_syntax()
    step_mock()
    step_structure()
    step_family()
    step_framework()
    step_intent()
    step_intent_service()
    step_behavior()

    fails = [r for r in results if r[0] == "FAIL"]
    skips = [r for r in results if r[0] == "SKIP"]
    print("=" * 68)
    print("smoke.py · 冒烟")
    print("=" * 68)
    for status, name, detail in results:
        icon = {"PASS": "  ✓", "FAIL": "  ✗", "SKIP": "  -"}[status]
        line = f"{icon} [{status}] {name}"
        if detail and status != "PASS":
            line += f"  ← {detail}"
        print(line)
    print("-" * 68)
    print(f"  PASS {len(results) - len(fails) - len(skips)}   FAIL {len(fails)}   SKIP {len(skips)}")
    print("  结果：" + ("通过" if not fails else "不通过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
