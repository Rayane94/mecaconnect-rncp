FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY frontend/public ./frontend/public
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["sh","-c","python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
