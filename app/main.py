from fastapi import FastAPI
import os
from datetime import datetime

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Hello from Feature 1 - Testing Enhanced Metadata!",
        "version": "2.0",
        "commit": os.getenv("COMMIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }

@app.get("/deployment-info")
def deployment_info():
    """
    Returns comprehensive deployment information about the running instance.
    This endpoint shows what version is currently deployed and running.
    """
    return {
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "commit_sha": os.getenv("COMMIT_SHA", "unknown"),
        "build_timestamp": os.getenv("BUILD_TIMESTAMP", "unknown"),
        "deployment_id": os.getenv("DEPLOYMENT_ID", "unknown"),
        "container_name": os.getenv("CONTAINER_NAME", "unknown"),
        "port": os.getenv("PORT", "8000"),
        "image_digest": os.getenv("IMAGE_DIGEST", "unknown"),
        "status": "running",
        "server_time": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/health")
def health_check():
    """
    Simple health check endpoint for deployment verification.
    """
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "commit": os.getenv("COMMIT_SHA", "unknown")
    }
