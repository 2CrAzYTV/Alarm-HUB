FROM mcr.microsoft.com/playwright/python:v1.54.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN python -m compileall -q app \
    && python -c "import app.entry; print('Alarm Hub import smoke test passed')"

EXPOSE 8080
CMD ["uvicorn", "app.entry:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
