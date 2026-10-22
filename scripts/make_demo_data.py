#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo_data.py — 生成脱敏演示数据（examples/demo_raw.json）

用途：
1. 没有 MCP Token 也能跑通整条链路（--demo 路径），让评审者 10 秒看到效果；
2. 作为 MCP 真实返回结构的参考样例，字段命名与官方接口保持一致。

所有数据均为虚构，与任何真实用户无关。
"""

import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "examples", "demo_raw.json")

random.seed(1024)

MENU = [
    ("巨无霸", 503), ("双层吉士堡", 440), ("麦辣鸡腿堡", 458), ("板烧鸡腿堡", 467),
    ("麦香鸡", 388), ("麦香鱼", 370), ("吉士汉堡", 295), ("汉堡", 248),
    ("猪柳蛋麦满分", 360), ("吉士蛋麦满分", 350), ("烟肉蛋麦满分", 420),
    ("薯条（大）", 412), ("薯条（中）", 319), ("麦乐鸡（5 块）", 216),
    ("香芋派", 113), ("苹果派", 109), ("圆筒冰淇淋", 123), ("麦旋风（原味）", 199),
    ("玉米杯", 102), ("可乐（中）", 144), ("雪碧（中）", 140), ("拿铁", 120),
    ("麦辣鸡翅（2 块）", 196), ("黄金鸡块（6 块）", 270),
]
# 权重：制造真实的偏好分布（Top5 集中）
WEIGHTS = [14, 11, 12, 16, 7, 6, 5, 4, 5, 4, 3, 10, 6, 8, 4, 3, 3, 2, 2, 5, 3, 3, 2, 3]

NAMES = [n for n, _ in MENU]
KCS = {n: k for n, k in MENU}

# 逐月单量：贴合「6 月峰值」的叙事
MONTHLY = [9, 6, 10, 11, 15, 23, 16, 12, 13, 14, 16, 17]

PAYS = ["微信支付", "支付宝", "银联卡", "麦当劳支付"]
MODES = ["餐厅自取", "麦乐送", "得来速"]
STORES = ["科技园餐厅", "中央广场店", "万象城餐厅", "地铁站餐厅"]


def build_orders():
    orders = []
    order_no = 0
    for month, count in enumerate(MONTHLY, start=1):
        for _ in range(count):
            order_no += 1
            day = random.randint(1, 28)
            # 深夜单占约 29%：约 1/3 的订单落在 22:00-05:59
            if random.random() < 0.30:
                hour = random.choice([22, 23, 0, 1, 2, 23, 22, 3])
            elif random.random() < 0.35:
                hour = random.choice([7, 8, 9, 10])
            elif random.random() < 0.55:
                hour = random.choice([11, 12, 13])
            else:
                hour = random.choice([14, 15, 16, 17, 18, 19, 20, 21])
            minute = random.randint(0, 59)

            n_items = random.choice([1, 1, 1, 2, 2, 3])
            picks = random.choices(range(len(NAMES)), weights=WEIGHTS, k=n_items)
            items = []
            for idx in picks:
                qty = 1 if random.random() < 0.88 else 2
                items.append({
                    "itemName": NAMES[idx],
                    "quantity": qty,
                    "price": round(random.uniform(8, 45), 2),
                    "energy": KCS[NAMES[idx]],
                })

            ts = "%04d-%02d-%02d %02d:%02d:%02d" % (2025, month, day, hour, minute, random.randint(0, 59))
            orders.append({
                "orderNo": "MCD2025%06d" % order_no,
                "createTime": ts,
                "payType": random.choice(PAYS),
                "orderType": random.choice(MODES),
                "storeName": random.choice(STORES),
                "items": items,
                "totalAmount": round(sum(i["price"] * i["quantity"] for i in items), 2),
            })
    return orders


def build_nutrition():
    out = []
    for name, kcal in MENU:
        out.append({
            "foodName": name,
            "energy": kcal,
            "protein": round(kcal * 0.055, 1),
            "fat": round(kcal * 0.11, 1),
            "carbohydrate": round(kcal * 0.09, 1),
            "sodium": round(kcal * 0.9),
            "calcium": round(kcal * 0.25),
        })
    return {"code": 0, "message": "success", "data": {"foods": out, "total": len(out)}}


def main():
    orders = build_orders()

    raw = {
        "_fetched_at": "2025-12-31T23:59:00+08:00",
        "_demo": True,
        "_note": "脱敏演示数据，与任何真实用户无关。",
        "_tools": {
            "order-list": {
                "code": 0, "message": "success",
                "data": {"list": orders, "total": len(orders)},
            },
            "mall-order-list": {
                "code": 0, "message": "success",
                "data": {"list": [], "total": 0},
            },
            "list-nutrition-foods": build_nutrition(),
            "query-my-account": {
                "code": 0, "message": "success",
                "data": {
                    "totalPoints": 4082,
                    "availablePoints": 2796,
                    "expiredPoints": 1286,
                    "expiringPoints": 640,
                    "frozenPoints": 0,
                    "redeemedPoints": 23,
                    "memberLevel": "金拱门会员",
                },
            },
            "query-my-coupons": {
                "code": 0, "message": "success",
                "data": {"list": [], "total": 0},
            },
            "query-my-prizes": {
                "code": 0, "message": "success",
                "data": {"list": [], "total": 0},
            },
        },
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print("演示数据已生成 -> %s" % OUT)
    print("  订单 %d 条 · 餐品营养 %d 项" % (len(orders), len(MENU)))
    return 0


if __name__ == "__main__":
    main()
