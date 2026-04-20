# Migration Policy

This repo now treats schema evolution like this:

- `backend/schema.sql` is the canonical definition for a fresh database.
- ordered SQL files in `backend/migrations/` are the canonical path for upgrading existing databases.
- runtime schema patching in `backend/app.py` is a temporary compatibility bridge for older local databases, not the long-term place to define new product schema.

## Working Rule For New Schema Changes

When a schema change is intentional and accepted:

1. Update `backend/schema.sql`.
2. Add a new ordered migration file in `backend/migrations/`.
3. If older local databases would break without help, add the smallest possible compatibility bridge in `backend/app.py`.
4. Treat that bridge as temporary and remove or reduce it once the migration path is established.

## Guardrails

- Do not add new schema work only in `backend/app.py`.
- Do not treat draft ideas in docs as schema commitments until they land in `schema.sql` plus an ordered migration.
- Keep migration files narrowly scoped and additive where possible.

## Current Note

`2026-04-17_research_extensions.sql` is an earlier draft/reference migration from before this rule was written. It is useful background, but it is not the current migration standard by itself.
