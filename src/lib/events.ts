import { createClient } from "@/lib/supabase/client";

const EVENTS_TABLE = "events";

// Optional context for an event. Per tech-specs the `events` table carries
// metadata only — never note content: `value` is a numeric count (accepted
// characters, duration ms) and `note_id` references the note an event is about.
export type EventDetails = {
  noteId?: string;
  value?: number;
};

type EventRow = {
  type: string;
  note_id?: string;
  value?: number;
};

/**
 * Records a lightweight analytics/telemetry event for the current user.
 *
 * Fire-and-forget by design: it never blocks the caller and never throws —
 * any failure (network, RLS, malformed response) is swallowed so telemetry can
 * never break a user-facing flow. The row carries only an event `type`, an
 * optional numeric `value`, and an optional `note_id`; never any note content.
 */
export function logEvent(type: string, details: EventDetails = {}): void {
  try {
    const supabase = createClient();
    const row: EventRow = { type };
    if (details.noteId !== undefined) {
      row.note_id = details.noteId;
    }
    if (details.value !== undefined) {
      row.value = details.value;
    }

    // Coerce to a promise so a synchronous/awaitable response is handled the
    // same way, then swallow rejections to keep this fire-and-forget.
    Promise.resolve(supabase.from(EVENTS_TABLE).insert(row)).catch(() => {});
  } catch {
    // Swallow synchronous failures (e.g. client construction) too.
  }
}
