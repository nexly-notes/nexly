# Architecture (MVP)

**Project:** `<PROJECT_NAME>` · **Version:** `<VERSION>` · **Date:** `<DATE>` · **Status:** Draft / In Review / Approved

---

## 1. Purpose

> What problem does this system solve, and for whom? One paragraph.

`<Purpose statement.>`

**In scope:** `<features included>`
**Out of scope:** `<what's explicitly excluded>`

---

## 2. Key Decisions

> Each row is an ADR. Add rows as decisions are made; mark superseded ones rather than deleting.

| ID  | Decision     | Why it was chosen            | Trade-off accepted  |
| :-- | :----------- | :--------------------------- | :------------------ |
| 001 | `<Decision>` | `<Constraint that drove it>` | `<What we give up>` |
| 002 |              |                              |                     |

---

## 3. Tech Stack

> Only decided choices. Undecideds belong in PRD §7 Open questions.

**Style:** `<Modular monolith / Microservices / Serverless / Event-driven>` — `<one-line rationale>`

| Layer              | Tech                                         |
| :----------------- | :------------------------------------------- |
| Language / runtime | `<e.g., TypeScript on Node 20>`              |
| Frontend           | `<framework, state, hosting>`                |
| Backend / API      | `<framework, REST/GraphQL/gRPC, validation>` |
| Datastore          | `<engine, hosting, ORM, pooling>`            |
| Async / jobs       | `<runner, or N/A>`                           |
| Auth               | `<provider, method>`                         |
| Infra / hosting    | `<platform(s)>`                              |

**Module boundaries:** `<one or two rules — e.g., transport may import core; core may not import transport.>`

---

## 4. Data Flow

> Happy path for the most critical user interaction. Be specific about where auth and validation happen.

```
1. <user action>
2. <transport / routing / auth check>
3. <validation>
4. <business logic>
5. <data access>
6. <response>
```

**Async flows (if any):** `<trigger → producer → consumer; retry/DLQ policy>`

---

## 5. Risks

| Risk     | Likelihood       | Impact           | Mitigation        |
| :------- | :--------------- | :--------------- | :---------------- |
| `<risk>` | Low / Med / High | Low / Med / High | `<how mitigated>` |

**Assumptions that, if wrong, change the design:** `<e.g., traffic stays below X; auth model stays simple>`

---

_Revisit whenever a new integration is added, the auth model changes, or a significant architectural decision is made._
