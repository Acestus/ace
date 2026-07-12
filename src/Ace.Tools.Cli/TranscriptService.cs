using Microsoft.Data.Sqlite;
using System.Text.RegularExpressions;

namespace Ace.Tools.Cli;

internal static class TranscriptService
{
    private static readonly Regex TicketKeyPattern =
        new(@"\b[A-Z][A-Z0-9]{1,9}-\d+\b", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    public static async Task<TranscriptSyncResult> SyncAsync(
        string catalogDbPath,
        string? sessionStorePath,
        DateOnly? since,
        CancellationToken cancellationToken)
    {
        var storePath = ResolveSessionStorePath(sessionStorePath);
        if (!File.Exists(storePath))
        {
            throw new InvalidOperationException($"Session store not found: {storePath}");
        }

        EnsureCatalogDirectory(catalogDbPath);
        await using var catalog = new SqliteConnection($"Data Source={catalogDbPath}");
        await catalog.OpenAsync(cancellationToken);
        await EnsureSchemaAsync(catalog, cancellationToken);

        var sinceUtc = ResolveSinceUtc(since);
        await using var store = new SqliteConnection($"Data Source={storePath};Mode=ReadOnly");
        await store.OpenAsync(cancellationToken);

        var sessions = await ReadSessionsAsync(store, sinceUtc, cancellationToken);
        var turnCount = 0;
        var linkCount = 0;

        foreach (var session in sessions)
        {
            var turns = await ReadTurnsAsync(store, session.Id, cancellationToken);
            foreach (var turn in turns)
            {
                var refs = ExtractTicketRefs(turn.UserMessage, turn.AssistantResponse);
                await UpsertTurnAsync(catalog, session, turn, refs, cancellationToken);
                turnCount++;
                linkCount += await UpsertTicketLinksAsync(catalog, session.Id, turn.TurnIndex, refs, cancellationToken);
            }
        }

        return new TranscriptSyncResult(sessions.Count, turnCount, linkCount);
    }

    public static async Task<IReadOnlyList<TranscriptTurn>> ListByTicketAsync(
        string catalogDbPath,
        string ticketKey,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var catalog = await OpenCatalogAsync(catalogDbPath, cancellationToken);
        var cmd = catalog.CreateCommand();
        cmd.CommandText =
            """
            SELECT t.session_id, t.turn_index, t.session_date, t.session_summary,
                   t.user_message, t.assistant_response, t.session_ts
            FROM transcript_turns t
            JOIN transcript_ticket_links l
              ON t.session_id = l.session_id AND t.turn_index = l.turn_index
            WHERE UPPER(l.ticket_key) = UPPER($key)
            ORDER BY t.session_ts DESC, t.turn_index ASC
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$key", NormalizeTicketKey(ticketKey));
        cmd.Parameters.AddWithValue("$limit", limit);
        return await ReadTurnsAsync(cmd, cancellationToken);
    }

    public static async Task<IReadOnlyList<TranscriptTurn>> ListByTicketForDateAsync(
        string catalogDbPath,
        string ticketKey,
        DateOnly date,
        int limit,
        string? sessionId,
        CancellationToken cancellationToken)
    {
        await using var catalog = await OpenCatalogAsync(catalogDbPath, cancellationToken);
        var cmd = catalog.CreateCommand();
        var sql =
            """
            SELECT t.session_id, t.turn_index, t.session_date, t.session_summary,
                   t.user_message, t.assistant_response, t.session_ts
            FROM transcript_turns t
            JOIN transcript_ticket_links l
              ON t.session_id = l.session_id AND t.turn_index = l.turn_index
            WHERE UPPER(l.ticket_key) = UPPER($key)
              AND t.session_date = $date
            """;
        if (!string.IsNullOrWhiteSpace(sessionId))
        {
            sql += "\n  AND t.session_id = $session_id";
        }

        sql +=
            """
            
            ORDER BY t.session_ts ASC, t.turn_index ASC
            LIMIT $limit;
            """;

        cmd.CommandText = sql;
        cmd.Parameters.AddWithValue("$key", NormalizeTicketKey(ticketKey));
        cmd.Parameters.AddWithValue("$date", date.ToString("yyyy-MM-dd"));
        cmd.Parameters.AddWithValue("$limit", limit);
        if (!string.IsNullOrWhiteSpace(sessionId))
        {
            cmd.Parameters.AddWithValue("$session_id", sessionId);
        }

        return await ReadTurnsAsync(cmd, cancellationToken);
    }

    private static DateTime ResolveSinceUtc(DateOnly? since)
    {
        if (since is null)
        {
            return DateTime.UtcNow.AddDays(-90);
        }

        return since.Value.ToDateTime(TimeOnly.MinValue, DateTimeKind.Local).ToUniversalTime();
    }

    private static string ResolveSessionStorePath(string? sessionStorePath)
    {
        if (!string.IsNullOrWhiteSpace(sessionStorePath))
        {
            return Path.GetFullPath(sessionStorePath);
        }

        var repoRoot = RepoPaths.FindRepoRoot();
        var localPath = Path.Combine(repoRoot, ".catalog", "session-store.db");
        if (File.Exists(localPath))
        {
            return localPath;
        }

        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".copilot", "session-store.db");
    }

    private static string NormalizeTicketKey(string key) => key.Trim().ToUpperInvariant();

    private static IReadOnlyList<string> ExtractTicketRefs(string userMessage, string? assistantResponse)
    {
        var combined = $"{userMessage} {assistantResponse}";
        var refs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (Match match in TicketKeyPattern.Matches(combined))
        {
            refs.Add(match.Value.ToUpperInvariant());
        }

        return refs.OrderBy(value => value).ToArray();
    }

    private static async Task<SqliteConnection> OpenCatalogAsync(string catalogDbPath, CancellationToken cancellationToken)
    {
        EnsureCatalogDirectory(catalogDbPath);
        var catalog = new SqliteConnection($"Data Source={catalogDbPath}");
        await catalog.OpenAsync(cancellationToken);
        await EnsureSchemaAsync(catalog, cancellationToken);
        return catalog;
    }

    private static void EnsureCatalogDirectory(string catalogDbPath)
    {
        var directory = Path.GetDirectoryName(catalogDbPath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }
    }

    private static async Task<List<TranscriptSession>> ReadSessionsAsync(
        SqliteConnection store,
        DateTime sinceUtc,
        CancellationToken cancellationToken)
    {
        var cmd = store.CreateCommand();
        cmd.CommandText =
            """
            SELECT id, COALESCE(summary, ''), updated_at
            FROM sessions
            WHERE updated_at >= $since
            ORDER BY created_at ASC;
            """;
        cmd.Parameters.AddWithValue("$since", sinceUtc.ToString("O"));

        var rows = new List<TranscriptSession>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new TranscriptSession(reader.GetString(0), reader.GetString(1), reader.GetString(2)));
        }

        return rows;
    }

    private static async Task<List<TranscriptTurnRecord>> ReadTurnsAsync(
        SqliteConnection store,
        string sessionId,
        CancellationToken cancellationToken)
    {
        var cmd = store.CreateCommand();
        cmd.CommandText =
            """
            SELECT turn_index, COALESCE(user_message, ''), COALESCE(assistant_response, ''), timestamp
            FROM turns
            WHERE session_id = $id
            ORDER BY turn_index ASC;
            """;
        cmd.Parameters.AddWithValue("$id", sessionId);

        var rows = new List<TranscriptTurnRecord>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new TranscriptTurnRecord(
                reader.GetInt32(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3)));
        }

        return rows;
    }

    private static async Task UpsertTurnAsync(
        SqliteConnection catalog,
        TranscriptSession session,
        TranscriptTurnRecord turn,
        IReadOnlyList<string> refs,
        CancellationToken cancellationToken)
    {
        var sessionDate = turn.Timestamp.Length >= 10 ? turn.Timestamp[..10] : turn.Timestamp;
        var cmd = catalog.CreateCommand();
        cmd.CommandText =
            """
            INSERT INTO transcript_turns
              (session_id, turn_index, session_date, session_summary,
               user_message, assistant_response, ticket_refs, session_ts, synced_at)
            VALUES
              ($session_id, $turn_index, $session_date, $session_summary,
               $user_message, $assistant_response, $ticket_refs, $session_ts, $synced_at)
            ON CONFLICT(session_id, turn_index) DO UPDATE SET
              session_summary = excluded.session_summary,
              user_message = excluded.user_message,
              assistant_response = excluded.assistant_response,
              ticket_refs = excluded.ticket_refs,
              synced_at = excluded.synced_at;
            """;
        cmd.Parameters.AddWithValue("$session_id", session.Id);
        cmd.Parameters.AddWithValue("$turn_index", turn.TurnIndex);
        cmd.Parameters.AddWithValue("$session_date", sessionDate);
        cmd.Parameters.AddWithValue("$session_summary", string.IsNullOrWhiteSpace(session.Summary) ? DBNull.Value : session.Summary);
        cmd.Parameters.AddWithValue("$user_message", string.IsNullOrWhiteSpace(turn.UserMessage) ? DBNull.Value : turn.UserMessage);
        cmd.Parameters.AddWithValue("$assistant_response", string.IsNullOrWhiteSpace(turn.AssistantResponse) ? DBNull.Value : turn.AssistantResponse);
        cmd.Parameters.AddWithValue("$ticket_refs", refs.Count == 0 ? DBNull.Value : string.Join(",", refs));
        cmd.Parameters.AddWithValue("$session_ts", turn.Timestamp);
        cmd.Parameters.AddWithValue("$synced_at", DateTime.UtcNow.ToString("O"));
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task<int> UpsertTicketLinksAsync(
        SqliteConnection catalog,
        string sessionId,
        int turnIndex,
        IReadOnlyList<string> keys,
        CancellationToken cancellationToken)
    {
        var inserted = 0;
        foreach (var key in keys)
        {
            var cmd = catalog.CreateCommand();
            cmd.CommandText =
                """
                INSERT OR IGNORE INTO transcript_ticket_links (session_id, turn_index, ticket_key)
                VALUES ($session_id, $turn_index, $ticket_key);
                """;
            cmd.Parameters.AddWithValue("$session_id", sessionId);
            cmd.Parameters.AddWithValue("$turn_index", turnIndex);
            cmd.Parameters.AddWithValue("$ticket_key", key);
            inserted += await cmd.ExecuteNonQueryAsync(cancellationToken);
        }

        return inserted;
    }

    private static async Task<IReadOnlyList<TranscriptTurn>> ReadTurnsAsync(SqliteCommand cmd, CancellationToken cancellationToken)
    {
        var rows = new List<TranscriptTurn>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new TranscriptTurn(
                reader.GetString(0),
                reader.GetInt32(1),
                DateOnly.Parse(reader.GetString(2)),
                reader.IsDBNull(3) ? null : reader.GetString(3),
                reader.IsDBNull(4) ? null : reader.GetString(4),
                reader.IsDBNull(5) ? null : reader.GetString(5),
                reader.GetString(6)));
        }

        return rows;
    }

    private static async Task EnsureSchemaAsync(SqliteConnection connection, CancellationToken cancellationToken)
    {
        var cmd = connection.CreateCommand();
        cmd.CommandText =
            """
            CREATE TABLE IF NOT EXISTS transcript_turns (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id  TEXT    NOT NULL,
              turn_index  INTEGER NOT NULL,
              session_date TEXT   NOT NULL,
              session_summary TEXT,
              user_message TEXT,
              assistant_response TEXT,
              ticket_refs TEXT,
              session_ts  TEXT    NOT NULL,
              synced_at   TEXT    NOT NULL,
              UNIQUE(session_id, turn_index)
            ) STRICT;

            CREATE INDEX IF NOT EXISTS idx_transcript_turns_date
              ON transcript_turns(session_date);

            CREATE INDEX IF NOT EXISTS idx_transcript_turns_session
              ON transcript_turns(session_id);

            CREATE TABLE IF NOT EXISTS transcript_ticket_links (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id  TEXT NOT NULL,
              turn_index  INTEGER NOT NULL,
              ticket_key  TEXT NOT NULL,
              UNIQUE(session_id, turn_index, ticket_key)
            ) STRICT;

            CREATE INDEX IF NOT EXISTS idx_transcript_links_key
              ON transcript_ticket_links(ticket_key);
            """;
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }
}

internal sealed record TranscriptSyncResult(int SessionCount, int TurnCount, int LinkCount);

internal sealed record TranscriptTurn(
    string SessionId,
    int TurnIndex,
    DateOnly SessionDate,
    string? SessionSummary,
    string? UserMessage,
    string? AssistantResponse,
    string SessionTs);

internal sealed record TranscriptSession(string Id, string Summary, string UpdatedAt);

internal sealed record TranscriptTurnRecord(int TurnIndex, string UserMessage, string AssistantResponse, string Timestamp);
