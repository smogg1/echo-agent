/**
 * intent_service.mjs —— 意图服务（LLM 适配器 + 离线回放）
 *
 * 定位：规则层认不出的长尾句子，交给这里做"翻译"，只输出 {tool, params, confidence}。
 * 三条硬规则：
 *   ① 白名单：工具必须出现在 docs/capabilities.json 里，模型不能发明能力；
 *   ② 阈值：confidence < 0.6 交给调用方反问，不许猜；
 *   ③ 兜底：超时/解析失败/校验不过 → 返回 ok:false，调用方回退规则层。
 *
 * 运行：
 *   node scripts/intent_service.mjs 8791                 # 有回放，无 key 也能跑（演示用）
 *   BANK_LLM_API_KEY=sk-... node scripts/intent_service.mjs   # 真实模型（OpenAI 兼容）
 *
 * 说明：docs/llm_replay.jsonl 里的条目是**手写的样例**，用来代替真实录制；
 * 录制器（把真实响应落盘）在有 key 时可用，格式完全一致。
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(here, '..');
const CAPS = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs', 'capabilities.json'), 'utf8'));
const TOOLS = new Set(Object.keys(CAPS.tools));
const REPLAY_PATH = path.join(ROOT, 'docs', 'llm_replay.jsonl');

const PORT = Number(process.env.INTENT_PORT || process.argv[2] || 8791);
const KEY = process.env.BANK_LLM_API_KEY || '';
const BASE_URL = (process.env.BANK_LLM_BASE_URL || 'https://open.bigmodel.cn/api/paas/v4').replace(/\/$/, '');
const MODEL = process.env.BANK_LLM_MODEL || 'glm-4-flash';
const MIN_CONFIDENCE = 0.6;

const norm = (t) => String(t).replace(/\s+/g, '').trim();
const digest = (t) => crypto.createHash('sha1').update(norm(t)).digest('hex').slice(0, 12);

function loadReplay() {
  const map = new Map();
  try {
    const lines = fs.readFileSync(REPLAY_PATH, 'utf8').split('\n');
    for (const line of lines) {
      if (!line.trim()) continue;
      const row = JSON.parse(line);
      map.set(digest(row.text), row);
    }
  } catch (err) {
    // 没有回放文件也能跑：只是长尾句子会全部落到 clarfy
  }
  return map;
}
const REPLAY = loadReplay();

/** 参数类型校验：只认整数分、字符串对象名，别让模型塞进奇怪结构 */
function validate(obj) {
  if (!obj || typeof obj !== 'object') return null;
  const tool = String(obj.tool || '');
  if (!TOOLS.has(tool)) return null;                       // ① 白名单
  const params = obj.params && typeof obj.params === 'object' ? obj.params : {};
  const conf = Number(obj.confidence);
  if (!Number.isFinite(conf)) return null;
  if (conf < MIN_CONFIDENCE) return null;                  // ② 阈值：不猜

  const money = ['amountCents', 'totalCents', 'targetCents'];
  for (const k of money) {
    if (params[k] !== undefined) {
      if (!Number.isInteger(params[k]) || params[k] < 0) return null;
    }
  }
  if (params.people !== undefined && (!Number.isInteger(params.people) || params.people < 2)) return null;
  if (params.to !== undefined && (typeof params.to !== 'string' || params.to.length > 12)) return null;
  if (params.text !== undefined) delete params.text;

  return { tool, params, confidence: Math.round(conf * 100) / 100, source: obj.source || 'llm' };
}

function fromReplay(text) {
  const row = REPLAY.get(digest(text));
  if (!row) return null;
  return { tool: row.tool, params: row.params || {}, confidence: row.confidence, source: 'mock' };
}

function systemPrompt() {
  const lines = Object.entries(CAPS.tools).map(([name, meta]) =>
    `- ${name}（${meta.scene}，${meta.level}）`);
  return [
    '你是银行 Agent 的意图解析器。把用户的一句话翻译成一个工具调用。',
    '只能从下面的工具里选，不许发明：',
    ...lines,
    '输出严格 JSON：{"tool":"<工具名>","params":{...},"confidence":0~1}。',
    '金额单位一律是"分"（整数），例如 500 元 → 50000。',
    '不确定就降低 confidence（低于 0.6），或用 clarify。不要猜。',
  ].join('\n');
}

async function fromLlm(text) {
  if (!KEY) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 2500);
  try {
    const res = await fetch(`${BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${KEY}` },
      signal: ctrl.signal,
      body: JSON.stringify({
        model: MODEL,
        temperature: 0,
        messages: [{ role: 'system', content: systemPrompt() }, { role: 'user', content: text }],
        response_format: { type: 'json_object' },
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const raw = (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || '';
    const obj = JSON.parse(raw);
    return { tool: obj.tool, params: obj.params || {}, confidence: Number(obj.confidence), source: 'llm' };
  } catch (err) {
    return null;                                           // ③ 兜底：超时/解析失败都返回 null
  } finally {
    clearTimeout(timer);
  }
}

function reply(res, code, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*' });
  res.end(body);
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url.startsWith('/health')) {
    reply(res, 200, { ok: true, provider: KEY ? 'llm+mock' : 'mock', tools: TOOLS.size, replay: REPLAY.size });
    return;
  }
  if (req.method === 'POST' && req.url.startsWith('/intent')) {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (c) => { body += c; if (body.length > 4096) req.destroy(); });
    req.on('end', async () => {
      let text = '';
      try { text = String(JSON.parse(body || '{}').text || ''); } catch { text = ''; }
      if (!text) { reply(res, 200, { ok: false, reason: 'empty' }); return; }
      const attempts = KEY ? [fromLlm, async () => fromReplay(text)] : [async () => fromReplay(text)];
      for (const pick of attempts) {
        const raw = await pick(text);
        if (!raw) continue;
        const valid = validate(raw);
        if (valid) { reply(res, 200, { ok: true, ...valid }); return; }
        // 校验不过（含低置信度）：继续试下一个来源，最后交给调用方反问
        if (Number(raw.confidence) < MIN_CONFIDENCE) {
          reply(res, 200, { ok: false, reason: 'low_confidence', confidence: Number(raw.confidence), tool: raw.tool });
          return;
        }
      }
      reply(res, 200, { ok: false, reason: 'no_intent' });
    });
    return;
  }
  reply(res, 404, { ok: false, reason: 'not_found' });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`意图服务: http://127.0.0.1:${PORT}/intent  (provider=${KEY ? 'llm+mock' : 'mock'}, tools=${TOOLS.size})`);
});
