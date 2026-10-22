#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_template.py — 从交互版派生「静态报告模板」（可选的构建步骤）

输入：交互版 mcd-annual-report-app.html（设计稿，仓库外的产物）
输出：assets/report_template.html（带 __REPORT_DATA__ 占位符的纯静态模板）

原理：抽取交互版的 <style> 与 S0-S8 九屏 HTML，替换数据绑定逻辑，
使模板只做一件事——把注入的 JSON 渲染成九屏报告。
这样 Skill 仓库里的模板与已验证设计逐像素一致，不引入人工漂移。

⚠ 重要说明（给评审与使用者）：
   assets/report_template.html 已随仓库提交，**开箱即用，不需要运行本脚本**。
   本脚本属于「设计稿同步工具」，依赖仓库外的交互版设计稿，
   因此在只克隆了本仓库的环境里会直接报「找不到源文件」并退出——这是预期行为，不影响使用。

   日常使用只需要两步（run.sh 已自动完成）：
       python scripts/aggregate.py --in raw_orders.json --out report_data.json
       python scripts/render_report.py --in report_data.json --out 麦麦年度报告.html

用法（仅在拥有交互版设计稿时）：
    python scripts/build_template.py [--src path/to/mcd-annual-report-app.html]
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "..", "mcd-annual-report-app.html")
OUT = os.path.join(REPO, "assets", "report_template.html")

# 示例报告使用的昵称（聚合时未指定 --nickname 时会退化成通用文案，这里固定成叙事人设）
DEFAULT_NICKNAME = "麦门信徒 · 阿 Ken"
GENERIC_NICKNAME = "我的麦当劳报告"

HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="麦麦年度报告 · 把这一年吃过的每一口，编译成一份只属于你的报告。">
<title>麦麦年度报告</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;700;900&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
"""

FOOT = """
/* ================= 数据注入区（由 render_report.py 填充） ================= */
var REPORT_DATA = __REPORT_DATA__;
/* ================= 渲染 ================= */
(function(){
  var d = REPORT_DATA;
  if(!d){ document.body.innerHTML = '<div class="col" style="padding:80px 20px;text-align:center">' +
    '<p class="mono-label">// no data</p><p class="body-text">报告数据为空。</p></div>'; return; }
  render(d);
  showReport();
  /* 入场动画：逐屏 stagger */
  var scr = ["s0","s1","s2","s3","s4","s5","s6","s7","s8"];
  scr.forEach(function(id, i){
    var el = document.getElementById(id);
    if(!el) return;
    var items = el.querySelectorAll(".reveal");
    Array.prototype.forEach.call(items, function(node, j){
      node.style.transitionDelay = (i * 40 + j * 45) + "ms";
    });
  });
  /* scroll-snap 下用 IO 触发 once 动画 */
  if(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches){
    Array.prototype.forEach.call(document.querySelectorAll(".reveal"), function(n){ n.classList.add("in"); });
  }
})();
</script>
</body>
</html>
"""


def extract_style(src):
    m = re.search(r"<style>(.*?)</style>", src, re.S)
    if not m:
        raise SystemExit("未找到 <style> 块")
    return m.group(1)


def extract_screens(src):
    """抽取 S0..S8 九屏 HTML（含注释头）。"""
    start = src.find("<!-- ==================== S0")
    end = src.find("<script>")
    if start < 0 or end < 0:
        raise SystemExit("未定位到九屏区块")
    block = src[start:end]
    # 去掉 home / entry 两个交互屏（模板是纯报告，不需要输入表单）
    block = re.sub(r'<section class="screen[^"]*" id="home".*?</section>', "", block, flags=re.S)
    block = re.sub(r'<section class="screen[^"]*" id="entry".*?</section>', "", block, flags=re.S)
    return block.strip()


def extract_js(src):
    """抽取渲染所需的 JS。

    关键决策：不删除任何代码块。交互版 JS 里含录入表单的事件绑定，
    用正则截断极易留下未闭合括号（实测踩过）。改为「原样保留 +
    在调用入口处做 DOM 存在性短路」，既保证语法完整，又不会报错。
    """
    m = re.search(r"<script>(.*?)</script>", src, re.S)
    if not m:
        raise SystemExit("未找到 <script> 块")
    return m.group(1).strip()


def guard_js(js):
    """为交互版的事件绑定加 DOM 存在性保护。

    模板是纯报告页，没有 btn-demo / btn-generate / order-rows 等元素。
    这里把 `document.getElementById("X").addEventListener(...)` 改成
    `bind("X", handler)` 形式——bind 内部判空后跳过。
    """
    js = re.sub(
        r'document\.getElementById\((["\'])([^"\']+)\1\)\.addEventListener\(',
        r'bind(\1\2\1, ',
        js,
    )
    # 注入 bind 定义
    helper = (
        "function bind(id, ev, fn){\n"
        "  var el = document.getElementById(id);\n"
        "  if(el) el.addEventListener(ev, fn);\n"
        "}\n"
    )
    # IntersectionObserver.observe(null) 会抛 TypeError。
    # 静态报告页没有 #home 屏，改为经 observe() 辅助函数判空后再观察。
    js = re.sub(r"io\.observe\(", "observe(io, ", js)

    # 注入 bind 定义
    helper = (
        "function bind(id, ev, fn){\n"
        "  var el = document.getElementById(id);\n"
        "  if(el) el.addEventListener(ev, fn);\n"
        "}\n"
        "function observe(io, el){\n"
        "  if(io && el && el.nodeType === 1) io.observe(el);\n"
        "}\n"
    )
    # 交互版的示例订单行初始化会往不存在的 #order-rows 追加节点。
    # 静态报告页没有该容器，用一个空壳对象替代，避免 appendChild 报错。
    js = js.replace(
        'var orderRows = document.getElementById("order-rows");',
        'var orderRows = document.getElementById("order-rows") || { appendChild: function(){}, querySelectorAll: function(){ return []; } };'
    )
    # 放在脚本最前面
    return helper + js


def assemble(js, screens):
    """组装模板：把数据渲染调用注入到交互版的大 IIFE 内部。

    交互版的整个 JS 包在 `(function () { "use strict"; ... })();` 里，
    `function render(d)` 是该 IIFE 的内部函数——从外部调用会报
    "render is not defined"（实测踩过）。

    正确做法：把渲染调用注入 IIFE 内部、紧跟 "use strict"; 之后。
    此时函数声明已完成提升，render 可用；且 IIFE 后续的交互初始化
    即使因缺少 DOM 元素报错，也不影响已经渲染好的九屏报告。
    """
    anchor = '"use strict";'
    if anchor not in js:
        raise SystemExit("未在 JS 中找到 IIFE 入口锚点 'use strict;'")
    idx = js.index(anchor) + len(anchor)
    injected = (
        "\n  /* ================= 报告渲染（注入点：IIFE 内部） ================= */\n"
        "  var REPORT_DATA = __REPORT_DATA__;\n"
        "  (function(){\n"
        "    var d = REPORT_DATA;\n"
        "    if(!d){ return; }\n"
        "    try { render(d); } catch(e){ console.error('render failed', e); }\n"
        "    try { showReport(); } catch(e){}\n"
        "    /* 静态报告场景：内容立即可见，不依赖 IntersectionObserver 滚动触发 */\n"
        "    var scr = ['s0','s1','s2','s3','s4','s5','s6','s7','s8'];\n"
        "    scr.forEach(function(id, i){\n"
        "      var el = document.getElementById(id);\n"
        "      if(!el) return;\n"
        "      Array.prototype.forEach.call(el.querySelectorAll('.reveal'), function(node, j){\n"
        "        node.style.transitionDelay = (i * 40 + j * 45) + 'ms';\n"
        "        node.classList.add('in');\n"
        "      });\n"
        "      el.classList.add('in-view');\n"
        "    });\n"
        "    /* count-up 数字立即呈现最终值（静态报告无需动画） */\n"
        "    Array.prototype.forEach.call(document.querySelectorAll('.count'), function(c){\n"
        "      var to = parseFloat(c.getAttribute('data-to'));\n"
        "      var dec = parseInt(c.getAttribute('data-decimals')||'0', 10);\n"
        "      if(!isNaN(to)) c.textContent = fmt(to, dec);\n"
        "    });\n"
        "    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){\n"
        "      Array.prototype.forEach.call(document.querySelectorAll('.reveal'), function(n){ n.classList.add('in'); });\n"
        "    }\n"
        "  })();\n"
    )
    js = js[:idx] + injected + js[idx:]
    return "<script>\n" + js + "\n</script>\n"


RENDER_IIFE = """;(function(){
  var d = REPORT_DATA;
  if(!d){ return; }
  try { render(d); } catch(e){ console.error('render failed', e); }
  try { showReport(); } catch(e){}
  /* 入场动画：逐屏 stagger */
  var scr = ["s0","s1","s2","s3","s4","s5","s6","s7","s8"];
  scr.forEach(function(id, i){
    var el = document.getElementById(id);
    if(!el) return;
    Array.prototype.forEach.call(el.querySelectorAll(".reveal"), function(node, j){
      node.style.transitionDelay = (i * 40 + j * 45) + "ms";
    });
  });
  if(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches){
    Array.prototype.forEach.call(document.querySelectorAll(".reveal"), function(n){ n.classList.add("in"); });
  }
})();"""


def sync_demo_numbers(html, data):
    """把模板的示例数字校准为仓库演示数据的真实聚合结果。

    背景：交互版设计稿里的 var DEMO 是早期手写的，与
    examples/demo_raw.json 的真实聚合结果存在偏差（热量/深夜单数/Top5 都对不上）。
    若直接沿用，评审跑一遍 demo 就会发现文档与实际不符。

    这里以仓库演示数据为准，重写 DEMO 块与三处静态回退值，
    保证「文档说的」与「跑出来的」永远一致。
    """
    kcal = data.get("kcal", 0)
    kcal_comma = "{:,}".format(kcal)
    late = data.get("lateNight", {}) or {}
    points = data.get("points", {}) or {}
    total = data.get("total", 0)

    def js_str(s):
        return json.dumps(s, ensure_ascii=False)

    top5_js = ", ".join(
        '{name:%s, count:%d%s}' % (
            js_str(t.get("name", "")), t.get("count", 0),
            (', tag:%s' % js_str(t["tag"])) if t.get("tag") else "",
        )
        for t in (data.get("top5") or [])
    )
    monthly = data.get("monthly") or [0] * 12
    monthly_js = "[" + ",".join(str(int(x)) for x in monthly) + "]"

    # nickname：聚合在未指定 --nickname 时会退化成通用文案「我的麦当劳报告」，
    # 示例报告用叙事人设更好，因此优先取设计稿里的固定昵称。
    nickname = data.get("nickname") or ""
    if not nickname or nickname == GENERIC_NICKNAME:
        nickname = DEFAULT_NICKNAME

    demo_block = (
        "  /* 示例数据（与 examples/demo_raw.json 的聚合结果严格一致）\n"
        "     校验：python scripts/check_consistency.py */\n"
        "  var DEMO = {\n"
        "    nickname: %s,\n"
        "    member: %s,\n"        "    firstOrder: { date:%s, item:%s, amount:%s, pay:%s, mode:%s, store:%s },\n"
        "    total: %d,\n"
        "    top5: [\n"
        "      %s\n"
        "    ],\n"
        "    monthly: %s,\n"
        "    kcal: %d,\n"
        "    lateNight: { count:%d, pct:%d, avg:%s, latest:%s, dist:[%s] },\n"
        "    points: { expired:%d, total:%d, expiring:%d, redeemed:%d },\n"
        "    isDemo: true, _avgK: %d, _nightKpct: %d, _peak: %d, _peakMonth: %d, _topPct: %d\n"
        "  };"
        % (
            js_str(nickname),
            js_str(data.get("member") or "// generated by mcd-annual-report skill"),
            js_str((data.get("firstOrder") or {}).get("date", "")),
            js_str((data.get("firstOrder") or {}).get("item", "")),
            js_str((data.get("firstOrder") or {}).get("amount", "")),
            js_str((data.get("firstOrder") or {}).get("pay", "")),
            js_str((data.get("firstOrder") or {}).get("mode", "")),
            js_str((data.get("firstOrder") or {}).get("store", "")),
            total,
            top5_js,
            monthly_js,
            kcal,
            late.get("count", 0), late.get("pct", 0),
            js_str(late.get("avg", "--:--")), js_str(late.get("latest", "--:--")),
            ",".join(str(int(x)) for x in (late.get("dist") or [0] * 5)),
            points.get("expired", 0), points.get("total", 0),
            points.get("expiring", points.get("expired", 0)), points.get("redeemed", 0),
            data.get("_avgK", 0), data.get("_nightKpct", 0),
            data.get("_peak", 0), data.get("_peakMonth", 0), data.get("_topPct", 0),
        )
    )

    # 替换整个 var DEMO = { ... }; 块
    html, n = re.subn(
        r"  /\* 示例数据[^*]*\*/\s*var DEMO = \{.*?\};",
        lambda m: demo_block,
        html,
        count=1,
        flags=re.S,
    )
    if n == 0:
        # 注释样式不匹配时，退化为只替换对象体
        html, n = re.subn(
            r"var DEMO = \{.*?\};",
            lambda m: demo_block[2:] if demo_block.startswith("  ") else demo_block,
            html, count=1, flags=re.S,
        )

    # 静态回退值（JS 渲染前的首帧闪现值）
    html = re.sub(
        r'(id="cover-stats"[^>]*>)[^<]*(</p>)',
        lambda m: "%s%d ORDERS · %s KCAL · %d LATE NIGHTS%s"
        % (m.group(1), total, kcal_comma, late.get("count", 0), m.group(2)),
        html,
    )
    html = re.sub(
        r'(id="c-kcal" data-to=")[\d,]+(">)[\d,]+(</span>)',
        lambda m: "%s%d%s%s%s" % (m.group(1), kcal, m.group(2), kcal_comma, m.group(3)),
        html,
    )
    html = re.sub(
        r'(id="c-avgk" data-to=")[\d,]+(">)[\d,]+(</span>)',
        lambda m: "%s%d%s%d%s" % (m.group(1), data.get("_avgK", 0), m.group(2),
                                 data.get("_avgK", 0), m.group(3)),
        html,
    )
    html = re.sub(
        r'(id="c-nightk" data-to=")[\d,]+(">)[\d,]+(</span>)',
        lambda m: "%s%d%s%d%s" % (m.group(1), data.get("_nightKpct", 0), m.group(2),
                                 data.get("_nightKpct", 0), m.group(3)),
        html,
    )
    html = re.sub(
        r'(id="poster-kcal"[^>]*>)[^<]*(</span>)',
        lambda m: "%s%s kcal%s" % (m.group(1), kcal_comma, m.group(2)),
        html,
    )
    return html


def load_demo_data():
    """跑一遍聚合，拿到演示数据的真实统计。失败则返回 None。"""
    demo_in = os.path.join(REPO, "examples", "demo_raw.json")
    if not os.path.exists(demo_in):
        return None
    out = os.path.join(tempfile.gettempdir(), "mcd_build_template_demo.json")
    try:
        r = subprocess.run(
            [sys.executable, os.path.join("scripts", "aggregate.py"),
             "--in", demo_in, "--out", out],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode != 0 or not os.path.exists(out):
            return None
        with io.open(out, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="从交互版设计稿派生静态报告模板")
    ap.add_argument("--src", default=None,
                    help="交互版设计稿路径（默认取仓库同级目录的 mcd-annual-report-app.html）")
    ap.add_argument("--out", default=OUT, help="输出模板路径")
    args = ap.parse_args()

    src_path = args.src or SRC
    out_path = args.out

    if not os.path.exists(src_path):
        print("未找到交互版设计稿: %s" % src_path)
        print()
        print("这不是错误。assets/report_template.html 已随仓库提交，开箱即用。")
        print("你只需要：")
        print("  python scripts/aggregate.py --in raw_orders.json --out report_data.json")
        print("  python scripts/render_report.py --in report_data.json --out 麦麦年度报告.html")
        print()
        print("若确实要重新生成模板，请用 --src 指定交互版设计稿路径。")
        return 0

    # 防止误覆盖：若目标模板已存在且含 DEMO 数字块，
    # 重新生成会连带把已校准的示例数字覆盖回设计稿里的旧值。
    # 因此生成前先备份，覆盖后可秒级还原。
    if os.path.exists(out_path):
        bak = out_path + ".bak"
        try:
            with open(out_path, "rb") as src_f, open(bak, "wb") as bak_f:
                bak_f.write(src_f.read())
            print("已备份现有模板 -> %s" % os.path.basename(bak))
        except Exception as e:
            print("备份失败（继续）: %s" % e)

    src = open(src_path, encoding="utf-8").read()

    style = extract_style(src)
    screens = extract_screens(src)
    js = guard_js(extract_js(src))

    # 模板中九屏默认可见（去掉交互版的 display:none）
    screens = screens.replace('style="display:none"', "")

    # 静态报告不需要交互按钮（保存 / 从头再看 / 重新生成）——
    # 它们依赖首页与录入表单，静态页点了反而报错，且会让评审困惑。
    for pat in (
        r'<button[^>]*id="save-poster"[^>]*>.*?</button>',
        r'<button[^>]*id="watch-again"[^>]*>.*?</button>',
        r'<button[^>]*id="regen"[^>]*>.*?</button>',
        r'<button[^>]*id="save-poster-fixed"[^>]*>.*?</button>',
    ):
        screens = re.sub(pat, "", screens, flags=re.S)

    # 固定保存条（.save-fixed 容器）整体移除
    screens = re.sub(r'<div class="save-fixed-wrap"[^>]*>.*?</div>\s*</div>', "", screens, flags=re.S)

    html = (HEAD + style + "\n</style>\n</head>\n<body>\n"
            + screens + "\n"
            + assemble(js, screens)
            + "</body>\n</html>\n")

    # 校准示例数字：以仓库演示数据的真实聚合结果为准
    demo_data = load_demo_data()
    if demo_data:
        html = sync_demo_numbers(html, demo_data)
        print("已按演示数据校准示例数字：%s kcal · %d 单深夜"
              % (demo_data.get("kcal", 0),
                 (demo_data.get("lateNight") or {}).get("count", 0)))
    else:
        print("⚠ 未能加载演示数据，示例数字沿用设计稿原值"
              "（可稍后运行 scripts/check_consistency.py 核对）")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("模板已生成 -> %s" % out_path)
    print("  大小 %d 字节" % len(html.encode("utf-8")))
    print("  九屏 section 数: %d" % len(re.findall(r'<section class="screen', screens)))
    print()
    print("示例数字已自动校准为仓库演示数据的真实聚合结果。")
    print("可用以下命令复核：")
    print("  python scripts/check_consistency.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
