/**
 * EventPayloadViewer atom — colorized, top-level-collapsible JSON tree for
 * an event payload. No external dependency. See IP-14 §4.3 + risk row
 * (large payloads).
 */

import { useState } from "react";

import { cn } from "@/lib/cn";

export interface EventPayloadViewerProps {
  value: unknown;
  className?: string | undefined;
}

const MAX_INLINE_BYTES = 5_000;

function formatPrimitive(v: unknown): { text: string; tokenColor: string } {
  if (v === null) {
    return { text: "null", tokenColor: "var(--text-muted)" };
  }
  switch (typeof v) {
    case "string":
      return {
        text: JSON.stringify(v),
        tokenColor: "var(--semantic-success)",
      };
    case "number":
      return { text: String(v), tokenColor: "var(--accent)" };
    case "boolean":
      return { text: String(v), tokenColor: "var(--semantic-warning)" };
    case "undefined":
      return { text: "undefined", tokenColor: "var(--text-muted)" };
    default:
      return {
        text: String(v),
        tokenColor: "var(--text-primary)",
      };
  }
}

function PrimitiveValue({ value }: { value: unknown }) {
  const { text, tokenColor } = formatPrimitive(value);
  return (
    <span data-testid="payload-primitive" style={{ color: tokenColor }}>
      {text}
    </span>
  );
}

function ArrayValue({ value }: { value: readonly unknown[] }) {
  if (value.length === 0) {
    return <span style={{ color: "var(--text-muted)" }}>[]</span>;
  }
  return (
    <span>
      <span style={{ color: "var(--text-muted)" }}>[</span>
      <div className="ml-3 border-l border-[var(--glass-border)] pl-3">
        {value.map((item, idx) => (
          <div key={idx}>
            <NestedValue value={item} />
            {idx < value.length - 1 ? (
              <span style={{ color: "var(--text-muted)" }}>,</span>
            ) : null}
          </div>
        ))}
      </div>
      <span style={{ color: "var(--text-muted)" }}>]</span>
    </span>
  );
}

function ObjectValue({ value }: { value: Record<string, unknown> }) {
  const keys = Object.keys(value);
  if (keys.length === 0) {
    return <span style={{ color: "var(--text-muted)" }}>{"{}"}</span>;
  }
  return (
    <span>
      <span style={{ color: "var(--text-muted)" }}>{"{"}</span>
      <div className="ml-3 border-l border-[var(--glass-border)] pl-3">
        {keys.map((k, idx) => (
          <div key={k}>
            <span style={{ color: "var(--accent)" }}>{JSON.stringify(k)}</span>
            <span style={{ color: "var(--text-muted)" }}>: </span>
            <NestedValue value={value[k]} />
            {idx < keys.length - 1 ? (
              <span style={{ color: "var(--text-muted)" }}>,</span>
            ) : null}
          </div>
        ))}
      </div>
      <span style={{ color: "var(--text-muted)" }}>{"}"}</span>
    </span>
  );
}

function NestedValue({ value }: { value: unknown }) {
  if (value === null || typeof value !== "object") {
    return <PrimitiveValue value={value} />;
  }
  if (Array.isArray(value)) {
    return <ArrayValue value={value} />;
  }
  return <ObjectValue value={value as Record<string, unknown>} />;
}

interface TopLevelKeyProps {
  name: string;
  value: unknown;
}

function TopLevelKey({ name, value }: TopLevelKeyProps) {
  const [open, setOpen] = useState(true);
  const previewSize = JSON.stringify(value).length;
  const isHeavy = previewSize > MAX_INLINE_BYTES;
  const showInline = open && !isHeavy;
  const toggleId = `payload-key-${name}`;

  return (
    <div data-testid="payload-toplevel" data-key={name}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
        }}
        aria-expanded={open}
        aria-controls={toggleId}
        className={cn(
          "flex w-full items-center gap-1 text-left",
          "hover:text-[var(--text-primary)]"
        )}
      >
        <span style={{ color: "var(--text-muted)" }}>{open ? "▾" : "▸"}</span>
        <span style={{ color: "var(--accent)" }}>{JSON.stringify(name)}</span>
        <span style={{ color: "var(--text-muted)" }}>:</span>
        {!open ? (
          <span style={{ color: "var(--text-muted)" }}>
            {Array.isArray(value)
              ? `[${value.length.toString()}]`
              : value === null
                ? "null"
                : typeof value === "object"
                  ? `{${Object.keys(value as object).length.toString()}}`
                  : "…"}
          </span>
        ) : null}
        {open && isHeavy ? (
          <span style={{ color: "var(--text-muted)" }}>
            ({(previewSize / 1024).toFixed(1)} KB hidden — click to collapse)
          </span>
        ) : null}
      </button>
      {showInline ? (
        <div id={toggleId} className="ml-4">
          <NestedValue value={value} />
        </div>
      ) : null}
    </div>
  );
}

export function EventPayloadViewer({
  value,
  className,
}: EventPayloadViewerProps) {
  const isObject =
    value !== null && typeof value === "object" && !Array.isArray(value);
  const entries = isObject
    ? Object.entries(value as Record<string, unknown>)
    : [];
  const isEmptyObject = isObject && entries.length === 0;

  return (
    <pre
      data-testid="event-payload-viewer"
      className={cn(
        "whitespace-pre-wrap break-words font-mono text-xs leading-relaxed",
        "text-[var(--text-secondary)]",
        className
      )}
    >
      {isEmptyObject ? (
        <span style={{ color: "var(--text-muted)" }}>{"{}"}</span>
      ) : isObject ? (
        entries.map(([k, v]) => <TopLevelKey key={k} name={k} value={v} />)
      ) : (
        <NestedValue value={value} />
      )}
    </pre>
  );
}
