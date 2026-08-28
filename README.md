# CryptoSage

### AI-Powered Firmware Cryptographic Security Analysis Platform

CryptoSage analyzes firmware binaries to detect cryptographic algorithms, assess security risks, generate recommendations, and provide evidence-backed explanations using RAG.

## Features

* Firmware upload and validation (`.bin`, `.img`, `.elf`)
* Firmware extraction using **Binwalk**
* ELF analysis using **LIEF**
* Binary disassembly using **Capstone**
* Static feature extraction
* Cryptographic algorithm detection
* ML-based algorithm classification
* Hierarchical **Family → Algorithm** prediction
* **SHAP** explainability
* Security risk scoring
* Automated security recommendations
* RAG-based security explanations
* REST API using **FastAPI**
* PostgreSQL database

## ML Performance

The model was trained on **7,095 real compiled samples** covering **24 cryptographic algorithms** across **6 families**.

| Metric             |      Score |
| ------------------ | ---------: |
| Algorithm Accuracy | **95.24%** |
| Algorithm F1       | **93.37%** |
| Family Accuracy    | **98.25%** |
| Family F1          | **98.08%** |

**Best Model:** `ExtraTreesClassifier`

## Architecture

```text
Firmware
   ↓
Upload & Validation
   ↓
Binwalk Extraction
   ↓
Executable Discovery
   ↓
LIEF + Capstone Analysis
   ↓
Feature Extraction
   ↓
ML Classification
   ↓
Risk Assessment
   ↓
Security Recommendations
   ↓
RAG-Based Explanation
```

## Tech Stack

| Layer            | Technologies                             |
| ---------------- | ---------------------------------------- |
| Language         | Python 3.12                              |
| Backend          | FastAPI                                  |
| Database         | PostgreSQL                               |
| ORM              | SQLAlchemy                               |
| Migrations       | Alembic                                  |
| Binary Analysis  | Binwalk, LIEF, Capstone                  |
| Machine Learning | Scikit-learn, XGBoost                    |
| Explainability   | SHAP                                     |
| RAG              | LangChain, ChromaDB                      |
| Embeddings       | Sentence Transformers                    |
| LLM              | Ollama                                   |
| Frontend         | Next.js, React, TypeScript, Tailwind CSS |

## Project Structure

```text
CryptoSage/
│
├── backend/
│   ├── api/
│   ├── input/
│   ├── analysis/
│   ├── dataset/
│   ├── ml/
│   ├── rag/
│   ├── reports/
│   ├── app.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   └── schemas.py
│
├── frontend/
│
└── README.md
```

# Installation

## 1. Clone Repository

```bash
git clone https://github.com/manya-1511/CryptoSage.git
cd CryptoSage
```

## 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

## 4. Configure PostgreSQL

Create a PostgreSQL database named:

```text
cryptosage
```

Create a `.env` file inside `backend/`:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/cryptosage

UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=500

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_0
```

Update the database credentials according to your PostgreSQL setup.

# Run the Backend

```bash
cd backend
uvicorn app:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

# Build Dataset

The dataset builder uses cryptographic libraries such as OpenSSL, mbedTLS, wolfSSL, LibTomCrypt, and libsodium.

```bash
cd backend/dataset
python builder.py
```

Preprocess the dataset:

```bash
python preprocess.py
```

# Train ML Model

```bash
cd backend/ml
python train.py
```

Trained models are stored in:

```text
backend/ml/saved_models/
```

# API Endpoints

| Method | Endpoint                 | Description                     |
| ------ | ------------------------ | ------------------------------- |
| `POST` | `/firmware/upload`       | Upload firmware                 |
| `GET`  | `/firmware`              | List firmware                   |
| `GET`  | `/firmware/{id}`         | Get firmware details            |
| `POST` | `/predict/{firmware_id}` | Predict cryptographic algorithm |
| `POST` | `/risk/{firmware_id}`    | Calculate security risk         |
| `POST` | `/explain/{firmware_id}` | Generate RAG explanation        |

# Analysis Pipeline

```text
Upload Firmware
      ↓
Validate & Store
      ↓
Binwalk Extraction
      ↓
Executable Discovery
      ↓
ELF Parsing
      ↓
Disassembly
      ↓
Feature Extraction
      ↓
ML Prediction
      ↓
Risk Assessment
      ↓
Recommendations
      ↓
RAG Explanation
```

# RAG Intelligence

CryptoSage uses a security knowledge base containing references from:

* NIST
* MITRE
* OWASP
* CISA
* RFCs
* Academic research

The RAG engine retrieves relevant security knowledge and explains the results produced by the ML and risk engines.

# Project Status

### Implemented

* Firmware upload and validation
* Firmware extraction
* Static binary analysis
* Feature extraction
* Dataset generation
* ML benchmarking
* Hierarchical classification
* SHAP explainability
* Risk assessment
* Security recommendations
* RAG-based explanations

### Future Work

* Frontend integration
* PDF security reports
* Production deployment

## License

This project is developed for **research and educational purposes**.
