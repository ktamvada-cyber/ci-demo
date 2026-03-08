FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app /app

# Build-time arguments (baked into image)
ARG COMMIT_SHA
ARG BUILD_TIMESTAMP

# Set build-time values as default environment variables
# These can be overridden at runtime with docker run -e
ENV COMMIT_SHA=$COMMIT_SHA
ENV BUILD_TIMESTAMP=$BUILD_TIMESTAMP

# Runtime environment variables (set via docker run -e)
# ENVIRONMENT, DEPLOYMENT_ID, CONTAINER_NAME, PORT, IMAGE_DIGEST
# These are set when the container starts, not during build

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
