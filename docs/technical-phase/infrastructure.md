# Infrastructure — Novum

> Deploy topology, hosting choices, cost analysis. Companion to [tech-stack.md](tech-stack.md) and [architecture.md](architecture.md).
>
> **Status legend:** ✅ locked · 🤔 proposed (pending confirmation) · ⏳ V2.

---

## 1. Topology at a glance

```
┌─────────────────────┐         ┌──────────────────────────────────────┐
│  User browser       │         │  Oracle Cloud Ampere ARM (free tier) │
│                     │         │  Ubuntu 22.04 LTS · 2 OCPU / 12 GB   │
│   ┌─────────────┐   │  HTTPS  │                                      │
│   │ Vercel CDN  │───┼─ static │   ┌─────────────┐                    │
│   │ (frontend)  │   │         │   │  Caddy 443  │ auto-TLS           │
│   └─────────────┘   │         │   └──────┬──────┘                    │
│         │ fetch +   │         │          │ reverse-proxy             │
│         │ SSE       │─────────┼──────────▶                           │
│         │           │  HTTPS  │   ┌──────▼──────────────────┐        │
│         ▼           │         │   │  uvicorn :8000          │        │
│   ┌─────────────┐   │         │   │  FastAPI (workers=1)    │        │
│   │ React app   │   │         │   │  agent loop + SSE       │        │
│   └─────────────┘   │         │   └──┬───────────────┬──────┘        │
└─────────────────────┘         │      │ asyncpg       │ httpx         │
                                │      ▼               │               │
                                │   ┌──────────────┐   │               │
                                │   │ PostgreSQL 16│   │               │
                                │   │ localhost    │   │               │
                                │   │ :5432        │   │               │
                                │   └──────────────┘   │               │
                                │   ┌──────────────┐   │               │
                                │   │ /backup/     │   pg_dump daily   │
                                │   └──────────────┘   │               │
                                │                      ▼               │
                                │                                      │
                                └────────┬────┬────────────────────────┘
                                         │    │
                       ┌─────────────────▼┐  ┌▼──────────────────┐
                       │ GitHub Models    │  │ Tavily API        │
                       │ (LLM gateway)    │  │ (web search)      │
                       └──────────────────┘  └───────────────────┘
                                              ┌───────────────────┐
                                              │ Wikipedia API     │
                                              └───────────────────┘
```

---

## 2. Frontend hosting · Vercel ✅

| Property | Value |
|---|---|
| Provider | Vercel |
| Plan | Hobby (free) |
| Build | `npm run build` → `dist/` |
| Framework preset | Vite |
| Preview deploys | Per PR, free |
| Custom domain | Not required for V1 (auto `.vercel.app`) |
| CDN | Global edge (100+ locations) |
| Tarjeta requerida | No |

**Why Vercel:**
- Best-in-class for Vite + React.
- Global CDN → demo from any reviewer location feels fast.
- Preview deploys per PR for free → iterate UI without touching production.
- Rollback = one click.
- Frontend stays up even if the Oracle VM is being redeployed (mitigates R10).

**Environment variables (Vercel dashboard):**
- `VITE_API_URL` → `https://<oracle-vm>.duckdns.org`
- `VITE_DEMO_SLOWDOWN` → `1` (or higher for slow demos)

---

## 3. Backend hosting · Oracle Cloud Ampere ARM ✅

### 3.1 Compute

| Property | Value | Rationale |
|---|---|---|
| Provider | **Oracle Cloud Infrastructure (OCI)** | Largest always-free tier in the market (Ampere A1 4 OCPU / 24 GB total across VMs). |
| Tier | **Always Free** | Truly free indefinitely (vs trial credits). Card required for verification only — no charges on free tier. |
| Region | TBD (closest to user — São Paulo or Querétaro) | Latency to LLM providers and to reviewers. |
| Shape | **VM.Standard.A1.Flex** | ARM Ampere — free tier eligible. |
| CPU | **2 OCPU** (half of free allowance) | Leaves headroom for a second VM if V2 splits services. |
| RAM | **12 GB** | Way more than needed; gives generous safety margin. |
| Boot volume | 50 GB | Default; sufficient. |
| Data volume | Block volume mounted at `/data` ⏳ V2 (optional) | V1 uses boot volume; V2 may split for backup independence. |
| OS | **Ubuntu 22.04 LTS ARM64** | Cleaner than Oracle Linux for our stack; mainstream APT packages. |

### 3.2 Network and TLS

| Property | Value | Rationale |
|---|---|---|
| Reverse proxy + TLS | **Caddy v2** ✅ | Auto-TLS via Let's Encrypt, zero-config. SSE-friendly with `flush_interval -1`. Simpler than Nginx for this use case. |
| Domain | **DuckDNS** (`novum-xxx.duckdns.org`) ✅ | Free, no card, no manual renewal. Alternative: `nip.io` (zero-config) if DuckDNS feels too rough. |
| Caddyfile (sketch) | `tu-dominio.duckdns.org { handle /api/* { reverse_proxy localhost:8000 } handle /events/* { reverse_proxy localhost:8000 { flush_interval -1 } } }` | SSE buffering disabled on the `/events/*` path. |
| Firewall (Oracle) | Security List: 443 open to world, 22 to your IP only | Layered with `ufw` on the VM. |
| Firewall (host) | **ufw** allowing 22 (your IP), 443 (world) | Defense in depth. |

### 3.3 Process management

| Property | Value | Rationale |
|---|---|---|
| Supervisor | **systemd units** ✅ | Native to Ubuntu, restart-on-failure, journal logs. Simpler than Docker for two services. |
| App service file | `/etc/systemd/system/novum.service` | Runs `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`. Depends on `postgresql.service` via `After=` / `Requires=`. |
| Database service | `postgresql.service` (apt-managed) ✅ | Default Ubuntu Postgres 16 unit. Auto-starts on boot. Bound to `127.0.0.1` only (no public exposure). |
| App user | dedicated `novum` user, no shell | Defense in depth. |
| DB role | `novum` Postgres role owning database `novum` | App connects via password from `DATABASE_URL`. |
| Connection | `localhost:5432` over the loopback interface | No TLS needed (loopback only). |

**Alternative considered:** Docker + Docker Compose. Discarded for V1 because:
- One service, one binary → containerization adds complexity without isolation benefit.
- systemd integrates with journalctl for free logging.
- ARM image build adds 5–10 min to deploy time.
- Add back in V2 if multiple services emerge.

### 3.4 Persistence layout

```
/var/lib/postgresql/16/main/    # Postgres data dir (apt default)
/backup/                        # cron-managed daily pg_dump
└── <yyyymmdd>/novum.dump       # pg_dump --format=custom output
```

**Tables (managed by Alembic migrations in `backend/alembic/versions/`):**
- `users` — `id`, `username` (unique), `token_hash`, `created_at`.
- `runs` — `id`, `owner_username` FK, `started_at`, `stopped_at`, `stop_reason`, `question`, `user_context`, `output_format`, `confidence_threshold`, `question_type`, `parent_run_id` FK, `forked_at_event_id`.
- `events` — `id`, `run_id` FK, `parent_event_id` FK, `step_index`, `type`, **`payload JSONB`**, `created_at`.

| Aspect | Value | Rationale |
|---|---|---|
| Engine | **PostgreSQL 16** (apt `postgresql-16` package) | Mature, ARM64 wheels for asyncpg, JSONB for payload flexibility. |
| Storage location | `/var/lib/postgresql/16/main/` | Default Ubuntu location — on the 50 GB boot volume. |
| Concurrency | Postgres MVCC + app-level "one agent task per run_id" discipline | No filelock needed. The agent task is the sole writer for its run; readers see committed events via the SSE catch-up query. |
| Disk usage estimate | ~5 KB/event × 30 events × 50 runs ≈ 7.5 MB demo | Boot volume's 50 GB is comically oversized → fine. |
| Backups | **cron daily** `pg_dump --format=custom -d novum -f /backup/$(date +%F)/novum.dump` + 7-day retention | Custom format supports selective restore. |
| Off-host backup | ⏳ V2 — Oracle Object Storage (also always-free, 20 GB) | Adds protection against VM loss. Out of V1 scope. |
| Recovery from VM loss | Manual re-provision + `pg_restore` from local laptop backup | Accept the risk; V1 is demo-grade. |
| Migrations | `alembic upgrade head` on every deploy (idempotent) | Versioned in git under `backend/alembic/versions/`. |

### 3.5 Deploy

| Property | Value | Rationale |
|---|---|---|
| Method | **GitHub Actions → SSH + `git pull` + `uv sync` + `alembic upgrade head` + `systemctl restart novum`** ✅ | Reproducible deploys + audit trail in the GitHub UI. ~30 min one-time setup, amortized from the second deploy onward. |
| Workflow file | `.github/workflows/deploy-backend.yml` | Triggered on push to `main`. |
| Secrets in CI | `ORACLE_SSH_KEY` + `ORACLE_HOST` + `ORACLE_USER` as GitHub Actions secrets | Standard. |
| Build location | On the VM (`uv sync`) | Avoids cross-arch wheel issues; uv handles it. |
| Migration step | `alembic upgrade head` runs **after** `git pull` and **before** `systemctl restart novum` | Idempotent; safe to run on every deploy. |
| Frontend deploy | Pushed via Vercel's git integration on `main` push | Independent of backend deploy. |
| Rollback | `git revert` + push → redeploys previous commit. No blue-green in V1. | Acceptable for demo. Alembic `downgrade` reserved for true emergencies. |

### 3.6 Monitoring and ops

| Aspect | V1 approach | Rationale |
|---|---|---|
| Logs | `journalctl -u novum -f` (app) + `journalctl -u postgresql -f` (db) | Plain-text greppable. No SaaS dependency. |
| Health endpoint | `GET /health` returns `{ ok, uptime, db_ok, last_run_at }` | Includes a `SELECT 1` round-trip to the DB. |
| Uptime monitoring | ⏳ optional — UptimeRobot free tier (50 monitors, 5-min cadence) | Useful before demo day. |
| Metrics | Script `scripts/metrics.py` querying Postgres | Covers KPIs 1/2/3/5 of RF §6-bis via aggregate SQL. |
| Alerting | None in V1 | Demo system; reviewer is the alert. |

---

## 4. External providers

### 4.1 LLM · GitHub Models ✅

| Property | Value |
|---|---|
| Endpoint | `https://models.github.ai/inference` |
| Auth | `Authorization: Bearer <GITHUB_TOKEN>` (PAT) |
| Free tier | Daily request limits per tier (Low / High models) |
| SDK | OpenAI-compatible → wrapped by **litellm** with `model="github/<provider>/<model>"` |
| Models in use | `meta/Llama-4-Scout`, `deepseek/DeepSeek-V3`, `openai/gpt-5` (see tech-stack §2.3) |
| Tarjeta | No |

**Free-tier limits (May 2026, approximate):**
- Low-tier models (Llama Scout): ~150 req/day, 50 req/min.
- High-tier models (GPT-5, DeepSeek-V3): ~50 req/day, 10–15 req/min.
- ~5–8 LLM calls per run → ~6–8 full runs per day on the High models on the free tier.

**Mitigation during build:** use Llama Scout for every role during development; switch to the final assignment for validation and demo.

### 4.2 Search · Tavily ✅

| Property | Value |
|---|---|
| Endpoint | `https://api.tavily.com/search` |
| Auth | `api_key` in body |
| Free tier | **1000 searches/month**, no card |
| SDK | `tavily-python` |
| Tarjeta | No |

Plenty for the 4–6h build + ~50 testing runs + 3 demo runs. Documented as a non-guarantee (R4).

### 4.3 Wikipedia · `wikipedia-api` ✅

| Property | Value |
|---|---|
| Endpoint | Wikimedia REST + Action API |
| Auth | None (User-Agent header required) |
| Free tier | Unlimited at our scale |
| Tarjeta | No |

Heterogeneity provider (RF-04 minimum source set).

---

## 5. Cost analysis

### 5.1 Steady-state monthly cost (after deploy)

| Component | Cost | Notes |
|---|---|---|
| Vercel Hobby | $0 | Always free for personal use within limits. |
| Oracle Cloud Ampere | $0 | Always-free tier, no expiration. |
| PostgreSQL 16 (self-hosted) | $0 | Apt package on the Oracle VM. Uses ~150 MB RAM idle — trivial vs the 12 GB allowance. |
| GitHub Models | $0 | Within free-tier rate limits. |
| Tavily | $0 | Within 1000/month free tier. |
| Wikipedia API | $0 | Unlimited free. |
| DuckDNS | $0 | Free DNS service. |
| Let's Encrypt (via Caddy) | $0 | Free TLS certificates. |
| GitHub Actions | $0 | Public repo or 2000 min/month free for private. |
| **Total** | **$0/month** | Indefinite. |

### 5.2 One-time / build-phase cost

| Item | Cost | Notes |
|---|---|---|
| Domain name (optional) | $0–$15/year | Skippable — DuckDNS suffices. |
| Personal time | Yours | Already budgeted as 4–6 h for build + ~1 h for infra setup. |
| **Total cost to ship V1** | **$0** | If GitHub Models stays free; if reviewer demos exceed limits in one day, ~$5 of OpenAI direct on hand as failsafe. |

### 5.3 Cards required

| Service | Card required? |
|---|---|
| Vercel | No |
| Oracle Cloud | **Yes** (verification only — no charges on always-free tier) |
| GitHub Models | No (just PAT) |
| Tavily | No (Google login suffices) |
| DuckDNS | No (GitHub login suffices) |

**Único punto que requiere tarjeta:** Oracle Cloud, y solo para verificación. Si esto es bloqueante, alternativa = **HuggingFace Spaces (Docker)** sin tarjeta pero con menos control. Documentado en understanding-phase but Oracle is locked.

### 5.4 Plan B for demo day (R10)

| Aspect | Setup |
|---|---|
| Fallback backend | **`localhost:8000` + Cloudflare Tunnel** (`cloudflared tunnel`) |
| Activation time | ~30 seconds (`cloudflared tunnel --url localhost:8000`) |
| Cost | $0 |
| Switch in frontend | Change `VITE_API_URL` in Vercel env vars, redeploy (~30s) |

Documented in the trust contract (§6-quater non-guarantees).

---

## 6. Pending decisions

| # | Decision | Default if not raised |
|---|---|---|
| 1 | Oracle region selection | TBD when provisioning |
| 2 | Whether to add Oracle Object Storage for off-host backups in V1 | Skip in V1 |
| 3 | UptimeRobot or similar pre-demo | Optional, add the week of the demo |

---

## 7. Provisioning checklist (when we get there)

> Pre-build infra setup — estimated **~1 hour total**.

1. Create Oracle Cloud account, verify card.
2. Provision VM.Standard.A1.Flex (2 OCPU / 12 GB / 50 GB boot) on Ubuntu 22.04 ARM.
3. Open port 443 in Security List; restrict 22 to my IP.
4. SSH in, run `apt update && apt upgrade`.
5. Create `novum` user, install Python 3.12, `uv`, Caddy.
6. `apt install postgresql-16` → confirm bound to `127.0.0.1` only; create role `novum` and database `novum` owned by it; store the password.
7. Register DuckDNS subdomain, point A record to VM public IP.
8. Write Caddyfile, point at `localhost:8000`, validate auto-TLS handshake.
9. Create systemd unit for the app (with `Requires=postgresql.service`), dummy uvicorn app, verify reverse proxy works.
10. Set `DATABASE_URL` in `.env`; run `alembic upgrade head` to create the initial schema.
11. Create Vercel project linked to repo, set `VITE_API_URL`, verify a 200 response from `/health`.
12. Configure cron for `pg_dump` daily backups with 7-day retention.
13. Configure GitHub Actions deploy workflow (`.github/workflows/deploy-backend.yml`); store `ORACLE_SSH_KEY` + `ORACLE_HOST` + `ORACLE_USER` as repo secrets; ensure the workflow runs `alembic upgrade head` after `git pull`.
14. Run a dry deploy: `git push` triggers Vercel + GH Actions; backend updates, frontend updates.
15. Document the URLs and the rollback procedure in `README.md`.
