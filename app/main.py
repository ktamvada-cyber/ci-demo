from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Hello from Feature 1 - Testing Enhanced Metadata!",
        "version": "2.0",
        "commit": os.getenv("COMMIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }
