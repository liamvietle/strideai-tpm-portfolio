# Jira-Style MVP Backlog

## Epic 1 — Wearable Data Integration

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-001 | Garmin authentication & connection | P0 | Backend/API | 1 | Garmin API |
| STRIDE-002 | Normalize wearable workout data | P0 | Backend/API | 1–2 | 001 |
| STRIDE-003 | Workout synchronization | P0 | Backend/API | 2 | 002 |

## Epic 2 — Data & Training Intelligence

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-004 | Training-load calculation | P0 | Data Science | 2–3 | 002 |
| STRIDE-005 | Recovery signal processing | P0 | Data Science | 2–3 | 002 |
| STRIDE-006 | Fatigue model | P0 | Data Science | 3–4 | 004,005 |

## Epic 3 — Adaptive Coaching

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-007 | Recommendation confidence engine | P0 | DS + Backend | 3–4 | 006 |
| STRIDE-008 | Workout adaptation engine | P0 | Backend | 4 | 006,007 |
| STRIDE-009 | Safety rules engine | P0 | Backend + DS | 3–4 | 006 |
| STRIDE-010 | Recommendation explanation | P0 | AI/Backend | 4 | 008,009 |

## Epic 4 — Product Experience

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-011 | Display adaptive workout | P0 | Mobile | 4–5 | 008,010 |
| STRIDE-012 | User confirmation / override | P0 | Mobile + Backend | 5 | 011 |

## Epic 5 — Reliability

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-013 | Asynchronous workout processing | P0 | Platform | 1–2 | — |
| STRIDE-014 | Autoscaling | P1 | Platform | 4–5 | 013 |
| STRIDE-015 | Monitoring & alerting | P0 | Platform | 3–5 | 013 |

## Epic 6 — Quality & Safety

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-016 | Recommendation evaluation framework | P0 | Data Science | 2–3 | 004–006 |
| STRIDE-017 | Safety test suite | P0 | QA + DS | 4–5 | 009 |
| STRIDE-018 | Load/performance testing | P1 | Platform + QA | 5 | 014,015 |

## Epic 7 — Launch

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-019 | Internal beta | P0 | TPM + Product | 6 | 017,018 |
| STRIDE-020 | Controlled customer rollout | P0 | TPM + Product | 6+ | 019 |
| STRIDE-021 | Rollback mechanism | P0 | Platform | 5–6 | 015 |

## Epic 8 — Incident Recovery

| ID | Story | Priority | Owner | Sprint | Dependency |
|---|---|---|---|---|---|
| STRIDE-022 | Wearable outage handling | P0 | Backend + TPM | 5 | 003 |

## Six-week plan

| Week | Focus |
|---|---|
| 1 | Architecture, integration, queue, schemas |
| 2 | Data ingestion + first end-to-end slice |
| 3 | Training load, recovery, fatigue |
| 4 | Adaptation, safety, explanation |
| 5 | Integration, performance, monitoring |
| 6 | Internal beta + controlled rollout |

**Critical milestone:** By end of Week 2, one real workout should flow end-to-end and produce a basic recommendation.
