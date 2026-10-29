# Supabase → Compose DB Implementation Plan

> **For agentic workers:** Steps use checkbox syntax. Execute task-by-task.

**Goal:** Stop Supabase as runtime DB; restore full dump into Compose Postgres; document Mac-server Compose ops; drop CI/Vercel Supabase DB coupling.

**Architecture:** One-shot `pg_dump`/`pg_restore` via `scripts/migrate_from_supabase.sh`, then default `docker-compose.yml` only.

**Tech Stack:** Docker Compose, Postgres 16, Flask/Alembic, Vercel env (remove DB URL).

## Global Constraints

- Do not commit `.env`, dumps, or real API keys.
- Hub must not share DB write with PM.
- Keep `apps/routes` · `apps/services` layout.

---

### Task 1: Migration script + ignore dumps

**Files:**
- Create: `scripts/migrate_from_supabase.sh`
- Modify: `.gitignore` (`tmp/`)

**Steps:**
- [ ] Script: require `SUPABASE_DATABASE_URL`, normalize to `postgresql://`, dump with dockerized `postgres:16` client if host lacks `pg_dump`, start compose `db`, restore with `--clean --if-exists --no-owner --no-acl`, print row counts.
- [ ] Add `tmp/` to `.gitignore`.

### Task 2: Docs / compose / CI / env example

**Files:**
- Modify: `docker-compose.supabase.yml` (deprecated banner)
- Modify: `README.md`, `.env.example`, `.github/workflows/ship.yml`
- Deprecate: `scripts/migrate_to_supabase.sh` comment pointing reverse script

**Steps:**
- [ ] README: Mac Compose primary; Supabase section → “이전 완료/중단”; Vercel note: no Hub DB.
- [ ] Remove `supabase` job from `ship.yml`.
- [ ] `.env.example`: compose URL default; Supabase lines as historical only.

### Task 3: Run migration + switch runtime

**Steps:**
- [ ] Stop scheduler (avoid writes during dump).
- [ ] Run migrate script using current Supabase URL from env (do not print secrets).
- [ ] `docker compose up -d --build` without supabase overlay.
- [ ] Verify healthz, row counts, `flask db current`.

### Task 4: Vercel env

**Steps:**
- [ ] Remove production `DATABASE_URL` pointing at Supabase (vercel env rm) or document if CLI lacks auth.
- [ ] Redeploy optional; expect DB-less Vercel behavior per design.
