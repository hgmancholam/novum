/**
 * Serializes a `StructuredAnswerData` payload to Markdown that mirrors
 * what `StructuredBlocks` renders on screen. Used by the Copy button so
 * the clipboard content matches the structured view (summary, optional
 * titles, key-value tables, ordered/unordered lists, mermaid fences).
 */
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

function paragraph(b: ParagraphBlock): string {
  return b.text;
}

function markdown(b: MarkdownBlock): string {
  return b.text;
}

function withTitle(title: string | null | undefined, body: string): string {
  if (title === null || title === undefined || title.trim() === "") {
    return body;
  }
  return `**${title}**\n\n${body}`;
}

function keyValue(b: KeyValueBlock): string {
  if (b.rows.length === 0) return withTitle(b.title, "");
  const header = "| Key | Value |\n| --- | --- |";
  const rows = b.rows
    .map((r) => `| ${escapeCell(r.key)} | ${escapeCell(r.value)} |`)
    .join("\n");
  return withTitle(b.title, `${header}\n${rows}`);
}

function escapeCell(s: string): string {
  return s.replace(/\|/g, "\\|").replace(/\n/g, " ");
}

function steps(b: StepsBlock): string {
  const body = b.items.map((item, i) => `${i + 1}. ${item}`).join("\n");
  return withTitle(b.title, body);
}

function keyPoints(b: KeyPointsBlock): string {
  const body = b.items.map((item) => `- ${item}`).join("\n");
  return withTitle(b.title, body);
}

function mermaid(b: MermaidBlock): string {
  const body = `\`\`\`mermaid\n${b.diagram}\n\`\`\``;
  return withTitle(b.title, body);
}

function renderBlock(block: StructuredBlock): string {
  switch (block.type) {
    case "paragraph":
      return paragraph(block);
    case "keyValue":
      return keyValue(block);
    case "steps":
      return steps(block);
    case "keyPoints":
      return keyPoints(block);
    case "mermaid":
      return mermaid(block);
    case "markdown":
      return markdown(block);
  }
}

export function structuredAnswerToMarkdown(
  data: StructuredAnswerData
): string {
  const parts: string[] = [];
  if (data.summary && data.summary.trim() !== "") {
    parts.push(data.summary);
  }
  for (const block of data.blocks) {
    const rendered = renderBlock(block);
    if (rendered.trim() !== "") {
      parts.push(rendered);
    }
  }
  return parts.join("\n\n");
}
