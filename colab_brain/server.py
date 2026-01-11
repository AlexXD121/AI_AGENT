"""FastAPI server for Cloud Brain vision inference.

Exposes vision model via REST API with ngrok tunnel support for Colab.
"""

import os
import signal
import io
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from PIL import Image
from loguru import logger

from colab_brain.inference import VisionModelEngine

# Security Scheme
security = HTTPBearer()

# Load API Key from env (or use default for dev)
BRAIN_SECRET = os.environ.get("BRAIN_SECRET", "sovereign-secret-key")


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate Bearer token."""
    if credentials.credentials != BRAIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# Global engine
engine: Optional[VisionModelEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown."""
    global engine
    logger.info("Starting Cloud Brain server...")
    engine = VisionModelEngine()
    logger.success("Model loaded")
    yield
    logger.info("Shutting down...")
    engine = None


app = FastAPI(title="Sovereign-Doc Brain", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ready" if engine else "loading",
        "model": engine.model_name if engine else None
    }


@app.post("/analyze", dependencies=[Depends(verify_api_key)])
async def analyze(file: UploadFile = File(...), query: str = Form(...)):
    """Analyze image with vision model (protected endpoint)."""
    if not engine:
        raise HTTPException(status_code=503, detail="Model loading")
    
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content)).convert("RGB")
        response = engine.process_request(query, image)
        return {"response": response}
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shutdown", dependencies=[Depends(verify_api_key)])
async def shutdown():
    """Shutdown server (protected endpoint)."""
    logger.warning("Shutdown requested")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Sovereign-Doc Cloud Brain",
        "endpoints": ["/health", "/analyze", "/shutdown"]
    }
