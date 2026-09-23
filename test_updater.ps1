param(
    [ValidateSet('Manifest', 'Hash')]
    [string]$Test = 'Manifest'
)

$ErrorActionPreference = 'Stop'

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
    Write-Host 'PASS: Hash'
}

if ($Test -eq 'Manifest') { Test-Manifest } else { Test-Hash }
