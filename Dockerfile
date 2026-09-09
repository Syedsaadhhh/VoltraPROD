# ==============================================================================
# Stage 1: Build the React Frontend
# ==============================================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Web Application & MCP Runtime
# ==============================================================================
FROM python:3.12-slim AS runner
WORKDIR /app

# Install system utilities if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy backend dependency definitions and lockfile
COPY backend/requirements.lock ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.lock

# Copy application source code
COPY backend/app ./backend/app
COPY sql ./sql

# Copy built frontend assets to the location expected by FastAPI
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app/backend
ENV PORT=8000
ENV ENVIRONMENT=production

EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT}"]
