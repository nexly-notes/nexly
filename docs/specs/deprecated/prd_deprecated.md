# NEXLY RN – Product Requirements Document (Deprecated)

## 1. Product Overview

- **Name:** NEXLY RN – AI-Powered Nursing Education Platform
- **Elevator Pitch:** NEXLY RN transforms chaotic lecture notes into clear, structured learning material by combining intelligent autocompletion during class with post-lecture AI refinement, helping nursing students capture information faster and study more effectively—bridging the gap between lecture hall and clinical competence
- **Problem:** Nursing students struggle to keep pace with fast-moving lectures while capturing complex medical terminology accurately, resulting in messy notes requiring hours of cleanup, wasting time, reducing retention, and increasing stress
- **Solution:** NEXLY RN provides AI-powered lecture note-taking in two phases:
  1. **Lecture Mode:** fast capture with intelligent autocompletion and minimal distraction
  2. **Study Mode:** post-lecture expansion, clarification, and definitions to transform shorthand into study-ready material

## 2. Goals & Success Criteria

### Primary Goals

1. Reduce lecture note-taking cognitive load by 40% through autocompletion
2. Cut post-lecture cleanup time by 60% with shorthand expansion and clarification
3. Improve note clarity (self-reported) by 75%
4. Achieve 70% DAU during academic terms
5. Build a community of 5,000+ nursing students in Year 1

### Non-Goals (Out of Scope for MVP)

- Audio recording/transcription
- Flashcards/quizzes
- Clinical documentation for patient care
- Real-time collaboration
- Mobile app (desktop/web only for MVP)
- LMS integrations
- Spaced repetition/scheduling
- Full visual concept maps

### Success Criteria (Definition of Done)

- User satisfaction ≥ 4.3/5
- 65% of users use AI expansion after ≥50% of lectures
- Average post-lecture cleanup reduced from 45 min → <15 min
- ≥80% report improved note clarity
- <5% monthly churn during terms
- ≥20% free-to-paid conversion in first semester
- ≥92% accuracy in AI-generated definitions (with educator validation)
- 60% of students use Lecture Mode consistently

## 3. Target Users

### Primary Persona

Pre-licensure Nursing Students (ADN/BSN)

### Secondary Persona

Advanced Practice Nursing Students (MSN/DNP)

### Tertiary Persona

Nursing Educators (as validators and institutional adopters)

### Pain Points

- Can't keep up in lectures
- Messy shorthand
- Unclear notes
- Long cleanup time
- Missing key concepts
- Difficulty identifying exam content
- AI trust concerns

## 4. User Workflow

### Flow

Sign Up → Guided Onboarding Sandbox → Lecture Mode (capture notes, autocompletion, time markers) → End Lecture → Switch to Study Mode → Expand shorthand → Clarify vague text → Lookup definitions → Review summaries/key terms → Save/export notes

### Key Screens

1. Lecture Note Editor (Tiptap-based)
2. Mode Toggle Bar
3. Refinement Panel
4. Highlight-to-Action Context Menu
5. Definitions Popup
6. Smart Summary View
7. Key Terms Sidebar
8. Note Library

## 5. Features (Lean MVP)

### MVP Structure: Core Loop + Differentiator + Fast-Follows

The MVP focuses on testing the central hypothesis: **nursing students gain value from separating fast capture (Lecture Mode) from structured refinement (Study Mode)**

Features are grouped into:

- **Core Loop:** essential for validation
- **Differentiator:** a single "wow" feature for engagement
- **Fast-Follows:** secondary features to ship after validation

### Core Loop MVP (must-have to validate product hypothesis)

#### 1. Feature 0: Lecture Mode vs Study Mode Toggle

_Core Concept:_ A persistent toggle that switches between capture-focused and refine-focused workflows

- **Lecture Mode:** Minimal AI; only autocomplete and time markers active; Visual indicator (blue accent)
- **Study Mode:** Full AI features available; Visual indicator (green accent)
- **Benefits:** Prevents distraction during lectures while enabling deep refinement later

#### 2. Feature 1: AI Autocompletion

_Purpose:_ Reduce typing load and catch missed terminology in real-time

- Suggests nursing-specific abbreviations, terminology, and common phrases
- Learns from user acceptance patterns
- Non-intrusive: appears only after pauses in Lecture Mode

#### 3. Feature 2: Shorthand Expansion

_Purpose:_ Convert messy, rushed shorthand into complete, professional notes

- Expands abbreviations, arrows (↑, ↓, →), and fragments into full sentences
- Available only in Study Mode
- Provides side-by-side before/after with accept/reject option

#### 4. Feature 5: Definition-on-Demand

_Purpose:_ Provide trusted, plain-language definitions with clinical examples

- Activated by highlight → contextual menu → "Define"
- Inline popup with definition + example
- Educator-validated during beta
- Ensures clarity for complex medical concepts

#### 5. Feature X: Guided Onboarding Sandbox

_Purpose:_ Ensure students understand workflow immediately

- Auto-loads a demo note with shorthand pre-filled
- Walks users through: typing shorthand → switching modes → expanding → defining terms
- Learn-by-doing instead of static tooltips

### Differentiator MVP (choose one "wow" factor for early adoption)

#### Option A: Smart Summarization

- Auto-generates section-level summaries and hierarchical key concepts
- Collapsible blocks for scanning
- Delivers immediate "time saved" value for studying

#### Option B: Key Term Spotlighting

- Highlights exam-relevant terms and professor cues (e.g., "this will be on the test")
- Uses regex + AI to detect emphasis signals
- Provides sidebar summary of all spotted terms

### Fast-Follow Features (to ship after validation)

- **Clarity Rewrite:** Highlight → "Clarify" with suggested rewrites for vague phrasing
- **Concept Linking:** Suggests connections between related concepts across notes
- **Figures & Tables Generator:** Converts structured text into formatted tables/equations
- **Time-Stamp Markers:** Lightweight note markers with clock time for navigation
- **Nursing Educator Validation Workflow:** Beta-only dashboard for validating AI output

## 6. Post-MVP Features

### Phase 2 (Q3 2025)

- Audio sync
- Flashcards from key terms
- Quiz generation
- Visual concept mapping
- Mobile companion app

### Phase 3 (Q4 2025–Q1 2026)

- Spaced repetition
- LMS integration
- Advanced analytics
- Educator dashboard in production

### Stretch (2026+)

- SimPatient builder
- AR/VR integration
- NCLEX readiness
- Personalized study guidance

## 7. Technical Requirements

### Frontend

- React + TypeScript
- Tiptap editor
- Tailwind + Shadcn UI
- Electron wrapper

### Backend

- Firebase (Auth, Firestore, Functions, Storage)

### AI

- GPT-4.1 nano for auto completion
- Model TBD for expansion, clarification and summarization
- Custom 5,000+ nursing terms DB for autocomplete

### Performance

- Autocomplete <100ms
- Mode toggle <50ms
- Expansion <30s for 3,000 words
- Definitions <500ms

## 8. Monetization Strategy

**Important!** We are adopting a **freemium SaaS model** with a **request-based cap** for autocomplete to avoid heavy token-tracking complexity while still controlling costs

### Free Tier (Baseline Adoption – $0/month)

- Unlimited note-taking
- Lecture Mode + Study Mode toggle
- **AI Autocompletion:** up to 100 requests/month (each request = one AI suggestion)
- After limit: fallback to dictionary-based autocomplete (5,000+ nursing terms DB, no API cost)
- Up to **10 AI refinement actions/month** (expand, clarify, define)
- Time-Stamp Markers (basic)
- Local note storage + export (PDF/DOCX)
- No educator-validated guarantee on definitions (shows indicator for unvalidated)

### Pro Tier (Core Value Unlock – $8.99/month or $79/year)

- Everything in Free, plus:
- **Unlimited AI Autocompletion requests**
- **Unlimited AI refinements** (expand, clarify, define)
- Smart Summarization
- Key Term Spotlighting
- Priority access to educator-validated definitions
- Advanced search + filters in Note Library
- Priority support + feature voting

### Team/Educator Tier (Institutional – $19.99/month per seat)

- Everything in Pro, plus:
- Educator Dashboard for validation workflows
- Institution-level note sharing + analytics
- Bulk license management
- Early access to beta features

### Rationale

- **Free Tier:** Showcases core product value while capping costs via request limits
- **Pro Tier:** Removes caps, adds study accelerators, and ensures heavy users upgrade
- **Team/Educator Tier:** Supports institutional adoption and credibility-building

## 9. Success Metrics

### Core Workflow Metrics

- **Mode Adoption Rate:** % of users switching between Lecture & Study Mode in week 1
- **AI Engagement:** Avg. number of expand/clarify/define actions per note
- **Onboarding Completion:** % of users finishing the sandbox tutorial

### Lagging Metrics

- DAU
- Retention
- Clarity score improvement
- Free-to-paid conversion
- Churn

### Revenue Metrics

- ARPU (Average Revenue Per User)
- Conversion rate from Free → Pro
- Institutional seat growth

## 10. Challenges & Risks

### Technical

- Autocomplete accuracy during fast lectures
- Expansion fidelity (preserving meaning)
- Latency at scale
- Hallucination risk in definitions

### User Behavior

- Students failing to adopt mode toggle
- Resistance to changing workflows
- Over-reliance on AI leading to passive note-taking

### Business

- Competition from generalist AI note apps
- Institutional adoption barriers
- Dependence on OpenAI API pricing

### Mitigations

- Interactive onboarding
- Educator validation (beta)
- Visible AI trust indicators (e.g., indicator for unvalidated)
- "Revert to original" always available
- Data privacy: notes not used to train AI
