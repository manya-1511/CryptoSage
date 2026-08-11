# CryptoSage

**CryptoSage** is an AI-powered firmware security analysis platform. It is
designed to inspect firmware images, detect cryptographic algorithms
through static binary analysis and machine learning, assess associated
security risk, and generate actionable recommendations and reports.

> **This repository currently implements Phase 1 (Project Setup),
> Phase 2A/2B (Offline Dataset Builder), Phase 3 (Firmware Input
> Module), Phase 4 (Firmware Analysis Engine), Phase 6 (ML
> Benchmarking Framework + Hierarchical Inference, superseding Phase
> 5A/5B), Phase 6/7 (Risk Assessment & Recommendation Engine), and
> Phase 7 (Explainable RAG Intelligence Engine).**
> Phase 1 provides a clean, production-ready backend foundation —
> FastAPI, PostgreSQL, SQLAlchemy, and Alembic. Phase 2A/2B build a
> real, algorithm-level labeled ML training dataset (now 7,095 real
> samples) from open-source cryptographic libraries. Phase 3 accepts,
> validates, and stores firmware uploads. Phase 4 adds the shared static
> analysis engine (Binwalk + LIEF + Capstone) used by both the Dataset
> Builder and runtime firmware analysis. Phase 6 benchmarks
> RandomForest/ExtraTrees/HistGradientBoosting/XGBoost under Stratified
> 5-Fold CV, automatically selects the best one, trains a hierarchical
> family→algorithm classifier with it (95.24% test accuracy), and
> serves it at runtime via `POST /predict/{firmware_id}`. Phase 6/7
> adds a deterministic, non-ML, weighted risk scoring and rule-based
> recommendation engine via `POST /risk/{firmware_id}`. Phase 7 adds a
> ChromaDB + LangChain retrieval-augmented explanation engine, with a
> local Ollama LLM integration (falling back to a deterministic
> template explainer when no local LLM is available), via
> `POST /explain/{firmware_id}`. PDF reporting is not implemented yet.

---

## 1. Architecture

CryptoSage separates cleanly into two pipelines that will eventually
work together, plus the FastAPI service that ties them to a database:

- **Offline dataset generation** (`dataset/`) — a pipeline, run manually
  or on a schedule and *independent of the live API*, that builds a
  labeled reference dataset from well-known open-source cryptographic
  libraries (OpenSSL, mbedTLS, wolfSSL, LibTomCrypt, libsodium). Its
  output feeds model training in `ml/`.
- **Online firmware analysis** (`input/` → `analysis/` → `ml/`) — the
  request-time path a real user's firmware upload will travel: intake
  and validation, extraction and feature discovery, then classification
  and prediction against the model trained offline.

Each stage gets its own folder so the codebase stays easy to navigate
as it grows, without introducing unnecessary abstraction layers at this
stage. **`dataset/` (Phase 2A/2B), `input/` (Phase 3), and `analysis/`
(Phase 4) are now fully implemented.** Only `ml/`, `rag/`, and
`reports/` remain documented placeholders for future phases.

```
CryptoSage/
│
├── backend/
│   ├── app.py                 # FastAPI application entrypoint
│   ├── config.py              # Environment-based settings
│   ├── database.py            # SQLAlchemy engine, session, Base
│   ├── models.py               # ORM models: Firmware, Analysis, Report, UploadedFeatures
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── requirements.txt         # Python dependencies (Phase 1 + Phase 2A)
│   │
│   ├── dataset/                 # OFFLINE dataset generation (Phase 2A -- implemented)
│   │   ├── config.py             # Central pipeline configuration (projects, opt levels, etc.)
│   │   ├── sources/              # Cloned reference crypto library checkouts
│   │   │   ├── openssl/src/
│   │   │   ├── mbedtls/src/
│   │   │   ├── wolfssl/src/
│   │   │   ├── libtomcrypt/src/
│   │   │   └── libsodium/src/
│   │   ├── compiled/             # Compiled binaries, organized project/opt-level/arch
│   │   ├── data/
│   │   │   ├── raw/               # dataset.csv + dataset_metadata.json
│   │   │   ├── processed/         # train.csv + test.csv + preprocessing_metadata.json
│   │   │   └── features/          # Reserved for future ML feature-set exports
│   │   ├── logs/                 # One timestamped log file per pipeline run
│   │   ├── builder.py             # Orchestrates cloning, building, feature extraction
│   │   ├── extractor.py           # Reusable LIEF/Capstone static feature extraction
│   │   └── preprocess.py          # Cleans, encodes, normalizes, splits the dataset
│   │
│   ├── input/                    # ONLINE upload intake & validation (Phase 3 -- implemented)
│   │   ├── upload.py               # Firmware upload workflow (hash, dedupe, storage)
│   │   ├── validator.py            # Upload validation (extension, MIME, size)
│   │   └── hardware.py             # Hardware/device metadata capture (placeholder)
│   │
│   ├── analysis/                 # Shared Firmware Analysis Engine (Phase 4 -- implemented)
│   │   ├── firmware.py             # Binwalk extraction -> analysis_output/<firmware_id>/
│   │   ├── binary.py               # Executable discovery + LIEF ELF parsing
│   │   ├── disassembler.py         # Capstone disassembly + instruction statistics
│   │   ├── constants.py            # Centralized crypto signature database
│   │   ├── features.py             # THE single canonical extract_features() implementation
│   │   ├── similarity.py           # Cosine similarity between feature vectors
│   │   └── utils.py                # Entropy, strings, hashing, MIME typing, safe file I/O
│   │
│   ├── ml/                       # Training, prediction, risk, recommendations (placeholder)
│   │   ├── train.py                # Trains the classification model (offline)
│   │   ├── predict.py              # Runtime inference (Phase 5B -- implemented)
│   │   ├── risk.py                 # Computes risk scores/levels
│   │   ├── recommend.py            # Generates security recommendations
│   │   └── saved_models/           # Model registry (see section 4)
│   │       ├── model_v1.pkl
│   │       ├── scaler.pkl
│   │       ├── label_encoder.pkl
│   │       └── metadata.json
│   │
│   ├── rag/                       # (future) retrieval-augmented explanation pipeline
│   ├── reports/                   # (future) PDF report generation
│   ├── api/
│   │   └── routes.py               # API routes (root, health, firmware upload/list/get)
│   └── uploads/                   # Uploaded firmware storage
│
├── frontend/                       # Reserved for future frontend application
└── README.md
```

---

## 2. Tech Stack (Phase 1)

| Layer          | Technology                     |
|----------------|---------------------------------|
| Language        | Python 3.12                    |
| Web framework   | FastAPI                        |
| Database        | PostgreSQL                     |
| ORM             | SQLAlchemy 2.0                 |
| Migrations      | Alembic                        |
| Validation      | Pydantic                       |
| Server          | Uvicorn                        |

The following technologies are planned for later phases and are **not**
installed yet: scikit-learn, SHAP, Binwalk, LangChain, ChromaDB,
sentence-transformer embeddings, Ollama, ReportLab, Docker. Pandas,
NumPy, LIEF, and Capstone are now installed and used by the Phase 2A
offline dataset builder (see section 5).

---

## 3. Database Schema

Four tables are defined, with foreign key relationships connecting them.

### `firmware`
| Column       | Type      | Notes                    |
|--------------|-----------|---------------------------|
| id           | Integer   | Primary key                |
| filename     | String    |                             |
| file_hash    | String    | Unique (indexed)            |
| file_size    | Integer   |                             |
| architecture | String    | Nullable                   |
| storage_path | String    | Nullable — relative path under `uploads/`, e.g. `"23/router.bin"` |
| upload_time  | DateTime  | Defaults to current UTC time |
| status       | String    | Defaults to `"Uploaded"`; see section 6.7 for the full status lifecycle |

### `analysis`
| Column          | Type     | Notes                              |
|-----------------|----------|-------------------------------------|
| id              | Integer  | Primary key                          |
| firmware_id     | Integer  | Foreign key → `firmware.id`          |
| algorithm       | String   | Nullable — populated by `/predict/{firmware_id}` or `/risk/{firmware_id}` |
| confidence      | Float    | Nullable — populated by `/predict/{firmware_id}` or `/risk/{firmware_id}` |
| risk_score      | Float    | Nullable — populated by `/risk/{firmware_id}` (Phase 6/7) |
| risk_level      | String   | Nullable — populated by `/risk/{firmware_id}` (Phase 6/7) |
| recommendation  | JSONB    | Nullable — list of recommendation strings (Phase 6/7) |
| risk_factors    | JSONB    | Nullable — list of `{factor, weight, contribution}` (Phase 6/7) |
| analysis_status | String   | Nullable — `"Completed"` / `"Failed"` (Phase 6/7) |
| analysis_time   | DateTime | Defaults to current UTC time         |

### `reports`
| Column          | Type     | Notes                              |
|-----------------|----------|--------------------------------------|
| id              | Integer  | Primary key                           |
| analysis_id     | Integer  | Foreign key → `analysis.id`           |
| rag_explanation | String   | Nullable                              |
| pdf_path        | String   | Nullable                              |
| created_at      | DateTime | Defaults to current UTC time          |

### `uploaded_features`
| Column           | Type      | Notes                              |
|------------------|-----------|--------------------------------------|
| id               | Integer   | Primary key                          |
| firmware_id      | Integer   | Foreign key → `firmware.id`          |
| feature_vector   | JSONB     | Nullable — extracted feature vector  |
| similarity_score | Float     | Nullable                             |
| upload_time      | DateTime  | Defaults to current UTC time         |

Relationships: one `firmware` record can have many `analysis` records
and many `uploaded_features` records; one `analysis` record can have
many `reports` records.

---

## 4. Model Registry (`ml/saved_models/`)

As of Phase 6, `ml/saved_models/` holds a **real, trained, hierarchical**
model — selected automatically from a 4-model benchmark, not assumed —
and its full set of supporting artifacts (see section 8 for how they
were produced):

- `best_model.pkl` — `{"family_model": ..., "algorithm_submodels": {...}}`
  (joblib-serialized): the winning model type/hyperparameters
  (`ExtraTreesClassifier` in the current run) trained once as a global
  family classifier and once per family as an algorithm sub-model
- `model_v1.pkl` — an identical copy, kept for naming backward-compatibility
- `label_encoder.pkl` — the fitted family `LabelEncoder`
- `algorithm_label_encoder.pkl` — the fitted algorithm `LabelEncoder`
- `feature_columns.json` — the ordered, leakage-free, selected feature
  list the model expects as input (see 8.3–8.5)
- `metadata.json` — model version, winning model, dataset version,
  training date, every headline metric, hyperparameters, feature count,
  sample counts, supported families/algorithms
- `metrics.json` — accuracy/precision/recall/F1 (algorithm and family
  stages), both confusion matrices, class names, SHAP top-feature ranking
- `classification_report.json` — scikit-learn's full per-class
  precision/recall/F1/support report (algorithm stage)
- `confusion_matrix.png` — rendered algorithm-stage confusion matrix
- `shap_summary.png` — SHAP summary plot (family-stage global model)
- `scaler.pkl` — retained from Phase 1 scaffolding; unused since
  normalization is baked into `dataset/preprocess.py`'s `*_normalized`
  columns

Additional benchmarking/explainability artifacts (per-model comparison,
both confusion matrices, SHAP bar plot, feature importance ranking) are
saved to `ml/reports/` — see section 8.10.

`ml/predict.py` (Phase 6) is the consumer of these artifacts.

---

## 5. Phase 2A/2B: Offline Dataset Builder (`dataset/`)

This is the pipeline that turns real, compiled open-source cryptographic
libraries into the labeled dataset the future ML classifier will train
on. It runs completely offline and independently of the FastAPI service
— nothing here touches the API, PostgreSQL, or firmware upload.

Everything is driven by `dataset/config.py`: the list of projects and
their Git URLs, the optimization levels and build types to use, the
architectures to target, and the crypto keyword/constant signatures used
for labeling. Adding a project, algorithm keyword, architecture, or
optimization level later is a config change, not a rewrite of
`builder.py`.

The builder generates real samples at **two levels of granularity**:

- **Library-level (Phase 2A):** one row per compiled executable/shared
  library (e.g. `libcrypto.so`). This is accurate but low-volume — a
  handful of rows per project.
- **Algorithm-level (Phase 2B):** one row per individual cryptographic
  algorithm *source file*, compiled standalone across every optimization
  level, build type, and available compiler. This is what makes a
  research-grade dataset of thousands of real samples possible, since a
  single library ships dozens to hundreds of distinct algorithm
  implementations (`aes.c`, `sha256.c`, `rsa.c`, `chacha20.c`, ...), and
  each one becomes many independent, differently-optimized samples.

### 5.1 How repositories are downloaded and updated

`builder.py` clones each configured project (OpenSSL, mbedTLS, wolfSSL,
LibTomCrypt, libsodium) with `git clone --depth 1 --recurse-submodules`
into `dataset/sources/<project>/src/`. If that directory already exists,
cloning is skipped and `git pull --ff-only` is run instead to pick up
upstream changes — nothing is ever re-cloned from scratch, and a failed
update falls back to the existing checkout rather than aborting. No
manual download step is required.

### 5.2 How projects are compiled — two strategies

**Library-level (Phase 2A):** for every configured optimization level
(`O0`–`O3`), `builder.py` resets the checkout to pristine (`git clean
-fdx`), auto-detects the build system (CMake / autotools / plain Make —
falling back to whatever is actually present), and invokes it with
`CC`/`CFLAGS`/`CXXFLAGS` set to the requested compiler and optimization
level.

**Algorithm-level (Phase 2B):** rather than running each project's full
build system, `builder.py` compiles individual algorithm source files
directly with `<compiler> -c file.c -O<n> <build-type-flags> <includes>
-o file.o`. Compiling one translation unit at a time sidesteps almost
all build-system/dependency complexity (no `configure` step, no
generated config headers required for most files) and is dramatically
faster, which is what makes thousands of real samples achievable. Include
paths are **not hardcoded per project** — `discover_header_include_dirs()`
walks the whole checkout and passes every directory containing a header
file as a `-I` flag, so the same code works unmodified across all five
libraries. A source file whose headers can't be resolved this way (a
handful of OpenSSL/mbedTLS files require a header generated by their own
`./Configure`/`cmake` step) simply fails to compile for that file — it
is logged and skipped, never fabricated, and every other file continues.

Both strategies build for every combination of:
- **Optimization level:** `O0`, `O1`, `O2`, `O3`
- **Build type** (Phase 2B only): `debug` (`-g -DDEBUG`) and `release`
  (`-DNDEBUG`), layered on top of the optimization level
- **Compiler:** `gcc` and `clang`, auto-detected at runtime
  (`get_available_compilers()`) — an unavailable compiler is skipped,
  never causing a failure

Phase 2A/2B fully support the host architecture (`x86_64`).
Cross-architecture support (ARM, ARM64, MIPS) is designed in from the
start — `config.ARCHITECTURE_TOOLCHAINS` already has commented-in
entries ready to enable once a cross-compiler is installed; no logic in
`builder.py` needs to change.

A single project, compiler, build variant, or source file failing to
build is logged and skipped — the pipeline always continues with
everything else rather than aborting.

### 5.3 How algorithm implementations are discovered

`discover_algorithm_source_files()` walks a cloned project's source tree
for `.c` files and matches each filename against an ordered list of
algorithm keywords in `config.ALGORITHM_SOURCE_KEYWORDS` (AES, DES,
3DES, Blowfish, Twofish, Camellia, RC4, ChaCha20, Poly1305, RSA, ECC,
X25519, Ed25519, SHA1/224/256/384/512, SHA3, MD5, HMAC, PBKDF2, HKDF,
Argon2). Matching uses exact filename-token comparison first (e.g.
`aes_desc.c` correctly matches `AES` and *not* `DES`, since `desc` is a
whole token, not `des`), then a length-gated substring fallback for
compound filenames like `chachapoly.c`. Files under test/example/demo
directories, or whose name itself marks them as a test/fuzz/benchmark
harness, are excluded. **A file that cannot be matched confidently is
skipped, not guessed at or labeled `NON_CRYPTO`** — Phase 2B only
produces samples it is confident about.

### 5.4 How binaries are discovered and copied

For Phase 2A whole-library builds, `builder.py` walks the build tree
and keeps every file whose first four bytes are the ELF magic number
(`\x7fELF`), which reliably identifies compiled executables and shared
libraries regardless of naming; documentation/test/example directories
and non-binary extensions are filtered out. Every valid binary is
copied into `dataset/compiled/<project>/<optimization_level>/<architecture>/`,
preserving the project name.

For Phase 2B, each successfully compiled object file is written to
`dataset/compiled/<project>/objects/<algorithm>/<source>__<compiler>_<opt>_<build_type>.o`
so the exact build variant is recoverable from the filename alone.

### 5.5 How features are extracted

`dataset/extractor.py` is a standalone, reusable module built around a
single function, `extract_features(binary_path)`, used identically for
both whole-library binaries and standalone object files — so the exact
same extraction logic will later be reused unmodified by the runtime
firmware-analysis pipeline (`analysis/features.py`), guaranteeing
training and inference always share an identical feature schema.

Using **LIEF** for structural parsing and **Capstone** for disassembly,
it extracts: architecture, binary size, Shannon entropy, entry point,
section count, symbol count, imported libraries/functions, printable
string count, a best-effort function count, instruction count and
opcode histogram (from disassembling `.text`), presence of known
cryptographic constants (AES S-box, SHA-1/SHA-256/MD5 initial hash
values, matched as raw byte signatures so they're detected even in
stripped binaries), and presence of crypto-related symbol names. **Any
feature that cannot be determined for a given binary is stored as
`None`** — never a fabricated placeholder value. (LIEF parses object
files as `FILE_TYPE.REL` binaries — their `.text`/symbol table are still
present, so the same extraction works; an object file's `entry_point` is
naturally `0`, since relocatable objects have no entry point, and
`import_libraries` is naturally empty, since an unlinked object has no
runtime dependencies yet.)

### 5.6 How labels and CSVs are generated

- **Phase 2A rows** use `infer_label()`, which checks filename keywords,
  path keywords, then crypto symbol/constant evidence from the extracted
  features, falling back to `NON_CRYPTO` if nothing matches.
- **Phase 2B rows** use the algorithm identified during source discovery
  directly (5.3) — a stronger label than post-hoc inference, since it
  comes from the matched implementation file itself.

Every row includes `binary_name`, `project`, `algorithm_label`,
`architecture`, `optimization_level`, `compiler`, `compiler_version`,
`build_type`, `build_system` (`"direct_compile"` for Phase 2B rows),
`binary_type` (`object` / `shared_library` / `static_library` /
`executable`), every extracted feature, and `crypto_library`. All rows
(Phase 2A and 2B combined) are written to `dataset/data/raw/dataset.csv`
with exact duplicates dropped, alongside `dataset_metadata.json`
capturing `dataset_version`, `generation_date`,
`generation_duration_seconds`, `projects_used`, `algorithms_detected`,
`compiler_versions`, `optimization_levels`, `build_types`,
`architectures`, `total_binaries`, `total_samples`,
`total_unique_binaries`, and `total_features`.

### 5.7 How preprocessing works

`dataset/preprocess.py` reads `dataset.csv` and, without ever discarding
or fabricating information:

1. Removes exact duplicate rows.
2. Imputes missing numeric values with the column median (or `0` if a
   column has no non-missing values at all, e.g. `import_libraries` for
   object-file samples) plus a `<column>_was_missing` indicator column,
   and fills missing categorical values with `"UNKNOWN"`.
3. Label-encodes categorical columns (`project`, `architecture`,
   `optimization_level`, `compiler`, `compiler_version`, `build_type`,
   `build_system`, `binary_type`, `crypto_library`), saving the encoding
   map used.
4. Min-max normalizes numeric feature columns, saving the scaler
   parameters used.
5. Splits the result 80/20 into train/test sets — stratified per
   `algorithm_label` when every class has enough members, otherwise a
   plain random split — and writes `train.csv` and `test.csv` to
   `dataset/data/processed/`, plus `preprocessing_metadata.json`.

No model is trained by this step or anywhere else in Phase 2A/2B.

### 5.8 Logging, run summaries, and dataset scale

Every run writes a timestamped log file to `dataset/logs/` in addition
to streaming to stdout, covering repository cloning/updates, algorithm
discovery, compilation progress per compiler/optimization
level/build type, binary discovery, feature extraction, CSV generation,
and preprocessing. At the end of a run, `builder.py` prints a summary of
successful/failed projects (with reasons), algorithms detected, total
library-level binaries processed, total algorithm-level objects
compiled vs. skipped/failed, and total dataset rows generated.

The framework is designed to reach **~5,000–7,000 real samples**
(`config.TARGET_SAMPLE_COUNT_MIN` / `_MAX`) by exhaustively compiling
every discovered algorithm source file across every optimization
level × build type × available compiler. In practice, running the
Phase 2B object pipeline against LibTomCrypt, mbedTLS, libsodium,
wolfSSL, and (after fixing the generic include-path discovery to also
add each header's *parent* directory, needed for OpenSSL's namespaced
`#include "internal/foo.h"` style includes) OpenSSL produced **7,095
real, unique compiled-object samples across 24 algorithm labels**
(LibTomCrypt alone contributed 2,432 objects across 22 algorithms,
spanning AES through Ed25519; OpenSSL contributed a further 2,071 once
its per-file compilation was unblocked). Any remaining source file that
still can't be resolved (a handful need additional build-generated
headers) is skipped by the fast standalone-compile strategy — every
skip is logged, never fabricated — and is still fully supported by the
slower Phase 2A whole-library build path.

### 5.9 Running the dataset builder

From `backend/dataset/`, with the virtual environment activated and
dependencies installed:

```bash
# Build the full dataset: whole-library builds (Phase 2A) + per-algorithm
# object compilation (Phase 2B) for all 5 configured libraries, all 4
# optimization levels, both build types, every available compiler.
python builder.py

# Then preprocess the result into train/test sets.
python preprocess.py
```

Running everything (both pipelines, all 5 libraries) end-to-end can take
a long time — the Phase 2A whole-library builds in particular (OpenSSL
and wolfSSL have large build graphs), while the Phase 2B object pipeline
is fast (hundreds of compiles per minute). Requires `git`, `gcc`
and/or `clang`, and — for whole-library builds of some projects —
`autoconf`/`automake`/`libtool` or `cmake` already installed.

To run a specific slice (e.g. only the fast, high-yield object pipeline,
against a subset of projects), call the pipeline directly:

```python
from builder import run_pipeline
from preprocess import run_preprocessing

run_pipeline(
    projects=["libtomcrypt", "libsodium", "wolfssl"],
    optimization_levels=["O0", "O1", "O2", "O3"],
    build_types=["debug", "release"],
    compilers=["gcc", "clang"],
    run_library_level=False,   # skip slow whole-library builds
    run_object_level=True,     # run the high-yield per-algorithm pipeline
)
run_preprocessing()
```

---

## 6. Phase 3: Firmware Input Module (`input/`, `api/routes.py`)

This is the module that accepts firmware files from users, validates
them, stores them safely on disk, and records their metadata in
PostgreSQL. **It is intake-only** — it does not extract, analyze,
classify, or otherwise inspect what's inside the firmware; that is
later-phase work.

Everything configurable lives in `config.py`: the upload directory
(`UPLOAD_DIR`), the maximum upload size (`MAX_UPLOAD_SIZE_MB`), the
allowed file extensions (`ALLOWED_FIRMWARE_EXTENSIONS`), and the
allowed MIME types (`ALLOWED_FIRMWARE_MIME_TYPES`) — none of these are
hardcoded in `input/upload.py` or `input/validator.py`.

### 6.1 Supported firmware formats

Only `.bin`, `.img`, and `.elf` are accepted. This list is not
hardcoded — it comes from the `ALLOWED_FIRMWARE_EXTENSIONS` environment
variable (comma-separated, e.g. `bin,img,elf`), defaulting to those
three if unset. Any other extension is rejected with `415 Unsupported
Media Type` and `{"detail": "Unsupported firmware format."}`.

### 6.2 Upload workflow

`POST /firmware/upload` runs the following steps, each logged:

1. **Validate metadata** (`input/validator.py`) — filename present,
   extension in the allow-list, and a best-effort MIME type check via
   Python's standard `mimetypes` module. Firmware extensions like
   `.bin`/`.img`/`.elf` are not registered in `mimetypes`' database, so
   an unrecognized (`None`) MIME type is expected and accepted; a
   *recognized but disallowed* MIME type is rejected.
2. **Stream to a temp file while hashing** (`input/upload.py`) — the
   upload is read and written in 1 MiB chunks (never loaded into memory
   whole), with `hashlib.sha256()` updated incrementally. The maximum
   upload size is enforced *during* the stream, so an oversized file is
   rejected as soon as it crosses the limit rather than after being
   fully written.
3. **Validate size** — reject an empty (0-byte) file with `400 Bad
   Request`, or an oversized file with `413 Request Entity Too Large`.
4. **Duplicate detection** — the computed SHA-256 is looked up against
   existing `firmware` rows. A match returns the *existing* record's ID
   and a `"Already Uploaded"` status without creating a new row or a
   new file on disk.
5. **Persist** — for a genuinely new firmware, a `firmware` row is
   inserted (status `"Uploaded"`) to obtain an auto-generated ID, the
   temp file is moved into `uploads/<firmware_id>/<original_filename>`,
   and that relative path is recorded as `storage_path`.

### 6.3 SHA-256 generation

Computed with `hashlib.sha256()` over the upload in 1 MiB chunks as it
streams to disk (see 6.2, step 2) — the file is never read into memory
in full, so upload size is not limited by available RAM. The resulting
64-character hex digest is stored in the `firmware.file_hash` column
(unique, indexed).

### 6.4 Duplicate detection

Every new upload's hash is compared against `firmware.file_hash` before
a database row is created. If a match is found:

```json
{
  "message": "Firmware already exists.",
  "firmware_id": 15,
  "sha256": "...",
  "status": "Already Uploaded"
}
```

No duplicate row and no duplicate file are ever created — the
temporary file is discarded immediately.

### 6.5 Storage structure

```
uploads/
└── <firmware_id>/
    └── <original_filename>
```

Example: `uploads/23/router.bin`. The directory is created
automatically per firmware ID, the original filename is always
preserved, and because each ID is unique and auto-generated, a file is
**never overwritten** — if a destination somehow already existed, the
upload would fail with `500 Internal Server Error` rather than silently
replace it. The relative path (e.g. `"23/router.bin"`) is what's stored
in `firmware.storage_path`, not an absolute filesystem path.

### 6.6 API endpoints

| Method | Path | Description |
|--------|------|--------------|
| `POST` | `/firmware/upload` | Upload a firmware file; returns the new record or a duplicate notice. |
| `GET` | `/firmware` | List all uploaded firmware records, most recent first. |
| `GET` | `/firmware/{firmware_id}` | Get metadata for one firmware record (`404` if not found). |

No `PUT`, `DELETE`, or analysis endpoints exist yet — this module is
intake-only.

**Successful upload** (`200 OK`):
```json
{
  "firmware_id": 23,
  "filename": "router.bin",
  "file_hash": "b6a47146d9b9c11159f7f592734fc2c690134c6d319e5b4b607cf47a0750006a",
  "file_size": 65536,
  "status": "Uploaded"
}
```

**Duplicate upload** (`200 OK`): see 6.4 above.

**Invalid extension** (`415 Unsupported Media Type`):
```json
{"detail": "Unsupported firmware format."}
```

Other error responses: `400` (missing/empty file), `413` (oversized
file), `404` (firmware ID not found), `500` (storage or database
failure — internal exception details are never exposed to the client;
they are logged server-side instead).

### 6.7 Firmware status lifecycle

`models.FirmwareStatus` defines the full set of statuses later phases
will use: `Uploaded` → `Extracting` → `Extracted` → `Analyzing` →
`Completed` (or `Failed` at any point). **Phase 3 only ever sets
`Uploaded`** — no analysis-related fields are populated during intake.

---

## 7. Phase 4: Firmware Analysis Engine (`analysis/`)

This is the **shared** static analysis engine used to turn a compiled
binary — whether it's one of the thousands of samples the offline
Dataset Builder compiles, or an executable discovered inside a user's
uploaded firmware — into the exact same feature schema. There is
**one** feature-extraction implementation in the entire codebase,
`analysis/features.py`; the Dataset Builder does not have its own
copy, it imports this one.

### 7.1 Pipeline

```
Firmware
  │
  ▼
Binwalk extraction (analysis/firmware.py)
  │
  ▼
Filesystem extraction (Binwalk's output directory)
  │
  ▼
Executable discovery (analysis/binary.py: discover_binaries)
  │
  ▼
ELF parsing (analysis/binary.py: parse_elf, via LIEF)
  │
  ▼
Disassembly (analysis/disassembler.py, via Capstone)
  │
  ▼
Feature extraction (analysis/features.py: extract_features)
  │
  ▼
feature_vector.json
```

Every executable discovered inside a firmware image is analyzed
**independently** — a firmware containing `busybox`, `dropbear`,
`libcrypto.so`, and `httpd` produces four separate feature vectors, and
a single binary's parsing/disassembly failure never stops the rest from
being processed (see 7.7).

### 7.2 Module breakdown

| Module | Responsibility |
|--------|------------------|
| `firmware.py` | Runs Binwalk to extract a `.bin`/`.img`/`.elf` firmware image into `analysis_output/<firmware_id>/`. Always leaves the original file available for analysis even if nothing was extractable. |
| `binary.py` | Recursively discovers ELF executables/shared libraries (ignoring images, fonts, configs, docs, temp files), and parses each with LIEF into structured metadata. |
| `disassembler.py` | Disassembles a binary's `.text` section with Capstone; instruction-level statistics only — no control-flow graph is built. |
| `constants.py` | The centralized cryptographic signature database (magic constants, symbol keywords, known library names) that both `features.py` and the Dataset Builder's labeling rely on. |
| `features.py` | **The single canonical `extract_features()` implementation.** Combines `binary.py` + `disassembler.py` + `constants.py` into one feature vector; also writes `feature_vector.json`. |
| `similarity.py` | Cosine similarity between two feature vectors, for comparing an uploaded binary against previously analyzed ones. Not used for ML classification. |
| `utils.py` | Shared helpers: entropy, string extraction, streaming SHA-256, safe file I/O, content-based MIME typing (`python-magic`). |

### 7.3 Firmware extraction (Binwalk)

`analysis.firmware.extract_firmware(firmware_path, firmware_id,
output_root)` runs `binwalk --extract --directory=<output_dir>
--run-as=root <file>` (the `--run-as=root` flag is required because
Binwalk refuses to run its extraction utilities as root otherwise) and
returns an `ExtractionResult(success, output_dir, message)`. The
original firmware file is always copied into
`<output_dir>/original/` as well, so binary discovery has something to
examine even when Binwalk finds no embedded filesystem to carve out
(e.g. a raw firmware blob, or an already-standalone `.elf`). A missing
Binwalk installation, a timeout, or a non-zero exit code is logged and
reflected in the returned result — never raised as an exception that
could take down the application.

### 7.4 ELF parsing (LIEF)

`analysis.binary.parse_elf()` extracts architecture, bitness,
endianness, entry point, sections (with per-section entropy), segments,
imported libraries/functions, exported functions, and the full symbol
table, plus the binary's size and SHA-256 hash. Discovery
(`discover_binaries()`) combines an ELF magic-byte check with
content-based MIME typing via `python-magic`, so a misleadingly-named
file (e.g. an image renamed without its extension) is still correctly
excluded.

### 7.5 Disassembly (Capstone)

`analysis.disassembler.disassemble_section()` disassembles raw section
bytes and returns instruction count, a full opcode/mnemonic histogram,
a normalized instruction-frequency map, and counts for six instruction
categories: jump, call, return, arithmetic, logical, and memory
(`branch_count` = jump + call). **No control-flow graph is
reconstructed** — this is linear disassembly and instruction-level
statistics only, per the Phase 4 scope.

### 7.6 Feature extraction — one shared schema

`analysis.features.extract_features(binary_path)` is called identically
by the Dataset Builder and by runtime firmware analysis. It preserves
every original Phase 2 dataset column exactly (`architecture`,
`binary_size`, `entropy`, `entry_point`, `section_count`,
`symbol_count`, `import_count`, `import_libraries`, `string_count`,
`function_count`, `instruction_count`, `opcode_histogram`, and the
original six crypto-evidence flags), so existing `dataset.csv` output
stays schema-compatible, and adds new fields for Phase 4:
`segment_count`, `export_count`, `section_entropy`, `compiler_hints`
and `optimization_hints` (both best-effort, non-authoritative),
`known_crypto_library`, and an expanded `crypto_evidence` dict covering
all sixteen algorithms in `constants.py` (AES, DES, 3DES, SHA-1/224/
256/384/512, RSA, ECC, ChaCha20, Poly1305, RC4, Blowfish, Twofish,
Camellia). As always, any feature that can't be determined is `None` —
never a fabricated value.

**`dataset/extractor.py` no longer implements extraction itself** — it
is now a thin shim that re-exports `analysis.features.extract_features`
(see the module's own docstring). This is the concrete mechanism that
guarantees the Dataset Builder and runtime analysis can never drift
into two different feature schemas.

### 7.7 Error handling and logging

Every stage — extraction, discovery, ELF parsing, disassembly, feature
generation, similarity — logs its progress and any failures. A single
executable that fails to parse or disassemble is logged and skipped;
the rest of the firmware's executables are still processed
(`extract_features_batch()` never lets one failure abort the batch). A
firmware that fails extraction entirely still returns a structured,
meaningful `ExtractionResult` rather than raising — the application
never terminates because of one bad firmware image or one corrupt
binary inside it.

### 7.8 Performance

Large firmware images are supported by design: `analysis.utils.sha256_file()`
and `analysis.firmware`'s file copy both stream in 1 MiB chunks rather
than loading a file into memory whole, so a 500+ MB firmware image is
never fully buffered in RAM during hashing or extraction staging.

---

## 8. Phase 6: Research-Grade ML Benchmarking Framework (`ml/train.py`)

Phase 6 replaces Phase 5A's single flat `RandomForestClassifier` with a
reproducible **benchmarking framework**: multiple models are
cross-validated and hyperparameter-tuned under identical conditions,
the winner is selected automatically (never assumed), and a
**hierarchical** two-stage classifier (cryptographic family, then
specific algorithm) is trained using that winning configuration. It is
still training-only — no FastAPI endpoint (see section 9 for the
runtime counterpart).

### 8.1 Why this upgrade exists

Phase 5A's flat classifier reported ~78% test accuracy, but its
Phase 5B runtime predictions were often wrong and low-confidence (see
that phase's now-resolved "known limitation"). The root cause: several
of the model's most important features (`project_encoded`,
`compiler_encoded`, `crypto_library_encoded`, ...) described *which
open-source library and build configuration a training sample came
from* — information a real uploaded firmware binary can never have.
The model had learned to recognize the Dataset Builder's own
fingerprints, not the cryptographic algorithms themselves. Phase 6 is
built around fixing that at the source.

### 8.2 Training workflow

```
train.csv
  │
  ▼
Feature validation (missing dataset / corrupted CSV / missing label -- caught early)
  │
  ▼
Metadata-leakage removal          <- resolve_candidate_feature_columns()
  │
  ▼
Feature selection (constant / correlated / low-importance)  <- select_features()
  │
  ▼
Stratified 5-Fold CV + hyperparameter search, per model      <- benchmark_models()
  │
  ▼
Automatic best-model selection (macro F1 -> balanced accuracy -> inference time)
  │
  ▼
Hierarchical training: family model + per-family algorithm sub-models
  │
  ▼
ONE final evaluation on test.csv (never touched before this point)
  │
  ▼
SHAP explainability + reports
  │
  ▼
Save best_model.pkl
```

`train.csv` is used *only* for cross-validation, hyperparameter search,
and model selection. `test.csv` is loaded once, at the very end, for
the official reported performance — never used to pick a model or tune
a hyperparameter, so the reported numbers are an honest estimate of
generalization rather than a number the pipeline indirectly optimized for.

### 8.3 Metadata-leakage removal

`resolve_candidate_feature_columns()` excludes `project`, `binary_name`,
`crypto_library`, `compiler`, `compiler_version`, `build_system`,
`optimization_level`, and `binary_type` — in both their raw and
`_encoded` forms — from the feature matrix entirely, rule-based rather
than as a fixed list that could go stale. `architecture_encoded` is
kept, since architecture is a real property of a binary's content, not
Dataset Builder provenance. In the current dataset, this removes every
dataset-provenance feature, leaving only genuine binary-content
signals: normalized numeric metrics and boolean crypto-evidence flags.

### 8.4 Feature engineering (extends, never removes, Phase 4's features)

`analysis/features.py` (the single shared feature-extraction
implementation used by both the Dataset Builder and runtime analysis —
unchanged principle from Phase 4) was extended with:

- **Opcode n-grams:** bigram/trigram entropy and unique-token ratio
  (captures instruction *sequencing*, not just individual opcode
  frequency, as fixed-width scalar features so they stay
  tabular-friendly regardless of which specific n-grams occur).
- **Instruction entropy** and **unique opcode ratio**.
- **Lightweight CFG/call-graph approximations** (`basic_block_count_estimate`,
  `cfg_edge_count_estimate`, `cyclomatic_complexity_estimate`,
  `call_graph_fanout_estimate`) derived from linear disassembly's
  jump/call counts — no control-flow graph is actually reconstructed
  (unchanged Phase 4 scope); these are principled, documented
  approximations, not exact CFG metrics.
- **Section permission ratios** (`executable_section_ratio`,
  `readonly_section_ratio`, `writable_section_ratio`) from ELF segment
  flags — populated for linked binaries/shared libraries; `None` for
  raw object files, which have no `PT_LOAD` segments yet (an honest
  ELF-semantics limitation, not a bug).
- **Crypto constant occurrence counts** (not just presence booleans) for
  every magic constant in `analysis/constants.py`.
- **RSA exponent detection** (the near-universal public exponent 65537)
  and **ECC curve OID detection** (P-256, P-384, P-521, secp256k1).

`dataset/builder.py`'s row-construction functions now automatically
include every scalar feature `extract_features()` returns
(`_flatten_scalar_features()`), so a future feature addition flows into
the dataset without needing this function edited again.

### 8.5 Feature selection

`select_features()` automatically removes, from the leakage-free
candidate list: constant features (single unique value), one feature
from every pair with `|Pearson r| > 0.95`, and the bottom 5% by
importance from a quick RandomForest fit. The final list is persisted
to `ml/saved_models/feature_columns.json` — in the current dataset,
28 features survive selection out of ~80 candidates.

### 8.6 Model benchmarking and automatic selection

Four models are registered (`MODEL_REGISTRY`, extensible by adding one
entry): `RandomForestClassifier`, `ExtraTreesClassifier`,
`HistGradientBoostingClassifier`, and `XGBClassifier`. Each is tuned
independently with `RandomizedSearchCV` over its own parameter space,
scored via **Stratified 5-Fold cross-validation** (`StratifiedKFold(n_splits=5,
random_state=42)`) on macro F1, with class imbalance handled via
per-fold `sample_weight` (`compute_sample_weight("balanced", ...)`)
rather than a `class_weight` argument that not every model supports
uniformly. **No model is assumed best.** Ranking is: macro F1 (primary)
→ balanced accuracy (first tie-breaker) → mean inference time (second
tie-breaker, lower is better). A real benchmark run on the current
dataset ranked `ExtraTreesClassifier` first (cv macro F1 ≈ 0.969), ahead
of `RandomForestClassifier` (≈ 0.964), `XGBClassifier` (≈ 0.948), and
`HistGradientBoostingClassifier` (≈ 0.941) — genuinely determined by
the benchmark, not assumed in advance.

### 8.7 Hierarchical classification

Stage 1 predicts a **cryptographic family** — `Symmetric Encryption`,
`Stream Cipher`, `Hash Functions`, `Message Authentication`, `Public
Key Cryptography`, and (a pragmatic, honestly-labeled extension for the
KDF algorithms the dataset genuinely contains) `Key Derivation` — using
one global model trained on all training rows. Stage 2 predicts the
**specific algorithm**, using a *separate sub-model per family*,
trained only on that family's rows/classes (`train_algorithm_submodels()`),
with the same model type and hyperparameters the Stage-1 benchmark
selected (a deliberate, documented simplification — an independent
search per family would multiply the already-substantial Stage-1 search
cost six-fold for little additional gain on families with few classes).
At inference, `hierarchical_predict()` runs Stage 1, then routes each
row to its predicted family's Stage-2 sub-model — batched by family for
efficiency, not row-by-row.

The family taxonomy lives in `analysis/constants.py`
(`ALGORITHM_FAMILIES`), so both training and runtime inference share
one source of truth for "which family is SHA256 in".

### 8.8 Final evaluation and real results

A real production run (`SEARCH_ITERATIONS=5`, `CV_FOLDS=5`) against the
current 7,095-sample dataset (5,666 train / 1,429 test, 24 algorithm
classes across 6 families) completed in **~4.8 minutes** and achieved,
on the held-out test set (evaluated exactly once):

| Metric | Value |
|--------|--------|
| Algorithm accuracy | **95.24%** |
| Algorithm F1 (macro) | **93.37%** |
| Algorithm balanced accuracy | 93.84% |
| Family accuracy | **98.25%** |
| Family F1 (macro) | 98.08% |
| Family ROC-AUC (macro, OVR) | computed and stored in `metrics.json` |

This is a substantial, genuine improvement over Phase 5A's ~78% flat
accuracy — not from a bigger model, but from removing the leaked
features that were letting the old model cheat, adding real
binary-content signal, and structuring the problem hierarchically.
Algorithm-level ROC-AUC is intentionally omitted: each family's
sub-model only produces probabilities over its own classes, so a single
well-defined 24-class probability matrix isn't available without
additional bookkeeping kept out of this phase's scope — accuracy, F1,
and the confusion matrix are the primary Stage-2 metrics reported.

### 8.9 Explainability (SHAP)

SHAP `TreeExplainer` runs against the family-level model (the one
global model in the hierarchy) over a 200-row sample of the test set,
producing a global summary plot, a bar plot, and a top-feature ranking
— saved to both `ml/reports/` and (summary plot, for backward
compatibility) `ml/saved_models/`. The top-ranked features in the
current run are `chacha_symbol`, `aes_symbol`, `ecc_symbol`,
`rsa_symbol`, and `entropy_normalized` — real binary-content evidence,
not dataset fingerprints. `explain_single_prediction()` (training-side)
and `ml/predict.py`'s `_explain_prediction()` (runtime-side) reuse the
same `TreeExplainer` construction for **per-prediction** explanations.

### 8.10 Reports and artifacts

| Location | File | Contents |
|----------|------|-----------|
| `ml/saved_models/` | `best_model.pkl` | `{"family_model": ..., "algorithm_submodels": {...}}` (joblib) |
| `ml/saved_models/` | `model_v1.pkl` | Identical copy, kept for naming backward-compatibility |
| `ml/saved_models/` | `label_encoder.pkl` | Family `LabelEncoder` |
| `ml/saved_models/` | `algorithm_label_encoder.pkl` | Algorithm `LabelEncoder` |
| `ml/saved_models/` + `ml/reports/` | `feature_columns.json`, `metrics.json`, `classification_report.json`, `confusion_matrix.png` / `algorithm_confusion_matrix.png` | Shared between both locations |
| `ml/reports/` | `benchmark_results.json` | Every model's CV macro F1, balanced accuracy, inference time, and best hyperparameters, plus the declared winner |
| `ml/reports/` | `family_confusion_matrix.png`, `shap_summary.png`, `shap_bar.png`, `feature_importance.csv` | Family-stage confusion matrix and full SHAP explainability output |
| `ml/saved_models/` | `metadata.json` | Model version (`"2.0"`), winning model name, dataset version, training date, every headline metric, training duration, mean prediction time, winning hyperparameters, feature count, train/test sample counts, supported families/algorithms |

### 8.11 Retraining

```bash
cd backend/ml
python train.py
```

Works identically regardless of dataset size (no hardcoded sample-count
assumptions) — the same code path handles the current 7,095-sample
dataset or a future 12,000-sample one. Delete
`ml/saved_models/feature_columns.json` first if the underlying feature
schema itself changed (e.g. after adding a new feature to
`analysis/features.py`) and the candidate set should be re-derived
before re-running selection.

---

## 9. Phase 6: Runtime Hierarchical ML Inference (`ml/predict.py`)

This is the **runtime** counterpart to section 8's offline
benchmarking: it loads `best_model.pkl` once, consumes feature vectors
the Firmware Analysis Engine already produced, and returns **both** the
predicted cryptographic family and the specific algorithm. **It never
retrains the model and never extracts features** — `ml/train.py`,
`analysis/`, `ml/risk.py`, and `ml/recommend.py` are all untouched by it.

### 9.1 Runtime prediction workflow

`POST /predict/{firmware_id}` expects the firmware to already be
uploaded (Phase 3) and already analyzed (Phase 4 — i.e.
`feature_vector.json` file(s) already exist under
`ANALYSIS_OUTPUT_DIR/<firmware_id>/`). It does **not** upload firmware,
run Binwalk, or extract features itself:

```
Firmware already uploaded
        │
        ▼
Analysis Engine already generated feature_vector.json
        │
        ▼
Load feature vector(s)            <- ml/predict.load_feature_vectors_for_firmware
        │
        ▼
Validate + derive model features  <- ml/predict.validate_and_prepare_features
        │
        ▼
Stage 1: family_model.predict() / predict_proba()
        │
        ▼
Stage 2: algorithm_submodels[family].predict() / predict_proba()
        │
        ▼
Store prediction in `analysis` table
        │
        ▼
Return response (family + algorithm + confidence + timing)
```

If the firmware doesn't exist, the endpoint returns `404`. If no
`feature_vector.json` exists for it yet, it also returns `404` with a
clear message to run the Firmware Analysis Engine first.

### 9.2 Model loading

`ml.predict.get_model_bundle()` loads `best_model.pkl` (falling back to
`model_v1.pkl` for naming compatibility), the family and algorithm
`LabelEncoder`s, `feature_columns.json`, and `metadata.json`, plus the
dataset's `preprocessing_metadata.json` for numeric scaler parameters.
Decorated with `functools.lru_cache`, so **the model bundle is loaded
exactly once per process** and reused for every request. A missing or
malformed `best_model.pkl` (e.g. not the expected
`{"family_model": ..., "algorithm_submodels": ...}` shape) raises
`ModelLoadError`, which the API turns into `503 Service Unavailable`.

### 9.3 Feature validation and derivation — the leakage fix in practice

`validate_and_prepare_features()` re-derives every `*_normalized`
feature from its raw source using the exact min-max parameters learned
during training, passes the boolean crypto-evidence/curve-detection
flags through as `0`/`1`, and reorders the result to exactly match
`feature_columns.json`. **Because Phase 6's feature selection removed
every dataset-provenance column**, this derivation is now
overwhelmingly simple in practice — no more encoding dataset-provenance
fields as `-1` "not applicable" placeholders, because none survived
into the selected feature set. Concretely, this closes the exact gap
Phase 5B's README documented as a known limitation: a real AES object
file that Phase 5B predicted as *"Argon2" at 30% confidence* is now
correctly predicted as **AES at 97.15% confidence** by the Phase 6
model — verified against the same real compiled binary.

If a field the model genuinely needs is absent, validation raises
`PredictionValidationError`, which the API turns into `422
Unprocessable Content` naming exactly which fields are missing.

### 9.4 Hierarchical prediction and confidence

`predict_single()` runs Stage 1 (family) then routes to the matching
Stage-2 sub-model for the specific algorithm, reporting the winning
class's probability from each stage as a `0–100` confidence score.
`prediction_time_ms` is measured around the actual `predict()`/
`predict_proba()` calls (excluding feature-vector loading), and
`feature_count_used` reports how many features the loaded model
actually expects — both useful for monitoring model performance over
time without needing to inspect logs.

### 9.5 Batch prediction

`predict_batch()` runs every discovered executable's feature vector
through hierarchical prediction independently — one binary's failure
is logged and recorded in a `failures` list, never stopping the rest.

### 9.6 Storing predictions

Each successful prediction writes a new `analysis` row — `firmware_id`,
`algorithm` (the Stage-2 result), and `confidence`. `risk_score`,
`risk_level`, and `recommendation` remain `NULL` (later phases).

### 9.7 API endpoint and response shapes

**Exactly one executable:**
```json
{
  "firmware_id": 15,
  "binary_name": "libcrypto.so",
  "algorithm_family": "Symmetric Encryption",
  "algorithm": "AES",
  "confidence": 98.73,
  "model": "ExtraTreesClassifier",
  "model_version": "2.0",
  "prediction_time_ms": 12.4,
  "feature_count_used": 28
}
```

**Multiple executables:**
```json
{
  "firmware_id": 15,
  "model": "ExtraTreesClassifier",
  "model_version": "2.0",
  "predictions": [
    {"binary_name": "libcrypto.so", "algorithm_family": "Symmetric Encryption", "algorithm": "AES", "confidence": 98.7, "prediction_time_ms": 11.9},
    {"binary_name": "libssl.so", "algorithm_family": "Hash Functions", "algorithm": "SHA256", "confidence": 97.9, "prediction_time_ms": 10.2}
  ],
  "failed": []
}
```

| Status | Meaning |
|--------|----------|
| `200` | Prediction(s) returned successfully |
| `404` | Firmware not found, or no analysis results exist for it yet |
| `422` | Every feature vector found failed validation |
| `503` | The trained model artifacts could not be loaded |
| `500` | An unexpected internal error (never exposes the raw exception) |

---

## 10. Phase 6/7: Risk Assessment & Recommendation Engine (`ml/risk.py`, `ml/recommend.py`)

This is a **deterministic, explainable, non-ML** engine that turns an
ML prediction (section 9) plus the already-extracted feature vector and
binary metadata (section 7) into a weighted security risk score and a
set of specific, actionable recommendations. **No machine learning
model, AI, or LLM is used anywhere in this module** — the same inputs
always produce the same output, and every point of the final score
traces back to a named, logged, configured factor.

### 10.1 Risk scoring methodology

```
Risk Score = Σ (category_weight × normalized_factor)     capped to [0, 100]
```

Four weighted categories, each independently configurable in
`ml/risk_config.json` (`category_weights`): **Algorithm Strength**
(30 pts), **Deprecated Algorithm** (20 pts), **Binary Security**
(30 pts, split across 10 sub-factors), and **Firmware Metadata**
(15 pts, split across 5 sub-factors). No weight or threshold is
hardcoded in `ml/risk.py` — every number in the scoring logic is read
from configuration, so adding a new algorithm, rule, or recommendation
never requires a code change.

### 10.2 Risk factors evaluated

- **Cryptographic algorithm strength** — a continuous per-algorithm
  weakness score (`algorithm_strength_scores`, 0 = strong like
  AES-256/SHA-256/ChaCha20, 1 = weak like DES/RC4/MD5).
- **Deprecated algorithms** — a categorical flag for DES, 3DES, RC4,
  MD5, and SHA1 (`deprecated_algorithms`), scored independently of the
  continuous strength score above.
- **Binary security** (from the Phase 4 feature vector, plus richer ELF
  structural metadata re-parsed from the analyzed binary when
  available): writable+executable sections (W^X violation), debug
  symbols / unstripped build, high entropy, missing symbols, suspicious
  imports (`system`, `strcpy`, `gets`, ...), hardcoded crypto constants,
  weak compiler protections (missing `__stack_chk_fail`), large
  executable surface, missing relocation protection (no PIE), and
  missing stack protection. A sub-factor whose underlying signal isn't
  available contributes 0 and is logged as such, never guessed.
- **Firmware metadata**: unknown compiler, old compiler version
  (parsed from the GCC/Clang version string), architecture mismatch,
  missing metadata, and firmware age.
- **Confidence adjustment**: when ML confidence is below
  `confidence_adjustment.low_confidence_threshold` (default 50%), only
  the two *algorithm-dependent* factors (strength, deprecated) are
  blended part-way toward a neutral score — bounded by
  `minimum_trust_factor` (default 0.85) so the score is never pulled
  more than 15% of the way to neutral. Binary-security and
  firmware-metadata factors are never touched by this adjustment, since
  their validity doesn't depend on the ML prediction being correct.

### 10.3 Risk levels

| Score | Level |
|-------|--------|
| 0–20 | Safe |
| 21–40 | Low |
| 41–60 | Medium |
| 61–80 | High |
| 81–100 | Critical |

Configured in `risk_config.json`'s `risk_levels` array — both the
numeric score and the textual level are always returned together.

### 10.4 Recommendation engine

`ml/recommend.py` generates recommendations by direct, deterministic
lookup: every *triggered* risk factor (`contribution > 0`) maps to a
specific recommendation string in `ml/recommendation_rules.json`
(algorithm-specific rules take priority over the generic
deprecated-algorithm message). Recommendations are specific ("Replace
RC4 with ChaCha20 or AES-GCM"), actionable (a concrete next step, often
with the exact compiler flag), evidence-based (only generated for
factors that actually triggered), and deterministic — no AI or LLM
involved. A real run against a compiled RC4 implementation produced:

```json
["Replace RC4 with ChaCha20 or AES-GCM.",
 "Strip debug symbols before production release (e.g. `strip --strip-debug`).",
 "If cryptographic keys or secrets are embedded directly in the binary, store them in a secure hardware element (TPM/HSM/Secure Enclave) or an encrypted key store instead.",
 "Recompile as a Position-Independent Executable (`-fPIE -pie`) to enable ASLR."]
```

### 10.5 API endpoint

`POST /risk/{firmware_id}` runs the full pipeline: firmware lookup →
ML prediction (Phase 6, reusing `ml.predict`) → risk assessment
(`ml.risk.assess_risk()`) → recommendations (`ml.recommend.generate_recommendations()`)
→ store in the `analysis` table → return. Like `/predict`, it expects
`feature_vector.json` file(s) to already exist for the firmware
(Phase 4) and does not upload firmware, run Binwalk, or extract
features itself.

**Response** (verified against a real compiled RC4 binary):
```json
{
  "firmware_id": 71,
  "binary_name": "rc4_fw.bin",
  "algorithm_family": "Stream Cipher",
  "algorithm": "RC4",
  "confidence": 99.41,
  "risk_score": 80.5,
  "risk_level": "Critical",
  "risk_factors": ["Algorithm Strength", "Deprecated RC4", "Debug Symbols", "Hardcoded Cryptographic Constants", "Missing Relocation Protection (No PIE)"],
  "recommendations": ["Replace RC4 with ChaCha20 or AES-GCM.", "..."]
}
```

For a firmware with multiple analyzed executables, the response wraps
per-binary assessments in a `{"firmware_id": ..., "assessments": [...]}`
shape, matching the established pattern from `/predict` (section 9.7).

| Status | Meaning |
|--------|----------|
| `200` | Assessment(s) returned successfully |
| `404` | Firmware not found, or no analysis results exist for it yet |
| `422` | Every binary's assessment failed (missing prediction/feature vector) |
| `500` | Risk/recommendation configuration is invalid, or an unexpected error |
| `503` | The prediction model is not currently available |

### 10.6 Database

The existing `analysis` table gained two columns
(`risk_factors` JSONB, `analysis_status`), and `recommendation` was
widened from a 500-character string to JSONB (a proper list of
recommendation strings, since a single truncated string couldn't hold
several actionable recommendations).

### 10.7 Configuration

Every weight, threshold, deprecated-algorithm list, and recommendation
string lives in `ml/risk_config.json` and `ml/recommendation_rules.json`
— adding a new algorithm's strength score, a new binary-security rule,
or a new recommendation is a JSON edit, never a `risk.py`/`recommend.py`
code change.

---

## 11. Phase 7: Explainable RAG Intelligence Engine (`rag/`)

This module explains, in evidence-backed natural language, the
conclusions the ML prediction (section 9), risk assessment, and
recommendation engine (section 10) already reached. **It never makes or
changes a security decision** — the algorithm, family, confidence,
risk score, risk level, and recommendations it explains were all
already decided by earlier phases; this module only retrieves
supporting standards documents and explains *why*.

### 11.1 Knowledge base

`rag/knowledge_base/` holds 14 original, human-written reference
documents (Markdown, with a small front-matter header giving each a
`title`, `source_type`, and `identifier` for citation) summarizing
real, well-known public standards relevant to the algorithms this
project detects: NIST FIPS 197 (AES), NIST SP 800-57 and SP 800-131A
(key management and algorithm deprecation), NIST FIPS 180-4/202 (SHA-2/
SHA-3), RFC 8439 (ChaCha20-Poly1305), RFC 8017 (RSA), NIST SP 800-186
(ECC curves), MITRE CWE-327 (broken/risky algorithms), CWE-798/CWE-215
(hardcoded credentials, debug information exposure), MITRE ATT&CK
T1600 (Weaken Encryption), the OWASP IoT Top 10, CISA cryptographic
modernization guidance, and the Sweet32 academic paper on 64-bit block
cipher birthday attacks (relevant to 3DES/Blowfish). Each document is
original content summarizing well-known public facts about its
standard, not reproduced text.

### 11.2 Embeddings

The specified embedding model is `BAAI/bge-small-en-v1.5` via
`sentence-transformers` (`rag/embeddings.py`). **This model requires
downloading weights from the Hugging Face Hub on first use.** If that
download isn't possible (no network access to the Hub in a given
deployment — true of the sandbox this was built and tested in), the
module automatically falls back to a local, dependency-light TF-IDF
embedding function (scikit-learn) that implements the same ChromaDB
`EmbeddingFunction` interface, so ingestion and retrieval remain fully
functional either way. The load attempt runs in a background thread
with a hard wall-clock timeout (`_try_load_sentence_transformer`),
since the underlying HTTP client can otherwise hang indefinitely
against a network-blocked host rather than failing fast. The active
backend is always logged and reported (`EmbeddingBackend.name`), never
silently substituted. The TF-IDF fallback's fitted vocabulary is
persisted to disk alongside the ChromaDB store, since ingestion and
retrieval normally run in separate processes.

**Verified in this environment:** the fallback path was exercised for
real — 14 documents were chunked into 30 pieces (`langchain_text_splitters.RecursiveCharacterTextSplitter`,
800-character chunks, 100-character overlap) and embedded/stored in a
persistent ChromaDB collection, and retrieval against that store
correctly surfaced RFC 8439 for a ChaCha20 recommendation query and
CWE-215 for a debug-symbols query.

### 11.3 Retrieval

`rag/retriever.py` builds a natural-language query from the pipeline's
structured context (`build_retrieval_query`: algorithm, family,
triggered risk factor names, recommendation text) and retrieves the
top-K most similar knowledge-base chunks from ChromaDB.
`settings.RAG_TOP_K` (default 4) is fully configurable, never
hardcoded. An empty result set (e.g. a query matching nothing) is
handled gracefully — logged and returned as `[]`, not raised as an error.

### 11.4 Prompt engineering

`rag/prompt.py` builds a single structured prompt (`build_explanation_prompt`)
containing firmware metadata, a feature-vector summary, the detected
algorithm/family/confidence, the risk score/level and every triggered
risk factor, the recommendations, and the retrieved reference context
— each retrieved chunk labeled with its citable identifier — followed
by an explicit request for the five required explanation sections. The
system instruction explicitly forbids citing any source not present in
the retrieved context and forbids inventing facts not supported by it.

### 11.5 Local LLM (Ollama) and the template-based fallback

`rag/explain.py`'s `OllamaClient` is a minimal HTTP client for a
**local** Ollama server (`settings.OLLAMA_BASE_URL`, default
`http://localhost:11434`; model `llama3.1:8b-instruct-q4_0` by
default) — no paid or hosted LLM API is used anywhere in this project.

**Ollama is not installed in the environment this was built in** (no
GPU, and the quantized Llama 3.1 8B model weights are several GB —
infeasible to download here). Rather than fabricate what an LLM
response would look like, `explain_firmware()` checks
`OllamaClient.is_available()` first; when Ollama isn't reachable, it
calls `generate_template_explanation()` instead — a **deterministic**
explanation built directly from the same structured data and retrieved
citations used to build the LLM prompt, formatted into the same five
sections. This trivially satisfies "no hallucination" (nothing is
invented; every sentence is templated from already-known facts), and
every `ExplanationResult.generated_by` field honestly records which
path produced it (`"ollama:<model>"` or `"template_fallback"`) rather
than presenting a template as if it were an LLM response. In a
deployment with Ollama installed and the model pulled
(`ollama pull llama3.1:8b-instruct-q4_0`), the exact same code path
calls the real local LLM with no configuration change needed.

### 11.6 Citations

`rag/citations.py` extracts a deduplicated citation list from the
chunks actually retrieved for a given explanation — never a generic or
fabricated reference. Supported source types: NIST, MITRE, OWASP,
CISA, RFC, CVE, Academic Paper, Vendor Documentation. Citations prefer
each document's specific identifier (e.g. `"FIPS 197"`, `"RFC 8439"`)
over its full title where available, matching the concise reference
style in the specification's example response.

### 11.7 API endpoint

`POST /explain/{firmware_id}` runs the full pipeline: firmware lookup
→ ML prediction (reusing `ml.predict`) → risk assessment
(`ml.risk`) → recommendations (`ml.recommend`) → RAG explanation
(`rag.explain`) → store in `analysis` **and** `reports` → return. Like
`/predict` and `/risk`, it expects `feature_vector.json` file(s) to
already exist for the firmware (Phase 4).

**Response** (verified end to end against a real compiled RC4 binary):
```json
{
  "firmware_id": 104,
  "binary_name": "rc4_explain.bin",
  "algorithm_family": "Stream Cipher",
  "algorithm": "RC4",
  "confidence": 99.41,
  "risk_score": 80.5,
  "risk_level": "Critical",
  "summary": "The firmware binary was classified as implementing RC4 ...",
  "sections": {
    "Algorithm Detection": "...",
    "Confidence Explanation": "...",
    "Risk Assessment Explanation": "...",
    "Recommendation Justification": "...",
    "Referenced Standards": "This explanation is grounded in: CWE-798, CWE-215, SP 800-57 Part 1 Rev. 5, OWASP IoT Top 10 (2018)."
  },
  "recommendations": ["Replace RC4 with ChaCha20 or AES-GCM.", "..."],
  "references": ["CWE-798, CWE-215", "SP 800-57 Part 1 Rev. 5", "OWASP IoT Top 10 (2018)"],
  "generated_by": "template_fallback",
  "generation_time_ms": 5845.35
}
```

For a firmware with multiple analyzed executables, the response wraps
per-binary explanations in `{"firmware_id": ..., "explanations": [...]}`,
matching the pattern established by `/predict` and `/risk`.

| Status | Meaning |
|--------|----------|
| `200` | Explanation(s) returned successfully |
| `404` | Firmware not found, or no analysis results exist for it yet |
| `422` | Every binary's explanation failed |
| `500` | Risk/recommendation configuration invalid, or an unexpected error |
| `503` | The prediction model is not currently available |

### 11.8 Database

The existing `reports` table's `rag_explanation` column was widened
from a plain string to JSONB, storing the full explanation (summary,
all five sections, references), the retrieved documents (content +
metadata, for audit), which generation path produced it, and the
generation time — satisfying the spec's "Store: RAG Explanation,
Retrieved Documents, Citations, Generation Time" without adding new
columns. `reports.analysis_id` links each explanation back to the
`analysis` row created by the same request.

### 11.9 A known environment limitation, stated plainly

Both the specified embedding model and the specified local LLM require
resources (Hugging Face Hub network access; several GB of disk plus a
capable CPU/GPU for Llama 3.1 8B) that this development sandbox does
not have. Every architectural piece — ChromaDB ingestion and
retrieval, LangChain-based chunking, structured prompt construction,
the Ollama HTTP client, citation extraction — is real, tested, working
code, verified end to end through the fallback paths described above.
Deploying with real network access and a provisioned Ollama instance
requires no code changes, only environment setup.

---

## 12. Installation

### 12.1 Clone the repository

```bash
git clone <your-repository-url>
cd CryptoSage/backend
```

### 12.2 Create and activate a virtual environment

```bash
python3.12 -m venv venv

# On Linux / macOS
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

### 12.3 Install dependencies

```bash
pip install -r requirements.txt
```

Phase 4 additionally requires **Binwalk** and **libmagic** as system
packages (not installable via pip alone):

```bash
sudo apt-get install -y binwalk libmagic1
```

### 12.4 Configure environment variables

Copy the example environment file and fill in your own values:

```bash
cp .env.example .env
```

`.env` contents:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cryptosage
SECRET_KEY=change-me-in-production
DEBUG=True
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=500
ALLOWED_FIRMWARE_EXTENSIONS=bin,img,elf
ANALYSIS_OUTPUT_DIR=analysis_output
RAG_TOP_K=4
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_0
```

### 12.5 Ingest the RAG knowledge base (Phase 7, one-time)

Before `/explain/{firmware_id}` can retrieve supporting documents, the
knowledge base must be chunked, embedded, and stored in ChromaDB once:

```bash
python -c "from rag.ingest import ingest_knowledge_base; print(ingest_knowledge_base())"
```

Re-run this after editing anything under `rag/knowledge_base/` — it
clears and rebuilds the collection each time, so it's always safe to
re-run. To use the real `BAAI/bge-small-en-v1.5` embeddings instead of
the local TF-IDF fallback, ensure this environment has network access
to the Hugging Face Hub before running ingestion (see section 11.9).
For real local LLM generation instead of the deterministic template
fallback, install [Ollama](https://ollama.com) and pull the model:

```bash
ollama pull llama3.1:8b-instruct-q4_0
ollama serve
```

---

## 13. PostgreSQL Setup

Make sure PostgreSQL is installed and running locally, then create the
database and (optionally) a dedicated user:

```bash
# Log in to the PostgreSQL shell
sudo -u postgres psql

# Inside the psql shell:
CREATE DATABASE cryptosage;
CREATE USER cryptosage_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE cryptosage TO cryptosage_user;
\q
```

Update `DATABASE_URL` in your `.env` file to match the credentials you
used above.

---

## 14. Alembic Migrations

Alembic is already configured to read the database URL from `config.py`
(which in turn reads from your `.env` file), and to track the models
defined in `models.py`. Five migrations currently exist:

1. Initial migration — creates `firmware`, `analysis`, and `reports`.
2. Add `uploaded_features` — adds the feature-vector/similarity table.
3. Add `storage_path` to `firmware` — records where each uploaded file
   lives under `uploads/` (Phase 3).
4. Add `risk_factors`/`analysis_status` to `analysis`, widen
   `recommendation` to JSONB (Phase 6/7).
5. Widen `reports.rag_explanation` to JSONB — stores the full
   explanation, retrieved documents, citations, and generation time
   (Phase 7).

Run all migrations up to the latest:

```bash
alembic upgrade head
```

To generate a new migration after changing `models.py` in the future:

```bash
alembic revision --autogenerate -m "Description of the change"
alembic upgrade head
```

To roll back the most recent migration:

```bash
alembic downgrade -1
```

---

## 15. Running the Server

From inside the `backend/` directory, with the virtual environment
activated:

```bash
uvicorn app:app --reload
```

The server will start at `http://127.0.0.1:8000`. Startup can take
20-30 seconds the first time in a given environment — the ML
(scikit-learn/XGBoost) and RAG (sentence-transformers/ChromaDB)
dependency chains are imported eagerly at startup rather than lazily
per-request.

### Available endpoints

- `GET /` — basic project status
- `GET /health` — API and database health check
- `POST /firmware/upload` — upload a firmware file (Phase 3)
- `GET /firmware` — list all uploaded firmware records (Phase 3)
- `GET /firmware/{firmware_id}` — get one firmware record (Phase 3)
- `POST /predict/{firmware_id}` — run ML inference on an already-analyzed firmware (Phase 6)
- `POST /risk/{firmware_id}` — run prediction + risk assessment + recommendations for a firmware (Phase 6/7)
- `POST /explain/{firmware_id}` — run prediction + risk + evidence-backed RAG explanation for a firmware (Phase 7)

### Example: uploading firmware with curl

```bash
curl -X POST http://127.0.0.1:8000/firmware/upload \
  -F "file=@/path/to/router.bin"
```

```bash
# List all uploaded firmware
curl http://127.0.0.1:8000/firmware

# Get one firmware record
curl http://127.0.0.1:8000/firmware/1
```

### Example: uploading firmware with Postman

1. Create a new request: `POST http://127.0.0.1:8000/firmware/upload`.
2. Under the **Body** tab, select **form-data**.
3. Add a key named `file`, set its type to **File**, and choose a
   `.bin`, `.img`, or `.elf` file from disk.
4. Send the request — the response body will contain the new
   `firmware_id`, or a duplicate notice if that exact file was already
   uploaded.

### Expected upload directory structure

After uploading `router.bin` (assigned ID `1`) and `firmware.img`
(assigned ID `2`):

```
backend/uploads/
├── 1/
│   └── router.bin
└── 2/
    └── firmware.img
```

### Example: running a prediction with curl

Assumes firmware `1` has already been uploaded *and* already analyzed
by the Firmware Analysis Engine (i.e. `analysis_output/1/` already
contains at least one `*_feature_vector.json`):

```bash
curl -X POST http://127.0.0.1:8000/predict/1
```

Expected JSON response (single executable):
```json
{
  "firmware_id": 1,
  "binary_name": "router.bin",
  "algorithm_family": "Symmetric Encryption",
  "algorithm": "AES",
  "confidence": 97.15,
  "model": "ExtraTreesClassifier",
  "model_version": "2.0",
  "prediction_time_ms": 12.4,
  "feature_count_used": 28
}
```

### Example: running a prediction with Postman

1. Create a new request: `POST http://127.0.0.1:8000/predict/1` (no
   body needed).
2. Send the request — the response contains either the single-binary
   shape or the `predictions` list shape from section 9.7, depending on
   how many executables were found inside the firmware.

---

## 16. API Documentation

FastAPI automatically generates interactive API documentation,
including the `/firmware/upload`, `/firmware`, `/firmware/{firmware_id}`
(Phase 3) and `/predict/{firmware_id}` (Phase 5B) endpoints:

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 17. Project Status

This README documents **Phase 1 (Project Setup)**, **Phase 2A (Offline
Dataset Builder)**, **Phase 2B (Algorithm-Level Dataset Upgrade)**,
**Phase 3 (Firmware Input Module)**, **Phase 4 (Firmware Analysis
Engine)**, **Phase 6 (ML Benchmarking Framework + Hierarchical
Inference)** (which supersedes the earlier Phase 5A/5B implementation),
**Phase 6/7 (Risk Assessment & Recommendation Engine)**, and **Phase 7
(Explainable RAG Intelligence Engine)**.
The FastAPI app, database layer, and `GET /` / `GET /health` endpoints
are functional; the database has a fourth table (`uploaded_features`)
ready to store extracted feature vectors and similarity scores;
`dataset/` fully implements automated cloning/updating, both
whole-library builds and per-algorithm standalone object compilation
across optimization levels/build types/compilers, ELF and object-file
discovery, feature extraction, algorithm-level and whole-binary label
inference, and preprocessing into `dataset.csv`, `train.csv`, and
`test.csv` — a real, reproducible run currently produces **7,095
samples across 24 algorithm labels**; `input/` fully implements
firmware intake — validated upload, streamed SHA-256 hashing,
duplicate detection, ID-scoped storage under `uploads/`, and the
`/firmware/upload`, `/firmware`, `/firmware/{firmware_id}` endpoints;
`analysis/` fully implements the shared Firmware Analysis Engine —
Binwalk extraction, LIEF-based ELF parsing and binary discovery,
Capstone disassembly, opcode n-gram/CFG-approximation/section-ratio/
RSA-ECC feature engineering, and the single canonical
`extract_features()` implementation that both the Dataset Builder and
runtime firmware analysis import identically; `ml/train.py`
cross-validates and hyperparameter-tunes four models (RandomForest,
ExtraTrees, HistGradientBoosting, XGBoost) under Stratified 5-Fold CV,
automatically selects the best one (`ExtraTreesClassifier`, in the
current run), trains it as a hierarchical family→algorithm classifier
with metadata leakage removed from its features, and evaluates it
exactly once on the held-out test set — **95.24% algorithm accuracy,
98.25% family accuracy**, a large genuine improvement over the earlier
flat classifier's ~78%; and `ml/predict.py` + `POST /predict/{firmware_id}`
load that hierarchical model once per process and return both the
predicted family and algorithm with a confidence score, timing, and
storage in the `analysis` table — verified to have resolved Phase 5B's
documented real-world confidence problem (a real AES sample now
predicts AES at 97%+ confidence, not "Argon2" at 30%); and `ml/risk.py`
+ `ml/recommend.py` + `POST /risk/{firmware_id}` compute a deterministic,
non-ML, weighted multi-factor security risk score (algorithm strength,
deprecation, ten binary-security sub-factors, five firmware-metadata
sub-factors) with full evidence, map it to a Safe→Critical risk level,
and generate rule-based, evidence-driven recommendations — verified end
to end against a real compiled RC4 binary (risk score 80.5, "Critical",
four specific recommendations, all persisted to the `analysis` table);
and `rag/` fully implements the Explainable RAG Intelligence Engine —
a 14-document original knowledge base (NIST/MITRE/OWASP/CISA/RFC/
academic sources) chunked with LangChain and embedded/stored in
ChromaDB (with an automatic, verified TF-IDF fallback when the
specified BAAI/bge-small-en-v1.5 model can't be downloaded), Top-K
retrieval driven by the pipeline's own risk factors and
recommendations, structured prompt construction, a local-only Ollama
LLM client with a deterministic non-hallucinating template fallback
when no local LLM is available, and citation extraction — via
`POST /explain/{firmware_id}`, verified end to end against the same
real RC4 binary (correctly citing CWE-798/215, NIST SP 800-57, and the
OWASP IoT Top 10, stored in both the `analysis` and `reports` tables).

PDF reporting is not implemented yet and will be documented separately
as it lands.
