/**
 * SearchStepCard molecule — grouped ToolCalled + EvidenceAdded display.
 * IP-24 Phase 2.
 */

import { useState } from "react";
import { motion } from "motion/react";
import { FeedStep } from "./FeedStep";
import { SourceLinkRow, Badge, CollapseToggleButton } from "@/components/atoms";
import { FEED_SEARCHED_WEB, FEED_RESULTS_COUNT } from "@/lib/microcopy";
import { cn } from "@/lib/cn";

export interface SearchSource {
  url: string;
  title: string;
  sourceType?: "tavily" | "wikipedia" | undefined;
}

export interface SearchStepCardProps {
  query: string;
  sources: readonly SearchSource[];
  isActive?: boolean | undefined;
  deltaMs?: number | undefined;
  className?: string | undefined;
}

export function SearchStepCard({
  query,
  sources,
  isActive = false,
  deltaMs,
  className,
}: SearchStepCardProps) {
  const autoCollapse = sources.length > 3;
  const [isCollapsed, setIsCollapsed] = useState(autoCollapse);

  return (
    <FeedStep
      type="ToolCalled"
      title={FEED_SEARCHED_WEB}
      isActive={isActive}
      deltaMs={deltaMs}
      className={className}
    >
      <div className="flex items-center gap-2 mb-2">
        <Badge variant="info" className="text-xs">
          "{query}"
        </Badge>
        <span className="text-xs text-[var(--text-muted)]">
          {FEED_RESULTS_COUNT(sources.length)}
        </span>
      </div>

      {sources.length > 0 ? (
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-[var(--text-muted)]">Fuentes</span>
            {autoCollapse ? (
              <CollapseToggleButton
                isCollapsed={isCollapsed}
                onToggle={() => {
                  setIsCollapsed(!isCollapsed);
                }}
                labelCollapse="Ocultar fuentes"
                labelExpand="Mostrar fuentes"
              />
            ) : null}
          </div>
          {!isCollapsed ? (
            <ul className={cn("flex flex-col gap-0.5")}>
              {sources.map((src, idx) => (
                <motion.li
                  key={`${src.url}-${idx.toString()}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    duration: 0.25,
                    delay: idx * 0.08,
                    ease: "easeOut",
                  }}
                >
                  <SourceLinkRow
                    url={src.url}
                    title={src.title}
                    sourceType={src.sourceType}
                  />
                </motion.li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </FeedStep>
  );
}
