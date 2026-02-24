# GitHub Actions Maintenance

## Overview
This document outlines the process for keeping GitHub Actions workflows current and functional using modern uv project management.

## Actions Inventory
Current actions used in `.github/workflows/`:

| Action | Version | Last Updated | Notes |
|--------|---------|-------------|-------|
| actions/checkout | v4 | 2026-02-24 | Latest stable |
| astral-sh/setup-uv | v7 | 2026-02-24 | Latest stable with caching |
| actions/upload-artifact | v4 | 2026-02-24 | Updated from deprecated v3 |

## Modern uv Integration
Our workflow now uses proper uv project management:

### Key Features:
- **Dependency Lockfile**: Uses `uv.lock` for reproducible builds
- **Project Sync**: Uses `uv sync --locked --all-extras --dev` instead of manual pip installs
- **Caching**: Enabled with `cache-dependency-glob` for `pyproject.toml` and `uv.lock`
- **Unified Commands**: Uses `uv run make test` for consistent environment

### Best Practices:
- Always use `--locked` flag in CI to ensure reproducible builds
- Enable caching for dependency files to improve build times
- Use `uv run` for all command executions to ensure proper environment

## Maintenance Schedule
- **Quarterly Review**: Check for new versions and security updates
- **Immediate Action**: Update deprecated actions within 7 days of deprecation notice
- **Annual Audit**: Full workflow review and optimization
- **Lock File Updates**: Review and update `uv.lock` monthly or when dependencies change

## Deprecation Monitoring
1. Subscribe to GitHub Actions changelog: https://github.blog/changelog
2. Monitor GitHub Actions marketplace for version updates
3. Watch astral-sh/setup-uv releases for new features
4. Use Dependabot for GitHub Actions (if available)

## Update Process
1. Check current versions against latest releases
2. Review changelog for breaking changes
3. Test workflows in feature branch
4. Update lockfile: `uv lock --upgrade`
5. Test locally: `uv run make test`
6. Update and merge after successful testing

## Emergency Response
If a workflow fails due to deprecated actions:
1. Identify the deprecated action from error messages
2. Check the action's repository for migration guide
3. Update to the recommended version
4. Regenerate lockfile if needed: `uv sync`
5. Test and deploy immediately

## Modern uv Commands Reference
```bash
# Local development
uv sync --all-extras --dev     # Install all dependencies
uv run make test               # Run tests in project environment
uv lock --upgrade              # Update lockfile

# CI/CD (in workflow)
uv sync --locked --all-extras --dev  # Reproducible install
uv run make test                      # Run tests
```

## Contact
For questions about GitHub Actions maintenance, refer to this document or check the official GitHub Actions documentation.