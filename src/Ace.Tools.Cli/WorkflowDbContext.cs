using System;
using System.Data.SQLite;
using System.IO;
using System.Threading.Tasks;
using Dapper;

namespace Ace.Tools.Cli;

/// <summary>
/// Manages SQLite database for local-first workflow.
/// All work during the day comes from this database.
/// Synced at start-my-day and end-my-day with Linear/Notion/GitHub.
/// </summary>
public class WorkflowDbContext : IDisposable
{
    private readonly string _dbPath;
    private SQLiteConnection? _connection;

    public WorkflowDbContext(string? dbPath = null)
    {
        _dbPath = dbPath ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".acestus",
            "workflow.db"
        );
        
        EnsureDirectoryExists();
    }

    public SQLiteConnection GetConnection()
    {
        if (_connection == null)
        {
            var connectionString = $"Data Source={_dbPath};Version=3;";
            _connection = new SQLiteConnection(connectionString);
            _connection.Open();
        }
        return _connection;
    }

    public async Task InitializeAsync()
    {
        var connection = GetConnection();
        var schemaPath = Path.Combine(
            AppContext.BaseDirectory,
            "schema.sql"
        );

        if (!File.Exists(schemaPath))
        {
            throw new FileNotFoundException($"Schema file not found: {schemaPath}");
        }

        var schema = await File.ReadAllTextAsync(schemaPath);
        
        // Split by semicolon and execute each statement
        var statements = schema.Split(new[] { ";" }, StringSplitOptions.RemoveEmptyEntries);
        foreach (var statement in statements)
        {
            if (!string.IsNullOrWhiteSpace(statement))
            {
                await connection.ExecuteAsync(statement.Trim());
            }
        }
    }

    public async Task<IEnumerable<Ticket>> GetPendingTicketsAsync()
    {
        var connection = GetConnection();
        return await connection.QueryAsync<Ticket>(
            @"SELECT * FROM tickets 
              WHERE status != 'done' 
              ORDER BY priority DESC, updated_at DESC"
        );
    }

    public async Task<IEnumerable<Ticket>> GetTicketsByStatusAsync(string status)
    {
        var connection = GetConnection();
        return await connection.QueryAsync<Ticket>(
            @"SELECT * FROM tickets 
              WHERE status = @Status 
              ORDER BY updated_at DESC",
            new { Status = status }
        );
    }

    public async Task<Ticket?> GetTicketAsync(string ticketId)
    {
        var connection = GetConnection();
        return await connection.QueryFirstOrDefaultAsync<Ticket>(
            @"SELECT * FROM tickets WHERE id = @Id",
            new { Id = ticketId }
        );
    }

    public async Task<int> UpsertTicketAsync(Ticket ticket)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO tickets 
              (id, title, description, status, created_at, updated_at, linear_id, linear_url, 
               assignee, estimate_points, swimlane, priority, tags, depends_on, last_synced_at)
              VALUES (@Id, @Title, @Description, @Status, @CreatedAt, @UpdatedAt, @LinearId, 
                      @LinearUrl, @Assignee, @EstimatePoints, @Swimlane, @Priority, @Tags, 
                      @DependsOn, @LastSyncedAt)",
            new
            {
                ticket.Id,
                ticket.Title,
                ticket.Description,
                ticket.Status,
                ticket.CreatedAt,
                ticket.UpdatedAt,
                ticket.LinearId,
                ticket.LinearUrl,
                ticket.Assignee,
                ticket.EstimatePoints,
                ticket.Swimlane,
                ticket.Priority,
                Tags = ticket.Tags == null ? null : string.Join(",", ticket.Tags),
                DependsOn = ticket.DependsOn == null ? null : string.Join(",", ticket.DependsOn),
                ticket.LastSyncedAt
            }
        );
    }

    public async Task<IEnumerable<WorkLog>> GetWorkLogsForDateAsync(string date)
    {
        var connection = GetConnection();
        return await connection.QueryAsync<WorkLog>(
            @"SELECT * FROM work_logs WHERE date = @Date ORDER BY created_at DESC",
            new { Date = date }
        );
    }

    public async Task<int> InsertWorkLogAsync(WorkLog workLog)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT INTO work_logs 
              (id, ticket_id, date, duration_minutes, notes, created_at, synced_to_linear)
              VALUES (@Id, @TicketId, @Date, @DurationMinutes, @Notes, @CreatedAt, @SyncedToLinear)",
            workLog
        );
    }

    public async Task<IEnumerable<CommentPending>> GetPendingCommentsAsync()
    {
        var connection = GetConnection();
        return await connection.QueryAsync<CommentPending>(
            @"SELECT * FROM comments_pending 
              WHERE status = 'pending' 
              ORDER BY created_at ASC"
        );
    }

    public async Task<int> InsertCommentPendingAsync(CommentPending comment)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT INTO comments_pending 
              (id, target_type, target_id, content, author, created_at, status)
              VALUES (@Id, @TargetType, @TargetId, @Content, @Author, @CreatedAt, @Status)",
            comment
        );
    }

    public async Task<int> UpdateCommentStatusAsync(string commentId, string status, string? errorMessage = null)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"UPDATE comments_pending 
              SET status = @Status, posted_at = CURRENT_TIMESTAMP, error_message = @ErrorMessage 
              WHERE id = @Id",
            new { Status = status, ErrorMessage = errorMessage, Id = commentId }
        );
    }

    public async Task<IEnumerable<PagePending>> GetPendingPagesAsync()
    {
        var connection = GetConnection();
        return await connection.QueryAsync<PagePending>(
            @"SELECT * FROM pages_pending 
              WHERE status = 'pending' 
              ORDER BY created_at ASC"
        );
    }

    public async Task<int> InsertPagePendingAsync(PagePending page)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT INTO pages_pending 
              (id, parent_page_id, title, content, page_type, created_at, status)
              VALUES (@Id, @ParentPageId, @Title, @Content, @PageType, @CreatedAt, @Status)",
            page
        );
    }

    public async Task<int> UpdatePageStatusAsync(string pageId, string status, string? notionPageId = null, string? errorMessage = null)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"UPDATE pages_pending 
              SET status = @Status, published_at = CURRENT_TIMESTAMP, notion_page_id = @NotionPageId, error_message = @ErrorMessage 
              WHERE id = @Id",
            new { Status = status, NotionPageId = notionPageId, ErrorMessage = errorMessage, Id = pageId }
        );
    }

    public async Task<IEnumerable<CrmContact>> GetCrmContactsAsync()
    {
        var connection = GetConnection();
        return await connection.QueryAsync<CrmContact>(
            @"SELECT * FROM crm_contacts ORDER BY last_contacted DESC NULLS LAST"
        );
    }

    public async Task<int> UpsertCrmContactAsync(CrmContact contact)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO crm_contacts 
              (id, first_name, last_name, email, phone, company_id, title, notes, last_contacted, created_at, updated_at, synced_to_notion)
              VALUES (@Id, @FirstName, @LastName, @Email, @Phone, @CompanyId, @Title, @Notes, @LastContacted, @CreatedAt, @UpdatedAt, @SyncedToNotion)",
            contact
        );
    }

    public async Task<IEnumerable<JobSearchApplication>> GetJobSearchApplicationsAsync(string? status = null)
    {
        var connection = GetConnection();
        return await connection.QueryAsync<JobSearchApplication>(
            status == null
                ? @"SELECT * FROM job_search_applications ORDER BY date_applied DESC"
                : @"SELECT * FROM job_search_applications WHERE status = @Status ORDER BY date_applied DESC",
            status == null ? null : new { Status = status }
        );
    }

    public async Task<int> UpsertJobSearchApplicationAsync(JobSearchApplication app)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO job_search_applications 
              (id, company, position_title, url, status, date_applied, date_updated, notes, salary_range, recruiter_contact, follow_up_date, synced_to_notion)
              VALUES (@Id, @Company, @PositionTitle, @Url, @Status, @DateApplied, @DateUpdated, @Notes, @SalaryRange, @RecruiterContact, @FollowUpDate, @SyncedToNotion)",
            app
        );
    }

    public async Task<RoundsState?> GetRoundsStateAsync(int laneNumber)
    {
        var connection = GetConnection();
        return await connection.QueryFirstOrDefaultAsync<RoundsState>(
            @"SELECT * FROM rounds_state WHERE lane_number = @LaneNumber",
            new { LaneNumber = laneNumber }
        );
    }

    public async Task<int> UpsertRoundsStateAsync(RoundsState state)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO rounds_state 
              (id, lane_number, current_ticket_id, status, started_at, updated_at)
              VALUES (@Id, @LaneNumber, @CurrentTicketId, @Status, @StartedAt, @UpdatedAt)",
            state
        );
    }

    public async Task<SyncState?> GetSyncStateAsync(string source)
    {
        var connection = GetConnection();
        return await connection.QueryFirstOrDefaultAsync<SyncState>(
            @"SELECT * FROM sync_state WHERE source = @Source",
            new { Source = source }
        );
    }

    public async Task<int> UpdateSyncStateAsync(SyncState state)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO sync_state 
              (source, last_sync_at, next_sync_at, status, error_message, synced_count)
              VALUES (@Source, @LastSyncAt, @NextSyncAt, @Status, @ErrorMessage, @SyncedCount)",
            state
        );
    }

    public async Task<int> UpsertPullRequestAsync(PullRequest pr)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO pull_requests 
              (id, repo, number, title, url, state, author, created_at, updated_at, merged_at, review_status, related_ticket, branch_name, last_synced_at)
              VALUES (@Id, @Repo, @Number, @Title, @Url, @State, @Author, @CreatedAt, @UpdatedAt, @MergedAt, @ReviewStatus, @RelatedTicket, @BranchName, @LastSyncedAt)",
            pr
        );
    }

    public async Task<int> UpsertGitHubIssueAsync(GitHubIssue issue)
    {
        var connection = GetConnection();
        return await connection.ExecuteAsync(
            @"INSERT OR REPLACE INTO github_issues 
              (id, repo, number, title, url, state, assignee, created_at, updated_at, labels, related_ticket, last_synced_at)
              VALUES (@Id, @Repo, @Number, @Title, @Url, @State, @Assignee, @CreatedAt, @UpdatedAt, @Labels, @RelatedTicket, @LastSyncedAt)",
            new
            {
                issue.Id,
                issue.Repo,
                issue.Number,
                issue.Title,
                issue.Url,
                issue.State,
                issue.Assignee,
                issue.CreatedAt,
                issue.UpdatedAt,
                Labels = issue.Labels == null ? null : string.Join(",", issue.Labels),
                issue.RelatedTicket,
                issue.LastSyncedAt
            }
        );
    }

    private void EnsureDirectoryExists()
    {
        var dir = Path.GetDirectoryName(_dbPath);
        if (!Directory.Exists(dir))
        {
            Directory.CreateDirectory(dir);
        }
    }

    public void Dispose()
    {
        _connection?.Dispose();
    }
}
