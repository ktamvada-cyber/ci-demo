from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Hello from Feature 1 - Testing Deployment!",
        "commit": os.getenv("COMMIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }
