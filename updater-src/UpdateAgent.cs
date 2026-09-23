using System;
using System.Collections.Generic;
using System.IO;
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
        return 2;
    }
}
