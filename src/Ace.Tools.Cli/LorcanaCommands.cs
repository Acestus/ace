using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Ace.Tools.Cli;

internal static partial class LorcanaCommands
{
    private const string DefaultUrl = "https://lorcanaplayer.com/lorcana-card-list/";

    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0 || IsHelpRequest(args))
        {
            PrintHelp(stdout);
            return 0;
        }

        return args[0] switch
        {
            "scrape" => await ScrapeAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            _ => UnknownSubcommand(args[0], stderr)
        };
    }

    public static void PrintHelp(TextWriter stdout)
    {
        stdout.WriteLine("lorcana — Lorcana Player card-list tools");
        stdout.WriteLine();
        stdout.WriteLine("SUBCOMMANDS");
        stdout.WriteLine("  scrape          Scrape a set list from lorcanaplayer.com into assets/lorcana/");
        stdout.WriteLine();
        stdout.WriteLine("EXAMPLES");
        stdout.WriteLine("  lorcana scrape https://lorcanaplayer.com/lorcana-card-list/#attack-of-the-vine");
        stdout.WriteLine("  lorcana scrape --set \"Attack of the Vine!\"");
        stdout.WriteLine("  lorcana scrape --url https://lorcanaplayer.com/attack-of-the-vine-card-list-lorcana-set-13/");
        stdout.WriteLine();
        stdout.WriteLine("OPTIONS");
        stdout.WriteLine("  --url <url>     Lorcana Player card-list URL. Defaults to the all-sets list.");
        stdout.WriteLine("  --set <name>    Set title to scrape when the URL does not include a useful fragment.");
        stdout.WriteLine("  --output <path> Output file. Defaults to assets/lorcana/<set-slug>-copypaste.txt.");
    }

    private static async Task<int> ScrapeAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        var positionalUrl = args.FirstOrDefault(arg => !arg.StartsWith("-", StringComparison.Ordinal));
        var rawUrl = CommandHelpers.GetOptionValue(args, "--url") ?? positionalUrl ?? DefaultUrl;
        var requestedSet = CommandHelpers.GetOptionValue(args, "--set");

        using var http = new HttpClient();
        http.DefaultRequestHeaders.UserAgent.ParseAdd("Ace.Tools.Cli/1.0");

        var uri = new Uri(rawUrl);
        var pageUrl = uri.GetLeftPart(UriPartial.Path);
        var html = await http.GetStringAsync(pageUrl, cancellationToken);

        requestedSet ??= GetSetNameFromFragment(html, uri.Fragment.TrimStart('#'));

        var blocks = FindCardListBlocks(html);
        var block = SelectBlock(blocks, requestedSet);
        if (block is null)
        {
            stderr.WriteLine(requestedSet is null
                ? "❌ Could not find a Lorcana card-list block on the page."
                : $"❌ Could not find a Lorcana card-list block for set: {requestedSet}");
            return 1;
        }

        var rows = ParseRows(block.Html).ToList();
        if (block.TwoStageEnabled)
        {
            var remainingHtml = await LoadRemainingCardsAsync(http, pageUrl, block, cancellationToken);
            rows.AddRange(ParseRows(remainingHtml));
        }

        rows = rows
            .GroupBy(row => row.Number + "\u001f" + row.Name)
            .Select(group => group.First())
            .OrderBy(row => ParseCardNumber(row.Number))
            .ToList();

        if (rows.Count == 0)
        {
            stderr.WriteLine($"❌ No cards parsed for {block.SetName}.");
            return 1;
        }

        var outputPath = CommandHelpers.GetOptionValue(args, "--output")
            ?? Path.Combine("assets", "lorcana", $"{Slugify(block.SetName)}-copypaste.txt");

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        await File.WriteAllTextAsync(outputPath, FormatCopyPaste(rows), cancellationToken);

        stdout.WriteLine($"✅ Wrote {rows.Count} cards for {block.SetName}");
        stdout.WriteLine($"   {outputPath}");
        return 0;
    }

    private static IReadOnlyList<CardListBlock> FindCardListBlocks(string html)
    {
        var starts = CardListBlockStartRegex().Matches(html).Select(match => match.Index).ToList();
        var blocks = new List<CardListBlock>();

        for (var i = 0; i < starts.Count; i++)
        {
            var start = starts[i];
            var end = i + 1 < starts.Count ? starts[i + 1] : html.Length;
            var blockHtml = html[start..end];
            var dataAtts = GetAttribute(blockHtml, "data-atts");
            if (string.IsNullOrWhiteSpace(dataAtts))
            {
                continue;
            }

            var decodedAtts = WebUtility.HtmlDecode(dataAtts);
            using var document = JsonDocument.Parse(decodedAtts);
            var root = document.RootElement;
            var setName = root.GetProperty("set").GetString();
            if (string.IsNullOrWhiteSpace(setName))
            {
                continue;
            }

            blocks.Add(new CardListBlock(
                setName,
                GetAttribute(blockHtml, "data-nonce") ?? string.Empty,
                root.TryGetProperty("default_sort", out var sort) ? sort.GetString() ?? "card_number" : "card_number",
                root.TryGetProperty("default_direction", out var direction) ? direction.GetString() ?? "asc" : "asc",
                root.TryGetProperty("display_options", out var displayOptions)
                    ? displayOptions.GetRawText()
                    : "{\"show_images\":true,\"show_type\":true,\"show_ink_colors\":true,\"show_rarity\":true}",
                string.Equals(GetAttribute(blockHtml, "data-two-stage-enabled"), "true", StringComparison.OrdinalIgnoreCase),
                blockHtml));
        }

        return blocks;
    }

    private static CardListBlock? SelectBlock(IReadOnlyList<CardListBlock> blocks, string? requestedSet)
    {
        if (blocks.Count == 0)
        {
            return null;
        }

        if (string.IsNullOrWhiteSpace(requestedSet))
        {
            return blocks[0];
        }

        return blocks.FirstOrDefault(block => string.Equals(block.SetName, requestedSet, StringComparison.OrdinalIgnoreCase))
            ?? blocks.FirstOrDefault(block => Slugify(block.SetName) == Slugify(requestedSet));
    }

    private static async Task<string> LoadRemainingCardsAsync(
        HttpClient http,
        string pageUrl,
        CardListBlock block,
        CancellationToken cancellationToken)
    {
        var ajaxUri = new Uri(new Uri(pageUrl), "/wp-admin/admin-ajax.php");
        using var form = new MultipartFormDataContent
        {
            { new StringContent("cardadmin_load_remaining"), "action" },
            { new StringContent(block.SetName), "set" },
            { new StringContent(block.SortField), "sort_field" },
            { new StringContent(block.SortDirection), "sort_direction" },
            { new StringContent(block.DisplayOptionsJson), "display_options" },
            { new StringContent(block.Nonce), "nonce" }
        };

        using var response = await http.PostAsync(ajaxUri, form, cancellationToken);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        if (!root.TryGetProperty("success", out var success) || !success.GetBoolean())
        {
            throw new InvalidOperationException("Lorcana Player AJAX response did not indicate success.");
        }

        return root.GetProperty("data").GetProperty("html").GetString() ?? string.Empty;
    }

    private static IEnumerable<CardRow> ParseRows(string html)
    {
        foreach (Match rowMatch in RowRegex().Matches(html))
        {
            var cells = CellRegex().Matches(rowMatch.Groups["html"].Value).Cast<Match>().Select(match => match.Groups["html"].Value).ToList();
            if (cells.Count < 6)
            {
                continue;
            }

            var number = CleanText(cells[1]);
            var name = CleanText(cells[2]);
            var ink = ExtractInk(cells[4]);
            var rarity = ExtractTitleOrText(cells[5]);

            if (string.IsNullOrWhiteSpace(number) || string.IsNullOrWhiteSpace(name))
            {
                continue;
            }

            yield return new CardRow(number, name, rarity, ink);
        }
    }

    private static string ExtractInk(string html)
    {
        var split = Regex.Match(html, @"class=""split-icon""[^>]*\btitle=""(?<title>[^""]+)""", RegexOptions.IgnoreCase);
        if (split.Success)
        {
            return CleanText(split.Groups["title"].Value);
        }

        var titles = Regex.Matches(html, @"\b(?:alt|title)=""(?<value>Amber|Amethyst|Emerald|Ruby|Sapphire|Steel)""", RegexOptions.IgnoreCase)
            .Cast<Match>()
            .Select(match => CleanText(match.Groups["value"].Value))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        return titles.Count > 0 ? string.Join(" / ", titles) : CleanText(html);
    }

    private static string ExtractTitleOrText(string html)
    {
        var title = Regex.Match(html, @"\btitle=""(?<title>[^""]+)""", RegexOptions.IgnoreCase);
        return title.Success ? CleanText(title.Groups["title"].Value) : CleanText(html);
    }

    private static string? GetSetNameFromFragment(string html, string fragment)
    {
        if (string.IsNullOrWhiteSpace(fragment))
        {
            return null;
        }

        var pattern = $@"<a\b[^>]*href=""#{Regex.Escape(fragment)}""[^>]*>(?<name>.*?)</a>";
        var match = Regex.Match(html, pattern, RegexOptions.IgnoreCase | RegexOptions.Singleline);
        return match.Success ? CleanText(match.Groups["name"].Value) : fragment.Replace('-', ' ');
    }

    private static string? GetAttribute(string html, string name)
    {
        var match = Regex.Match(html, $@"\b{Regex.Escape(name)}=""(?<value>[^""]*)""", RegexOptions.IgnoreCase);
        return match.Success ? WebUtility.HtmlDecode(match.Groups["value"].Value) : null;
    }

    private static string CleanText(string html)
    {
        var withoutTags = Regex.Replace(html, "<.*?>", " ", RegexOptions.Singleline);
        var decoded = WebUtility.HtmlDecode(withoutTags);
        return Regex.Replace(decoded, @"\s+", " ").Trim();
    }

    private static int ParseCardNumber(string number)
    {
        var match = Regex.Match(number, @"^\d+");
        return match.Success && int.TryParse(match.Value, out var value) ? value : int.MaxValue;
    }

    private static string FormatCopyPaste(IReadOnlyList<CardRow> rows)
    {
        var builder = new StringBuilder();

        builder.AppendLine("=== NAMES ===");
        foreach (var row in rows)
        {
            builder.AppendLine(row.Name);
        }

        builder.AppendLine();
        builder.AppendLine("=== RARITY ===");
        foreach (var row in rows)
        {
            builder.AppendLine(row.Rarity);
        }

        builder.AppendLine();
        builder.AppendLine("=== INK COLOR ===");
        foreach (var row in rows)
        {
            builder.AppendLine(row.Ink);
        }

        return builder.ToString();
    }

    private static string Slugify(string value)
    {
        var lower = value.ToLowerInvariant().Replace("&", "and");
        var slug = Regex.Replace(lower, @"[^a-z0-9]+", "-").Trim('-');
        return Regex.Replace(slug, "-{2,}", "-");
    }

    private static bool IsHelpRequest(string[] args) => args.Length > 0 && args[0] is "help" or "--help" or "-h";

    private static int UnknownSubcommand(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown lorcana command: {command}");
        return 2;
    }

    private sealed record CardListBlock(
        string SetName,
        string Nonce,
        string SortField,
        string SortDirection,
        string DisplayOptionsJson,
        bool TwoStageEnabled,
        string Html);

    private sealed record CardRow(string Number, string Name, string Rarity, string Ink);

    [GeneratedRegex(@"<div\b(?=[^>]*\bid=""card-list-block-[^""]+"")(?=[^>]*\bclass=""card-list-block"")[^>]*>", RegexOptions.IgnoreCase)]
    private static partial Regex CardListBlockStartRegex();

    [GeneratedRegex(@"<tr>(?<html>.*?)</tr>", RegexOptions.IgnoreCase | RegexOptions.Singleline)]
    private static partial Regex RowRegex();

    [GeneratedRegex(@"<td[^>]*>(?<html>.*?)</td>", RegexOptions.IgnoreCase | RegexOptions.Singleline)]
    private static partial Regex CellRegex();
}
