FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app /app

ARG COMMIT_SHA
ARG ENVIRONMENT

ENV COMMIT_SHA=$COMMIT_SHA
ENV ENVIRONMENT=$ENVIRONMENT

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
