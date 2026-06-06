FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libopenblas.so

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data skills && \
    useradd --create-home --shell /bin/bash msgstack && \
    chown -R msgstack:msgstack /app

USER msgstack

EXPOSE 8001

CMD ["python", "run_server.py"]
