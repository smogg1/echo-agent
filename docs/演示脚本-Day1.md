# Day 1 演示脚本（自测 / 录屏都能用）

> 三条路，任选一条。全部**不需要网络、不需要 API key**。

## 路线 A：看网页（最直观，30 秒）

打开 `app/index.html`（双击即可，单文件、零依赖）。

按顺序在输入框里敲下面 6 句，对照"应该看到"：

| # | 输入 | 应该看到 |
|---|---|---|
| 1 | `帮我看看余额` | 🟢 自动执行，余额 10,000.00 元，卡号 `****1234` |
| 2 | `转给小王 500 元` | 🟡 确认卡：`irreversible_op｜该操作不可逆…`；点「确认执行」后余额 9,500.00 元 |
| 3 | `转给小王 5000 元` | 🔴 拦截，两行原因：`单笔 5,000.00 元超过单笔限额 1,000.00 元`／`日累计…` |
| 4 | `转给小王五千块` | 口语金额也认：判为同一笔 5,000.00 元的超限拦截 |
| 5 | `转给小李 100 元` | 🔴 `payee_first_time｜收款人「小李」不在通讯录，首次转账需人工核验` |
| 6 | `转给小王` → 再输入 `500` | 多轮：先追问金额，补一句「500」后才弹确认卡 |

右侧「审计日志」实时滚出 `工具 → 决策`；点 **⬇ 导出 audit.log** 会下载一份 JSONL，共 5 要素（时间、原话、工具、脱敏参数、决策）。

注：第 2 步确认后余额会变，想重来就刷新页面。

## 路线 B：看终端里的界面文本（不用开浏览器）

```powershell
cd D:\WorkSoftware\dsh\echo-agent
node scripts/js_harness.mjs --demo
```

它会把「转账 500 → 确认 → 转 5000 → 按备注转账」四步的界面文本原样打出来，包括每张卡片上的规则名与 detail。这是**同一份页面代码**跑出来的，不是另写一段文案。

## 路线 C：看命令行 Agent（证明"真调了工具"）

```powershell
cd D:\WorkSoftware\dsh\echo-agent
python app/hello_agent.py --mock
```

应该看到三行关键输出：`[意图理解]…` → `[工具调用] transfer(...)` → `[工具返回] {'ok': True, 'balance_cents': 990000}`。
**余额是工具算出来的，不是模型编的**——这行就是防幻觉的证据。

## 看代码的话，改动的三处

| 位置 | 内容 |
|---|---|
| `app/index.html` | `LIMITS`（阈值）、`evaluate()` + `RULES`（7 条规则）、`parseIntent()`（口语 / 手机号 / 多轮槽位 / 备注拒绝）、`addToolCard()`（显示 rule｜detail） |
| `app/hello_agent.py` | 金额改整数分（`balance_cents`），工具 schema 用 `amount_cents` |
| `scripts/js_harness.mjs` | 32 项行为断言，Day 1 新增 14 项 |

## 自己验一遍闸门

```powershell
cd D:\WorkSoftware\dsh\echo-agent
python scripts/check.py    # 期望：FAIL 0  WARN 0
python scripts/smoke.py    # 期望：PASS 32  FAIL 0
```

## 版本快照在哪

`.releases\v0.0.1\`（Day 0）与 `.releases\v0.1.0\`（Day 1），每个目录里都有 `MANIFEST.sha256`。
想看这两天到底改了什么：

```powershell
python scripts/snapshot.py v0.1.1 --diff
```

会打印相对 v0.1.0 的 `+新增 / ~修改 / -删除` 清单。
