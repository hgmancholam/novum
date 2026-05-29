import { describe, expect, it } from "vitest";
import { structuredAnswerToMarkdown } from "@/lib/structuredAnswerMarkdown";
import type { StructuredAnswerData } from "@/types/events";

describe("structuredAnswerToMarkdown", () => {
  it("includes summary and renders titled blocks", () => {
    const data: StructuredAnswerData = {
      summary: "La capital de Colombia es Bogotá.",
      blocks: [
        { type: "paragraph", text: "Most likely interpretation: ..." },
        {
          type: "keyPoints",
          title: "Alternative interpretations",
          items: ["One", "Two"],
        },
        { type: "markdown", text: "Body paragraph [1]." },
      ],
    };
    const md = structuredAnswerToMarkdown(data);
    expect(md).toContain("La capital de Colombia es Bogotá.");
    expect(md).toContain("Most likely interpretation: ...");
    expect(md).toContain("**Alternative interpretations**");
    expect(md).toContain("- One");
    expect(md).toContain("- Two");
    expect(md).toContain("Body paragraph [1].");
  });

  it("renders numbered steps and key-value tables", () => {
    const data: StructuredAnswerData = {
      summary: "",
      blocks: [
        { type: "steps", title: "Process", items: ["First", "Second"] },
        {
          type: "keyValue",
          title: "Facts",
          rows: [
            { key: "Population", value: "7M" },
            { key: "Region", value: "Andes" },
          ],
        },
      ],
    };
    const md = structuredAnswerToMarkdown(data);
    expect(md).toContain("**Process**");
    expect(md).toContain("1. First");
    expect(md).toContain("2. Second");
    expect(md).toContain("| Key | Value |");
    expect(md).toContain("| Population | 7M |");
    expect(md).toContain("| Region | Andes |");
  });

  it("emits a mermaid fence", () => {
    const data: StructuredAnswerData = {
      summary: "",
      blocks: [
        { type: "mermaid", title: null, diagram: "graph TD; A-->B;" },
      ],
    };
    const md = structuredAnswerToMarkdown(data);
    expect(md).toContain("```mermaid");
    expect(md).toContain("graph TD; A-->B;");
    expect(md).toContain("```");
  });
});
