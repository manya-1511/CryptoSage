# CryptoSage Console (frontend) — v2

Rebuilt for the current backend (`app/api/routes.py`): firmware-centric,
with three independent analysis endpoints instead of one combined
`/analyze` call.

## Run

```bash
npm install
npm run dev
```

Opens on **http://localhost:3000**. Backend expected on
`http://localhost:8000` — override with a `.env` (copy `.env.example`).

CORS: your current `app/main.py` already has `CORSMiddleware` configured
for `http://localhost:3000`, so no backend changes should be needed.

## What changed from v1

The previous version of this frontend was built against a different
backend (`/upload` → `/analyze`, one combined pipeline response). This
version matches the actual current API:

| Endpoint | Used for |
|---|---|
| `GET /health` | backend status pill |
| `POST /firmware/upload` | upload a `.bin`/`.img`/`.elf`, handles the duplicate-upload response shape |
| `GET /firmware` | sidebar firmware list |
| `GET /firmware/{id}` | selected firmware's metadata |
| `POST /predict/{id}` | ML prediction (family + algorithm + confidence) |
| `POST /risk/{id}` | risk score/level/factors + recommendations |
| `POST /explain/{id}` | RAG explanation with sections + citations |

Prediction, risk, and explanation are **three separate buttons**, not one
pipeline — because they're three separate endpoints on the backend, each
independently callable (risk re-runs prediction internally, explanation
re-runs both). You don't need to click them in order.

## ⚠️ Important: this UI cannot trigger Phase 4 analysis

`/predict`, `/risk`, and `/explain` all expect `feature_vector.json` to
already exist for the firmware under `ANALYSIS_OUTPUT_DIR/<firmware_id>/`
— i.e. the Firmware Analysis Engine (Binwalk extraction, ELF parsing,
Capstone disassembly, feature extraction) must have already run. **That
step has no API endpoint** per the current `routes.py` — it's not
something this frontend, or any frontend, can trigger over HTTP right now.

If a button in this UI 404s with something like *"No analysis results
found for this firmware. Run the Firmware Analysis Engine before
requesting a prediction"* — that's expected given the current backend,
not a frontend bug. You'll need to invoke Phase 4 analysis some other way
(directly in Python, a script, a management command — whatever your
project uses) before prediction/risk/explanation will succeed for a given
firmware ID. Worth flagging to whoever owns the backend if you want this
runnable end-to-end from the UI alone: it'd need one more endpoint, e.g.
`POST /firmware/{id}/analyze`.

## Response-shape handling

`/predict`, `/risk`, and `/explain` each return **either** a `Single*`
shape (exactly one analyzed executable, no failures) **or** a `Multiple*`
shape (`{..., predictions/assessments/explanations: [...], failed: [...]}`)
depending on how many executables were found inside the firmware. `src/api.js`
exports `normalizePredictions` / `normalizeRiskAssessments` /
`normalizeExplanations`, which flatten either shape into one consistent
`{ items: [...], failed: [...] }` so the result components never branch on
which shape came back — every result card renders per-binary regardless of
whether there was 1 executable or 12.

## What the UI shows

- **Sidebar** — upload dropzone (`.bin`/`.img`/`.elf`, with real upload
  progress) + a list of every uploaded firmware record, click to select.
  Duplicate uploads (same SHA-256) surface a toast pointing at the
  existing record instead of creating a new one, matching the backend's
  own dedup behavior.
- **Firmware header** — id, filename, size, architecture, upload time,
  full SHA-256 with a copy button, and status badge.
- **Action bar** — Run Prediction / Assess Risk / Generate Explanation,
  each independently loading, with the Phase-4-dependency warning shown
  above it so a 404 there is legible instead of mysterious.
- **Prediction results** — per-binary family, algorithm, and an animated
  confidence bar, plus which model/version produced it.
- **Risk results** — per-binary radial risk gauge (0–100, Safe → Critical,
  matching the backend's five-level scale exactly), triggered risk-factor
  chips, and numbered recommendations.
- **Explanation results** — per-binary summary, all five explanation
  sections, citation chips for every referenced standard, and a
  `generated_by` tag so it's always visible whether a given explanation
  came from the real local LLM (`ollama:<model>`) or the deterministic
  template fallback (`template_fallback`) — per the backend's own honesty
  guarantee about never disguising one as the other.

Any binary that fails prediction/risk/explanation is shown in a separate
"N binary(ies) failed" banner rather than silently dropped, matching the
backend's `failed: [...]` list.

## Build for production

```bash
npm run build    # outputs to dist/
npm run preview  # serve the build on :3000 to sanity-check it
```
