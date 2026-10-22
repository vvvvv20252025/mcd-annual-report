#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_consistency.py — 自检：文档里的数字是否与真实跑出来的数据一致

背景（真实踩过的坑）：
    README 首屏写「113,400 KCAL · 47 LATE NIGHTS」，
    但仓库 demo 实跑是「103,705 kcal · 50 单深夜」。
    评审只要跑一遍 `./run.sh --demo` 就会发现数字对不上——这是最容易翻车的低级错误。

本脚本做三件事：
    1. 跑通 demo 管线，拿到真实聚合结果；
    2. 把结果里的关键数字，逐个回查 README / 模板 / Skill 文档；
    3. 任何一处对不上就以非零码退出。

用法：
    python scripts/check_consistency.py
退出码：
    0 = 全部一致
    1 = 存在不一致（请按提示修正）
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# 参与检查的文档
DOCS = [
    "README.md",
    "MCP_INTEGRATION.md",
    "assets/report_template.html",
]

# 不该出现在文档里的编造数字（曾经写错过的地方）
FORBIDDEN = [
    ("113,400", "旧版手写的热量值，与 demo 实跑 103,705 不符"),
    ("113400", "旧版手写的热量值，与 demo 实跑 103705 不符"),
    ("158 个餐品", "营养表数量未核实，demo 实跑为 24 项"),
    ("158 款餐品", "营养表数量未核实，demo 实跑为 24 项"),
]


def run(args):
    p = subprocess.run([sys.executable] + args, cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8")
    return p


def aggregate_demo():
    """跑通 demo 管线，返回聚合结果。"""
    demo_in = os.path.join(REPO, "examples", "demo_raw.json")
    if not os.path.exists(demo_in):
        r = run([os.path.join("scripts", "make_demo_data.py")])
        if r.returncode != 0:
            print("生成演示数据失败:\n%s" % (r.stderr or r.stdout))
            return None

    out = os.path.join(tempfile.gettempdir(), "mcd_consistency_check.json")
    r = run([os.path.join("scripts", "aggregate.py"), "--in", demo_in, "--out", out])
    if r.returncode != 0:
        print("聚合失败:\n%s" % (r.stderr or r.stdout))
        return None
    if not os.path.exists(out):
        print("聚合未产出结果文件")
        return None
    with io.open(out, encoding="utf-8") as f:
        return json.load(f)


def check_numbers(data):
    """检查文档中的关键数字是否与实跑结果一致。"""
    problems = []

    total = data.get("total")
    kcal = data.get("kcal")
    late = data.get("lateNight", {}).get("count")
    nutrition = data.get("_nutritionCount")
    peak_month = data.get("_peakMonth")
    peak = data.get("_peak")

    # 期望出现的字符串形式
    kcal_comma = "{:,}".format(kcal)
    kcal_plain = str(kcal)

    # README 首屏必须写实际热量与实际深夜单数
    readme = ""
    p = os.path.join(REPO, "README.md")
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as f:
            readme = f.read()

    if readme:
        if kcal_comma not in readme:
            problems.append("README.md 未出现实际热量 %s kcal" % kcal_comma)
        if not re.search(r"\b%d LATE NIGHTS\b" % late, readme):
            problems.append("README.md 未出现实际深夜单数 %d LATE NIGHTS" % late)
        if not re.search(r"\b%d ORDERS\b" % total, readme):
            problems.append("README.md 未出现实际订单数 %d ORDERS" % total)

    # 模板的静态回退值必须与实跑一致（否则 JS 渲染前会闪现旧数字）
    tpl_path = os.path.join(REPO, "assets", "report_template.html")
    if os.path.exists(tpl_path):
        with io.open(tpl_path, encoding="utf-8") as f:
            tpl = f.read()
        if 'id="c-kcal" data-to="%s"' % kcal_plain not in tpl:
            problems.append("模板 c-kcal 的 data-to 应为 %s" % kcal_plain)
        if "%s LATE NIGHTS" % late not in tpl:
            problems.append("模板 cover-stats 应含 %d LATE NIGHTS" % late)
        m = re.search(r"kcal:\s*(\d+)", tpl)
        if m and m.group(1) != kcal_plain:
            problems.append("模板 DEMO.kcal 应为 %s，实际 %s" % (kcal_plain, m.group(1)))

    # 演示数据跑出的关键指标，用于人工确认
    print("  实际聚合结果：")
    print("    订单 %s 单 · 商品 %s 件" % (total, data.get("itemCount")))
    print("    热量 %s kcal · 深夜 %s 单 · 营养表 %s 项"
          % (kcal_comma, late, nutrition))
    print("    峰值月 %s 月（%s 单）· 本命 %s"
          % (peak_month, peak,
             (data.get("top5") or [{}])[0].get("name", "—")))
    return problems


def check_forbidden():
    """检查文档里是否残留编造的数字。"""
    problems = []
    for rel in DOCS:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        with io.open(p, encoding="utf-8") as f:
            text = f.read()
        for token, reason in FORBIDDEN:
            if token in text:
                problems.append("%s 仍含「%s」——%s" % (rel, token, reason))
    return problems


def main():
    print("=" * 62)
    print(" 一致性自检：文档数字 vs demo 实跑结果")
    print("=" * 62)
    print()

    data = aggregate_demo()
    if data is None:
        print("自检中止：无法得到聚合结果")
        return 1

    problems = []
    problems += check_numbers(data)
    problems += check_forbidden()

    print()
    if problems:
        print("发现 %d 处不一致：" % len(problems))
        for i, pb in enumerate(problems, 1):
            print("  %d. %s" % (i, pb))
        print()
        print("请修正后重跑本脚本。")
        return 1

    print("全部一致 ✅  README / 模板 / 演示数据的数字对得上。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
