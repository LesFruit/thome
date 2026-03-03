# Documentation Index (RAG-Graph Style)

This index provides structured navigation across all project documentation.
It maps documents, their relationships, and retrieval tags for both human reviewers
and AI-assisted retrieval.

## Document Nodes

| ID | Title | Path | Purpose | Owner | Last Verified |
|----|-------|------|---------|-------|---------------|
| D-001 | Requirements Plan | `REQUIREMENTS.MD` | Single-source-of-truth recreation plan | Project | 2026-03-03 |
| D-002 | README | `README.md` | Setup, API reference, project structure | Project | 2026-03-03 |
| D-003 | AI Usage Report | `docs/AI_USAGE.md` | AI-driven development evidence log | Project | 2026-03-03 |
| D-004 | Documentation Index | `docs/INDEX.md` | This file — graph navigation | Project | 2026-03-03 |
| D-005 | Environment Config | `.env.example` | Required env vars and defaults | Platform | 2026-03-03 |

## Relationship Edges

| Source | Target | Relationship | Notes |
|--------|--------|-------------|-------|
| D-002 | D-001 | depends_on | README references requirements |
| D-003 | D-001 | verified_by | AI log traces back to requirements |
| D-004 | D-002 | related_to | Index references all docs |
| D-005 | D-002 | related_to | README links to env config |

## Retrieval Tags

| Tag | Documents |
|-----|-----------|
| `feature` | D-001 |
| `setup` | D-002, D-005 |
| `ai_evidence` | D-003 |
| `ops_area` | D-005 |
| `navigation` | D-004 |

## Start Here (Reading Paths)

**For implementers:** D-001 (requirements) → D-002 (setup) → D-005 (env) → code

**For reviewers:** D-003 (AI usage) → D-001 (requirements) → D-004 (index) → tests → evidence

---

*This index is updated as new documents are added.*
