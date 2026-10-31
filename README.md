# 哔哩哔哩视频提取

独立的 Windows x64 桌面程序，可提取 UP 主投稿、关键词/话题搜索结果和单个视频的信息，导出 XLSX，并下载当前登录账号可获取的最高画质视频。它不读取或写入旧抖音程序的数据。

**正式版：v1.0.4。** [源码标签](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/tree/v1.0.4)对应提交 `8ef06c1`；[GitHub Release](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/releases/tag/v1.0.4)提供 Windows 完整包。该 ZIP 的 SHA-256 是 `20CE45C39979986608535E1A87DF99199BCE6037004731D1CFCECD79E1FE6C80`。本文件后续的文档修订不改变已发布的 v1.0.4 二进制内容。新电脑接手、更新推送与网站上架先读 [RELEASE-GUIDE.md](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/blob/master/docs/RELEASE-GUIDE.md)，再读 [HANDOFF.md](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/blob/master/HANDOFF.md)。

## 下载、安装与启动

1. 从上述 Release 下载 `bilibili-video-extractor-desktop-1.0.4-windows-x64.zip`。这是完整包，不是仅供自动更新器使用的更新 ZIP。
2. 建议在 PowerShell 核对下载文件：`(Get-FileHash -Algorithm SHA256 '下载的ZIP完整路径').Hash`，应与上面的哈希一致。
3. 浏览器下载的 ZIP 若在「右键 → 属性 → 常规」底部显示「解除锁定」，在确认来源和哈希后先解除锁定、应用，**再完整解压到新文件夹**。若已解压，解除 ZIP 锁定后需要重新解压；不要关闭系统下载安全保护。Windows 的下载文件标记可能阻止包内的 .NET 程序集加载。
4. 双击解压目录**根目录**的 `Start-App.cmd`。不要只复制或直接运行 `app/` 内的 EXE；那样不会进行启动前更新检查。保持 `app/`、`updater/` 和 `Start-App.cmd` 的相对位置。

启动器通过 HTTPS 清单检查新版本、校验更新 ZIP 的 SHA-256 和目录布局，再替换 `app/`；失败时更新器尝试恢复旧版。用户数据不在安装目录，默认位于 `%LOCALAPPDATA%\哔哩哔哩视频提取\`，包括 `browser_session/` 登录资料、`data/bilibili_extractor.db` 数据库和 `desktop.log`。换包或排查问题时不要清空这些目录。

## 首次配置

- 程序自带用于网页提取的 Chromium、下载用的 yt-dlp 和音视频合并用的 FFmpeg。使用完整包时无需单独配置哔哩哔哩 API Key。
- 需要账号权限的资料或画质时，在窗口右上角点「扫码登录哔哩哔哩」，在弹出的浏览器完成扫码。登录状态保存在本程序独立的 `browser_session/` 中，不会从其他程序复制。
- 「清空浏览器缓存」会删除本程序的登录状态，只有明确要重新登录时才使用。普通提取失败不需要先清缓存。

## 主要操作

### UP 主作品

在「UP主提取」页每行粘贴一个 `https://space.bilibili.com/<MID>` 主页链接，点「添加UP主主页」。资料未读取的作者可用「一键读取未读取资料」重试。设置完整的开始/结束时间，或填「最新前」1～1000 条（两种筛选方式互斥），再点「全部提取」。结果即时出现，并按添加 UP 主的顺序排列；同一作者内按发布时间排列。「清空UP主列表」还会清空相关作品结果，请确认后使用。

### 关键词或话题

在「话题提取」页输入关键词、`#话题名` 或哔哩哔哩话题/搜索页链接；设置完整时间范围和最多 1～1000 条，再开始提取。页面会即时显示符合条件的结果。

### 单作品

在「单作品提取」页每行放一个视频链接，也可粘贴包含链接的整行分享文案；支持 `bilibili.com` 和 `b23.tv`。一次最多 1000 行，重复链接按输入行分别保留。无效链接会使这次提交被拒绝；请修正后再开始。

### 暂停、导出、下载

三个**提取**任务运行时可点「暂停提取」，再点「继续提取」。暂停在当前网页请求结束后的安全检查点生效，进度显示「正在暂停」或「已暂停」；关闭程序后无法续跑。此按钮**不暂停视频下载**。

有结果后点「导出 XLSX」并在另存为窗口选择位置。下载时勾选结果行，点「下载勾选视频」并选择保存文件夹；下载使用当前账号可访问的画质，FFmpeg 合并音视频，多 P 命名为 `标题 - P01.mp4`、`标题 - P02.mp4` 等。下载任务完成或失败后界面会显示状态。

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| 启动弹窗称缺少 .NET Framework，安装后仍失败；日志出现 `Failed to resolve Python.Runtime.Loader.Initialize` | v1.0.4 会把多种桌面组件错误误写成 .NET 缺失。先核对下载 ZIP 的哈希；对可信 ZIP 在「属性」中解除锁定，重新解压到新文件夹再运行 `Start-App.cmd`。此问题已在另一台 Windows 电脑上通过该步骤解决。[微软解释了下载文件标记对 .NET 程序集的影响](https://learn.microsoft.com/en-us/dotnet/framework/configure-apps/file-schema/runtime/loadfromremotesources-element)。不要反复安装同一运行库。 |
| UP 主资料未读取，接口返回 `-352` | 打开本程序的扫码登录窗口完成登录，再点「一键读取未读取资料」。平台接口也可能临时限制访问，稍后重试。 |
| 找不到 FFmpeg、只有音频或视频半成品 | 使用完整 ZIP 并保持 `app/tools/ffmpeg/bin/ffmpeg.exe`；不要只复制 EXE。 |
| 自动更新失败或新包无法启动 | 保留安装目录和用户数据，重新运行根目录 `Start-App.cmd`，检查网络、清单和 ZIP 校验；不要把完整包当作更新载荷。记录报错后联系维护者。 |
| 需要诊断启动错误 | 正式 v1.0.4 的早期 .NET 检查可能不留下完整日志。[启动诊断预发布](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/releases/tag/v1.0.4-startup-diagnostics)基于 [`codex/startup-diagnostics` 源码分支](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/tree/codex/startup-diagnostics)，可记录原始异常，但**不是正式版更新**。分享日志前可遮住个人路径等信息。 |

## 开发与验证

开发环境需 Python 3、Windows、Playwright Chromium 和 FFmpeg。执行 `Setup-Dev.cmd` 创建 `.venv` 并安装 `requirements.txt` 与 Chromium；再执行 `Start-Dev.cmd`。构建时另需在 `.venv` 中安装 PyInstaller，并让 `ffmpeg.exe` 在 `PATH` 中，或设置 `BILIBILI_FFMPEG_EXE`。`build.ps1` 默认从 `%LOCALAPPDATA%\ms-playwright` 读取浏览器；可用 `BILIBILI_PLAYWRIGHT_BROWSERS_PATH` 指向已安装的 Chromium 目录。不要把本机浏览器资料、数据库或日志放进 Git 或发布包。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Manifest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`test_updater.ps1` 还支持 `Hash`、`PackageValidation`、`Transaction`、`Launcher`、`PackageLayout`。其中 `PackageLayout` 会构建发布目录；`build.ps1` 会重建仓库内的 `build/portable-release` 与 `dist/`，运行前先确认没有需要保留的本地构建产物。正式发布、升级载荷及其验证步骤见 [HANDOFF.md](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/blob/master/HANDOFF.md)。
