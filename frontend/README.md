# 🛡️ CryptoSage — Firmware Cryptographic Security Analysis Platform (Frontend)

An AI-powered frontend for CryptoSage: upload firmware, detect the
cryptographic algorithms inside it, get a weighted security risk score,
and receive an evidence-backed, cited explanation of the findings.

This is the **frontend only**. It talks to your existing CryptoSage
FastAPI backend (the one with `/firmware/upload`, `/analyze`, `/predict`,
`/risk`, `/explain`, etc.) — it does not include or require its own
database; all persistent state lives in the backend's PostgreSQL.

---

## ✨ Features

- **Landing page** with product overview and sign-up
- **Clerk authentication** (sign-in/sign-up, protected routes)
- **Dashboard** with quick actions
- **Analyze** — drag-and-drop firmware upload that runs the full
  upload → extract → predict → risk-score → explain pipeline, with
  live progress and a results view
- **Firmware History** — every uploaded firmware, with a detail page
  per firmware that re-fetches or re-runs its report
- **Report Assistant** — a lightweight AI-style chat that answers
  questions grounded entirely in a specific firmware's own report
  (algorithm, risk score, recommendations, references). It does not
  call an LLM — the backend has no chat endpoint — so it stays
  strictly accurate to what CryptoSage actually found rather than
  fabricating a "live AI" that isn't there.
- **Violet/purple design system** — glass cards, animated neon grid
  background, floating particles, dark mode by default

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v4 |
| Auth | Clerk |
| Animation | Framer Motion |
| Icons | lucide-react |
| HTTP client | axios |
| Backend | Your existing CryptoSage FastAPI service |

No frontend database. No Vapi, no mfapi.in, no Drizzle/Neon — those
were specific to a prior, unrelated app and have been fully removed.

---

## 🚀 Getting Started (local dev)

### Prerequisites
- Node.js 18+
- npm
- A [Clerk](https://clerk.com) application
- The CryptoSage FastAPI backend running and reachable (default assumed
  at `http://localhost:8000`)

### 1. Install dependencies

```bash
npm install
```

### 2. Configure environment variables

Copy `.env.example` to `.env.local` and fill in your real values:

```bash
cp .env.example .env.local
```

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

# Server-side only (used by app/api/* proxy routes) — never exposed to the browser
API_URL=http://localhost:8000
# Client-side (used by lib/api.ts calling the backend directly)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`.env.local` is already in `.gitignore` — never commit real secrets.

### 3. Run the dev server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Make sure your
CryptoSage FastAPI backend is running separately (see its own README)
on whatever `NEXT_PUBLIC_API_BASE_URL` points to.

### 4. Build for production (optional local check)

```bash
npm run build
npm start
```

---

## 🐳 Running with Docker

### Build the image

Build-time public env vars (safe to be visible in the browser bundle)
are passed as build args; the secret key is **not** — it's only ever
passed at `docker run` time.

```bash
docker build \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_key \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com \
  -t cryptosage-frontend .
```

### Run the container

```bash
docker run -p 3000:3000 \
  -e CLERK_SECRET_KEY=sk_test_your_secret_key \
  -e API_URL=https://your-backend.example.com \
  -e NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com \
  cryptosage-frontend
```

Open [http://localhost:3000](http://localhost:3000).

### Or with docker-compose

Create a `.env` file (compose reads this automatically) with the same
variables shown in `.env.example`, then:

```bash
docker compose up --build
```

`docker-compose.yml` assumes your FastAPI backend is either:
- reachable at a URL you set in `API_URL` / `NEXT_PUBLIC_API_BASE_URL`, or
- running as its own `backend` service on the same Docker network (edit
  `API_URL` to `http://backend:8000` and add that service yourself if
  you want to run both containers together — this repo only contains
  the frontend).

---

## 🔐 Auth & route protection

`middleware.ts` protects `/dashboard`, `/analyze`, and `/firmware` —
signed-out users are redirected to sign in before reaching them. The
landing page (`/`) redirects signed-in users straight to `/dashboard`.

---

## 🔌 Backend endpoints this frontend expects

All defined and typed in `lib/api.ts`, matching your FastAPI router:

| Method | Endpoint | Used by |
|---|---|---|
| POST | `/firmware/upload` | Analyze page |
| GET | `/firmware` | Firmware History, Report Assistant |
| GET | `/firmware/{id}` | Firmware detail page |
| POST | `/firmware/{id}/analyze` | Analyze page, Firmware detail, Report Assistant |
| POST | `/predict/{id}` | available in `lib/api.ts`, not currently called directly (superseded by `/explain`) |
| POST | `/risk/{id}` | available in `lib/api.ts`, not currently called directly (superseded by `/explain`) |
| POST | `/explain/{id}` | Analyze page, Firmware detail, Report Assistant |
| GET | `/health` | `app/api/health` proxy |

If any response shape differs from what's in `lib/api.ts` (this was
built against your `routes.py` but not your `schemas.py`), that file
is the one place to correct field names.

---

## 📜 License

This project is developed for research and educational purposes.
