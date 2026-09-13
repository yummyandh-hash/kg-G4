FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip

COPY torch-cache/torch-2.5.1+cpu-cp310-cp310-linux_x86_64.whl /tmp/

RUN pip install --no-cache-dir /tmp/torch-2.5.1+cpu-cp310-cp310-linux_x86_64.whl \
    && pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY orchestration ./orchestration
COPY retrieval ./retrieval
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]