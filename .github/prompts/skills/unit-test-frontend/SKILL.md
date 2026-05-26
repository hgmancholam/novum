# Frontend Unit Testing Skill

## Description
Specialized knowledge for React/Vitest testing best practices, component testing, accessibility testing, and API mocking.

## When to Use
- Writing unit tests for React components
- Testing with Testing Library
- Ensuring accessibility with jest-axe
- Mocking APIs with MSW
- Measuring test coverage

## Tech Stack

- **Testing Framework**: Vitest
- **Component Testing**: Testing Library
- **Accessibility**: jest-axe
- **API Mocking**: MSW (Mock Service Worker)
- **User Interactions**: @testing-library/user-event

## Test Structure

```
frontend/src/
├── components/
│   ├── atoms/
│   │   ├── Button.tsx
│   │   └── Button.test.tsx      # Co-located tests
│   ├── molecules/
│   │   ├── SearchBar.tsx
│   │   └── SearchBar.test.tsx
│   └── organisms/
│       ├── RunCard.tsx
│       └── RunCard.test.tsx
├── lib/
│   └── api/
│       └── api.test.ts
├── test/
│   ├── setup.ts                 # Test setup
│   ├── mocks/
│   │   ├── handlers.ts          # MSW handlers
│   │   └── server.ts            # MSW server
│   └── utils.tsx                # Test utilities
└── vitest.config.ts
```

## Vitest Configuration

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      exclude: ["node_modules/", "src/test/"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },
  },
});
```

## Test Setup

```typescript
// src/test/setup.ts
import "@testing-library/jest-dom";
import { expect, afterEach, beforeAll, afterAll } from "vitest";
import { cleanup } from "@testing-library/react";
import { toHaveNoViolations } from "jest-axe";
import { server } from "./mocks/server";

// Extend expect with jest-axe matchers
expect.extend(toHaveNoViolations);

// Setup MSW
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
```

## Component Testing Patterns

### Basic Component Test
```typescript
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders with text", () => {
    render(<Button>Click me</Button>);
    
    expect(screen.getByRole("button", { name: /click me/i }))
      .toBeInTheDocument();
  });

  it("applies variant styles", () => {
    render(<Button variant="destructive">Delete</Button>);
    
    expect(screen.getByRole("button"))
      .toHaveClass("bg-destructive");
  });

  it("is disabled when prop is set", () => {
    render(<Button disabled>Disabled</Button>);
    
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

### User Interaction Testing
```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { SearchBar } from "./SearchBar";

describe("SearchBar", () => {
  it("calls onSearch when form is submitted", async () => {
    const user = userEvent.setup();
    const handleSearch = vi.fn();
    
    render(<SearchBar onSearch={handleSearch} />);
    
    await user.type(screen.getByRole("textbox"), "test query");
    await user.click(screen.getByRole("button", { name: /search/i }));
    
    expect(handleSearch).toHaveBeenCalledWith("test query");
  });

  it("clears input after search", async () => {
    const user = userEvent.setup();
    
    render(<SearchBar onSearch={vi.fn()} />);
    
    const input = screen.getByRole("textbox");
    await user.type(input, "test");
    await user.keyboard("{Enter}");
    
    expect(input).toHaveValue("");
  });
});
```

## Accessibility Testing

```typescript
import { render } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { describe, it, expect } from "vitest";
import { RunCard } from "./RunCard";

expect.extend(toHaveNoViolations);

describe("RunCard Accessibility", () => {
  const mockRun = {
    id: "123",
    query: "What is TypeScript?",
    status: "completed",
    createdAt: new Date().toISOString(),
  };

  it("has no accessibility violations", async () => {
    const { container } = render(<RunCard run={mockRun} />);
    const results = await axe(container);
    
    expect(results).toHaveNoViolations();
  });

  it("has accessible button labels", () => {
    render(<RunCard run={mockRun} />);
    
    expect(screen.getByRole("button", { name: /view details/i }))
      .toBeInTheDocument();
  });

  it("uses semantic headings", () => {
    render(<RunCard run={mockRun} />);
    
    expect(screen.getByRole("heading", { level: 3 }))
      .toHaveTextContent(mockRun.query);
  });
});
```

## MSW API Mocking

### Handler Setup
```typescript
// src/test/mocks/handlers.ts
import { http, HttpResponse } from "msw";

export const handlers = [
  // GET /api/runs
  http.get("/api/runs", () => {
    return HttpResponse.json([
      { id: "1", query: "Test", status: "completed" },
      { id: "2", query: "Test 2", status: "pending" },
    ]);
  }),

  // GET /api/runs/:id
  http.get("/api/runs/:id", ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      query: "Test query",
      status: "completed",
    });
  }),

  // POST /api/runs
  http.post("/api/runs", async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(
      { id: "new-id", ...body, status: "pending" },
      { status: 201 }
    );
  }),

  // Error scenarios
  http.get("/api/runs/error", () => {
    return HttpResponse.json(
      { error: "Not found" },
      { status: 404 }
    );
  }),
];
```

### Server Setup
```typescript
// src/test/mocks/server.ts
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

### Using in Tests
```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { server } from "@/test/mocks/server";
import { http, HttpResponse } from "msw";
import { RunList } from "./RunList";

describe("RunList", () => {
  it("displays runs from API", async () => {
    render(<RunList />);
    
    await waitFor(() => {
      expect(screen.getByText("Test")).toBeInTheDocument();
    });
  });

  it("handles API errors gracefully", async () => {
    // Override handler for this test
    server.use(
      http.get("/api/runs", () => {
        return HttpResponse.json(
          { error: "Server error" },
          { status: 500 }
        );
      })
    );
    
    render(<RunList />);
    
    await waitFor(() => {
      expect(screen.getByRole("alert"))
        .toHaveTextContent(/error/i);
    });
  });
});
```

## Test Utilities

### Custom Render with Providers
```typescript
// src/test/utils.tsx
import { ReactElement } from "react";
import { render, RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

const AllProviders = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  );
};

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) => render(ui, { wrapper: AllProviders, ...options });

export * from "@testing-library/react";
export { customRender as render };
```

### Mock Data Factories
```typescript
// src/test/factories.ts
import { Run, Event } from "@/types";

export function createMockRun(overrides?: Partial<Run>): Run {
  return {
    id: crypto.randomUUID(),
    query: "Default query",
    status: "pending",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

export function createMockEvent(overrides?: Partial<Event>): Event {
  return {
    id: crypto.randomUUID(),
    runId: crypto.randomUUID(),
    type: "search",
    payload: {},
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}
```

## Running Tests

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test -- --watch

# Run specific file
npm run test -- src/components/Button.test.tsx

# Run with coverage
npm run test -- --coverage

# Run only accessibility tests
npm run test -- -t "accessibility"
```

## Coverage Requirements

### Minimum Thresholds
- Lines: 80%
- Functions: 80%
- Branches: 80%
- Statements: 80%

### Excluding from Coverage
```typescript
// vitest.config.ts
coverage: {
  exclude: [
    "src/test/**",
    "src/types/**",
    "**/*.d.ts",
    "src/main.tsx",
  ],
}
```

## Best Practices

1. **Query Priority** (most to least preferred):
   - `getByRole`
   - `getByLabelText`
   - `getByText`
   - `getByTestId`

2. **Async Operations**: Always use `waitFor` or `findBy` queries

3. **User Events**: Use `userEvent` over `fireEvent`

4. **Test IDs**: Only as last resort, use `data-testid`

5. **Mocking**: Mock at the network level (MSW), not module level
