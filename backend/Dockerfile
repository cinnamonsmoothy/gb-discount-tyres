FROM python:3.11-slim
WORKDIR /app
COPY requirements-cloud-run.txt ./
RUN pip install --no-cache-dir -r requirements-cloud-run.txt
COPY cloud_run_app.py fitmentx_lookup.py ./
ENV PORT=8080
CMD ["sh", "-c", "uvicorn cloud_run_app:app --host 0.0.0.0 --port ${PORT}"]
