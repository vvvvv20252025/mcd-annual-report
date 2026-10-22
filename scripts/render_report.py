#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_report.py — 把聚合数据渲染为自包含的九屏 HTML 报告

用法：
    python scripts/render_report.py --in report_data.json --out 麦麦年度报告.html

产物是单个 HTML 文件（CSS/JS/SVG 全内联），可直接双击打开、
发微信、发社交平台，无需任何服务器。
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TEMPLATE = os.path.join(REPO, "assets", "report_template.html")


def render(data, template):
    """把数据注入模板。"""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # 防止 JSON 中的 </script> 提前闭合脚本块
    payload = payload.replace("</", "<\\/")
    return template.replace("__REPORT_DATA__", payload)


def main():
    ap = argparse.ArgumentParser(description="渲染麦麦年度报告")
    ap.add_argument("--in", dest="inp", default="report_data.json")
    ap.add_argument("--out", default="麦麦年度报告.html")
    ap.add_argument("--template", default=TEMPLATE)
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print("找不到数据文件: %s（先运行 aggregate.py）" % args.inp, file=sys.stderr)
        return 1
    if not os.path.exists(args.template):
        print("找不到模板: %s（先运行 build_template.py）" % args.template, file=sys.stderr)
        return 1

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(args.template, "r", encoding="utf-8") as f:
        template = f.read()

    html = render(data, template)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print("报告已生成 -> %s" % args.out)
    print("  大小 %d 字节" % len(html.encode("utf-8")))
    print("  订单 %d 单 · 热量 %s kcal · 本命 %s"
          % (data.get("total", 0), format(data.get("kcal", 0), ","),
             (data.get("top5") or [{}])[0].get("name", "—")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
