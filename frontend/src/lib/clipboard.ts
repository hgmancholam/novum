/**
 * Clipboard utilities for Novum frontend.
 * Used by ShareLinkButton to copy run URLs.
 * See ui-prototype.md §8.3.
 */

/**
 * Copies text to the clipboard.
 * Uses the modern Clipboard API with fallback.
 *
 * @param text - The text to copy
 * @returns Promise that resolves when copied, rejects on failure
 */
export async function copyToClipboard(text: string): Promise<void> {
  // Try modern Clipboard API first
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    await navigator.clipboard.writeText(text);
    return;
  }

  // Fallback for older browsers or non-HTTPS contexts
  const textArea = document.createElement("textarea");
  textArea.value = text;

  // Prevent scrolling to bottom
  textArea.style.position = "fixed";
  textArea.style.top = "0";
  textArea.style.left = "0";
  textArea.style.width = "2em";
  textArea.style.height = "2em";
  textArea.style.padding = "0";
  textArea.style.border = "none";
  textArea.style.outline = "none";
  textArea.style.boxShadow = "none";
  textArea.style.background = "transparent";

  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();

  try {
    const successful = document.execCommand("copy");
    if (!successful) {
      throw new Error("Copy command failed");
    }
  } finally {
    document.body.removeChild(textArea);
  }
}

/**
 * Copies the current run URL to clipboard.
 * Convenience wrapper for ShareLinkButton.
 *
 * @param runId - The run ID to build the URL for
 * @returns Promise that resolves when copied
 */
export async function copyRunUrl(runId: string): Promise<void> {
  const url = `${window.location.origin}/runs/${runId}`;
  await copyToClipboard(url);
}

/**
 * Copies a diff URL to clipboard.
 *
 * @param runAId - First run ID
 * @param runBId - Second run ID
 * @returns Promise that resolves when copied
 */
export async function copyDiffUrl(runAId: string, runBId: string): Promise<void> {
  const url = `${window.location.origin}/diff/${runAId}/${runBId}`;
  await copyToClipboard(url);
}
