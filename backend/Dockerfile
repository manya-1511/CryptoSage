FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    binwalk \
    libmagic1 \
    file \
    p7zip-full \
    squashfs-tools \
    mtd-utils \
    zlib1g-dev \
    liblzma-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/extractions

EXPOSE 8000