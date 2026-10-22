---
name: mcd-annual-report
description: "生成你的麦当劳个人年度报告（Wrapped 式九屏报告）。当用户说「生成我的麦当劳年度报告」「我的点单报告」「麦当劳年度总结」「看看我今年点了多少次麦当劳」时使用。通过麦当劳官方 MCP Server 拉取历史订单与营养数据，聚合后渲染为可分享的单文件 HTML 报告。"
version: 1.0.0
display_name: "麦麦年度报告"
display_name_en: "McDonald's Annual Food Report"
license: MIT
---

# 麦麦年度报告 · McDonald's Annual Food Report

把用户一年的点单史，编译成一份 Wrapped 式的九屏个人报告。

## 何时使用

用户表达以下意图时触发：

- 「生成我的麦当劳年度报告」「我的点单报告」「麦当劳年终总结」
- 「我今年点了多少次麦当劳」「看看我的麦当劳数据」
- 「给我一份麦当劳年度报告」

## 前置条件

| 条件 | 说明 |
|------|------|
| MCP Token | 需用户在 https://open.mcd.cn/mcp 申请；通过环境变量 `MCD_MCP_TOKEN` 提供 |
| Python | 3.8+，**仅用标准库**（无需 pip install） |
| MCP Server | `https://mcp.mcd.cn`（Streamable HTTP），已在 MCP 客户端配置 |

MCP 客户端配置示例：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

## 执行流程

### 第 1 步 · 确认授权与 Token

1. 确认用户已授权访问麦当劳 MCP 数据（订单、积分）。
2. 检查环境变量 `MCD_MCP_TOKEN` 是否存在。
   - **不存在** → 告知用户去 https://open.mcd.cn/mcp 申请，并给出申请步骤；或提供 `--demo` 演示模式先看效果。
   - **存在** → 继续。

### 第 2 步 · 拉取 MCP 数据

```bash
python scripts/mcp_fetch.py --out raw_orders.json
```

调用 6 个官方 Tool（串行，遵守官方 600 次/分钟限流）：

| Tool | 用途 |
|------|------|
| `order-list` | 历史订单（到店/外送） |
| `mall-order-list` | 近一年麦麦商城订单 |
| `list-nutrition-foods` | 官方餐品营养数据（能量/蛋白质/脂肪/碳水/钠/钙） |
| `query-my-account` | 积分账户（可用/累计/过期/冻结） |
| `query-my-coupons` | 优惠券 |
| `query-my-prizes` | 积分抽奖奖品记录 |

> 无 Token 时可运行 `python scripts/mcp_fetch.py --demo --out raw_orders.json`，使用内置脱敏样例数据。

### 第 3 步 · 聚合

```bash
python scripts/aggregate.py --in raw_orders.json --out report_data.json --nickname "用户昵称"
```

产出 `report_data.json`，包含：
- `total` 订单数 / `itemCount` 件数
- `top5` 最爱单品 Top5（按件数，含 `w` 份额条宽度）
- `monthly` 12 个月订单数（用于曲线）
- `kcal` 累计热量（按官方营养数据匹配）
- `lateNight` 深夜画像（22:00–05:59 订单数、占比、均时、最晚时段、5 时段分布）
- `points` 积分体检（累计/过期/临期/可用/兑换）
- `persona` 1024 程序员人格标签（**纯数据驱动**）

### 第 4 步 · 渲染报告

```bash
python scripts/render_report.py --in report_data.json --out "麦麦年度报告.html"
```

产出**单文件自包含 HTML**（CSS/JS/SVG 全内联），九屏滚动叙事，可直接双击打开、转发分享。

### 第 5 步 · 交付

1. 告知用户报告文件路径。
2. 提示「保存」即可离线查看与转发。
3. 若部分餐品未匹配到官方营养数据，**如实告知**（聚合脚本会打印 `_unmatched` 列表），不要假装数据完整。

## 报告的九屏结构

| 屏 | 内容 | 数据来源 |
|----|------|----------|
| S0 | 封面 · 昵称 · 年度总览 | `total` / `kcal` / `lateNight.count` |
| S1 | 第一单 | 最早订单的日期、餐品、支付、取餐、门店 |
| S2 | 最爱 Top5 | `top5` |
| S3 | 逐月曲线 | `monthly`（SVG 动态绘制） |
| S4 | 热量洞察 | `kcal` / `_avgK` / `_nightKpct` |
| S5 | 深夜画像 | `lateNight.avg` / `lateNight.dist` |
| S6 | 积分体检 | `points` |
| S7 | 1024 人格彩蛋 | `persona` |
| S8 | 分享海报 | 3:4 海报卡 + 截图指引 |

## 隐私与合规（重要）

- **MCP Token 只从环境变量读取**，绝不写入代码、配置文件或报告输出。
- 用户数据**全程本地处理**，不上传任何第三方服务器。
- `raw_orders.json` 含用户真实订单，属于敏感文件：处理完应提示用户删除，或加入 `.gitignore`。
- 报告中**不含任何品牌贬损表述**，热量数据只做客观陈述与趣味换算，不做健康评判。
- 幽默标签是**数据特征的描述**（如「深夜时段占比高」），**不是运势预测或占卜**。

## 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 401 | Token 无效/过期 | 重新到 open.mcd.cn/mcp 申请 |
| 429 | 触发限流（600 次/分钟） | 降低调用频率后重试 |
| 订单数为 0 | 返回结构中订单在 `data.list` / `data.records` 等不同键下 | `aggregate.py` 已做多键兼容；若仍为空，请记录原始返回并反馈 |
| 热量偏低 | 部分餐品未命中官方营养表 | 查看 `_unmatched`，多为套餐名或新品 |
| 深夜均时异常 | 已按跨零点偏移量计算 | 若仍异常，请检查订单时间字段是否含时区 |

## 文件说明

```
mcd-annual-report/
├── SKILL.md                     # 本文件
├── scripts/
│   ├── mcp_fetch.py             # MCP 客户端（纯标准库）
│   ├── aggregate.py             # 数据聚合引擎
│   ├── render_report.py         # HTML 渲染器
│   ├── build_template.py        # 从交互版派生静态模板
│   └── make_demo_data.py        # 生成脱敏演示数据
├── assets/
│   └── report_template.html     # 九屏报告模板（数据占位符）
├── examples/
│   └── demo_raw.json            # 脱敏样例数据
└── docs/
    └── architecture.png         # 架构图
```

## License

MIT
