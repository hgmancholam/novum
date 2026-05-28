/**
 * DeepFetchEntry molecule — renders a single `DeepFetchPerformed` event
 * in the trace timeline (BRD-23 WP-2, §4.6). Success shows page-size
 * + latency, failure shows the reason string.
 */

import { Download } from "lucide-react";

export interface DeepFetchEntryProps {
  url: string;
  title?: string | null;
  fetchMs: number;
  contentLength: number;
  success: boolean;
  failureReason?: string | null;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

export function DeepFetchEntry({
  url,
  title,
  fetchMs,
  contentLength,
  success,
  failureReason,
}: DeepFetchEntryProps) {
  const label = title?.trim() || hostOf(url);
  return (
    <div
      role="group"
      aria-label="Deep fetch performed"
      className="flex items-start gap-2 text-sm"
    >
      <Download aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        {success ? (
          <p>
            Fetched full page for «{label}» ({fetchMs} ms, {contentLength} chars)
          </p>
        ) : (
          <p>Deep-fetch failed: {failureReason ?? "unknown reason"}</p>
        )}
      </div>
    </div>
  );
}
