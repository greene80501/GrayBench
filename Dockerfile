FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends graphviz libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
WORKDIR /work
USER 65534:65534
