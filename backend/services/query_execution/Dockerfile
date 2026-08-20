FROM python:3.12-slim

WORKDIR /app

COPY packages/contracts /tmp/contracts
RUN pip install --no-cache-dir /tmp/contracts && rm -rf /tmp/contracts

COPY backend/services/query_execution/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/services/query_execution/app ./app

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
