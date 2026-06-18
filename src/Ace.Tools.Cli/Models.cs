using System;
using System.Collections.Generic;

namespace Ace.Tools.Cli;

/// <summary>
/// Represents a Linear ticket, synced from Linear API and stored locally.
/// </summary>
public class Ticket
{
    public string Id { get; set; } = null!;                    // ENG-123
    public string Title { get; set; } = null!;
    public string? Description { get; set; }
    public string Status { get; set; } = null!;                // pending, in_progress, blocked, waiting_review, done
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    public string LinearId { get; set; } = null!;              // Internal Linear UUID
    public string? LinearUrl { get; set; }
    public string? Assignee { get; set; }
    public int? EstimatePoints { get; set; }
    public string? Swimlane { get; set; }                       // flow:todo, flow:in_progress, etc.
    public string? Priority { get; set; }                       // P0, P1, P2, P3
    public List<string>? Tags { get; set; }
    public List<string>? DependsOn { get; set; }
    public DateTime LastSyncedAt { get; set; }
}

/// <summary>
/// Represents a work log entry for time tracking.
/// </summary>
public class WorkLog
{
    public string Id { get; set; } = null!;
    public string TicketId { get; set; } = null!;
    public string Date { get; set; } = null!;                  // YYYY-MM-DD
    public int? DurationMinutes { get; set; }
    public string? Notes { get; set; }
    public DateTime CreatedAt { get; set; }
    public bool SyncedToLinear { get; set; }
}

/// <summary>
/// Represents a comment pending publication to Linear.
/// </summary>
public class CommentPending
{
    public string Id { get; set; } = null!;
    public string TargetType { get; set; } = null!;            // linear_ticket, notion_page
    public string TargetId { get; set; } = null!;
    public string Content { get; set; } = null!;
    public string? Author { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? PostedAt { get; set; }
    public string Status { get; set; } = "pending";            // pending, posted, failed
    public string? ErrorMessage { get; set; }
}

/// <summary>
/// Represents a Notion page pending publication.
/// </summary>
public class PagePending
{
    public string Id { get; set; } = null!;
    public string? ParentPageId { get; set; }
    public string Title { get; set; } = null!;
    public string Content { get; set; } = null!;
    public string? PageType { get; set; }                       // standup, crm, job_search, weekly, etc.
    public DateTime CreatedAt { get; set; }
    public DateTime? PublishedAt { get; set; }
    public string Status { get; set; } = "pending";            // pending, published, failed
    public string? ErrorMessage { get; set; }
    public string? NotionPageId { get; set; }
}

/// <summary>
/// Represents a GitHub Pull Request.
/// </summary>
public class PullRequest
{
    public string Id { get; set; } = null!;                    // owner/repo#number
    public string Repo { get; set; } = null!;
    public int Number { get; set; }
    public string Title { get; set; } = null!;
    public string Url { get; set; } = null!;
    public string State { get; set; } = null!;                 // open, closed, merged
    public string? Author { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public DateTime? MergedAt { get; set; }
    public string? ReviewStatus { get; set; }                  // draft, pending_review, approved, changes_requested
    public string? RelatedTicket { get; set; }
    public string? BranchName { get; set; }
    public DateTime LastSyncedAt { get; set; }
}

/// <summary>
/// Represents a GitHub Issue.
/// </summary>
public class GitHubIssue
{
    public string Id { get; set; } = null!;                    // owner/repo#number
    public string Repo { get; set; } = null!;
    public int Number { get; set; }
    public string Title { get; set; } = null!;
    public string Url { get; set; } = null!;
    public string State { get; set; } = null!;                 // open, closed
    public string? Assignee { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public List<string>? Labels { get; set; }
    public string? RelatedTicket { get; set; }
    public DateTime LastSyncedAt { get; set; }
}

/// <summary>
/// Represents a CRM contact.
/// </summary>
public class CrmContact
{
    public string Id { get; set; } = null!;
    public string? FirstName { get; set; }
    public string? LastName { get; set; }
    public string? Email { get; set; }
    public string? Phone { get; set; }
    public string? CompanyId { get; set; }
    public string? Title { get; set; }
    public string? Notes { get; set; }
    public DateTime? LastContacted { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    public bool SyncedToNotion { get; set; }
}

/// <summary>
/// Represents a job search application.
/// </summary>
public class JobSearchApplication
{
    public string Id { get; set; } = null!;
    public string Company { get; set; } = null!;
    public string PositionTitle { get; set; } = null!;
    public string? Url { get; set; }
    public string Status { get; set; } = null!;                // applied, interviewing, offer, rejected, withdrawn
    public DateTime DateApplied { get; set; }
    public DateTime DateUpdated { get; set; }
    public string? Notes { get; set; }
    public string? SalaryRange { get; set; }
    public string? RecruiterContact { get; set; }
    public DateTime? FollowUpDate { get; set; }
    public bool SyncedToNotion { get; set; }
}

/// <summary>
/// Represents the state of a kanban lane in rounds.
/// </summary>
public class RoundsState
{
    public string Id { get; set; } = null!;
    public int LaneNumber { get; set; }                         // 1-5
    public string? CurrentTicketId { get; set; }
    public string Status { get; set; } = "idle";               // idle, active, waiting, blocked
    public DateTime? StartedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}

/// <summary>
/// Tracks sync state for external sources.
/// </summary>
public class SyncState
{
    public string Source { get; set; } = null!;                // linear, notion, github
    public DateTime? LastSyncAt { get; set; }
    public DateTime? NextSyncAt { get; set; }
    public string Status { get; set; } = "idle";               // idle, syncing, success, error
    public string? ErrorMessage { get; set; }
    public int SyncedCount { get; set; }
}
