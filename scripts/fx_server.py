#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fx_server.py —— 本地「假汇率服务 + 静态页面」，同一个源，省掉 CORS

为什么需要它：赛题要证明"系统能接外部服务"，但演示又不许依赖外网。
所以外部服务跑在本机、可随时关掉——关掉就是最好的降级演示。

用法：
  python scripts/fx_server.py          # 起在 http://127.0.0.1:8787
  浏览器打开 http://127.0.0.1:8787/index.html
  Ctrl+C 停掉 = 演示"外部服务挂掉"，刷新页面后问汇率应看到降级话术

接口：
  GET /fx?from=USD&to=CNY  →  {"from":"USD","to":"CNY","rate":7.12}
"""
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent.parent / "app"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787

RATES = {
    ("USD", "CNY"): 7.12,
    ("HKD", "CNY"): 0.92,
    ("EUR", "CNY"): 7.78,
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/fx":
            q = parse_qs(url.query)
            src = (q.get("from", ["USD"])[0]).upper()
            dst = (q.get("to", ["CNY"])[0]).upper()
            rate = RATES.get((src, dst))
            if rate is None:
                self._json({"error": f"unsupported pair {src}/{dst}"}, 404)
                return
            self._json({"from": src, "to": dst, "rate": rate}, 200)
            return
        super().do_GET()

    def _json(self, payload: dict, code: int) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 安静一点，别刷屏
        pass


if __name__ == "__main__":
    print(f"静态站点 + 汇率服务: http://127.0.0.1:{PORT}/index.html")
    print(f"  接口自测:          http://127.0.0.1:{PORT}/fx?from=USD&to=CNY")
    print("  停掉本进程即等于「外部服务挂掉」，用来演示 2 秒超时降级。")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
