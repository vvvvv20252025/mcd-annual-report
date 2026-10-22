#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aggregate.py — 把麦当劳 MCP 原始返回聚合成年度报告数据

输入：raw_orders.json（mcp_fetch.py 的产出）
输出：report_data.json（渲染器直接消费）

设计要点：真实 MCP 返回的字段命名在不同版本间可能变化，
因此所有取值都走「候选键列表 + 模糊匹配」，不依赖单一字段名。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

# ---------- 字段候选键 ----------

DATE_KEYS = ["createTime", "create_time", "orderTime", "order_time", "orderDate",
             "order_date", "createdAt", "created_at", "time", "date", "timestamp",
             "orderCreateTime", "createDate"]
ITEM_KEYS = ["itemName", "item_name", "productName", "product_name", "name", "foodName",
             "mealName", "goodsName", "item", "meal", "product"]
COUNT_KEYS = ["quantity", "count", "num", "amount", "qty", "numQuantity", "itemCount"]
PRICE_KEYS = ["price", "amount", "totalPrice", "total_price", "payAmount", "totalAmount"]
KCAL_KEYS = ["energy", "calorie", "calories", "kcal", "heat", "energyValue", "energyKcal"]
TOTAL_KEYS = ["totalPoints", "total_points", "accumulatedPoints", "accumulatePoints",
              "total", "points", "availablePoints", "usablePoints"]
EXPIRE_KEYS = ["expiredPoints", "expired_points", "expiringPoints", "willExpirePoints",
               "expiring_points", "aboutToExpirePoints"]
AVAIL_KEYS = ["availablePoints", "usablePoints", "currentPoints", "balance", "points"]
FROZEN_KEYS = ["frozenPoints", "frozen_points", "lockedPoints"]
REDEEM_KEYS = ["redeemedPoints", "redeemed_points", "usedPoints", "exchangedPoints"]
PAY_KEYS = ["payType", "pay_type", "paymentType", "payMethod", "paymentMethod", "payName"]
MODE_KEYS = ["orderType", "order_type", "deliveryType", "fulfillmentType", "dineType", "type"]
STORE_KEYS = ["storeName", "store_name", "restaurantName", "shopName", "store"]

# 餐品名归一化：去掉规格后缀与空白，便于 Top5 聚合
SUFFIX_RE = re.compile(r"[（(【\[].*?[)）】\]]")


def pick(d, keys, default=None):
    """按候选键顺序取值；全部缺失时返回 default。

    会向下穿透一层 `data` / `result` 包装——官方 MCP 返回普遍是
    {"code":0,"data":{...}} 结构，字段都在 data 里。
    """
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    # 退化为模糊匹配（忽略大小写/下划线）
    norm = {re.sub(r"[_\-]", "", str(k).lower()): v for k, v in d.items()}
    for k in keys:
        nk = re.sub(r"[_\-]", "", k.lower())
        if nk in norm and norm[nk] not in (None, ""):
            return norm[nk]
    # 向下穿透一层常见包装
    for wrapper in ("data", "result", "account", "info"):
        sub = d.get(wrapper)
        if isinstance(sub, dict):
            got = pick(sub, keys, None)
            if got is not None:
                return got
    return default


def parse_dt(value):
    """把各种时间格式解析为 (year, month, day, hour, minute, sortkey)。

    支持：毫秒/秒时间戳、ISO 字符串、"2025-01-03 08:42"、"2025/01/03"、
    "202501030842"、带毫秒的紧凑数字串等。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:      # 毫秒
            ts /= 1000.0
        if ts < 1e8:       # 太小，不像时间戳
            return None
        import time
        lt = time.localtime(ts)
        return (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, ts)

    s = str(value).strip()
    if not s:
        return None

    # 纯数字：时间戳 或 紧凑日期
    if s.replace(".", "", 1).isdigit():
        if "." in s:
            try:
                return parse_dt(float(s))
            except (ValueError, TypeError):
                pass
        if len(s) >= 11:
            try:
                return parse_dt(int(s))
            except (ValueError, TypeError):
                pass
        m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2}))?", s)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            h = int(m.group(4) or 0)
            mi = int(m.group(5) or 0)
            return (y, mo, d, h, mi, float("%s%02d%02d%02d%02d" % (y, mo, d, h, mi)))
        return None

    # ISO / 常规字符串
    m = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?"
                  r"(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h = int(m.group(4) or 0)
        mi = int(m.group(5) or 0)
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return (y, mo, d, h, mi, float("%s%02d%02d%02d%02d" % (y, mo, d, h, mi)))
    return None


def find_items(node, out):
    """递归找出所有看起来像「订单」或「订单行」的字典节点。"""
    if isinstance(node, dict):
        name = pick(node, ITEM_KEYS)
        has_name = isinstance(name, str) and name.strip()
        # 订单行：有名且有数量/价格
        if has_name and (pick(node, COUNT_KEYS) is not None or pick(node, PRICE_KEYS) is not None):
            out.append(node)
            return
        # 订单：有时间且可能内含 items 列表
        for k, v in node.items():
            if isinstance(v, list):
                for it in v:
                    find_items(it, out)
            elif isinstance(v, dict):
                find_items(v, out)
    elif isinstance(node, list):
        for it in node:
            find_items(it, out)


def extract_orders(raw):
    """从 raw 的 order-list / mall-order-list 返回中提取「订单」列表。

    每个订单含若干订单行（items）。订单数与件数是两个不同口径：
      - 订单数 = 用户下单次数（用于「全年订单」「逐月曲线」「深夜单占比」）
      - 件数   = 餐品数量之和（用于「最爱 Top5」）
    官方返回里订单与订单行可能嵌套，因此这里做「向上归并」：
    先找出所有订单行，再按其所属订单（父级）聚合。
    """
    orders = []
    for tool in ("order-list", "mall-order-list"):
        payload = (raw.get("_tools") or {}).get(tool)
        if not payload:
            continue

        # 优先找「含 items 数组的订单对象」
        order_objs = []
        found_lines = []

        def walk(node, in_order):
            if isinstance(node, dict):
                name = pick(node, ITEM_KEYS)
                has_name = isinstance(name, str) and name.strip()
                has_qty = pick(node, COUNT_KEYS) is not None
                has_price = pick(node, PRICE_KEYS) is not None
                # 订单行：有名字 + 数量/价格，但本身不是订单容器
                if has_name and (has_qty or has_price) and not _has_items_list(node):
                    found_lines.append(node)
                    return
                if _has_items_list(node) or (pick(node, DATE_KEYS) is not None and _has_items_list(node)):
                    order_objs.append(node)
                for v in node.values():
                    if isinstance(v, (list, dict)):
                        walk(v, in_order)
            elif isinstance(node, list):
                for it in node:
                    walk(it, in_order)

        walk(payload, False)

        if order_objs:
            for o in order_objs:
                items = []
                for lst in o.values():
                    if isinstance(lst, list):
                        for it in lst:
                            if isinstance(it, dict):
                                nm = pick(it, ITEM_KEYS)
                                if isinstance(nm, str) and nm.strip():
                                    items.append(it)
                if not items:
                    continue
                dt = parse_dt(pick(o, DATE_KEYS))
                orders.append(_mk_order(tool, o, items, dt))
        elif found_lines:
            # 扁平结构：每行就是一笔订单
            for node in found_lines:
                dt = parse_dt(pick(node, DATE_KEYS))
                orders.append(_mk_order(tool, node, [node], dt))
    return orders


def _has_items_list(node):
    if not isinstance(node, dict):
        return False
    for k, v in node.items():
        if isinstance(v, list) and k.lower() in ("items", "orderitems", "order_items", "products", "goods", "details", "lines"):
            return True
    return False


def _mk_order(tool, order_node, item_nodes, dt):
    """构造一个标准化的订单记录。"""
    if dt is None:
        dt = (0, 0, 0, None, None, 0)
    lines = []
    for node in item_nodes:
        nm = str(pick(node, ITEM_KEYS, "未知餐品")).strip()
        try:
            cnt = int(float(pick(node, COUNT_KEYS, 1) or 1))
        except (ValueError, TypeError):
            cnt = 1
        cnt = max(1, cnt)
        price = pick(node, PRICE_KEYS)
        try:
            price = float(price) if price is not None else None
        except (ValueError, TypeError):
            price = None
        lines.append({"item": nm, "count": cnt, "price": price})

    return {
        "items": lines,
        "count": sum(l["count"] for l in lines),   # 件数
        "ts": dt[5],
        "year": dt[0], "month": dt[1], "day": dt[2],
        "hour": dt[3], "min": dt[4],
        "amount": pick(order_node, PRICE_KEYS),
        "pay": pick(order_node, PAY_KEYS),
        "mode": pick(order_node, MODE_KEYS),
        "store": pick(order_node, STORE_KEYS),
        "_tool": tool,
    }


def build_nutrition(raw):
    """从 list-nutrition-foods 建立 餐品名 -> kcal 映射。"""
    payload = (raw.get("_tools") or {}).get("list-nutrition-foods")
    table = {}
    if not payload:
        return table

    def walk(node):
        if isinstance(node, dict):
            name = pick(node, ITEM_KEYS)
            kcal = pick(node, KCAL_KEYS)
            if isinstance(name, str) and name.strip() and kcal is not None:
                try:
                    table.setdefault(name.strip(), float(kcal))
                except (ValueError, TypeError):
                    pass
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)

    walk(payload)
    return table


def norm_name(name):
    """去掉规格后缀做匹配键。"""
    return SUFFIX_RE.sub("", name).strip()


def kcal_lookup(name, nutrition):
    """按原名 → 去后缀名 → 包含匹配 三级策略查热量。"""
    if not nutrition:
        return None
    if name in nutrition:
        return nutrition[name]
    key = norm_name(name)
    if key in nutrition:
        return nutrition[key]
    for n, v in nutrition.items():
        if norm_name(n) == key:
            return v
    for n, v in nutrition.items():
        if key and (key in norm_name(n) or norm_name(n) in key):
            return v
    return None


def fmt_hour(minutes):
    h = int(round(minutes)) // 60 % 24
    m = int(round(minutes)) % 60
    return "%02d:%02d" % (h, m)


def aggregate(raw, nickname=None):
    orders = extract_orders(raw)
    nutrition = build_nutrition(raw)

    # 未在营养表命中的餐品：记下来，便于 README 提示用户
    unmatched = sorted({l["item"] for o in orders for l in o["items"]
                        if kcal_lookup(l["item"], nutrition) is None})

    dated = [o for o in orders if o["year"]]
    total = len(orders)                            # 订单数（下单次数）
    item_count = sum(o["count"] for o in orders)    # 件数（餐品数量之和）

    # ---- 逐月曲线（按订单数）----
    monthly = [0] * 12
    for o in dated:
        mo = o["month"] - 1
        if 0 <= mo < 12:
            monthly[mo] += 1
    peak = max(monthly) if monthly else 0
    peak_month = (monthly.index(peak) + 1) if peak else 0

    # ---- Top5（按件数）----
    counter = Counter()
    for o in orders:
        for l in o["items"]:
            counter[l["item"]] += l["count"]
    top5 = [{"name": n, "count": c} for n, c in counter.most_common(5)]
    if top5:
        top5[0]["tag"] = "\u672c\u547d"
        mx = top5[0]["count"] or 1
        for t in top5:
            t["w"] = max(8, round(t["count"] / mx * 100))
    top_pct = round(sum(t["count"] for t in top5) / item_count * 100) if item_count else 0

    # ---- 热量（按件）----
    kcal = 0
    kcal_missing = 0
    for o in orders:
        for l in o["items"]:
            k = kcal_lookup(l["item"], nutrition)
            if k is None:
                kcal_missing += l["count"]
                k = 0
            kcal += k * l["count"]
    avg_k = round(kcal / total) if total else 0   # 均单热量：按订单数

    # ---- 深夜画像（按订单数）----
    night_orders = [o for o in dated if o["hour"] is not None and (o["hour"] >= 22 or o["hour"] < 6)]
    night_count = len(night_orders)
    night_pct = round(night_count / total * 100) if total else 0
    night_kcal = 0
    for o in night_orders:
        for l in o["items"]:
            night_kcal += (kcal_lookup(l["item"], nutrition) or 0) * l["count"]
    night_kpct = round(night_kcal / kcal * 100) if kcal else 0
    if night_orders:
        # 深夜时刻跨零点（22:00-05:59），直接取算术平均会得到 12 点附近的错误值。
        # 做法：把 22:00 之后的时刻平移到「以 20:00 为原点」的时间轴上再平均，
        # 再折回真实时刻。
        def night_offset(o):
            h, mi = o["hour"], (o["min"] or 0)
            m = h * 60 + mi
            if h >= 22:
                return m - 22 * 60          # 22:00 -> 0
            if h < 6:
                return (24 - 22) * 60 + m   # 00:00 -> 120, 05:59 -> 479
            return m
        offs = [night_offset(o) for o in night_orders]
        avg_off = sum(offs) / len(offs)
        # 折回真实时刻：偏移 >= 360 表示已跨零点
        real = (22 * 60 + avg_off) % (24 * 60)
        night_avg = fmt_hour(real)
        latest = max(night_orders, key=lambda o: o["ts"])
        night_latest = fmt_hour(latest["hour"] * 60 + (latest["min"] or 0))
    else:
        night_avg, night_latest = "--:--", "--:--"

    # ---- 时段分布（早/午/下午茶/晚餐/深夜，按订单数）----
    buckets = {"morning": 0, "lunch": 0, "tea": 0, "dinner": 0, "night": 0}
    for o in dated:
        h = o["hour"]
        if h is None:
            buckets["lunch"] += 1
        elif h < 11:
            buckets["morning"] += 1
        elif h < 14:
            buckets["lunch"] += 1
        elif h < 17:
            buckets["tea"] += 1
        elif h < 22:
            buckets["dinner"] += 1
        else:
            buckets["night"] += 1
    s = total or 1
    dist = [round(buckets[k] / s * 100) for k in ("morning", "lunch", "tea", "dinner", "night")]

    # ---- 第一单 ----
    if dated:
        first = min(dated, key=lambda o: o["ts"])
        first_item = first["items"][0]["item"] if first["items"] else "\u2014"
        first_price = next((l["price"] for l in first["items"] if l.get("price") is not None), None)
        first_order = {
            "date": "%d.%02d.%02d" % (first["year"], first["month"], first["day"]),
            "item": first_item,
            "amount": ("\u00a5%.2f" % first_price) if first_price is not None else "\u2014",
            "pay": first.get("pay") or "\u2014",
            "mode": first.get("mode") or "\u2014",
            "store": first.get("store") or "\u2014",
        }
    else:
        first_order = {"date": "\u2014", "item": "\u2014", "amount": "\u2014",
                       "pay": "\u2014", "mode": "\u2014", "store": "\u2014"}

    # ---- 积分 ----
    acct = (raw.get("_tools") or {}).get("query-my-account") or {}
    points = {"total": 0, "expired": 0, "expiring": 0, "redeemed": 0}
    if isinstance(acct, dict):
        def num(keys):
            v = pick(acct, keys)
            try:
                return int(float(v)) if v is not None else 0
            except (ValueError, TypeError):
                return 0
        points["total"] = num(TOTAL_KEYS)
        points["expired"] = num(EXPIRE_KEYS)
        points["expiring"] = num(EXPIRE_KEYS)
        points["available"] = num(AVAIL_KEYS)
        points["frozen"] = num(FROZEN_KEYS)
        points["redeemed"] = num(REDEEM_KEYS)
        # 过期积分优先取明确字段，否则用「累计 - 可用」推算
        if not points["expired"] and points["total"] and points.get("available"):
            points["expired"] = max(0, points["total"] - points["available"])
        if not points["expiring"]:
            points["expiring"] = points["expired"]

    # ---- 人格标签（数据驱动的幽默，不是运势预测）----
    persona = derive_persona(night_pct, top5, dist, monthly, points, total)

    return {
        "nickname": nickname or "\u6211\u7684\u9ea6\u5f53\u52b3\u62a5\u544a",
        "member": "// generated by mcd-annual-report skill",
        "firstOrder": first_order,
        "total": total,
        "itemCount": item_count,
        "top5": top5,
        "monthly": monthly,
        "kcal": int(round(kcal)),
        "lateNight": {"count": night_count, "pct": night_pct, "avg": night_avg,
                      "latest": night_latest, "dist": dist},
        "points": points,
        "persona": persona,
        "isDemo": False,
        "_avgK": avg_k,
        "_nightKpct": night_kpct,
        "_peak": peak,
        "_peakMonth": peak_month,
        "_topPct": top_pct,
        "_nutritionCount": len(nutrition),
        "_unmatched": unmatched,
        "_kcalMissing": kcal_missing,
        "_ordersParsed": len(orders),
    }


def derive_persona(night_pct, top5, dist, monthly, points, total):
    """依据真实数据特征生成程序员人格标签（纯数据驱动，非命理预测）。"""
    name = top5[0]["name"] if top5 else "麦门信徒"
    if night_pct >= 40:
        tag, desc = "深夜修 Bug 的麦门信徒", "你的订单里有一半发生在代码编辑器还亮着的时候。凌晨的门店，是这个城市最后一个还亮着的窗口。"
    elif night_pct >= 25:
        tag, desc = "准时下班的麦门信徒", "你不是熬夜型，你是「刚好在下班路上顺手点」型——二十三点半的那一单，是你给一天收尾的方式。"
    elif dist and dist[0] >= 30:
        tag, desc = "早餐先行的麦门信徒", "别人还在刷牙，你已经吃完了。清晨的那一单，是一天里最像你自己的决定。"
    else:
        tag, desc = "午休限定麦门信徒", "你的点单时间集中在午间与傍晚——规律得像一段没有 bug 的代码。"

    if points.get("expired", 0) > 0:
        desc += "另外，你有 %d 积分没能用上。" % points["expired"]
    return {"tag": tag, "desc": desc, "main": name}


def main():
    ap = argparse.ArgumentParser(description="聚合麦当劳 MCP 数据")
    ap.add_argument("--in", dest="inp", default="raw_orders.json")
    ap.add_argument("--out", default="report_data.json")
    ap.add_argument("--nickname", default=None)
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print("找不到输入文件: %s（先运行 mcp_fetch.py）" % args.inp, file=sys.stderr)
        return 1

    with open(args.inp, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data = aggregate(raw, args.nickname)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("聚合完成 -> %s" % args.out)
    print("  订单行 %d / 订单数 %d / 营养表 %d 项 / 热量 %d kcal"
          % (data["_ordersParsed"], data["total"], data["_nutritionCount"], data["kcal"]))
    if data["_unmatched"]:
        print("  ⚠ %d 个餐品未匹配到官方营养数据: %s"
              % (len(data["_unmatched"]), "、".join(data["_unmatched"][:8])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
