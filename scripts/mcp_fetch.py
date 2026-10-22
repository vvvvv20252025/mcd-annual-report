#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_fetch.py — 麦当劳官方 MCP Server 客户端（纯标准库实现）

不依赖 requests / httpx / mcp 等第三方包，仅用 urllib。
实现 MCP Streamable HTTP 传输协议：
  POST https://mcp.mcd.cn
  Headers:
    Authorization: Bearer <MCP_TOKEN>
    Content-Type: application/json
    Accept: application/json, text/event-stream

用法：
    export MCD_MCP_TOKEN=xxxxx
    python scripts/mcp_fetch.py --out raw_orders.json
    python scripts/mcp_fetch.py --out raw_orders.json --demo   # 无 Token 也能跑通
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2024-11-05"

# 本 Skill 实际使用的工具
TOOLS_USED = [
    "order-list",
    "mall-order-list",
    "list-nutrition-foods",
    "query-my-account",
    "query-my-coupons",
    "query-my-prizes",
]


class McDMCPClient:
    """麦当劳官方 MCP Server 的最小可用客户端。"""

    def __init__(self, token, url=MCP_URL, timeout=30):
        if not token:
            raise ValueError("缺少 MCP Token。请在 https://open.mcd.cn/mcp 申请，并设置环境变量 MCD_MCP_TOKEN")
        self.token = token
        self.url = url
        self.timeout = timeout
        self.session_id = None
        self._id = 0

    # ---------- 底层 HTTP ----------

    def _headers(self):
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer %s" % self.token,
            "User-Agent": "mcd-annual-report-skill/1.0",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                raw = resp.read().decode("utf-8", errors="replace")
                ctype = resp.headers.get("Content-Type", "")
                return self._parse(raw, ctype)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            if e.code == 401:
                raise RuntimeError("MCP Token 无效或已过期（401）。请重新在 open.mcd.cn/mcp 申请。")
            if e.code == 429:
                raise RuntimeError("触发限流（429）。官方限制每 Token 每分钟 600 次请求，请降低频率后重试。")
            raise RuntimeError("MCP 请求失败 HTTP %s: %s" % (e.code, detail))
        except urllib.error.URLError as e:
            raise RuntimeError("无法连接麦当劳 MCP Server（%s）。请检查网络或代理设置。" % e.reason)

    @staticmethod
    def _parse(raw, ctype):
        """兼容两种响应：SSE (text/event-stream) 与纯 JSON。"""
        raw = raw.strip()
        if not raw:
            return None
        if "text/event-stream" in ctype or raw.startswith("event:") or raw.startswith("data:"):
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk and chunk != "[DONE]":
                        try:
                            return json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _next_id(self):
        self._id += 1
        return self._id

    # ---------- MCP 协议 ----------

    def initialize(self):
        """建立会话（必须先于任何 tools/call）。"""
        result = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-annual-report", "version": "1.0.0"},
            },
        })
        # 通知 initialized（无需等待响应）
        try:
            self._post({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })
        except Exception:
            pass
        return result

    def call_tool(self, name, arguments=None):
        """调用一个 MCP Tool，返回解析后的数据部分（失败时返回带 _error 的字典）。"""
        result = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })
        if result is None:
            return {"_error": "empty response"}
        if "error" in result:
            return {"_error": result["error"]}

        res = result.get("result", {})
        # MCP 标准返回是 content 数组（text 类型）
        if isinstance(res, dict) and res.get("content"):
            texts = []
            for item in res["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            merged = "\n".join(texts)
            try:
                return json.loads(merged)
            except json.JSONDecodeError:
                try:
                    return json.loads(merged[merged.index("{"):merged.rindex("}") + 1])
                except (ValueError, json.JSONDecodeError):
                    return merged
        return res


def fetch_all(token, timeout=30, verbose=True):
    """拉取本 Skill 需要的全部数据。"""
    client = McDMCPClient(token, timeout=timeout)
    if verbose:
        print("[mcp] 初始化会话 ...", file=sys.stderr)
    client.initialize()

    raw = {"_fetched_at": None, "_tools": {}}
    for tool in TOOLS_USED:
        if verbose:
            print("[mcp] 调用 %s ..." % tool, file=sys.stderr)
        try:
            raw["_tools"][tool] = client.call_tool(tool)
        except RuntimeError as e:
            raw["_tools"][tool] = {"_error": str(e)}
        # 官方限流 600 次/分钟；留出余量，串行调用即可
    return raw


def main():
    ap = argparse.ArgumentParser(description="麦当劳官方 MCP 数据拉取")
    ap.add_argument("--out", default="raw_orders.json", help="输出 JSON 路径")
    ap.add_argument("--demo", action="store_true", help="使用内置脱敏样例数据，不请求网络")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    if args.demo:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        demo_path = os.path.join(here, "examples", "demo_raw.json")
        if not os.path.exists(demo_path):
            print("找不到样例数据: %s" % demo_path, file=sys.stderr)
            return 1
        with open(demo_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("已写入样例数据 -> %s" % args.out)
        return 0

    token = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if not token:
        print("错误：未设置环境变量 MCD_MCP_TOKEN。", file=sys.stderr)
        print("  申请地址: https://open.mcd.cn/mcp", file=sys.stderr)
        print("  用法: export MCD_MCP_TOKEN=你的Token  (Windows: set MCD_MCP_TOKEN=你的Token)", file=sys.stderr)
        return 2

    try:
        data = fetch_all(token, timeout=args.timeout)
    except RuntimeError as e:
        print("拉取失败: %s" % e, file=sys.stderr)
        return 3

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("已写入 -> %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
