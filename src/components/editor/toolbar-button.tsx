"use client";

import type { LucideIcon } from "lucide-react";

type ToolbarButtonProps = {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  isActive?: boolean;
  isDisabled?: boolean;
};

export function ToolbarButton({
  icon: Icon,
  label,
  onClick,
  isActive = false,
  isDisabled = false,
}: ToolbarButtonProps) {
  const stateClasses = isActive
    ? "bg-brand/15 text-brand"
    : "text-muted-foreground hover:bg-surface hover:text-foreground";

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={isActive}
      title={label}
      disabled={isDisabled}
      onClick={onClick}
      className={`flex size-8 items-center justify-center rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${stateClasses}`}
    >
      <Icon size={16} aria-hidden />
    </button>
  );
}
