# User Story Template

**Story ID:** US-{number}
**Title:** {Short descriptive title}
**BRD Reference:** BRD-{date}-{feature}
**Priority:** High | Medium | Low
**Estimated Effort:** S | M | L | XL
**Status:** Draft | Ready | In Progress | Done

---

## User Story

**As a** {type of user}
**I want** {goal/desire}
**So that** {benefit/value}

---

## Acceptance Criteria

### Scenario 1: {Happy Path}

```gherkin
Given {initial context/precondition}
And {additional context if needed}
When {action/trigger}
Then {expected outcome}
And {additional outcomes if needed}
```

### Scenario 2: {Alternative Path}

```gherkin
Given {initial context/precondition}
When {action/trigger}
Then {expected outcome}
```

### Scenario 3: {Error Path}

```gherkin
Given {initial context/precondition}
When {invalid action/trigger}
Then {error handling/feedback}
```

---

## Technical Notes

### Backend Considerations
- {Backend implementation note 1}
- {Backend implementation note 2}

### Frontend Considerations
- {Frontend implementation note 1}
- {Frontend implementation note 2}

### Database Changes
- {Database change 1}
- {Database change 2}

### API Changes
- {API endpoint change 1}
- {API endpoint change 2}

---

## UI/UX Notes

{Include wireframe references, design system components to use, accessibility requirements}

---

## Dependencies

- [ ] {Dependency 1 - link to related story/task}
- [ ] {Dependency 2}

---

## Test Cases

| ID | Test Description | Type | Priority |
|----|------------------|------|----------|
| TC-01 | {test description} | Unit/Integration/E2E | High |
| TC-02 | {test description} | Unit/Integration/E2E | Medium |

---

## Definition of Done

- [ ] Code implemented and follows coding standards
- [ ] Unit tests written and passing (≥80% coverage)
- [ ] Code reviewed and approved (score ≥9/10)
- [ ] Acceptance criteria verified
- [ ] Documentation updated
- [ ] Deployed to staging environment
- [ ] Memory bank updated

---

## Notes

{Any additional notes, context, or clarifications}

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {date} | BSA Agent | Initial creation |
