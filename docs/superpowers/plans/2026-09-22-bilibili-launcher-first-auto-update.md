# Bilibili Launcher-First Auto Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v1.0.2 as a self-contained Windows package that updates later versions safely before opening the Bilibili extractor GUI.

**Architecture:** A root `Start-App.cmd` runs an independent .NET Framework `UpdateAgent.exe` before launching the GUI under `app/`. The updater consumes an HTTPS manifest, validates an immutable app-only ZIP and its SHA-256, swaps only `app/` transactionally, and restores the prior app on every replacement failure.

**Tech Stack:** Python 3.13, PyInstaller onedir, C# compiled with .NET Framework `csc.exe`, PowerShell 5.1 test/build scripts, .NET `System.IO.Compression`, OSS HTTPS static objects.

**Spec:** `docs/superpowers/specs/2026-09-22-bilibili-auto-update-design.md`

## Global Constraints

- Release version is `1.0.2`; `1.0.0` and `1.0.1` users manually install this first updater-aware version.
- Do not modify BVID parsing, extraction, download, login, XLSX, or other business Python behavior.
- User data remains only in `%LOCALAPPDATA%\哔哩哔哩视频提取`; never package, replace, read, or upload it.
- Manifest and payload URLs must be HTTPS; required manifest fields are `version`, `url`, and a 64-hex-character `sha256`.
- The complete ZIP contains root `Start-App.cmd`, `updater/`, and `app/`; the update ZIP contains only `app/`.
- The updater only replaces `app/`, recovers `app.previous/` after interruption, and launches no GUI itself.
- Immutable ZIPs must be public and hash-verified before `latest.json`, `latest.js`, or the download-site card changes.

## Review Focus

- A manifest URL using `http://` must be rejected before any request; Task 1 pins `ParseManifest` to reject it.
- A remote ZIP that contains `../` or any root other than `app/` must not write outside staging; Task 2 pins path and layout rejection.
- A validly hashed ZIP whose `version.json` differs from the manifest must not replace the installed app; Task 2 pins mismatch rejection.
- A replacement failure after `app/` was moved must restore the exact previous payload; Task 3 pins rollback and interrupted-update recovery.
- A failed update check must still let `Start-App.cmd` launch the existing GUI, while `%LOCALAPPDATA%` remains byte-for-byte unchanged; Task 4 pins launcher and data-isolation behavior.

---

### Task 1: Define the updater contract and prove manifest/hash failures

**Files:**
- Create: `updater-src/UpdateAgent.cs`
- Create: `updater-src/build-updater.ps1`
- Create: `test_updater.ps1`

**Interfaces:**
- Produces `public sealed class ReleaseManifest(Version version, Uri packageUri, string sha256)`.
- Produces `public static class Updater` methods `IsNewer(Version, Version)`, `ParseManifest(string, Uri)`, and `VerifyFileSha256(string, string)`.
- Produces `UpdateAgent.exe --check <updater-config.json>` with exit `0` for no update and `1` for checked failure.

- [ ] **Step 1: Write the failing manifest and hash tests**

```powershell
Assert-Equal $false ($updater::IsNewer([Version]'1.0.2', [Version]'1.0.2')) 'equal versions must not update'
Assert-Equal $true ($updater::IsNewer([Version]'1.0.3', [Version]'1.0.2')) 'higher version must update'
Assert-Throws {
  $updater::ParseManifest('{"version":"1.0.3","url":"http://example.test/app.zip","sha256":"' + ('a' * 64) + '"}', [Uri]'https://example.test/latest.json')
} 'HTTPS'
Assert-Throws { $updater::VerifyFileSha256($fixture, ('0' * 64)) } 'SHA-256'
```

- [ ] **Step 2: Run the focused test before implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Manifest`

Expected: FAIL because `updater-src\build-updater.ps1` and type `Updater` do not exist.

- [ ] **Step 3: Implement the manifest/hash boundary**

```csharp
public static bool IsNewer(Version remote, Version local) => remote.CompareTo(local) > 0;

public static ReleaseManifest ParseManifest(string json, Uri manifestUri) {
    RequireHttps(manifestUri, "manifest URL");
    var fields = new JavaScriptSerializer().DeserializeObject(json) as IDictionary<string, object>;
    string versionText = RequiredString(fields, "version");
    string packageText = RequiredString(fields, "url");
    string sha256 = RequiredString(fields, "sha256");
    Version version; if (!Version.TryParse(versionText, out version)) throw new InvalidOperationException("Manifest version is invalid.");
    if (!Regex.IsMatch(sha256, "^[A-Fa-f0-9]{64}$")) throw new InvalidOperationException("Manifest SHA-256 is invalid.");
    Uri packageUri; if (!Uri.TryCreate(packageText, UriKind.Absolute, out packageUri)) throw new InvalidOperationException("Manifest package URL is invalid.");
    RequireHttps(packageUri, "package URL");
    return new ReleaseManifest(version, packageUri, sha256);
}

public static string VerifyFileSha256(string filePath, string expectedSha256) {
    using (var input = File.OpenRead(filePath)) using (var sha = SHA256.Create()) {
        string actual = BitConverter.ToString(sha.ComputeHash(input)).Replace("-", String.Empty);
        if (!String.Equals(actual, expectedSha256, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Package SHA-256 does not match the manifest.");
        return actual;
    }
}
```

`build-updater.ps1` must resolve `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`, fall back to `Framework\...`, and compile with `System.IO.Compression.dll`, `System.IO.Compression.FileSystem.dll`, and `System.Web.Extensions.dll`.

- [ ] **Step 4: Run focused updater tests after implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Manifest; powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Hash`

Expected: both print `PASS`; malformed hash and non-HTTPS URLs fail only inside their asserted cases.

- [ ] **Step 5: Commit the contract**

```powershell
git add updater-src\UpdateAgent.cs updater-src\build-updater.ps1 test_updater.ps1
git commit -m "feat: validate update manifests and hashes"
```

### Task 2: Validate update ZIPs before any installed-file operation

**Files:**
- Modify: `updater-src/UpdateAgent.cs`
- Modify: `test_updater.ps1`

**Interfaces:**
- Consumes `Updater.VerifyFileSha256` and `ReleaseManifest` from Task 1.
- Produces `Updater.DownloadAndVerify(Uri packageUri, string expectedSha256, string temporaryDirectory)` and `Updater.ValidatePackage(string zipPath, string stagingDirectory, Version expectedVersion)`.
- Produces a staged directory whose only application root is `stage\app\`.

- [ ] **Step 1: Add failing ZIP-safety and version-mismatch tests**

```powershell
Assert-Throws { $updater::ValidatePackage($traversalZip, $badStage, [Version]'1.0.3') } 'unsafe path'
Assert-Throws { $updater::ValidatePackage($wrongRootZip, $badStage, [Version]'1.0.3') } 'only the app directory'
Assert-Throws { $updater::ValidatePackage($version102Zip, $badStage, [Version]'1.0.3') } 'version'
```

Create each fixture with `System.IO.Compression.ZipFile`; the valid fixture must contain `app\app.exe`, `app\_internal\`, `app\ms-playwright\`, `app\tools\ffmpeg\bin\ffmpeg.exe`, `app\使用说明.md`, and `app\version.json`.

- [ ] **Step 2: Run ZIP validation before implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test PackageValidation`

Expected: FAIL because `ValidatePackage` is not defined.

- [ ] **Step 3: Implement download and package validation**

```csharp
public static void ValidatePackage(string zipPath, string stagingDirectory, Version expectedVersion) {
    string appRoot = Path.GetFullPath(Path.Combine(stagingDirectory, "app")).TrimEnd(Path.DirectorySeparatorChar);
    string appPrefix = appRoot + Path.DirectorySeparatorChar;
    foreach (ZipArchiveEntry entry in ZipFile.OpenRead(zipPath).Entries) {
        string name = entry.FullName.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
        if (!name.StartsWith("app" + Path.DirectorySeparatorChar, StringComparison.Ordinal) && name != "app/") throw new InvalidOperationException("ZIP must contain only the app directory.");
        string target = Path.GetFullPath(Path.Combine(stagingDirectory, name));
        if (!String.Equals(target, appRoot, StringComparison.OrdinalIgnoreCase) && !target.StartsWith(appPrefix, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("ZIP contains an unsafe path.");
        if (String.IsNullOrEmpty(entry.Name)) Directory.CreateDirectory(target); else { Directory.CreateDirectory(Path.GetDirectoryName(target)); entry.ExtractToFile(target, true); }
    }
    ValidateInstalledApp(Path.Combine(stagingDirectory, "app"), expectedVersion);
}

private static void ValidateInstalledApp(string appDirectory, Version expectedVersion) {
    if (Directory.GetFiles(appDirectory, "*.exe").Length != 1) throw new InvalidOperationException("Package GUI executable is missing.");
    if (!Directory.Exists(Path.Combine(appDirectory, "_internal"))) throw new InvalidOperationException("Package internal directory is missing.");
    if (!Directory.Exists(Path.Combine(appDirectory, "ms-playwright"))) throw new InvalidOperationException("Package Chromium is missing.");
    if (!File.Exists(Path.Combine(appDirectory, "tools", "ffmpeg", "bin", "ffmpeg.exe"))) throw new InvalidOperationException("Package ffmpeg is missing.");
    // Require 使用说明.md and version.json, parse its version, and require equality when expectedVersion is non-null.
}
```

`DownloadAndVerify` must disable redirects, require HTTP 200, use finite timeouts, write to a GUID-named ZIP under the provided short temporary directory, and delete the partial artifact on exceptions.

- [ ] **Step 4: Run ZIP validation after implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test PackageValidation`

Expected: PASS; valid ZIP stages only below `stage\app`, and every invalid fixture is rejected.

- [ ] **Step 5: Commit the package gate**

```powershell
git add updater-src\UpdateAgent.cs test_updater.ps1
git commit -m "feat: validate update package layout"
```

### Task 3: Add atomic app replacement, recovery, and synchronous check command

**Files:**
- Modify: `updater-src/UpdateAgent.cs`
- Modify: `test_updater.ps1`
- Create: `updater-src/updater-config.json`
- Create: `Start-App.cmd`
- Create: `version.json`

**Interfaces:**
- Consumes validated `stage\app` from Task 2.
- Produces `Updater.ApplyVerifiedApp(string installRoot, string stagedAppDirectory)` and `Updater.RecoverInterruptedUpdate(string installRoot)`.
- Produces `Start-App.cmd`, which calls `updater\UpdateAgent.exe --check updater\updater-config.json` before starting the only EXE under `app\`.

- [ ] **Step 1: Add failing transaction, recovery, and launcher tests**

```powershell
$updater::ApplyVerifiedApp($install, (Join-Path $stage 'app'))
Assert-Equal 'new-build' ([IO.File]::ReadAllText((Join-Path $install 'app\payload.txt'))) 'new app was not installed'
Assert-Throws { $updater::ApplyVerifiedApp($install, $badStageApp) } 'version'
Assert-Equal 'new-build' ([IO.File]::ReadAllText((Join-Path $install 'app\payload.txt'))) 'failed replacement did not restore old app'
Move-Item (Join-Path $install 'app') (Join-Path $install 'app.previous')
$updater::RecoverInterruptedUpdate($install)
Assert-True (Test-Path (Join-Path $install 'app\payload.txt')) 'interrupted update did not recover app'
```

- [ ] **Step 2: Run transaction tests before implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Transaction`

Expected: FAIL because replacement and recovery methods do not exist.

- [ ] **Step 3: Implement app-only directory transaction and CLI**

```csharp
public static void ApplyVerifiedApp(string installRoot, string stagedAppDirectory) {
    string app = Path.Combine(installRoot, "app");
    string backup = Path.Combine(installRoot, "app.previous");
    if (Directory.Exists(backup)) Directory.Delete(backup, true);
    try { if (Directory.Exists(app)) Directory.Move(app, backup); Directory.Move(stagedAppDirectory, app); ValidateInstalledApp(app, null); if (Directory.Exists(backup)) Directory.Delete(backup, true); }
    catch { if (Directory.Exists(app)) Directory.Delete(app, true); if (Directory.Exists(backup)) Directory.Move(backup, app); throw; }
}

private static void RunCheck(string configPath) {
    RecoverInterruptedUpdate(installRoot);
    ReleaseManifest remote = ParseManifest(DownloadText(manifestUri), manifestUri);
    if (!IsNewer(remote.Version, ReadLocalVersion(Path.Combine(installRoot, "app", "version.json")))) return;
    string temp = Path.Combine(Path.GetTempPath(), "bilibili-update-" + Guid.NewGuid().ToString("N"));
    try { string zip = DownloadAndVerify(remote.PackageUri, remote.Sha256, temp); string stage = Path.Combine(temp, "stage"); ValidatePackage(zip, stage, remote.Version); ApplyVerifiedApp(installRoot, Path.Combine(stage, "app")); }
    finally { if (Directory.Exists(temp)) Directory.Delete(temp, true); }
}
```

Create `version.json` containing `{ "version": "1.0.2" }`. Configure the exact OSS `latest.json` URL from the spec. `Start-App.cmd` must ignore the updater exit status and always attempt to start the first `app\*.exe`; it returns `2` only if no app EXE exists.

- [ ] **Step 4: Run transaction and launcher tests after implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Transaction; powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test Launcher`

Expected: both print `PASS`; a missing updater config yields check exit `1`, while the batch launcher still has the old GUI path available.

- [ ] **Step 5: Commit replacement and launcher**

```powershell
git add updater-src\UpdateAgent.cs updater-src\updater-config.json Start-App.cmd version.json test_updater.ps1
git commit -m "feat: replace app atomically with rollback"
```

### Task 4: Build the updater-aware portable layout without user data

**Files:**
- Create: `build.ps1`
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: `test_updater.ps1`

**Interfaces:**
- Consumes source `desktop_app.py`, `web/`, pinned `version.json`, `Start-App.cmd`, and `updater-src/`.
- Produces `dist\哔哩哔哩视频提取\{Start-App.cmd,updater\,app\}`.
- Produces `app\哔哩哔哩视频提取.exe`, `_internal\`, `ms-playwright\`, `tools\ffmpeg\bin\ffmpeg.exe`, `version.json`, and `使用说明.md`.

- [ ] **Step 1: Add failing build-layout and private-data tests**

```powershell
& .\build.ps1
Assert-True (Test-Path "$distRoot\Start-App.cmd") 'launcher missing'
Assert-True (Test-Path "$distRoot\updater\UpdateAgent.exe") 'updater missing'
Assert-True (@(Get-ChildItem "$distRoot\app\ms-playwright" -Directory -Filter 'chromium-*' | Get-ChildItem -Recurse -Filter chrome.exe -File).Count -gt 0) 'Chromium missing'
Assert-True (Test-Path "$distRoot\app\tools\ffmpeg\bin\ffmpeg.exe") 'ffmpeg missing'
Assert-False (@(Get-ChildItem $distRoot -Recurse -Include *.db,*.sqlite,*.log | Measure-Object).Count -gt 0) 'user data leaked into build'
```

- [ ] **Step 2: Run layout test before implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test PackageLayout`

Expected: FAIL because `build.ps1` does not exist.

- [ ] **Step 3: Implement isolated build layout**

```powershell
$builtApp = Join-Path $pyInstallerDist '哔哩哔哩视频提取'
$stagedApp = Join-Path $releaseDir 'app'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name '哔哩哔哩视频提取' --add-data "$PSScriptRoot\web;web" --distpath $pyInstallerDist --workpath $pyInstallerWork --specpath $buildRoot desktop_app.py
Move-Item -LiteralPath $builtApp -Destination $stagedApp
Copy-Item -LiteralPath $browserRoot -Destination (Join-Path $stagedApp 'ms-playwright') -Recurse -Force
Copy-Item -LiteralPath $ffmpegExe -Destination (Join-Path $stagedApp 'tools\ffmpeg\bin\ffmpeg.exe') -Force
Copy-Item -LiteralPath .\version.json -Destination (Join-Path $stagedApp 'version.json') -Force
Copy-Item -LiteralPath .\README.md -Destination (Join-Path $stagedApp '使用说明.md') -Force
& .\updater-src\build-updater.ps1 -OutputPath (Join-Path $releaseDir 'updater\UpdateAgent.exe')
Copy-Item .\updater-src\updater-config.json (Join-Path $releaseDir 'updater\updater-config.json') -Force
Copy-Item .\Start-App.cmd (Join-Path $releaseDir 'Start-App.cmd') -Force
```

The build must source Chromium and ffmpeg by explicit, inspected paths; it must not copy `data/`, `browser_session/`, logs, `.venv/`, or `%LOCALAPPDATA%`. Extend `.gitignore` for `dist/`, `build/`, `.venv/`, updater test output, and release ZIP artifacts. Update README to identify `Start-App.cmd` as the installed-package entry point and explain that v1.0.2 enables later automatic updates.

- [ ] **Step 4: Run layout test and existing business tests after implementation**

Run: `powershell -ExecutionPolicy Bypass -File .\test_updater.ps1 -Test PackageLayout; .\.venv\Scripts\python.exe -m unittest tests\test_core.py -v; .\.venv\Scripts\python.exe -m py_compile bilibili_client.py downloader.py desktop_app.py`

Expected: layout test prints `PASS`, all 8 business tests pass, and compilation exits `0`.

- [ ] **Step 5: Commit the package build**

```powershell
git add build.ps1 README.md .gitignore test_updater.ps1
git commit -m "build: stage portable updater layout"
```

### Task 5: Perform isolated end-to-end update verification and publish safely

**Files:**
- Create: `release-artifacts/` only in an ignored isolated build worktree
- Modify: `software-download-center/index.html` in its own repository only after OSS assets and manifests are public

**Interfaces:**
- Consumes the v1.0.2 full layout from Task 4.
- Produces a v1.0.2 full ZIP and v1.0.2 app-only update ZIP plus matching SHA-256 values.
- Produces OSS `latest.json` and `latest.js` only after immutable asset verification.

- [ ] **Step 1: Build test fixtures and assert no private files**

```powershell
$fullZip = Join-Path $artifactRoot 'bilibili-video-extractor-desktop-1.0.2-windows-x64.zip'
$updateZip = Join-Path $artifactRoot 'bilibili-video-extractor-desktop-update-1.0.2.zip'
[IO.Compression.ZipFile]::CreateFromDirectory($releaseDir, $fullZip)
[IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $artifactRoot 'payload-root-containing-only-app'), $updateZip)
$privateEntries = [IO.Compression.ZipFile]::OpenRead($fullZip).Entries.FullName | Where-Object { $_ -match '(^|/)(data|browser_session|logs)(/|$)|\.(db|sqlite|log)$' }
Assert-Equal 0 @($privateEntries).Count 'private user material leaked into full ZIP'
```

- [ ] **Step 2: Run isolated update and rollback acceptance before publishing**

Run: copy v1.0.2 full layout to a new temporary install directory; set a test `%LOCALAPPDATA%`; create a copy-only v1.0.3 acceptance payload by changing the copied payload's `app\version.json`; upload that immutable acceptance ZIP and a separate public HTTPS acceptance manifest under `updates/bilibili-video-extractor-desktop/acceptance/`; point only the copied install's `updater-config.json` at that acceptance manifest; run `Start-App.cmd`; inspect `app\version.json`; then run bad-hash and replacement-failure fixtures with direct transaction tests.

Expected: the acceptance install reaches `1.0.3`, the production `latest.json` remains untouched during acceptance, bad fixtures leave `1.0.2` runnable, no `app.previous/` remains after success, and the LocalAppData fixture hash is unchanged for all cases.

- [ ] **Step 3: Publish immutable assets before pointers**

```text
1. Push source and tag the updater-aware release only after all local tests pass.
2. Upload versioned full ZIP and app-only ZIP to OSS.
3. Publicly download both and compare SHA-256 with local values.
4. Upload latest.json and latest.js with the verified app-only URL and hash.
5. Update the download-site card to the verified full-package URL and version.
```

- [ ] **Step 4: Verify public release state**

Run: fetch public `latest.json`; download its update ZIP and compute SHA-256; load `https://download.luotuoqiluotuozhaoma.com/`; verify the Bilibili card shows v1.0.2 and the exact full ZIP link.

Expected: manifest reports v1.0.2 with the published immutable update ZIP and matching hash; website shows v1.0.2; no pointer references an unpublished asset.

- [ ] **Step 5: Commit only source and site changes separately**

```powershell
git -C C:\软件\bilibili提取 status --short
git -C 'C:\Users\Administrator\Documents\ChatGPT\更新 2\software-download-center' status --short
```

Expected: the source repository contains only updater source/build/docs changes, and the site repository contains only the Bilibili card/script update. Never commit generated ZIPs, tests' LocalAppData fixture, or user data.
