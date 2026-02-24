from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Hello from CI Demo",
        "commit": os.getenv("COMMIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }
