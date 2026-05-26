# User Experience & Frontend Skill

## Description
Specialized knowledge for UI/UX best practices, accessibility, responsive design, and frontend development with React, Tailwind, and shadcn/ui.

## When to Use
- Implementing frontend components
- Designing user interfaces
- Ensuring accessibility compliance
- Creating responsive layouts
- Applying design system patterns

## Tech Stack Reference

### Core Technologies
- **React 19**: Modern hooks API, concurrent rendering
- **Vite**: Sub-second HMR, native ESM
- **TypeScript**: Strict mode enabled
- **Tailwind v4**: Plugin via @tailwindcss/vite

### UI Components
- **shadcn/ui**: Radix UI primitives
- **Motion v12**: Animations (motion/react)
- **Lucide React**: Icons

## UX Best Practices

### Accessibility (WCAG 2.1 AA)
```typescript
// 1. All interactive elements must be keyboard accessible
<Button onKeyDown={handleKeyDown} tabIndex={0}>
  Click me
</Button>

// 2. Use semantic HTML
<nav aria-label="Main navigation">
  <ul role="list">
    <li><a href="/home">Home</a></li>
  </ul>
</nav>

// 3. Provide alt text for images
<img src={image} alt="Descriptive text about the image" />

// 4. Use aria-labels for icon buttons
<Button aria-label="Close dialog">
  <X className="h-4 w-4" />
</Button>

// 5. Test with jest-axe
import { axe, toHaveNoViolations } from "jest-axe";
expect.extend(toHaveNoViolations);

it("has no accessibility violations", async () => {
  const { container } = render(<Component />);
  expect(await axe(container)).toHaveNoViolations();
});
```

### Responsive Design
```typescript
// Mobile-first approach with Tailwind
<div className="
  p-4          // Base (mobile)
  sm:p-6       // Small screens
  md:p-8       // Medium screens
  lg:p-10      // Large screens
  xl:p-12      // Extra large
">
  Content
</div>

// Container queries (Tailwind v4)
<div className="@container">
  <div className="@sm:flex @md:grid @lg:grid-cols-3">
    Responsive content
  </div>
</div>
```

### Animation Principles
```typescript
import { motion } from "motion/react";

// 1. Subtle, purposeful animations
<motion.div
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.2, ease: "easeOut" }}
>
  Fading content
</motion.div>

// 2. Respect reduced motion preferences
const prefersReducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)"
).matches;

<motion.div
  animate={{ scale: prefersReducedMotion ? 1 : 1.05 }}
>
  Interactive element
</motion.div>
```

## Component Patterns

### Atomic Design Structure
```
frontend/src/
├── components/
│   ├── atoms/         # Basic building blocks
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   └── Badge.tsx
│   ├── molecules/     # Combinations of atoms
│   │   ├── SearchBar.tsx
│   │   └── FormField.tsx
│   ├── organisms/     # Complex components
│   │   ├── Header.tsx
│   │   └── RunCard.tsx
│   ├── templates/     # Page layouts
│   │   └── MainLayout.tsx
│   └── pages/         # Route components (fetch data here)
│       └── RunPage.tsx
```

### Component Template
```typescript
import { cn } from "@/lib/utils";
import { motion } from "motion/react";

interface ComponentProps {
  children: React.ReactNode;
  variant?: "default" | "outline" | "ghost";
  className?: string;
}

export function Component({
  children,
  variant = "default",
  className,
}: ComponentProps) {
  return (
    <motion.div
      className={cn(
        "rounded-lg p-4",
        variant === "default" && "bg-primary text-primary-foreground",
        variant === "outline" && "border border-input",
        variant === "ghost" && "hover:bg-accent",
        className
      )}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {children}
    </motion.div>
  );
}
```

### Form Patterns
```typescript
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  query: z.string().min(1, "Query is required"),
});

type FormData = z.infer<typeof schema>;

function QueryForm() {
  const form = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = (data: FormData) => {
    // Handle submission
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Input
        {...form.register("query")}
        aria-invalid={!!form.formState.errors.query}
        aria-describedby="query-error"
      />
      {form.formState.errors.query && (
        <span id="query-error" role="alert">
          {form.formState.errors.query.message}
        </span>
      )}
    </form>
  );
}
```

## Tailwind v4 Specifics

### Setup (No config file needed)
```css
/* index.css - First line MUST be: */
@import "tailwindcss";

/* Custom theme via CSS variables */
@theme {
  --color-primary: oklch(0.7 0.15 200);
  --font-sans: "Inter", sans-serif;
}
```

### Using cn() Utility
```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Usage
<div className={cn(
  "base-styles",
  isActive && "active-styles",
  isDisabled && "disabled-styles"
)} />
```

## Testing Guidelines

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("Button", () => {
  it("handles click events", async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    
    await userEvent.click(screen.getByRole("button"));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("is keyboard accessible", async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    
    screen.getByRole("button").focus();
    await userEvent.keyboard("{Enter}");
    expect(handleClick).toHaveBeenCalledOnce();
  });
});
```
