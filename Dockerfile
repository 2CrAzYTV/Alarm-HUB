FROM mcr.microsoft.com/playwright/python:v1.54.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/alarm-hub-entrypoint
RUN chmod +x /usr/local/bin/alarm-hub-entrypoint \
    && python -m compileall -q app \
    && python -c "import app.entry; print('Alarm Hub import smoke test passed')"

VOLUME ["/config"]
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/alarm-hub-entrypoint"]
