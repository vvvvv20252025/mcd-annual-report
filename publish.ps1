﻿﻿﻿# ============================================================
#  麦当劳 x WorkBuddy 大赛 - 一键发布到 GitHub
#  用法：右键本文件 -> "使用 PowerShell 运行"
#        或在 PowerShell 里执行：  .\一键发布.ps1
#  按提示填两样东西即可完成：
#    1) 你的 GitHub 用户名
#    2) 你的 GitHub Token（ghp_ 开头）
#  其余全自动：替换占位符 -> 建仓库 -> 上传文件 -> 提交参赛 Issue
# ============================================================

$ErrorActionPreference = "Continue"

# 控制台强制 UTF-8，避免中文在旧版 PowerShell 里乱码
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# 路径含 [ ] 空格时必须用 -LiteralPath，否则 Set-Location 会失败
if (-not (Test-Path -LiteralPath $PSScriptRoot)) {
    Write-Host "[X] 无法定位脚本所在目录：$PSScriptRoot" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}
Set-Location -LiteralPath $PSScriptRoot

function Write-Line($msg, $color = "Gray") {
    Write-Host $msg -ForegroundColor $color
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkYellow
Write-Host "  麦当劳 x WorkBuddy 大赛 - 一键发布" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor DarkYellow
Write-Host ""

# ---------- 1. 检查 Python ----------
$py = $null
foreach ($cand in @("python", "python3", "py")) {
    if ($py) { break }
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cand }
}
if (-not $py) {
    Write-Host "[X] 没找到 Python。" -ForegroundColor Red
    Write-Host "    请先安装 Python 3.8+： https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "    安装时务必勾选 Add Python to PATH。" -ForegroundColor Red
    Write-Host ""
    Read-Host "按回车退出"
    exit 1
}
Write-Host "[OK] Python: $py" -ForegroundColor Green

# ---------- 2. 用户名 ----------
Write-Host ""
$GH_USER = Read-Host "请输入你的 GitHub 用户名（github.com 主页上的那个名字）"
if (-not $GH_USER.Trim()) {
    Write-Host "[X] 用户名不能为空。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}
Write-Host "[OK] 用户名: $GH_USER" -ForegroundColor Green

# ---------- 3. Token ----------
Write-Host ""
Write-Host "请到 https://github.com/settings/tokens 申请 Token：" -ForegroundColor Cyan
Write-Host "  1) 点 Generate new token (classic)"
Write-Host "  2) 勾选 repo 权限"
Write-Host "  3) 拉到底点 Generate token"
Write-Host "  4) 复制那串 ghp_ 开头的字符（只显示一次）"
Write-Host ""
$GH_TOKEN = Read-Host "粘贴你的 Token（粘贴后回车，屏幕上不显示属正常）"
if (-not $GH_TOKEN.Trim()) {
    Write-Host "[X] Token 不能为空。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# ---------- 4. 可选：姓名与邮箱 ----------
Write-Host ""
$GH_NAME  = Read-Host "参赛者姓名（可留空，直接回车跳过）"
$GH_EMAIL = Read-Host "联系邮箱（可留空，直接回车跳过）"

# ---------- 5. 替换占位符 ----------
Write-Host ""
Write-Host "[..] 正在替换仓库里的占位符 ..." -ForegroundColor Cyan
if ($GH_NAME.Trim() -and $GH_EMAIL.Trim()) {
    & $py scripts\fill_placeholders.py --username $GH_USER --name "$GH_NAME" --email "$GH_EMAIL"
} elseif ($GH_NAME.Trim()) {
    & $py scripts\fill_placeholders.py --username $GH_USER --name "$GH_NAME"
} else {
    & $py scripts\fill_placeholders.py --username $GH_USER
}

# ---------- 6. 发布 ----------
Write-Host ""
Write-Host "[..] 正在发布到 GitHub（建仓库 + 上传文件 + 提交参赛 Issue）..." -ForegroundColor Cyan
Write-Host ""
$env:GITHUB_TOKEN = $GH_TOKEN.Trim()
& $py scripts\publish_github.py --owner $GH_USER --repo mcd-annual-report
$rc = $LASTEXITCODE

Write-Host ""
if ($rc -eq 0) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  发布成功" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  仓库地址  : https://github.com/$GH_USER/mcd-annual-report" -ForegroundColor Green
    Write-Host "  参赛Issue : https://github.com/M-China/mcd-developer-innovation-challenge/issues" -ForegroundColor Green
    Write-Host ""
    Write-Host "  接下来建议做三件事：" -ForegroundColor Yellow
    Write-Host "    1. 用无痕窗口打开仓库首页，确认 README 首屏 GIF 能播放"
    Write-Host "    2. 在仓库里搜 ghp_ ，确认没有泄露 Token"
    Write-Host "    3. 给仓库点个 Star，并在 README 贴上自己的截图"
    Write-Host ""
} else {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  发布未完成（退出码 $rc）" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  常见原因：" -ForegroundColor Yellow
    Write-Host "    - Token 过期或没勾 repo 权限 -> 重新申请"
    Write-Host "    - 网络问题 -> 稍后重试，或开启代理后重跑"
    Write-Host "  详细排查见 docs\GitHub发布指引.md"
    Write-Host ""
}

Read-Host "按回车退出"
