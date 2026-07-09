# UI/UX Specification
**Project:** VeritasRAG · **Phase:** 9 (step 9) · **Version:** 1.0 · **Date:** 2026-06-07
**Inspiration bar:** Linear (speed/keyboard), Notion (structure), Vercel (clean dark), Stripe (trust/clarity), Perplexity (answer+citations UX).

## 1. Design principles
Verification is the hero of the UI: every answer is secondary to *how trustworthy each claim is*. Calm, dense-but-legible, keyboard-first, dark-mode-native, motion that informs (not decorates).

## 2. Design system
- **Framework:** Next.js 15 (App Router) + React 19 + TypeScript; Tailwind + shadcn/ui; Framer Motion; lucide icons.
- **Tokens:** CSS variables for color/space/radius/typography; light + dark themes.
  - Color: neutral slate base; brand indigo `#4F46E5`; semantic green/amber/red for supportedness bands (green ≥ 0.8, amber ≥ threshold, red < threshold).
  - Type: Inter (UI), JetBrains Mono (scores/IDs). Scale 12/14/16/20/24/32.
  - Radius 8–12; spacing 4-pt grid; elevation via subtle borders, not heavy shadows.
- **Accessibility:** WCAG 2.1 AA; visible focus rings; ARIA on interactive elements; color never the sole signal (icon + label accompany band color); reduced-motion honored.
- **States everywhere:** loading (skeletons), empty, error, success; optimistic UI where safe.

## 3. Information architecture
```
/(marketing)        landing, pricing, docs
/app                 (authed)
  /onboarding        create org, first corpus, pick mode
  /dashboard         usage analytics, recent runs, verified-answer rate
  /corpora           list; /corpora/[id] documents + index status
  /ask               question console (streamed answer + verification)
  /history           past runs; /history/[id] full run + per-claim
  /evaluations       (admin) benchmark runs + comparison
  /settings          profile, providers/keys, thresholds, appearance
  /admin             members/RBAC, usage, audit log
```

## 4. Key screens & component hierarchy
- **Ask console (`/ask`)** — the core experience:
  ```
  <AskPage>
    <CorpusSelector/> <ModeToggle cloud|local/> <ProviderSelect/>
    <QuestionInput (RHF+Zod)/>
    <AnswerStream>           // tokens stream in
      <AnswerText/>          // inline [n] chips → scroll to claim
      <SubQuestions/>        // planner output chips
    </AnswerStream>
    <VerificationPanel>
      <ClaimCard band=green|amber|red>
        <ClaimText/> <SupportednessBadge/> <RelianceFlag/>
        <CitedChunk file page excerpt/> <RejectButton/>
      </ClaimCard> …
    </VerificationPanel>
    <PrivacyNotice mode/>    // mode-specific data-flow statement
  </AskPage>
  ```
- **Dashboard** — KPI cards (verified-answer rate, runs, avg latency by mode, tokens/cost), trend charts, recent runs table.
- **Corpus detail** — document list, index status, re-index, drag-drop uploader with progress (SSE/WebSocket).
- **Evaluations (admin)** — pipeline×mode comparison table, significance badges, export.
- **Settings/Providers** — provider cards (Gemini/OpenRouter/NIM/Ollama), enable, default model, key status (set via env/secret-ref, never shown), threshold sliders with live band preview.
- **Admin** — members + roles, usage meters, searchable audit log.

## 5. Core user flows
1. **First-run onboarding:** sign up → name org → choose data-residency (cloud/local) → create first corpus → upload PDFs → guided first question → see verification → "aha".
2. **Ask → verify → act:** type question → stream answer → expand claim cards → reject a weak claim → re-ask/refine → export cited answer.
3. **Go private:** toggle Local mode → confirm privacy statement modal → ask (all on-device).
4. **Admin governs:** set provider+model+thresholds → invite members with roles → monitor usage/audit.

## 6. Wireframes (low-fi, ASCII)
```
ASK CONSOLE
┌───────────────────────────────────────────────┐
│ Corpus ▼   ◉ Cloud ○ Local   Provider ▼        │
│ ┌───────────────────────────────────────────┐ │
│ │ Ask a question about your papers…       ⏎ │ │
│ └───────────────────────────────────────────┘ │
│ Answer ▌(streaming)…  with citations [1][2]    │
│ Sub-questions:  ▢ q1   ▢ q2                     │
│ ── Verification ───────────────────────────────│
│ 🟢 92%  Claim text…           [1] a.pdf p.3  ⊘ │
│ 🔴 41%  Claim text…  NOT entailed  [2] b.pdf ⊘ │
│ Privacy: Cloud mode — question+chunks sent…     │
└───────────────────────────────────────────────┘
```
(High-fidelity mockups + the full component library live in `packages/ui-library`; a clickable prototype is produced in the UI phase.)

## 7. Motion & micro-interactions
Token streaming with caret; claim cards animate in as verified; band color transitions; skeleton→content cross-fade; route transitions < 200 ms; all respect `prefers-reduced-motion`.

## 8. Responsive & mobile
Mobile-first; ask console collapses verification into an expandable sheet; tables → stacked cards; bottom-nav on small screens; 44-px touch targets.

*Changes logged in `changelog.md`.*
