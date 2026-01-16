"""FastAPI server for Cloud Brain vision inference.

Exposes vision model via REST API with ngrok tunnel support for Colab.
"""

import os
import signal
import io
import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from PIL import Image
from loguru import logger

from colab_brain.inference import VisionModelEngine

# Security Scheme
security = HTTPBearer()

# Load secrets from environment
BRAIN_SECRET = os.environ.get("BRAIN_SECRET", "sovereign-secret-key")  # Legacy API key
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")  # New secure token


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate Bearer token (legacy auth)."""
    if credentials.credentials != BRAIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_token(x_sovereign_token: Optional[str] = Header(None)):
    """Verify X-Sovereign-Token header for secure access.
    
    Args:
        x_sovereign_token: Token from request header
        
    Raises:
        HTTPException: If token is missing or invalid
        
    Returns:
        The validated token
    """
    # If ACCESS_TOKEN not configured, log warning but allow (dev mode)
    if not ACCESS_TOKEN:
        logger.warning("ACCESS_TOKEN not configured - running in development mode (insecure!)")
        return None
    
    # Check token provided
    if not x_sovereign_token:
        logger.error("Authentication failed: X-Sovereign-Token header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Sovereign-Token header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Validate token (use secrets.compare_digest to prevent timing attacks)
    if not secrets.compare_digest(x_sovereign_token, ACCESS_TOKEN):
        logger.error("Authentication failed: Invalid access token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    logger.debug("Token authentication successful")
    return x_sovereign_token


# Global engine
engine: Optional[VisionModelEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown."""
    global engine
    logger.info("Starting Cloud Brain server...")
    
    # Log security status
    if ACCESS_TOKEN:
        logger.info(f"Security enabled: Access token configured (length: {len(ACCESS_TOKEN)})")
    else:
        logger.warning("⚠️  Security disabled: ACCESS_TOKEN not set - Running in DEV mode!")
    
    engine = VisionModelEngine()
    logger.success("Model loaded")
    yield
    logger.info("Shutting down...")
    engine = None


app = FastAPI(title="Sovereign-Doc Brain", lifespan=lifespan)


@app.get("/health", dependencies=[Depends(verify_token)])
async def health():
    """Health check endpoint (protected)."""
    return {
        "status": "ready" if engine else "loading",
        "model": engine.model_name if engine else None,
        "security": "enabled" if ACCESS_TOKEN else "disabled"
    }



@app.post("/analyze", dependencies=[Depends(verify_token)])
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


@app.post("/shutdown", dependencies=[Depends(verify_token)])
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
