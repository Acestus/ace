# GitHub Workflows File Convention Instructions

## File Extension Requirements

**CRITICAL**: All GitHub Actions workflow files MUST use the `.yaml` extension, NOT `.yml`.

### ✅ Correct Examples

- `.github/workflows/ci.yaml`
- `.github/workflows/pipeline-health-monitor.yaml`
- `.github/workflows/comprehensive-ci.yaml`
- `.github/workflows/powershell-tests.yaml`

### ❌ Incorrect Examples

- `.github/workflows/ci.yml`
- `.github/workflows/pipeline-health-monitor.yml`
- `.github/workflows/comprehensive-ci.yml`

## Implementation Rules

1. **New Workflows**: Always create new workflow files with `.yaml` extension
2. **Existing Workflows**: When modifying existing `.yml` files, rename them to `.yaml`
3. **References**: Update any documentation or references to use `.yaml` extension
4. **Consistency**: Maintain this convention across all workflow files in the repository

## Rationale

- **Consistency**: Standardizes on the full YAML extension format
- **Clarity**: `.yaml` is more explicit and readable than the abbreviated `.yml`
- **Best Practice**: Aligns with modern YAML file naming conventions
- **Maintainability**: Reduces confusion about file extensions in the codebase

## AI Assistant Instructions

When creating or modifying GitHub Actions workflows:

- Always use `.yaml` file extension
- Never use `.yml` extension for new files
- Suggest renaming existing `.yml` files to `.yaml` when appropriate
- Update any references in documentation to reflect `.yaml` extension

---

This instruction applies to all GitHub Actions workflow files in the `.github/workflows/` directory.
