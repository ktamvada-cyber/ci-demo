from fastapi import FastAPI
import os
from datetime import datetime

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Hello from Feature 1 - v2.6",
        "version": "2.6",
        "commit": os.getenv("COMMIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }

@app.get("/deployment-info")
def deployment_info():
    """
    Returns comprehensive deployment information about the running instance.
    This endpoint shows what version is currently deployed and running.
    """
    # Mask API_KEY for security (show only first 8 chars)
    #new commit thats it
    api_key = os.getenv("API_KEY", "not-set")
    api_key_masked = api_key[:8] + "***" if len(api_key) > 8 else api_key

    return {
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "commit_sha": os.getenv("COMMIT_SHA", "unknown"),
        "build_timestamp": os.getenv("BUILD_TIMESTAMP", "unknown"),
        "deployment_id": os.getenv("DEPLOYMENT_ID", "unknown"),
        "container_name": os.getenv("CONTAINER_NAME", "unknown"),
        "port": os.getenv("PORT", "8000"),
        "image_digest": os.getenv("IMAGE_DIGEST", "unknown"),
        "api_key": api_key_masked,
        "db_host": os.getenv("DB_HOST", "not-set"),
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

@app.get("/api/version")
def version_info():
    """
    Returns version information and deployment metadata.
    Useful for verifying which version is deployed via GitHub Deployments.
    """
    return {
        "version": "2.6",
        "commit_sha": os.getenv("COMMIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "deployment_id": os.getenv("DEPLOYMENT_ID", "unknown"),
        "build_timestamp": os.getenv("BUILD_TIMESTAMP", "unknown"),
        "feature": "GitHub Deployments API Integration Test"
    }
