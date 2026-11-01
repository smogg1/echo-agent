# 回声 Agent · Echo Agent

> 让每一次呼唤都有回应 —— 面向银发人群的受控语音银行智能体
> 2026（第八届）FinTechathon 深圳国际金融科技大赛 · 微众银行金融科技大学生挑战赛 · 人工智能赛道

## 这是什么

老人说一句话就能办银行业务（查账、转账、挂失、退订），**动钱必须过"家庭回声"**——子女远程授权，老人始终是账户主体。

三层架构，也是三层叙事：

| 层 | 谁回应 | 技术落点 | 对应评分 |
|---|---|---|---|
| 技术回声 | Agent 回应老人 | 意图理解 → 多步规划 → 调工具办成事 | 任务完成率 40% |
| 家庭回声 | 子女回应授权 | 双通道确认：老人复述 + 家属授权码 | 安全合规性 30% |
| 社会回声 | 银行回应异常 | 沉默检测、超时升级、审计可回放 | 创新与体验 30% |

**只做两处护城河**：① 可解释的三色判定（每条都能报出 rule + 阈值）；② 双通道授权契约。

## 架构：一个内核，三个入口

```
老人端 index.html ─┐
家属端 family.html ─┼─→ 意图 → 判定 → 确认 → 执行 → 审计（同一份内核）
渠道 webhook.mjs ──┘
```

模型只决定"想办什么"，决定不了"能不能办"：判定、确认、执行、审计全在代码里。
分层、不变量、能力矩阵见 [00-架构.md](docs/00-架构.md)；能力清单见 [capabilities.json](docs/capabilities.json)，由 `smoke.py` 与代码逐项对账。

## 目录

```
echo-agent/
├── app/
│   ├── index.html        # 老人端：三色判定 + 确认兜底 + 家属授权 + 审计导出（单文件）
│   ├── family.html       # 家属端：只收口令/金额/收款人，回一个 6 位回执
│   └── hello_agent.py    # 命令行最小闭环：ReAct 循环 + 工具调用（--mock 可断网排练）
├── scripts/
│   ├── check.py          # 静态闸门：密钥 / 明文卡号 / 占位实现
│   ├── smoke.py          # 冒烟：mock 链路 + 前端结构 + 45 项行为断言
│   ├── js_harness.mjs    # 在 Node 里跑 index.html 的脚本做断言（--demo 可打印界面文本）
│   ├── page_sandbox.mjs  # 单测与渠道共用的最小 DOM 环境
│   ├── fx_server.py      # 本地假汇率 + 静态站点（关掉 = 演示降级）
│   ├── webhook.mjs       # 渠道：POST /webhook → {level, reply, audit}
│   └── snapshot.py       # 版本快照（本机没装 git，先用它替代 commit）
├── docs/
│   ├── 00-架构.md         # 一个内核三个入口：分层、不变量、能力矩阵
│   ├── capabilities.json  # 能力清单（单一事实源，与代码对账）
│   ├── 环境检查清单.md
│   ├── 05-常见坑.md
│   ├── 演示脚本-Day1.md
│   └── 演示脚本-Day2.md
├── .releases/            # snapshot.py 产出，不进版本库
├── CHANGELOG.md
└── README.md
```

## 怎么跑

```powershell
# 1) 静态闸门（密钥、明文卡号、占位实现）
python scripts/check.py -v

# 2) 冒烟（含 Node 行为单测；找不到 node 会跳过并 WARN）
python scripts/smoke.py

# 3) 形态一：命令行 Agent（断网排练）
python app/hello_agent.py --mock
python app/hello_agent.py          # 真实大模型，需三个环境变量（见下）

# 4) 形态二：老人端网页 + 家属端网页（双通道）
start app/index.html
start app/family.html

# 5) 外部服务：本地假汇率（关掉就是"外部服务挂掉"的降级演示）
python scripts/fx_server.py        # http://127.0.0.1:8787/index.html

# 6) 渠道：IM / APP 网关的替身
node scripts/webhook.mjs 8790
curl.exe -s -X POST http://127.0.0.1:8790/webhook -H "content-type: application/json" -d "{\"text\":\"查一下余额\"}"
```

真实大模型模式只从环境变量读配置，源码里不出现任何 key：

```powershell
$env:BANK_LLM_API_KEY  = "sk-..."                                  # 只在本机设置，绝不入库
$env:BANK_LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
$env:BANK_LLM_MODEL    = "glm-4-flash"
```

## 验收标准（三天版）

| 门禁 | 命令 | 现在 |
|---|---|---|
| 静态闸门通过 | `python scripts/check.py` | ✅ |
| 冒烟通过 | `python scripts/smoke.py` | ✅ 136 项 |
| 架构与代码一致 | `capabilities.json` ↔ `TOOL_IMPL`/`PERMISSIONS`/`RULES` | ✅ |
| 三场景可演示 | 手工：账单 / 转账 / 订阅 | ✅ |
| 越权全判红 | 手工：改密 / 挂失 / 大额 | ✅ |
| 注入被拦 | 备注藏指令 / 攻击者收款人 | ✅ |
| 双通道可走通 | `index.html` + `family.html` 两窗口 | ✅ |
| 外部服务可降级 | 停 `fx_server.py` 后问汇率 | ✅ |
| 渠道返回 level | `curl POST /webhook` | ✅ |
| 断网可跑 | 拔网线跑 mock + 网页 | ✅ |

## 已知债务（Day 3 清单）

- 语音层未接：演示是文字输入，真实产品应是 ASR + TTS；补齐条件是拿到可离线运行的语音包或允许联网，这一点会如实写进自述；
- 家属端与老人端在同一台机器上共享算法，**真实实现应由子女设备持有私钥**（当前是为了离线演示而简化）；
- 会话状态在内存里，刷新即重置；跨设备持久化需要后端与账户体系；
- 只有 mock 数据，没有接真实银行接口（赛题不要求，但落地时是第一道坎）。

## 版本

| 版本 | 内容 |
|---|---|
| v0.0.1 | Day 0：骨架、闸门、冒烟、离线可跑 |

> 本机未安装 git。`scripts/snapshot.py` 会生成 `.releases/<版本>/` 快照 + `MANIFEST.sha256`，并用文件 SHA256 判定"有没有改动"，等价于一次 commit。装好 git 后可 `git init` 直接接管。











