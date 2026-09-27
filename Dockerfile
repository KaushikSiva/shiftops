FROM node:22-bookworm-slim AS web
WORKDIR /build/web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglfw3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home shiftops
COPY backend/ backend/
COPY --from=web /build/web/dist web/dist/
COPY web/public/assets/g1/ web/public/assets/g1/
RUN mkdir -p /app/data && chown -R shiftops:shiftops /app/data
USER shiftops
ENV SHIFTOPS_DB=/app/data/shiftops.sqlite3
EXPOSE 8197
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8197/api/health',timeout=4)"
CMD ["uvicorn","backend.app:app","--host","0.0.0.0","--port","8197","--proxy-headers","--forwarded-allow-ips","*"]
