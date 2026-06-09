# NEXLY RN – Design Specifications (Phase 2: Fast-Follow)

*Developer handoff for post-MVP Fast-Follow components deferred from `project/specs/mvp/design.md`. Scope maps to `project/specs/phase-2/prd.md` (shorthand expansion, definition-on-demand, full version history UI).*

**Important!** Design tokens, typography, spacing, primitives, and the base Study Tools Panel are inherited from the MVP design doc. The full Comparison Dialog (unified + side-by-side diff) is itself **Phase 2** — its diff behavior is owned by `project/specs/phase-2/prd.md`. Only the deferred pieces are specified here. These components already exist in the prototype code but must not be wired until Phase 2.

## 1. Shorthand Expansion (Week 5-6)

**`Shorthand` inline annotation** (Study Mode article)
- `cursor-pointer rounded border-b-2 border-dotted border-primary-brand bg-blue-500/15 px-1 font-medium hover:bg-blue-500/25`
- Clicking opens `ExpansionPreviewDialog` with original/expanded copy from `shorthandExpansions`
- Inline JSX, not a Tiptap mark (the study article is hand-authored HTML)

**Expansion Preview Dialog** (`ExpansionPreviewDialog`)
- Radix `Dialog`, `sm:max-w-xl`
- Title: "Shorthand Expansion Preview"
- Two-column grid (`grid-cols-2 gap-4 pt-2`): Original (Shorthand) | Expanded (Full Terms)
- Each column: `text-sm font-semibold text-custom-muted-foreground` label + `bg-custom-accent rounded-lg p-4 text-sm leading-relaxed` block
- Footer (`flex justify-end gap-3 pt-2`): outline `Cancel`, primary-brand `Accept & Apply` with `Check` icon

**Study Tools refinement action**
- Expand Shortcuts: `ActionButton` with `Wand2` icon, quota badge `7/10`

## 2. Definition-on-Demand (Week 5-6)

**Definition Popup** (`DefinitionPopup`)
- Radix `Popover` (click-to-pin pattern; the hover `Tooltip` variant on `MedicalTerm` ships in the MVP — see Term Definition Tooltip in `project/specs/mvp/design.md`)
- Content width `400px`, `p-4`, aligned `start`
- Term: `text-lg` semibold foreground (`mb-2`)
- Definition: `text-sm leading-relaxed text-custom-foreground` (`mb-3`)
- Clinical example: `text-sm italic text-custom-muted-foreground` prefixed `Example:` (`mb-3`)
- Footer: validation pill — `text-emerald-500` `CheckCircle` ("Educator Validated") or `text-amber-500` `AlertCircle` ("Unvalidated") — plus a `Bookmark` icon button (`h-7 w-7`)

**Study Tools refinement action**
- Clarify Text: `ActionButton` with `Lightbulb` icon, quota badge `9/10`

*The **Refinement** section (uppercase muted heading) sits at the top of the Study Tools Panel, above Smart Summary, when these two actions are wired. `ActionButton` pattern is inherited from the MVP doc.*

## 3. Full Version History UI – Side-by-Side Diff (Week 7-8)

*The Comparison Dialog is new in Phase 2: unified diff is the base view; this section adds the side-by-side toggle.*

**View toggle**
- `ToggleGroup` on `bg-custom-accent rounded-lg p-1` with two items: `Columns` "Side-by-Side" and `AlignLeft` "Unified"

**Side-by-Side view**
- 2-column grid; each side has a header bar (`bg-custom-muted` with `File` / `FileCheck` icon + label) and a `ScrollArea max-h-[400px] p-5 text-base leading-[1.8]`
- Deletions: `<mark>` `bg-red-500/15 text-red-500 line-through`
- Additions: `<mark>` `bg-emerald-500/15 text-emerald-500`

## 4. Data Sources

**`src/lib/dictionary/medical-data.ts`**
- `shorthandExpansions` — 9 abbreviations (`VS`, `BP`, `HR`, `RR`, `ECG`, `PO`, `O2`, `SL`, `PRN`); consumed by the `Shorthand` annotation and `ExpansionPreviewDialog`
- `MedicalDefinition` stays defined in the MVP doc (shared with the MVP `MedicalTerm` hover tooltip); `DefinitionPopup` reuses it

## 5. Icons (Phase 2 only)

- Shorthand / refinement: `Wand2`, `Lightbulb`
- Side-by-side diff: `Columns`, `File`, `FileCheck`
- *`AlignLeft` labels the Unified toggle — the base diff view*

## 6. Custom Components (deferred)

- `src/components/study/`: `DefinitionPopup`, `ExpansionPreviewDialog`
- Side-by-side machinery lives inside `ComparisonDialog` — the whole component is Phase 2 (unified-diff base + side-by-side toggle)
