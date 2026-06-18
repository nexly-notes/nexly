# NEXLY RN – Design Specifications

*Developer handoff document.* Captures every screen, component, interaction, design token, data shape, route, and known gap in the prototype. Code is the source of truth; this file should match it.

**Important!** Project is a **React 19 + Vite + TypeScript** browser SPA. No React Native, no Tauri, no mobile build. Tiptap v3 powers the editor.

## 1. Design System Foundation

### Color Palette

**Brand Colors**
- Primary Brand: `#3ba9ff` (accents, CTAs, focus states, links, validated states inherit through `custom-success`)
- Secondary Brand: `#2a8fd9` (hover state on brand buttons, also used as `--custom-info`)
- Tertiary Brand: `#1e1e1e` (reserved for high-contrast contexts)

*Important!* Single blue brand palette is shared across Lecture and Study Mode. Modes are differentiated by layout, badges, and contextual UI — not by accent color.

**Light Mode Tokens** (`:root`)
- `--custom-background`: `#ffffff`
- `--custom-accent`: `#f5f5f5`
- `--custom-muted`: `#e6e3e3`
- `--custom-foreground`: `#1a1a1a`
- `--custom-accent-foreground`: `#1a1a1a`
- `--custom-muted-foreground`: `#6b6b6b`
- `--custom-border`: `#ededed`
- `--custom-ring`: `#ebebeb`
- `--custom-warning`: `#ff4d4d`
- `--custom-success`: `#3ba9ff`
- `--custom-info`: `#2a8fd9`
- `--highlight-color`: `#fef3c7`
- `--shadow`: `rgba(0,0,0,0.1)`
- `--shadow-lg`: `rgba(0,0,0,0.15)`

**Dark Mode Tokens** (`.dark`)
- `--custom-background`: `#0b0b0c`
- `--custom-accent`: `#141414`
- `--custom-muted`: `#1b1a1a`
- `--custom-foreground`: `#e0e0e0`
- `--custom-muted-foreground`: `#a0a0a0`
- `--custom-border`: `#1f1f1f`
- `--shadow`: `rgba(0,0,0,0.5)`
- `--shadow-lg`: `rgba(0,0,0,0.7)`

**Semantic Colors**
- Success / Validated: `emerald-500` (educator-validated definitions, additions in diff)
- Warning / Unsaved: `amber-500` (unsaved changes badge, unvalidated definitions, favorite filled state, alert icon)
- Error / Deletions: `red-500` (diff deletions); destructive Dropdown items use `text-destructive` shadcn token
- Info: `--custom-info` `#2a8fd9`

**Note Card Tag Variants** (mapped in `TAG_VARIANT_STYLES`)
- `purple`: `bg-purple-500` (Pharmacology)
- `success`: `bg-emerald-500` (Anatomy)
- `warning`: `bg-amber-500` (Clinical)

**Tailwind v4 Theme Hookup**
- All `--custom-*` and brand vars are exposed as Tailwind utilities via `@theme inline` in `src/custom-styles.css` (e.g. `bg-custom-background`, `text-primary-brand`, `border-custom-border`).
- Light/dark switched by adding `light`/`dark` class to `<html>` from `ThemeProvider`.

### Typography

**Font Stack**
- Default: system UI stack (no custom web font loaded for MVP)
- Monospace: system mono stack (used for shortcut `kbd` and tabular counts)

**Editor Type Scale** (`.tiptap`, defined in `editor-content.css`)
- Base body: `font-size: 18px`, `line-height: 1.6`, color `--custom-foreground`
- `h1`: `text-3xl` bold, `mt-6 mb-4`
- `h2`: `text-2xl` semibold, `mt-5 mb-3`
- `h3`: `text-xl` semibold, `mt-4 mb-2`
- Paragraph: `mb-3`
- `ul`/`ol`: `pl-6 mb-3`; `li` `mb-1`
- Blockquote: `border-l-3 border-primary-brand pl-4 italic text-custom-muted-foreground my-3`
- Inline `code`: `bg-custom-accent rounded px-1.5 py-0.5 text-sm font-mono`
- Block `pre`: `bg-custom-accent rounded-lg p-4 my-3 overflow-x-auto`
- Link `a`: `text-primary-brand underline`
- Placeholder: `--custom-muted-foreground`, opacity 0.5 on focus
- Modern layout title: `text-4xl` bold, contenteditable, placeholder "Untitled" via `:empty::before`

**UI Type Scale**
- Page title (note list header): `text-xl` semibold
- Section heading (editor header title): `text-lg` semibold
- Card title: `text-base` semibold, `line-clamp-2`
- Body / list rows: `text-sm`
- Metadata / status bar / quota badges: `text-xs`
- Section labels in panels: `text-xs` uppercase semibold, muted foreground
- Shortcut keys: `text-[10px]` mono inside `kbd`
- Settings sub-labels: `text-[10px]` muted foreground

### Spacing System

**Base Unit**: `4px` (Tailwind default).

**Recurring Spacing**
- Sidebar internal padding: `px-3 py-2`
- Header padding: `px-4 py-3` (editor) and `px-6 py-4` (note list / dialog headers)
- Card padding: `p-4`
- Editor canvas padding: `px-8 py-6` (classic), `px-10 pt-12 pb-2` (modern title), `px-10 pb-10` (modern editor body)
- Toolbar padding: `px-4 py-1.5`
- Popover / dialog content padding: `p-4`
- Study Tools sections: `space-y-6 p-4`

### Border Radius

- Small `rounded-md` (`6px`): buttons, toolbar items, nav rows, kbd chips
- Medium `rounded-lg` (`8px`): cards, panels, action buttons, dialog inner blocks
- Large `rounded-xl` (`12px`): modern floating menu panel
- Full `rounded-full`: avatar, tag chip dot, tag chip pill, badge counters

### Elevation

- Card hover: `hover:shadow-md`
- Floating menu / popovers: `shadow-lg`
- Sidebar floating trigger: `shadow-sm`
- Custom shadow tokens: `--shadow` and `--shadow-lg` (alpha shifts between light/dark)

## 2. Component Specifications

### Note List Sidebar

**Layout**
- Fixed width `280px`, full height, right border `border-custom-border`
- Hidden entirely when `isCollapsed` (header `PanelLeft` toggle controls)
- Vertical stack: logo → Quick Create → Search → scroll area (nav + tags + folders) → footer (theme toggle + profile)

**Sections (top to bottom)**
- Logo: 32px square brand mark with letter "N" on `bg-primary-brand`, plus "NEXLY RN" wordmark in `text-base` semibold
- Quick Create button: full-width `bg-primary-brand` button with `Plus` icon and label "New"
- Search input: `Input` with `pl-8` and leading `Search` icon; controlled by `searchQuery`
- Navigation list (`navItems`): All Notes (12), Favorites (3), Recent, Archive — each row has icon + label + optional `Badge` counter on the right
- Tags section (`tagItems`): uppercase label header with `Plus` button; rows show 10px colored dot, label, count
- Folders section (`folderItems`): uppercase label header with `Plus` button; rows show `Folder` icon + label
- Footer (sticky, `shrink-0 border-t`): theme toggle row (Sun/Moon icon + "Light Mode"/"Dark Mode" label) and user profile row (8x8 circular avatar, name, role, `SettingsDrawer` trigger)

**Behavior**
- Active nav row: `bg-custom-accent text-custom-foreground font-medium`
- Inactive rows: `text-custom-muted-foreground`, same accent on hover
- Sections separated by `Separator mx-3 my-2`
- Search filters `noteCards` by case-insensitive substring on `title` or `preview` (memoized in `NoteListPage`)
- Theme toggle button cycles only between `light` and `dark`; `system` is reachable via Settings → Preferences

### Note List Page

**Layout**
- Two-column shell: `NoteListSidebar` (left) + main flex column (right)
- Header row: collapse `Button`, page title "All Notes", view toggle, sort `Select`
- Grid view: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`, `gap-4`
- List view: `flex-col` with `gap-3`
- Empty state: centered "No notes found" + "Try adjusting your search query" in muted foreground (`py-16`)

**Header Controls**
- View toggle: `ToggleGroup type="single"` wrapping `Grid3X3` and `List` inside `border border-custom-border rounded-md`, `h-8 w-8` items
- Sort: `Select` width `180px`, options from `sortOptions` (Recently Modified, Date Created, Title A-Z, Title Z-A) — *sort logic itself not yet wired*

**Click Behavior**
- Clicking a card opens `ModeSelectDialog` (does not auto-route)
- `Quick Create` button opens `QuickCreateDialog` (template picker)

### Note Card

- `rounded-lg border border-custom-border bg-custom-background p-4 transition-all hover:shadow-md`
- Header row: tag chip pill (colored dot + label on `bg-custom-accent px-2.5 py-1 rounded-full text-xs`) and overflow `MoreVertical` button (`h-7 w-7`) revealed via `opacity-0 group-hover:opacity-100`
- Title: `text-base` semibold, `line-clamp-2`, `mb-2`
- Preview: `text-sm leading-relaxed text-custom-muted-foreground line-clamp-3`, `mb-4`
- Footer row: date with `Calendar` icon (muted) and a favorite `Star` button (`h-7 w-7`)
- Favorite active state: `fill-amber-400 text-amber-400`; inactive: `text-custom-muted-foreground`
- Overflow `DropdownMenu` (align end): Open, Duplicate, Export, Delete (Delete uses `text-destructive`)

### Quick Create Dialog

- Radix `Dialog`, `sm:max-w-md`
- Title: "Quick Create"
- 2x2 grid (`grid-cols-2 gap-3`) of bordered tiles (`rounded-lg border p-6 flex-col items-center gap-3`)
- Hover changes border to `primary-brand` and adds `bg-custom-accent`
- Options (`createOptions`): Blank Note (`FileText`), SOAP Note (`Clipboard`), Drug Card (`Pill`), Care Plan (`Heart`)
- Icon size: `h-6 w-6` in `text-custom-muted-foreground`
- Selecting an option calls `onSelect(label)` and closes the dialog

### Mode Select Dialog

- Radix `Dialog`, `sm:max-w-sm`
- Title: "Choose Mode", description "Select how you want to open this note."
- Two side-by-side CTAs in `flex gap-3 pt-2`, each `flex-1 py-6 gap-2`
- Lecture Mode: outline button with `Presentation` icon
- Study Mode: solid primary-brand button with `BookOpen` icon (recommended path)

### Editor Header (Classic Layout)

**Layout**
- `border-b border-custom-border bg-custom-background px-4 py-3`, no fixed height, `shrink-0`
- Left: `Home` icon button that navigates to `/`
- Center: contenteditable title block (`min-w-[120px] max-w-[400px] truncate`, `text-lg` semibold, `border-transparent` becomes `border-primary-brand` on focus, hover `border-custom-border`), placeholder "Untitled Note", `role="textbox"`
- Adjacent: tag chip "Add tag" — pill `border-custom-border rounded-full px-3 py-1 text-xs`, hover gets `primary-brand` border and text
- Right action cluster (`gap-1`): layout toggle, theme toggle, print, pin, more

**Layout Toggle**
- Switches between Classic and Modern editor shells
- Icon: `Columns2` when currently classic (showing target Modern), `PanelTop` when currently modern
- Wrapped in `Tooltip` aligned default; tooltip text: "Switch to Modern" / "Switch to Classic"

**Theme Toggle**
- Local `useTheme()` from `theme-provider`; toggles only `light` ↔ `dark` (system reachable via Settings)
- Icon: `Sun` when dark, `Moon` when light

### Editor Toolbar (Classic Layout)

**Layout**
- Bar below header on `bg-custom-accent px-4 py-1.5 shrink-0` (see `toolbar.css`)
- Single `ToggleGroup type="single"` containing all icon buttons
- Undo/Redo render as plain `Button` (non-toggle) at the start with `disabled` reflecting `editor.can().undo/redo()`
- Vertical `Separator` rendered between every item (`mx-1.5 h-5`)
- Trailing `more` (`MoreHorizontal`) button outside the toggle group

**Items** (sourced from `toolbarIconsProps`)
- `undo`, `redo`, `bold`, `italic`, `underline`, `strikethrough`, `highlighter`, `code`, `link`, `list`, `listOrdered`, `listChecks`, `alignLeft`, `alignCenter`, `alignRight`, `image`, `table`, `quote`, `more`

**Button Style**
- Size: `h-8 w-8 rounded-md`
- Idle: `text-custom-muted-foreground`
- Hover: `bg-custom-muted text-custom-foreground`
- Active (`data-state="on"`): `bg-primary-brand/15 text-primary-brand`

**Actions Wired**
- All formatting and structural commands route through `editor.chain().focus().*().run()`
- Link / Image use `window.prompt` for URL
- Table inserts a 3x3 grid with header row
- **Important!** When selection is inside `.modern-title` (the contenteditable title), bold/italic/underline/strikethrough fall through to `document.execCommand` so the toolbar works on the title too (see `isSelectionInTitle` + `TITLE_EXEC_COMMANDS`)

### Editor Header (Modern Layout) — Modern Floating Menu

- Replaces the top header and toolbar with a floating left-edge menu (`ModernFloatingMenu`)
- Default state: small `Menu` icon pill at `fixed left-4 top-1/2`, `h-9 w-9 rounded-lg border bg-custom-background shadow-sm`
- Open state: vertical column of icon buttons inside `rounded-xl border bg-custom-background p-2 shadow-lg`, with full-viewport backdrop (`fixed inset-0 z-40`) for click-to-close
- Open animation: `animate-in fade-in slide-in-from-left-2 duration-200`
- Items (in order, separated by `Separator my-1`): close (`PanelLeftClose`) → Home → Add Tag → Switch to Classic (`PanelTop`) → Theme → Print → Pin → More
- Each button uses `MenuButton` primitive: `Button variant="ghost" size="icon" h-8 w-8` wrapped in `Tooltip` aligned `right` with `sideOffset 8` and `delayDuration 200`

### Tiptap Editor

**Container**
- Classic: `mx-auto w-full max-w-[900px]`, inner Tiptap padded `px-8 py-6`
- Modern: `mx-auto w-full max-w-[800px]`, inner Tiptap padded `px-10 pt-0 pb-10`, `ModernTitle` rendered as `before` prop above the editor
- Scroll wrapper `.editor-scroll-area`: `flex-1 overflow-y-auto flex flex-col`; child fills with `flex: 1`
- Modern variant adds `.modern-layout` class to the scroll wrapper; root cursor is `default`, editor cursor is `text`, min-height `60vh`

**Editor Styling**
- `font-size: 18px`, `line-height: 1.6`
- Focus outline removed (`focus-visible:outline-none`), cursor is text inside content area
- Placeholder uses Tiptap `Placeholder` extension; rendered via `.is-empty.is-editor-empty::before` at `--custom-muted-foreground`, half opacity on focus

**Extensions** (`editorExtensions` in `config/tiptap-editor.ts`)
- `StarterKit`
- `Underline`
- `Highlight`
- `TextAlign.configure({ types: ['heading', 'paragraph'] })`
- `Link.configure({ openOnClick: false })`
- `Image`
- `Table.configure({ resizable: true })`, `TableRow`, `TableCell`, `TableHeader`
- `TaskList`, `TaskItem.configure({ nested: true })`
- `Placeholder.configure({ placeholder: 'Start writing...' })`
- `AutocompleteExtension` (custom)

### Modern Title

- Component: `ModernTitle` inside `NoteEditorClassic.tsx`; passed as `before` prop into `ContentAreaClassic`
- Inline contenteditable at top of canvas with class `.modern-title`
- `text-4xl` bold, `px-10 pt-12 pb-2`
- Placeholder "Untitled" rendered via `:empty::before` using the `data-placeholder` attribute
- Enter key moves focus into the Tiptap editor (`document.querySelector('.tiptap').focus()`)
- `onInput` strips lingering `<br>` so the `:empty` placeholder reappears when the title is cleared
- `role="textbox"` with `aria-label="Note title"`

### Selection Bubble (`CustomSelectionPopover`)

- Lives in `src/components/ui/custom-popover.tsx`; wraps `ContentAreaClassic` and `ContentAreaMinimalist`
- Listens to `selectionchange`; if selection range falls inside the wrapped container, opens a portal-rendered popover
- Debounce: `120ms` in `ContentAreaClassic`, `500ms` in `ContentAreaMinimalist`
- Vertical offset: `80px` above the selection, with **flip-below** logic — if `rect.top < offsetY` it positions `8px` below the selection instead
- Content: full `EditorToolbar` floating inside `p-2` rounded container
- Animation: `bubble-in` keyframe (scale `0.5 → 1` with fade), curve `cubic-bezier(0.175, 0.885, 0.32, 1.275)`, duration `0.2s`
- Dismisses on outside mousedown, `Escape` key, or selection collapse
- `onMouseDown` is `preventDefault`-ed inside the portal so clicking toolbar buttons doesn't clear the selection

### Ghost Text Autocomplete

**Behavior**
- Tiptap extension `AutocompleteExtension` (`extensions/autocomplete-extension.ts`) using a ProseMirror widget decoration
- Active only when `storage.mode === 'lecture'` and `storage.enabled`
- Debounce: `200ms` (constant `DEBOUNCE_MS`) after the last keystroke
- Requires at least 2 characters and a word boundary after the cursor (no immediate following char or only whitespace)
- Tab inserts the completion + trailing space; Escape clears state; non-doc-changing transactions don't re-fire lookup (avoids dispatch loop)
- Suggestion sourced from `getBestSuggestion(currentWord, textBefore)` in `extensions/autocomplete-data.ts`
- Data file `NURSING_TERMS`: ~60 entries each with `text`, `contexts` (cardiac / pharm / assessment / respiratory), and base `weight`; scoring boosts contextual matches (+15 cardiac/pharm/respiratory, +10 assessment), boosts exact prefix (+20), slight penalty per term length

**Styling (`.ai-ghost-text`)**
- Light: color `#9ca3af`, opacity `0.45`
- Dark: color `#6b7280`, opacity `0.4`
- `pointer-events: none`, `user-select: none`, `display: inline`
- Fade-in animation `ghostFadeIn` `150ms ease-out`

### Status Bar

- Used in classic Lecture, Study, and Edit modes (component `StatusBar`)
- `border-t border-custom-border px-4 py-2 text-xs text-custom-muted-foreground`
- Left cluster: `Words: N`, `Characters: N`, optional Key Term count with `Bookmark` icon, optional "Unsaved changes" with `AlertCircle` in amber
- Right cluster: "Auto-saved" when `isSaved && !hasUnsavedChanges`, then mode label with `CheckCircle` icon
- Mode label map: `lecture → "Lecture Mode"`, `study → "Study Mode"`, `edit → "Edit Mode Active"`
- Numbers rendered via `toLocaleString()`

### Study Mode Page

**Layout**
- Two-column shell: read-only article (left flex column) + `StudyToolsPanel` (right, `320px`)
- Header (`border-b px-4 py-3`): `Home` button, plain note title block (`text-base` semibold), badge cluster (`Study Mode` + topic e.g. `Cardiology`), action buttons (theme, print, edit, more)
- Edit button navigates to `/edit` (entry point to Edit Mode)
- Body: `ScrollArea` with article `max-w-[900px] px-8 py-6 text-lg leading-[1.6] text-custom-foreground`
- Footer: `StatusBar` with `mode="study"`, `keyTermCount={5}`

**Inline Annotations**
- `MedicalTerm`: `cursor-help border-b border-dotted border-primary-brand text-primary-brand font-medium hover:bg-blue-500/10`; hovering opens a Radix `Tooltip` with the term + short content snippet (full popup data sourced from `definitions[termKey]`)
- `Shorthand`: `cursor-pointer rounded border-b-2 border-dotted border-primary-brand bg-blue-500/15 px-1 font-medium hover:bg-blue-500/25`; clicking opens `ExpansionPreviewDialog` with original/expanded copy from `shorthandExpansions`
- Annotations are inline JSX, not Tiptap marks — the study article is hand-authored HTML in the page component

### Study Tools Panel

- Right sidebar, `w-[320px] border-l bg-custom-background`, conditionally rendered via `isOpen`
- Header (`border-b px-4 py-3`): `Sparkles` icon + "Study Tools" title, close `X` (`h-7 w-7`)
- `ScrollArea` body with `space-y-6 p-4`
- Sections (each with uppercase muted heading `text-xs font-semibold uppercase`):
  1. **Refinement**: Expand Shortcuts (`Wand2`, quota `7/10`), Clarify Text (`Lightbulb`, quota `9/10`)
  2. **Smart Summary**: read-only `bg-custom-accent rounded-lg p-4` block titled "Key Takeaways" with bullet points from `smartSummary`, followed by Regenerate Summary action (`RefreshCw`)
  3. **Key Terms Spotted**: tappable rows from `keyTerms` on `bg-custom-accent rounded-md px-3 py-2`, hover gets `border-l-3 border-primary-brand` and lifts background to `bg-custom-background`
  4. **Exam-Relevant**: count line "3 exam-relevant items highlighted", then Show Exam Tips action (`BookOpen`)
- `ActionButton` pattern: `rounded-lg border px-4 py-3` with icon (muted), label (flex-1, left-aligned), optional `secondary` badge for quota, hover `bg-custom-accent`

### Definition Popup (`DefinitionPopup`)

- Radix `Popover` (not yet wired into `StudyModePage` — the tooltip variant is used for hover, this richer popup exists for click-to-pin patterns)
- Content width `400px`, `p-4`, aligned `start`
- Term: `text-lg` semibold foreground (`mb-2`)
- Definition: `text-sm leading-relaxed text-custom-foreground` (`mb-3`)
- Clinical example: `text-sm italic text-custom-muted-foreground` prefixed `Example:` (`mb-3`)
- Footer row: validation pill — `text-emerald-500` with `CheckCircle` ("Educator Validated") or `text-amber-500` with `AlertCircle` ("Unvalidated") — and a `Bookmark` icon button (`h-7 w-7`)

### Expansion Preview Dialog

- Radix `Dialog`, `sm:max-w-xl`
- Title: "Shorthand Expansion Preview"
- Two-column grid (`grid-cols-2 gap-4 pt-2`): Original (Shorthand) | Expanded (Full Terms)
- Each column has a `text-sm font-semibold text-custom-muted-foreground` label and a `bg-custom-accent rounded-lg p-4 text-sm leading-relaxed` block
- Footer actions (`flex justify-end gap-3 pt-2`): outline `Cancel`, primary-brand `Accept & Apply` with `Check` icon

### Comparison Dialog

*Used by Edit Mode to diff the in-progress draft against the original note.*

- Radix `Dialog`, `max-h-[90vh] max-w-6xl overflow-hidden p-0` (custom-sized, larger than other dialogs)
- Header (`border-b px-6 py-4`): `GitCompare` icon + "Compare Changes" title (`text-lg`)
- Body (`overflow-y-auto px-6 py-4`):
  - Stats strip on `bg-custom-accent rounded-lg p-4 mb-5`: `PlusCircle` additions in `text-emerald-500`, `MinusCircle` deletions in `text-red-500`, `Percent` percent-changed in muted foreground
  - View toggle: `ToggleGroup` on `bg-custom-accent rounded-lg p-1` with two items — `Columns` "Side-by-Side" and `AlignLeft` "Unified"
  - Side-by-side view: 2-column grid; each side has a header bar (`bg-custom-muted` with `File` / `FileCheck` icon + label) and a `ScrollArea max-h-[400px] p-5 text-base leading-[1.8]`. Deletions rendered as `<mark>` with `bg-red-500/15 text-red-500 line-through`; additions with `bg-emerald-500/15 text-emerald-500`
  - Unified view: single `ScrollArea max-h-[500px]` with both add/delete `<mark>` styles interleaved
- Footer (`border-t px-6 py-4 flex justify-between`): outline `Revert Changes` (`RotateCcw`) on the left; outline `Cancel` and primary-brand `Save Changes` (`Check`) on the right
- Props: `open`, `onOpenChange`, `onSave`, `onRevert`
- Sample copy is hardcoded in the component (medical "Cardiac Assessment" diff); real wiring TBD

### Edit Mode Page

- Route `/edit`; entered from Study Mode header (`Edit3` button)
- Top-level layout: `flex h-screen flex-col bg-custom-background`
- Header (`border-b px-4 py-3`):
  - `Home` button → navigate to `/`
  - Title block (`ml-3 flex-1`): contenteditable note title `text-base` semibold + badge row with `Edit Mode` (`secondary`) and `Unsaved Changes` (`outline` in `text-amber-500`)
  - Action cluster (`gap-2`): `Cancel` (`X`, ghost, navigates back to `/editor`), `Compare Changes` (`GitCompare`, ghost) opens `ComparisonDialog`, `Save` (`Save` icon, `bg-primary-brand` solid)
- Toolbar: shared `EditorToolbar` instance bound to the same `editor`
- Body: `ContentAreaClassic` inside `mx-auto max-w-[900px]`
- Footer: `StatusBar mode="edit" hasUnsavedChanges`, counts hardcoded (`wordCount=124`, `charCount=892`)
- Comparison dialog props wired: `onSave` navigates to `/editor`; `onRevert` resets the editor to `INITIAL_CONTENT`

### Settings Drawer (Popover)

**Trigger**
- Gear icon (`Settings`) in the sidebar footer next to the user profile (`Button variant="ghost" size="icon" h-7 w-7`)
- Opens a Radix `Popover` anchored `side="top" align="start"`, `sideOffset={8}`, `min-w-[240px] p-0`

**Menu State** (`SettingsMenu`)
- Title bar `border-b px-4 py-3`: "Settings"
- Items: Profile (`User`, "Name, email, avatar"), Preferences (`SlidersHorizontal`, "Theme, auto-save, defaults"), Keyboard Shortcuts (`Keyboard`, "Customize key bindings"), Subscription (`CreditCard`, "Plan and billing")
- Each row shows an icon tile (`h-8 w-8 rounded-md bg-custom-accent`), label, and description; full row hover gets `bg-custom-accent`
- Closing the popover resets state to `menu`

**Sub-page Wrapper** (`SettingsPageWrapper`)
- `flex max-h-[420px] flex-col`
- Header (`border-b px-3 py-3`): back arrow `ChevronLeft` (`h-7 w-7`) + page title
- `ScrollArea` content area with inner `p-4`

**Profile Page**
- Avatar block: `h-16 w-16 rounded-full bg-primary-brand text-lg font-bold text-white` with initials "JD"; camera overlay button (`h-6 w-6 rounded-full border-2 border-custom-background bg-custom-accent`)
- `Free Tier` badge (`secondary`)
- `Separator` then `FieldGroup` rows: Full Name, Email, Institution, Program — all `Input h-8 text-sm`
- Footer: primary-brand `Save Changes` button (`size="sm"`, full width)

**Preferences Page**
- Theme picker: `grid-cols-3 gap-1.5` of tiles `light | dark | system`; active uses `border-primary-brand bg-primary-brand/10 text-primary-brand`; inactive uses `border-custom-border` and hover `border-custom-foreground`
- `SettingsToggle` rows (each `flex justify-between` with label + `text-[10px]` description + Radix `Switch`): Auto-save, Spell Check, Word Count — all default checked
- Default Mode picker: `grid-cols-2 gap-1.5` of `Lecture | Study` tiles; Lecture is hardcoded as active in the prototype

**Shortcuts Page**
- Static list of action/keys rows (hover `bg-custom-accent`, `px-2 py-1.5 rounded-md`)
- Keys rendered inside `kbd` chip on `bg-custom-accent rounded px-1.5 py-0.5 font-mono text-[10px]`
- Pairs included: Bold `Ctrl+B`, Italic `Ctrl+I`, Underline `Ctrl+U`, Undo `Ctrl+Z`, Redo `Ctrl+Shift+Z`, Save `Ctrl+S`, Search `Ctrl+F`, New Note `Ctrl+N`, Toggle Mode `Ctrl+M`, Accept Suggestion `Tab`, Dismiss Suggestion `Esc`, Heading 1 `Ctrl+Alt+1`, Heading 2 `Ctrl+Alt+2`, Bullet List `Ctrl+Shift+8`, Numbered List `Ctrl+Shift+7`

**Subscription Page**
- Stack of 3 tier cards (`rounded-lg border p-3 space-y-3`): Free `$0/mo`, Pro `$8.99/mo`, Team `$19.99/seat/mo`
- Current tier uses `border-primary-brand bg-primary-brand/5` and shows a `Current` badge in `bg-primary-brand text-[10px] text-white`
- Each card lists features as `text-xs text-custom-muted-foreground` bullets prefixed `-`
- Non-current cards show an outline `Upgrade to {Tier}` button at the bottom

## 3. User Flow Screens

### Note List → Mode Select Flow

1. User lands on `/` (`NoteListPage`)
2. Sidebar exposes navigation, search, tags, folders, theme toggle, settings
3. Tapping a card opens `ModeSelectDialog` with `selectedNoteId` stashed in state
4. Lecture choice routes to `/editor?noteId=...&mode=lecture`
5. Study choice routes to `/study?noteId=...`
6. Tapping Quick Create opens `QuickCreateDialog`; selecting a template routes to `/editor?template={label}`

### Lecture Note Editor (`/editor`)

**Classic Shell**
- Header → Toolbar → centered editor → status bar
- Ghost-text autocomplete active in lecture mode
- Title is edited inline in the header; classic toolbar acts on both Tiptap and the contenteditable title
- Tag chip in the header opens tag entry (placeholder, no handler wired)

**Modern Shell**
- Floating left menu replaces the header and toolbar
- Inline `text-4xl` title above the editor (`ModernTitle`); Enter focuses the editor body
- Editor fills the centered column; clicks on the outer gutter blur the editor
- Toolbar surfaces as a floating bubble only after a text selection (debounced `120ms`)
- Status bar is **hidden** in Modern shell (only rendered when `layout === 'classic'`)

### Study Mode Editor (`/study`)

- Read-only article surface (no Tiptap editor instance)
- Inline annotations make terms (hover Tooltip) and shorthand (click → Expansion Preview) interactive
- `StudyToolsPanel` provides refinement, summary, key terms, exam tips (starts open)
- Header `Edit3` button routes to `/edit` for changes
- Status bar shows `study` mode with key term count

### Edit Mode Flow (`/edit`)

1. Entered from Study Mode header `Edit3` button (only documented entry point)
2. Page mounts with hardcoded `INITIAL_CONTENT` (Cardiac Assessment sample) bound to a fresh Tiptap editor + `EditorToolbar`
3. Header offers Cancel (navigates back to `/editor`), Compare (opens `ComparisonDialog`), Save (navigates to `/editor`)
4. Inside `ComparisonDialog`: Revert resets editor to `INITIAL_CONTENT`; Save Changes navigates to `/editor`; Cancel just closes the dialog
5. Status bar shows `edit` mode with `hasUnsavedChanges` always true in the prototype

### Onboarding Sandbox

*Not yet implemented in code.* The PRD treats this as MVP scope; design tokens and components in this doc apply when built.

## 4. Interaction Patterns

### Selection Bubble

- Debounce: `120ms` (Classic), `500ms` (Minimalist scaffold)
- Offset: `80px` above selection; flips to `8px` below when there isn't room above
- Dismisses on outside mousedown, `Escape`, or selection collapse
- Portal-rendered with `bubble-in` keyframe (scale 0.5 → 1, fade) using `cubic-bezier(0.175, 0.885, 0.32, 1.275)` over `0.2s`

### Ghost-Text Autocomplete

- Triggered after `200ms` typing pause inside the editor
- Requires `currentWord.length >= 2` and a word boundary right after the caret
- Tab inserts the suggestion + trailing space; Escape clears state
- Suppressed automatically outside Lecture Mode (storage flag check inside the plugin view)

### Note Card Interactions

- Hover reveals overflow menu (`opacity-0 → 100`) and elevates with `shadow-md`
- Favorite star toggles between muted outline and amber filled (local state — not yet persisted)
- Card click opens `ModeSelectDialog`; clicking the overflow button or star uses `stopPropagation`

### Mode Differentiation

- Brand color stays consistent across modes (intentional)
- Lecture vs Study vs Edit is communicated through:
  1. Route and shell (editable Tiptap vs read-only article vs Edit Mode wrapper)
  2. Header badges in Study (`Study Mode` + topic) and Edit (`Edit Mode` + `Unsaved Changes`)
  3. Status bar label and icon (`Lecture Mode` / `Study Mode` / `Edit Mode Active`)
  4. Availability of inline annotations + Study Tools panel (Study only)
  5. Header right-cluster actions (Edit uses Cancel / Compare / Save instead of layout / pin / etc.)

### Quota Indicators

- Refinement actions in the Study Tools panel show inline `Badge variant="secondary"` quota strings (e.g. `7/10`)
- No quota enforcement is wired; values are static in the component

## 5. Accessibility

- Buttons use `aria-label` via tooltip wrappers and `ToggleGroupItem aria-label={key}` for each toolbar action
- Tooltips delay `200ms` (modern menu) and align to consistent sides (`right` for the floating menu)
- Inline annotations use semantic spans with `cursor-help` (terms) or `cursor-pointer` (shorthand)
- Contenteditable fields expose `role="textbox"` and named labels (e.g. `aria-label="Note title"` on `ModernTitle`)
- Focus uses theme-driven `--custom-ring` and `primary-brand` border for the editable title
- Keyboard support already wired: Tab/Escape for autocomplete, Enter to leave modern title, standard Tiptap formatting shortcuts (Ctrl+B etc.) via `StarterKit`
- *Important!* The Modern Floating Menu backdrop is a sibling `<div>` not a Radix Dialog — there is no focus trap. Improve if adding more menu items.

## 6. Responsive Behavior

*Important!* The product is a browser SPA targeting **desktop-first**. Mobile layouts are not yet implemented and `xs` breakpoints have not been designed.

- Note grid scales from 1 column to 4 columns via Tailwind breakpoints `sm` (640px), `lg` (1024px), `xl` (1280px)
- Sidebar fixed at `280px`, collapsible entirely via the page header button
- Editor column max widths: `900px` (classic / edit) and `800px` (modern)
- Study Tools panel fixed `320px` on desktop, hide via the close button

## 7. Animation Specifications

- Ghost text fade-in: `ghostFadeIn` `150ms ease-out`, target opacity `0.45` light / `0.4` dark
- Selection bubble: `bubble-in` keyframe `scale 0.5 → 1`, `opacity 0 → 1`, curve `cubic-bezier(0.175, 0.885, 0.32, 1.275)`, `0.2s`
- Modern menu open: Tailwind `animate-in fade-in slide-in-from-left-2 duration-200`
- Note card overflow / favorite reveal: `transition-opacity` + `transition-all` (default duration)
- Hover state changes: Tailwind `transition-colors` defaults
- Theme switch: instant token swap, no explicit transition tween

## 8. Icon System

**Library**: `lucide-react` (`@tabler/icons-react` is also installed but not yet used in components).

**Recurring Icons**
- Navigation: `Home`, `PanelLeft`, `PanelLeftClose`, `PanelTop`, `Columns2`, `Menu`
- Editor actions: `Bold`, `Italic`, `Underline`, `Strikethrough`, `Highlighter`, `Code`, `Quote`, `Undo`, `Redo`, `Link`, `Image`, `Table`, `List`, `ListOrdered`, `ListChecks`, `AlignLeft`, `AlignCenter`, `AlignRight`, `Plus`, `MoreHorizontal`
- Content types (Quick Create): `FileText`, `Clipboard`, `Pill`, `Heart`
- Sidebar nav: `FileText`, `Star`, `Clock`, `Archive`, `Folder`, `Search`
- Status / validation: `CheckCircle`, `AlertCircle`, `Star`, `Calendar`, `Bookmark`
- Tools (Study panel + dialogs): `Sparkles`, `Wand2`, `Lightbulb`, `RefreshCw`, `BookOpen`
- Theme: `Sun`, `Moon`, `Monitor`
- Settings: `Settings`, `SlidersHorizontal`, `Keyboard`, `CreditCard`, `Camera`, `User`
- Editor header extras: `Printer`, `Pin`, `MoreVertical`, `Edit3`
- General: `Check`, `X`, `ChevronLeft`, `Presentation`, `Grid3X3`, `List`
- Comparison Dialog: `GitCompare`, `PlusCircle`, `MinusCircle`, `Percent`, `Columns`, `AlignLeft`, `RotateCcw`, `Save`, `File`, `FileCheck`

**Sizing Conventions**
- `h-3 w-3` or `h-3.5 w-3.5`: inline metadata, tiny chips, plus buttons in sidebar headers
- `h-4 w-4`: default action and menu icons
- `h-5 w-5`: emphasized header icons (sidebar collapse `PanelLeft`)
- `h-6 w-6`: Quick Create tile icons

## 9. Design Foundations

**Component Library** — shadcn/ui `new-york` style, `neutral` base color (`components.json`).

**Primitives present in `src/components/ui/`** (do **not** modify per project rules)
- `avatar`, `badge`, `button`, `card`, `collapsible`, `command`, `context-menu`, `custom-popover`, `dialog`, `dropdown-menu`, `hover-card`, `input`, `popover`, `scroll-area`, `select`, `separator`, `sheet`, `sidebar`, `skeleton`, `switch`, `tabs`, `textarea`, `toggle`, `toggle-group`, `tooltip`

**Custom Components**
- `src/note-editor/components/`: `NoteListSidebar`, `NoteCard`, `QuickCreateDialog`, `ModeSelectDialog`, `ModernFloatingMenu`, `SettingsDrawer`, `StatusBar`, `StudyToolsPanel`, `DefinitionPopup`, `ExpansionPreviewDialog`, `ComparisonDialog`
- `src/note-editor/`: `NoteListPage`, `NoteEditorClassic`, `NoteEditorMinimalist` (scaffold), `ContentAreaClassic`, `ContentAreaMinimalist`, `EditorHeader`, `EditorToolbar`, `StudyModePage`, `EditModePage`
- `src/note-editor/extensions/`: `AutocompleteExtension` and `autocomplete-data`
- `src/note-editor/custom-styles/`: `editor-content.css`, `editor-header.css`, `toolbar.css`
- `src/components/theme-mode/`: `ThemeProvider`, `useTheme`, `ModeToggle` (dropdown variant; not currently mounted but available)

**Design Tokens**
- Defined in `src/custom-styles.css` via `@theme inline` plus `:root` (light) and `.dark` (dark) selectors
- Consumed in Tailwind utilities (e.g. `bg-custom-background`, `text-primary-brand`, `border-custom-border`)

## 10. Data Model & Mock Sources

All mock data lives in `src/note-editor/config/` and `src/note-editor/extensions/`. There is **no backend** wired — every list is hardcoded.

**`config/note-list-data.ts`**
- `NoteCardData { id, title, preview, tag, tagVariant, date, isFavorite }` — 12 sample cards
- `NavItem { label, icon, badge? }` — All Notes (12), Favorites (3), Recent, Archive
- `TagItem { label, color, count }` — Pharmacology `#8b5cf6` (5), Anatomy `#10b981` (3), Clinical `#f59e0b` (4)
- `FolderItem { label }` — Semester 1, NCLEX Prep
- `CreateOption { label, icon }` — Blank Note, SOAP Note, Drug Card, Care Plan
- `sortOptions` — recent / created / title / title-desc

**`config/medical-data.ts`**
- `MedicalDefinition { term, content, example, validated }` — 7 entries (`murmur`, `sinus-rhythm`, `pvc`, `diaphoresis`, `nasal-cannula`, `nitroglycerin`, `myocardial-infarction`)
- `shorthandExpansions` — 9 abbreviations (`VS`, `BP`, `HR`, `RR`, `ECG`, `PO`, `O2`, `SL`, `PRN`)
- `keyTerms` — 5 sample key terms
- `smartSummary { title, points }` — "Key Takeaways" with 3 bullets

**`extensions/autocomplete-data.ts`**
- `AutocompleteTerm { text, contexts, weight }` — ~60 entries
- Contexts: `cardiac`, `pharm`, `assessment`, `respiratory`, plus uncontextual common phrases
- `getBestSuggestion(query, textBefore)` scores prefix matches, contextual matches, and a length penalty; returns `null` when query already equals the best term

**`config/toolbar.config.tsx`**
- `toolbarIconsProps` keyed object mapping action name → Lucide icon JSX

## 11. Routes

Defined in `src/App.tsx`. All routes are wrapped in a `ThemeProvider` from `src/main.tsx`.

- `/` → `note-editor/NoteListPage`
- `/editor` → `note-editor/NoteEditorClassic` (query params: `noteId`, `mode=lecture`, `template`)
- `/study` → `note-editor/StudyModePage` (query param: `noteId`)
- `/edit` → `note-editor/EditModePage`

**Important!** Query params are not yet read inside the route components — navigation passes them but pages currently render hardcoded content.

## 12. Theme Provider

- File: `src/components/theme-mode/theme-provider.tsx`
- `Theme = 'dark' | 'light' | 'system'`
- Stored under `localStorage` key `vite-ui-theme`
- `system` resolves via `window.matchMedia('(prefers-color-scheme: dark)')`
- Applies `light` / `dark` class on `document.documentElement` (CSS variables flip via `.dark` selector)
- `useTheme()` is a thin hook; throws if used outside the provider
- `ModeToggle` (`mode-toggle.tsx`) is an unused convenience `DropdownMenu` variant of the toggle — sidebar uses a plain icon button instead

## 13. File Map (Quick Reference)

- `src/main.tsx` — Root, mounts `<App />` inside `ThemeProvider`
- `src/App.tsx` — Router and route table
- `src/styles.css` — Tailwind + shadcn base
- `src/custom-styles.css` — Brand tokens (light + dark) + `@theme inline` bindings
- `src/note-editor/NoteListPage.tsx` — Live note list (`/`)
- `src/note-editor/NoteEditorClassic.tsx` — Lecture editor wrapper with Classic/Modern shell switching
- `src/note-editor/NoteEditorMinimalist.tsx` — Standalone Modern shell scaffold (not routed)
- `src/note-editor/EditModePage.tsx` — Edit Mode page with Comparison dialog
- `src/note-editor/StudyModePage.tsx` — Read-only annotated article
- `src/note-editor/ContentAreaClassic.tsx` — Tiptap content wrapper + selection bubble (`debounce 120ms`)
- `src/note-editor/ContentAreaMinimalist.tsx` — Same wrapper without `before` slot (`debounce 500ms`)
- `src/note-editor/EditorHeader.tsx` — Classic editor header
- `src/note-editor/EditorToolbar.tsx` — Shared formatting toolbar
- `src/note-editor/components/*` — Dialogs, panels, sidebar, cards, popups
- `src/note-editor/config/*` — Mock data + toolbar config
- `src/note-editor/extensions/*` — Autocomplete extension + data
- `src/note-editor/custom-styles/*` — Editor-scoped CSS partials
- `src/components/ui/*` — shadcn primitives (do not modify)
- `src/components/theme-mode/*` — Theme provider + dropdown variant toggle

## 14. Known Gaps & Stale Bits

- **`src/pages/NoteListPage.tsx`** is an orphan dashboard scaffold using shadcn `sidebar` — **not routed**. The live note list is `src/note-editor/NoteListPage.tsx`. Don't edit the orphan by accident.
- **`src/components/Sidebar.tsx`** and `src/components/sidebar copy/` are also unused remnants of the orphan dashboard scaffold.
- **`src/components/Card.tsx`** is unused; `NoteCard` is the live card component.
- **Sort dropdown** in `NoteListPage` updates state but does not actually re-order `noteCards`.
- **Tag chip in Editor Header**, plus Pin / Print / More buttons across headers, are visual only — no handlers wired.
- **`DefinitionPopup`** component exists but `StudyModePage` currently uses Radix Tooltip for hover previews; the rich popup is reserved for click-to-pin once wired.
- **`config/note-list-page.tsx`** is present alongside `note-list-data.ts` — verify before adding new data which file is being imported.
- **Query params** (`noteId`, `mode`, `template`) are pushed by navigation but not consumed by route components — every page renders fixed content for the prototype.
- **Onboarding Sandbox** is unbuilt; PRD scope only.
- **No mobile layout** has been designed; below `sm` breakpoint the grid degrades to a single column but the sidebar/panel widths are not responsive.
