# -*- coding: utf-8 -*-
"""
模块四/五演示：Hello-World 银行 Agent —— 最小闭环
链路：用户一句话 → 意图理解 → 工具调用（Mock 数据）→ 自然语言回复

金额一律整数分（cents），源码里不出现浮点金额，只在显示时转成元。

用法：
  python app/hello_agent.py          # 真实大模型（需环境变量 BANK_LLM_API_KEY）
  python app/hello_agent.py --mock   # 无网排练模式（内置剧本模拟大模型返回）

真实模式默认走 OpenAI 兼容接口（GLM / DeepSeek / Qwen 均可）：
  export BANK_LLM_API_KEY=sk-xxx
  export BANK_LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4   # 以 GLM 为例
  export BANK_LLM_MODEL=glm-4-flash
"""
import json
import os
import sys

YUAN = 100


def fmt(cents: int) -> str:
    """整数分 → 元，只在显示时使用。"""
    return "{}.{:02d}".format(cents // YUAN, cents % YUAN)


# ---------------- Mock 银行数据（真实项目中替换为银行接口） ----------------
ACCOUNTS = {"我": 10000 * YUAN}
CONTACTS = {"小王": "6222****1234"}
BILLS = [
    {"item": "视频会员订阅", "cents": 25 * YUAN},
    {"item": "午餐", "cents": 3250},
    {"item": "打车", "cents": 18 * YUAN},
]


def check_balance():
    """查询我的账户余额"""
    return {"balance_cents": ACCOUNTS["我"]}


def transfer(payee: str, amount_cents: int):
    """向指定收款人转账（Mock，不真实扣款）"""
    if payee not in CONTACTS:
        return {"ok": False, "msg": f"查无收款人：{payee}"}
    if not isinstance(amount_cents, int) or amount_cents <= 0:
        return {"ok": False, "msg": "金额必须是正整数分"}
    if amount_cents > ACCOUNTS["我"]:
        return {"ok": False, "msg": "余额不足"}
    ACCOUNTS["我"] -= amount_cents
    return {
        "ok": True,
        "msg": f"已向 {payee}（{CONTACTS[payee]}）转账 {fmt(amount_cents)} 元",
        "balance_cents": ACCOUNTS["我"],
    }


def list_bills():
    """列出本月账单"""
    total = sum(b["cents"] for b in BILLS)
    return {"bills": BILLS, "total_cents": total}


TOOLS = {
    "check_balance": check_balance,
    "transfer": transfer,
    "list_bills": list_bills,
}

# 工具定义（JSON Schema）—— 告诉模型「你有哪些手」
TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "check_balance", "description": "查询我的账户余额", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "transfer", "description": "向指定收款人转账，金额单位为分",
                                      "parameters": {"type": "object",
                                                     "properties": {"payee": {"type": "string", "description": "收款人姓名"},
                                                                    "amount_cents": {"type": "integer", "description": "金额（分），必须是正整数"}},
                                                     "required": ["payee", "amount_cents"]}}},
    {"type": "function", "function": {"name": "list_bills", "description": "列出本月账单", "parameters": {"type": "object", "properties": {}}}},
]

SYSTEM_PROMPT = "你是一名银行 AI 智能体。用户用自然语言提出银行业务请求，你通过调用工具完成，不要编造余额或交易结果。"


# ---------------- 真实大模型模式 ----------------
def run_real(user_text: str):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["BANK_LLM_API_KEY"],
                    base_url=os.environ.get("BANK_LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"))
    model = os.environ.get("BANK_LLM_MODEL", "glm-4-flash")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}]
    # Agent 循环：模型可能连续多轮调工具
    while True:
        resp = client.chat.completions.create(model=model, messages=messages, tools=TOOL_SCHEMAS)
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            return msg.content
        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments or "{}")
            print(f"  [工具调用] {name}({args})")
            result = TOOLS[name](**args)
            print(f"  [工具返回] {result}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)})


# ---------------- Mock 排练模式（无 API key 也能录课排练） ----------------
def run_mock(user_text: str):
    print("  [意图理解] 识别到「转账」意图，提取参数：payee=小王, amount_cents=10000（即 100.00 元）")
    result = transfer(payee="小王", amount_cents=100 * YUAN)
    print("  [工具调用] transfer({'payee': '小王', 'amount_cents': 10000})")
    print(f"  [工具返回] {result}")
    return f"已完成转账：向小王转账 100.00 元，当前余额 {fmt(result['balance_cents'])} 元。"


if __name__ == "__main__":
    text = "转给小王 100 块"
    print(f"用户：{text}")
    reply = run_mock(text) if "--mock" in sys.argv else run_real(text)
    print(f"Agent：{reply}")
