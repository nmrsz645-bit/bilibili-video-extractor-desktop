# 下一位 Codex：哔哩哔哩视频提取交接

更新于 2026-10-31。先读 [README.md](README.md) 的用户操作与常见错误；新电脑接手、更新与网站发布以 [docs/RELEASE-GUIDE.md](docs/RELEASE-GUIDE.md) 为入口，再看本文件。这里记录的是已核实的仓库状态；历史设计文件在 `docs/superpowers/`，不能代替当前源码和发布验证。

## 1. 用途、当前版本与边界

- 独立 Windows x64 工具：UP 主投稿、关键词/话题、单作品提取；SQLite 保存结果；XLSX 导出；yt-dlp/FFmpeg 下载当前登录账号可访问的画质。旧抖音项目只能参考，不能读写其用户数据。
- **正式程序仍为 v1.0.4**，`version.json`、Git 标签 `v1.0.4`、正式源码提交 `8ef06c1bb9e4551dea7b31c8f67560c347c7f0ca`。对应 [GitHub Release](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/releases/tag/v1.0.4) 的 Windows 完整包 `bilibili-video-extractor-desktop-1.0.4-windows-x64.zip`：486,354,789 字节，SHA-256 `20CE45C39979986608535E1A87DF99199BCE6037004731D1CFCECD79E1FE6C80`。文档提交在标签之后，不代表正式二进制已重建。
- 另有 [`codex/startup-diagnostics`](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/tree/codex/startup-diagnostics) 分支，提交 `8bc22b97d6c87e8b61675428a8969f9c2f98cb3b`，仅改进启动异常日志与提示。[v1.0.4-startup-diagnostics](https://github.com/nmrsz645-bit/bilibili-video-extractor-desktop/releases/tag/v1.0.4-startup-diagnostics) 是非 Latest 诊断预发布，**未合入 `master`、未打正式新版本、未替换 v1.0.4 Release**。不要把诊断包或该分支称作 v1.0.5。
- GitHub 仓库是现有公开仓库 `nmrsz645-bit/bilibili-video-extractor-desktop`；保持原有可见性。`master` 不含 GitHub Actions 工作流，生产自动更新取自独立 OSS HTTPS 清单；推送源码本身不是生产发布。

## 2. 架构与关键文件

`Start-App.cmd` → `updater/UpdateAgent.exe`（先检查远端版本）→ `app/哔哩哔哩视频提取.exe` → `desktop_app.py` 启动本机随机端口 FastAPI 服务和 pywebview 桌面窗口 → `web/app.py` 路由/任务状态 → Playwright 持久浏览器访问哔哩哔哩 → SQLite/XLSX/下载器。

| 路径 | 作用与修改入口 |
| --- | --- |
| `desktop_app.py`、`config.py` | 桌面启动、数据目录、Chromium/FFmpeg 路径；启动异常在这里处理。正式 v1.0.4 的错误提示过于笼统，诊断分支对此有改动。 |
| `web/app.py`、`web/templates/`、`web/static/` | 三页界面，扫码登录、添加作者、提取/暂停、导出和下载 API。页面状态在进程内，关闭窗口后不能恢复正在运行的任务。 |
| `bilibili_client.py`、`pause_control.py` | Playwright 网页/接口读取，保留 BVID 大小写；三个提取任务的暂停检查点。 |
| `db.py` | SQLite 表、旧结果迁移、作者添加顺序与单作品输入行顺序。重复单作品链接可占多行。 |
| `downloader.py` | yt-dlp 最高可获取画质、临时 Cookie 文件、FFmpeg 合并与多 P 命名。暂停按钮不控制下载。 |
| `updater-src/UpdateAgent.cs`、`updater-src/updater-config.json`、`Start-App.cmd` | HTTPS manifest/SHA-256/ZIP 布局校验、`app/` 替换和回滚；当前启动脚本在更新器返回失败后仍尝试启动现有 EXE。 |
| `build.ps1`、`test_updater.ps1`、`tests/` | PyInstaller 发布构建、更新器分项测试及 Python 回归测试。 |

## 3. 用户数据与安全配置

- 正式桌面版在 `%LOCALAPPDATA%\哔哩哔哩视频提取\` 保存 `browser_session/` 登录态、`data/bilibili_extractor.db`、`desktop.log`。**不要为了测试删除、重置或打包这些目录**。构建产物及测试数据只放隔离路径；不强制结束用户正在运行的程序。
- `config.py` 可在单独导入 Web/API 时读取 `BILIBILI_EXTRACTOR_DATA`；但 `desktop_app.py` 启动时会根据 `LOCALAPPDATA` 设置自己的数据目录并覆盖该变量。需要隔离桌面 EXE 测试时，应在测试进程中设置隔离的 `LOCALAPPDATA`，不要假设仅设置 `BILIBILI_EXTRACTOR_DATA` 有效。
- **无需哔哩哔哩 API Key。** 登录资料由界面右上角「扫码登录哔哩哔哩」在本机生成。不得把账号、Cookie、浏览器 profile、真实 `.env`、下载文件或数据库提交到 Git；`browser_session/`、`data/`、日志和构建目录已在 `.gitignore` 中。
- 仓库唯一发布配置模板是 `updater-src/updater-config.json`，其 `manifestUrl` 是公开 HTTPS 地址，无密码：`https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/bilibili-video-extractor-desktop/latest.json`。若换存储服务，先由发布所有者提供新的**公开只读**清单地址，再修改模板；写入凭证只能从所有者授权的安全环境取得，不能放进仓库或交接文件。GitHub 推送使用有该仓库权限的 `gh`/Git 凭据，不扩大权限。
- `BILIBILI_PLAYWRIGHT_BROWSERS_PATH` 指向本机已安装的 Playwright Chromium 目录（`build.ps1` 默认读 `%LOCALAPPDATA%\ms-playwright`）；`BILIBILI_FFMPEG_EXE` 指向本机 `ffmpeg.exe` 供构建复制。分别通过 `python -m playwright install chromium` 与可信 FFmpeg 安装取得，不要使用其他产品的浏览器 profile。运行包会优先使用自带的 `app/ms-playwright/` 和 `app/tools/ffmpeg/bin/`。

## 4. 环境、开发、测试、打包

当前本机开发环境快照：Windows 10 x64，Python 3.13.15，PyInstaller 6.22.3，Playwright 1.63.0，pywebview 6.2.1，pythonnet 3.1.0，yt-dlp 2026.8.19，FastAPI 0.141.1，uvicorn 0.53.0，openpyxl 3.1.5。`requirements.txt` 用版本范围，**没有锁文件**；这些是 2026-10-31 本机值，不保证就是 2026-09-24 正式包的全部精确依赖。构建更新器需 Windows PowerShell 5.1 和本机 .NET Framework C# 编译器。

```powershell
# Windows PowerShell；首次开发环境。Setup-Dev.cmd 会创建 .venv、装依赖和 Chromium。
.\Setup-Dev.cmd
.\Start-Dev.cmd

# 单元/接口回归测试；测试使用隔离夹具，不依赖真实登录。
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 更新器各项测试必须由 powershell.exe (Windows PowerShell 5.1) 执行。
foreach ($kind in 'Manifest','Hash','PackageValidation','Transaction','Launcher','PackageLayout') {
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test $kind
  if ($LASTEXITCODE -ne 0) { throw "Updater test failed: $kind" }
}

# 安装 PyInstaller 并确保 Chromium、FFmpeg 路径满足 build.ps1 后再构建。
.\.venv\Scripts\python.exe -m pip install pyinstaller
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` 会删除并重建**仓库内** `build/portable-release` 和 `dist/`；先确认这些是可替换的本地构建产物。不要把构建根目录重定向到用户数据。此脚本产出发布目录，不自动生成 GitHub Release 或线上更新 ZIP。正式 v1.0.4 的 GitHub 安装包已存在，不应同名重建并替换。

## 5. 发布与升级边界

- **GitHub 交付**：核对 `version.json`、待发布提交与安全扫描；打包后检查完整 ZIP 的 CRC、内容布局和 SHA-256，使用隔离 `LOCALAPPDATA` 从解压包启动；创建与提交一致的新标签和 Release，上传完整包后从 GitHub 核实附件大小、哈希和可下载性。不要覆盖 v1.0.4 的附件或改写其标签。文档可在 `master` 更新，但必须说明标签后的文档提交不改变二进制。
- **完整包**根目录应有 `Start-App.cmd`、`updater/`、`app/`，供人手动解压。**自动更新载荷**只能含 `app/`，里面须有 `version.json`、Chromium、FFmpeg 和说明文件。两者不能混用。
- **生产自动更新与下载站**不归本次 GitHub 文档任务：历史流程是先上传不可变包并公网回读校验，再更新 OSS `latest.json`/下载目录，最后验证旧版隔离升级和网站。当前公开清单指向 v1.0.4 更新 ZIP，SHA-256 `033031844707EB53F089C6C42CAA668C18672F0BF36AA90504311BB7A17E8AB1`。未来改生产前需独立检查权限、URL、哈希、完整包/更新包布局和旧版升级；不要把源码推送等同于客户端已更新。
- `Start-App.cmd` 先运行更新器再启动 EXE；保留用户数据目录和旧版备份/回滚路径。不要为了验证清空登录态、数据库或客户安装目录。使用隔离安装目录和隔离 `LOCALAPPDATA` 测试。

## 6. 已验证、已知故障与下一步

- 2026-09-24 v1.0.4 发布时：16 项核心测试、更新器测试、ZIP 布局/哈希、隔离目录下的真实 UP 主/话题/单作品提取、XLSX、单视频下载，以及 v1.0.3→v1.0.4 公网清单升级曾通过；这是当时记录，不等于对今天的哔哩哔哩接口重新实测。2026-10-31 的本轮命令及结果见交付回复。
- **已复现的启动故障**：从浏览器下载的 ZIP 解压后，Windows `Zone.Identifier` 可能传播至 `Python.Runtime.dll`；`import clr` 报 `Failed to resolve Python.Runtime.Loader.Initialize`。正式 v1.0.4 的 `desktop_app.py` 错误地将所有此类异常提示为“需要 .NET Framework 4.8.1”。在隔离 DLL 上添加标记可复现同错，移除标记后加载成功；用户在另一台电脑对可信 ZIP 先解除锁定、再重新解压，也确认可正常打开。不要让用户反复重装 .NET，不要全局关闭 Windows 下载保护。诊断分支修正了提示并记录原始异常；尚未形成正式修复版本。
- UP 主资料在未登录时可能返回 `-352`；扫码登录后重试。界面 `web/templates/creator.html` 的 `addProfiles()` 在部分作者资料读取失败时仍清空输入框，失败 URL 无法直接重新提交；尚未修复，改动时加回归测试并保留已添加顺序。
- 暂停只管提取，不管正在下载的视频；暂停在安全检查点生效，进程关闭后无法续跑。单作品 BVID 大小写必须保留；重复输入行与作者添加顺序是行为要求。
- 后续如要把诊断改动正式化，先评估 Windows 下载标记的用户体验与安全边界，给出面向可信包的处理方案；不要在启动器里无条件解除所有下载文件的安全标记。合并诊断分支、补测试、出新版本和做客户端升级验证时再发布新的不可变 ZIP。不要将诊断包标成正式 v1.0.4 的替代附件。

## 7. 从哪里继续

建议先执行 `git status --short --branch`、`git ls-remote --heads origin`、检查 `version.json` 与 GitHub Release，再读 `README.md`、`desktop_app.py`、`web/app.py` 和目标测试。历史 `docs/superpowers/` 是设计背景；本交接和当前源码优先。诊断问题从 `codex/startup-diagnostics` 的 `desktop_app.py`、`tests/test_startup_diagnostics.py` 开始；提取/顺序问题从 `bilibili_client.py`、`db.py`、`web/app.py` 开始；发布问题从 `Start-App.cmd`、`updater-src/`、`build.ps1`、`test_updater.ps1` 开始。
