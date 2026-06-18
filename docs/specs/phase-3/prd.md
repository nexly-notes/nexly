# NEXLY RN – Product Requirements Document (Phase 3 & Stretch)

## 1. Overview

- **Scope:** Long-term, institutional, and exploratory features beyond Phase 2 (see `phase-2/prd.md`)
- **Goal:** Move from individual study tool to institutional platform and differentiated learning system
- **Dependency:** Requires validated Phase 2 adoption and educator interest

## 2. Phase 3 (after validated Phase 2 adoption)

- **LMS Integration:** Connect notes/key terms to institutional LMS (e.g., Canvas, Blackboard)
- **Advanced Analytics:** Study behavior, term mastery, and cohort insights
- **Educator Dashboard (Production):** Validation workflows, note sharing, institution-level analytics, bulk license management

## 3. Stretch (exploratory — own PRD before build)

- **SimPatient Builder:** Generate simulated patient scenarios from notes
- **AR/VR Integration:** Immersive review of concepts and procedures
- **NCLEX Readiness:** Targeted readiness scoring and gap analysis
- **Personalized Study Guidance:** Adaptive recommendations based on study history

## 4. Requirements (High-Level)

**Functional**

1. LMS integration via standard institutional protocols; data export honors privacy commitments
2. Analytics and Educator Dashboard operate at institution scope under the Team/Educator tier
3. Stretch features are exploratory — each requires its own validated PRD before build

**Non-Functional**

1. Maintain the data-privacy commitment: user notes are never used to train AI
2. Institutional features must scale beyond single-user latency budgets
3. Educator/analytics access is role-gated and audited
