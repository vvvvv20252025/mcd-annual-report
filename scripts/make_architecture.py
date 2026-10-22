#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Skill 数据流架构图（draw.io mxGraph XML）+ 导出 PNG。

设计约束（踩坑记录）：
1. 所有 mxCell 必须位于 <root> 内，否则渲染为空白页；
2. 每个 cell 必须有唯一 id —— 用显式 id 参数，不依赖全局计数器；
3. style 中的 fontFamily 含逗号，必须用 &quot; 包裹，否则 style 串解析错位；
4. edge 的 source/target 必须引用真实存在的 id。
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)
DRAWIO = "D:/Software/Draw.io/draw.io.exe"

BG = "#FAF7F5"
WINE = "#6E1E2C"
GOLD = "#C9962F"
CARD = "#FFFFFF"
BORDER = "#E7DED6"
MUTED = "#8F7C74"
GREEN = "#3F7D58"
ORANGE = "#C2410C"
SLATE = "#8A7A72"

FONT = "PingFang SC,Microsoft YaHei,Noto Sans SC,sans-serif"
MONO = "JetBrains Mono,Consolas,monospace"
FS = "&quot;%s&quot;" % FONT
MS = "&quot;%s&quot;" % MONO

CELLS = []


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def vbox(cid, x, y, w, h, title, sub="", fill=CARD, stroke=BORDER,
         tcolor="#2B2226", size=15, bold=False, mono=False, sw=1):
    """矩形节点。value 用纯文本 + &#10; 换行，避免 HTML 富文本解析差异。"""
    fam = MS if mono else FS
    val = esc(title)
    if sub:
        val += "&#10;" + esc(sub)
    CELLS.append(
        '<mxCell id="%s" value="%s" style="rounded=1;arcSize=8;whiteSpace=wrap;html=1;'
        'fillColor=%s;strokeColor=%s;strokeWidth=%d;align=center;verticalAlign=middle;'
        'spacing=10;fontSize=%d;fontFamily=%s;fontColor=%s;shadow=0;" vertex="1" parent="1">'
        '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
        % (cid, val, fill, stroke, sw, size, fam, tcolor, x, y, w, h)
    )
    return cid


def label(cid, x, y, w, h, text, size=13, color=MUTED, mono=False, bold=False,
          align="left"):
    fam = MS if mono else FS
    weight = "700" if bold else "400"
    CELLS.append(
        '<mxCell id="%s" value="%s" style="text;html=1;align=%s;verticalAlign=middle;'
        'fontSize=%d;fontFamily=%s;fontStyle=%s;fontColor=%s;shadow=0;" vertex="1" '
        'parent="1"><mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/>'
        '</mxCell>' % (cid, esc(text), align, size, fam, weight, color, x, y, w, h)
    )
    return cid


def band(cid, x, y, w, h, title, fill, tcolor="#FFFFFF"):
    val = "&#10;".join(esc(t) for t in title.split("\n"))
    CELLS.append(
        '<mxCell id="%s" value="%s" style="rounded=1;arcSize=6;whiteSpace=wrap;html=1;'
        'fillColor=%s;strokeColor=%s;strokeWidth=1;fontSize=13;fontFamily=%s;'
        'fontStyle=1;fontColor=%s;align=center;verticalAlign=middle;shadow=0;" '
        'vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="%d" height="%d" '
        'as="geometry"/></mxCell>' % (cid, val, fill, fill, FS, tcolor, x, y, w, h)
    )
    return cid


def edge(eid, src, dst, text="", color=GOLD, w=2, dashed=False):
    dash = "dashed=1;" if dashed else ""
    CELLS.append(
        '<mxCell id="%s" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;'
        'strokeColor=%s;strokeWidth=%d;%sendArrow=block;endFill=1;fontSize=11;'
        'fontFamily=%s;fontColor=%s;labelBackgroundColor=%s;" edge="1" parent="1" '
        'source="%s" target="%s"><mxGeometry relative="1" as="geometry"/></mxCell>'
        % (eid, color, w, dash, MS, MUTED, BG, src, dst)
    )
    if text:
        CELLS.append(
            '<mxCell id="%s_l" value="%s" style="edgeLabel;html=1;align=center;'
            'verticalAlign=middle;fontSize=11;fontFamily=%s;fontColor=%s;'
            'labelBackgroundColor=%s;" edge="1" parent="%s" connectable="0">'
            '<mxGeometry x="-0.2" relative="1" as="geometry"/></mxCell>'
            % (eid, esc(text), MS, MUTED, BG, eid)
        )
    return eid


def build():
    label("title", 60, 30, 900, 40, "麦麦年度报告 · Skill 数据流", size=26,
          color=WINE, bold=True)
    label("subtitle", 60, 72, 900, 24,
          "// MCP Streamable HTTP · 本地聚合 · 单文件 HTML 产出",
          size=13, mono=True)

    # L1
    y1 = 116
    band("l1b", 60, y1, 130, 96, "L1\n用户层", SLATE)
    vbox("u1", 236, y1, 240, 44, "用户", "WorkBuddy / Cursor / Claude")
    vbox("u2", 520, y1, 250, 44, "触发语", "「生成我的麦麦年度报告」", mono=True)
    edge("e_u", "u1", "u2", color=SLATE, w=1)

    # L2
    y2 = 248
    band("l2b", 60, y2, 130, 170, "L2\nSkill 编排", WINE)
    vbox("s1", 236, y2, 190, 44, "SKILL.md", "工作流定义",
         fill="#FBF4F5", stroke=WINE, tcolor=WINE)
    vbox("s2", 456, y2, 210, 44, "mcp_fetch.py", "MCP 客户端 · 纯标准库",
         fill="#FBF4F5", stroke=WINE, tcolor=WINE, mono=True)
    vbox("s3", 696, y2, 190, 44, "aggregate.py", "聚合引擎",
         fill="#FBF4F5", stroke=WINE, tcolor=WINE, mono=True)
    vbox("s4", 916, y2, 200, 44, "render_report.py", "HTML 渲染器",
         fill="#FBF4F5", stroke=WINE, tcolor=WINE, mono=True)
    edge("e_us", "u1", "s1", "调用", color=WINE)
    edge("e_s1", "s1", "s2", "1", color=WINE)
    edge("e_s2", "s2", "s3", "2", color=WINE)
    edge("e_s3", "s3", "s4", "3", color=WINE)

    # L3
    y3 = 452
    band("l3b", 60, y3, 130, 196, "L3\n麦当劳\n官方 MCP", GOLD)
    CELLS.append(
        '<mxCell id="mframe" value="" style="rounded=1;arcSize=8;whiteSpace=wrap;html=1;'
        'fillColor=#FDF8EC;strokeColor=%s;strokeWidth=1;shadow=0;" vertex="1" parent="1">'
        '<mxGeometry x="236" y="%d" width="160" height="196" as="geometry"/></mxCell>'
        % (GOLD, y3)
    )
    label("murl", 240, y3 + 8, 152, 20, "mcp.mcd.cn", size=12, color=WINE, mono=True,
          align="center", bold=True)
    tools = ["order-list", "mall-order-list", "list-nutrition-foods",
             "query-my-account", "query-my-coupons", "query-my-prizes"]
    for i, t in enumerate(tools):
        CELLS.append(
            '<mxCell id="t%d" value="%s" style="rounded=1;arcSize=14;whiteSpace=wrap;'
            'html=1;fillColor=%s;strokeColor=%s;strokeWidth=1;fontSize=11;'
            'fontFamily=%s;fontColor=%s;align=center;verticalAlign=middle;shadow=0;" '
            'vertex="1" parent="1"><mxGeometry x="246" y="%d" width="140" height="21" '
            'as="geometry"/></mxCell>'
            % (i + 1, esc(t), CARD, GOLD, MS, WINE, y3 + 36 + i * 23)
        )
    label("mnote", 236, y3 + 200, 160, 18, "Bearer Token · 600 req/min", size=10,
          mono=True, align="center")
    edge("e_s2m", "s2", "t1", "tools/call", color=GOLD)

    # L4
    y4 = 690
    band("l4b", 60, y4, 130, 130, "L4\n数据与\n产物", "#D9C08A", tcolor=WINE)
    vbox("d1", 236, y4, 200, 52, "raw_orders.json", "脱敏后的原始返回", mono=True)
    vbox("d2", 466, y4, 220, 52, "report_data.json", "Top5 / 曲线 / 热量 / 积分",
         mono=True)
    vbox("d3", 716, y4, 240, 52, "麦麦年度报告.html", "自包含单文件 · 九屏",
         fill="#FBF4F5", stroke=WINE, tcolor=WINE, mono=True)
    vbox("d4", 986, y4, 170, 52, "分享截图", "每屏值得晒",
         fill="#FBF4F5", stroke=WINE, tcolor=WINE)
    edge("e_sd", "s3", "d1", "落盘", color=WINE)
    edge("e_d1", "d1", "d2", "聚合", color=WINE)
    edge("e_d2", "d2", "d3", "注入", color=WINE)
    edge("e_d3", "d3", "d4", color=WINE, w=1)

    # 右侧泳道
    CELLS.append(
        '<mxCell id="side" value="" style="rounded=1;arcSize=8;whiteSpace=wrap;html=1;'
        'fillColor=#F7F2EE;strokeColor=%s;strokeWidth=1;shadow=0;" vertex="1" parent="1">'
        '<mxGeometry x="1180" y="248" width="290" height="290" as="geometry"/></mxCell>'
        % BORDER
    )
    label("stitle", 1200, 264, 250, 26, "隐私与降级边界", size=14, color=WINE, bold=True)
    rows = [
        ("Token", "仅从环境变量读取，不写入代码", GOLD),
        ("数据流向", "本地处理，不经第三方服务器", GOLD),
        ("真实订单", "raw_orders.json 不入库", ORANGE),
        ("演示模式", "--demo 无需 Token 与网络", GREEN),
        ("仓库内容", "全部为虚构脱敏数据", GREEN),
    ]
    for i, (k, v, c) in enumerate(rows):
        yy = 300 + i * 46
        label("sk%d" % i, 1200, yy, 250, 18, k, size=11, color=c, mono=True, bold=True)
        label("sv%d" % i, 1200, yy + 18, 250, 30, v, size=12)

    edge("e_side1", "s2", "sk0", color=BORDER, w=1, dashed=True)
    edge("e_side2", "d1", "sk2", color=BORDER, w=1, dashed=True)

    label("legend", 60, 856, 1000, 24,
          "■ 官方 MCP Tool    ■ 数据文件    ■ 产出物    ──▶  数据流向",
          size=12, mono=True)

    body = "".join(CELLS)
    root = ('<mxGraphModel dx="1400" dy="900" grid="0" gridSize="10" guides="1" '
            'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            'pageWidth="1500" pageHeight="880" math="0" shadow="0">'
            '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + body +
            '</root></mxGraphModel>')
    return ('<mxfile host="app.diagrams.net" type="device">'
            '<diagram id="mcd-arch" name="架构图">' + root + '</diagram></mxfile>')


def main():
    xml = build()
    out_xml = os.path.join(OUT_DIR, "docs", "architecture.drawio")
    os.makedirs(os.path.dirname(out_xml), exist_ok=True)
    with open(out_xml, "w", encoding="utf-8") as f:
        f.write(xml)
    print("XML 已生成 -> %s (%d bytes, %d cells)"
          % (out_xml, len(xml.encode("utf-8")), len(CELLS)))

    if not os.path.exists(DRAWIO):
        print("未找到 draw.io CLI:", DRAWIO)
        return 1
    out_png = os.path.join(OUT_DIR, "docs", "architecture.png")
    r = subprocess.run([DRAWIO, "-x", "-f", "png", "--width", "2400", "-b", "20",
                        "-o", out_png, out_xml],
                       capture_output=True, text=True, timeout=240)
    print("draw.io exit:", r.returncode)
    if r.stderr.strip():
        print("  stderr:", r.stderr.strip()[:300])
    if os.path.exists(out_png):
        print("PNG 已生成 -> %s (%.1f KB)" % (out_png, os.path.getsize(out_png) / 1024))
        return 0
    print("PNG 导出失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
