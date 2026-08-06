# Practical Cloud Content

Use this skill when the user wants to capture, score, draft, or distribute Practical Cloud Systems content.

## Principle

This skill is a thin collar. Do not keep business state in the skill. Call the .NET CLI and let the file-backed content workspace remain the source of truth.

## Commands

From the repo root:

```bash
dotnet run --project src/Ace.Tools.Cli -- content health
dotnet run --project src/Ace.Tools.Cli -- content init
dotnet run --project src/Ace.Tools.Cli -- content idea add --title "<title>" --pillar "<pillar>" --viewer "<viewer>"
dotnet run --project src/Ace.Tools.Cli -- content icahn score --id <pcs-001> --views <n> --subs <n> --demand <0-10> --pain <0-10> --content-signal <0-10> --packaging-upside <0-10> --monetization <0-10> --repurposing <0-10>
dotnet run --project src/Ace.Tools.Cli -- content draft --id <pcs-001>
dotnet run --project src/Ace.Tools.Cli -- content distribute --id <pcs-001> --channel <youtube|substack|x|mastodon|linkedin|instagram>
```

## Icahn Method Adaptation

Look for videos where the idea is carrying performance:

- low subscriber count
- high view count
- high views-per-subscriber ratio
- mediocre audio/video/presentation
- weak title or thumbnail
- obvious viewer pain or curiosity

Then create a clearer Practical Cloud Systems version with better packaging, stronger structure, and a CTA into the newsletter or consulting funnel.

## Safety

Posting externally is not automatic. The CLI records distribution intent first. Any command that actually posts to X, Mastodon, LinkedIn, YouTube, Substack, or email must require explicit configuration and should support dry-run output.
