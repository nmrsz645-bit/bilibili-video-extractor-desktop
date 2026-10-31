# Historical safe snapshot: opt-in updater prototype

Captured 2026-10-31 from an older, uncommitted local worktree. **Backup only.** This branch is not the official v1.0.3/v1.0.4 source, not a release candidate, and must not be merged into `master` without a new review. No production OSS manifest, download page, or installed program was changed by this backup.

## Recovery basis

- Verified repository: `nmrsz645-bit/bilibili-video-extractor-desktop` (public).
- Base commit: `091c2baf1a311b3e8d348458dd1a44f4c36327bd` (`version.json` 1.0.2).
- This branch copies the nine modified tracked project files from the historical worktree, including its local `version.json` 1.0.3, and two small generated metadata files. Existing `db.py` and `tests/test_core.py` content was already preserved in the current official repository history; they are included here to reconstruct the exact historical worktree state.
- Source worktree had no staged changes. Its original files and Git index were not modified. Do not use this snapshot's opt-in manifest as the current production manifest.

## Captured source and metadata

SHA-256 values below are for the captured local file bytes before Git checkout line-ending transformations. The 11 selected files are also preserved byte-for-byte in `backup-assets/opt-in-1.0.3/source-worktree-raw.zip` (18,721 bytes, SHA-256 `3A00F95D2D580DDF18BB08E1508B277C3958910BC0A5EF0738545A48E9ECC468`). It contains only the listed project files; it is not a program package or a copy of the generated `release/` directory.

| Path in this branch | SHA-256 |
| --- | --- |
| `README.md` | `24086E5D9DA0BABC039CECE1BAF26929AC69CF041E096EF1A8D0EC950DD43AF7` |
| `db.py` | `2DAAFB0FC1E86F5B3A8E954C72589E7E5DCCEFC05B6B1962D1397B111427D263` |
| `docs/superpowers/specs/2026-09-22-bilibili-auto-update-design.md` | `789EA1709F2259DA5DCF7D0B679BE45087A3D879ABCF7199FFCAD9070613E1DE` |
| `test_updater.ps1` | `989EB95A576CE116B0F7367712EFF9172793E1611258106CB98091D09693487E` |
| `tests/test_core.py` | `0413EA38313323CB6684993C678F5040CCBDAC1A1726F05617464534CA27F03A` |
| `updater-src/UpdateAgent.cs` | `5EC088587263CB06C66273A06EFD9353E58F23477ADE9DC6D675A62CB390FAB1` |
| `updater-src/build-updater.ps1` | `6A1E667B28D61D6E227ECAACB5F7459BFEDC2D56C979B936D653B0DC0031E7D1` |
| `updater-src/updater-config.json` | `2D82217ADC6E779CBFE718E8130909BE4E967864452560E4F5F8D7A52F2185EA` |
| `version.json` | `B98A567BBD173ECEC9C42D4F0DB733207F0FE320A937CEF421D3FE62A1F29950` |
| `backup-assets/opt-in-1.0.3/latest.js` | `E2836946E4250CEF246FC698C48FF0CF0DEDE976E3F772E5CCE87586B3C5C374` |
| `backup-assets/opt-in-1.0.3/latest.json` | `A51B7620AF03D04D5B8E421831DE22283AA869035D29D2CE09BDD3ABECA92E2C` |

## Historical binary assets

The original worktree also held two generated ZIPs. They are too large for normal Git source history; see the **non-Latest backup prerelease** tagged `backup-existing-safe-20261031` and `BACKUP-ASSET-SHA256SUMS.txt`. The full ZIP has 3117 entries rooted at `Start-App.cmd`, `app/`, and `updater/`; the update ZIP has 3114 entries rooted only at `app/`. Both passed ZIP CRC and filename checks. This does not establish a new successful build or functional test.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `bilibili-video-extractor-1.0.3-windows-x64.zip` | 492765318 | `FBB7FE4DA62958CCC350B407B3F7608272CFF1A8CF1514FEC7CEF970F921D988` |
| `bilibili-video-extractor-update-1.0.3.zip` | 480768934 | `041D2BC9C9D07F05F853B1E2EAC2FB7E98B8EC88A0B95F3D197C9DFFB8E6759B` |

Excluded: generated unpacked payload and third-party Chromium/FFmpeg/Python libraries, old build caches and downloaded verification copies, virtual environments, logs, cookies, browser profiles, databases, user media and other business data. No secret values were copied. Dependency sources remain `requirements.txt`, `build.ps1`, Playwright's official browser installer and the documented FFmpeg source in the repository history; there is no exact lockfile for this historical build.

To inspect, fetch `backup/existing-safe-20261031`, compare against base `091c2ba`, and read this file first. Restore individual source files only after review; the official production branch and the current v1.0.4 Release remain separate.
