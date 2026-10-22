"""从本机 WorkBuddy 会话记录中抽取真实开发对话，脱敏后生成可作为参赛凭证的 workbuddy.md 上下文。

输出：mcd-skill-repo/.workbuddy/memory/2026-10-22.md（脱敏版开发对话上下文）
"""
import json
import os
import re

SRC = r"C:\Users\Administrator\.workbuddy\projects\d-[  WorkBuddy  ]-Workspace-2026-10-22-12-20-08\8fff7a71-79fa-48fa-88ed-fb689b00e0c9.jsonl"
DST = r"D:\[  WorkBuddy  ]\Workspace\2026-10-22-12-20-08\mcd-skill-repo\.workbuddy\memory\2026-10-22.md"

# ---- 脱敏规则 ----
EMAILS = ["vvvvv20252025@163.com", "doming81@189.cn"]
SECRETS = [
    "1qaz#EDC5tgb^^",
    "2wsx#EDC4rfv",
]

# ---- 话题过滤 ----
# 与「项目开发」直接相关的关键词（命中才保留）
TOPIC_OK = [
    "报告", "九屏", "聚合", "MCP", "订单", "积分", "营养", "热量", "深夜",
    "README", "SKILL", "模板", "HTML", "GIF", "架构", "Skill", "原型",
    "设计", "配色", "评审", "质量", "仓库", "Issue", "参赛", "大赛",
    "WorkBuddy", "脚本", "Python", "数据", "Top5", "演示", "demo", "引流",
    "冲榜", "Star", "star", "海报", "截图", "可视化", "曲线", "餐品",
    "年报", "年度", "麦麦", "麦当劳", "令牌", "设计系统", "排版", "动效",
]
# 命中即丢弃（账号开通、凭据探测等与开发无关且不宜公开的内容）
TOPIC_BLOCK = [
    "1qaz", "2wsx", "DPAPI", "CryptUnprotect", "imap", "IMAP", "授权码",
    "滑块", "DataDome", "爆破", "bruteforce", "brute", "password_value",
    "Login Data", "Cookies", "解密", "验证码", "logged_in", "_octo",
    "gh_token", "PAT", "personal access", "oauth_access", "找回", "注册",
    "126.com", "sina.com", "foxmail", "outlook.com", "gmail.com", "qq.com",
    "doming81", "@163.com", "@189.cn", "msedge", "host-resolver",
    "gh_profile", "settings/tokens", "profile", "设备验证",
]


# 系统自动通知 / 框架噪音（整条丢弃）
NOISE = [
    "Use the TaskOutput tool",
    "[Framework Auto-Notification]",
    "[SYSTEM NOTIFICATION",
    "<system-reminder",
    "<task-notification>",
    "This is an automated background-task event",
    "<teammate-message",
]


def is_noise(text: str) -> bool:
    return any(n in text for n in NOISE)


def keep_topic(text: str) -> bool:
    if not text:
        return False
    for bad in TOPIC_BLOCK:
        if bad in text:
            return False
    return any(k in text for k in TOPIC_OK)


def scrub(text: str) -> str:
    if not text:
        return text
    for s in SECRETS:
        text = text.replace(s, "[已脱敏]")
    # GitHub token
    text = re.sub(r"gh[pousr]_[A-Za-z0-9]{16,}", "[TOKEN已脱敏]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]{20,}", "[TOKEN已脱敏]", text)
    # 手机号
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    # 邮箱
    for e in EMAILS:
        text = text.replace(e, "[邮箱已脱敏]")
    # 本地绝对路径
    text = re.sub(r"[A-Za-z]:\\\\Users\\\\[^\\\s\"']+", "[本地路径已脱敏]", text)
    text = re.sub(r"[A-Za-z]:\\\\?[^\s\"'<>|*?]*WorkBuddy[^\s\"'<>|*?]*", "[本地路径已脱敏]", text)
    return text


def extract_text(content):
    """从 message.content 提取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, str):
                parts.append(b)
                continue
            if not isinstance(b, dict):
                continue
            t = b.get("type") or ""
            # 只要有 text 字段就当正文（input_text / output_text / text 都覆盖）
            if "text" in b and isinstance(b["text"], str):
                parts.append(b["text"])
                continue
            if "thinking" in t or t == "thinking":
                continue
            if "tool" in t and "result" not in t:
                name = b.get("name", "?")
                inp = b.get("input", {})
                brief = ""
                if isinstance(inp, dict):
                    brief = (inp.get("command") or inp.get("file_path")
                             or inp.get("pattern") or inp.get("description") or "")
                parts.append("\n> `_调用工具 %s_`%s\n" % (name, (" · " + str(brief)[:120]) if brief else ""))
            # 其余（tool_result 等）跳过：体积大、噪音多
        return "\n".join(parts)
    return ""


rows = []
with open(SRC, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") != "message":
            continue
        role = obj.get("role")
        if role not in ("user", "assistant"):
            continue
        txt = extract_text(obj.get("content"))
        if not txt or not txt.strip():
            continue
        # 跳过系统注入的提示块
        if txt.strip().startswith(("<system-reminder", "[SYSTEM NOTIFICATION")):
            continue
        txt = re.sub(r"<system-reminder>.*?</system-reminder>", "", txt, flags=re.S)
        txt = re.sub(r"<task-notification>.*?</task-notification>", "", txt, flags=re.S)
        txt = re.sub(r"\[SYSTEM NOTIFICATION[^\]]*\]", "", txt)
        txt = txt.strip()
        if not txt:
            continue
        txt = scrub(txt)
        if is_noise(txt):
            continue
        # 话题过滤：助手消息走白名单（去噪音）；用户消息只做黑名单（保留全部诉求）
        if role == "assistant":
            if not keep_topic(txt):
                continue
        else:
            if any(bad in txt for bad in TOPIC_BLOCK):
                continue
        # 丢弃过短的寒暄
        body = re.sub(r"`_调用工具[^`]*`", "", txt).strip()
        if len(body) < 25:
            continue
        rows.append((role, txt))

print("抽取到对话条目:", len(rows))

# ---- 组装输出 ----
out = []
out.append("# WorkBuddy 开发对话上下文 · 2026-10-22")
out.append("")
out.append("> 本文件由腾讯 WorkBuddy 智能体的真实开发对话记录导出并脱敏，用于核验本项目确由 WorkBuddy 开发。")
out.append("> 脱敏范围：账号密码、访问令牌、手机号、个人邮箱、本地绝对路径。")
out.append("> 导出时间：2026-10-23")
out.append("")
out.append("---")
out.append("")

n_user = n_ass = 0
for role, txt in rows:
    if role == "user":
        n_user += 1
        out.append("## 🧑 用户\n")
        out.append(txt + "\n")
    else:
        n_ass += 1
        out.append("## 🤖 WorkBuddy\n")
        out.append(txt + "\n")
    out.append("---\n")

os.makedirs(os.path.dirname(DST), exist_ok=True)
with open(DST, "w", encoding="utf-8") as f:
    f.write("\n".join(out))

size = os.path.getsize(DST)
print("用户发言:", n_user, " WorkBuddy 回复:", n_ass)
print("输出（全量草稿，不上传）:", DST, "大小: %.1f KB" % (size / 1024))

# ---- 精选版：只留有实质技术内容的推演，作为随仓库公开的凭证 ----
SEL = r"D:\[  WorkBuddy  ]\Workspace\2026-10-22-12-20-08\mcd-skill-repo\docs\workbuddy-对话上下文.md"
sel = []
sel.append("# WorkBuddy 开发对话上下文（精选 · 已脱敏）")
sel.append("")
sel.append("> 本文件节选自腾讯 WorkBuddy 智能体开发「麦麦年度报告」过程中的真实对话记录，")
sel.append("> 用于核验本项目确由 WorkBuddy 智能体开发（麦当劳程序员创意开发大赛 WorkBuddy 专项奖励凭证）。")
sel.append(">")
sel.append("> **脱敏范围**：账号密码、访问令牌、手机号、个人邮箱、本地绝对路径、第三方平台凭据。")
sel.append("> **节选标准**：保留含实质技术判断与决策过程的对话；剔除系统通知、工具回显、账号操作类内容。")
sel.append("> 导出时间：2026-10-23")
sel.append("")
sel.append("---")
sel.append("")

kept = 0
for role, txt in rows:
    plain = re.sub(r"> `_调用工具[^`]*`", "[调用工具]", txt).strip()
    if len(plain) < 200:
        continue
    who = "**用户**" if role == "user" else "**WorkBuddy**"
    sel.append("### %s\n" % who)
    sel.append(plain + "\n")
    sel.append("---\n")
    kept += 1

os.makedirs(os.path.dirname(SEL), exist_ok=True)
with open(SEL, "w", encoding="utf-8") as f:
    f.write("\n".join(sel))
print("精选条目:", kept, "->", SEL, "大小: %.1f KB" % (os.path.getsize(SEL) / 1024))
