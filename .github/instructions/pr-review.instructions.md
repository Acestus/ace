# Pull Request Review Instructions

## Overview

This document provides comprehensive guidelines for reviewing pull requests in the Fabric Pipeline Automation project. This project uses Azure Functions, PowerShell, GitHub Actions, and Infrastructure as Code (Bicep) to provide automated, secure, and scalable pipeline execution.

## 🔍 Review Checklist

### 1. Code Quality & Standards

#### PowerShell Code Review
- [ ] **Syntax Validation**: Ensure PowerShell syntax is correct and follows best practices
- [ ] **Error Handling**: Verify proper `try-catch-finally` blocks with meaningful error messages
- [ ] **Logging**: Check that appropriate `Write-Host` statements exist for troubleshooting
- [ ] **Variable Scope**: Ensure proper variable scoping (`$script:`, `$global:`, `$local:`)
- [ ] **Parameter Validation**: Verify function parameters have proper validation attributes
- [ ] **Code Comments**: Review inline comments for complex logic or business rules

```powershell
# Good Example
try {
    Write-Host "🔐 Getting access token using system managed identity..." -ForegroundColor Cyan
    $tokenResponse = Invoke-RestMethod -Uri $tokenUri -Method GET -Headers $headers -UseBasicParsing -TimeoutSec 30
    Write-Host "✅ Token acquired successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Token acquisition failed: $($_.Exception.Message)" -ForegroundColor Red
    throw "Authentication failed: $($_.Exception.Message)"
}
```

#### General Code Quality
- [ ] **No hardcoded secrets**: Verify no passwords, API keys, or sensitive data in code
- [ ] **Configuration externalized**: Check that environment-specific values use variables
- [ ] **Consistent naming**: Verify consistent naming conventions throughout
- [ ] **Code reusability**: Look for opportunities to reduce duplication

### 2. Security Review

#### Authentication & Authorization
- [ ] **Managed Identity Usage**: Verify proper use of Azure Managed Identity, no stored credentials
- [ ] **Token Handling**: Check that tokens are not logged or exposed in output
- [ ] **API Permissions**: Verify least-privilege access to Fabric APIs
- [ ] **OIDC Configuration**: Ensure proper OIDC federated credential usage in workflows

#### Secrets Management
- [ ] **No secrets in code**: Verify no hardcoded passwords, connection strings, or API keys
- [ ] **GitHub Secrets**: Check that sensitive values use GitHub repository secrets
- [ ] **Environment Variables**: Verify sensitive data accessed via environment variables only

```powershell
# ✅ Good - Using environment variables
$workspaceId = $env:FABRIC_WORKSPACE_ID

# ❌ Bad - Hardcoded sensitive data
$workspaceId = "<RESOURCE_GUID>"
```

### 3. Azure Functions Specific

#### Function Configuration
- [ ] **Timer Triggers**: Verify CRON expressions are correct and appropriate
- [ ] **Function Bindings**: Check `function.json` configurations are valid
- [ ] **Runtime Version**: Ensure PowerShell runtime version is specified correctly
- [ ] **Timeout Settings**: Verify appropriate timeout values for function execution

#### Performance & Reliability
- [ ] **Resource Usage**: Check for efficient resource utilization
- [ ] **Retry Logic**: Verify appropriate retry mechanisms for external API calls
- [ ] **Timeout Handling**: Ensure proper timeout configurations (30 seconds for token requests)
- [ ] **Memory Management**: Look for potential memory leaks or excessive resource usage

### 4. Infrastructure as Code (Bicep)

#### Template Quality
- [ ] **Parameter Validation**: Verify input parameters have proper constraints and descriptions
- [ ] **Resource Naming**: Check consistent and meaningful resource naming conventions
- [ ] **Tags**: Ensure proper resource tagging for cost management and organization
- [ ] **Dependencies**: Verify correct resource dependencies and deployment order

#### Security Configuration
- [ ] **Network Security**: Review NSG rules, subnet configurations, and network isolation
- [ ] **Identity Configuration**: Verify managed identity assignments and role-based access
- [ ] **Storage Security**: Check storage account access policies and encryption settings
- [ ] **Monitoring**: Ensure Application Insights and logging are properly configured

### 5. GitHub Actions Workflows

#### Workflow Security
- [ ] **OIDC Authentication**: Verify proper OIDC configuration, no long-lived secrets
- [ ] **Permissions**: Check that workflow permissions follow least-privilege principle
- [ ] **Environment Protection**: Ensure production environments have proper protection rules
- [ ] **Secrets Usage**: Verify secrets are accessed securely and not logged

#### Workflow Efficiency
- [ ] **Parallel Execution**: Check for opportunities to parallelize independent jobs
- [ ] **Caching**: Verify proper caching of dependencies and build artifacts
- [ ] **Conditional Execution**: Ensure workflows run only when necessary (path filters, conditions)
- [ ] **Resource Usage**: Review runner requirements and optimize for cost

```yaml
# Good Example - Proper permissions and conditions
permissions:
  id-token: write
  contents: read
  statuses: write
  pull-requests: write

jobs:
  validation:
    if: github.event_name == 'pull_request' && !github.event.pull_request.draft
```

### 6. Testing & Validation

#### Test Coverage
- [ ] **Unit Tests**: Verify appropriate PowerShell Pester tests exist
- [ ] **Integration Tests**: Check end-to-end validation scenarios
- [ ] **Health Checks**: Ensure comprehensive health check functionality
- [ ] **Error Scenarios**: Verify proper testing of failure conditions

#### Validation Scripts
- [ ] **Multiple Check Types**: Verify support for different validation scenarios
- [ ] **Clear Output**: Check that validation results are clear and actionable
- [ ] **Exit Codes**: Ensure proper exit code usage for CI/CD integration
- [ ] **Logging Quality**: Review log messages for troubleshooting value

### 7. Documentation

#### Code Documentation
- [ ] **README Updates**: Verify README reflects any functional changes
- [ ] **Inline Comments**: Check complex logic has explanatory comments
- [ ] **Change Documentation**: Ensure significant changes are documented
- [ ] **Architecture Diagrams**: Update diagrams if architecture changes

#### Operational Documentation
- [ ] **Troubleshooting Guides**: Check troubleshooting information is updated
- [ ] **Configuration Documentation**: Verify configuration changes are documented
- [ ] **Runbooks**: Ensure operational procedures are current

## 🚀 Best Practices

### Development Workflow
1. **Feature Branches**: Always create feature branches from `main`
2. **Small PRs**: Keep pull requests focused and reasonably sized
3. **Descriptive Commits**: Use clear, descriptive commit messages
4. **Self-Review**: Review your own PR before requesting reviews

### Code Quality
1. **Idempotent Operations**: Ensure scripts can be run multiple times safely
2. **Graceful Degradation**: Handle failures gracefully with appropriate fallbacks
3. **Comprehensive Logging**: Provide detailed logging for troubleshooting
4. **Configuration Management**: Externalize all environment-specific configuration

### Security First
1. **Zero Secrets**: Never commit secrets, passwords, or API keys
2. **Least Privilege**: Use minimal required permissions
3. **Audit Trail**: Ensure all operations are logged and traceable
4. **Regular Updates**: Keep dependencies and runtime versions current

### Performance Optimization
1. **Efficient API Calls**: Minimize external API calls and implement proper retry logic
2. **Resource Management**: Clean up resources and avoid memory leaks
3. **Parallel Processing**: Use parallel execution where appropriate
4. **Caching**: Implement appropriate caching strategies

## 🔧 Common Issues to Watch For

### PowerShell Specific
- **Variable Scoping**: Incorrect variable scope causing unexpected behavior
- **String Escaping**: Improper string escaping in regex or API calls
- **Error Handling**: Missing or inadequate error handling
- **Type Conversion**: Implicit type conversions causing unexpected results

### Azure Functions
- **Cold Start**: Functions not optimized for cold start scenarios
- **Timeout Issues**: Functions exceeding timeout limits
- **Dependency Loading**: Slow or failed module/dependency loading
- **Configuration Errors**: Incorrect `host.json` or `function.json` settings

### GitHub Actions
- **Permission Errors**: Insufficient workflow permissions
- **Secret Exposure**: Accidentally logging sensitive information
- **Resource Constraints**: Workflows running out of time or memory
- **Dependency Issues**: Missing or incorrect action versions

## 📝 Review Comments Template

### Approval Comments
```
✅ **LGTM** - Excellent implementation of [specific feature]
- Security: Proper managed identity usage
- Code quality: Clean, well-documented PowerShell
- Testing: Comprehensive validation coverage
- Documentation: Updated and accurate
```

### Request Changes Comments
```
🔄 **Changes Requested**

**Security Issues:**
- [ ] Remove hardcoded workspace ID on line 42
- [ ] Add proper error handling for token acquisition

**Code Quality:**
- [ ] Add validation for required parameters
- [ ] Improve error messages for better troubleshooting

**Testing:**
- [ ] Add test case for authentication failure scenario
```

### Suggestions
```
💡 **Suggestions for Improvement**
- Consider adding retry logic for transient Fabric API failures
- Opportunity to parallelize health checks for better performance
- Could benefit from additional logging for troubleshooting
```

## 🎯 Final Review Checklist

Before approving any PR, ensure:
- [ ] All automated checks are passing
- [ ] Security review is complete
- [ ] Code follows project standards
- [ ] Documentation is updated
- [ ] Tests provide adequate coverage
- [ ] No breaking changes without proper communication
- [ ] Performance impact is acceptable
- [ ] Error handling is comprehensive

## 🆘 When to Escalate

Escalate to senior developers or architects when:
- **Security concerns** that you're unsure about
- **Architecture changes** that affect multiple components
- **Performance issues** that may impact production
- **Breaking changes** that affect downstream consumers
- **Complex authentication** or authorization modifications

Remember: **It's better to ask questions than to let issues slip through!**