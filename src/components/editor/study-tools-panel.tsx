"use client";

import { Sparkles, X } from "lucide-react";
import { useState } from "react";

export function StudyToolsPanel() {
  const [isOpen, setIsOpen] = useState(true);

  if (!isOpen) {
    return null;
  }

  return (
    <aside
      data-testid="study-tools-panel"
      aria-label="Study Tools"
      className="flex w-80 shrink-0 flex-col border-l border-border bg-background"
    >
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Sparkles size={16} className="text-brand" aria-hidden />
        <h2 className="text-sm font-semibold">Study Tools</h2>
        <button
          type="button"
          aria-label="Close Study Tools"
          onClick={() => setIsOpen(false)}
          className="ml-auto rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
        >
          <X size={16} aria-hidden />
        </button>
      </div>
      <div className="flex-1 space-y-6 overflow-y-auto p-4">
        <section>
          <h3 className="text-xs font-semibold uppercase text-muted-foreground">
            Key Terms Spotted
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            AI key-term spotting will appear here.
          </p>
        </section>
        <section>
          <h3 className="text-xs font-semibold uppercase text-muted-foreground">
            Exam-Relevant
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Emphasis cues from your note will be counted here.
          </p>
        </section>
      </div>
    </aside>
  );
}
