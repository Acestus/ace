using Microsoft.Data.Sqlite;

namespace Ace.Tools.Cli;

/// <summary>
/// SQLite-backed state for the rounds work session engine.
/// Database lives at ~/.ace/rounds.db and survives machine reboots.
/// </summary>
internal static class RoundsDb
{
    private static readonly string DbPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
        ".ace",
        "rounds.db");

    // ---------------------------------------------------------------------------
    // Schema
    // ---------------------------------------------------------------------------

    private static async Task EnsureSchemaAsync(SqliteConnection connection, CancellationToken cancellationToken)
    {
        var cmd = connection.CreateCommand();
        cmd.CommandText = """
            CREATE TABLE IF NOT EXISTS claims (
                lane        INTEGER PRIMARY KEY,
                key         TEXT    NOT NULL,
                claimed_at  TEXT    NOT NULL,
                pid         INTEGER
            );

            CREATE TABLE IF NOT EXISTS worklogs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session     TEXT,
                lane        INTEGER,
                key         TEXT,
                action      TEXT,
                note        TEXT,
                ts          TEXT DEFAULT (datetime('now'))
            );
            """;
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task<SqliteConnection> OpenAsync(CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(DbPath)!);
        var connection = new SqliteConnection($"Data Source={DbPath}");
        await connection.OpenAsync(cancellationToken);
        await EnsureSchemaAsync(connection, cancellationToken);
        return connection;
    }

    // ---------------------------------------------------------------------------
    // Claims
    // ---------------------------------------------------------------------------

    /// <summary>Returns all active lane → key claims, auto-expiring stale ones (>4h).</summary>
    public static async Task<Dictionary<int, ClaimRow>> GetClaimsAsync(CancellationToken cancellationToken)
    {
        await using var connection = await OpenAsync(cancellationToken);

        // Expire stale claims before reading
        var expire = connection.CreateCommand();
        expire.CommandText = """
            DELETE FROM claims
            WHERE claimed_at < datetime('now', '-4 hours');
            """;
        await expire.ExecuteNonQueryAsync(cancellationToken);

        var select = connection.CreateCommand();
        select.CommandText = "SELECT lane, key, claimed_at, pid FROM claims;";

        var result = new Dictionary<int, ClaimRow>();
        await using var reader = await select.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            var lane = reader.GetInt32(0);
            result[lane] = new ClaimRow(lane, reader.GetString(1), reader.GetString(2), reader.IsDBNull(3) ? null : reader.GetInt32(3));
        }

        return result;
    }

    /// <summary>Writes or overwrites the claim for a lane.</summary>
    public static async Task SetClaimAsync(int lane, string key, CancellationToken cancellationToken)
    {
        await using var connection = await OpenAsync(cancellationToken);
        var cmd = connection.CreateCommand();
        cmd.CommandText = """
            INSERT INTO claims (lane, key, claimed_at, pid)
            VALUES ($lane, $key, datetime('now'), $pid)
            ON CONFLICT(lane) DO UPDATE SET
                key        = excluded.key,
                claimed_at = excluded.claimed_at,
                pid        = excluded.pid;
            """;
        cmd.Parameters.AddWithValue("$lane", lane);
        cmd.Parameters.AddWithValue("$key", key.ToUpperInvariant());
        cmd.Parameters.AddWithValue("$pid", (object?)Environment.ProcessId ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }

    /// <summary>Removes the claim for a lane (on exit / transition to done/waiting).</summary>
    public static async Task ClearClaimAsync(int lane, CancellationToken cancellationToken)
    {
        await using var connection = await OpenAsync(cancellationToken);
        var cmd = connection.CreateCommand();
        cmd.CommandText = "DELETE FROM claims WHERE lane = $lane;";
        cmd.Parameters.AddWithValue("$lane", lane);
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }

    /// <summary>Returns all currently claimed keys (for dispatch deduplication).</summary>
    public static async Task<List<string>> GetClaimedKeysAsync(CancellationToken cancellationToken)
    {
        var claims = await GetClaimsAsync(cancellationToken);
        return claims.Values.Select(c => c.Key.ToUpperInvariant()).ToList();
    }

    // ---------------------------------------------------------------------------
    // Worklogs
    // ---------------------------------------------------------------------------

    /// <summary>Appends a worklog entry for a key.</summary>
    public static async Task AppendWorklogAsync(
        int? lane,
        string key,
        string action,
        string? note,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenAsync(cancellationToken);
        var cmd = connection.CreateCommand();
        cmd.CommandText = """
            INSERT INTO worklogs (session, lane, key, action, note)
            VALUES ($session, $lane, $key, $action, $note);
            """;
        cmd.Parameters.AddWithValue("$session", Environment.ProcessId.ToString());
        cmd.Parameters.AddWithValue("$lane", (object?)lane ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$key", key.ToUpperInvariant());
        cmd.Parameters.AddWithValue("$action", action);
        cmd.Parameters.AddWithValue("$note", (object?)note ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }
}

internal sealed record ClaimRow(int Lane, string Key, string ClaimedAt, int? Pid);
