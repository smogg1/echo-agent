# app/ 里的三个文件怎么交互

> 一句话：**不是一个应用的三个零件，而是三个独立入口**，各自能单独跑；它们共用同一套“意图 → 判定 → 确认 → 执行 → 审计”的规则，但**不通过进程或网络通信**。

```
        ┌─────────────────────────────┐
        │  app/index.html   （老人端）  │
        │  84 KB 单文件，逻辑全内联      │
        │  意图 / 判定 / 确认 / 执行 / 审计 │
        └───────┬─────────────┬───────┘
                │             │
     口令 + 回执 │             │ 同一份代码被 Node 加载
     （人工传递）│             │ （scripts/webhook.mjs、intent_service）
                ▼             ▼
   ┌────────────────────┐  ┌──────────────────────────┐
   │ app/family.html    │  │ scripts/webhook.mjs      │
   │ （家属端，6 KB）     │  │ IM/APP 渠道替身，只转发    │
   │ 只算回执，不显示操作 │  └──────────────────────────┘
   └────────────────────┘
                ┌──────────────────────────────┐
                │ app/hello_agent.py（教学用）   │
                │ 独立命令行，演示 Function Calling │
                │ 与网页链路**没有**代码共享        │
                └──────────────────────────────┘
```

## 三个文件分别是什么

| 文件 | 是什么 | 和谁交互 | 怎么跑 |
|---|---|---|---|
| `index.html`（84 KB） | **老人端**。整个内核内联在这一个文件里：`parseIntent / evaluate / dispatchIntent / runTool / audit` | 浏览器、家属端（人工传口令与回执）、可选的本机意图服务 | 双击即开，断网可用 |
| `family.html`（6 KB） | **家属端**。只做一件事：用「口令 + 金额 + 收款人」算出 6 位回执 | 与老人端**不联网**，靠人念口令、人念回执 | 双击即开 |
| `hello_agent.py`（5 KB） | **命令行教学样例**。演示真实的 LLM Function Calling 与防幻觉 | 只与 LLM 接口（或 `--mock`）交互 | `python app/hello_agent.py --mock` |

## 一次转账，谁和谁说话

```
① 老人端：输入「转给小王 500 元」
        ↓ parseIntent → evaluate（判黄）
② 老人端：弹确认卡（含规则与阈值）
        ↓ 点「让家人确认」→ 屏幕上出现 6 位口令
③ 人：把口令念给家属（这一步没有网络，是人和人的交互）
        ↓
④ 家属端：输入 口令 + 500 + 小王 → 算出回执
        ↓ 人把回执念回给老人
⑤ 老人端：输入回执 → 校验通过 → runTool 执行 → audit 留痕
```

关键点：**②③④ 之间没有任何数据通道**。这是刻意的——家属端不显示操作详情，必须自己填金额与收款人，防的是“老人被话术引导后转述”。

## 那“内核只有一份”怎么保证

- `index.html` 是唯一实现；
- `scripts/page_sandbox.mjs` 把这个 HTML 里的 `<script>` 抽出来，在 Node 里跑同一个内核——
  渠道 `webhook.mjs` 与意图服务因此复用同一份逻辑，不存在两套规则；
- `scripts/smoke.py` 的「结构.两端回执算法一致」会比对 `index.html` 与 `family.html` 的
  `shortHash` 是否逐字相同，防止两边算法漂移。

## 为什么不做成“前端 + 后端”

1. **演示可靠性优先**：现场断网、评委机器没 Node、没装依赖，双击就能跑是硬要求；
2. **零依赖**：没有构建步骤，也没有 `npm install` 失败的可能；
3. **结构约束靠闸门而不是靠目录**：137 项断言 + 能力清单对账，比“目录看着复杂”更能证明工程质量。

## 服务形态（第四个入口，可选）

如果评委想看“系统化”的那面，用服务形态：

```powershell
node scripts/agent_server.mjs 8792
# 控制台：http://127.0.0.1:8792/server-client.html
# 接口：  POST /chat  POST /confirm  GET /audit
```

- `agent_server.mjs` 用 `page_sandbox.mjs` 把 **index.html 里的内核**加载进 Node 的 `vm` 跑，
  不是重写一遍——所以两种形态的判定结果逐字相同；
- 每个 `session` 一个独立沙箱，`STATE / pending / AUDIT_LOG` 互不影响；
- `app/server-client.html` 是**开发者视角**的控制台：左边对话，右边直接展示 `{level, hits, reply, pending, audit}`，
  方便评委核对“每一条判定都能说出规则名与数字”。

老人端 `index.html` 不受影响，仍然是断网双击可用的单文件版本。

## 快速自检

```powershell
python scripts/smoke.py     # 期望 PASS 136 / FAIL 0
```
