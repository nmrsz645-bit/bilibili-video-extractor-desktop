param(
    [string]$BrowserRoot = $env:BILIBILI_PLAYWRIGHT_BROWSERS_PATH,
    [string]$FfmpegExe = $env:BILIBILI_FFMPEG_EXE
)

$ErrorActionPreference = 'Stop'

function Get-UnicodeText {
    param([int[]]$CodePoints)
    return -join ($CodePoints | ForEach-Object { [char]$_ })
}

function Reset-BuildDirectory {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        [IO.Directory]::Delete($Path, $true)
    }
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Copy-DirectoryWithoutLogs {
    param([string]$Source, [string]$Destination)
    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\\')
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -Force | ForEach-Object {
        $relativePath = $_.FullName.Substring($sourceRoot.Length).TrimStart('\\')
        $targetPath = Join-Path $Destination $relativePath
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        } elseif ($_.Extension -ne '.log') {
            $targetDirectory = Split-Path -Parent $targetPath
            New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $targetPath -Force
        }
    }
}

$appName = Get-UnicodeText @(0x54D4, 0x54E9, 0x54D4, 0x54E9, 0x89C6, 0x9891, 0x63D0, 0x53D6)
$usageFileName = (Get-UnicodeText @(0x4F7F, 0x7528, 0x8BF4, 0x660E)) + '.md'
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'version.json') -Raw | ConvertFrom-Json).version

if ([string]::IsNullOrWhiteSpace($BrowserRoot)) {
    $BrowserRoot = Join-Path $env:LOCALAPPDATA 'ms-playwright'
}
if (-not (Test-Path -LiteralPath $BrowserRoot)) {
    throw "Playwright browser directory was not found: $BrowserRoot"
}
if ([string]::IsNullOrWhiteSpace($FfmpegExe)) {
    $FfmpegExe = (Get-Command ffmpeg.exe -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $FfmpegExe)) {
    throw "ffmpeg.exe was not found: $FfmpegExe"
}

$buildRoot = Join-Path $PSScriptRoot 'build\portable-release'
$distRoot = Join-Path $PSScriptRoot 'dist'
$releaseRoot = Join-Path $distRoot $appName
$pyInstallerWork = Join-Path $buildRoot 'pyinstaller-work'
$pyInstallerSpec = Join-Path $buildRoot 'pyinstaller-spec'
$pyInstallerDist = Join-Path $buildRoot 'pyinstaller-dist'

Reset-BuildDirectory $buildRoot
Reset-BuildDirectory $distRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Isolated build Python was not found. Create .venv and install requirements first.'
}

& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name $appName `
    --distpath $pyInstallerDist --workpath $pyInstallerWork --specpath $pyInstallerSpec `
    --add-data ((Join-Path $PSScriptRoot 'web') + ';web') `
    --collect-all webview --collect-all playwright --collect-all uvicorn --collect-all yt_dlp `
    --hidden-import clr_loader --hidden-import pythonnet `
    (Join-Path $PSScriptRoot 'desktop_app.py')
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller packaging failed.'
}

$pyInstallerOutput = Join-Path $pyInstallerDist $appName
$appRoot = Join-Path $releaseRoot 'app'
New-Item -ItemType Directory -Path $appRoot -Force | Out-Null
Get-ChildItem -LiteralPath $pyInstallerOutput -Force | Copy-Item -Destination $appRoot -Recurse -Force
Copy-DirectoryWithoutLogs $BrowserRoot (Join-Path $appRoot 'ms-playwright')
$ffmpegTarget = Join-Path $appRoot 'tools\ffmpeg\bin'
New-Item -ItemType Directory -Path $ffmpegTarget -Force | Out-Null
Copy-Item -LiteralPath $FfmpegExe -Destination (Join-Path $ffmpegTarget 'ffmpeg.exe') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'version.json') -Destination (Join-Path $appRoot 'version.json') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $appRoot $usageFileName) -Force

New-Item -ItemType Directory -Path (Join-Path $releaseRoot 'updater') -Force | Out-Null
& (Join-Path $PSScriptRoot 'updater-src\build-updater.ps1') -OutputPath (Join-Path $releaseRoot 'updater\UpdateAgent.exe')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'updater-src\updater-config.json') -Destination (Join-Path $releaseRoot 'updater\updater-config.json') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Start-App.cmd') -Destination (Join-Path $releaseRoot 'Start-App.cmd') -Force

Write-Host "Portable release $version created at: $releaseRoot"
