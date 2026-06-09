# UX/UI Design Specification (Lean MVP)

**Project:** `<PROJECT_NAME>` · **Version:** `<VERSION>` · **Date:** `<DATE>` · **Status:** Draft / Approved

---

## 1. Purpose & Scope

> _What user-facing problem does this design solve, and what's explicitly not in it?_

- **Problem:** `<The user pain or behavior this design targets.>`
- **Success looks like:** `<One measurable UX outcome — e.g., "user completes first task in < 2 min".>`
- **In scope:** `<Surfaces and flows covered.>`
- **Out of scope:** `<Explicit exclusions.>`

---

## 2. Users & Critical Journeys

### 2.1 Primary Persona(s)

| Persona  | Goal                  | Main Pain Point          |
| :------- | :-------------------- | :----------------------- |
| `<NAME>` | `<What they want>`    | `<What blocks them now>` |

### 2.2 Critical Journeys

> _List only the 1–3 journeys that, if broken, make the product unusable._

| Journey       | Trigger            | Steps              | Success State              |
| :------------ | :----------------- | :----------------- | :------------------------- |
| `<JOURNEY_1>` | `<What starts it>` | `<Numbered steps>` | `<What "done" looks like>` |

---

## 3. Information Architecture

### 3.1 Sitemap

```
<Insert sitemap or screen tree here.>
```

### 3.2 Navigation

- **Primary nav:** `<e.g., top bar / sidebar / tab bar>` — `<why this fits>`
- **Default landing:** `<What the user sees on first login vs. return>`

---

## 4. Screens & States

### 4.1 Screen Inventory

| Screen ID | Name            | Purpose                     | Primary Actions      |
| :-------- | :-------------- | :-------------------------- | :------------------- |
| `SCR-001` | `<Screen name>` | `<What this screen is for>` | `<Top user actions>` |

### 4.2 Required States (per screen)

| State         | When It Appears                             | Design Approach                            |
| :------------ | :------------------------------------------ | :----------------------------------------- |
| **Loading**   | Initial fetch, mutation in flight           | `<Skeleton / spinner / optimistic update>` |
| **Empty**     | No data yet (new user, filtered to nothing) | `<Onboarding prompt / CTA>`                |
| **Error**     | Fetch/mutation failure                      | `<Inline message / retry>`                 |
| **Populated** | Normal happy path                           | `<Default rendering>`                      |

### 4.3 Wireframes

`<Link to wireframes / Figma / inline ASCII layout.>`

---

## 5. Component System

### 5.1 Library

| Layer            | Source                                   |
| :--------------- | :--------------------------------------- |
| **Base library** | `<e.g., shadcn/ui, MUI, Chakra, custom>` |
| **Icons**        | `<e.g., Lucide, Heroicons>`              |

### 5.2 Design Tokens

| Group          | Source / Reference                          |
| :------------- | :------------------------------------------ |
| **Color**      | `<Palette source — e.g., Tailwind theme>`   |
| **Typography** | `<Type scale, font families>`               |
| **Spacing**    | `<Base unit + scale — e.g., 4px base>`      |
| **Radius**     | `<Border radius scale>`                     |

---

## 6. Accessibility Minimum

- **WCAG target:** 2.1 AA.
- **Keyboard:** Every interactive element reachable via Tab with a visible focus ring.
- **Contrast:** Body text ≥ 4.5:1, large text & UI ≥ 3:1.
- **Color alone never conveys meaning** — pair with icon, text, or shape.
- **Touch targets:** ≥ 44×44px.
- **Respect `prefers-reduced-motion`.**

---

_Revisit when the IA changes, a new critical journey is added, or accessibility targets shift._
