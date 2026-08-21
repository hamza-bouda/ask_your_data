FROM python:3.12-slim

WORKDIR /app

# Install contracts package first (shared dependency)
COPY packages/contracts /tmp/contracts
COPY packages/observability /tmp/observability
RUN pip install --no-cache-dir /tmp/contracts && rm -rf /tmp/contracts
RUN pip install --no-cache-dir /tmp/observability && rm -rf /tmp/observability

# Install service dependencies
COPY backend/services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY backend/services/gateway/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

