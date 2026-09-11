# ADR 0001 — Record architecture decisions

**Status:** Accepted
**Date:** 2026-07-09

## Context

MANSOUR Vision is intended for sale to government agencies and large event
organizers. Procurement review, security accreditation, and privacy assessment
will each ask *why* the system is built the way it is — not just *how*. Answering
those questions from memory, months later, is how projects lose deals.

## Decision

Every architecturally significant decision is recorded here as a numbered,
immutable ADR. "Architecturally significant" means: it is expensive to reverse,
it constrains a legal or regulatory position, or it determines a failure domain.

An ADR is never edited once accepted. It is superseded by a later ADR, which
links back to it.

## Consequences

- A privacy or legal reviewer can be handed `docs/adr/` and get a complete,
  dated account of the platform's obligations and prohibitions.
- Decisions taken under time pressure are visible as such.
- The cost is discipline: a decision made in chat is not made until it is here.
