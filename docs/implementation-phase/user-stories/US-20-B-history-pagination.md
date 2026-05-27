# US-20-B: Paginate the history panel with a "More" button

**Story ID:** US-20-B
**BRD Reference:** BRD-20
**Priority:** High
**Estimated Effort:** S

## User Story

**As an** authenticated user with many prior runs
**I want** the History panel to load 20 runs initially and let me request more on demand
**So that** the initial render stays fast and I can still reach older runs when I need them

## Acceptance Criteria

### Scenario 1: First page returns 20 items by default
```gherkin
Given I am authenticated and I have 35 runs
When the History panel mounts
Then the panel sends GET /api/runs?limit=20
  And the response is { items: [...20...], has_more: true, next_cursor: "<opaque>" }
  And exactly 20 cards are rendered
  And a "More" button is rendered at the end of the list
```

### Scenario 2: "More" loads the next page and appends
```gherkin
Given the panel has loaded the first 20 items and "More" is visible
When I click "More"
Then the panel sends GET /api/runs?limit=20&cursor=<next_cursor from page 1>
  And the response items are appended below the existing 20
  And the new next_cursor replaces the old one
  And the "More" button stays visible if has_more is still true
```

### Scenario 3: End of list — button hides
```gherkin
Given the last loaded page returned has_more=false
When the render commits
Then the "More" button is no longer in the DOM
  And no further pagination requests are sent
```

### Scenario 4: Empty history
```gherkin
Given I have zero runs
When the History panel mounts
Then the response is { items: [], has_more: false, next_cursor: null }
  And the panel renders the L1 empty state from BRD-12
  And no "More" button is rendered
```

### Scenario 5: Loading state inside the "More" button
```gherkin
Given the user has just clicked "More"
When the request is in flight
Then the button is disabled
  And its label shows a spinner or "Loading…" text
  And no duplicate requests are sent on additional clicks
```

### Scenario 6: Malformed or tampered cursor → 400
```gherkin
Given a client sends GET /api/runs?cursor=NOT_BASE64
When the backend decodes the cursor
Then the backend returns 400 Bad Request
  And the response body contains "Invalid cursor"
```

### Scenario 7: Pagination is stable when runs are deleted between pages
```gherkin
Given the panel has loaded page 1 (20 items) and page 2 (20 items)
  And the user deletes the last item of page 1
When the user clicks "More" to load page 3
Then page 3 is computed from the cursor of page 2 (unchanged)
  And no item is duplicated or skipped
```

### Scenario 8: Keyset ordering — stable when new runs arrive
```gherkin
Given the user has loaded pages 1 and 2
  And a new run is created in the background
When the user clicks "More" to load page 3
Then page 3 contains rows older than the last row of page 2
  And the new run does not appear inside page 3
  And no row from page 2 is duplicated in page 3
```

## Technical Notes

- Backend uses `ORDER BY started_at DESC, id DESC`, keyset over `(started_at, id)`.
- Cursor codec: `base64url(f"{started_at.isoformat()}|{id}")`. Decoded server-side; bad cursors → 400.
- `limit` clamped to `1 ≤ limit ≤ 100`, default `20`.
- Frontend: TanStack `useInfiniteQuery`, `initialPageParam: undefined`, `getNextPageParam: (p) => p.next_cursor ?? undefined`. Flat list via `data.pages.flatMap(p => p.items)`.
- Keep the existing `useRunHistory` query key shape `["runs", filters]` so `useDeleteRun` can update it.
- Breaking change: `GET /api/runs` previously returned `list[RunListItem]`. It now returns `RunListPage`. The only consumer is the frontend `useRunHistory`, updated atomically.
- Frontend `getRunHistory(cursor?)` MUST prefix `API_URL` (per user memory L-008).
- No `IntersectionObserver` auto-load — the user wants an explicit gesture.

## Dependencies

- [ ] BRD-12 `HistoryPanel` exists
- [ ] BRD-04 `X-Username` dependency available
- [ ] US-20-A — same query key invalidation surface; the two stories share a hook

## Definition of Done

- [ ] `GET /api/runs` returns `RunListPage` with `items`, `has_more`, `next_cursor`
- [ ] `useRunHistory` migrated to `useInfiniteQuery`
- [ ] `HistoryPanel` renders the "More" button per spec (loading, disabled, hidden when done)
- [ ] Cursor codec + bad-cursor 400 covered by tests
- [ ] Unit tests pass (BE ≥ 80% on `list_runs_keyset`; FE ≥ 80% on `HistoryPanel`)
- [ ] Code review score ≥ 9/10
