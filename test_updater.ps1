param(
    [ValidateSet('Manifest', 'Hash', 'PackageValidation', 'Transaction', 'Launcher', 'PackageLayout')]
    [string]$Test = 'Manifest'
)

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Run updater tests with Windows PowerShell 5.1 (powershell.exe), not PowerShell Core.'
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "ASSERTION FAILED: $Message" }
}

function Assert-Equal {
    param($Expected, $Actual, [string]$Message)
    if ($Expected -ne $Actual) {
        throw "ASSERTION FAILED: $Message. Expected '$Expected', got '$Actual'."
    }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$ExpectedMessage)
    try {
        & $Action
    } catch {
        if ($_.Exception.Message -notmatch [Regex]::Escape($ExpectedMessage)) {
            throw "ASSERTION FAILED: expected error containing '$ExpectedMessage', got '$($_.Exception.Message)'."
        }
        return
    }
    throw "ASSERTION FAILED: expected error containing '$ExpectedMessage'."
}

function Get-UpdaterType {
    $builder = Join-Path $PSScriptRoot 'updater-src\build-updater.ps1'
    Assert-True (Test-Path -LiteralPath $builder) 'UpdateAgent build script is missing'
    $output = Join-Path $PSScriptRoot ('build\updater-test\UpdateAgent-' + [Guid]::NewGuid().ToString('N') + '.exe')
    & $builder -OutputPath $output
    $assembly = [Reflection.Assembly]::LoadFile($output)
    return $assembly.GetType('Updater', $true)
}

function Test-Manifest {
    $updater = Get-UpdaterType
    Assert-Equal $false ($updater::IsNewer([Version]'1.0.2', [Version]'1.0.2')) 'equal versions must not update'
    Assert-Equal $true ($updater::IsNewer([Version]'1.0.3', [Version]'1.0.2')) 'higher version must update'
    $hash = 'a' * 64
    $httpManifest = '{"version":"1.0.3","url":"http://example.test/app.zip","sha256":"' + $hash + '"}'
    Assert-Throws { $updater::ParseManifest($httpManifest, [Uri]'https://example.test/latest.json') } 'HTTPS'
    Write-Host 'PASS: Manifest'
}

function Test-Hash {
    $updater = Get-UpdaterType
    $fixtureDirectory = Join-Path $PSScriptRoot 'build\updater-test\fixtures'
    New-Item -ItemType Directory -Path $fixtureDirectory -Force | Out-Null
    $fixture = Join-Path $fixtureDirectory 'payload.bin'
    [IO.File]::WriteAllBytes($fixture, [byte[]](1, 2, 3, 4))
    $goodHash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash
    Assert-Equal $goodHash ($updater::VerifyFileSha256($fixture, $goodHash)) 'correct SHA-256 must be accepted'
    Assert-Throws { $updater::VerifyFileSha256($fixture, ('0' * 64)) } 'SHA-256'
    Assert-Throws { $updater::DownloadAndVerify([Uri]'http://example.test/app.zip', $goodHash, $fixtureDirectory) } 'HTTPS'
    Write-Host 'PASS: Hash'
}

function New-TestZip {
    param([string]$ZipPath, [hashtable]$Entries)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
    $archive = [IO.Compression.ZipFile]::Open($ZipPath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $Entries.Keys) {
            $entry = $archive.CreateEntry([string]$name)
            $writer = [IO.StreamWriter]::new($entry.Open())
            try { $writer.Write([string]$Entries[$name]) } finally { $writer.Dispose() }
        }
    } finally {
        $archive.Dispose()
    }
}

function New-DuplicateEntryZip {
    param([string]$ZipPath)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::Open($ZipPath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($payload in @('first', 'second')) {
            $entry = $archive.CreateEntry('app/duplicate.txt')
            $writer = [IO.StreamWriter]::new($entry.Open())
            try { $writer.Write($payload) } finally { $writer.Dispose() }
        }
    } finally {
        $archive.Dispose()
    }
}

function Get-UsageFileName {
    return (-join (@(0x4F7F, 0x7528, 0x8BF4, 0x660E) | ForEach-Object { [char]$_ })) + '.md'
}

function Test-PackageValidation {
    $updater = Get-UpdaterType
    $root = Join-Path $PSScriptRoot ('build\updater-test\package-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $traversalZip = Join-Path $root 'traversal.zip'
    $wrongRootZip = Join-Path $root 'wrong-root.zip'
    $duplicateZip = Join-Path $root 'duplicate.zip'
    $versionMismatchZip = Join-Path $root 'version-mismatch.zip'
    New-TestZip $traversalZip @{ 'app/../../outside.txt' = 'unsafe' }
    New-TestZip $wrongRootZip @{ 'other/file.txt' = 'wrong root' }
    New-DuplicateEntryZip $duplicateZip
    $entries = @{
        'app/app.exe' = 'exe'
        'app/_internal/keep.txt' = 'internal'
        'app/ms-playwright/chromium-1/chrome-win64/chrome.exe' = 'chromium'
        'app/tools/ffmpeg/bin/ffmpeg.exe' = 'ffmpeg'
        'app/version.json' = '{"version":"1.0.2"}'
    }
    $entries['app/' + (Get-UsageFileName)] = 'readme'
    New-TestZip $versionMismatchZip $entries
    Assert-Throws { $updater::ValidatePackage($traversalZip, (Join-Path $root 'traversal-stage'), [Version]'1.0.3') } 'unsafe path'
    Assert-Throws { $updater::ValidatePackage($wrongRootZip, (Join-Path $root 'wrong-root-stage'), [Version]'1.0.3') } 'only the app directory'
    Assert-Throws { $updater::ValidatePackage($duplicateZip, (Join-Path $root 'duplicate-stage'), [Version]'1.0.3') } 'duplicate path'
    Assert-Throws { $updater::ValidatePackage($versionMismatchZip, (Join-Path $root 'version-stage'), [Version]'1.0.3') } 'version'
    Write-Host 'PASS: PackageValidation'
}

function New-TestApp {
    param([string]$AppPath, [string]$Version, [string]$Payload)
    New-Item -ItemType Directory -Path (Join-Path $AppPath '_internal') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $AppPath 'ms-playwright\chromium-1\chrome-win64') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $AppPath 'tools\ffmpeg\bin') -Force | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $AppPath 'app.exe'), [byte[]](1))
    [IO.File]::WriteAllText((Join-Path $AppPath 'ms-playwright\chromium-1\chrome-win64\chrome.exe'), 'chromium')
    [IO.File]::WriteAllText((Join-Path $AppPath 'tools\ffmpeg\bin\ffmpeg.exe'), 'ffmpeg')
    [IO.File]::WriteAllText((Join-Path $AppPath (Get-UsageFileName)), 'readme')
    [IO.File]::WriteAllText((Join-Path $AppPath 'version.json'), ('{"version":"' + $Version + '"}'))
    [IO.File]::WriteAllText((Join-Path $AppPath 'payload.txt'), $Payload)
}

function Test-Transaction {
    $updater = Get-UpdaterType
    $root = Join-Path $PSScriptRoot ('build\updater-test\transaction-' + [Guid]::NewGuid().ToString('N'))
    $install = Join-Path $root 'install'
    $stagedApp = Join-Path $root 'stage\app'
    New-TestApp (Join-Path $install 'app') '1.0.2' 'old-build'
    New-TestApp $stagedApp '1.0.3' 'new-build'
    $updater::ApplyVerifiedApp($install, $stagedApp)
    Assert-Equal 'new-build' ([IO.File]::ReadAllText((Join-Path $install 'app\payload.txt'))) 'new app was not installed'

    $badStage = Join-Path $root 'bad-stage\app'
    New-Item -ItemType Directory -Path (Join-Path $badStage '_internal') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $badStage 'ms-playwright\chromium-1\chrome-win64') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $badStage 'tools\ffmpeg\bin') -Force | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $badStage 'app.exe'), [byte[]](1))
    [IO.File]::WriteAllText((Join-Path $badStage 'ms-playwright\chromium-1\chrome-win64\chrome.exe'), 'chromium')
    [IO.File]::WriteAllText((Join-Path $badStage 'tools\ffmpeg\bin\ffmpeg.exe'), 'ffmpeg')
    [IO.File]::WriteAllText((Join-Path $badStage (Get-UsageFileName)), 'readme')
    Assert-Throws { $updater::ApplyVerifiedApp($install, $badStage) } 'version'
    Assert-Equal 'new-build' ([IO.File]::ReadAllText((Join-Path $install 'app\payload.txt'))) 'failed replacement did not restore old app'

    Move-Item -LiteralPath (Join-Path $install 'app') -Destination (Join-Path $install 'app.previous')
    $updater::RecoverInterruptedUpdate($install)
    Assert-True (Test-Path -LiteralPath (Join-Path $install 'app\payload.txt')) 'interrupted update did not recover app'
    Write-Host 'PASS: Transaction'
}

function Test-Launcher {
    Assert-True (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'Start-App.cmd')) 'root launcher is missing'
    $builder = Join-Path $PSScriptRoot 'updater-src\build-updater.ps1'
    $output = Join-Path $PSScriptRoot ('build\updater-test\cli-' + [Guid]::NewGuid().ToString('N') + '.exe')
    & $builder -OutputPath $output
    & $output --check (Join-Path $PSScriptRoot 'build\missing-config.json')
    Assert-Equal 1 $LASTEXITCODE 'missing updater config must fail the check command'
    Write-Host 'PASS: Launcher'
}

function Test-PackageLayout {
    $builder = Join-Path $PSScriptRoot 'build.ps1'
    Assert-True (Test-Path -LiteralPath $builder) 'portable package build script is missing'
    & $builder
    $releaseDirectories = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'dist') -Directory)
    Assert-Equal 1 $releaseDirectories.Count 'exactly one release directory was expected'
    $distRoot = $releaseDirectories[0].FullName
    Assert-True (Test-Path -LiteralPath (Join-Path $distRoot 'Start-App.cmd')) 'launcher missing from release'
    Assert-True (Test-Path -LiteralPath (Join-Path $distRoot 'updater\UpdateAgent.exe')) 'updater missing from release'
    Assert-True (Test-Path -LiteralPath (Join-Path $distRoot 'app\version.json')) 'app version file missing'
    Assert-Equal '1.0.2' ((Get-Content -LiteralPath (Join-Path $distRoot 'app\version.json') -Raw | ConvertFrom-Json).version) 'wrong packaged version'
    Assert-Equal 1 @(Get-ChildItem -LiteralPath (Join-Path $distRoot 'app') -Filter '*.exe' -File).Count 'GUI EXE must be staged in app'
    Assert-True (@(Get-ChildItem -LiteralPath (Join-Path $distRoot 'app\ms-playwright') -Directory -Filter 'chromium-*' | Get-ChildItem -Recurse -Filter chrome.exe -File).Count -gt 0) 'Chromium missing from app'
    Assert-True (Test-Path -LiteralPath (Join-Path $distRoot 'app\tools\ffmpeg\bin\ffmpeg.exe')) 'ffmpeg missing from app'
    $privateFiles = Get-ChildItem -LiteralPath $distRoot -Recurse -File | Where-Object { $_.FullName -match '\\(data|browser_session|logs)(\\|$)|\.(db|sqlite|log)$' }
    Assert-Equal 0 @($privateFiles).Count 'private user material leaked into build'
    Write-Host 'PASS: PackageLayout'
}

switch ($Test) {
    'Manifest' { Test-Manifest }
    'Hash' { Test-Hash }
    'PackageValidation' { Test-PackageValidation }
    'Transaction' { Test-Transaction }
    'Launcher' { Test-Launcher }
    'PackageLayout' { Test-PackageLayout }
}
