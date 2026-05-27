import { render, screen, within } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { describe, expect, it } from "vitest";

import { StructuredBlocks } from "./StructuredBlocks";
import type { StructuredAnswerData } from "@/types/events";

expect.extend(toHaveNoViolations);

describe("StructuredBlocks", () => {
  it("renders only the summary when no blocks are provided", () => {
    const data: StructuredAnswerData = {
      summary: "La capital de Japón es Tokio.",
      blocks: [],
    };
    render(<StructuredBlocks data={data} />);
    expect(screen.getByTestId("structured-summary")).toHaveTextContent(
      "La capital de Japón es Tokio."
    );
    expect(screen.queryByTestId("block-paragraph")).toBeNull();
  });

  it("renders paragraph blocks", () => {
    const data: StructuredAnswerData = {
      summary: "Resumen.",
      blocks: [
        { type: "paragraph", text: "Primer párrafo." },
        { type: "paragraph", text: "Segundo párrafo." },
      ],
    };
    render(<StructuredBlocks data={data} />);
    const paragraphs = screen.getAllByTestId("block-paragraph");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]).toHaveTextContent("Primer párrafo.");
  });

  it("renders a key/value block as a semantic table", () => {
    const data: StructuredAnswerData = {
      summary: "Datos clave.",
      blocks: [
        {
          type: "keyValue",
          title: "Facts",
          rows: [
            { key: "País", value: "Japón" },
            { key: "Capital", value: "Tokio" },
          ],
        },
      ],
    };
    render(<StructuredBlocks data={data} />);
    const block = screen.getByTestId("block-key-value");
    const rowHeaders = within(block).getAllByRole("rowheader");
    expect(rowHeaders).toHaveLength(2);
    expect(rowHeaders[0]).toHaveTextContent("País");
    expect(within(block).getByText("Tokio")).toBeInTheDocument();
  });

  it("renders an ordered list for steps", () => {
    const data: StructuredAnswerData = {
      summary: "Proceso.",
      blocks: [
        {
          type: "steps",
          title: "Pasos",
          items: ["Primero", "Segundo", "Tercero"],
        },
      ],
    };
    render(<StructuredBlocks data={data} />);
    const list = within(screen.getByTestId("block-steps")).getByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Primero");
  });

  it("renders an unordered list for key points", () => {
    const data: StructuredAnswerData = {
      summary: "Resumen.",
      blocks: [
        {
          type: "keyPoints",
          title: "Puntos",
          items: ["Uno", "Dos"],
        },
      ],
    };
    render(<StructuredBlocks data={data} />);
    const list = within(screen.getByTestId("block-key-points")).getByRole(
      "list"
    );
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders a mermaid diagram source", () => {
    const data: StructuredAnswerData = {
      summary: "Flujo.",
      blocks: [
        {
          type: "mermaid",
          title: "Diagrama",
          diagram: "flowchart TD\n  A --> B",
        },
      ],
    };
    render(<StructuredBlocks data={data} />);
    const block = screen.getByTestId("block-mermaid");
    expect(block).toHaveTextContent(/flowchart/);
  });

  it("renders the markdown fallback as rich text", () => {
    const data: StructuredAnswerData = {
      summary: "Tabla.",
      blocks: [
        {
          type: "markdown",
          text: "## Sección\n\nContenido",
        },
      ],
    };
    render(<StructuredBlocks data={data} />);
    const block = screen.getByTestId("block-markdown");
    expect(within(block).getByRole("heading", { name: "Sección" })).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const data: StructuredAnswerData = {
      summary: "Resumen accesible.",
      blocks: [
        {
          type: "keyValue",
          title: "Facts",
          rows: [
            { key: "K1", value: "V1" },
            { key: "K2", value: "V2" },
          ],
        },
        {
          type: "steps",
          title: "Pasos",
          items: ["Uno", "Dos", "Tres"],
        },
      ],
    };
    const { container } = render(<StructuredBlocks data={data} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
