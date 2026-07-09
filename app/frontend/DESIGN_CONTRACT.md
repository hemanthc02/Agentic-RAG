# VeritasRAG Frontend Design Contract (Light Professional Redesign)

Every page/component edit MUST follow this contract. Do not deviate.

## Theme
- **Light theme only.** Canvas `#F9FAFB` (use `bg-canvas` or `bg-zinc-50`), surfaces pure white.
- Text: primary `text-zinc-900`, secondary `text-zinc-500`, tertiary/disabled `text-zinc-400`.
- Borders: `border-zinc-200/60` (1px). Shadows: diffused only — `shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]` or the `.card` class.
- **Single accent**: the existing `brand` teal scale. Buttons `bg-brand-600 hover:bg-brand-700`, tints `bg-brand-50 text-brand-700 border-brand-200`. NO other accent colors except semantic green/amber/red for faithfulness scores.
- Semantic score colors (light variants, already defined): `.score-green`, `.score-amber`, `.score-red`.
- NEVER: dark backgrounds (`bg-slate-950`, `bg-slate-900`, `bg-white/5`...), purple/violet, gradient text on big headers, pure black.

## Typography
- Font is set globally: Geist (sans) + Geist Mono. Do not add font-family overrides.
- Headlines: `font-semibold` or `font-bold`, `tracking-tight`. Sentence case ("Research guide", not "Research Guide").
- Numbers in data/metrics: `font-mono tabular-nums`.
- Body copy max width `max-w-[65ch]`.

## Shared classes (defined in src/index.css — use these, don't reinvent)
- `.card` — white surface, zinc border, rounded-2xl, diffused shadow
- `.btn-primary` — teal filled button
- `.btn-ghost` — white bordered button
- `.input` — light input field
- `.badge`, `.score-green`, `.score-amber`, `.score-red`

## Layout contract for workspace pages (guide / viva / papers)
These pages render INSIDE `WorkspaceLayout` (top bar + tabs already provided):
- Export the same default component name. **Remove** `<Navbar />`, its import, and any outer `min-h-screen bg-slate-950` wrapper.
- Root element: `<div className="h-full flex ...">` filling the content area (the layout gives it a fixed-height flex container; use `h-full` + internal `overflow-y-auto` for scrolling regions).
- Read `mode` and `provider` from `useStore()` — the top bar owns the online/offline toggle. Remove any per-page mode selectors.
- Keep ALL existing logic, state, API calls, and props EXACTLY as they are. This is a restyle + de-shell, not a rewrite.

## Interaction states
- All buttons: hover shift + `active:scale-[0.98]`, `transition` 150–200ms, visible focus ring (`focus-visible:ring-2 focus-visible:ring-brand-500`).
- Loading: skeleton shimmer blocks (`animate-pulse bg-zinc-100 rounded`) matching layout, not spinners, where practical.
- Empty states: icon + one clear sentence + one action. No "No data found" alone.
- Errors: inline `text-red-600 text-sm`, direct wording ("Connection failed. Try again."), no "Oops".

## Hard bans
- NO emojis anywhere (UI text, toasts, icons). Replace with lucide-react icons (already a dependency) or colored dot `<span className="w-2 h-2 rounded-full bg-emerald-500" />`.
- NO new npm dependencies.
- NO `h-screen` — use `min-h-[100dvh]` (public pages) or `h-full` (workspace panels).
- NO 3-equal-card feature rows; use asymmetric grids or 2-column zig-zag.
- NO centered hero on public pages — left-aligned text with asymmetric whitespace.
- NO AI-cliché copy ("Elevate", "Seamless", "Unleash", "never hallucinates" is OK to replace with concrete claims like "every citation checked by an NLI model").
- Do not touch files outside your assignment.
