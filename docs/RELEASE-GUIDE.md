# 哔哩哔哩视频提取：新电脑接手与发布指南

更新于 2026-10-31。本文是本项目的操作入口；网站通用规则另见[网站接手指南](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#website)、[卡片机制](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#catalog)、[发布顺序](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#client-update)、[验证与回滚](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#verify-rollback)和[凭证](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#credentials)。以下命令用于**以后获得发布授权的操作员**；本次只写文档，没有执行生产上传、切换清单或网站部署。

## 1. 仓库、版本与新电脑

- 源码仓库：`https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop.git`，默认 `master`。2026-10-31 核对时没有本仓库 GitHub Actions 工作流或 Pages；源码推送不会自动修改 OSS 客户端清单或下载站。先确认远端状态，不强推、不覆盖他人提交。
- 正式稳定版是 [v1.0.4](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/releases/tag/v1.0.4)，标签提交 `8ef06c1bb9e4551dea7b31c8f67560c347c7f0ca`；应用内 `version.json` 是 `1.0.4`。`master` 在标签之后可有文档提交，不能据此声称二进制已更新。
- [v1.0.4-startup-diagnostics](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/releases/tag/v1.0.4-startup-diagnostics) 是非 Latest 诊断预发布，源码提交 `8bc22b97d6c87e8b61675428a8969f9c2f98cb3b`，应用版本也仍是 `1.0.4`。它只改启动异常日志/提示，不是 v1.0.5，不得替换正式包或写入生产清单。

```powershell
git clone https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop.git
Set-Location .\bilibili-video-extractor-desktop
git fetch --tags origin
git status --short --branch
git ls-remote --heads origin master codex/startup-diagnostics
git show v1.0.4:version.json  # 核对正式标签；后续开发从已核实的 master 建独立分支
```

新电脑需要 Windows x64、Git、Python 3.13 x64、Windows PowerShell 5.1、可用的 .NET Framework C# 编译器、Playwright Chromium、FFmpeg，以及有权限时的 GitHub CLI。2026-10-31 已验证的**本机快照**是 Python 3.13.15、.NET Framework 4.8.1（注册表 Release `533325`）、PyInstaller 6.22.3、Playwright 1.63.0（Chromium 目录 `chromium-1243`）、pywebview 6.2.1、pythonnet 3.1.0、yt-dlp 2026.8.19、FastAPI 0.141.1、Jinja2 3.1.6、uvicorn 0.53.0、openpyxl 3.1.5、FFmpeg 9.0.1。`requirements.txt` 使用范围而非锁文件；**无法仅靠这些命令保证跨电脑依赖逐字节一致**，新机要记录 `pip freeze`、浏览器修订号和 FFmpeg 哈希。正式 v1.0.4 包是 2026-09-24 的构建，不应把本机快照冒充当时的精确构建环境。

```powershell
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python.exe -m playwright install chromium
ffmpeg -version
New-Item -ItemType Directory -Path .\build -Force | Out-Null
.\.venv\Scripts\python.exe -m pip freeze > .\build\dependency-snapshot.txt  # build/ 被 Git 忽略
.\Start-Dev.cmd
```

仓库另有 `Setup-Dev.cmd`，会用 `py -3` 建环境并装依赖/Chromium；机器上有多个 Python 3 时，先确认其实际选择的解释器。测试与构建用 `powershell.exe`（Windows PowerShell 5.1），而不是 PowerShell 7 的 `pwsh`：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
foreach ($kind in 'Manifest','Hash','PackageValidation','Transaction','Launcher','PackageLayout') {
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test $kind
  if ($LASTEXITCODE -ne 0) { throw "Updater test failed: $kind" }
}
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` 接受 `-BrowserRoot <Playwright 浏览器目录>`、`-FfmpegExe <ffmpeg.exe 完整路径>`，或同义环境变量 `BILIBILI_PLAYWRIGHT_BROWSERS_PATH`、`BILIBILI_FFMPEG_EXE`；默认浏览器目录是 `%LOCALAPPDATA%\ms-playwright`，FFmpeg 默认从 `PATH` 查找。脚本会**删除并重建本仓库** `build/portable-release` 与 `dist/`，运行前确认其中没有需保留的产物。其输出目录是 `dist/哔哩哔哩视频提取/`，根下必须有 `Start-App.cmd`、`updater/`、`app/`。`updater-src/build-updater.ps1 -OutputPath <路径>` 会寻找 Windows 的 `Framework64/Framework/v4.0.30319/csc.exe`；编译器缺失需先修复构建机环境。

桌面用户数据在 `%LOCALAPPDATA%\哔哩哔哩视频提取\`：`browser_session/`、`data/bilibili_extractor.db`、`desktop.log`。**不要把这些目录、下载的视频、Cookie、个人配置或构建机日志复制到仓库/ZIP/另一台电脑**。Chromium 登录态可能受 Windows 用户/机器加密保护，不能当作可分发资料；新机由使用者重新扫码。若确需迁移业务数据库，先得到用户授权并做独立备份、停机与兼容性验证；本文没有经过验证的数据库迁移脚本。`desktop_app.py` 会从 `LOCALAPPDATA` 建数据路径并覆盖 `BILIBILI_EXTRACTOR_DATA`，隔离桌面测试需设置**测试进程**的 `LOCALAPPDATA`。

## 2. 生成下一正式版本的两种包

版本号的唯一源码入口是根目录 `version.json`；`build.ps1` 把它复制到 `app/version.json`。以后选定新版本时，先改源码、测试并提交；新版的 Git 标签、完整包名、更新包名、OSS 路径和清单 `version` 必须一致。**不要修改 v1.0.4 标签、Release 附件或同名 OSS 对象。** 本仓库没有一键生成 ZIP、上传 OSS 或发布网站的受控脚本，以下是 Windows PowerShell 5.1 的手工打包示例，运行前用新版本替换源码并重建：

```powershell
$version = (Get-Content .\version.json -Raw | ConvertFrom-Json).version
$releaseRoot = (Resolve-Path '.\dist\哔哩哔哩视频提取').Path
$artifactRoot = Join-Path (Get-Location) "release-artifacts\$version"
if (Test-Path -LiteralPath $artifactRoot) { throw "Artifact directory exists: $artifactRoot" }
New-Item -ItemType Directory -Path $artifactRoot | Out-Null
$fullZip = Join-Path $artifactRoot "bilibili-video-extractor-desktop-$version-windows-x64.zip"
$updateZip = Join-Path $artifactRoot "bilibili-video-extractor-desktop-update-$version.zip"
$env:BILIBILI_RELEASE_ROOT = $releaseRoot
$env:BILIBILI_FULL_ZIP = $fullZip
$env:BILIBILI_UPDATE_ZIP = $updateZip
$env:BILIBILI_VERSION = $version
@'
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(os.environ['BILIBILI_RELEASE_ROOT'])
files = sorted(p for p in root.rglob('*') if p.is_file())
required = ('Start-App.cmd', 'updater/UpdateAgent.exe', 'app/version.json')
if not all((root / name).is_file() for name in required):
    raise SystemExit('release layout is incomplete')
if json.loads((root / 'app/version.json').read_text(encoding='utf-8'))['version'] != os.environ['BILIBILI_VERSION']:
    raise SystemExit('built app version differs from source version')
for path in files:
    rel = path.relative_to(root)
    if rel.parts[0] not in {'Start-App.cmd', 'app', 'updater'}:
        raise SystemExit(f'unexpected release root: {rel}')
    if any(part.lower() in {'data', 'browser_session', 'logs'} for part in rel.parts) or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.log', '.env', '.pem', '.key'}:
        raise SystemExit(f'user data or secret-like file: {rel}')
with ZipFile(os.environ['BILIBILI_FULL_ZIP'], 'w', ZIP_DEFLATED, compresslevel=6, allowZip64=True) as full, \
     ZipFile(os.environ['BILIBILI_UPDATE_ZIP'], 'w', ZIP_DEFLATED, compresslevel=6, allowZip64=True) as update:
    for path in files:
        rel = path.relative_to(root)
        name = rel.as_posix()
        full.write(path, name)
        if rel.parts[0] == 'app':
            update.write(path, name)
'@ | .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'ZIP creation failed' }
Get-FileHash -Algorithm SHA256 -LiteralPath $fullZip,$updateZip | Format-Table Path,Hash
py -3.13 -m zipfile -t $fullZip
py -3.13 -m zipfile -t $updateZip
```

完整 ZIP 的根只能是供用户使用的 `Start-App.cmd`、`updater/`、`app/`；更新 ZIP **只能包含 `app/`**，内有单个 EXE、`_internal/`、`ms-playwright/`、`tools/ffmpeg/bin/ffmpeg.exe`、`使用说明.md`、`version.json`。更新器 `Updater.ValidatePackage` 逐条检查布局、重复/越界路径和版本；不能把完整包网址写进更新清单。对两个 ZIP 做 CRC、目录清单、敏感内容与 SHA-256 检查，并从完整包解压副本用隔离 `LOCALAPPDATA` 启动。浏览器下载包若带 Windows `Zone.Identifier`，核对来源与哈希后先对 ZIP「解除锁定」再重新解压；已确认的另一台电脑启动故障由此恢复。不要全局关闭下载保护。

## 3. 客户端更新、OSS 和 GitHub Release

`Start-App.cmd` 调 `updater/UpdateAgent.exe --check updater/updater-config.json`，然后尝试启动 `app/*.exe`；更新检查失败也会尝试启动旧程序。模板 `updater-src/updater-config.json` 的**公开只读** `manifestUrl` 指向：

`https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/bilibili-video-extractor-desktop/latest.json`

对应 OSS bucket `luotuoruanjiangengx`、北京地域，当前 `latest.json` 的真实字段仅为 `version`、`url`、`sha256`。`url` 必须是 HTTPS **仅含 `app/` 的更新 ZIP**；清单和 ZIP 请求都禁用 HTTP 跳转、要求直接返回 200，超时设置为 30 秒。SHA-256 是更新 ZIP 的哈希，不是完整包哈希。更新器只在远端版本高于本地时更新，先验哈希/ZIP/版本，再以 `app.previous` 短暂备份替换 `app/`；成功后删备份，失败时尝试恢复。**既有安装只更新 `app/`，不会更换 `Start-App.cmd` 或 `updater/`**；如果下一版需改启动器/更新器，必须另设计兼容旧安装的迁移或引导用户安装新完整包。当前公开清单为 v1.0.4，更新 ZIP 哈希 `033031844707EB53F089C6C42CAA668C18672F0BF36AA90504311BB7A17E8AB1`。

新版本的**不可变对象 key 模板**：

| 用途 | OSS key / GitHub 位置 |
| --- | --- |
| 完整包 | `packages/bilibili-video-extractor-desktop/<version>/bilibili-video-extractor-desktop-<version>-windows-x64.zip` |
| 更新载荷 | `updates/bilibili-video-extractor-desktop/releases/<version>/bilibili-video-extractor-desktop-update-<version>.zip` |
| 生产更新指针 | `updates/bilibili-video-extractor-desktop/latest.json` |
| GitHub 备用完整包 | 本源码仓库的新 `v<version>` Release 附件；不覆盖旧 Release |

发布顺序：①确定代码提交/新版本并完成测试与两包审计；②用有该 bucket 与本产品 prefix 权限的 OSS 控制台或经验证的外部上传工具，上传**新 key** 的完整包和更新包，上传后从公网重新下载并验大小、哈希；③新建 Git 标签和 GitHub Release，上传完整包并回读哈希；④用**非生产验收清单**和旧版安装副本，在隔离 `LOCALAPPDATA` 下验证 `Start-App.cmd` 升级及故障回滚；⑤保存旧 `latest.json` 内容/哈希后，最后原子地切换生产 `latest.json`，再次公网回读；⑥下载站的静态卡片确认完整包已可下载后再改版号和链接。每一步失败都保留旧版入口并停止后续切换。

GitHub CLI 的将来发布示例（**本轮未执行**；假定已审查并正常合并到本地 `master`，且远端 HEAD 未漂移；先核对待发布提交，无强推）：

```powershell
$version = (Get-Content .\version.json -Raw | ConvertFrom-Json).version
$fullZip = Join-Path (Get-Location) "release-artifacts\$version\bilibili-video-extractor-desktop-$version-windows-x64.zip"
if ((git branch --show-current).Trim() -ne 'master') { throw 'Review and merge into master before tagging' }
if (-not (Test-Path -LiteralPath $fullZip)) { throw "Missing full ZIP: $fullZip" }
$commit = (git rev-parse HEAD).Trim()
git push origin master
git tag "v$version" $commit
git push origin "v$version"
gh release create "v$version" "$fullZip" --repo nmrsz645-bit/bilibili-video-extractor-desktop --verify-tag --title "哔哩哔哩视频提取 v$version" --notes "Windows x64 完整包；SHA-256 请以本次核对结果为准。"
```

上述 `--notes` 是占位说明，正式发布需填入**实测 SHA-256、改动、验证与限制**。本仓库没有 OSS 上传脚本；不要套用其他产品的脚本或假设本机忽略的 `build/tools/` 可在新机使用。手工上传时在 OSS 控制台选择上述 bucket/key，核对 HTTPS 公网可读；新清单 JSON 形如 `{"version":"<version>","url":"https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/bilibili-video-extractor-desktop/releases/<version>/bilibili-video-extractor-desktop-update-<version>.zip","sha256":"<更新ZIP的64位SHA-256>"}`。必须先完成隔离升级验收，再写生产 `latest.json`；这里的占位值不可直接发布。

## 4. 下载站上架与核验

网站仓库是 `https://github.com/nmrsz645-bit/software-download-center.git`，Pages 来源是其 `main` 分支根目录，域名 `https://download.luotuoqiluotuozhaoma.com/`。**本项目卡片没有 `id`**；在该仓库 `index.html` 搜索标题 `<h3>哔哩哔哩视频提取</h3>`。其相邻 `.meta` 当前写 v1.0.4，下一条 `<a class="download">` 静态指向上述 OSS 完整包 key。当前页面没有针对本项目的 `latest.js`、站内 JSON 或 catalog 读取器；更新客户端 `latest.json` **不会自动刷新网站卡片**。未来上架应由网站负责人仅在该卡片更新 `.meta` 版号、按钮文案和完整包 `href`，审查后正常提交到网站 `main`；其文档分支不会发布网页。网站仓库根下的 `updates/` 目前也不是本项目更新清单的来源。网站新机接手时执行 `git clone https://github.com/nmrsz645-bit/software-download-center.git`，在该仓库用 `Select-String -Path .\index.html -Pattern '哔哩哔哩视频提取' -Context 4,5` 定位卡片；真正推 `main` 前再核实 Pages 来源和远端 HEAD。

发布后分别核对：源码远端提交/标签与 `version.json`；GitHub Release 与 OSS 两个完整包、OSS 更新包的公网下载哈希；公网 `latest.json` 的三字段与更新 ZIP 一致；带随机查询参数打开下载站，读到正确卡片文字/完整包 URL 并实际下载验哈希；在**旧版本副本**中运行根目录 `Start-App.cmd`，确认升级后 `app/version.json` 和功能可用、隔离用户数据哈希不变，再模拟失败载荷验证保留旧版。直接启动 `app/*.exe` 不能验证更新。页面 HTTP 200、源代码推送或新 Release 本身均不能证明客户端已升级；业务在线接口还要另做实时验收。

回滚：在生产清单切换前停止即可让旧版继续使用。切换后若发现问题，先保留所有旧包和旧清单，恢复先前已验证的 `latest.json` 可阻止**尚未升级**的客户端获取问题版；更新器只接受更高版本，**不会让已升级客户端自动降级**。成功更新后 `app.previous` 已删除；受影响设备需经授权从可信旧完整包恢复，或发布更高版本修复，并保护 `%LOCALAPPDATA%` 数据。网站卡片可单独恢复其上一版已验证链接；网站回滚不等于客户端回滚。

## 5. 权限、缺项与停止条件

- GitHub：用 `gh auth login` 的交互登录或 Git Credential Manager 获取**本仓库**写权限；网站另需网站仓库的最小分支权限。不要把 PAT、SSH 私钥或凭据文件写入仓库/文档/包。
- OSS：本仓库只保存公开 `manifestUrl`，**没有 OSS 凭证配置名或上传脚本**。由获得授权的操作员从 OSS 控制台登录，或从所有者批准的短时 STS/OIDC 环境取得最小权限凭据；不要在命令历史、聊天、仓库、ZIP 中记录 AccessKey/Token。只开放本产品 prefix 的必要上传、读取与清单写入权限。
- 未具备/未验证：本仓库包含核心程序源码，但不包含下载站源码（在上文的公开网站仓库）、OSS 服务端源码或可复制的 OSS 上传自动化；没有依赖锁文件、正式包构建机全量精确快照、数据库跨机迁移脚本。新机 .NET/Chromium/FFmpeg 环境、实际 Pages 部署与 OSS 写权限需发布人现场核验；哔哩哔哩实时接口、另一台新电脑打包结果、下一版本旧版升级尚未在本次文档工作中验证。发现远端提交漂移、哈希不符、包含用户数据或验收失败时停止发布，先保留证据与旧版。
