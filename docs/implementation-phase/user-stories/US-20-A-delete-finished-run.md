# US-20-A: Delete a finished run from the history panel

**Story ID:** US-20-A
**BRD Reference:** BRD-20
**Priority:** High
**Estimated Effort:** M

## User Story

**As an** authenticated user with prior research runs
**I want** to permanently remove a finished run from my history with a single click
**So that** I can curate my history and stop seeing runs I no longer care about

## Acceptance Criteria

### Scenario 1: Trash icon revealed on hover for finished runs
```gherkin
Given I am viewing the History panel
  And the panel contains a finished run R (run.stop_reason is set)
When I hover the run card for R
Then a trash icon appears at the bottom-right of the card
  And the icon has accessible name "Delete run"
  And the icon is reachable via keyboard focus
```

### Scenario 2: Trash icon hidden for in-progress runs
```gherkin
Given the panel contains a run R with status "running" (stop_reason is null)
When I hover R's card
Then no trash icon is rendered
```

### Scenario 3: Delete without confirmation, optimistic UI
```gherkin
Given I own a finished run R that is visible in my panel
When I click the trash icon on R's card
Then no confirmation dialog is shown
  And R's card animates out within ~180ms
  And R disappears from the cached history pages immediately
  And the backend receives DELETE /api/runs/{R.id}
  And the backend responds 204 No Content
```

### Scenario 4: Backend cascades the deletion
```gherkin
Given run R has N event rows
When DELETE /api/runs/{R.id} commits
Then the runs row for R is removed
  And all N events rows referencing R are removed via ON DELETE CASCADE
```

### Scenario 5: Cannot delete an in-progress run (server defense)
```gherkin
Given a run R with stop_reason IS NULL
When DELETE /api/runs/{R.id} is sent (even bypassing the UI)
Then the backend returns 409 Conflict
  And the response body contains "Cannot delete a run that is still in progress"
  And no rows are deleted
```

### Scenario 6: Cannot delete a run I do not own
```gherkin
Given run R is owned by user "alice"
  And I am authenticated as "bob"
When I send DELETE /api/runs/{R.id}
Then the backend returns 403 Forbidden
  And no rows are deleted
```

### Scenario 7: Fork orphaning preserves descendants
```gherkin
Given a finished run P has two forked children F1 and F2 (parent_run_id = P.id)
When P is deleted successfully
Then F1 and F2 still exist in the database
  And F1.parent_run_id IS NULL
  And F2.parent_run_id IS NULL
  And F1 and F2 still appear in the history list (without the fork lineage badge)
```

### Scenario 8: Network/server error rolls back the optimistic removal
```gherkin
Given I clicked the trash icon and the card animated out
When the DELETE request returns 5xx or fails to reach the server
Then the card is restored to its previous position in the panel
  And an error message is surfaced (toast or inline)
  And the cached query state is restored to the pre-mutation snapshot
```

## Technical Notes

- Trash button: `lucide-react` `Trash2`, 16px, absolute-positioned `bottom-2 right-2`, `opacity-0 group-hover:opacity-100 focus-visible:opacity-100`, 120ms fade (skipped when `prefers-reduced-motion`).
- `aria-label="Delete run"`, `title="Delete run"`, `type="button"`, `onClick` stops propagation so the row click handler (select run) does not fire.
- Conditional render: button only mounts when `run.stop_reason !== null` AND `onDelete` is defined.
- Optimistic mutation: `useDeleteRun` snapshots all `["runs", *]` query data in `onMutate`, removes the item from every page, and restores on `onError`. Invalidate on `onSettled`.
- Server: ownership check **before** terminal-state check (do not leak existence of someone else's run).
- The schema already has `events.run_id ON DELETE CASCADE` and `runs.parent_run_id ON DELETE SET NULL`; no migration is required (BRD-20 §4.2).
- Append a `connection_manager.close(run_id)` call after the delete commits to drop any in-flight SSE consumers cleanly.

## Dependencies

- [ ] BRD-12 `HistoryItem` / `HistoryPanel` exist
- [ ] BRD-04 `X-Username` dependency available
- [ ] BRD-09 `stop_reason` enum reachable via `Run.stop_reason`

## Definition of Done

- [ ] `DELETE /api/runs/{run_id}` implemented and returns 204/403/404/409 per BRD-20 §4.5
- [ ] `HistoryItem` renders trash button per spec (hover, focus, ARIA, conditional)
- [ ] `useDeleteRun` performs optimistic update + rollback
- [ ] Unit tests pass (BE ≥ 80% on `run_service.delete_run`; FE ≥ 80% on `HistoryItem` + `useDeleteRun`)
- [ ] jest-axe a11y scan on `HistoryPanel` passes
- [ ] Code review score ≥ 9/10
