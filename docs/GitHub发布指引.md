# GitHub 发布指引（国内网络环境版）

本项目**全程可用 GitHub REST API 完成发布**，不需要能打开 `github.com` 主站。
（实测：`api.github.com` 始终可达；`github.com` 主站时通时不通，走代理时也可能被 502 拦下。）

---

## 零、最省事的做法：双击 `一键发布.cmd`

仓库根目录有 **`一键发布.cmd`**（Windows）。双击它，按提示填两项：

1. 你的 **GitHub 用户名**（github.com 主页上那个名字）
2. 你的 **GitHub Token**（`ghp_` 开头，粘贴时不显示是正常的）

然后什么都不用管了 —— 它会自动完成：

- 把仓库里所有 `vvvvv20252025` 占位符换成你的真实用户名
- 创建 Public 仓库 `mcd-annual-report`
- 上传全部文件（大文件自动走 Git Data API）
- 在官方仓库提交参赛 Issue
- 打印仓库地址与参赛 Issue 链接

> 替换前会自动把原始占位符版本备份到 `.placeholder_backup/`（已在 .gitignore 中，不会上传）。
> 万一用户名填错，从备份目录拷回对应文件即可复原。

macOS / Linux 用户请看下面第二节的手动命令。

---

## 一、前置：申请 GitHub Token

1. 打开 <https://github.com/settings/tokens>（若主站打不开，用下面的镜像入口）
2. 点 **Generate new token (classic)**
3. 勾选权限：
   - `repo`（必需，用于建仓库和上传文件）
   - `public_repo`（新仓库默认是 public，一般 `repo` 已包含）
4. 设置有效期（建议 30 天），点 **Generate token**
5. **复制 Token**（`ghp_...` 开头），只显示一次

> Token 等同于账号密码，**不要提交到 GitHub、不要发到群里**。

### 主站打不开时的备选入口

| 用途 | 镜像入口 | 实测 |
|------|----------|------|
| Token 申请 | <https://gh-proxy.com/https://github.com/settings/tokens> | ✅ 可用 |
| 浏览仓库 | <https://gh-proxy.com/https://github.com/> | ✅ 可用 |
| 备选 | <https://ghproxy.net/https://github.com/settings/tokens> | ⚠️ 时常 403 |

> 镜像只是代理，`api.github.com` 本身通常直连可达，**所有写操作都由脚本走 API 完成**，
> 不受镜像登录态影响。镜像只用来开页面拿 Token。

---

## 二、发布（一条命令）

```bash
# macOS / Linux / Git Bash
export GITHUB_TOKEN=ghp_你的Token
python scripts/publish_github.py --owner 你的GitHub用户名 --repo mcd-annual-report
```

```powershell
# Windows PowerShell
$env:GITHUB_TOKEN="ghp_你的Token"
python scripts\publish_github.py --owner 你的GitHub用户名 --repo mcd-annual-report
```

脚本会自动完成：

| 步骤 | API 调用 |
|------|----------|
| 校验 Token | `GET /user` |
| 创建 Public 仓库 | `POST /user/repos` |
| 上传全部文件 | `PUT /repos/{owner}/{repo}/contents/{path}` |
| 提交参赛 Issue | `POST /repos/M-China/mcd-developer-innovation-challenge/issues` |

上传的文件清单：

```
README.md  SKILL.md  LICENSE  CONTEST_DECLARATION.md  MCP_INTEGRATION.md
mcp-config.example.json  workbuddy.md  run.sh  .gitignore
scripts/mcp_fetch.py  scripts/aggregate.py  scripts/render_report.py
scripts/build_template.py  scripts/make_demo_data.py  scripts/make_architecture.py
scripts/publish_github.py  scripts/fill_placeholders.py  scripts/check_consistency.py
assets/report_template.html  examples/demo_raw.json
docs/architecture.png  docs/architecture.drawio  docs/引流文案.md
docs/GitHub发布指引.md
.workbuddy/memory/2026-10-22.md
readme-demo.gif
```

**只提交 Issue 不传文件**（文件已手动上传过时）：

```bash
python scripts/publish_github.py --owner 你的用户名 --repo mcd-annual-report --issue-only
```

---

## 三、提交后必做的三件事

### 1. 确认占位符已替换

一键脚本会自动替换并备份。若手动发布，用下面命令自查：

```bash
grep -rn "你的GitHub用户名\|你的姓名\|你的邮箱" . --include="*.md" --include="*.json"
```

> 应替换的文件：`README.md`（clone 地址与图片链接）、`CONTEST_DECLARATION.md`（参赛者信息）、
> `docs/引流文案.md`（各平台文案的仓库地址）、`docs/GitHub发布指引.md`（示例命令）。
> 占位符原版已备份在 `.placeholder_backup/`（不上传），拷回即可复原。

### 2. 数字一致性自检

```bash
python scripts/check_consistency.py
```

会实跑一遍 demo 管线，把结果里的关键数字回查 README 与模板；有任何对不上就报错退出。
**评审很可能自己跑一遍 demo，数字对不上是致命的低级错误** —— 改完文档务必跑一次。

### 2. 无痕窗口自检

用**未登录状态**打开仓库首页，确认：

- README 首屏 GIF 正常播放
- 架构图正常显示
- 5 个必需文件齐全：`README.md` / `CONTEST_DECLARATION.md` / `MCP_INTEGRATION.md` /
  `mcp-config.example.json` / `workbuddy.md`
- 全文搜索不到真实 Token（搜 `ghp_`、`Bearer ghp`、你的 Token 片段）

### 3. 确认 Issue 已创建

到 <https://github.com/M-China/mcd-developer-innovation-challenge/issues> 查看，
应有一条标题为「【参赛申请】麦麦年度报告 · McDonald's Annual Food Report」的 Issue。

> 官方 Issue 模板只有三行内容，脚本已按官方格式自动填充：
> ```
> 【参赛申请】
> 项目名称：麦麦年度报告 · McDonald's Annual Food Report
> 项目地址：https://github.com/<你的用户名>/mcd-annual-report
> 项目简介：接入麦当劳官方 MCP Server（...）...
> ```

---

## 四、常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `401 Bad credentials` | Token 无效/过期/权限不足 | 重新生成，确认勾了 `repo` |
| `404 Not Found`（创建仓库） | Token 属于无仓库权限的账号 | 检查 Token 的 scope |
| `422` 创建仓库 | 仓库名已存在 | 脚本会自动检测并跳过创建，直接上传 |
| 上传文件 `422` | 文件已存在 | 脚本会自动取 sha 后更新，无需手动处理 |
| `429` | API 限流（未认证 60 次/小时） | 等待或使用带认证的 Token（5000 次/小时） |
| 连不上 `api.github.com` | 网络阻断 | 开启代理后重试；脚本所有请求走标准 `urllib`，自动遵循 `HTTPS_PROXY` 环境变量 |
| Issue 创建失败 | 无 `public_repo` 权限 | 用 `--no-issue` 跳过，然后在活动页手动提交 |

---

## 五、代理设置（如需要）

```bash
# Git Bash / macOS / Linux
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
python scripts/publish_github.py --owner 你的用户名 --repo mcd-annual-report
```

```powershell
# PowerShell
$env:HTTPS_PROXY="http://127.0.0.1:7890"
python scripts\publish_github.py --owner 你的用户名 --repo mcd-annual-report
```

> 端口换成你实际使用的代理软件端口。

---

## 六、手动兜底方案（脚本完全不可用时）

1. **建仓库**：镜像打开 <https://ghproxy.net/https://github.com/new>，填仓库名 `mcd-annual-report`，
   勾选 Public，勾选 README。
2. **传文件**：把仓库文件夹里的文件按目录结构拖到 GitHub 网页的「Add file → Upload files」，
   一次最多 100 个文件、单个 ≤100MB，本项目文件量完全够用。
3. **提 Issue**：镜像打开活动的 issues 页面 → New issue → 选参赛模板 → 粘贴三行内容。
