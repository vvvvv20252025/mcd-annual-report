#!/usr/bin/env bash
# 一键生成我的麦当劳年度报告
#
# 用法：
#   ./run.sh                # 真实模式（需先设置 MCD_MCP_TOKEN）
#   ./run.sh --demo         # 离线演示模式（无需 Token 与网络）
#   ./run.sh --demo "你的昵称"

set -e

PY="${PYTHON:-python3}"
NICKNAME="${2:-}"
MODE="${1:-}"

echo "╭─────────────────────────────────────────╮"
echo "│  麦麦年度报告 · McDonald's Annual Report  │"
echo "╰─────────────────────────────────────────╯"
echo

if [ "$MODE" = "--demo" ]; then
  echo "[1/4] 生成脱敏演示数据 ..."
  "$PY" scripts/make_demo_data.py
  "$PY" scripts/mcp_fetch.py --demo --out raw_orders.json
elif [ "$MODE" = "--help" ] || [ "$MODE" = "-h" ]; then
  echo "用法: ./run.sh [--demo] [昵称]"
  echo "  --demo   使用内置脱敏数据，无需 MCP Token 与网络"
  exit 0
else
  if [ -z "$MCD_MCP_TOKEN" ]; then
    echo "✗ 未设置环境变量 MCD_MCP_TOKEN"
    echo "  申请地址: https://open.mcd.cn/mcp"
    echo "  设置方式: export MCD_MCP_TOKEN=你的Token"
    echo "  或先看效果: ./run.sh --demo"
    exit 2
  fi
  echo "[1/4] 拉取麦当劳官方 MCP 数据 ..."
  "$PY" scripts/mcp_fetch.py --out raw_orders.json
fi

echo "[2/4] 聚合数据 ..."
if [ -n "$NICKNAME" ]; then
  "$PY" scripts/aggregate.py --in raw_orders.json --out report_data.json --nickname "$NICKNAME"
else
  "$PY" scripts/aggregate.py --in raw_orders.json --out report_data.json
fi

echo "[3/4] 渲染九屏报告 ..."
"$PY" scripts/render_report.py --in report_data.json --out "麦麦年度报告.html"

echo "[4/4] 完成 ✅"
echo
echo "报告已生成: 麦麦年度报告.html"
echo "双击即可打开，也可以直接转发分享。"
