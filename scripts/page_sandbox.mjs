/**
 * page_sandbox.mjs —— 把 app/index.html 的脚本跑起来所需的最小环境（零依赖）
 *
 * 为什么要单独抽出来：行为单测（js_harness）和渠道（webhook）要跑同一份业务代码。
 * 复制两份 DOM 桩一定会漂移，所以这里做唯一实现。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
export const APP_DIR = path.join(here, '..', 'app');

/** 抽出页面里最后一个内联 <script>（我们所有逻辑都在这一个块里） */
export function loadPageScript(file = 'index.html') {
  const html = fs.readFileSync(path.join(APP_DIR, file), 'utf8');
  const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)];
  if (blocks.length === 0) throw new Error(`${file} 没有内联 script`);
  return blocks[blocks.length - 1][1];
}

function makeEl(tag = 'div') {
  const el = {
    tagName: tag, id: '', className: '', innerHTML: '', textContent: '', value: '',
    style: {}, dataset: {}, children: [], parentNode: null,
    scrollTop: 0, scrollHeight: 0, checked: false, disabled: false,
    appendChild(c) { el.children.push(c); c.parentNode = el; return c; },
    removeChild(c) { el.children = el.children.filter((x) => x !== c); return c; },
    remove() { if (el.parentNode) el.parentNode.removeChild(el); },
    addEventListener() {}, removeEventListener() {},
    setAttribute() {}, getAttribute() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; },
    classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    focus() {}, click() {},
  };
  return el;
}

export function createSandbox() {
  const registry = new Map();
  const documentStub = {
    getElementById(id) {
      if (!registry.has(id)) { const el = makeEl(); el.id = id; registry.set(id, el); }
      return registry.get(id);
    },
    createElement(tag) { return makeEl(tag); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
    body: makeEl('body'),
  };

  const sandbox = {
    document: documentStub,
    window: {},
    console: { log() {}, warn() {}, error() {} },
    alert() {},
    URL: { createObjectURL: () => 'blob:stub', revokeObjectURL() {} },
    Blob: class Blob { constructor(parts) { this.parts = parts; } },
    setTimeout: () => 0,
    clearTimeout() {},
    setInterval: () => 0,
    clearInterval() {},
  };
  return { sandbox, documentStub, registry };
}
