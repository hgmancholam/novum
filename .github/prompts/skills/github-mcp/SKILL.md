# GitHub MCP Integration Skill

## Description
Connects to GitHub via Model Context Protocol (MCP) for issues, pull requests, and documentation synchronization.

## When to Use
- Creating GitHub issues from user stories
- Creating pull requests
- Pushing documentation to repository
- Commenting on issues and PRs
- Managing labels and milestones

## Capabilities

### Issue Management
```yaml
create_issue:
  - title: string
  - body: markdown
  - labels: string[]
  - milestone: string
  - assignees: string[]

update_issue:
  - issue_number: int
  - body: markdown
  - state: open | closed

comment_on_issue:
  - issue_number: int
  - body: markdown
```

### Pull Request Management
```yaml
create_pr:
  - title: string
  - body: markdown
  - base: string (branch)
  - head: string (branch)
  - labels: string[]

review_pr:
  - pr_number: int
  - event: APPROVE | REQUEST_CHANGES | COMMENT
  - body: markdown
```

### Documentation Sync
```yaml
push_file:
  - path: string
  - content: string
  - message: string
  - branch: string
```

## MCP Configuration

When GitHub MCP is available, use these tools:
- `github_create_issue`
- `github_update_issue`
- `github_create_pull_request`
- `github_push_file`

## Usage Examples

### Creating Issue from User Story
```typescript
// When BSA Agent creates a user story, also create GitHub issue
const issue = await github_create_issue({
  title: "US-001: Create user session",
  body: `## User Story
As a user, I want to create a session so that I can track my queries.

## Acceptance Criteria
- [ ] Session created with unique ID
- [ ] Session persists across page reloads

## Reference
BRD: docs/implementation-phase/brds/BRD-2026-05-26-sessions.md`,
  labels: ["user-story", "backend", "frontend"],
  milestone: "v1.0"
});
```

### Creating PR from Implementation
```typescript
const pr = await github_create_pull_request({
  title: "feat(US-001): Implement user session creation",
  body: `## Summary
Implements user session creation as specified in US-001.

## Changes
- Added session model
- Created session API endpoints
- Added frontend session management

## Test Coverage
Backend: 85%
Frontend: 82%

## Review Score
9/10 - Approved by Reviewer Agent`,
  base: "main",
  head: "feature/us-001-user-session",
  labels: ["enhancement"]
});
```

## Fallback (Without MCP)

If GitHub MCP is not available:
1. Document changes locally
2. Provide git commands for manual execution
3. Generate PR description in markdown for copy-paste

```bash
# Manual GitHub operations
gh issue create --title "US-001: Create user session" --body-file issue.md
gh pr create --title "feat(US-001): Implement user session" --body-file pr.md
```
