# NEXLY RN

An AI-powered, installable PWA that helps nursing students keep pace with lectures and
turn their own notes into study material. AI is **assistive, not substitutive** — it
accelerates the student's own work (catching up, spotting key terms) and never authors
notes for them.

> **Status:** MVP scaffold — framework genesis only. Internal application architecture
> and the full dependency stack are added in later setup steps.

## Prerequisites

- [Node.js](https://nodejs.org/) 22
- npm

## Getting started

```bash
npm install
npm run dev
```

The app runs at [http://localhost:3000](http://localhost:3000).

Copy `.env.example` to `.env.local` and fill in values when backend features are wired up.

## Commands

| Command             | Description                          |
| ------------------- | ------------------------------------ |
| `npm run dev`       | Start the development server         |
| `npm run build`     | Production build (main CI gate)      |
| `npm run start`     | Serve the production build           |
| `npm run lint`      | Lint with ESLint (flat config)       |
| `npm run lint:fix`  | Lint and auto-fix                    |
| `npm run typecheck` | Type-check with `tsc --noEmit`       |

CI (`.github/workflows/ci.yml`) runs `npm ci → lint → typecheck → build` on push/PR to
`main` (Node 22); all steps must pass.

## Project structure

```
nexly/
├── .github/workflows/ci.yml   # CI: lint → typecheck → build
├── project/                   # MVP specs (source of truth for scope)
├── CLAUDE.md                  # Project instructions
├── README.md
├── .env.example               # Environment variable template
├── .gitignore
├── eslint.config.mjs          # ESLint flat config
├── next.config.ts
├── next-env.d.ts
├── postcss.config.mjs
├── package.json
├── package-lock.json
├── tsconfig.json              # TS strict; `@/*` → `src/*`
└── src/
    └── app/                   # Next.js App Router
        ├── layout.tsx
        └── page.tsx
```
