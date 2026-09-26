FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# System packages required by firmware analysis / Binwalk
RUN apt-get update && apt-get install -y \
    binwalk \
    file \
    xz-utils \
    gzip \
    bzip2 \
    unzip \
    p7zip-full \
    cpio \
    tar \
    squashfs-tools \
    zstd \
    lz4 \
    libmagic1 \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Application
COPY . .

ENV PORT=10000

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]