FROM python:3.12-slim

WORKDIR /app

# Install contracts package first (shared dependency)
COPY packages/contracts /tmp/contracts
RUN pip install --no-cache-dir /tmp/contracts && rm -rf /tmp/contracts

# Install service dependencies
COPY backend/services/sql_generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY backend/services/sql_generator/app ./app

EXPOSE 8006

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
