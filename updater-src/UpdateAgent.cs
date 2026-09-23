using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

public sealed class ReleaseManifest
{
    public Version Version { get; private set; }
    public Uri PackageUri { get; private set; }
    public string Sha256 { get; private set; }

    public ReleaseManifest(Version version, Uri packageUri, string sha256)
    {
        Version = version;
        PackageUri = packageUri;
        Sha256 = sha256;
    }
}

public static class Updater
{
    public static bool IsNewer(Version remote, Version local)
    {
        if (remote == null) throw new ArgumentNullException("remote");
        if (local == null) throw new ArgumentNullException("local");
        return remote.CompareTo(local) > 0;
    }

    public static ReleaseManifest ParseManifest(string json, Uri manifestUri)
    {
        RequireHttps(manifestUri, "manifest URL");
        if (String.IsNullOrWhiteSpace(json)) throw new InvalidOperationException("Manifest is empty.");

        IDictionary<string, object> fields = new JavaScriptSerializer().DeserializeObject(json) as IDictionary<string, object>;
        string versionText = RequiredString(fields, "version");
        string packageText = RequiredString(fields, "url");
        string sha256 = RequiredString(fields, "sha256");

        Version version;
        if (!Version.TryParse(versionText, out version)) throw new InvalidOperationException("Manifest version is invalid.");
        if (!Regex.IsMatch(sha256, "^[A-Fa-f0-9]{64}$")) throw new InvalidOperationException("Manifest SHA-256 is invalid.");

        Uri packageUri;
        if (!Uri.TryCreate(packageText, UriKind.Absolute, out packageUri)) throw new InvalidOperationException("Manifest package URL is invalid.");
        RequireHttps(packageUri, "package URL");
        return new ReleaseManifest(version, packageUri, sha256);
    }

    public static string VerifyFileSha256(string filePath, string expectedSha256)
    {
        if (String.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath)) throw new InvalidOperationException("Package file is missing.");
        if (!Regex.IsMatch(expectedSha256 ?? String.Empty, "^[A-Fa-f0-9]{64}$")) throw new InvalidOperationException("Expected SHA-256 is invalid.");

        string actual;
        using (FileStream stream = File.OpenRead(filePath))
        using (SHA256 sha256 = SHA256.Create())
        {
            actual = BitConverter.ToString(sha256.ComputeHash(stream)).Replace("-", String.Empty);
        }
        if (!String.Equals(actual, expectedSha256, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Package SHA-256 does not match the manifest.");
        return actual;
    }

    public static string DownloadAndVerify(Uri packageUri, string expectedSha256, string temporaryDirectory)
    {
        RequireHttps(packageUri, "package URL");
        if (String.IsNullOrWhiteSpace(temporaryDirectory)) throw new InvalidOperationException("Temporary directory is required.");

        Directory.CreateDirectory(temporaryDirectory);
        string targetPath = Path.Combine(temporaryDirectory, Guid.NewGuid().ToString("N") + ".zip");
        try
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(packageUri);
            request.AllowAutoRedirect = false;
            request.Timeout = 30000;
            request.ReadWriteTimeout = 30000;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {
                if (response.StatusCode != HttpStatusCode.OK) throw new InvalidOperationException("Package download did not return HTTP 200.");
                using (Stream source = response.GetResponseStream())
                using (FileStream destination = File.Create(targetPath))
                {
                    source.CopyTo(destination);
                }
            }
            VerifyFileSha256(targetPath, expectedSha256);
            return targetPath;
        }
        catch
        {
            if (File.Exists(targetPath)) File.Delete(targetPath);
            throw;
        }
    }

    public static void ValidatePackage(string zipPath, string stagingDirectory, Version expectedVersion)
    {
        if (String.IsNullOrWhiteSpace(zipPath) || !File.Exists(zipPath)) throw new InvalidOperationException("Package ZIP is missing.");
        if (String.IsNullOrWhiteSpace(stagingDirectory)) throw new InvalidOperationException("Staging directory is required.");
        if (expectedVersion == null) throw new ArgumentNullException("expectedVersion");
        if (Directory.Exists(stagingDirectory)) Directory.Delete(stagingDirectory, true);
        Directory.CreateDirectory(stagingDirectory);

        string appRoot = Path.GetFullPath(Path.Combine(stagingDirectory, "app")).TrimEnd(Path.DirectorySeparatorChar);
        string appPrefix = appRoot + Path.DirectorySeparatorChar;
        string appEntryRoot = "app" + Path.DirectorySeparatorChar;
        try
        {
            using (ZipArchive archive = ZipFile.OpenRead(zipPath))
            {
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string name = entry.FullName.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
                    if (!name.StartsWith(appEntryRoot, StringComparison.Ordinal) && name != appEntryRoot)
                        throw new InvalidOperationException("ZIP must contain only the app directory.");

                    string target = Path.GetFullPath(Path.Combine(stagingDirectory, name));
                    if (!String.Equals(target, appRoot, StringComparison.OrdinalIgnoreCase) && !target.StartsWith(appPrefix, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidOperationException("ZIP contains an unsafe path.");

                    if (String.IsNullOrEmpty(entry.Name)) Directory.CreateDirectory(target);
                    else
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(target));
                        entry.ExtractToFile(target, true);
                    }
                }
            }
            ValidateInstalledApp(Path.Combine(stagingDirectory, "app"), expectedVersion);
        }
        catch
        {
            if (Directory.Exists(stagingDirectory)) Directory.Delete(stagingDirectory, true);
            throw;
        }
    }

    public static void ApplyVerifiedApp(string installRoot, string stagedAppDirectory)
    {
        if (String.IsNullOrWhiteSpace(installRoot) || String.IsNullOrWhiteSpace(stagedAppDirectory)) throw new InvalidOperationException("Install paths are required.");
        string app = Path.Combine(installRoot, "app");
        string backup = Path.Combine(installRoot, "app.previous");
        if (!Directory.Exists(stagedAppDirectory)) throw new InvalidOperationException("Validated app directory is missing.");
        if (Directory.Exists(backup)) Directory.Delete(backup, true);
        try
        {
            if (Directory.Exists(app)) Directory.Move(app, backup);
            Directory.Move(stagedAppDirectory, app);
            ValidateInstalledApp(app, null);
            if (Directory.Exists(backup)) Directory.Delete(backup, true);
        }
        catch
        {
            if (Directory.Exists(app)) Directory.Delete(app, true);
            if (Directory.Exists(backup)) Directory.Move(backup, app);
            throw;
        }
    }

    public static void RecoverInterruptedUpdate(string installRoot)
    {
        string app = Path.Combine(installRoot, "app");
        string backup = Path.Combine(installRoot, "app.previous");
        if (!Directory.Exists(app) && Directory.Exists(backup)) Directory.Move(backup, app);
    }

    private static void ValidateInstalledApp(string appDirectory, Version expectedVersion)
    {
        if (!Directory.Exists(appDirectory)) throw new InvalidOperationException("Package app directory is missing.");
        if (Directory.GetFiles(appDirectory, "*.exe").Length != 1) throw new InvalidOperationException("Package GUI executable is missing.");
        if (!Directory.Exists(Path.Combine(appDirectory, "_internal"))) throw new InvalidOperationException("Package internal directory is missing.");
        if (!Directory.Exists(Path.Combine(appDirectory, "ms-playwright"))) throw new InvalidOperationException("Package Chromium is missing.");
        if (!File.Exists(Path.Combine(appDirectory, "tools", "ffmpeg", "bin", "ffmpeg.exe"))) throw new InvalidOperationException("Package ffmpeg is missing.");

        string usageName = new String(new[] { (char)0x4F7F, (char)0x7528, (char)0x8BF4, (char)0x660E }) + ".md";
        if (!File.Exists(Path.Combine(appDirectory, usageName))) throw new InvalidOperationException("Package usage document is missing.");
        string versionPath = Path.Combine(appDirectory, "version.json");
        if (!File.Exists(versionPath)) throw new InvalidOperationException("Package version file is missing.");

        IDictionary<string, object> fields = new JavaScriptSerializer().DeserializeObject(File.ReadAllText(versionPath)) as IDictionary<string, object>;
        Version packageVersion;
        if (!Version.TryParse(RequiredString(fields, "version"), out packageVersion)) throw new InvalidOperationException("Package version is invalid.");
        if (expectedVersion != null && packageVersion.CompareTo(expectedVersion) != 0)
            throw new InvalidOperationException("Package version does not match the manifest version.");
    }

    private static string RequiredString(IDictionary<string, object> fields, string name)
    {
        object value;
        if (fields == null || !fields.TryGetValue(name, out value) || !(value is string) || String.IsNullOrWhiteSpace((string)value))
            throw new InvalidOperationException("Manifest field '" + name + "' is required.");
        return ((string)value).Trim();
    }

    private static void RequireHttps(Uri uri, string label)
    {
        if (uri == null || !String.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(label + " must use HTTPS.");
    }
}

public static class Program
{
    public static int Main(string[] args)
    {
        if (args.Length != 2 || !String.Equals(args[0], "--check", StringComparison.Ordinal)) return 2;
        try
        {
            RunCheck(args[1]);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("Update check failed: " + error.Message);
            return 1;
        }
    }

    private static void RunCheck(string configPath)
    {
        if (String.IsNullOrWhiteSpace(configPath) || !File.Exists(configPath)) throw new InvalidOperationException("Updater config is missing.");
        IDictionary<string, object> config = new JavaScriptSerializer().DeserializeObject(File.ReadAllText(configPath)) as IDictionary<string, object>;
        string manifestText = RequiredConfigString(config, "manifestUrl");
        Uri manifestUri;
        if (!Uri.TryCreate(manifestText, UriKind.Absolute, out manifestUri)) throw new InvalidOperationException("Manifest URL is invalid.");
        if (!String.Equals(manifestUri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Manifest URL must use HTTPS.");

        string updaterDirectory = Path.GetDirectoryName(typeof(Program).Assembly.Location);
        string installRoot = Directory.GetParent(updaterDirectory).FullName;
        Updater.RecoverInterruptedUpdate(installRoot);
        Version localVersion = ReadLocalVersion(Path.Combine(installRoot, "app", "version.json"));
        ReleaseManifest remote = Updater.ParseManifest(DownloadText(manifestUri), manifestUri);
        if (!Updater.IsNewer(remote.Version, localVersion)) return;

        string temporaryDirectory = Path.Combine(Path.GetTempPath(), "bilibili-update-" + Guid.NewGuid().ToString("N"));
        try
        {
            string zipPath = Updater.DownloadAndVerify(remote.PackageUri, remote.Sha256, temporaryDirectory);
            string stage = Path.Combine(temporaryDirectory, "stage");
            Updater.ValidatePackage(zipPath, stage, remote.Version);
            Updater.ApplyVerifiedApp(installRoot, Path.Combine(stage, "app"));
        }
        finally
        {
            if (Directory.Exists(temporaryDirectory)) Directory.Delete(temporaryDirectory, true);
        }
    }

    private static string DownloadText(Uri uri)
    {
        HttpWebRequest request = (HttpWebRequest)WebRequest.Create(uri);
        request.AllowAutoRedirect = false;
        request.Timeout = 30000;
        using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
        {
            if (response.StatusCode != HttpStatusCode.OK) throw new InvalidOperationException("Manifest download did not return HTTP 200.");
            using (StreamReader reader = new StreamReader(response.GetResponseStream())) return reader.ReadToEnd();
        }
    }

    private static Version ReadLocalVersion(string versionPath)
    {
        if (!File.Exists(versionPath)) throw new InvalidOperationException("Local version file is missing.");
        IDictionary<string, object> fields = new JavaScriptSerializer().DeserializeObject(File.ReadAllText(versionPath)) as IDictionary<string, object>;
        Version version;
        if (!Version.TryParse(RequiredConfigString(fields, "version"), out version)) throw new InvalidOperationException("Local version is invalid.");
        return version;
    }

    private static string RequiredConfigString(IDictionary<string, object> fields, string name)
    {
        object value;
        if (fields == null || !fields.TryGetValue(name, out value) || !(value is string) || String.IsNullOrWhiteSpace((string)value))
            throw new InvalidOperationException("Required field '" + name + "' is missing.");
        return ((string)value).Trim();
    }
}
