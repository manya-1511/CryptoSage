# 🛡️ CryptoSage

### AI-Powered Firmware Cryptographic Security Analysis Platform

CryptoSage is an AI-powered firmware security analysis platform designed to inspect firmware images, detect cryptographic algorithms through static binary analysis and machine learning, assess security risk, and generate evidence-backed recommendations and explanations.

The platform combines a **FastAPI backend**, **machine-learning pipeline**, **deterministic risk engine**, **RAG-based explanation engine**, and a **Next.js frontend** into a single end-to-end security analysis workflow.

---

## ✨ Key Features

* 🔐 Firmware upload and validation for `.bin`, `.img`, and `.elf`
* 🔍 Static binary analysis using **Binwalk, LIEF, and Capstone**
* 🧠 Hierarchical ML classification:

  * Cryptographic family detection
  * Specific algorithm detection
* 📊 Research-grade ML benchmarking with multiple classifiers
* 🎯 **95.24% algorithm-level accuracy**
* 🛡️ Deterministic weighted security risk scoring
* ⚠️ Risk levels: **Safe, Low, Medium, High, Critical**
* 💡 Rule-based security recommendations
* 🔎 SHAP-based ML explainability
* 📚 RAG-based evidence-backed explanations
* 🤖 Local Ollama LLM integration with deterministic fallback
* 🗂️ Firmware history and detailed analysis pages
* 💬 Report Assistant grounded in the firmware's analysis report
* 🔑 Clerk authentication and protected frontend routes
* 📈 Modern dark-themed dashboard with responsive UI
* 🐳 Docker support

---

# 🏗️ System Architecture

CryptoSage consists of four major layers:

```text
                    ┌─────────────────────────┐
                    │       Next.js UI        │
                    │  Dashboard / Analysis   │
                    │ History / Reports / Auth│
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      FastAPI Backend     │
                    │       REST API Layer     │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
       Firmware Input      Static Analysis       PostgreSQL
       Upload/Validation   Binwalk/LIEF/Capstone  Persistence
              │                  │
              └────────────┬─────┘
                           ▼
                  ┌───────────────────┐
                  │ ML Classification │
                  │ Family → Algorithm│
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │  Risk Assessment  │
                  │ + Recommendations │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │ RAG Explanation   │
                  │ ChromaDB + LLM    │
                  └───────────────────┘
```

---

# 🧰 Tech Stack

## Backend

| Layer             | Technology             |
| ----------------- | ---------------------- |
| Language          | Python 3.12            |
| API               | FastAPI                |
| Database          | PostgreSQL             |
| ORM               | SQLAlchemy 2.0         |
| Migrations        | Alembic                |
| Validation        | Pydantic               |
| Server            | Uvicorn                |
| Binary Extraction | Binwalk                |
| Binary Parsing    | LIEF                   |
| Disassembly       | Capstone               |
| ML                | Scikit-learn, XGBoost  |
| Explainability    | SHAP                   |
| RAG               | LangChain              |
| Vector Database   | ChromaDB               |
| Embeddings        | BAAI/bge-small-en-v1.5 |
| Local LLM         | Ollama                 |

## Frontend

| Layer          | Technology    |
| -------------- | ------------- |
| Framework      | Next.js 14    |
| Language       | TypeScript    |
| Styling        | Tailwind CSS  |
| Authentication | Clerk         |
| Animation      | Framer Motion |
| Icons          | lucide-react  |
| HTTP Client    | Axios         |
| Architecture   | App Router    |

---

# 🧪 Dataset

CryptoSage contains a reproducible offline dataset-generation pipeline built from open-source cryptographic libraries:

* OpenSSL
* mbedTLS
* wolfSSL
* LibTomCrypt
* libsodium

The algorithm-level pipeline compiles individual cryptographic source files across:

* GCC / Clang
* O0 / O1 / O2 / O3
* Debug / Release configurations

The current dataset contains:

**7,095 real compiled samples across 24 algorithm labels.**

---

# 🧠 Machine Learning Pipeline

CryptoSage uses a hierarchical classification strategy:

```text
                    Firmware Binary
                          │
                          ▼
                  Feature Extraction
                          │
                          ▼
                ┌───────────────────┐
                │ Stage 1           │
                │ Crypto Family     │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ Stage 2           │
                │ Specific Algorithm│
                └───────────────────┘
```

Four models are benchmarked:

* Random Forest
* Extra Trees
* XGBoost
* HistGradientBoosting

The benchmark uses **Stratified 5-Fold Cross-Validation** and automatically selects the best model based primarily on macro F1.

The current benchmark selected **ExtraTreesClassifier**.

---

# 📊 ML Results

Evaluation was performed on a held-out test set containing:

* **5,666 training samples**
* **1,429 test samples**
* **24 algorithm classes**
* **6 cryptographic families**

| Metric                      |     Result |
| --------------------------- | ---------: |
| Algorithm Accuracy          | **95.24%** |
| Algorithm Macro F1          | **93.37%** |
| Algorithm Balanced Accuracy | **93.84%** |
| Family Accuracy             | **98.25%** |
| Family Macro F1             | **98.08%** |
| Cross-Validation Macro F1   | **≈96.9%** |

The reported test results come from a final evaluation on the held-out test set after model selection.

---

# 🔍 Explainable AI

CryptoSage uses SHAP to explain model predictions.

The system provides:

* Global feature importance
* SHAP summary
* Feature contribution analysis
* Per-prediction explanations

Current high-ranking binary-content features include:

```text
chacha_symbol
aes_symbol
ecc_symbol
rsa_symbol
entropy_normalized
```

The explainability pipeline is designed to use binary-content signals rather than dataset provenance features.

---

# 🛡️ Risk Assessment

Risk assessment is **deterministic and non-ML**.

```text
Risk Score =
Σ(category weight × normalized factor)
```

The score is bounded between `0` and `100`.

### Risk Levels

|  Score | Level    |
| -----: | -------- |
|   0–20 | Safe     |
|  21–40 | Low      |
|  41–60 | Medium   |
|  61–80 | High     |
| 81–100 | Critical |

The risk engine uses configured weights and rules rather than an additional ML or LLM model.

---

# 📚 RAG Explanation Engine

CryptoSage provides evidence-backed explanations using Retrieval-Augmented Generation.

```text
Analysis Result
      ↓
Retrieve relevant security knowledge
      ↓
ChromaDB
      ↓
Relevant documents
      ↓
Ollama local LLM
      ↓
Grounded explanation
      ↓
Recommendations + references
```

The knowledge base is designed around security standards and references such as:

* NIST
* MITRE CWE / ATT&CK
* OWASP IoT
* CISA advisories
* Relevant RFCs

When the local LLM is unavailable, the backend can fall back to a deterministic template-based explanation.

---

# 🚀 Getting Started

## 1. Clone the repository

```bash
git clone https://github.com/manya-1511/CryptoSage.git
cd CryptoSage
```

---

# ⚙️ Backend Setup

```bash
cd backend
```

Create and activate a Python environment:

```bash
python3.12 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp .env.example .env
```

Configure your PostgreSQL connection and other required backend settings in `.env`.

Run database migrations:

```bash
alembic upgrade head
```

Start FastAPI:

```bash
uvicorn app:app --reload
```

Backend:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

---

# 🎨 Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create the environment file:

```bash
cp .env.example .env.local
```

Configure:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_key
CLERK_SECRET_KEY=sk_test_your_key

NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

API_URL=http://localhost:8000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

Frontend:

```text
http://localhost:3000
```

---

# 🐳 Docker

The project includes Docker support for the frontend and backend infrastructure.

Frontend build:

```bash
cd frontend

docker build \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_key \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  -t cryptosage-frontend .
```

Run:

```bash
docker run -p 3000:3000 \
  -e CLERK_SECRET_KEY=your_secret_key \
  -e API_URL=http://localhost:8000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  cryptosage-frontend
```

---

# 🧪 Dataset Generation

To generate the dataset:

```bash
cd backend/dataset
python builder.py
```

Then preprocess:

```bash
python preprocess.py
```

The pipeline generates training and test data from compiled cryptographic implementations.

---

# 🤖 Model Training

```bash
cd backend/ml
python train.py
```

### Future Work

* [ ] PDF security report generation
* [ ] Expanded firmware architecture support
* [ ] Additional cryptographic algorithms
* [ ] ARM / ARM64 / MIPS cross-architecture dataset expansion
* [ ] More advanced binary-level security analysis
* [ ] Production deployment and monitoring

---

# 🎓 Research Highlights

CryptoSage focuses on the combination of:

```text
Static Binary Analysis
        +
Machine Learning
        +
Explainable AI
        +
Deterministic Risk Assessment
        +
Retrieval-Augmented Generation
```

A key design principle is keeping **training, runtime analysis, risk scoring, and explanations independently traceable**, rather than relying on an opaque end-to-end prediction system.

The current research dataset contains **7,095 real compiled samples across 24 cryptographic algorithms**, while the hierarchical classifier achieved **95.24% held-out algorithm accuracy** and **98.25% family-level accuracy**.

---

# 📜 License

This project is developed for research and educational purposes.

---
