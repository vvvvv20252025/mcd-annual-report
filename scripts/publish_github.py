#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_github.py — 通过 GitHub REST API 建仓库并上传文件（绕过被墙的 github.com 主站）

背景：国内直连 github.com / raw.githubusercontent.com 常被阻断，
但 api.github.com 通常可用。本脚本用 API 完成全部操作：
  1. 创建 Public 仓库
  2. 逐个上传文件（PUT /repos/{owner}/{repo}/contents/{path}）
  3. 提交参赛 Issue（POST /repos/M-China/mcd-developer-innovation-challenge/issues）

用法：
  export GITHUB_TOKEN=ghp_xxx
  python scripts/publish_github.py --owner <你的GitHub用户名> --repo mcd-annual-report
  python scripts/publish_github.py --owner xxx --repo mcd-annual-report --issue-only
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
CONTEST_REPO = "M-China/mcd-developer-innovation-challenge"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 需要上传的文件（相对仓库根）
UPLOAD_FILES = [
    "README.md",
    "SKILL.md",
    "LICENSE",
    "CONTEST_DECLARATION.md",
    "MCP_INTEGRATION.md",
    "mcp-config.example.json",
    "workbuddy.md",
    "run.sh",
    ".gitignore",
    "publish.ps1",
    "一键发布.cmd",
    "scripts/mcp_fetch.py",
    "scripts/aggregate.py",
    "scripts/render_report.py",
    "scripts/build_template.py",
    "scripts/make_demo_data.py",
    "scripts/make_architecture.py",
    "scripts/publish_github.py",
    "scripts/fill_placeholders.py",
    "scripts/check_consistency.py",
    "assets/report_template.html",
    "examples/demo_raw.json",
    "docs/architecture.png",
    "docs/architecture.drawio",
    "docs/引流文案.md",
    "docs/GitHub发布指引.md",
    "readme-demo.gif",
    # WorkBuddy 开发对话记录（官方 workbuddy.md 专项奖励凭证）
    ".workbuddy/memory/2026-10-22.md",
]


def api(method, path, token, body=None, raw_body=None):
    url = API + path
    headers = {
        "Authorization": "Bearer %s" % token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mcd-annual-report-publisher",
    }
    data = None
    if raw_body is not None:
        data = raw_body
        headers["Content-Type"] = "application/json"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:600]
        return e.code, {"_error": detail}
    except urllib.error.URLError as e:
        print("网络错误: %s" % e.reason, file=sys.stderr)
        sys.exit(3)


def create_repo(owner, repo, token, description):
    status, data = api("POST", "/user/repos", token, body={
        "name": repo,
        "description": description,
        "private": False,
        "auto_init": True,
        "has_issues": True,
        "has_wiki": False,
        "license_template": "mit",
    })
    if status in (201, 422):
        # 422 通常是「已存在」，再查一次确认
        s2, d2 = api("GET", "/repos/%s/%s" % (owner, repo), token)
        if s2 == 200:
            print("仓库已存在，跳过创建: %s/%s" % (owner, repo))
            return True
        print("创建仓库失败 HTTP %s: %s" % (status, data))
        return False
    if status != 201:
        print("创建仓库失败 HTTP %s: %s" % (status, data))
        return False
    print("仓库已创建: https://github.com/%s/%s" % (owner, repo))
    return True


def upload_file(owner, repo, path, token, content, message):
    # 路径各段必须做百分号编码，否则中文文件名（如 一键发布.cmd）会触发
    # UnicodeEncodeError: 'ascii' codec can't encode characters
    enc_path = "/".join(urllib.parse.quote(seg, safe="") for seg in path.split("/"))
    api_url = "/repos/%s/%s/contents/%s" % (owner, repo, enc_path)
    b64 = base64.b64encode(content).decode("ascii")
    status, data = api("PUT", api_url, token, body={
        "message": message,
        "content": b64,
        "branch": "main",
    })
    if status in (200, 201):
        return True
    # 文件已存在则需要先取 sha 再更新
    if status == 422:
        s, d = api("GET", api_url, token)
        if s == 200 and isinstance(d, dict) and d.get("sha"):
            status2, data2 = api("PUT", api_url, token, body={
                "message": message,
                "content": b64,
                "sha": d["sha"],
                "branch": "main",
            })
            if status2 in (200, 201):
                return True
            print("  更新失败 %s: %s" % (path, data2))
            return False
    print("  上传失败 %s (HTTP %s): %s" % (path, status, data))
    return False


# contents API 对大文件不可靠（base64 膨胀 + 请求体上限）。
# 超过此阈值的文件改走 Git Data API（blobs），可支持到 100MB。
LARGE_FILE_THRESHOLD = 800 * 1024


def upload_large_file(owner, repo, path, token, content, message):
    """用 Git Data API 上传大文件：create blob -> create tree -> update ref。"""
    b64 = base64.b64encode(content).decode("ascii")

    # 1) 创建 blob
    st, blob = api("POST", "/repos/%s/%s/git/blobs" % (owner, repo), token,
                   body={"content": b64, "encoding": "base64"})
    if st not in (201, 200) or not isinstance(blob, dict) or "sha" not in blob:
        print("  blob 创建失败 %s (HTTP %s): %s" % (path, st, blob))
        return False
    blob_sha = blob["sha"]

    # 2) 取当前 main 分支的 tree
    st, ref = api("GET", "/repos/%s/%s/git/ref/heads/main" % (owner, repo), token)
    base_tree = None
    if st == 200 and isinstance(ref, dict):
        base_tree = (ref.get("object") or {}).get("sha")
    # 用 commit 的 tree 作为基底
    st, commit = api("GET", "/repos/%s/%s/git/commits/main" % (owner, repo), token)
    if st == 200 and isinstance(commit, dict):
        base_tree = (commit.get("tree") or {}).get("sha")

    # 3) 创建 tree（只含本文件，基于当前 tree 叠加）
    st, tree = api("POST", "/repos/%s/%s/git/trees" % (owner, repo), token, body={
        "base_tree": base_tree,
        "tree": [{
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        }],
    })
    if st not in (201, 200) or not isinstance(tree, dict) or "sha" not in tree:
        print("  tree 创建失败 %s (HTTP %s): %s" % (path, st, tree))
        return False
    tree_sha = tree["sha"]

    # 4) 创建 commit
    st, new_commit = api("POST", "/repos/%s/%s/git/commits" % (owner, repo), token, body={
        "message": message,
        "tree": tree_sha,
        "parents": [base_tree] if base_tree else [],
    })
    if st not in (201, 200) or not isinstance(new_commit, dict) or "sha" not in new_commit:
        print("  commit 创建失败 %s (HTTP %s): %s" % (path, st, new_commit))
        return False
    commit_sha = new_commit["sha"]

    # 5) 更新分支引用
    st, upd = api("PATCH", "/repos/%s/%s/git/refs/heads/main" % (owner, repo), token, body={
        "sha": commit_sha,
        "force": False,
    })
    if st not in (200, 201):
        print("  分支更新失败 %s (HTTP %s): %s" % (path, st, upd))
        return False
    return True


def upload_all(owner, repo, token, root=REPO_ROOT):
    ok = 0
    fail = []
    for rel in UPLOAD_FILES:
        full = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(full):
            print("  跳过（不存在）: %s" % rel)
            fail.append(rel)
            continue
        with open(full, "rb") as f:
            content = f.read()
        size = len(content)
        # 大文件走 Git Data API（contents API 对 >800KB 的载荷不可靠）
        if size > LARGE_FILE_THRESHOLD:
            print("  ↑ %s (%.2f MB) 走 Git Data API ..." % (rel, size / 1024 / 1024))
            done = upload_large_file(owner, repo, rel, token, content, "feat: %s" % rel)
        else:
            done = upload_file(owner, repo, rel, token, content, "feat: %s" % rel)
        if done:
            print("  ✓ %s (%.1f KB)" % (rel, size / 1024))
            ok += 1
        else:
            fail.append(rel)
        time.sleep(0.25)   # 避免触发次级限流
    print("上传完成: %d 成功, %d 失败" % (ok, len(fail)))
    if fail:
        print("失败清单: %s" % ", ".join(fail))
        print("提示: 大文件失败时，改用 git push 上传（见 docs/GitHub发布指引.md 兜底方案）")
    return ok, fail


def submit_issue(owner, repo, token, title, body):
    status, data = api("POST", "/repos/%s/%s/issues" % (CONTEST_REPO, ""), token, body={
        "title": title,
        "body": body,
        "labels": [],
    })
    if status == 201:
        print("参赛 Issue 已提交: %s" % data.get("html_url"))
        return True
    print("提交 Issue 失败 HTTP %s: %s" % (status, data))
    return False


def main():
    ap = argparse.ArgumentParser(description="发布到 GitHub")
    ap.add_argument("--owner", required=True, help="GitHub 用户名")
    ap.add_argument("--repo", default="mcd-annual-report")
    ap.add_argument("--description", default="把这一年吃过的每一口，编译成一份只属于你的报告。接入麦当劳官方 MCP，生成 Wrapped 式九屏个人年度报告。")
    ap.add_argument("--issue-only", action="store_true", help="只提交 Issue，不传文件")
    ap.add_argument("--no-issue", action="store_true", help="不提交 Issue")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("错误：未设置环境变量 GITHUB_TOKEN。", file=sys.stderr)
        print("  申请: https://github.com/settings/tokens（勾选 repo 权限）", file=sys.stderr)
        return 2

    # 校验 token
    status, data = api("GET", "/user", token)
    if status != 200:
        print("Token 校验失败 HTTP %s: %s" % (status, data), file=sys.stderr)
        return 3
    print("认证成功: %s" % data.get("login"))

    if not args.issue_only:
        if not create_repo(args.owner, args.repo, token, args.description):
            return 4
        upload_all(args.owner, args.repo, token)

    if not args.no_issue:
        issue_body = """【参赛申请】
项目名称：麦麦年度报告 · McDonald's Annual Food Report
项目地址：https://github.com/%s/%s
项目简介：把已经发生的一年，编译成一份值得晒出来的个人档案。接入麦当劳官方 MCP Server 的 6 个接口（历史订单 / 商城订单 / 官方餐品营养数据 / 积分账户 / 优惠券 / 抽奖奖品），把用户一年的点单史聚合成 Wrapped 式九屏个人年度报告——最爱单品 Top5、逐月进食曲线、累计热量趣味换算、深夜点餐画像、积分过期体检，以及数据驱动的 1024 程序员人格标签，产出为单文件自包含 HTML，可直接分享截图。同赛道项目多在「向前看」（下一餐怎么点、这单怎么省），本项目坚持「向后看」：不做一次决策，做一份年度档案与社交货币。工程上仅用 Python 标准库自实现 MCP Streamable HTTP 客户端，处理了订单数与件数口径分离、跨零点深夜时刻平均、餐品名与营养表三级匹配三个真实数据陷阱；用户数据本地处理，不经任何第三方服务器，仓库演示数据全部虚构脱敏。""" % (args.owner, args.repo)
        submit_issue(args.owner, args.repo, token,
                     "【参赛申请】麦麦年度报告 · McDonald's Annual Food Report",
                     issue_body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
