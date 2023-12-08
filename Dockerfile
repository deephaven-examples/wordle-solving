FROM ghcr.io/deephaven/server:0.12.0 AS ws-server
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
COPY app.d /app.d
COPY data /data
HEALTHCHECK --interval=3s --retries=3 --timeout=11s CMD /bin/grpc_health_probe -addr=localhost:8080 -connect-timeout=10s || exit 1

FROM ghcr.io/deephaven/web:latest AS ws-web
COPY data/notebooks /data/notebooks
RUN chown www-data:www-data /data/notebooks
