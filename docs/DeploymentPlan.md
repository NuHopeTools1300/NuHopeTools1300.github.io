# Deployment Plan

Updated: May 3, 2026

This is the current deployment direction. It is not yet an implementation checklist for public launch.

## Current Local Shape

- Frontend: static HTML/CSS/JS in this repository
- Backend: local Flask API
- Database: local SQLite at `backend/data/ilm1300.db`
- Runtime files: local `backend/data/uploads/` and `backend/data/part_images/`
- Operator database browsing: Datasette sidecar

## Near-Term Private Deployment

Use the simplest stack that keeps private research moving:

- GitHub Pages or Cloudflare Pages for static frontend files
- Flask backend on Render, Fly, Railway, or a VPS
- Persistent volume for SQLite while the project remains private/small
- Image files either on a backend persistent volume or external object storage
- Environment variables for admin/API secrets

This keeps the current architecture intact while avoiding a premature database migration.

## Later Public/Semi-Public Deployment

Before broader contributor access, move toward:

- containerized Flask backend served by a production WSGI server
- managed Postgres instead of SQLite
- object storage for images, with CDN if needed
- automated database backups
- explicit auth and role model for trusted contributors
- deployment checks that run `tools/verify.ps1` or an equivalent CI workflow

## Access Control Direction

Current local admin behavior is intentionally operator-friendly:

- `X-API-Key` when `ADMIN_API_KEY` is configured
- `X-Admin-Local: 1` for local trusted work

For remote/private deployment, use API keys or a small token allowlist first. Do not treat local admin headers as remote authentication.

For public/community phases, use a real contribution workflow with review and moderation instead of exposing direct database editing.

## Storage Direction

Short term:

- keep local/runtime files out of git
- keep `backend/data/` ignored
- keep private archives out of normal source-control churn

Long term:

- store images in S3/GCS/R2 or equivalent object storage
- store stable storage keys/URLs in `images`
- use signed URLs or backend proxying if private access is required

## Decision Points Before Launch

- Render/Fly/Railway/VPS backend host
- SQLite with persistent disk vs managed Postgres migration timing
- image storage provider
- auth model for trusted contributors
- backup cadence and restore test
- whether Datasette remains local-only or gets a protected operator deployment

