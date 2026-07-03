using System.Linq;

namespace Ace.Tools.Cli;

/// <summary>
/// Single source of truth for how tickets are ranked for dispatch: Linear's own
/// priority field first (Urgent &gt; High &gt; Medium &gt; Low &gt; No Priority), then issue
/// number as a stable tie-break. Both the live `linear dispatch-next` command and the
/// local SQLite `workflow dispatch` command call into this so the two never diverge.
/// Replaces the old urgency/importance (Eisenhower) label scheme, which was never
/// actually read by either dispatcher.
/// </summary>
internal static class LinearRanking
{
    /// <summary>
    /// Maps Linear's raw priority (0 = No priority, 1 = Urgent, 2 = High, 3 = Medium,
    /// 4 = Low) to a rank where lower sorts first. No-priority issues rank last.
    /// </summary>
    public static int PriorityRank(int linearPriority) => linearPriority switch
    {
        1 => 1,
        2 => 2,
        3 => 3,
        4 => 4,
        _ => 5,
    };

    /// <summary>
    /// Extracts the numeric suffix of a Linear identifier (e.g. "ACE-8" -&gt; 8) for use
    /// as a tie-break so ranking is deterministic when priority is equal.
    /// </summary>
    public static int ParseIssueNumber(string identifier)
    {
        var suffix = identifier.Split('-', 2).LastOrDefault() ?? string.Empty;
        return int.TryParse(suffix, out var parsed) ? parsed : int.MaxValue;
    }
}
