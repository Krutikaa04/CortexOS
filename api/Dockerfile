FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml ./
# Install dependencies first for layer caching; git is needed at runtime
# for repository ingestion, installed in the final stage.
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 cortex

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

USER cortex
EXPOSE 8000
CMD ["uvicorn", "cortex.main:app", "--host", "0.0.0.0", "--port", "8000"]
