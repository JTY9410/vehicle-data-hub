FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim-bookworm
RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN mkdir -p /app/uploads /app/instance && chown -R appuser:appuser /app
USER appuser
ENV FLASK_APP=app:app
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
