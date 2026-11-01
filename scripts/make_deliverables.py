# -*- coding: utf-8 -*-
"""生成四份提交材料：技术文档 / 答辩 PPT / 安全自评报告 / 源码包内容。"""
import json
import os
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Inches, Pt as PPt
from pptx.dml.color import RGBColor as PRGB

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables"
ASSETS = OUT / "assets"
OUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

CAPS = json.loads((ROOT / "docs" / "capabilities.json").read_text(encoding="utf-8"))
TOOLS = CAPS["tools"]
RED_ONLY = CAPS["red_only"]
RULES = CAPS["rules"]
N_TOOLS = len(TOOLS) + len(RED_ONLY)
N_RULES = len(RULES)
INTENT_CASES = json.loads((ROOT / "docs" / "intent_cases.json").read_text(encoding="utf-8"))
N_CASES = len(INTENT_CASES)
N_ASSERT = 136

INK = RGBColor(0x11, 0x12, 0x14)
SUB = RGBColor(0x6E, 0x73, 0x78)
ACCENT = RGBColor(0x2A, 0x5C, 0xDB)
FONT = "微软雅黑"


def set_font(run, size=None, bold=None, color=None, mono=False):
    name = "Consolas" if mono else FONT
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def para(doc, text, size=10.5, bold=False, color=INK, space_after=4, align=None, mono=False):
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.35
    run = p.add_run(text)
    set_font(run, size, bold, color, mono)
    return p


def heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    set_font(run, 16 if level == 1 else 12.5, True, INK)
    return p


def table(doc, headers, rows, widths=None, size=9):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        set_font(run, size, True, INK)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            set_font(run, size, False, INK)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = Cm(w)
    return t


# ---------------------------------------------------------------- 架构图
def make_diagram():
    W, H = 1600, 900
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    try:
        f_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 34)
        f_mid = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
        f_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    except OSError:
        f_big = f_mid = f_sm = ImageFont.load_default()

    def box(x, y, w, h, title, sub="", color="#111214", fill="#FFFFFF"):
        d.rounded_rectangle([x, y, x + w, y + h], radius=14, outline=color, width=3, fill=fill)
        d.text((x + 18, y + 14), title, font=f_mid, fill=color)
        if sub:
            d.text((x + 18, y + 52), sub, font=f_sm, fill="#6E7378")

    d.text((60, 40), "回声 Agent · 一个内核，三个入口", font=f_big, fill="#111214")
    d.text((60, 92), "模型只决定“想办什么”，决定不了“能不能办”", font=f_sm, fill="#6E7378")

    box(60, 150, 460, 110, "老人端 index.html", "语音 / 大字 / 图标 / 电话模式")
    box(570, 150, 460, 110, "家属端 family.html", "只收口令、金额、收款人 → 回执")
    box(1080, 150, 460, 110, "渠道 webhook.mjs", "IM / APP 网关，只转发不判定")

    for cx in (290, 800, 1310):
        d.line([cx, 260, cx, 320], fill="#DEDFE2", width=3)
        d.polygon([(cx - 8, 312), (cx + 8, 312), (cx, 326)], fill="#DEDFE2")

    box(60, 330, 1480, 90, "① 意图层", "规则 resolveIntent() ｜ 认不出 → 意图服务（LLM/回放），白名单 + 置信度 ≥0.6，否则反问", color="#111214")
    box(60, 440, 1480, 90, "② 判定层 evaluate()", f"{N_RULES} 条规则：金额 / 收款人 / 可逆性 / 频次；只读状态，每条命中都给 rule + 带数字的 detail", color="#8A6100")
    box(60, 550, 1480, 90, "③ 确认层 runPending()", "确认前不执行；转账走双通道（老人口令 + 家属回执）；红级拦截并给出“接下来怎么办”", color="#111214")
    box(60, 660, 700, 90, "④ 执行层 TOOL_IMPL", f"{N_TOOLS} 个工具，白名单 + 参数校验（整数分）", color="#0F7B5F")
    box(800, 660, 740, 90, "⑤ 审计层 audit()", "五要素留痕 · 卡号脱敏 · JSONL 导出 · 可按决策筛选", color="#0F7B5F")

    d.text((60, 790), f"验证：{N_ASSERT} 项断言（含 {N_CASES} 条意图评测）+ 三次负向验证", font=f_sm, fill="#6E7378")
    d.text((60, 825), "离线可跑：断网时规则层与回放层接管，语音降级会明说", font=f_sm, fill="#6E7378")

    path = ASSETS / "architecture.png"
    img.save(path)
    return path


# ---------------------------------------------------------------- 技术文档
def make_tech_doc(diagram):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)
    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("回声 Agent · 技术文档"), 24, True, INK)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p2.add_run("面向银发人群的受控语音银行智能体 ｜ 2026 FinTechathon 人工智能赛道"), 10.5, False, SUB)

    heading(doc, "一、项目定位")
    para(doc, "回声 Agent 面向不会用手机银行、也不该独自承担金融风险的老年人：用一句话完成查询、转账、挂失、退订等业务，"
              "动钱必须经过“家庭回声”——子女远程授权，老人始终是账户主体。产品名取自“呼唤必有回应”。")
    para(doc, "三层叙事同时也是三层技术架构：技术回声（听懂并办成）、家庭回声（授权兜底）、社会回声（异常升级与留痕）。")

    heading(doc, "二、系统架构")
    doc.add_picture(str(diagram), width=Cm(16))
    para(doc, "图 1 系统架构：一个内核，三个入口", 9, False, SUB, align=WD_ALIGN_PARAGRAPH.CENTER)

    heading(doc, "2.1 分层职责与不变量", 2)
    table(doc,
          ["层", "职责", "不变量"],
          [["① 意图", "一句话 → {tool, params}", "只做理解，不决定能不能办；认不出返回 null"],
           ["② 判定", "意图 → {level, hits}", "只读状态；每条命中必须给 rule 名与带数字的 detail"],
           ["③ 确认", "黄级挂起、红级拦截", "确认前工具绝不被调用；只有一个执行出口 runPending()"],
           ["④ 执行", "真正改数据", "仅白名单工具；金额整数分；非法参数在代码层拒绝"],
           ["⑤ 审计", "留痕", "时间/原话/工具/脱敏参数/决策+actor，卡号只留后四位"]],
          widths=[2.2, 5.2, 9.4])

    heading(doc, "2.2 三个入口共用一套逻辑", 2)
    table(doc,
          ["入口", "复用方式", "特点"],
          [["老人端 index.html", "页面内联脚本即内核", "断网双击可跑，演示主链路"],
           ["家属端 family.html", "只共享回执算法（shortHash）", "不显示操作详情，防转述误导"],
           ["渠道 webhook.mjs", "用 page_sandbox 在 Node 里跑同一份脚本", "渠道层不做判定，规则只有一份"],
           ["命令行 hello_agent.py", "独立的教学用最小闭环", "演示 Function Calling 与防幻觉"]],
          widths=[4.6, 6.0, 6.2])

    heading(doc, "三、核心算法说明")
    heading(doc, "3.1 可解释的三色判定", 2)
    para(doc, "判定 = 基础等级与命中规则取最严。规则只读 STATE，写入只发生在工具执行成功之后，"
              "因此“判定不改数据”可作为不变量被断言（rule.判定不改状态）。")
    rows = []
    for name, meta in TOOLS.items():
        rows.append([name, meta.get("scene", ""), {"green": "🟢 自动", "yellow": "🟡 确认", "red": "🔴 拦截"}[meta["level"]],
                     meta.get("confirm", "none")])
    for name, meta in RED_ONLY.items():
        rows.append([name, meta.get("scene", ""), "🔴 只拦不做", "人工/强验证"])
    table(doc, ["工具", "场景", "级别", "确认方式"], rows, widths=[5.0, 3.4, 3.0, 5.4], size=8.5)

    para(doc, f"当前 {N_RULES} 条规则：", 10.5, True, INK, space_after=2)
    table(doc, ["规则", "触发条件（摘要）"],
          [["memo_payee_rejected", "以备注中的账户信息作为收款依据"],
           ["payee_unverified_phone", "收款人是手机号且不在通讯录"],
           ["amount_over_single", "单笔超过 1,000.00 元"],
           ["amount_over_daily", "日累计超过 5,000.00 元（按天归零）"],
           ["payee_first_time", "收款人不在通讯录 → 升为“需确认”"],
           ["new_payee_over_limit", "新收款人单笔超过 200.00 元"],
           ["wealth_over_limit", "理财申购超过 5,000.00 元"],
           ["irreversible_op", "转账/挂失/改密等不可逆操作"],
           ["freq_over_limit", "10 分钟内同类操作 ≥ 3 次"]],
          widths=[5.4, 11.0], size=8.5)

    heading(doc, "3.2 双通道授权（家庭回声）", 2)
    para(doc, "老人端生成 6 位口令（2 分钟有效）；家属端不显示操作内容，必须独立输入“金额 + 收款人”才能算出回执；"
              "回执 = shortHash(收款人|金额分|口令|ok)，任一项不同即对不上。老人端校验回执后才执行，"
              "连续 3 次不符作废并记 family_blocked。")
    para(doc, "设计要点：家属端刻意不展示详情——防止老人被话术引导后转述，把“300 说成 3000”。"
              "当前为同机演示（两端共享算法），真实实现应由子女设备持私钥、老人端只持公钥验签。", 10, False, SUB)

    heading(doc, "3.3 混合意图路由", 2)
    para(doc, "规则层（关键词 + 正则 + 槽位）先跑：快、离线、可解释，命中直接进入判定。"
              "认不出时才调用意图服务（POST /intent）：有 key 走 OpenAI 兼容模型，无 key 读回放文件。"
              "服务返回必须通过四关——ok、工具白名单、参数类型、置信度 ≥ 0.6；低于阈值返回 low_confidence，"
              "由页面反问而不是猜。服务超时/未启动时静默回退规则层。")
    para(doc, f"意图评测集 {N_CASES} 条（docs/intent_cases.json），覆盖全部工具与“必须反问”的歧义句，"
              "以“落对率”为指标，危险误判率要求为 0。")

    heading(doc, "3.4 金额与精度", 2)
    para(doc, "所有金额以整数分存储与运算（amountCents），仅在展示层转为“5,000.00”。"
              "中文金额（五千/一百二十/两千五）在解析时直接转分，不经过浮点。")

    heading(doc, "四、安全设计")
    table(doc, ["威胁", "防线", "证据"],
          [["Prompt 注入（备注塞指令）", "确认环节不经过模型；工具白名单；参数校验", "guard.备注注入未动钱"],
           ["全角/零宽绕过", "解析前归一化：去零宽、全角转半角、方言词表", "inject.* 四条"],
           ["越权操作", "红级只拦不做（无实现体）；拦截后给“接下来怎么办”", "authz.*、block.*"],
           ["敏感数据泄露", "卡号只留后四位；审计五要素；导出 JSONL", "audit.卡号脱敏"],
           ["误操作不可逆", "按可逆性分级：临时冻结自动、正式挂失拦截", "stop.*"],
           ["冒充与转述", "双通道回执与参数强绑定", "family.金额不符则回执不同"]],
          widths=[5.0, 7.4, 4.4], size=9)
    para(doc, "完整自查见《安全自评报告》。")

    heading(doc, "五、验证方式")
    para(doc, f"共 {N_ASSERT} 项断言，分五段：语法与链路、结构、框架一致性、意图评测（{N_CASES} 条）、行为。"
              "关键做法是“负向验证”：把某个防线临时拆掉，确认对应断言真的会红。"
              "已做三次：归一化置空（inject.* 四红）、删掉“给去处”（block.* 两红 + reach.* 一红）、"
              "改写推荐规则（意图评测准确报出“推荐→期望 recommend_wealth 实得 list_wealth”）。")

    heading(doc, "六、部署与运行")
    table(doc, ["形态", "命令", "说明"],
          [["网页（主链路）", "双击 app/index.html", "单文件、零依赖、断网可跑"],
           ["意图服务", "node scripts/intent_service.mjs 8791", "有 key 用模型，无 key 用回放"],
           ["家属端", "双击 app/family.html", "与老人端配合演示双通道"],
           ["渠道", "node scripts/webhook.mjs 8790", "curl POST /webhook 返回 level"],
           ["外部服务", "python scripts/fx_server.py", "本地假汇率，关掉即演示降级"],
           ["闸门", "python scripts/smoke.py", f"{N_ASSERT} 项断言"]],
          widths=[3.6, 7.0, 6.2], size=9)

    heading(doc, "七、局限与演进")
    para(doc, "1) 真实模型未联调：本机无 key，fromLlm() 只有结构保证；2) 回放仅 8 条且为手写样例；"
              "3) 语音输入依赖浏览器识别，需联网；4) 双通道为同机简化；5) 无真实银行接口，业务数据为 Mock。"
              "演进路径：接入真实模型并录制回放 → 扩评测集至 200 条 → 接入银行沙箱接口。")

    path = OUT / "回声Agent-技术文档.docx"
    doc.save(path)
    return path


# ---------------------------------------------------------------- 安全自评
def make_security_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)
    doc.styles["Normal"].font.name = FONT
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.styles["Normal"].element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("回声 Agent · 安全自评报告"), 24, True, INK)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p2.add_run("权限分级实现说明与已知风险清单 ｜ 2026 FinTechathon"), 10.5, False, SUB)

    heading(doc, "一、结论摘要")
    para(doc, "本系统把“能不能办”完全放在代码里：模型只输出意图，判定、确认、执行、审计四层不接受模型直接指令。"
              "当前已实现三色权限分级、双通道授权、注入归一化、审计留痕与红级去处，并以 136 项断言覆盖。"
              "已知风险 7 项，其中 2 项为演示简化，5 项为能力缺口，逐条列于第五节。")

    heading(doc, "二、权限分级实现说明")
    table(doc, ["级别", "判定依据", "执行策略", "工具示例"],
          [["🟢 绿", "只读，不改数据", "自动执行", f"query_balance、list_bills、upcoming_renewals（共 {sum(1 for t in TOOLS.values() if t['level'] == 'green')} 个）"],
           ["🟡 黄", "改数据但可逆，或金额在新收款人额度内", "用户确认；转账可走家属回执", "transfer、cancel_subscription、buy_wealth"],
           ["🔴 红", "不可逆，或超过额度/频率阈值", "拦截 + 给出去处 + 转人工留痕", "report_loss、change_password"]],
          widths=[2.2, 6.2, 5.0, 3.4], size=9)
    para(doc, "实现要点：① 基础等级取自 PERMISSIONS，规则命中只升不降；② 红级工具**没有实现体**，"
              "TOOL_IMPL 中不存在，调用即返回“该能力未开放”；③ 所有确认后执行只有一个出口 runPending()，"
              "避免出现第二条绕过路径；④ 拦截后按命中规则给定制建议，并支持“转人工”留痕（handoff_to_human）。")

    heading(doc, "三、注入与越权防护")
    table(doc, ["攻击面", "实现", "验证方式"],
          [["零宽/全角绕过", "normalizeText()：剥 U+200B–200F、U+202A–202E、U+2060–2064、FEFF；FF01–FF5E 转半角", "inject.零宽字符不绕过 等 4 条"],
           ["备注注入", "备注只作附言；“按备注找收款人”直接拒绝（memo_payee_rejected）", "guard.备注注入未动钱"],
           ["模型被诱导转账", "确认环节不经过模型；额度规则与频次规则独立于意图来源", "guard.攻击者收款人被拦"],
           ["越权改密/挂失", "红级只拦不做；改密明确告知“我不代您改”", "authz.改密判红、authz.正式挂失判红"],
           ["适配器塞非法参数", "页面与服务各做一次参数校验（整数分、人数≥2、对象名≤12 字）", "adapter.非法参数被拒"]],
          widths=[4.4, 8.6, 5.0], size=9)

    heading(doc, "四、敏感数据与审计")
    para(doc, "卡号在展示与审计中一律脱敏（只留后四位，格式 ****1234）；审计记录五要素：时间、用户原话、工具、"
              "脱敏参数、决策与 actor，可导出 JSONL 供复核；页面右侧可按“全部/已执行/待确认/已拦截”筛选。"
              "仓库内不含任何密钥，密钥只从环境变量读取，提交前由 check.py 扫描 sk- 形密钥与 16 位明文卡号。")

    heading(doc, "五、已知风险清单")
    table(doc, ["#", "风险", "影响", "现状与缓解", "遗留"],
          [["1", "双通道为同机简化：两端共享 shortHash 算法", "理论上老人端可自行算出回执", "演示限定；文档明示真实实现应由子女设备持私钥、老人端持公钥验签", "是"],
           ["2", "无真实 MFA", "红级仅有拦截与转人工，没有密码/短信验证通道", "拦截 + 人工受理号留痕", "是"],
           ["3", "无网关级限流", "仅业务频控（10 分钟 ≥3 次升红）", "渠道层可加令牌桶，未实现", "是"],
           ["4", "意图层覆盖有限", "长尾说法落到“没听懂”或走适配器", "34 条评测集 + 混合路由 + 低置信度反问", "部分"],
           ["5", "真实模型未联调", "fromLlm() 只有结构保证", "回放模式保证离线可演；有 key 即替换", "是"],
           ["6", "语音输入依赖浏览器识别", "Chrome Web Speech 需联网；不支持时明确提示", "文字链路始终可用，speak() 无引擎返回 false 不谎报", "是"],
           ["7", "无真实银行接口", "业务数据为 Mock", "工具层预留替换点；赛题不要求真实接口", "是"]],
          widths=[0.9, 4.6, 4.2, 6.4, 1.4], size=8.5)

    heading(doc, "六、验证证据")
    para(doc, f"断言总数 {N_ASSERT}，其中安全相关：inject.* 4 条、authz.* 3 条、block.* 6 条、adapter.* 4 条、"
              "audit.* 3 条、family.* 4 条、reach.* 5 条。已执行三次负向验证（拆掉防线确认断言会红），"
              "并记录在 CHANGELOG。提交前运行：python scripts/check.py && python scripts/smoke.py。")

    heading(doc, "七、提交前检查")
    table(doc, ["检查项", "命令/方式", "期望"],
          [["密钥与明文卡号", "python scripts/check.py", "FAIL 0 / WARN 0"],
           ["全部断言", "python scripts/smoke.py", f"PASS {N_ASSERT} / FAIL 0"],
           ["能力清单与代码一致", "smoke 的框架段", "PASS"],
           ["意图评测集", "smoke 的意图段", f"{N_CASES} 条全落对"],
           ["演示断网可跑", "断网后双击 app/index.html", "核心链路可用"]],
          widths=[4.6, 7.0, 6.4], size=9)

    path = OUT / "回声Agent-安全自评报告.docx"
    doc.save(path)
    return path


# ---------------------------------------------------------------- 答辩 PPT
def make_ppt(diagram):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    W = prs.slide_width

    def slide(title=None, kicker=None):
        s = prs.slides.add_slide(blank)
        bg = s.shapes.add_shape(1, 0, 0, W, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = PRGB(0xFF, 0xFF, 0xFF)
        bg.line.fill.background()
        if kicker:
            box = s.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.4))
            r = box.text_frame.paragraphs[0].add_run()
            r.text = kicker
            r.font.size = PPt(13)
            r.font.color.rgb = PRGB(0x9A, 0xA0, 0xA6)
        if title:
            box = s.shapes.add_textbox(Inches(0.8), Inches(0.85), Inches(11.7), Inches(0.9))
            r = box.text_frame.paragraphs[0].add_run()
            r.text = title
            r.font.size = PPt(30)
            r.font.bold = True
            r.font.color.rgb = PRGB(0x11, 0x12, 0x14)
            r.font.name = FONT
        return s

    def bullets(s, items, top=2.0, size=17, left=0.9, width=11.6, gap=0.62):
        box = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(0.6))
        tf = box.text_frame
        tf.word_wrap = True
        for i, it in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = PPt(10)
            r = p.add_run()
            r.text = it
            r.font.size = PPt(size)
            r.font.color.rgb = PRGB(0x2B, 0x2D, 0x31)
            r.font.name = FONT
        return tf

    def note(s, text):
        s.notes_slide.notes_text_frame.text = text

    # 1 封面
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(1, 0, 0, W, prs.slide_height)
    bg.fill.solid(); bg.fill.fore_color.rgb = PRGB(0x0B, 0x0E, 0x1A); bg.line.fill.background()
    t = s.shapes.add_textbox(Inches(0.9), Inches(2.3), Inches(11.5), Inches(1.2))
    r = t.text_frame.paragraphs[0].add_run(); r.text = "回声 Agent"
    r.font.size = PPt(54); r.font.bold = True; r.font.color.rgb = PRGB(0xFF, 0xFF, 0xFF); r.font.name = FONT
    t2 = s.shapes.add_textbox(Inches(0.95), Inches(3.5), Inches(11.5), Inches(0.6))
    r2 = t2.text_frame.paragraphs[0].add_run(); r2.text = "让每一次呼唤都有回应"
    r2.font.size = PPt(24); r2.font.color.rgb = PRGB(0xC9, 0xD0, 0xE0); r2.font.name = FONT
    t3 = s.shapes.add_textbox(Inches(0.95), Inches(4.6), Inches(11.5), Inches(0.5))
    r3 = t3.text_frame.paragraphs[0].add_run()
    r3.text = "2026 FinTechathon 深圳国际金融科技大赛 · 人工智能赛道"
    r3.font.size = PPt(14); r3.font.color.rgb = PRGB(0x8E, 0x98, 0xB0); r3.font.name = FONT
    note(s, "30 秒：我们做的是给老人用的银行智能体。一句话：让爸妈只动嘴，不动钱。")

    # 2 问题
    s = slide("银行对老人关上了门", "01 / 问题")
    bullets(s, ["他喊了一声“我卡里钱怎么少了”，没人应。",
                "手机银行有界面，但没有回应：菜单深、字小、看不懂。",
                "子女不敢给大额权限，老人又确实要办事。",
                "一次冒充客服的电话，可能就是一生积蓄。"], top=2.0, size=19)
    note(s, "45 秒：不要讲市场数据，讲一个具体的人。强调“不是不会用，是没人接住”。")

    # 3 用户与场景
    s = slide("六类业务，老人用得上的都覆盖", "02 / 场景")
    bullets(s, [f"转账 · 账单 · 订阅 · 卡片 · 联动 · 理财",
                f"共 {N_TOOLS} 个工具，三色分级（绿 {sum(1 for t in TOOLS.values() if t['level']=='green')} / 黄 {sum(1 for t in TOOLS.values() if t['level']=='yellow')} / 红 2）",
                "不是功能堆砌：每一项都过了“会不会动钱、可不可逆”的判断",
                "第二用户群：视障、听障、低识字人群，同一套语音架构"], top=1.9, size=18)
    note(s, "40 秒：强调我们只做六场景，但每个场景都能走完 解析→判定→确认→执行→审计。")

    # 4 架构图
    s = slide("一个内核，三个入口", "03 / 架构")
    s.shapes.add_picture(str(diagram), Inches(0.55), Inches(1.55), width=Inches(12.2))
    note(s, "60 秒：模型只决定“想办什么”，决定不了“能不能办”。这句话是本项目的技术立场。")

    # 5 三色判定
    s = slide("判断必须能解释：每条都给规则名和数字", "04 / 关键设计一")
    bullets(s, ["🟢 只读 → 自动执行；🟡 改数据且可逆 → 确认；🔴 不可逆或超限 → 拦截",
                f"{N_RULES} 条规则：金额、收款人、可逆性、频次",
                "例：单笔 5,000.00 元超过单笔限额 1,000.00 元（rule + 具体数字）",
                "判定只读状态，写入只发生在执行成功之后"], top=1.9, size=18)
    note(s, "60 秒：现场点一句超限转账，让评委看到两行原因，而不是一个红点。")

    # 6 双通道
    s = slide("家庭回声：动钱要两个人同意", "05 / 关键设计二")
    bullets(s, ["老人端只显示 6 位口令（2 分钟有效）",
                "家属端不显示操作内容，必须独立输入金额与收款人",
                "回执 = hash(收款人|金额|口令)，任一项不同即对不上",
                "连错 3 次作废，全程留痕"], top=1.9, size=18)
    note(s, "60 秒：强调“家属端刻意不显示详情”，防止老人被话术引导后转述。")

    # 7 止损优先
    s = slide("止损优先：能救的先救，不能救的才拦", "06 / 关键设计三")
    bullets(s, ["“我卡好像丢了” → 自动临时冻结（可逆、不打扰）",
                "冻结状态穿透到执行层：转账被拒，不只是文案",
                "“找到了” → 解冻，仍需确认",
                "“正式挂失” → 判红 + 给去处 + 转人工留痕"], top=1.9, size=18)
    note(s, "55 秒：这是最容易被记住的一段，也是“分级依据是可逆性而不是金额”的证明。")

    # 8 混合路由
    s = slide("不猜：规则先跑，长尾交给意图服务", "07 / 关键设计四")
    bullets(s, ["规则层：快、离线、可解释，命中直接进管线",
                "认不出 → 意图服务（模型或回放），四关校验：白名单/参数/置信度/超时",
                "置信度 < 0.6 → 反问，不许猜",
                "服务没起 → 静默回退，演示不崩"], top=1.9, size=18)
    note(s, "55 秒：现场演示“卡里还有多少”被正确理解，再演示“今天天气”不被瞎猜。")

    # 9 无障碍
    s = slide("看不清字的人，也能办成事", "08 / 无障碍")
    bullets(s, ["语音播报：金额读成中文（5,000.00 → 五千元）",
                "语音输入：不支持就明说，并给替代路径",
                "一句话确认 + 图标模式 + 大字模式",
                "电话模式：模拟来电，按 1 确认 / 2 取消，大额直接拒绝"], top=1.9, size=18)
    note(s, "50 秒：强调我们没有假装 TTS 一定可用，speak() 无引擎返回 false。")

    # 10 安全
    s = slide("模型被骗，也转不走钱", "09 / 安全")
    bullets(s, ["确认环节不经过模型；工具白名单 + 参数校验",
                "注入归一化：零宽、全角、备注塞指令都拦",
                "红级无实现体：判红的东西没有可调用的入口",
                "审计五要素 + 卡号脱敏 + 可筛选导出"], top=1.9, size=18)
    note(s, "50 秒：现场跑一次红队注入，让评委看到 audit 里的 blocked 记录。")

    # 11 验证
    s = slide(f"{N_ASSERT} 项断言，三次负向验证", "10 / 验证")
    bullets(s, [f"意图评测 {N_CASES} 条：宽规则抢答窄意图会立刻报红",
                "负向验证：拆掉防线，确认断言真的会红（归一化 / 给去处 / 推荐规则）",
                "双闸门：check.py（密钥、明文卡号）+ smoke.py（行为、框架、意图）",
                "全部可复现：断网、无 key 也能跑完整链路"], top=1.9, size=18)
    note(s, "45 秒：这一页是可信度来源。说“我们知道哪里没做到”。")

    # 12 局限
    s = slide("我们知道哪里还没做到", "11 / 局限与路线")
    bullets(s, ["真实模型未联调：本机无 key，只有结构保证",
                "回放仅 8 条且为手写样例",
                "语音输入依赖浏览器识别，需联网",
                "双通道为同机简化；无真实银行接口",
                "路线：接模型并录制回放 → 扩评测集到 200 条 → 接银行沙箱"], top=1.8, size=16.5)
    note(s, "40 秒：主动说不足，比被问出来强。最后一句收在“先兜住，再核身”。")

    path = OUT / "回声Agent-答辩材料.pptx"
    prs.save(path)
    return path


if __name__ == "__main__":
    diagram = make_diagram()
    print("diagram:", diagram)
    print("tech:", make_tech_doc(diagram))
    print("security:", make_security_doc())
    print("ppt:", make_ppt(diagram))
