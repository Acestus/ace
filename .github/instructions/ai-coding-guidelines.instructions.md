# AI Coding Guidelines and Principles

## Overview

This document establishes the core coding principles and guidelines that AI assistants must follow when generating, modifying, or reviewing code in this project. These principles prioritize maintainability, readability, and long-term sustainability over short-term clever solutions.

## 🎯 Core Principles

### 1. Simplicity Over Complexity

- **We prefer simple, clean, maintainable solutions over clever or complex ones**
- Choose straightforward approaches that any developer can understand
- Avoid over-engineering or premature optimization
- If there are two ways to solve a problem, choose the simpler one

```powershell
# ✅ Good - Simple and clear
function Get-PipelineConfig {
    param([string]$ConfigName)
    
    $config = Get-ConfigFromYaml -Name $ConfigName
    if (-not $config) {
        throw "Configuration '$ConfigName' not found"
    }
    return $config
}

# ❌ Bad - Overly complex for the task
function Get-PipelineConfig {
    param([string]$ConfigName)
    
    $memoizedConfigs = @{}
    if ($memoizedConfigs.ContainsKey($ConfigName)) {
        return [PSCustomObject]@{
            Config = $memoizedConfigs[$ConfigName]
            FromCache = $true
            Timestamp = Get-Date
        }
    }
    # ... unnecessary complexity continues
}
```

### 2. Readability and Maintainability First

- **Readability and maintainability are primary concerns**
- Code should read like well-written prose
- Optimize for the developer who will maintain this code in 6 months
- Clear intent is more valuable than clever shortcuts

### 3. Self-Documenting Code

- **Self-documenting names and code**
- Function and variable names should clearly express their purpose
- Avoid abbreviations and cryptic names
- Code structure should tell the story without extensive comments

```powershell
# ✅ Good - Self-documenting
function Send-PipelineTriggerRequest {
    $apiEndpoint = Build-FabricApiUrl -WorkspaceId $WorkspaceId -PipelineId $PipelineId
    $authHeaders = Get-AuthenticationHeaders -AccessToken $AccessToken
    $requestBody = Build-TriggerRequestBody -PipelineName $PipelineName
    
    return Invoke-RestMethod -Uri $apiEndpoint -Headers $authHeaders -Body $requestBody -Method Post
}

# ❌ Bad - Cryptic and unclear
function Send-Req {
    $url = Get-Url $wId $pId
    $hdr = Get-Hdr $tkn
    $bdy = Get-Bdy $nm
    
    return Invoke-RestMethod -Uri $url -Headers $hdr -Body $bdy -Method Post
}
```

### 4. Small Functions
- **Small functions**
- Each function should do one thing well
- Aim for functions that fit on a single screen (15-25 lines max)
- Break down large functions into smaller, focused helpers
- Small functions are easier to test, debug, and reuse

### 5. Single Responsibility Principle
- **Follow single responsibility principle in classes and functions**
- Each function should have exactly one reason to change
- Separate concerns into different functions
- If you use "and" to describe what a function does, it probably does too much

```powershell
# ✅ Good - Each function has single responsibility
function Get-AccessToken {
    return Get-TokenFromManagedIdentity
}

function Send-PipelineRequest {
    param($AccessToken, $PipelineData)
    # Only handles sending the request
}

function Log-PipelineResult {
    param($Result)
    # Only handles logging
}

# ❌ Bad - Multiple responsibilities
function ProcessPipelineAndLogResults {
    # Gets token, sends request, logs results, handles errors, updates database
    # Too many responsibilities
}
```

## 📋 Implementation Guidelines

### Function Design
- **Maximum function length**: 25 lines of code
- **Maximum parameters**: 4 parameters (consider objects for more)
- **Single exit point**: Prefer one return statement when possible
- **Clear parameter validation**: Use parameter attributes in PowerShell

### 🚨 File-Specific Exceptions

#### GitHub Pages Dashboard (`docs/index.html`)

The GitHub Pages dashboard file is **exempt** from the clean code guidelines for the following reasons:
- **Critical stability**: This is a public-facing dashboard that must remain functional
- **Legacy compatibility**: Contains embedded inline JavaScript that works reliably
- **Complex integration**: Mixing HTML, CSS, and JavaScript in a single file for GitHub Pages deployment
- **Performance considerations**: Inline code reduces HTTP requests for the dashboard

**Exception Rules for `docs/index.html`:**

- ✅ Keep existing working code structure intact
- ✅ Allow longer functions if they work reliably
- ✅ Allow mixed concerns (HTML/CSS/JS) for deployment simplicity
- ✅ Prioritize functionality over code organization
- ❌ Do not refactor unless absolutely necessary and thoroughly tested
- ❌ Do not apply single responsibility principle if it breaks functionality

When modifying this file, prioritize working code over clean code principles.

### Naming Conventions

- **Functions**: Use verb-noun format (`Get-PipelineConfig`, `Send-TriggerRequest`)
- **Variables**: Use descriptive names (`$pipelineConfiguration` not `$config`)
- **Constants**: Use ALL_CAPS with underscores (`$MAX_RETRY_ATTEMPTS`)
- **Boolean variables**: Use is/has/can prefix (`$isAuthenticated`, `$hasPermission`)

### Error Handling

- **Fail fast**: Validate inputs early and provide clear error messages
- **Meaningful exceptions**: Include context in error messages
- **Clean error paths**: Don't let errors leave the system in an inconsistent state

```powershell
# ✅ Good - Clear error handling
function Invoke-PipelineTrigger {
    param(
        [Parameter(Mandatory=$true)]
        [string]$WorkspaceId,
        [Parameter(Mandatory=$true)]
        [string]$PipelineId
    )
    
    if ([string]::IsNullOrEmpty($WorkspaceId)) {
        throw "WorkspaceId cannot be null or empty"
    }
    
    try {
        $accessToken = Get-AccessToken
        return Send-PipelineRequest -AccessToken $accessToken -WorkspaceId $WorkspaceId -PipelineId $PipelineId
    } catch {
        Write-Error "Failed to trigger pipeline '$PipelineId' in workspace '$WorkspaceId': $($_.Exception.Message)"
        throw
    }
}
```

### Code Organization

- **Logical grouping**: Group related functions together
- **Clear separation**: Use comments to separate logical sections
- **Consistent formatting**: Follow established formatting patterns
- **Remove dead code**: Don't leave commented-out code

## 🚫 Anti-Patterns to Avoid

### Complexity Anti-Patterns

- **God functions**: Functions that do everything
- **Deep nesting**: More than 3 levels of nesting
- **Long parameter lists**: More than 4 parameters
- **Magic numbers**: Unexplained numeric constants

### Naming Anti-Patterns
- **Abbreviations**: `usr`, `cfg`, `mgr`, `proc`
- **Generic names**: `data`, `info`, `item`, `thing`
- **Misleading names**: Names that don't match the function's behavior
- **Inconsistent naming**: Mixed naming conventions within the same file

### Structure Anti-Patterns
- **Mixed concerns**: Functions that handle multiple unrelated tasks
- **Tight coupling**: Functions that know too much about other functions
- **Global state**: Over-reliance on global variables
- **Copy-paste code**: Duplicated logic instead of shared functions

## 📚 Language-Specific Guidelines

### PowerShell
- Use approved verbs for function names
- Leverage parameter validation attributes
- Use proper error handling with try-catch-finally
- Follow PowerShell formatting conventions

### JavaScript
- Use const/let appropriately, avoid var
- Prefer arrow functions for simple operations
- Use meaningful function and variable names
- Keep functions pure when possible

### YAML/JSON
- Consistent indentation (2 spaces)
- Meaningful keys and structure
- Avoid deep nesting where possible
- Use comments to explain complex configurations

## ✅ Review Checklist

When reviewing AI-generated code, ensure:

- [ ] Functions are small and focused (< 25 lines)
- [ ] Names clearly express intent without abbreviations
- [ ] Each function has a single, clear responsibility
- [ ] Code is simple and avoids unnecessary complexity
- [ ] Error handling is clear and meaningful
- [ ] No dead code or commented-out sections
- [ ] Consistent formatting and style
- [ ] Proper parameter validation
- [ ] Logical code organization and structure

## 🎯 Success Metrics

Code following these principles should be:
- **Easily testable**: Small functions with clear inputs/outputs
- **Quickly debuggable**: Issues can be isolated to specific functions
- **Simply maintainable**: Changes require minimal code modification
- **Clearly understandable**: New team members can grasp the code quickly
- **Safely refactorable**: Code can be changed without breaking other parts

---

*These guidelines ensure that AI-generated code contributes to a maintainable, professional codebase that the team can confidently build upon.*