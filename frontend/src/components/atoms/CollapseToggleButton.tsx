/**
 * CollapseToggleButton atom — animated chevron button for expand/collapse.
 * IP-24 Phase 1.
 */

import { ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";

export interface CollapseToggleButtonProps {
  isCollapsed: boolean;
  onToggle: () => void;
  labelCollapse: string;
  labelExpand: string;
  className?: string | undefined;
}

export function CollapseToggleButton({
  isCollapsed,
  onToggle,
  labelCollapse,
  labelExpand,
  className,
}: CollapseToggleButtonProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={!isCollapsed}
      aria-label={isCollapsed ? labelExpand : labelCollapse}
      className={cn(
        "flex items-center justify-center",
        "w-6 h-6 rounded-md",
        "text-[var(--text-muted)] hover:text-[var(--text-primary)]",
        "hover:bg-[var(--glass-hover)]",
        "transition-colors",
        className
      )}
    >
      <motion.div
        animate={{ rotate: isCollapsed ? 0 : 90 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <ChevronRight aria-hidden="true" width={16} height={16} />
      </motion.div>
    </button>
  );
}
