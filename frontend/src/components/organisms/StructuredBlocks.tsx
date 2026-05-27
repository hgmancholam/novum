/**
 * StructuredBlocks organism — renders typed structured-answer JSON (RF-10).
 *
 * Receives a `StructuredAnswerData` payload produced by the backend
 * `StructuredRenderer.build_data` and styles each block with native UI
 * components (tables, ordered/unordered lists, Mermaid fence, prose).
 *
 * No markdown parsing on the read path — markdown is only used inside
 * the `markdown` block (fallback for already-formatted LLM content).
 */
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/cn";
import type {
  KeyPointsBlock,
  KeyValueBlock,
  MarkdownBlock,
  MermaidBlock,
  ParagraphBlock,
  StepsBlock,
  StructuredAnswerData,
  StructuredBlock,
} from "@/types/events";

export interface StructuredBlocksProps {
  data: StructuredAnswerData;
  className?: string | undefined;
}

export function StructuredBlocks({ data, className }: StructuredBlocksProps) {
  return (
    <section
      data-testid="structured-blocks"
      aria-label="Structured answer"
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-(--glass-border)",
        "bg-(--bg-secondary) p-5",
        className
      )}
    >
      {data.summary ? (
        <p
          data-testid="structured-summary"
          className="text-base font-medium leading-relaxed text-(--text-primary)"
        >
          {data.summary}
        </p>
      ) : null}
      {data.blocks.length > 0 ? (
        <div className="flex flex-col gap-3">
          {data.blocks.map((block, idx) => (
            <BlockRenderer key={idx} block={block} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function BlockRenderer({ block }: { block: StructuredBlock }) {
  switch (block.type) {
    case "paragraph":
      return <Paragraph block={block} />;
    case "keyValue":
      return <KeyValueTable block={block} />;
    case "steps":
      return <Steps block={block} />;
    case "keyPoints":
      return <KeyPoints block={block} />;
    case "mermaid":
      return <Mermaid block={block} />;
    case "markdown":
      return <MarkdownFallback block={block} />;
  }
}

function BlockTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-(--text-muted)">
      {children}
    </h3>
  );
}

function Paragraph({ block }: { block: ParagraphBlock }) {
  return (
    <p
      data-testid="block-paragraph"
      className="text-sm leading-relaxed text-(--text-primary)"
    >
      {block.text}
    </p>
  );
}

function KeyValueTable({ block }: { block: KeyValueBlock }) {
  return (
    <div data-testid="block-key-value" className="flex flex-col gap-2">
      {block.title ? <BlockTitle>{block.title}</BlockTitle> : null}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <tbody>
            {block.rows.map((row, idx) => (
              <tr
                key={idx}
                className="border-b border-(--glass-border) last:border-b-0"
              >
                <th
                  scope="row"
                  className="w-1/3 py-2 pr-4 text-left align-top font-medium text-(--text-muted)"
                >
                  {row.key}
                </th>
                <td className="py-2 align-top text-(--text-primary)">
                  {row.value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Steps({ block }: { block: StepsBlock }) {
  return (
    <div data-testid="block-steps" className="flex flex-col gap-2">
      {block.title ? <BlockTitle>{block.title}</BlockTitle> : null}
      <ol className="flex flex-col gap-2 pl-2">
        {block.items.map((item, idx) => (
          <li key={idx} className="flex gap-3 text-sm text-(--text-primary)">
            <span
              aria-hidden="true"
              className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-(--accent-primary) text-xs font-semibold text-(--bg-primary)"
            >
              {idx + 1}
            </span>
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function KeyPoints({ block }: { block: KeyPointsBlock }) {
  return (
    <div data-testid="block-key-points" className="flex flex-col gap-2">
      {block.title ? <BlockTitle>{block.title}</BlockTitle> : null}
      <ul className="flex flex-col gap-1.5 pl-1">
        {block.items.map((item, idx) => (
          <li key={idx} className="flex gap-2 text-sm text-(--text-primary)">
            <span
              aria-hidden="true"
              className="mt-2 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-(--accent-primary)"
            />
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Mermaid({ block }: { block: MermaidBlock }) {
  return (
    <div data-testid="block-mermaid" className="flex flex-col gap-2">
      {block.title ? <BlockTitle>{block.title}</BlockTitle> : null}
      <div
        className={cn(
          "overflow-x-auto rounded-lg border border-(--accent-primary)",
          "bg-(--bg-primary) p-3"
        )}
      >
        <SyntaxHighlighter
          language="yaml"
          style={oneDark}
          customStyle={{
            margin: 0,
            borderRadius: "0.375rem",
            fontSize: "0.8rem",
          }}
        >
          {block.diagram}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

function MarkdownFallback({ block }: { block: MarkdownBlock }) {
  return (
    <div
      data-testid="block-markdown"
      className="prose prose-sm max-w-none
        prose-headings:text-(--text-primary)
        prose-p:text-(--text-primary)
        prose-li:text-(--text-primary)
        prose-a:text-(--accent-primary)
        prose-table:text-(--text-primary)
        prose-th:text-(--text-primary)
        prose-td:text-(--text-primary)"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.text}</ReactMarkdown>
    </div>
  );
}
