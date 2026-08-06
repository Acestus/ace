# Practical Cloud Systems Content Growth Engine

This directory is the text-file source of truth for Practical Cloud Systems content operations.

## Purpose

Build distribution and authority around Practical Cloud Systems:

- YouTube videos and Shorts
- Hugo/static-site articles
- newsletter/Substack drafts
- engagement emails
- LinkedIn/X/Mastodon/Instagram variants
- distribution records
- future consulting/course/book funnel assets

## Source of Truth

The CLI writes durable state here instead of hiding it in a SaaS database.

```text
content-growth/
  backlog/        # pcs-001.json idea records and Icahn scores
  articles/       # canonical article drafts for Hugo/static site
  drafts/
    youtube/      # long-form video scripts
    shorts/       # short video scripts
    social/       # LinkedIn/X/Mastodon/Instagram copy
    newsletter/   # Substack/newsletter drafts
  distribution/   # records of planned/published distribution
  sources/        # Confluence exports, transcripts, research notes
  templates/      # editable draft templates
```

## CLI

```bash
dotnet run --project src/Ace.Tools.Cli -- content init
dotnet run --project src/Ace.Tools.Cli -- content health
dotnet run --project src/Ace.Tools.Cli -- content idea add --title "What does a cloud engineer actually do?" --pillar "Cloud Careers" --viewer "cloud beginner"
dotnet run --project src/Ace.Tools.Cli -- content icahn score --id pcs-001 --views 100000 --subs 1000 --demand 9 --pain 8 --content-signal 10 --packaging-upside 8 --monetization 7 --repurposing 9
dotnet run --project src/Ace.Tools.Cli -- content draft --id pcs-001
dotnet run --project src/Ace.Tools.Cli -- content distribute --id pcs-001 --channel linkedin --source-url "https://youtube.com/..."
```

## Icahn Method

Use Shane Hummus-style idea validation: find videos where the content idea appears to be carrying performance.

Strong signal:

```text
low subscriber channel
+ unusually high view count
+ mediocre production or packaging
+ clear audience pain/curiosity
= validated idea worth adapting
```

The Practical Cloud Systems spin should be simpler and broader at the top of funnel, then point interested viewers toward deeper Azure/Fabric/platform-engineering authority pieces.
