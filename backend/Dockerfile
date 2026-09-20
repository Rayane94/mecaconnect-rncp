FROM node:22-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/tsconfig.json ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend-build /src/frontend/public ./frontend/public
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["sh","-c","python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
