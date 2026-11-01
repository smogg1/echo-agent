/**
 * agent_server.mjs —— 服务形态：静态站点 + /chat 接口 + 会话确认 + 审计查询
 *
 * 关键点：服务端**不重写业务逻辑**，而是用 page_sandbox 把 app/index.html 里的
 * 内核脚本加载进 Node 的 vm 里跑。因此老人端（单文件）与服务形态共用同一份
 * 意图 / 判定 / 确认 / 执行 / 审计代码，不存在两套规则。
 *
 * 运行：
 *   node scripts/agent_server.mjs 8792
 *   → 浏览器打开 http://127.0.0.1:8792/            （老人端，单文件版）
 *   → 浏览器打开 http://127.0.0.1:8792/server-client.html （服务形态控制台）
 *
 * 接口：
 *   POST /chat    {"text":"转给小王 100 元","session":"demo"}
 *                 → {level, hits, reply, pending, audit}
 *   POST /confirm {"approve":true,"session":"demo"}
 *                 → {reply, audit}
 *   GET  /audit?session=demo   → JSONL（每行一条审计）
 *   GET  /health               → {ok, sessions}
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createSandbox, loadPageScript, APP_DIR } from './page_sandbox.mjs';

const PORT = Number(process.env.AGENT_PORT || process.argv[2] || 8792);
const PAGE_SCRIPT = loadPageScript('index.html');
const SESSIONS = new Map();

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".md": "text/markdown; charset=utf-8",
};

/** 一个会话 = 一个独立的内核沙箱（STATE / pending / AUDIT_LOG 都隔离） */
function session(id) {
  if (SESSIONS.has(id)) return SESSIONS.get(id);
  const { sandbox } = createSandbox();
  vm.createContext(sandbox);
  vm.runInContext(PAGE_SCRIPT, sandbox, { timeout: 5000 });
  SESSIONS.set(id, sandbox);
  return sandbox;
}

function chat(sandbox, text) {
  const code = `(() => {
    const t = ${JSON.stringify(text)};
    resolveIntent(t);                    // 先解析一次，仅为拿到判定结果
    handleUserText(t);                   // 真正走管线（含确认卡、审计）
    const rec = AUDIT_LOG[AUDIT_LOG.length - 1] || null;
    const verdict = parseIntent(t) ? evaluate(parseIntent(t)) : null;
    return JSON.stringify({
      level: verdict ? verdict.level : "unknown",
      hits: verdict ? verdict.hits : [],
      reply: pending ? pending.ask : LAST_REPLY,
      pending: pending ? { tool: pending.tool, params: pending.params } : null,
      audit: rec,
    });
  })()`;
  return JSON.parse(vm.runInContext(code, sandbox, { timeout: 5000 }));
}

function confirm(sandbox, approve) {
  const code = `(() => {
    if (!pending) return JSON.stringify({ ok: false, reason: "no_pending" });
    onConfirm(${approve ? "true" : "false"});
    return JSON.stringify({ ok: true, reply: LAST_REPLY, audit: AUDIT_LOG[AUDIT_LOG.length - 1] || null });
  })()`;
  return JSON.parse(vm.runInContext(code, sandbox, { timeout: 5000 }));
}

function auditJsonl(sandbox) {
  return vm.runInContext("AUDIT_LOG.map((r) => JSON.stringify(r)).join('\\n')", sandbox);
}

function json(res, code, payload) {
  const body = typeof payload === "string" ? payload : JSON.stringify(payload);
  res.writeHead(code, {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (c) => { body += c; if (body.length > 8192) req.destroy(); });
    req.on("end", () => resolve(body));
  });
}

function serveStatic(res, urlPath) {
  const rel = urlPath === "/" ? "index.html" : urlPath.replace(/^\/+/, "");
  const target = path.join(APP_DIR, rel);
  if (!target.startsWith(APP_DIR)) { json(res, 403, { ok: false, reason: "forbidden" }); return; }
  fs.readFile(target, (err, buf) => {
    if (err) { json(res, 404, { ok: false, reason: "not_found", path: rel }); return; }
    res.writeHead(200, { "content-type": MIME[path.extname(target)] || "application/octet-stream" });
    res.end(buf);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (req.method === "GET" && url.pathname === "/health") {
    json(res, 200, { ok: true, sessions: SESSIONS.size, tools: Object.keys({}).length });
    return;
  }

  if (req.method === "GET" && url.pathname === "/audit") {
    const id = url.searchParams.get("session") || "demo";
    res.writeHead(200, { "content-type": "application/x-ndjson; charset=utf-8" });
    res.end(auditJsonl(session(id)));
    return;
  }

  if (req.method === "POST" && url.pathname === "/chat") {
    const body = await readBody(req);
    let text = "";
    let id = "demo";
    try {
      const parsed = JSON.parse(body || "{}");
      text = String(parsed.text || "");
      id = String(parsed.session || "demo");
    } catch { /* 空请求按空文本处理 */ }
    if (!text) { json(res, 200, { ok: false, reason: "empty_text" }); return; }
    try {
      json(res, 200, { ok: true, ...chat(session(id), text) });
    } catch (err) {
      json(res, 500, { ok: false, reason: "kernel_error", detail: String(err).slice(0, 120) });
    }
    return;
  }

  if (req.method === "POST" && url.pathname === "/confirm") {
    const body = await readBody(req);
    let approve = false;
    let id = "demo";
    try {
      const parsed = JSON.parse(body || "{}");
      approve = parsed.approve === true;
      id = String(parsed.session || "demo");
    } catch { /* 默认拒绝 */ }
    json(res, 200, { ...confirm(session(id), approve) });
    return;
  }

  if (req.method === "GET") { serveStatic(res, url.pathname); return; }

  json(res, 404, { ok: false, reason: "not_found" });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`服务形态: http://127.0.0.1:${PORT}/`);
  console.log(`控制台:   http://127.0.0.1:${PORT}/server-client.html`);
  console.log(`接口:     POST /chat  POST /confirm  GET /audit  GET /health`);
});
