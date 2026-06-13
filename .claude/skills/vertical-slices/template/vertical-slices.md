# <Project> - <Phase> Vertical Slices

## Metadata

- **Source PRD:** `project/specs/<phase>/prd.md`
- **Other inputs:** <other specs read, or "none">
- **Slices:** <N>

## Slice Map

| Slice | Name   | Requirements   | Depends on | Demo proves |
| ----- | ------ | -------------- | ---------- | ----------- |
| VS-001 | <name> | <FR-xxx, ...>  | -          | <one line>  |

## Slices

### VS-001 - <Name>

- **Goal:** <one line - the user-visible behavior this slice delivers>
- **Requirements:** <FR-xxx (full); FR-yyy (partial - deferred: <what>, to VS-zzz)>
- **End-to-end path:** <UI surface> -> <logic> -> <data/service>
- **In:** <one line - the thin scope included>
- **Out:** <one line - what is trimmed and the slice it moves to>
- **Demo:** <1-3 numbered steps a human runs to prove the slice works>
- **Depends on:** <earlier slice IDs, or "-">

*Repeat the section above for every slice.*

## Coverage

| Requirement | Slices |
| ----------- | ------ |
| FR-001      | VS-001  |

- **Cross-cutting NFRs:** <each NFR and the slice where it first becomes testable>
- **Exclusions (non-goals):** <out-of-scope items restated from the PRD>

## Open Questions

- <unknowns that affect slicing, or "none">
