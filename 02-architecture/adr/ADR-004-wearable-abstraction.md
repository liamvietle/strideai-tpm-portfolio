# ADR-004 — Wearable Abstraction Layer

## Decision
Normalize provider-specific wearable data before it reaches core coaching services.

## Rationale
The coaching engine should not be coupled to Garmin or any other individual provider.

## Trade-offs
Adds an integration layer but simplifies future provider expansion and isolates API changes.

## Alternatives considered

### Provider-specific integration

Build the coaching pipeline directly around each wearable provider's API.

**Pros:** potentially faster for the first provider.

**Cons:** tightly couples downstream services to provider-specific schemas and makes additional integrations more expensive.

### Common StrideAI data model

Normalize provider-specific data into a common internal schema.

**Pros:** isolates provider differences, simplifies downstream processing, and makes future providers easier to add.

**Cons:** requires schema design and mapping logic up front.

## Decision rationale

Because wearable data is a core input to adaptive coaching and additional providers may be added later, provider abstraction reduces long-term coupling and protects the coaching engine from API-specific changes.
