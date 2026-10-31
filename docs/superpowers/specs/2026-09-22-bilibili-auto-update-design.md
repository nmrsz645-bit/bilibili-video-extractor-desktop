# 哔哩哔哩视频提取 v1.0.2 自动更新设计

## 目标

原计划发布 v1.0.2，并在启动时自动安装；该行为已由用户后续决定取代。当前执行目标为 v1.0.3：用户先选择是否下载；同意后只下载并校验，当前启动继续运行旧版；程序关闭后，下次启动才安装暂存版本。断网、拒绝下载、校验或替换失败时继续运行旧版。

v1.0.0、v1.0.1、v1.0.2 的既有客户端仍可能使用旧清单协议，因此 v1.0.3 改用 `/updates/bilibili-video-extractor-desktop/opt-in/latest.json`。发布时保留旧清单不变；用户需从下载站手动安装一次 v1.0.3 完整包，以进入新的选择式更新通道。

## 范围与约束

- 不改变 BVID 解析、提取、下载、登录或 XLSX 功能。
- 不读取、写入、打包或上传用户的登录态、数据库、Cookie、日志或下载视频。
- 用户数据继续只保存于 `%LOCALAPPDATA%\哔哩哔哩视频提取`。
- 更新清单及更新 ZIP 必须为 HTTPS；新选择式清单必须含 `version`、`url`、`sha256`。
- 仅替换安装目录中的 `app\`；启动器与更新器永不自我替换。
- 失败时恢复旧 `app\`，然后照常启动旧版 GUI。
- 完整安装 ZIP 与自动更新载荷 ZIP 分开发布，均为不可变版本文件并各自校验。

## 安装布局

```text
哔哩哔哩视频提取\
  Start-App.cmd
  updater\
    UpdateAgent.exe
    updater-config.json
  app\
    哔哩哔哩视频提取.exe
    _internal\...
    ms-playwright\...
    tools\ffmpeg\bin\ffmpeg.exe
    version.json
    使用说明.md
```

`app\version.json` 的唯一字段为 `version`。完整安装 ZIP 含全部布局；自动更新载荷 ZIP 只含根目录 `app\`。启动器和更新器固定在根目录，以便更新期间不被占用的 GUI 文件影响。

## 组件与数据流

1. 用户启动 `Start-App.cmd`。
2. 它同步执行 `updater\UpdateAgent.exe --check updater\updater-config.json`，然后无论更新检查成功与否都启动 `app\` 内唯一 GUI EXE。
3. 更新器先处理已校验的暂存包；没有暂存包时，读取本地 `app\version.json` 和 HTTPS 选择式清单，询问用户是否下载。
4. 用户同意后只暂存完整性已验证的 app-only ZIP；本次继续启动旧 GUI，直到用户关闭程序并再次启动才替换 `app\`。
4. 远端版本不高于本地版本时不做任何替换；更高时下载版本化更新 ZIP 到短临时目录。
5. 更新器严格验证 SHA-256、ZIP 路径安全性、ZIP 只含 `app\`、GUI EXE、`_internal\`、Chromium、ffmpeg、使用说明和与清单一致的版本文件。
6. 验证后将原 `app\` 重命名为 `app.previous\`，将暂存 `app\` 改名为正式目录；验证最终目录后删除备份。任一步失败则恢复备份。

更新器是独立 .NET Framework C# EXE。主程序目前已经要求 .NET Framework 创建 pywebview 窗口，因此更新器不引入新的系统运行时前提。

## 清单与发布位置

更新器配置固定指向：

```text
https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/bilibili-video-extractor-desktop/opt-in/latest.json
```

清单最小格式：

```json
{
  "version": "1.0.3",
  "url": "https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/bilibili-video-extractor-desktop/releases/1.0.3/bilibili-video-extractor-desktop-update-1.0.3.zip",
  "sha256": "64 位十六进制 SHA-256"
}
```

首次安装完整包继续使用不可变路径：

```text
packages/bilibili-video-extractor-desktop/<版本>/bilibili-video-extractor-desktop-<版本>-windows-x64.zip
```

发布顺序必须为：更新载荷 ZIP 与完整 ZIP → 两者公网下载回读并核验 SHA-256 → `latest.json` / `latest.js` → 下载站链接与版本文字。`latest.json` 是唯一触发自动更新的指针，禁止先更新它。

## 用户体验与错误处理

- 与现有统一更新器一致：在启动器阶段自动检查并安装，不在 GUI 运行时更新。
- 网络、HTTP、非 HTTPS、JSON、版本、哈希、ZIP 布局、磁盘或替换失败：不替换 `app\`；启动器继续启动旧版。
- v1.0.2 之后的更新载荷可能较大，因为必须携带运行时、Chromium 与 ffmpeg；更新器不读取用户数据，也不发送用户数据。
- 本次按既有统一逻辑采用启动时静默下载；若用户需要流量确认或进度 UI，属于后续独立需求，不在本次加入。

## 源码与测试边界

预计新增或修改：`version.json`、`Start-App.cmd`、`updater-src\UpdateAgent.cs`、`updater-src\build-updater.ps1`、`updater-src\updater-config.json`、`build.ps1`、`test_updater.ps1`、打包说明和发布脚本。业务 Python 模块及既有 8 项回归测试不修改。

新增更新器测试覆盖：版本比较、HTTPS 拒绝、清单字段拒绝、SHA-256 拒绝、ZIP 路径穿越与布局拒绝、正确更新、替换失败回滚、异常中断恢复、启动器失败仍启动旧 EXE，以及 `%LOCALAPPDATA%` 测试夹具哈希不变。发布前还需用隔离安装目录执行真实 v1.0.2 到 v1.0.3 升级，并复核公开 ZIP、清单及下载站。
