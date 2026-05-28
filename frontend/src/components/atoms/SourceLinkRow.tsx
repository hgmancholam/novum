/**
 * SourceLinkRow atom — clickable source citation with favicon, title, and hostname.
 * IP-24 Phase 1.
 */

import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";

export interface SourceLinkRowProps {
  url: string;
  title: string;
  sourceType?: "tavily" | "wikipedia" | undefined;
  className?: string | undefined;
}

function extractHostname(url: string): string {
  try {
    const hostname = new URL(url).hostname;
    return hostname.replace(/^www\./, "");
  } catch {
    return "unknown";
  }
}

export function SourceLinkRow({
  url,
  title,
  sourceType,
  className,
}: SourceLinkRowProps) {
  const hostname = extractHostname(url);
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${hostname}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      data-source-type={sourceType}
      className={cn(
        "flex items-center gap-2 py-1.5 px-2 rounded-md",
        "hover:bg-[var(--glass-hover)] transition-colors",
        "text-sm group",
        className
      )}
    >
      <img
        src={faviconUrl}
        alt=""
        width={16}
        height={16}
        className="flex-shrink-0"
        onError={(e) => {
          // Fallback to Globe icon on favicon load error
          e.currentTarget.style.display = "none";
          const parent = e.currentTarget.parentElement;
          if (parent && !parent.querySelector('[data-fallback-icon]')) {
            const icon = document.createElement("div");
            icon.setAttribute("data-fallback-icon", "true");
            icon.className = "flex-shrink-0 text-[var(--text-muted)]";
            icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path><path d="M2 12h20"></path></svg>`;
            parent.insertBefore(icon, e.currentTarget);
          }
        }}
      />
      <span className="flex-1 truncate text-[var(--text-primary)] group-hover:text-[var(--accent)]">
        {title}
      </span>
      <span className="flex items-center gap-1 text-xs text-[var(--text-muted)] flex-shrink-0">
        {hostname}
        <ExternalLink aria-hidden="true" width={12} height={12} />
      </span>
    </a>
  );
}
