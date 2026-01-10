"""FastAPI server for Cloud Brain vision inference.

Exposes vision model via REST API with ngrok tunnel support for Colab.
"""

import os
import signal
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import io
from loguru import logger

from colab_brain.inference import VisionModelEngine

# Global engine instance
engine: Optional[VisionModelEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown"""
    global engine
    
    logger.info("Starting Cloud Brain server...")
    try:
        engine = VisionModelEngine()
        logger.success("Model loaded and ready")
        yield
    finally:
        logger.info("Shutting down...")
        engine = None


# Create FastAPI app
app = FastAPI(
    title="Sovereign-Doc Cloud Brain",
    description="Vision-language inference via vLLM",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ready" if engine else "loading",
        "model": engine.model_name if engine else None
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(..., description="Image file"),
    query: str = Form(..., description="Analysis query")
):
    """Analyze image with vision model"""
    if not engine:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Read and validate image
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Process request
        logger.info(f"Processing query: {query[:50]}...")
        response = engine.process_request(query, image)
        
        return {"response": response}
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shutdown")
async def shutdown():
    """Shutdown server (for Colab cleanup)"""
    logger.warning("Shutdown requested")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Sovereign-Doc Cloud Brain",
        "endpoints": ["/health", "/analyze", "/shutdown"]
    }
