FROM python:3.12-slim

WORKDIR /app

COPY packages/contracts /tmp/contracts
COPY packages/observability /tmp/observability
RUN pip install --no-cache-dir /tmp/contracts && rm -rf /tmp/contracts
RUN pip install --no-cache-dir /tmp/observability && rm -rf /tmp/observability

COPY backend/services/identity/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/services/identity/app ./app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

