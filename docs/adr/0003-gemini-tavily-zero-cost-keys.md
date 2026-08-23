# ADR 0003 — LLM Gateway with Gemini Primary + Tavily ($0 MVP Keys)

- **Status:** Accepted
- **Date:** 2026-08-23

## Context

Budget is a hard constraint (student). Every agent needs chat models and embeddings;
Search/Research agents need web results. Keys must never reach the frontend; providers
must stay replaceable; every call should be logged for cost observability.

## Decision

All model traffic flows through a single **LLM Gateway** module (model router, prompt
registry, token/cost accounting, Redis response cache, provider adapters). MVP keys:
**one free Gemini API key** (chat + embeddings via text-embedding-004) and **one free
Tavily key** (search, 1k req/mo). OpenAI/Anthropic adapters are optional fallbacks —
not required. Ollama provides unlimited local testing so development burns zero quota.
Total required paid spend for MVP: **$0**.

## Consequences

+ One place for retries/fallbacks/logging; swapping providers = one adapter file
+ Free-tier-first economics with cost visibility from day one
− Gemini rate limits on free tier (mitigated: routing, caching, Ollama for dev)
