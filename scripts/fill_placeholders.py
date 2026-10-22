#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_placeholders.py — 把仓库里的 <你的GitHub用户名> 占位符替换为真实用户名

用法：
    python scripts/fill_placeholders.py --username 你的GitHub用户名
    python scripts/fill_placeholders.py --username xxx --name "你的姓名" --email "you@example.com"

会处理的文件：README.md / CONTEST_DECLARATION.md / MCP_INTEGRATION.md /
             workbuddy.md / SKILL.md / docs/引流文案.md / docs/GitHub发布指引.md
"""

import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

TARGETS = [
    "README.md",
    "CONTEST_DECLARATION.md",
    "MCP_INTEGRATION.md",
    "workbuddy.md",
    "SKILL.md",
    "docs/引流文案.md",
    "docs/GitHub发布指引.md",
    "docs/交付总览.md",
]

USER_PLACEHOLDER = "<你的GitHub用户名>"
NAME_PLACEHOLDER = "<你的姓名>"
EMAIL_PLACEHOLDER = "<你的邮箱>"
REPO_NAME = "mcd-annual-report"


def main():
    ap = argparse.ArgumentParser(description="替换仓库占位符")
    ap.add_argument("--username", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--email", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # 改写前先备份一份原始占位符版本：
    # 万一填错用户名，备份可秒级还原，不必手工改回去。
    backup_dir = os.path.join(REPO, ".placeholder_backup")
    if not args.dry_run and not os.path.isdir(backup_dir):
        os.makedirs(backup_dir)
        print("已创建原始占位符备份 -> %s" % backup_dir)

    changed = 0
    for rel in TARGETS:
        path = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.exists(path):
            print("跳过（不存在）:", rel)
            continue
        with io.open(path, encoding="utf-8") as f:
            orig = f.read()
        text = orig.replace(USER_PLACEHOLDER, args.username)
        text = text.replace(REPO_NAME + " 仓库", args.username + "/" + REPO_NAME + " 仓库")
        if args.name:
            text = text.replace(NAME_PLACEHOLDER, args.name)
        if args.email:
            text = text.replace(EMAIL_PLACEHOLDER, args.email)
        # 通用形式：<你的GitHub用户名>/xxx
        text = text.replace("<你的GitHub用户名>/", args.username + "/")
        if text == orig:
            print("  无变化:", rel)
            continue
        if args.dry_run:
            print("  [dry-run] 将修改:", rel)
        else:
            if not args.dry_run:
                bak = os.path.join(backup_dir, rel.replace("/", "_"))
                with io.open(bak, "w", encoding="utf-8") as bf:
                    bf.write(orig)
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print("  ✓ 已替换:", rel)
        changed += 1

    print("\n共修改 %d 个文件。" % changed)

    # 漏网检查：扫描所有文档，若还有占位符残留就明确报出来
    leftovers = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".placeholder_backup", "assets", "examples")]
        for fn in filenames:
            if not fn.endswith((".md", ".json", ".html")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, REPO).replace(os.sep, "/")
            if rel in TARGETS or rel == "scripts/fill_placeholders.py":
                continue
            try:
                with io.open(full, encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                continue
            # 只关心「真正的链接占位符」，忽略 --username 你的GitHub用户名 这类命令示例
            if (USER_PLACEHOLDER + "/") in text:
                leftovers.append(rel)

    if leftovers:
        print("\n⚠ 以下文档仍含占位符，但不在替换清单里，请手动处理：")
        for rel in leftovers:
            print("  -", rel)

    if changed and not args.dry_run:
        print("\n下一步：")
        print("  1. 检查残留占位符: grep -rn \"你的GitHub用户名\\|你的姓名\\|你的邮箱\" .")
        print("  2. 发布到 GitHub:")
        print("     export GITHUB_TOKEN=ghp_xxx")
        print("     python scripts/publish_github.py --owner %s --repo %s"
              % (args.username, REPO_NAME))
    return 0


if __name__ == "__main__":
    sys.exit(main())
