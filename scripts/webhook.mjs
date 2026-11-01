/**
 * webhook.mjs —— 渠道适配器（IM / APP 网关的替身）
 *
 * 纪律：渠道层**不做任何业务判定**，只做三件事——收文本、交给页面同一份逻辑、回 JSON。
 * 这样"网页能办的事，IM 里也能办"，而且不存在两套规则漂移。
 *
 * 用法：
 *   node scripts/webhook.mjs 8790
 *   curl -s -X POST http://127.0.0.1:8790/webhook -H "content-type: application/json" \
 *        -d "{\"text\":\"查一下余额\"}"
 *   → {"level":"green","reply":"...","audit":{...}}
 */
import http from 'node:http';
import vm from 'node:vm';
import { createSandbox, loadPageScript } from './page_sandbox.mjs';

const PORT = Number(process.env.WEBHOOK_PORT || process.argv[2] || 8790);
const pageScript = loadPageScript('index.html');
const { sandbox } = createSandbox();
vm.createContext(sandbox);
vm.runInContext(pageScript, sandbox, { timeout: 5000 });

/** 把一句话交给页面逻辑，取回等级、回复文本与最后一条审计 */
function run(text) {
  const code = `(() => {
    const t = ${JSON.stringify(text)};
    const intent = parseIntent(t);
    const verdict = intent ? evaluate(intent) : null;
    handleUserText(t);
    const kids = document.getElementById('messages').children;
    const agent = kids.filter((k) => String(k.className).includes('agent')).pop();
    const html = agent ? String(agent.innerHTML) : '';
    // 只取气泡里的正文，不要把下面的「Agent」标签也带回去
    const bubble = html.match(/<div class="bubble">([\\s\\S]*?)<\\/div>/);
    const body = bubble ? bubble[1] : html;
    return JSON.stringify({
      level: verdict ? verdict.level : 'unknown',
      reply: body.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim(),
      audit: AUDIT_LOG[AUDIT_LOG.length - 1] || null,
    });
  })()`;
  return vm.runInContext(code, sandbox, { timeout: 5000 });
}

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url.startsWith('/webhook')) {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 8192) req.destroy();
    });
    req.on('end', () => {
      let text = '';
      try {
        text = String(JSON.parse(body || '{}').text || '');
      } catch {
        text = '';
      }
      let out;
      try {
        out = run(text);
      } catch (err) {
        out = JSON.stringify({ level: 'error', reply: String(err) });
      }
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      res.end(out);
    });
    return;
  }
  res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
  res.end('POST /webhook {"text":"查一下余额"}');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`webhook 渠道已起: http://127.0.0.1:${PORT}/webhook`);
  console.log('示例: curl -s -X POST http://127.0.0.1:%d/webhook -H "content-type: application/json" -d "{\\"text\\":\\"查一下余额\\"}"', PORT);
});
