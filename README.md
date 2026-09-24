# 哔哩哔哩视频提取

独立的新项目，不读取或写入旧抖音程序的数据。

开发测试：先双击 `Setup-Dev.cmd` 安装 Python 依赖与 Chromium，再双击 `启动哔哩哔哩视频提取.vbs`。该启动文件不会显示命令框；`Start-Dev.cmd` 也会后台启动，不会保留命令框。

发布包：用户应从解压后的根目录双击 `Start-App.cmd`。它会先校验 HTTPS 更新清单和完整包 SHA-256；有新版时仅替换 `app/`，校验失败或更新中断会恢复上一版，再启动当前可用程序。不要直接运行 `app` 内的 EXE，否则不会检查更新。

构建发布包：在隔离构建目录创建 `.venv` 并安装 `requirements.txt`、`pyinstaller` 后，运行 `powershell.exe -ExecutionPolicy Bypass -File .\build.ps1`。更新器测试也必须使用 Windows PowerShell 5.1（`powershell.exe`）；可用 `BILIBILI_PLAYWRIGHT_BROWSERS_PATH` 和 `BILIBILI_FFMPEG_EXE` 覆盖 Chromium 与 ffmpeg 的来源路径。构建不会读取或复制 `data`、`browser_session`、`logs`。

功能：批量 UP 主空间提取、关键词/话题提取、批量单视频提取，分钟级筛选、XLSX 另存为，以及当前账号可获取的最高画质下载。多 P 会下载为 `标题 - P01.mp4`、`标题 - P02.mp4` 等，并依赖完整发布包中的 ffmpeg 进行音视频合并。

三种提取任务运行时均可点击“暂停提取”，随后点击“继续提取”接着运行。暂停会在当前网页请求完成后的下一个安全检查点生效；请保持程序运行，关闭程序后无法续跑。视频下载不受此按钮控制。
