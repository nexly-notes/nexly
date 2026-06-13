# NEXLY RN – Design Specifications

_Design specification for the NEXLY RN desktop/web experience._ Defines every screen, component, visual token, and interaction pattern from a design perspective. This document describes intended look and behavior only — it does not cover implementation.

**Important!** All modes share a single blue brand accent. Create and Edit (both editable; the PRD's capture and revision modes) and read-only Study are differentiated by layout, badges, and contextual UI — never by accent color.

**Important! Scope:** This is the three-mode MVP design (Create + Edit + Study). Create and Edit are both editable and behave identically for now (Edit gains revision-specific tooling later); Study is the read-only key-term lens. Only Edit's revision tooling — the Comparison/inline-diff dialog and version history — plus Smart Summary, paid-tier/Subscription UI, and nursing templates are **Phase 2** (see `phase-2/prd.md`) and are called out where they would have appeared.

**Important! Build contract:** the PRD's FR set gates the MVP. Favorites, tags, folders, and archive appear in this spec but are non-gating stretch scope for the beta.

## 1. Design System Foundation

### Color Palette

**Brand Colors**

- Primary Brand: `#3ba9ff` — accents, CTAs, focus states, links, validated states
- Secondary Brand: `#2a8fd9` — hover state on brand buttons, also the info color
- Tertiary Brand: `#1e1e1e` — reserved for high-contrast contexts

**Surface & Text Tokens** (light / dark)

- Background: `#ffffff` / `#0b0b0c`
- Surface (accent): `#f5f5f5` / `#141414`
- Muted: `#e6e3e3` / `#1b1a1a`
- Foreground: `#1a1a1a` / `#e0e0e0`
- Muted Foreground: `#6b6b6b` / `#a0a0a0`
- Border: `#ededed` / `#1f1f1f`
- Focus Ring: `#ebebeb` (dark inherits)
- Highlight: `#fef3c7`
- Shadow: `rgba(0,0,0,0.1)` / `rgba(0,0,0,0.5)`
- Shadow (large): `rgba(0,0,0,0.15)` / `rgba(0,0,0,0.7)`

**Semantic Colors**

- Success / Validated: `#10b981` — success and validated states (_diff additions and educator-validated definitions are Phase 2_)
- Warning / Unsaved: `#f59e0b` — unsaved-changes badge, filled favorite, alert icon
- Error / Destructive: `#ef4444` — destructive menu items (_diff deletions are Phase 2_)
- Info: `#2a8fd9`

**Note Card Tag Variants**

- Purple `#8b5cf6` — Pharmacology
- Emerald `#10b981` — Anatomy
- Amber `#f59e0b` — Clinical

**Theming**

- Light and dark are full token sets; switching swaps the entire palette instantly.
- Brand blue is constant across light, dark, and all modes.

### Typography

**Font Stack**

- Default: `Inter`, with a system UI fallback stack
- Monospace: system mono stack — used for shortcut keys and tabular counts

**Editor Type Scale**

- Body: `18px`, line-height `1.6`, foreground color
- `H1`: `30px` bold, generous top/bottom margin
- `H2`: `24px` semibold
- `H3`: `20px` semibold
- Paragraph: bottom margin `12px`
- Lists: left indent `24px`; list items `4px` spacing
- Blockquote: `3px` left border in brand, italic, muted foreground
- Inline code: muted surface background, mono, small
- Code block: muted surface, rounded, padded, horizontal scroll
- Link: brand color, underlined
- Placeholder: muted foreground, half opacity on focus
- Modern layout title: `36px` bold, "Untitled" placeholder

**UI Type Scale**

- Page title: `20px` semibold
- Section heading: `18px` semibold
- Card title: `16px` semibold, clamped to 2 lines
- Body / list rows: `14px`
- Metadata / status bar: `12px`
- Panel section labels: `12px` uppercase semibold, muted foreground
- Shortcut keys: `10px` mono
- Settings sub-labels: `10px` muted foreground

### Spacing System

- Base unit: `4px`
- Sidebar internal padding: `12px / 8px`
- Header padding: `16px / 12px` (editor), `24px / 16px` (note list, dialogs)
- Card padding: `16px`
- Editor canvas padding: classic `32px / 24px`; modern title `40px / 48px / 8px`; modern body `40px / 40px`
- Toolbar padding: `16px / 6px`
- Popover / dialog content padding: `16px`
- Study Tools sections: `24px` vertical rhythm, `16px` padding

### Border Radius

- Small `6px` — buttons, toolbar items, nav rows, key chips
- Medium `8px` — cards, panels, action buttons, dialog inner blocks
- Large `12px` — modern floating menu panel
- Full — avatars, tag dots, tag pills, badge counters

### Elevation

- Card hover: medium shadow
- Floating menu / popovers: large shadow
- Sidebar floating trigger: small shadow
- Shadow opacity deepens in dark mode

## 2. Component Specifications

### Note List Sidebar

- Fixed width `280px`, full height, right border; hidden entirely when collapsed
- Vertical stack: logo → Quick Create → search → scroll area (nav + tags + folders) → footer
- Logo: `32px` brand-blue square with letter "N" plus "NEXLY RN" wordmark
- Quick Create: full-width brand button with plus icon, label "New"
- Search: input with leading search icon
- Navigation: All Notes (12), Favorites (3), Recent, Archive — icon + label + optional counter badge
- Tags: uppercase header with add button; rows show `10px` colored dot, label, count
- Folders: uppercase header with add button; rows show folder icon + label
- Footer (sticky): theme toggle row (sun/moon + label) and profile row (`32px` avatar, name, role, settings trigger)
- Active row: surface background, foreground text, medium weight; inactive rows muted with same hover
- Sections separated by inset dividers
- Search filters notes by case-insensitive match on title only (MVP scope per FR-007; preview-text search is deferred)
- Theme toggle cycles light ↔ dark; `system` is reachable via Settings

### Note List Page

- Two-column shell: sidebar (left) + main column (right)
- Header: collapse button, page title "All Notes", view toggle, sort selector
- Grid view: 1 → 4 columns responsive, `16px` gap
- List view: single column, `12px` gap
- Empty state: centered "No notes found" + "Try adjusting your search query" in muted foreground
- View toggle: grid / list, `32px` segmented control inside a bordered group
- Sort options: Recently Modified, Date Created, Title A-Z, Title Z-A
- Clicking a card opens the note in Create Mode (the user's Default Mode); no open dialog
- Quick Create opens a new blank note

### Note Card

- Rounded medium, bordered, background surface, hover raises medium shadow
- Header: tag chip pill (colored dot + label on surface pill) and overflow button revealed on hover
- Title: `16px` semibold, clamped to 2 lines
- Preview: `14px` relaxed leading, muted, clamped to 3 lines
- Footer: date with calendar icon (muted) and a favorite star button
- Favorite active: filled amber; inactive: muted outline
- Overflow menu (MVP): Open, Delete (Delete in destructive color); _Duplicate and Export (PDF/DOCX) are Phase 2 — the MVP overflow menu is Open + Delete only_

### Quick Create

- The "New" button creates a blank note and opens it directly in Create Mode
- _The template picker (2×2 grid: SOAP Note, Drug Card, Care Plan) is Phase 2 — the MVP creates blank notes only_

### Mode Toggle

- A mode control in the editor header cycles the active mode in place (Create → Edit → Study → Create) — there is no mode-choice dialog on open
- Notes open in the user's Default Mode (Create unless changed in Preferences)
- The control shows the next mode in the cycle with its icon: Create advances to Edit (edit icon), Edit advances to Study (book icon), Study advances back to Create (edit icon)
- Keyboard: `Ctrl+M` cycles to the next mode; transition completes in <50ms

### Editor Header (Classic Layout)

- Bottom border, background, horizontal padding; non-fixed height
- Left: home icon button
- Center: inline editable title — placeholder "Untitled Note", brand border on focus, muted border on hover, truncates
- Adjacent: "Add tag" chip pill — brand border and text on hover
- Right cluster: mode cycle control, layout toggle, theme toggle, print, pin, more
- Layout toggle: switches Classic ↔ Modern shell, with tooltip "Switch to Modern" / "Switch to Classic"
- Theme toggle: light ↔ dark; sun icon in dark, moon icon in light

### Editor Toolbar (Classic Layout)

- Bar below header on surface background
- Undo / Redo lead as plain buttons reflecting availability
- Single segmented group of icon buttons with thin separators between every item; trailing "more" button outside the group
- Items: undo, redo, bold, italic, underline, strikethrough, highlighter, code, link, list, ordered list, checklist, align left, align center, align right, image, table, quote, more
- Button: `32px` square, small radius; idle muted; hover surface + foreground; active brand-tinted background + brand icon
- Link / Image prompt for a URL; Table inserts a 3×3 grid with header row
- **Important!** Formatting applied inside the modern inline title still works through the toolbar

### Editor Header (Modern Layout) — Floating Menu

_MVP/beta scope: the Modern shell, its Classic/Modern layout toggle, and the selection-bubble toolbar are designed but deferred to a post-beta fast-follow; the beta ships classic-only._

- Replaces header and toolbar with a floating left-edge menu
- Collapsed: small menu pill at left-center, `36px` square, large radius, bordered, subtle shadow
- Expanded: vertical icon column inside a large-radius bordered panel with large shadow and a full-viewport click-to-close backdrop
- Open animation: fade + slide-in from left, `200ms`
- Items (separated): close → Home → Mode Cycle → Add Tag → Switch to Classic → Theme → Print → Pin → More
- Each button is a ghost icon button with a right-aligned tooltip

### Editor Canvas

- Classic: centered column max `900px`, inner padding `32px / 24px`
- Modern: centered column max `800px`, inline title rendered above the body
- Scrollable content region fills available height
- Body text `18px`, line-height `1.6`; focus outline removed; text cursor inside content
- Placeholder "Start writing..." in muted foreground, half opacity on focus
- Supported content: headings, bold, italic, underline, highlight, text alignment, links, images, resizable tables, bullet/ordered/check lists, blockquote, code

### Modern Title

- Inline editable title at the top of the canvas, `36px` bold, padded `40px / 48px / 8px`
- Placeholder "Untitled"
- Enter moves focus into the editor body
- Clearing the title restores the placeholder

### Selection Bubble

- Appears when a text selection falls inside the editor
- Debounce: `120ms` (classic), `500ms` (minimalist)
- Positioned `80px` above the selection; flips to `8px` below when there is no room above
- Content: the full editor toolbar inside a rounded padded container
- Animation: scale `0.5 → 1` with fade, spring curve, `0.2s`
- Dismisses on outside click, `Escape`, or selection collapse
- Clicking toolbar buttons does not clear the selection

### Ghost Text Autocomplete

- Active in Create & Edit when enabled (never in Study)
- Local-first: local nursing-term completion is the instant primary path (<100ms); AI phrase ghost-text appears after a `150ms` typing pause when available (else suppressed)
- Requires at least 2 characters and a word boundary after the cursor
- `Tab` accepts the completion plus a trailing space; `Escape` clears it
- Styling: muted gray, low opacity (`0.45` light, `0.4` dark), non-interactive, inline, `150ms` fade-in — visually distinct from typed text

### Status Bar

- Used in classic Create, Edit, and Study modes
- Top border, small padding, `12px` muted text
- Left: words count, characters count, optional key-term count with bookmark icon, optional "Unsaved changes" with amber alert icon
- Right: "Auto-saved" when saved and clean, then mode label with check icon
- Mode labels: "Create Mode", "Edit Mode", "Study Mode"
- Numbers are locale-formatted

### Study Mode Page

- Two-column shell: read-only article (left) + Study Tools Panel (right, `320px`)
- Header: home button, plain note title, badge cluster ("Study Mode" + topic, e.g. "Cardiology"), actions (mode cycle control, theme, print, more)
- The mode cycle control advances Study back to Create Mode
- Body: scrollable article, max `900px`, `18px` text, `1.6` leading
- Footer: status bar in Study mode with key-term count

**Inline Annotations**

- Medical term: dotted brand underline, brand text, medium weight; hover opens the Term Definition Tooltip
- Annotations are inline within the read-only article
- _Shorthand annotation (click → Expansion Preview) is Phase 2._

**Term Definition Tooltip** (MVP)

- Trigger: hovering a spotted medical term; `200ms` delay (shared tooltip timing)
- Floating surface card, rounded, subtle border + shadow, compact padding, anchored above/near the term
- Content: term in semibold foreground, then a short definition snippet in smaller muted text
- Source: local nursing-terms dictionary (`MedicalDefinition`) — no AI call, no quota
- _No clinical example, validation pill, or bookmark — those belong to the Phase 2 click-to-pin `DefinitionPopup`_
- Reference: `project/ui-images/study-mode/hover-definition.png`

### Study Tools Panel

- Right sidebar, `320px`, left border, conditionally shown
- Header: sparkles icon + "Study Tools" title, close button
- Scrollable body with `24px` section rhythm; each section has an uppercase muted heading
  1. **Key Terms Spotted**: tappable rows (click-to-jump to the term in the article); hover adds a brand left border and lifts the background; each row carries a small helpful/not-helpful feedback affordance (logs a usage event); a "Copy terms" action copies the list to the clipboard
  2. **Exam-Relevant**: count line ("3 exam-relevant items highlighted") derived from the spotting emphasis cues
- On long notes, key terms populate progressively (chunked spotting); notes beyond ~12,000 words show a truncation notice (terms cover the first ~12,000 words)
- **AI-paused state**: when the daily runaway backstop trips, the panel shows a non-blocking notice ("AI assist is paused until tomorrow"); the local term-definition hover and all editing remain available
- _Smart Summary ("Key Takeaways" + Regenerate) and the Refinement section (Expand Shortcuts, Clarify Text) are Phase 2._
- Action button pattern: bordered medium-radius row with muted icon, left-aligned label, surface hover

### Edit Mode Revision Tooling & Comparison Dialog (Phase 2)

- _Edit ships in the MVP as an editable mode identical to Create — the same classic shell, toolbar, autocomplete, and status bar. Only its revision-specific tooling is deferred: the unified inline-diff "Compare Changes" dialog and version history are Phase 2 (see `phase-2/prd.md`)._
- _In the MVP, Edit has no inline diff or compare/revert view; it is simply a second editable surface alongside Create._

### Settings Drawer

- Trigger: gear icon in the sidebar footer next to the profile
- Opens a popover anchored above-start, min width `240px`

**Menu**

- Title bar "Settings"
- Items: Profile ("Name, email, avatar"), Preferences ("Theme, auto-save, defaults"), Keyboard Shortcuts ("Customize key bindings")
- Each row: icon tile, label, description; full-row surface hover
- Closing resets to the menu
- _Subscription (plan & billing) is Phase 2._

**Sub-page Wrapper**

- Max height `420px`, column layout
- Header: back arrow + page title; scrollable content with `16px` padding

**Profile**

- `64px` circular brand avatar with initials and a camera overlay button
- Field rows: Full Name, Email, Institution, Program
- Footer: solid brand "Save Changes" button

**Preferences**

- Theme picker: 3 tiles (light / dark / system); active uses brand border + tint
- Toggle rows: Spell Check, Word Count — default on
- Auto-save: locked-on, display-only status row (always enabled; cannot be turned off, per NFR-002's while-connected no-data-loss guarantee and local crash-recovery copy) — not a user-disableable toggle
- Default Mode picker: Create / Edit / Study tiles

**Shortcuts**

- Static list of action/key rows with surface hover; keys rendered in mono key chips
- Bold `Ctrl+B`, Italic `Ctrl+I`, Underline `Ctrl+U`, Undo `Ctrl+Z`, Redo `Ctrl+Shift+Z`, Save `Ctrl+S`, Search `Ctrl+F`, New Note `Ctrl+N`, Toggle Mode `Ctrl+M`, Accept Suggestion `Tab`, Dismiss Suggestion `Esc`, Heading 1 `Ctrl+Alt+1`, Heading 2 `Ctrl+Alt+2`, Bullet List `Ctrl+Shift+8`, Numbered List `Ctrl+Shift+7`

**Subscription (Phase 2)**

- _Tier cards and billing are deferred to Phase 2; not shown in the MVP._

### Post-MVP Components (Phase 2)

_The click-to-pin Definition-on-demand popup, the shorthand Expansion Preview dialog, Edit Mode's Comparison/inline-diff dialog and version history (the editable Edit mode itself is in the MVP), the Smart Summary block, the template picker, and the Subscription/tier UI are designed-for or deferred to Phase 2. The term hover tooltip (see Term Definition Tooltip under Inline Annotations) is in MVP._

## 3. User Flow Screens

### Note List → Note Editor

1. User lands on the note list
2. Sidebar exposes navigation, search, tags, folders, theme toggle, settings
3. Tapping a card opens the note in Create Mode (the user's Default Mode)
4. The mode cycle control (or `Ctrl+M`) advances modes in place (Create → Edit → Study)
5. Quick Create makes a blank note and opens the Create editor

### Note Editor (Create / Edit)

**Classic Shell**

- Header → toolbar → centered editor → status bar
- Ghost-text autocomplete active (local-first)
- Title edited inline in the header; toolbar acts on both body and title
- Header tag chip opens tag entry
- The mode cycle control in the header advances to the next mode (Create → Edit → Study)
- Create and Edit share this shell and behave identically for now (Edit's revision tooling is Phase 2)

**Modern Shell**

- Floating left menu replaces the header and toolbar
- Inline `36px` title above the editor; Enter focuses the body
- Editor fills the centered column; clicking the outer gutter blurs the editor
- Toolbar appears only as a floating bubble after a text selection
- Status bar is hidden in the Modern shell

### Study Mode

- Read-only article surface
- Inline annotations make terms interactive on hover
- Study Tools Panel provides spotted key terms and exam-relevant count (starts open)
- Header mode cycle control advances back to Create Mode
- Status bar shows Study mode with key-term count

### Sign-Up (stub)

- Email/password form (Supabase Auth); detailed visual design TBD using the tokens in this document
- Account creation requires accepting the beta ToS — didactic lecture notes only; entering patient-identifying information (PHI) is prohibited
- The ToS gate lives at sign-up so contextual onboarding stays non-blocking (FR-008)

### Onboarding

- Contextual onboarding tooltips introduce the three modes (Create, Edit, Study) on first use; dismissable and non-blocking (no 2-screen flow)
- Applies the tokens and components defined in this document

## 4. Interaction Patterns

### Selection Bubble

- Debounce: `120ms` (classic), `500ms` (minimalist)
- Offset: `80px` above the selection; flips to `8px` below when there is no room above
- Dismisses on outside click, `Escape`, or selection collapse
- Spring entrance: scale `0.5 → 1` with fade over `0.2s`

### Ghost-Text Autocomplete

- Local nursing-term completion is the instant primary path; AI phrase ghost-text is triggered after a `150ms` typing pause when available
- Requires at least 2 characters and a word boundary right after the caret
- `Tab` accepts the suggestion plus a trailing space; `Escape` clears it
- Suppressed automatically outside Create & Edit

### Note Card Interactions

- Hover reveals the overflow menu and raises a medium shadow
- Favorite star toggles between muted outline and filled amber
- Card click opens the note in Create Mode; the overflow button and star do not trigger the card click

### Mode Differentiation

- Brand color stays constant across modes (intentional)
- Create/Edit vs Study is communicated through:
  1. Layout and shell (editable canvas vs read-only article)
  2. Header badge in Study ("Study Mode" + topic)
  3. Status bar label and icon ("Create Mode" / "Edit Mode" / "Study Mode")
  4. Availability of inline annotations and the Study Tools Panel (Study only)
  5. The mode cycle control in the header

## 5. Accessibility

- Buttons expose accessible labels via tooltip wrappers and per-action labels
- Tooltips use a `200ms` delay and consistent placement (right side for the floating menu)
- Inline annotations use a help cursor for terms
- Editable title and body expose a textbox role with named labels
- Focus uses the theme focus ring and a brand border for the editable title
- Keyboard support: Tab / Escape for autocomplete, Enter to leave the modern title, standard formatting shortcuts
- _Important!_ The Modern Floating Menu backdrop has no focus trap — revisit if more menu items are added

## 6. Responsive Behavior

_Important!_ The product is desktop-first. Mobile layouts are not yet designed.

- Note grid scales from 1 to 4 columns at breakpoints `640px`, `1024px`, `1280px`
- Sidebar fixed at `280px`, collapsible entirely via the header button
- Editor column max widths: `900px` (classic), `800px` (modern)
- Study Tools Panel fixed `320px` on desktop, dismissible via its close button

## 7. Animation Specifications

- Ghost text fade-in: `150ms` ease-out, target opacity `0.45` light / `0.4` dark
- Selection bubble: scale `0.5 → 1`, fade, spring curve, `0.2s`
- Modern menu open: fade + slide-in from left, `200ms`
- Note card overflow / favorite reveal: opacity + transform transition
- Hover state changes: color transition
- Theme switch: instant token swap, no tween

## 8. Icon System

**Library**: `Lucide` icon set.

**Recurring Icons (by role)**

- Navigation: home, panel collapse, panel layout, menu
- Editor actions: bold, italic, underline, strikethrough, highlighter, code, quote, undo, redo, link, image, table, bullet list, ordered list, checklist, align left/center/right, plus, more
- Sidebar nav: document, star, clock, archive, folder, search
- Status / validation: check circle, alert circle, star, calendar, bookmark
- Study tools: sparkles, book, copy
- Mode cycle: book (to Study), edit (to Create / Edit)
- Theme: sun, moon, monitor
- Settings: gear, sliders, keyboard, camera, user
- Editor header extras: printer, pin, more, edit
- General: check, close, chevron, grid, list
- _Phase 2 — Comparison Dialog: compare, add circle, minus circle, percent, revert, save_

**Sizing Conventions**

- `12px` – `14px`: inline metadata, tiny chips, sidebar header plus buttons
- `16px`: default action and menu icons
- `20px`: emphasized header icons (sidebar collapse)
- `24px`: Quick Create tile icons
