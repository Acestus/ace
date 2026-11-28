#!/usr/bin/env dotnet
#:sdk Microsoft.NET.Sdk
#:property TargetFramework=net10.0

using System.Diagnostics;

const string DefaultSource = "/media/acestus/INFUSE1/infuse01/";
const string DefaultDestinationHost = "violet";
const string DefaultDestination = "/media/violet/movies01/infuse01/";

var source = GetOption("--source", DefaultSource);
var host = GetOption("--host", DefaultDestinationHost);
var destination = GetOption("--destination", DefaultDestination);
var dryRun = HasFlag("--dry-run");

if (HasFlag("--help") || HasFlag("-h"))
{
    Console.WriteLine("Synchronize Eleanor media to Violet without deleting destination files.");
    Console.WriteLine();
    Console.WriteLine("Usage:");
    Console.WriteLine("  dotnet run --file ~/git/ace/scripts/sync-media.cs");
    Console.WriteLine();
    Console.WriteLine("Options:");
    Console.WriteLine($"  --source PATH       Source directory (default: {DefaultSource})");
    Console.WriteLine($"  --host HOST         SSH destination host (default: {DefaultDestinationHost})");
    Console.WriteLine($"  --destination PATH  Destination directory (default: {DefaultDestination})");
    Console.WriteLine("  --dry-run           Show what would transfer without copying");
    return;
}

if (!Directory.Exists(source))
    throw new DirectoryNotFoundException($"Source directory is not mounted: {source}");

var arguments = new List<string>
{
    "-aP",
    "--partial",
    "--append-verify",
    "--update",
    "--no-owner",
    "--no-group",
    "--exclude=.DS_Store",
    "--exclude=Thumbs.db",
    "--exclude=desktop.ini",
    "--exclude=*.parts",
    "--exclude=.*parts",
    "--exclude=*.tmp",
    "--exclude=*.temp",
    "--info=progress2",
};

if (dryRun)
    arguments.Add("--dry-run");

arguments.Add(source);
arguments.Add($"{host}:{destination}");

Console.WriteLine("Eleanor → Violet media sync");
Console.WriteLine($"  Source:      {source}");
Console.WriteLine($"  Destination: {host}:{destination}");
Console.WriteLine($"  Dry run:     {dryRun}");
Console.WriteLine("  Policy:      no destination deletion; partial files are retained");
Console.WriteLine();

var psi = new ProcessStartInfo
{
    FileName = "rsync",
    UseShellExecute = false,
    RedirectStandardOutput = false,
    RedirectStandardError = false,
};
foreach (var argument in arguments)
    psi.ArgumentList.Add(argument);

using var process = Process.Start(psi) ?? throw new InvalidOperationException("Could not start rsync.");
await process.WaitForExitAsync();
Environment.ExitCode = process.ExitCode;

string GetOption(string name, string fallback)
{
    for (var i = 0; i < args.Length - 1; i++)
        if (args[i].Equals(name, StringComparison.Ordinal))
            return args[i + 1];
    return fallback;
}

bool HasFlag(string name) => args.Any(a => a.Equals(name, StringComparison.Ordinal));
