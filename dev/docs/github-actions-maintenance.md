# GitHub Actions Maintenance

## Overview
This document outlines the process for keeping GitHub Actions workflows current and functional.

## Actions Inventory
Current actions used in `.github/workflows/`:

| Action | Version | Last Updated | Notes |
|--------|---------|-------------|-------|
| actions/checkout | v4 | 2026-02-24 | Latest stable |
| astral-sh/setup-uv | v4 | 2026-02-24 | Latest stable |
| actions/upload-artifact | v4 | 2026-02-24 | Updated from deprecated v3 |

## Maintenance Schedule
- **Quarterly Review**: Check for new versions and security updates
- **Immediate Action**: Update deprecated actions within 7 days of deprecation notice
- **Annual Audit**: Full workflow review and optimization

## Deprecation Monitoring
1. Subscribe to GitHub Actions changelog: https://github.blog/changelog
2. Monitor GitHub Actions marketplace for version updates
3. Use Dependabot for GitHub Actions (if available)

## Update Process
1. Check current versions against latest releases
2. Review changelog for breaking changes
3. Test workflows in feature branch
4. Update and merge after successful testing

## Emergency Response
If a workflow fails due to deprecated actions:
1. Identify the deprecated action from error messages
2. Check the action's repository for migration guide
3. Update to the recommended version
4. Test and deploy immediately

## Contact
For questions about GitHub Actions maintenance, refer to this document or check the official GitHub Actions documentation.