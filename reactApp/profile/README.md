# BrainCharge Profile App — Google Calendar Setup

This React app syncs the **Recipient Schedule** with Google Calendar using a **service account** on a **Node.js backend**. The private key never goes in the frontend.

---

## Architecture

```
React App (Vite, port 5173)
        │
        │  HTTP  /api/*
        ▼
Node/Express Backend (port 3001)
        │
        │  googleapis + service account JSON
        ▼
Google Calendar API
        │
        ▼
Your shared Google Calendar
```

| Layer | Role |
|-------|------|
| **Frontend** (`src/`) | UI for viewing, creating, editing, and deleting appointments |
| **Backend** (`server/`) | Holds `service-account.json`, talks to Google Calendar API |
| **Google Calendar** | Source of truth for schedule events |

### What we do **not** use

- OAuth desktop flow / browser sign-in
- `credentials.json` (OAuth client)
- `@google-cloud/local-auth`
- Domain-wide delegation
- Google Workspace admin console

---

## Prerequisites

1. **Node.js 18+** (you have v22 — good)
2. **A Google Cloud project** with the **Google Calendar API** enabled
3. **A service account** with a downloaded JSON key
4. **A Google Calendar** shared with the service account email

---

## Google Cloud setup (one-time)

### 1. Enable the Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. **APIs & Services → Library**
4. Search for **Google Calendar API** → **Enable**

### 2. Create a service account

1. **APIs & Services → Credentials**
2. **Create Credentials → Service account**
3. Name it (e.g. `braincharge-calendar`)
4. Skip optional role steps → **Done**
5. Click the new service account → **Keys** tab
6. **Add Key → Create new key → JSON**
7. A file downloads — this is your `service-account.json`

The service account email looks like:

```
something@your-project-id.iam.gserviceaccount.com
```

### 3. Share your calendar with the service account

1. Open [Google Calendar](https://calendar.google.com)
2. Find the calendar you want to sync (left sidebar)
3. Click the **⋮** next to it → **Settings and sharing**
4. Under **Share with specific people**, click **Add people**
5. Paste the **service account email** (from the JSON file, field `client_email`)
6. Permission: **Make changes to events**
7. **Send**

### 4. Get your Calendar ID

Still in that calendar’s settings:

1. Scroll to **Integrate calendar**
2. Copy the **Calendar ID**

Examples:

| Calendar type | Calendar ID looks like |
|---------------|------------------------|
| Primary Gmail calendar | `yourname@gmail.com` |
| Secondary / created calendar | `abc123...@group.calendar.google.com` |

Put this value in `server/.env` as `GOOGLE_CALENDAR_ID`.

> **Important:** The app only shows events on **this specific calendar**. Events on other calendars (e.g. your main Gmail calendar) will not appear unless you share that calendar and use its ID in `.env`.

---

## Project structure

```
reactApp/profile/
├── src/                          # React frontend
│   ├── api/calendar.js           # API client (calls /api/*)
│   └── screens/
│       ├── ScheduleScreen.jsx    # List + delete appointments
│       ├── AddAppointmentScreen.jsx  # Create + edit appointments
│       └── HomeScreen.jsx        # Shows upcoming calendar events
├── server/                       # Node backend (KEEP SECRETS HERE)
│   ├── index.js                  # Express API routes
│   ├── calendar.js               # Google Calendar logic
│   ├── test-calendar.js          # One-off connection test
│   ├── service-account.json      # ⚠️ YOU ADD THIS — never commit
│   ├── .env                      # ⚠️ YOU ADD THIS — never commit
│   ├── .env.example              # Template for .env
│   └── package.json
├── vite.config.js                # Proxies /api → backend in dev
└── package.json                  # Frontend scripts + server shortcuts
```

---

## Where `service-account.json` goes

Place the downloaded JSON key **only** here:

```
reactApp/profile/server/service-account.json
```

### Correct layout

```
server/
├── service-account.json    ← your GCP key file
├── .env
├── index.js
└── ...
```

### Security rules

| Do | Don't |
|----|-------|
| Keep the file in `server/` only | Put it in `src/` or anywhere the React app bundles |
| Add it to `.gitignore` (already done) | Commit it to GitHub |
| Reference it via `GOOGLE_SERVICE_ACCOUNT_PATH` in `.env` | Hard-code the private key in source code |

The file is gitignored by these entries:

```
server/service-account.json
server/.env
```

---

## Backend configuration

### 1. Create `.env` from the example

```powershell
cd reactApp/profile/server
copy .env.example .env
```

### 2. Edit `server/.env`

```env
PORT=3001
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
GOOGLE_CALENDAR_ID=your-calendar-id-here@gmail.com
CALENDAR_TIMEZONE=America/Chicago

# Better Auth (see "Better Auth configuration" section below)
BETTER_AUTH_SECRET=your-generated-secret-here
BETTER_AUTH_URL=http://localhost:5173
CLIENT_ORIGIN=http://localhost:5173
```

| Variable | Description |
|----------|-------------|
| `PORT` | Backend port (default `3001`) |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to JSON key, relative to `server/` |
| `GOOGLE_CALENDAR_ID` | Calendar ID from Google Calendar settings |
| `CALENDAR_TIMEZONE` | IANA timezone for event times (e.g. `America/New_York`) |
| `HOST` | Optional. Default `127.0.0.1` |
| `BETTER_AUTH_SECRET` | Random secret for encrypting sessions (you generate this) |
| `BETTER_AUTH_URL` | URL the **browser** uses to reach the app (Vite dev server) |
| `CLIENT_ORIGIN` | Frontend origin for CORS and cookies (usually same as above) |

### 3. Install backend dependencies

```powershell
cd reactApp/profile/server
npm install
```

---

## Better Auth configuration

User sign-up and sign-in use [Better Auth](https://www.better-auth.com/) with **email/password** and a local **SQLite** database. You do **not** need Google OAuth, Postgres, or any third-party auth provider for basic login.

All Better Auth settings go in **`reactApp/profile/server/.env`** (same file as the calendar settings).

### What to add to `server/.env`

```env
# Required — random secret you generate yourself (min 32 characters)
BETTER_AUTH_SECRET=your-long-random-secret-here

# Required for local dev — must match your Vite frontend URL
BETTER_AUTH_URL=http://localhost:5173
CLIENT_ORIGIN=http://localhost:5173
```

### Where each value comes from

| Variable | Required? | Where to get it |
|----------|-----------|-----------------|
| `BETTER_AUTH_SECRET` | **Yes** | **You generate it.** Not from Google or any website. Used to sign session cookies and encrypt auth data. |
| `BETTER_AUTH_URL` | **Yes (dev)** | Your **frontend** URL in the browser. For local dev with Vite: `http://localhost:5173`. Do **not** use `http://127.0.0.1:3001` — that breaks cookies through the Vite proxy. |
| `CLIENT_ORIGIN` | **Yes (dev)** | Same as `BETTER_AUTH_URL` for local dev: `http://localhost:5173`. Tells the backend which frontend is allowed to send auth requests (CORS + cookies). |

### How to generate `BETTER_AUTH_SECRET`

Run **one** of these in a terminal and paste the output into `.env`:

**PowerShell:**
```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

**Git Bash / WSL / macOS / Linux:**
```bash
openssl rand -base64 32
```

Example result (yours will be different):
```
BETTER_AUTH_SECRET=k7xP2mN9qR4vL8wJ3tY6hF1cB5nM0sA==
```

Keep this secret private. Never commit it to git.

### What you do **not** need for Better Auth

| Not needed | Why |
|------------|-----|
| Google OAuth client ID / `credentials.json` | Auth uses email/password, not Google sign-in |
| Postgres / MySQL | Users are stored in local SQLite (`server/auth.db`) |
| Domain-wide delegation | Only used for Google Workspace calendar access, not app login |
| Better Auth cloud account | Self-hosted in your Express server |
| Frontend `.env` for auth (local dev) | Vite proxy handles `/api/auth/*` automatically |

### Where user data is stored

| Data | Location |
|------|----------|
| User accounts (email, name) | `server/auth.db` (SQLite, auto-created) |
| Passwords | Hashed inside `auth.db` — never stored as plain text |
| Login sessions | `auth.db` + httpOnly cookie in the browser |
| Google Calendar key | `server/service-account.json` (separate from user auth) |

The database file is created automatically on first server start. You do not download or configure it manually.

`auth.db` is gitignored — do not commit it.

### Example full `server/.env` (calendar + auth)

```env
PORT=3001
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
GOOGLE_CALENDAR_ID=your.email@gmail.com
CALENDAR_TIMEZONE=America/Chicago

BETTER_AUTH_SECRET=paste-your-openssl-or-powershell-output-here
BETTER_AUTH_URL=http://localhost:5173
CLIENT_ORIGIN=http://localhost:5173
```

### Verify auth is working

1. Start backend and frontend (see [Running the app](#running-the-app-development))
2. Open http://127.0.0.1:3001/api/auth/ok — should return `{"ok":true}`
3. In the app: **Get Started** → create an account → you should land on Home
4. **Log Out** → should return to the Sign In screen
5. Sign in again with the same email/password

### Auth troubleshooting

| Problem | Fix |
|---------|-----|
| Blank screen after sign-up | Restart both servers. Ensure `BETTER_AUTH_URL=http://localhost:5173` (not port 3001). |
| `User not found` on sign-in | Account may not have been created. Create a **new** account after fixing `.env`. |
| Stuck on "Signing you in..." after logout | Refresh the page. Should show Sign In (fixed in latest app code). |
| `EADDRINUSE` on port 3001 | Old server still running — see [troubleshooting](#eaddrinuse-address-already-in-use-1270013001) below. |
| `MISSING_OR_NULL_ORIGIN` in server logs | Set `CLIENT_ORIGIN=http://localhost:5173` and open the app at that exact URL. |

### Production notes (auth)

When deploying later, update:

```env
BETTER_AUTH_URL=https://your-production-frontend.com
CLIENT_ORIGIN=https://your-production-frontend.com
BETTER_AUTH_SECRET=<new strong secret for production>
```

Use HTTPS in production and set secure cookies (the dev server disables secure cookies for localhost).

---

## Frontend configuration

### Install frontend dependencies

```powershell
cd reactApp/profile
npm install
```

### Dev proxy (already configured)

In development, Vite proxies API calls automatically:

```
Browser  →  http://localhost:5173/api/events
                ↓ (Vite proxy)
           http://127.0.0.1:3001/api/events
```

No frontend env file is required for local dev.

### Optional: custom API URL

For production or a remote backend, create `.env` in `reactApp/profile/`:

```env
VITE_API_URL=https://your-server.com/api
```

---

## PWA (Progressive Web App)

BrainCharge is configured as a **PWA** using `vite-plugin-pwa`. Users can install it on their phone home screen from the browser — no App Store or APK required.

Works on:
- **Android** — Chrome → menu → Install app / Add to Home screen
- **iPhone** — Safari → Share → **Add to Home Screen**
- **Desktop** — Chrome/Edge install icon in the address bar

### What was added

| File | Purpose |
|------|---------|
| `vite.config.js` | PWA plugin, manifest, service worker |
| `public/pwa-192.png`, `public/pwa-512.png` | Home screen icons |
| `public/pwa-icon.svg` | Favicon |
| `src/main.jsx` | Registers service worker |

### Test locally

**Development** (service worker enabled in dev):

```powershell
cd reactApp/profile
npm run dev
```

Open http://localhost:5173 — check DevTools → Application → Manifest / Service Workers.

**Production build** (recommended for install testing):

```powershell
cd reactApp/profile
npm run build
npm run preview
```

Open the preview URL (usually http://localhost:4173) and install from the browser.

### Important: backend still required

The PWA caches the **frontend** (HTML, JS, CSS). Calendar and auth still need the **Node backend** running:

```powershell
npm run server
```

When installed as a PWA on your phone, the app must be able to reach your API. For local phone testing, use your PC's LAN IP (e.g. `http://192.168.1.5:5173`) with backend on the same network — or deploy both frontend and backend to production.

### iOS limitations

- No rich push notifications like a native app (Safari limits this)
- Must use **Safari** to Add to Home Screen (Chrome on iOS won't install PWAs the same way)
- Bluetooth / deep native features are limited compared to Capacitor

---

## Running the app (development)

You need **two terminals** — backend and frontend run separately.

### Terminal 1 — Backend

```powershell
cd reactApp/profile
npm run server
```

Expected output:

```
Calendar API running at http://127.0.0.1:3001
Health check: http://127.0.0.1:3001/api/health
Auth routes: http://127.0.0.1:3001/api/auth/*
Verify access: http://127.0.0.1:3001/api/calendar/verify
```

### Terminal 2 — Frontend

```powershell
cd reactApp/profile
npm run dev
```

Open: **http://localhost:5173**

### Verify before using the UI

```powershell
cd reactApp/profile
npm run test-calendar
```

Success looks like:

```
Success! Calendar is reachable.
Calendar ID: your-calendar-id@...
Events found (sample window): 0
```

`0` events is fine — it means the connection works but the calendar is empty.

### Quick browser checks

| URL | Expected |
|-----|----------|
| http://127.0.0.1:3001/api/health | `{"ok":true,"service":"braincharge-calendar-api"}` |
| http://127.0.0.1:3001/api/events | `[]` or a JSON array of events |

---

## npm scripts reference

Run from `reactApp/profile/`:

| Command | What it does |
|---------|--------------|
| `npm run dev` | Start React app (Vite, port 5173) |
| `npm run server` | Start backend with auto-reload (`node --watch`) |
| `npm run server:start` | Start backend without watch (production-style) |
| `npm run test-calendar` | Test Google Calendar access (no server needed) |
| `npm run build` | Build frontend to `dist/` |
| `npm run preview` | Preview production build |

Run from `reactApp/profile/server/`:

| Command | What it does |
|---------|--------------|
| `npm run dev` | Start API with auto-reload |
| `npm start` | Start API |
| `npm run test-calendar` | Test calendar connection |

---

## API endpoints

Base URL: `http://127.0.0.1:3001/api`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health check |
| `GET` | `/calendar/verify` | Test service account + calendar access |
| `GET` | `/events` | List events (optional: `?timeMin`, `?timeMax`, `?maxResults`) |
| `GET` | `/events/:id` | Get one event |
| `POST` | `/events` | Create event |
| `PUT` | `/events/:id` | Update event |
| `DELETE` | `/events/:id` | Delete event |

### Create / update request body

```json
{
  "title": "Doctor Visit",
  "date": "2026-07-08",
  "time": "14:30",
  "note": "Bring insurance card"
}
```

- `title` — required
- `date` — required, `YYYY-MM-DD`
- `time` — `HH:MM` (24-hour). Default event duration is 1 hour.
- `note` — optional, stored as Google Calendar description

---

## Using the app

1. Open the **Schedule** tab
2. **Add Recipient Appointment** — creates an event in Google Calendar
3. Events appear in the app and on [calendar.google.com](https://calendar.google.com) under the synced calendar
4. **Edit** (pencil icon) or **Delete** (trash icon) on each card

You can also create events directly in Google Calendar — make sure you select the **correct calendar** in the event dropdown. Refresh the app to see them.

---

## Troubleshooting

### `502` / `Calendar server is not running`

The backend is not running. Start it:

```powershell
npm run server
```

### `EADDRINUSE: address already in use 127.0.0.1:3001`

Another process is already on port 3001 (often a previous server instance).

```powershell
netstat -ano | findstr :3001
taskkill /PID 49284 /F
npm run server
```

Replace `49284` with the PID from the last column of the `netstat` output.

### Empty schedule but no error

Sync is working. The calendar has no events in the loaded date range (30 days ago → 1 year ahead).

- Add a test event via **Add Recipient Appointment**, or
- Create one on [calendar.google.com](https://calendar.google.com) on the **correct calendar**

### Events on Google Calendar don’t show in the app

1. Confirm the event is on the calendar whose ID is in `GOOGLE_CALENDAR_ID`
2. In Google Calendar event editor, check the **calendar dropdown** under the title
3. Run `npm run test-calendar` and confirm the Calendar ID matches

### `Failed to verify calendar access` / 403 / 404

| Check | Fix |
|-------|-----|
| Calendar API enabled | GCP Console → APIs & Services → Library |
| `service-account.json` path | Must match `GOOGLE_SERVICE_ACCOUNT_PATH` in `.env` |
| Calendar shared | Service account email added with **Make changes to events** |
| Wrong Calendar ID | Copy from Google Calendar → Settings → Integrate calendar |

### `connect ECONNREFUSED ::1:3001` (Vite proxy)

The Vite proxy targets `127.0.0.1:3001` (not `localhost`) to avoid Windows IPv6 issues. Ensure the backend is running and restart `npm run dev` after config changes.

### Changing the backend port

1. Set `PORT=3002` in `server/.env`
2. Update `vite.config.js` proxy target to `http://127.0.0.1:3002`
3. Restart both servers

---

## Production notes

- Deploy the **backend** to a server (Railway, Render, VPS, etc.)
- Set environment variables on the host (do not upload `service-account.json` to public storage — use secrets/env injection)
- Set `VITE_API_URL` on the frontend build to point at your deployed API
- The React `dist/` build does **not** include the service account key

---

## Security checklist

- [ ] `service-account.json` is in `server/` only
- [ ] `server/service-account.json` and `server/.env` are gitignored
- [ ] `server/auth.db` is gitignored (SQLite user database)
- [ ] Service account has access only to the one shared calendar
- [ ] JSON key is never imported in React components or committed to git
- [ ] Backend is not exposed to the public internet without authentication (future hardening)

---

## Full setup checklist

- [ ] Google Calendar API enabled in GCP
- [ ] Service account created, JSON key downloaded
- [ ] `service-account.json` placed in `reactApp/profile/server/`
- [ ] Calendar shared with service account email (`client_email` from JSON)
- [ ] `server/.env` created and `GOOGLE_CALENDAR_ID` set
- [ ] `BETTER_AUTH_SECRET` generated and added to `server/.env`
- [ ] `BETTER_AUTH_URL` and `CLIENT_ORIGIN` set to `http://localhost:5173`
- [ ] `npm install` in both `reactApp/profile/` and `reactApp/profile/server/`
- [ ] `npm run test-calendar` succeeds
- [ ] `npm run server` running in Terminal 1
- [ ] `npm run dev` running in Terminal 2
- [ ] http://127.0.0.1:3001/api/health returns `ok: true`
- [ ] http://127.0.0.1:3001/api/auth/ok returns `ok: true`
- [ ] Create account + sign in + sign out works in the app
- [ ] Test event created and visible in app + Google Calendar
