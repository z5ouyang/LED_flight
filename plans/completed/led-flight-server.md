# LED Flight Server

## Status

| Field | Value |
|-------|-------|
| Stage | completed |
| Type | plan |
| Created | 2026-04-05 |
| Last Updated | 2026-04-07 11:41 |
| Author | Tim / Claude |
| Approver | Tim |
| Plan Review | completed |
| Review Date | 2026-04-05 |
| PM Review | required |
| PM Review Date | - |
| Execution Approved | no |
| Execution Approved By | - |
| Execution Started | - |
| AI Developer Ready | yes |
| AI Developer Ready By | Tim |
| AI Developer Ready Date | 2026-04-05 |
| AI Developer Ready Iteration | 1 |
| Implementation Verified | yes |
| Implementation Verified By | Tim |
| Implementation Verified Date | 2026-04-07 |
| Remediation Plan | - |
| Last Run | - |
| Last Result | - |
| Run Count | 0 |

### Progress Log

| Timestamp | Phase | Notes |
|-----------|-------|-------|
| 2026-04-05 | draft | Plan created |
| 2026-04-05 | review | Full 7-phase tech review: 51+ issues fixed across tech accuracy, adversarial analysis, security, AI-readiness, goal alignment, PM, user advocate |

---

## Overview

Centralized server for the LED Flight platform at `flights.truefol.com`. Replaces direct device-to-FR24 API calls with a managed architecture: server polls flight data once per region, stores it in Postgres, and pushes to devices over WebSocket. Includes user management, device registration (claim codes), firmware OTA, and flight alerts.

This is a commercial product. All architecture decisions assume multi-tenant, multi-user from day one.

### Architecture

```
[Flightradar24 API]
        │
        ▼ (one poll per region)
[flights.truefol.com]
   ├── FastAPI backend
   ├── React/TS frontend (admin portal)
   ├── PostgreSQL (flights, devices, users)
   └── WebSocket server (device + admin comms)
        │                        │
        │ WebSocket (devices)    │ OIDC
        │                        ▼
   ┌────┼────┐            [Zitadel]
   ▼    ▼    ▼         (separate service)
  [Pi] [Pi] [MatrixPortal]
```

### Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (async) |
| Frontend | React + TypeScript + Tailwind (Vite build) |
| Database | PostgreSQL |
| ORM | SQLAlchemy + Alembic |
| Validation | Pydantic (backend) + Zod (frontend) |
| Auth | Zitadel OIDC |
| Device comms | WebSocket (bidirectional) |
| Deployment | k3s via ops.sh ship |
| Domain | flights.truefol.com (Traefik + cert-manager) |
| Shared lib | tim-lib |

### Repo

`/Volumes/External/Git/LED_flight_server/` — private GitHub repo `LED_flight_server`.

### Key Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| FR24 shuts down public API or adds auth | Total loss of flight data | Abstract FR24 behind a `FlightDataSource` interface. Design poller to support swapping in alternative sources (ADS-B Exchange, OpenSky). For now, FR24 is the only implementation, but the interface allows migration without rewriting the push/filtering layer. |
| WebSocket instability on ESP32-S3 | Frequent device disconnects, poor UX | The reconnection protocol handles this. Additionally, device should cache last flight data in RAM and display it during disconnects. Validate CircuitPython WebSocket library (`adafruit_websocket` or `websocket` on ESP32) stability early in Phase 1 — if too unstable, implement HTTP long-polling as a fallback device comm mode. |
| FR24 rate-limits harder than expected | Stale flight data for some regions | Graceful degradation: extend poll intervals dynamically, prioritize regions with recently active users. Worst case: some regions get 30s or 60s polls instead of 15s. |

---

## Phase 0: Project Setup

### 0.1 — Create repo and scaffold

- Create `/Volumes/External/Git/LED_flight_server/`
- `git init`, create private GitHub repo
- Add `lib/tim` submodule (sparse-checkout, exclude plugin/marketplace dirs)
- Run `tim-sync --register .` then `tim-sync LED_flight_server`
- Create `CLAUDE.md` with project-specific context (stack: FastAPI/React/Postgres, deployment: k3s ops.sh, auth: Zitadel OIDC, project-specific patterns, link to this plan)
- Create `.tim-patterns.yaml` (register patterns: FastAPI routers, Pydantic schemas, SQLAlchemy models, Alembic migrations, WebSocket handlers)
- Configure `pyproject.toml` with: mypy strict mode, ruff linting, Python ≥3.12
- Run `tim-compliance-check.sh`
- Install tim-loop from marketplace

### 0.2 — Project structure

```
LED_flight_server/
├── server/                  # FastAPI backend
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, WebSocket
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # SQLAlchemy engine, session
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── device.py
│   │   ├── device_log.py
│   │   ├── flight.py
│   │   ├── flight_alert.py
│   │   ├── firmware_version.py
│   │   └── region.py
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── device.py
│   │   ├── flight.py
│   │   ├── firmware.py
│   │   ├── alert.py
│   │   ├── region.py
│   │   ├── ws.py            # WebSocket message schemas
│   │   └── user.py
│   ├── routers/             # API route modules
│   │   ├── devices.py
│   │   ├── flights.py
│   │   ├── firmware.py
│   │   ├── alerts.py
│   │   ├── auth.py
│   │   └── ws.py            # WebSocket endpoints (device + admin)
│   ├── services/            # Business logic
│   │   ├── flight_poller.py # FR24 polling engine
│   │   ├── device_manager.py
│   │   ├── ws_manager.py    # WebSocket connection registry, per-device state
│   │   ├── firmware.py
│   │   └── alerts.py
│   └── migrations/          # Alembic
│       └── versions/
├── web/                     # React frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Devices.tsx
│   │   │   ├── DeviceDetail.tsx
│   │   │   ├── AddDevice.tsx
│   │   │   ├── FlightHistory.tsx
│   │   │   ├── Alerts.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── App.tsx
│   ├── package.json
│   └── tsconfig.json
├── firmware/                # Device firmware versions (served to devices)
│   ├── dietpi/              # Pi firmware files
│   └── circuitpython/       # MatrixPortal firmware files
├── k8s/                     # Kubernetes manifests (ops.sh uses these directly)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingressroute.yaml    # Traefik IngressRoute CRD (not standard Ingress)
│   └── migration-job.yaml
├── tests/                   # Test directory (human-written tests only)
│   ├── conftest.py
│   └── ...
├── ops-config.yaml
├── Dockerfile               # Multi-stage: python:3.12-slim base, pip install, uvicorn entrypoint
├── docker-compose.yaml      # Local dev: postgres + server + (optional) frontend dev server
├── alembic.ini
├── pyproject.toml             # Dependencies managed via pip-tools (pip-compile)
├── requirements.txt           # Compiled from pyproject.toml
├── CLAUDE.md
└── .tim-patterns.yaml
```

### 0.3 — Infrastructure (human-executed — requires cluster access)

- Create DNS: `flights.truefol.com` → DDNS to k3s cluster
- Add Traefik IngressRoute in `k3s-infra/traefik/routes/flights.yaml` (following pattern from existing routes like `truefol.yaml`)
- TLS cert via cert-manager (Let's Encrypt, using existing `tls-truefol-wildcard` cert)
- Zitadel app registration for OIDC: create a new "Web" application in the existing Zitadel instance. Settings: auth method = PKCE, redirect URIs = `https://flights.truefol.com/callback` + `http://localhost:5173/callback`, post-logout URI = `https://flights.truefol.com/`. Scopes: `openid profile email`. Record `client_id` and `issuer_url` for server config.
- Postgres database: create database `flights` on existing central-db StatefulSet (Bitnami PostgreSQL). Connection pooling via existing PgBouncer deployment. Required extensions: `uuid-ossp` (UUID generation), `pg_trgm` (pattern matching for flight alerts).
- Vault secrets: `secret/flights/{fr24_api_key, db_password, zitadel_client_secret}` (device auth_tokens are random hex strings stored in DB, no signing key needed)
- ops-config.yaml with `project.name: "flights"` (enables `flights --env dev ship` alias)

---

## Phase 1: Server Skeleton + Device Claim Flow + Basic Admin UI

### 1.1 — FastAPI skeleton

- FastAPI app with lifespan: startup initializes DB pool, WebSocket manager, flight poller. Shutdown closes all WebSocket connections gracefully (close code 1001 "going away"), stops poller, disposes DB pool. Devices interpret 1001 as "server restarting" and reconnect immediately (skip backoff).
- SQLAlchemy async engine (`create_async_engine` with `asyncpg` driver) + Alembic migrations (async-compatible via `run_async`)
- Pydantic settings from env vars (DB URL, Zitadel issuer, FR24 key)
- Health endpoint: `GET /health` — returns simple UP/DOWN status (no internal metrics). Detailed metrics (DB connectivity, poller status, WebSocket count) available via `GET /health/detail` (admin-only, Zitadel JWT required).
- CORS middleware: allow `flights.truefol.com` origin (same-origin for production; `localhost:5173` for Vite dev server — dev-only, controlled by `ENVIRONMENT` env var)
- Security headers middleware: CSP, HSTS, X-Content-Type-Options, X-Frame-Options (required by TIM standards, applied to all responses)
- tim-lib integration: settings, logging, error handlers, database pooling

### 1.2 — Database models

**users**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| zitadel_id | str | OIDC subject, unique index |
| email | str | from OIDC claims, unique index |
| display_name | str | |
| role | enum | user, admin (default: user) |
| created_at | timestamp | |

**devices**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| serial_number | str | unique, from device hardware (see note below) |
| hardware_type | enum | dietpi, circuitpython |
| name | str | user-assigned friendly name |
| owner_id | UUID | FK → users, nullable (unclaimed) |
| claim_code | str | 6-char alphanumeric, nullable |
| claim_code_expires | timestamp | TTL for claim code |
| region_id | UUID | FK → regions, nullable (unset until user configures geo_loc) |
| firmware_version | str | currently running version |
| target_firmware_version | str | version server wants device to run |
| firmware_push_at | timestamp | scheduled push time, nullable (UTC; convert from device timezone at write) |
| last_seen | timestamp | last WebSocket heartbeat |
| config | JSONB | device-specific config (schema below) |
| auth_token | str | device bearer token, generated at registration, unique |
| created_at | timestamp | |

> **Device config JSONB schema:** Validated server-side by Pydantic before storage.
> ```json
> {
>   "brightness": 100,          // 0-255, LED brightness
>   "flip_east_west": false,    // mirror display for mounting orientation
>   "timezone": "America/Los_Angeles",  // IANA timezone for local time display
>   "altitude_min": 0,          // ft, filter flights below this
>   "altitude_max": 60000,      // ft, filter flights above this
>   "heading_filter": null,     // [min_deg, max_deg] or null for all
>   "speed_min": 0,             // knots, filter slow-moving
>   "display_time_night": false // show time instead of flights at night
> }
> ```
> These map to existing `private.json` fields: `altitude`, `altitude_rev`, `heading`, `heading_rev`, `speed`, `flip_east_west`, `display_time_night`. Server pushes config to device via `config_update` WebSocket message on any change.
>
> **Serial number sourcing:** DietPi (Pi) has `get_serial()` in `led_flight.py:51-73` which reads `/proc/device-tree/serial-number` or `/proc/cpuinfo`. CircuitPython (MatrixPortal S3) has no hardware serial — use `microcontroller.cpu.uid` (available on ESP32-S3) hex-encoded as the serial. Both paths must be implemented in the device client changes.
>
> **Indexes:** `serial_number` (unique), `owner_id`, `region_id`, `claim_code` (partial index WHERE claim_code IS NOT NULL), `last_seen` (for stale device detection).
>
> **auth_token:** Generated server-side during device registration. **Stored as SHA-256 hash in DB** (not plaintext) — compare by hashing the incoming token. Device stores the plaintext token in `private.json` and includes it in WebSocket query params and API calls. This solves the device-auth bootstrap problem — the initial `POST /api/devices/register` is unauthenticated (any device can register), but all subsequent calls require the auth_token.
>
> **Token revocation:** Admin portal provides "Regenerate Token" action per device. This invalidates the old token (device disconnects), generates a new one, and displays it once. The device must be physically accessed to update `private.json` with the new token. Use this if a token is compromised.

**regions**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| geo_loc | JSONB | `[north_lat, south_lat, west_lng, east_lng]` — matches FR24 bounds parameter order and existing `private.json` format |
| local_airport | str | IATA code, computed from geo_loc center via KD-tree (port `kdnode.py` logic) |
| timezone | str | IANA timezone (e.g., "America/Los_Angeles"), computed from geo_loc center via `timezonefinder` |
| poll_interval_sec | int | default 15 |
| last_polled | timestamp | |

> **Coordinate ordering:** The existing codebase stores geo_loc as `[tl_lat, br_lat, tl_lon, br_lon]` (see `flight_region.py:32`), passed directly to FR24's bounds parameter. The server must use this same ordering. Label consistently as `[north_lat, south_lat, west_lng, east_lng]`.
>
> **Timezone:** Each region's timezone is derived from the geo_loc center point using the `timezonefinder` Python library (offline, no API calls). This replaces the current `TIMEZONEDB_API_KEY` dependency in `flight_api.py:312`. The timezone is used for: scheduled firmware pushes (2am local), sunrise/sunset calculation, and display time on devices.
>
> **Sunrise/sunset:** Computed server-side using the `astral` Python library (offline, replaces current `api.sunrise-sunset.org` API calls). Server includes sunrise/sunset times in the device config pushed over WebSocket. Recalculated daily and pushed as `config_update`. Devices use this for brightness dimming (the existing `display_time_night` feature).
>
> **Removed `active_device_count`:** Use `SELECT COUNT(*) FROM devices WHERE region_id = ?` instead. A denormalized counter creates race conditions on concurrent claim/unclaim and adds no performance benefit at expected scale (hundreds of devices, not millions). If count queries become slow, add a materialized view later.
>
> **Indexes:** `geo_loc` (GIN index for JSONB containment queries).

**flights**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| fr24_id | str | FR24 flight index |
| region_id | UUID | FK → regions |
| flight_number | str | |
| airline_name | str | |
| aircraft_type | str | |
| aircraft_model | str | |
| origin | str | IATA |
| destination | str | IATA |
| altitude | int | |
| speed | int | |
| heading | int | |
| latitude | float | |
| longitude | float | |
| first_seen | timestamp | when flight entered region |
| last_seen | timestamp | last update |
| landed | bool | |

> **Constraints:** Unique on `(fr24_id, region_id)` — required for upsert behavior.
>
> **Indexes:** `(region_id, last_seen)` composite (primary query pattern for active flights), `(region_id, first_seen)` (history queries), `flight_number` (alert matching). The unique constraint on `(fr24_id, region_id)` serves as the upsert lookup index.
>
> **Partitioning:** With 10 regions × ~50 flights × 96 polls/day = ~48,000 upserts/day, the table will exceed 1M rows within weeks. Use declarative range partitioning on `first_seen` by month from day one. The archival job (90 days) then becomes a simple `DROP PARTITION` rather than a DELETE scan. Alembic migration creates the partitioned table structure.
>
> **Data retention:** Flights older than 90 days move to a `flights_archive` table (same schema) via a daily background job. Analytics queries join both tables. This keeps the active flights table fast while preserving history. The retention period is configurable via settings.

**flight_alerts**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| alert_type | enum | aircraft_type, flight_number, airline |
| pattern | str | e.g., "A380", "UA123", "Emirates" — case-insensitive match via `pg_trgm` |
| enabled | bool | default true |
| notify_method | enum | push, email |
| created_at | timestamp | |

> **Indexes:** `(user_id, enabled)` for active alert lookups, `(alert_type, pattern)` for poller matching.
>
> **Email notification:** Deferred to Phase 5 (requires email service integration). Phase 4 supports `push` only (WebSocket real-time banner in admin UI). The `email` enum value exists in the schema but the delivery path is not implemented until Phase 5.

**device_logs** (referenced by WebSocket `log` message type)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| device_id | UUID | FK → devices |
| level | enum | debug, info, warning, error |
| message | text | |
| created_at | timestamp | |

> **Indexes:** `(device_id, created_at)` for per-device log queries. **Retention:** Logs older than 30 days auto-deleted by daily background job. **Size limit:** `message` field capped at 4KB (reject longer messages in WebSocket handler). Rate limit: max 10 log messages per device per minute (prevents log flooding).

**firmware_versions** (referenced by Phase 3)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| version | str | semver (e.g., "1.2.0") |
| hardware_type | enum | dietpi, circuitpython |
| file_hash | str | SHA-256 of firmware archive |
| file_path | str | relative to firmware/ directory |
| release_notes | text | |
| channel | enum | stable, beta (default: stable) |
| created_at | timestamp | |

> **Constraints:** Unique on `(hardware_type, version)`. **Indexes:** `(hardware_type, channel)` for latest-version lookups.

### 1.3 — Device registration API

**Device-facing (auth: device bearer token unless noted):**
- `POST /api/devices/register` — **unauthenticated**. Device sends `serial_number` + `hardware_type`. Validate: `serial_number` must be 8-32 hex characters, `hardware_type` must be a valid enum value. If serial already registered → return HTTP 409 Conflict (do NOT return the existing auth_token — that would let anyone who knows/guesses a serial steal the device's credentials). Otherwise create device record, generate `auth_token` (cryptographically random, 64-char hex) and `claim_code` (6-char alphanumeric, uppercase, expires 1 hour). Return `{auth_token, claim_code, ws_url}`. Device stores auth_token in `private.json`. The auth_token is only ever returned ONCE — during initial registration. If the device loses its token, human intervention is required (admin portal can regenerate). **Rate limit:** 10 registrations per IP per hour (prevents abuse of unauthenticated endpoint).
- `POST /api/devices/renew-claim` — device requests new claim code (e.g., previous one expired). Server generates new code, expires old one. Returns `{claim_code, expires_at}`. Device displays new code. Rate limit: max 1 renewal per 5 minutes.

**User-facing (auth: Zitadel OIDC JWT):**
- `POST /api/devices/claim` — authenticated user sends claim_code. Server uses `SELECT ... FOR UPDATE` on the device row to prevent concurrent claims. Links device to user, clears claim_code, returns device config. **Rate limit:** 5 claim attempts per user per minute (prevents brute-force of 6-char codes). Failed attempts logged for monitoring.
- `GET /api/devices` — list user's devices
- `GET /api/devices/{id}` — device detail
- `PATCH /api/devices/{id}` — update config (name, region, brightness, etc.). **Ownership check:** server verifies `device.owner_id == authenticated_user.id` (or user is admin). geo_loc input validated: lats in [-90, 90], lngs in [-180, 180], north_lat > south_lat, region area ≤ 10,000 km² (prevents polling entire continents). Device `name` limited to 100 chars, sanitized.
- `DELETE /api/devices/{id}` — unclaim device (nulls owner_id, does NOT delete device record — device stays registered). **Ownership check** required.

> **Device lifecycle states:**
> 1. **Registered** (unclaimed): `owner_id=NULL`, `region_id=NULL`. Device displays claim code. Can connect via WebSocket but receives no flight data.
> 2. **Claimed** (no region): `owner_id=set`, `region_id=NULL`. User owns device but hasn't configured a location. Device shows "configure location in admin portal" message.
> 3. **Active**: `owner_id=set`, `region_id=set`. Device receives flight data.
> 4. **Unclaimed** (via DELETE): Returns to state 1. `owner_id=NULL`, `region_id=NULL`, new claim code generated.
>
> **Claim code expiry UX:** When claim_code expires, the device is still registered and connected via WebSocket. It can request a new claim code via `POST /api/devices/renew-claim`. The device should display a "code expired, refreshing..." message and auto-request a new code. The server sends the new code via WebSocket `claim_code` message type.

### 1.4 — WebSocket protocol

Device connects to `wss://flights.truefol.com/ws/{device_id}?v=1&token={auth_token}`. Server validates token against `devices.auth_token`. Invalid/missing token → close with 4001 (unauthorized). The `v` query parameter is the protocol version — server rejects unsupported versions with close code 4002 (unsupported protocol).

> **Auth via query param (not header):** CircuitPython WebSocket libraries may not support custom HTTP headers. Query parameter auth is used for device connections. The admin WebSocket (`/ws/admin`) uses `Authorization: Bearer {jwt}` header since browsers support it. Token in query params appears in server access logs — configure Traefik to redact `token` query parameter from access logs (or disable access logging for the `/ws/` path prefix).
>
> **WebSocket security controls:**
> - Max message size: 64KB for device→server messages (prevents memory exhaustion from malicious payloads)
> - Max 1 WebSocket connection per device_id (new connection closes existing — prevents connection exhaustion)
> - Max 50 WebSocket connections per IP (prevents single-source DoS)
> - Message type whitelist: server rejects unknown `type` values (prevents protocol abuse)
> - Admin WebSocket JWT validation: re-validate JWT every 5 minutes. If expired, close connection with 4003 (token expired). Frontend handles re-auth and reconnect.
> - All user-supplied strings (device `name`, log `message`, alert `pattern`) must be HTML-escaped before rendering in the admin UI (React's JSX does this by default — avoid `dangerouslySetInnerHTML`).

**Server → Device messages:**
```json
{"type": "flight_batch", "data": [{flight}, {flight}, ...]}
{"type": "no_flights", "data": {"local_airport": "SAN"}}
{"type": "config_update", "data": {config object}}
{"type": "firmware_update", "data": {"version": "1.2.0", "url": "/api/firmware/download/...", "sha256": "abc123..."}}
{"type": "claim_code", "data": {"code": "A3X9K2", "expires_at": "2026-04-05T13:00:00Z"}}
{"type": "error", "data": {"code": "string", "message": "string"}}
```

**Device → Server messages:**
```json
{"type": "heartbeat", "data": {"uptime": 3600, "memory": 150000, "firmware": "1.1.0"}}
{"type": "status", "data": {"displaying": "flight", "flight_number": "UA123"}}
{"type": "log", "data": {"level": "info", "message": "string"}}
```

> **Reconnection protocol:** On WebSocket disconnect, device uses exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (cap). Jitter: ±25%. No max retry limit — device retries indefinitely. During disconnection, device displays last known flight data with a "disconnected" indicator. On reconnect, server sends current flight state + any pending config_update or firmware_update messages.
>
> **Offline behavior (DietPi only):** If disconnected for >5 minutes, DietPi devices MAY fall back to direct FR24 polling (preserving the current standalone behavior as a degradation path). This keeps the display useful during server outages. MatrixPortal devices lack the memory for a full FR24 client and should display "offline" + last data. This fallback is a future enhancement — initial implementation shows "disconnected" on all devices. Flagged here so the device-side refactor doesn't delete the FR24 polling code from DietPi entirely; keep it available but inactive behind a config flag.
>
> **Log message type:** Replaces current MQTT logging (`logs/matrixportal` topic). Device sends log messages over WebSocket instead of MQTT. Server stores in a `device_logs` table or forwards to the cluster's logging infrastructure.
>
> **Heartbeat interval:** Every 30 seconds. Server marks device offline if no heartbeat received for 90 seconds (3× interval). Offline status visible in admin UI.
>
> **Config delivery on reconnect:** Server tracks pending config changes per device. On WebSocket connect, server sends the current full config as `config_update`. This ensures offline devices receive config changes when they reconnect.

### 1.5 — Basic admin UI

- Login via Zitadel OIDC (use `oidc-client-ts` library for PKCE flow)
- Dashboard: list of user's devices with status (online/offline/unclaimed), live-updating
- Add Device page: input claim code
- Device detail: name, location, status, last seen, firmware version, flight counter (total flights tracked)
- Device config: geo_loc (text input for lat/lng bounds — 4 fields), brightness slider, timezone dropdown. Map picker is a future enhancement (not in this plan's scope).

> **Real-time admin UI updates:** The frontend connects to `wss://flights.truefol.com/ws/admin` with the user's OIDC JWT. This is a separate WebSocket endpoint from the device one. Server pushes: device status changes (online/offline), alert triggers (real-time banner), flight count updates. This avoids polling and gives instant feedback when a device connects or an alert fires.
>
> **Flight counter:** The current codebase tracks a per-device flight counter (persisted to disk, see recent commit `56d0458`). The server maintains this as a derived metric: total flights matching the device's region and filters since the device was claimed (`devices.created_at`). Computed on-demand, not stored. Exposed in device detail and dashboard.

---

## Phase 2: FR24 Polling Engine + Flight Data API

### 2.1 — Region-based polling

- Background task: for each active region (at least one connected device), poll FR24 at `poll_interval_sec`
- Parse FR24 response into flight records. Upsert by `(fr24_id, region_id)` — update position/altitude/speed on existing, insert on new.
- Detect state transitions: new flights entering region (first_seen set), flights exiting (no longer in FR24 response after 2 consecutive polls), landings (altitude < threshold + speed < threshold).
- **Note:** The region-level poller fetches ALL flights within the geographic bounds. Per-device filtering (altitude, heading, speed from device config) is applied at push time in Phase 2.2, NOT in the poller. Port the geographic bounds logic from `flight_region.py` to `flight_poller.py`, but leave the altitude/heading/speed filtering to the push layer.

> **Region deduplication:** Regions are shared, not per-device. When a user sets a geo_loc for their device, the server checks for an existing region where the bounding boxes overlap by ≥80% (intersection area / union area). If found, assign the device to the existing region. If not, create a new region. Overlap is computed as a simple rectangle intersection — no geo libraries needed.
>
> **Region mutation rules:** Regions are immutable once created. If a user changes their device's geo_loc: check for an existing matching region → assign device to it (or create new). If the old region has no remaining devices, delete it (the poller skips regions with zero connected devices anyway). Regions are never edited — only created or orphaned. This avoids the complexity of "what happens when you resize a shared region."
>
> **FR24 rate limiting:** FR24's public feed endpoint has undocumented rate limits (~100 req/min observed). The poller must use a global rate limiter (token bucket, 1 request per second) shared across all region polls. On HTTP 429: back off 60 seconds, then resume. Log 429 events for monitoring. Regions are polled in round-robin order, not concurrently.
>
> **FR24 endpoints to use:** Same as existing `flight_api.py`:
> - Feed: `https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds={geo_loc}&faa=1&...`
> - Detail: `https://data-live.flightradar24.com/clickhandler/?flight={flight_id}`
>
> Port `get_flights()` and `get_flight_detail()` from `flight_api.py` to `flight_poller.py`, converting from synchronous `requests` to async `httpx`.
>
> **Flight detail caching:** The FR24 detail endpoint (`clickhandler`) is the main rate-limit bottleneck — one call per flight per poll. Flight details (airline, aircraft type, origin, destination) don't change mid-flight. Cache detail responses in-memory keyed by `fr24_id`, TTL = flight lifetime (until exited). Only call the detail API for newly discovered flights. The current code already does this (`FLIGHT_DETAILS_LATEST` global in `flight_api.py`).

### 2.2 — Flight data push

- When poller gets new data, push **delta updates** to all devices connected to that region via WebSocket — only flights that are new, changed (position/altitude moved), or exited since last push. Full state sync sent on device reconnect.
- Server formats each flight as:
  ```json
  {
    "flight_number": "UA123",
    "origin": "SFO",
    "destination": "LAX",
    "altitude": 35000,
    "speed": 450,
    "heading": 180,
    "airline_name": "United Airlines",
    "aircraft_type": "B738",
    "aircraft_model": "Boeing 737-800",
    "latitude": 34.05,
    "longitude": -118.24,
    "vertical_direction": "climbing",
    "is_new": true,
    "exited": false
  }
  ```
  This mirrors the fields the current `led_flight.py` extracts from FR24 detail responses, plus `vertical_direction` (from recent `display_helpers.py` changes) and state flags.
- Device becomes a thin renderer — no API calls, no data processing
- `no_flights` message sent when a region has zero active flights for that device (after per-device filtering)

> **Per-device filtering vs shared regions:** Regions are shared (one FR24 poll), but each device has its own config filters (altitude_min/max, heading_filter, speed_min). The server must apply per-device filters after polling:
> 1. Poller fetches all flights for the region → stores unfiltered in `flights` table
> 2. For each connected device in that region, apply the device's config filters server-side
> 3. Push the device-specific filtered result
>
> This means delta tracking is **per-device**, not per-region. The WebSocket manager maintains per-device last-sent state to compute deltas. Memory cost: ~1KB per connected device (list of flight IDs last sent). This is the correct trade-off — the alternative (pushing all flights and filtering on-device) defeats the "thin renderer" goal.

### 2.3 — Flight history API

**Auth: Zitadel OIDC JWT.** Users can only query regions associated with their devices.

- `GET /api/flights?region_id=&date=&page=&per_page=50` — paginated flight history. Server validates that the authenticated user owns a device in the requested region. Returns flights from both `flights` and `flights_archive` tables transparently.
- `GET /api/flights/stats?region_id=&period=day|week|month` — stats: flights per period, unique airlines, aircraft types, busiest hours
- Frontend: Flight History page with table, filters, date range picker

---

## Phase 3: Firmware Management

### 3.1 — Firmware registry

- `firmware/` directory in repo stores versioned firmware files per hardware type. CircuitPython files are `.py` (small, git-friendly). DietPi files are Python scripts from the LED_flight repo — no binaries, so standard git is sufficient (no git-lfs needed).
- DB table `firmware_versions` tracks metadata (defined in Phase 1.2 models). `file_path` points to the file in the `firmware/` directory, committed to git. The file is served directly by FastAPI at download time.
- **Upload workflow:** Developer commits firmware files to `firmware/{hardware_type}/{version}/` in git → deploys server via `flights --env dev ship` (bakes firmware into container image) → admin UI "Register Version" form reads the committed files from disk, computes SHA-256 hash, creates `firmware_versions` DB record. New firmware requires a server deploy before registration. This is intentional — it ensures firmware files pass CI validation before becoming available to devices. No file upload via HTTP — files come from the deployed container.
- Admin UI: register firmware version, view version history, mark version as stable/beta, compare versions

### 3.2 — Firmware distribution

- `GET /api/firmware/download/{hardware_type}/{version}` — authenticated via device bearer token or user OIDC JWT (admin). **Device auth validation:** server checks that `device.hardware_type == requested hardware_type` (prevents a compromised DietPi token from downloading CircuitPython firmware or vice versa). Serves firmware archive as binary stream.
- Device checks in via WebSocket, server compares `firmware_version` vs `target_firmware_version`
- If mismatch: server sends `firmware_update` message with download URL

### 3.3 — Push controls

- Per-device: "Push Now" button in admin UI → sends firmware_update message immediately
- Per-device: "Schedule Push" → sets `firmware_push_at` (default 2:00 AM device local time)
- Bulk: "Update All Devices" → sets target version for all devices owned by user
- Server background task runs every 60 seconds, checks for devices where `firmware_push_at <= now()` and device is online, sends `firmware_update` message, clears `firmware_push_at`

### 3.4 — Device-side OTA

- DietPi: device receives `firmware_update` via WebSocket (includes `sha256` hash), downloads files from `GET /api/firmware/download/{hardware_type}/{version}` using auth_token, **verifies SHA-256 hash of downloaded file matches the hash from the WebSocket message**, writes to `/opt/LED_flight/`, restarts via `os.execv(sys.executable, ...)` (existing pattern in `led_flight.py` watchdog). If hash mismatch → discard download, log error, do not apply.
- CircuitPython: device receives `firmware_update`, downloads `.py` files from server, writes to local filesystem. **Note:** The existing `git_sync()` in `code.py:67-93` is disabled with comment "Git sync not called due to write-only system" — investigate whether the CIRCUITPY filesystem is writable at runtime on MatrixPortal S3. If not, OTA requires USB mass-storage remount or a two-stage boot approach.
- Device reports new `firmware_version` in next heartbeat after restart
- Server compares heartbeat `firmware_version` to `target_firmware_version`. If match → mark update success in DB + admin UI. If mismatch after 5 minutes → mark as failed, alert in admin UI.

> **OTA rollback (DietPi):** Before applying an update, the device copies the current firmware to `/opt/LED_flight/rollback/`. If the new firmware fails to connect to the server within 3 minutes of restart, the watchdog (which should survive the update) restores from the rollback directory and restarts again. This prevents bricked devices from bad firmware pushes. The rollback mechanism is critical for a commercial product — it's the difference between "push a fix" and "send someone to physically access the device."
>
> **OTA rollback (CircuitPython):** More limited. If the device fails to connect after update, it could revert by keeping the previous `.py` files in a backup directory on the filesystem (if space allows). MatrixPortal S3 has limited storage, so this may not be feasible. Investigate during Phase 1 CircuitPython WebSocket validation.

---

## Phase 4: Flight Alerts + Analytics

### 4.1 — Alert engine

**Alert CRUD API (auth: Zitadel OIDC JWT):**
- `POST /api/alerts` — create alert (alert_type, pattern, notify_method)
- `GET /api/alerts` — list user's alerts
- `PATCH /api/alerts/{id}` — update alert (pattern, enabled, notify_method)
- `DELETE /api/alerts/{id}` — delete alert

**Matching logic:**
- Alert types: `aircraft_type` (e.g., "A380" matches "A388", "A380-800" — prefix match), `flight_number` (exact match, case-insensitive), `airline` (substring match, case-insensitive, e.g., "Emirates" matches "Emirates" airline_name)
- When poller detects a flight matching any enabled alert for users with devices in that region, trigger notification
- Notification methods: WebSocket push to admin UI (real-time banner) via `/ws/admin`. Email deferred to Phase 5.
- Alert evaluation runs inline with the poller — after upserting flights, check new/changed flights against all enabled alerts for that region's users. Use a single query joining `flight_alerts` with the new flight data to minimize DB round-trips.
- Deduplication: don't re-alert for the same flight within a 1-hour window (track in memory per user+flight).

### 4.2 — Analytics dashboard

**Analytics API (auth: Zitadel OIDC JWT):**
- `GET /api/analytics/flights-over-time?region_id=&period=day|week|month&start=&end=` — time series data
- `GET /api/analytics/top?region_id=&category=airline|aircraft_type|route&limit=10` — top N rankings
- `GET /api/analytics/peak-hours?region_id=&period=week|month` — hourly distribution
- `GET /api/analytics/export?region_id=&format=csv&start=&end=` — data export (max 365-day range, max 100K rows per request)

**Frontend (React + Recharts):**
- Flights per day/week/month line chart
- Top airlines, top aircraft types, top routes bar charts
- Peak hours heatmap (24h × 7d grid — use a custom grid component with Tailwind styling, as Recharts lacks a native heatmap)
- Per-device activity comparison
- CSV export button

---

## Phase 5: Commercial Polish

> **Note:** Each section below (5.1-5.4) should be broken into its own detailed plan before implementation. Billing and multi-org in particular are each larger than some entire earlier phases. The descriptions here define scope and intent; the implementation plans will specify schemas, APIs, and UX flows in full detail.

### 5.1 — Onboarding flow

- Sign up → verify email → add first device → configure region → see flights
- Guided setup wizard in admin UI

### 5.2 — Landing page

- Public page at flights.truefol.com (unauthenticated)
- Product description, screenshots, pricing tiers
- "Get Started" → sign up

### 5.3 — Billing hooks

- Stripe integration for subscription tiers via Stripe Checkout + Webhooks
- Free tier: 1 device, 7-day flight history, no alerts
- Pro tier: unlimited devices, alerts, full history, analytics, CSV export
- DB tables: `subscriptions` (user_id, stripe_customer_id, stripe_subscription_id, tier, status, current_period_end)
- **"Structure ready"** means: Stripe SDK integrated, webhook handler receives events, subscription records stored, tier limits defined in config. Enforcement middleware exists but is disabled via feature flag until launch. This allows testing the full billing flow in dev without blocking real users.

### 5.4 — Multi-org support

- New DB tables: `organizations` (id, name, created_at), `org_memberships` (user_id, org_id, role enum [owner, admin, viewer])
- Devices can be owned by an org instead of a user (add `org_id` FK to devices, nullable, mutually exclusive with `owner_id`)
- Org admins can manage devices, org viewers can see device status and flight history but cannot change config
- Invite flow: org admin generates invite link → invitee signs up/logs in → added to org as viewer
- Billing: subscription is per-org (the org owner's subscription), not per-user

---

## Implementation Order

| Phase | Dependencies | Success Criteria |
|-------|-------------|------------------|
| Phase 0 | None | Repo exists, TIM compliant, infra provisioned, `flights --env dev status` works |
| Phase 1 | Phase 0 | Health endpoint responds, DB migrations run, device can register → claim → connect WS, admin UI shows device list |
| Phase 2 | Phase 1 | Poller fetches FR24 data, flights stored in DB, connected device receives flight_batch messages, flight history page shows data |
| Phase 3 | Phase 1 | Firmware version registered, device receives firmware_update message, download endpoint serves file, OTA update verified |
| Phase 4 | Phase 2 | Alert created in UI triggers notification when matching flight appears, analytics charts render with real data |
| Phase 5 | Phase 2-4 | Separate detailed plans required before implementation |

Phases 2 and 3 can run in parallel after Phase 1 is complete.

### Within-phase implementation order

**Phase 1:** 1.1 (skeleton) → 1.2 (models + initial Alembic migration via `alembic init` + `alembic revision --autogenerate`) → 1.3 (registration API) → 1.4 (WebSocket endpoint) → 1.5 (React frontend scaffold + OIDC integration + basic pages).

**Frontend serving:** Vite builds static files to `web/dist/`. In production, FastAPI serves them via `StaticFiles` mount at `/` (single container, no separate frontend pod). In development, Vite dev server runs on port 5173 and proxies API calls to FastAPI on port 8000.

---

## Device Client Changes (LED_flight repo)

> **Scope: This section is INFORMATIONAL CONTEXT ONLY.** These changes will be implemented in a separate plan against the `LED_flight` repo, not as part of this plan. They are documented here so the server-side implementation knows what the device will send/expect.

The existing LED_flight code needs to be refactored into a thin WebSocket client. Key changes:

- Remove direct FR24 API calls from device code (`flight_api.py` becomes unused on-device)
- Remove MQTT logging — replaced by WebSocket `log` message type
- Remove sunrise-sunset.org API calls — server provides brightness schedule in config
- Add WebSocket client that connects to `wss://flights.truefol.com/ws/{device_id}?v=1&token={auth_token}`
- On boot: read `private.json` for `device_id` and `auth_token`. If missing, call `POST /api/devices/register` with serial_number (Pi: `/proc/device-tree/serial-number`, MatrixPortal: `microcontroller.cpu.uid` hex), display claim code on LED matrix
- Once claimed: receive flight data via WebSocket, render on display (no local filtering — server already applied region filters)
- Report heartbeat every 30 seconds (uptime, memory, firmware_version)
- Send `log` messages for events currently going to MQTT
- Handle `config_update` messages — apply brightness, flip, filter changes at runtime
- Handle `firmware_update` messages — download from server API using auth_token, write to disk, restart
- Store `device_id`, `auth_token`, and `server_url` in `private.json`
- Implement exponential backoff reconnection (1s → 30s cap, ±25% jitter)

> **Files retained on device:** `modbus_led.py` (display driver), `display_helpers.py`, `plane_icon.py`, `kdnode.py` (may be removed if local airport lookup is server-side). Files removed: `flight_api.py`, `flight_region.py` (filtering moves to server). `led_flight.py` and `code.py` rewritten as WebSocket clients.
