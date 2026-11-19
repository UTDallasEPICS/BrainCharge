# BrainCharge Web App

Companion web UI for BrainCharge: caregiver schedule/calendar, reminders, settings, and a **robot face** driven by the Nano over a local API link.

| Piece | Path | Role |
|-------|------|------|
| Frontend | `reactApp/frontend/` | React (Vite) PWA — UI + face screen |
| Backend | `reactApp/backend/` | Express API — auth, Google Calendar, Nano face relay |
| Nano link | `NanoCodebase/app/webapp/` | Python posts face events to the backend |

---

## Architecture

```
Browser (Vite :5173) ──HTTP /api/*──► Express backend (:3001)
        │                                    │
        │ SSE /api/nano/events               ├── Better Auth (SQLite)
        │ (face screen)                      ├── Google Calendar API
        ▼                                    └── Nano face hub
Robot face UI                         ▲
                                      │ POST /api/nano/event
                                      │ Bearer NANO_TOKEN
                                 NanoCodebase (main.py)
```

| Layer | Role |
|-------|------|
| **Frontend** | Sign-in, home, schedule, calendar, reminders, settings, connect UI, robot face |
| **Backend** | Holds secrets (`service-account.json`, `.env`), calendar CRUD, auth, Nano→face SSE |
| **Google Calendar** | Source of truth for schedule events (service account) |
| **Nano** | Posts `robot.state` / `robot.expression`; never talks to the browser directly |

### What we do **not** use

- OAuth desktop flow / Google sign-in for caregivers
- Putting `service-account.json` in the frontend
- Domain-wide Google Workspace delegation (unless you add it later)

---

## Features (current UI)

| Area | Notes |
|------|--------|
| **Auth** | Email/password via [Better Auth](https://www.better-auth.com/) + local SQLite (`auth.db`) |
| **Home** | Main caregiver landing screen |
| **Schedule** | List / add / edit / delete recipient appointments (Google Calendar) |
| **Calendar** | Month-style view (`react-big-calendar`) |
| **Reminders** | Local reminder UI (browser notifications helpers) |
| **Settings** | Dark mode, font size, language (en / es / fr / de) |
| **Connect** | Device connection screen (Bluetooth pairing UI is still a stub) |
| **Robot face** | Full-screen face mode; follows Nano state/expression over SSE |
| **PWA** | Installable (`vite-plugin-pwa`) |

---

## Prerequisites

1. **Node.js 18+**
2. **Google Cloud project** with **Google Calendar API** enabled
3. **Service account** JSON key + calendar shared with that account
4. (Optional, for face) **NanoCodebase** running with matching `webapp.token` / `NANO_TOKEN`

---

## Quick start (local)

```powershell
# Terminal 1 — backend
cd reactApp/backend
copy .env.example .env
# Edit .env: calendar ID, BETTER_AUTH_*, NANO_TOKEN
npm install
npm run dev

# Terminal 2 — frontend
cd reactApp/frontend
npm install
npm run dev
```

Open **http://localhost:5173**

Checks:

| URL | Expected |
|-----|----------|
| http://127.0.0.1:3001/api/health | `{"ok":true,"service":"braincharge-calendar-api"}` |
| http://127.0.0.1:3001/api/auth/ok | `{"ok":true}` |
| http://127.0.0.1:3001/api/nano/status | JSON status (face clients / last events) |

---

## Project structure

```
reactApp/
├── README.md                 # This file (canonical webapp docs)
├── frontend/
│   ├── src/
│   │   ├── api/calendar.js   # Calendar API client
│   │   ├── face/             # Robot face SVG + expressions
│   │   ├── nanoLink/         # SSE client (useNanoEvents)
│   │   ├── screens/          # Splash, auth, home, schedule, …
│   │   ├── i18n/             # Translations
│   │   └── lib/auth-client.js
│   ├── vite.config.js        # Dev proxy /api → :3001 + PWA
│   └── package.json
└── backend/
    ├── index.js              # Express entry
    ├── auth.js               # Better Auth
    ├── calendar.js           # Google Calendar
    ├── nanoLink/             # Face event protocol + SSE hub
    ├── middleware/requireAuth.js
    ├── .env.example
    ├── service-account.json  # YOU ADD — never commit
    ├── .env                  # YOU ADD — never commit
    └── package.json
```

---

## Backend configuration

### 1. Create `.env`

```powershell
cd reactApp/backend
copy .env.example .env
```

### 2. Fill in values

```env
PORT=3001
HOST=127.0.0.1

GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
GOOGLE_CALENDAR_ID=your-calendar-id-here@gmail.com
CALENDAR_TIMEZONE=America/Chicago

BETTER_AUTH_SECRET=your-generated-secret-here
BETTER_AUTH_URL=http://localhost:5173
CLIENT_ORIGIN=http://localhost:5173

# Must match NanoCodebase userConfig.json → webapp.token
NANO_TOKEN=change-me
```

| Variable | Description |
|----------|-------------|
| `PORT` / `HOST` | API listen address (default `127.0.0.1:3001`) |
| `GOOGLE_*` | Service account path + calendar ID |
| `CALENDAR_TIMEZONE` | IANA zone for event times |
| `BETTER_AUTH_SECRET` | Random secret (≥32 chars) for sessions |
| `BETTER_AUTH_URL` | **Browser** origin of the frontend (Vite: `http://localhost:5173`) |
| `CLIENT_ORIGIN` | CORS / cookies origin (usually same as above) |
| `NANO_TOKEN` | Shared secret for `POST /api/nano/event` |

Generate secrets:

```powershell
# PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

```bash
openssl rand -base64 32
```

Put the **same** value in `backend/.env` → `NANO_TOKEN` and in Nano `userConfig.json` → `webapp.token`.

### 3. Install

```powershell
cd reactApp/backend
npm install
```

---

## Google Calendar setup (one-time)

### 1. Enable the Calendar API

1. [Google Cloud Console](https://console.cloud.google.com/)
2. **APIs & Services → Library** → **Google Calendar API** → **Enable**

### 2. Create a service account + JSON key

1. **APIs & Services → Credentials** → **Create Credentials → Service account**
2. Open the account → **Keys** → **Add Key → JSON**
3. Save the file as:

```
reactApp/backend/service-account.json
```

### 3. Share the calendar

1. [Google Calendar](https://calendar.google.com) → calendar **⋮** → **Settings and sharing**
2. **Share with specific people** → service account `client_email`
3. Permission: **Make changes to events**

### 4. Calendar ID → `.env`

Settings → **Integrate calendar** → copy **Calendar ID** into `GOOGLE_CALENDAR_ID`.

> Only events on **that** calendar appear in the app.

### Verify calendar access

```powershell
cd reactApp/backend
npm run test-calendar
```

`0` events is fine if the calendar is empty.

---

## Better Auth

Email/password accounts are stored in **`backend/auth.db`** (auto-created, gitignored).

| Do | Don't |
|----|-------|
| Set `BETTER_AUTH_URL` / `CLIENT_ORIGIN` to the **frontend** URL | Point them at `:3001` in local Vite dev |
| Generate your own `BETTER_AUTH_SECRET` | Commit `.env` or `auth.db` |

**Smoke test**

1. Start backend + frontend
2. **Get Started** → create account → land on Home
3. Log out → sign in again

| Problem | Fix |
|---------|-----|
| Blank after sign-up | Restart both; `BETTER_AUTH_URL=http://localhost:5173` |
| `MISSING_OR_NULL_ORIGIN` | Set `CLIENT_ORIGIN=http://localhost:5173`; open that exact URL |
| `EADDRINUSE` on 3001 | Kill the old Node process (see troubleshooting) |

Calendar **API routes require a logged-in session** (`requireAuth`). Calling `/api/events` in a bare browser tab without cookies returns **401**.

---

## Nano face link

The Nano does **not** use Bluetooth for the face. It HTTP-posts protocol messages; the backend fans them out over SSE to the face screen.

### Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/nano/events` | None | SSE stream for the face UI (`robot.state`, `robot.expression` only) |
| `POST` | `/api/nano/event` | `Authorization: Bearer <NANO_TOKEN>` | Nano publishes one face message |
| `GET` | `/api/nano/status` | None | Debug: connected clients + last state/expression |

Protocol lives in `backend/nanoLink/protocol.js` (version `1`). Expression names must match `frontend/src/face/expressions.js` (e.g. `Neutral`, `Happy`, `Thinking`).

### NanoCodebase config

In `NanoCodebase/userConfig.json` (or defaults under `app/defaultConfigs/`):

```json
"webapp": {
  "enabled": true,
  "url": "http://127.0.0.1:3001/api/nano/event",
  "token": "same-as-NANO_TOKEN-in-backend-env"
}
```

| Field | Meaning |
|-------|---------|
| `enabled` | When false, face posts are disabled |
| `url` | Must be the backend `POST /api/nano/event` URL |
| `token` | Must equal `NANO_TOKEN` |

Implementation: `NanoCodebase/app/webapp/service.py` (queues posts; drops if backend is down; resyncs periodically).

### How to see the face update

1. Backend running with `NANO_TOKEN` set
2. Frontend open (face mode / robot UI)
3. Nano `main.py` with `webapp.enabled: true` and matching token
4. Wake the robot — face should leave sleeping / show expressions
5. Optional: `GET http://127.0.0.1:3001/api/nano/status`

**Connect** tab Bluetooth scan is a **placeholder**; real robot↔face sync today is this Nano HTTP link.

---

## Frontend

```powershell
cd reactApp/frontend
npm install
npm run dev
```

Dev proxy (already in `vite.config.js`):

```
Browser → http://localhost:5173/api/...
              ↓
         http://127.0.0.1:3001/api/...
```

No frontend `.env` needed for local dev. For a remote API:

```env
VITE_API_URL=https://your-server.com/api
```

---

## npm scripts

**Frontend** (`reactApp/frontend/`):

| Command | What |
|---------|------|
| `npm run dev` | Vite on port 5173 |
| `npm run build` | Production `dist/` |
| `npm run preview` | Preview build |
| `npm run lint` | ESLint |

**Backend** (`reactApp/backend/`):

| Command | What |
|---------|------|
| `npm run dev` | API with `--watch` |
| `npm start` | API without watch |
| `npm run test-calendar` | Verify service account + calendar |
| `npm run migrate-auth` | Auth DB migration helper |

---

## API reference

Base: `http://127.0.0.1:3001/api`

### Public / health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `ALL` | `/auth/*` | Better Auth routes |
| `GET` | `/me` | Current session (401 if logged out) |

### Calendar (session required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/calendar/verify` | Test service account access |
| `GET` | `/events` | List (`?timeMin`, `?timeMax`, `?maxResults`) |
| `GET` | `/events/:id` | Get one |
| `POST` | `/events` | Create |
| `PUT` | `/events/:id` | Update |
| `DELETE` | `/events/:id` | Delete |

Create/update body:

```json
{
  "title": "Doctor Visit",
  "date": "2026-07-08",
  "time": "14:30",
  "note": "Bring insurance card"
}
```

### Nano face

See [Nano face link](#nano-face-link) above.

---

## Using the app

1. Open http://localhost:5173 → create account / sign in
2. **Schedule** → **Add Recipient Appointment** (writes Google Calendar)
3. **Calendar** → month view of the same events
4. **Reminders** / **Settings** as needed
5. Run Nano + backend with matching tokens to drive the **robot face**

Events created in Google Calendar appear after refresh **if** they are on the `GOOGLE_CALENDAR_ID` calendar.

---

## Troubleshooting

### `502` / calendar server not running

```powershell
cd reactApp/backend
npm run dev
```

### `EADDRINUSE: address already in use 127.0.0.1:3001`

```powershell
netstat -ano | findstr :3001
taskkill /PID <pid-from-last-column> /F
```

### Empty schedule, no error

Calendar connected but empty in the loaded window, or wrong calendar ID. Run `npm run test-calendar`.

### Events on Google don’t show in the app

1. Event must be on the calendar in `GOOGLE_CALENDAR_ID`
2. You must be signed in (calendar routes are auth-gated)
3. Re-run `npm run test-calendar`

### Face never updates

| Check | Fix |
|-------|-----|
| Backend up | `npm run dev` in `backend/` |
| Token match | `NANO_TOKEN` ↔ `userConfig.json` `webapp.token` |
| Nano config | `webapp.enabled: true`, URL ends with `/api/nano/event` |
| Status | Open `/api/nano/status` while face page is open |
| Nano logs | Look for `[WebApp]` reconnect / reject messages |

### `connect ECONNREFUSED` (Vite proxy)

Backend must listen on `127.0.0.1:3001`. Restart frontend after proxy/port changes.

### Changing backend port

1. `PORT=3002` in `backend/.env`
2. Update `frontend/vite.config.js` proxy target
3. Update Nano `webapp.url` if used
4. Restart both servers (+ Nano)

---

## Production notes

- Deploy backend with env vars / secrets (do not commit `service-account.json`)
- Set `BETTER_AUTH_URL` + `CLIENT_ORIGIN` to the public frontend HTTPS URL
- Build frontend with `VITE_API_URL` pointing at the API
- Use HTTPS; rotate `BETTER_AUTH_SECRET` and `NANO_TOKEN` for production
- `dist/` never includes the service account key

---

## Security checklist

- [ ] `service-account.json` only under `backend/`
- [ ] `backend/.env`, `service-account.json`, `auth.db` gitignored
- [ ] Service account limited to the one shared calendar
- [ ] `NANO_TOKEN` is strong and not committed
- [ ] Calendar mutations require a logged-in caregiver session
- [ ] Face SSE does not carry transcripts (only state/expression)

---

## Full setup checklist

- [ ] Google Calendar API enabled
- [ ] Service account JSON in `reactApp/backend/service-account.json`
- [ ] Calendar shared with service account email
- [ ] `backend/.env` from `.env.example` (calendar + auth + `NANO_TOKEN`)
- [ ] `npm install` in `frontend/` and `backend/`
- [ ] `npm run test-calendar` succeeds
- [ ] Backend + frontend `npm run dev`
- [ ] `/api/health` and `/api/auth/ok` OK
- [ ] Sign-up / sign-in / sign-out works
- [ ] Test appointment visible in app + Google Calendar
- [ ] (Optional) Nano `webapp.token` matches `NANO_TOKEN`; face follows robot
