# Troubleshooting Guide

Common issues and their solutions for Sovereign-Doc.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Docker & Qdrant Issues](#docker--qdrant-issues)
- [Processing Errors](#processing-errors)
- [Memory & Performance Issues](#memory--performance-issues)
- [Model Loading Errors](#model-loading-errors)
- [PDF & Document Issues](#pdf--document-issues)
- [Colab Brain Issues](#colab-brain-issues)
- [Streamlit UI Issues](#streamlit-ui-issues)

---

## Installation Issues

### Error: "ModuleNotFoundError: No module named 'pydantic'"

**Cause:** Dependencies not installed or wrong virtual environment  
**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Error: "Python version 3.9 not supported"

**Cause:** Python version too old  
**Solution:**
1. Install Python 3.10+ from https://python.org
2. Create new virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Error: "ERROR: Could not build wheels for opencv-python"

**Cause:** Missing system dependencies  
**Solution (Linux):**
```bash
sudo apt-get update
sudo apt-get install python3-dev build-essential libssl-dev libffi-dev
pip install --upgrade pip setuptools wheel
pip install opencv-python
```

---

## Docker & Qdrant Issues

### Error: "Connection refused to localhost:6333"

**Cause:** Qdrant Docker container not running  
**Solution:**

1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **If container not listed, start it:**
   ```bash
   docker-compose up -d
   ```

3. **Check container logs:**
   ```bash
   docker logs qdrant-db
   ```

4. **Verify Qdrant is accessible:**
   ```bash
   curl http://localhost:6333/healthz
   # Expected: {"status":"ok"}
   ```

### Error: "Docker daemon not running"

**Cause:** Docker Desktop not started  
**Solution:**
- **Windows/Mac:** Start Docker Desktop application
- **Linux:** 
  ```bash
  sudo systemctl start docker
  ```

### Error: "Port 6333 already in use"

**Cause:** Another service using the same port  
**Solution:**

1. **Find what's using the port:**
   ```bash
   # Windows
   netstat -ano | findstr :6333
   
   # Linux/Mac
   lsof -i :6333
   ```

2. **Either kill that process or change Qdrant port:**
   
   Edit `docker-compose.yml`:
   ```yaml
   ports:
     - "6334:6333"  # Map to different port
   ```
   
   Update `config.yaml`:
   ```yaml
   qdrant:
     url: "http://localhost:6334"
   ```

---

## Processing Errors

### Error: "System resources critical. Processing paused."

**Cause:** SystemMonitor detecting low RAM (>95% usage)  
**Solution:**

1. **Close other applications** to free memory

2. **Run manual cleanup:**
   - In Streamlit: Click "🧹 Clean Memory" button in sidebar

3. **Lower batch size in config.yaml:**
   ```yaml
   processing:
     batch_size: 1  # Process one page at a time
   ```

4. **Switch to OCR-only mode:**
   ```yaml
   processing:
     mode: "ocr_only"  # Lighter processing
   ```

### Error: "System in cool-down mode due to high temperature"

**Cause:** CPU temperature > 80°C  
**Solution:**

1. **Wait for system to cool** (5-10 minutes)

2. **Improve cooling:**
   - Clean dust from fans
   - Improve airflow around computer
   - Use cooling pad for laptops

3. **Lower workload:**
   ```yaml
   processing:
     batch_size: 1
     max_workers: 1
   ```

### Error: "Layout Agent not found" or "LayoutAgent will not work without it"

**Cause:** `ultralytics` package not installed  
**Solution:**
```bash
pip install ultralytics

# For GPU support
pip install ultralytics torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**Alternative (CPU only):**
```yaml
# config.yaml
processing:
  mode: "ocr_only"  # Skip layout detection
```

---

## Memory & Performance Issues

### Issue: "Out of Memory" / System Freezes During Processing

**Cause:** Document too large for available RAM  
**Solutions:**

1. **Enable Streaming Mode (auto-enabled for 8GB+ RAM):**
   ```yaml
   recovery:
     enable_streaming: true
     stream_threshold_pages: 10
   ```

2. **Process pages sequentially:**
   ```yaml
   processing:
     batch_size: 1
     max_workers: 1
   ```

3. **Use quantization for models:**
   ```yaml
   processing:
     use_quantization: true
   ```

4. **Increase system virtual memory:**
   - **Windows:** Control Panel → System → Advanced → Performance Settings → Virtual Memory
   - **Linux:** Increase swap size

### Issue: Processing is Very Slow

**Solutions:**

1. **Check which mode is active:**
   ```python
   # In config.yaml
   processing:
     mode: "hybrid"  # Best for modern GPUs
     # mode: "local_gpu"  # If you have strong GPU
     # mode: "ocr_only"  # Fastest but less accurate
   ```

2. **Enable GPU if available:**
   ```bash
   # Check NVIDIA GPU
   nvidia-smi
   
   # Install GPU libraries
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   pip install paddlepaddle-gpu
   ```

3. **Increase batch size (if you have RAM):**
   ```yaml
   processing:
     batch_size: 4  # Process 4 pages at once
     max_workers: 2
   ```

---

## Model Loading Errors

### Error: "Could not load PaddleOCR model"

**Cause:** PaddleOCR models not downloaded  
**Solution:**

1. **First run downloads models** (~500MB) - be patient

2. **If download fails, manual download:**
   ```bash
   python -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(lang='en')"
   ```

3. **Check internet connection** - models download from Baidu servers

4. **Use CPU version if GPU fails:**
   ```bash
   pip uninstall paddlepaddle-gpu
   pip install paddlepaddle
   ```

### Error: "CUDA out of memory"

**Cause:** GPU VRAM insufficient for models  
**Solutions:**

1. **Use smaller batch size:**
   ```yaml
   processing:
     batch_size: 1
   ```

2. **Enable 8-bit quantization:**
   ```yaml
   processing:
     use_quantization: true
   ```

3. **Switch to CPU mode:**
   ```yaml
   processing:
     mode: "ocr_only"
   ```

4. **Close other GPU applications:**
   ```bash
   # Check GPU usage
   nvidia-smi
   ```

---

## PDF & Document Issues

### Error: "PDFInfoNotInstalledError" or "poppler not found"

**Cause:** Poppler not installed (required for pdf2image)  
**Solution:**

**Windows:**
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler`
3. Add to PATH: `C:\Program Files\poppler\Library\bin`
4. Restart terminal/IDE

**Linux:**
```bash
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

**Verify:**
```bash
pdftoppm -v
# Expected: pdftoppm version 23.x.x
```

### Error: "PDF is corrupted or encrypted"

**Cause:** Invalid or password-protected PDF  
**Solutions:**

1. **Check if PDF opens normally** in a PDF reader

2. **Remove password protection:**
   - Use Adobe Acrobat or online tools to remove password
   - Re-upload the unlocked PDF

3. **Try re-saving the PDF:**
   - Open in browser or PDF reader
   - Print to PDF → Save as new file

### Error: "Image conversion failed for page X"

**Cause:** Corrupted page in PDF  
**Solution:**

1. **Skip problematic page:**
   - System will log error and continue with other pages

2. **Extract and re-insert page:**
   - Use PDF editor to extract page
   - Save as new PDF
   - Merge back to original

---

## Colab Brain Issues

### Error: "Tunnel connection failed" or "Could not connect to Colab"

**Cause:** ngrok tunnel not active or wrong URL  
**Solutions:**

1. **Check Colab notebook is running:**
   - Look for "Server running at: https://..." in Colab output
   - Cell should show "Running" status

2. **Verify ngrok URL in config.yaml:**
   ```yaml
   llm:
     base_url: "https://xxxx-xx-xx-xx-xx.ngrok-free.app"  # Must match Colab output
   ```

3. **Restart Colab runtime:**
   - Runtime → Restart runtime
   - Re-run all cells
   - Copy NEW ngrok URL to config.yaml

### Error: "ngrok: ERR_NGROK_3200"

**Cause:** ngrok auth token not set or invalid  
**Solution:**

1. **Check token in Colab secrets:**
   - Click 🔑 Secrets in left sidebar
   - Verify NGROK_TOKEN is set
   - Enable "Notebook access"

2. **Get new token if invalid:**
   - https://dashboard.ngrok.com/get-started/your-authtoken
   - Update in Colab secrets

### Error: "429 Too Many Requests" from Colab

**Cause:** Hit Colab free tier rate limits  
**Solutions:**

1. **Wait 1 hour** for rate limit reset

2. **Process fewer pages:**
   ```yaml
   processing:
     batch_size: 1
   ```

3. **Upgrade to Colab Pro** ($10/month for higher limits)

---

## Streamlit UI Issues

### Error: "Streamlit command not found"

**Cause:** Virtual environment not activated or Streamlit not installed  
**Solution:**
```bash
source venv/bin/activate
pip install streamlit
streamlit --version
```

### Issue: "Analyze Document" Button Disabled

**Cause:** System health check failed  
**Solution:**

1. **Check sidebar** for system status:
   - Red status = critical resources
   - Yellow = warning

2. **Free up RAM:**
   - Close other applications
   - Click "🧹 Clean Memory"

3. **Check temperature:**
   - If > 80°C, wait for cool-down

### Issue: Dashboard Shows "No conflicts detected" but should show conflicts

**Cause:** Dashboard not reading real state correctly  
**Solution:**

1. **Verify workflow completed:**
   - Check for "Processing complete" message
   - Look for error logs

2. **Check session state:**
   - Might be an integration bug
   - Report issue with logs

---

## General Debugging Tips

### Enable Debug Logging

Add to top of your script or config:

```python
# Set log level to DEBUG
import logging
logging.basicConfig(level=logging.DEBUG)

# For loguru
from loguru import logger
logger.add("debug.log", level="DEBUG")
```

Or in config.yaml:
```yaml
logging:
  level: "DEBUG"
  file: "logs/debug.log"
```

### Collect System Information

For bug reports, run:

```bash
python -c "
import sys
import platform
import torch if available
print(f'Python: {sys.version}')
print(f'Platform: {platform.platform()}')
print(f'CUDA: {torch.cuda.is_available() if torch else False}')
"
```

### Check Logs

**Application logs:**
- Check terminal/console output
- Look in `logs/` directory if configured

**Docker logs:**
```bash
docker logs qdrant-db
```

**System Monitor logs:**
- Check sidebar in Streamlit for current metrics

---

## Still Having Issues?

1. **Check existing issues:** https://github.com/yourusername/sovereign-doc/issues

2. **Create new issue** with:
   - Error message (full traceback)
   - Your environment (OS, Python version, GPU)
   - config.yaml (remove sensitive tokens)
   - Steps to reproduce

3. **Join discussions:** https://github.com/yourusername/sovereign-doc/discussions

---

## Quick Reference: Error Code Meanings

| Error Code | Meaning | Quick Fix |
|------------|---------|-----------|
| `ERR_QDRANT_CONN` | Can't connect to Qdrant | `docker-compose up -d` |
| `ERR_OOM` | Out of memory | Lower batch_size to 1 |
| `ERR_TEMP_HIGH` | CPU too hot | Wait for cool-down |
| `ERR_POPPLER` | PDF conversion failed | Install Poppler |
| `ERR_MODEL_LOAD` | AI model error | Check GPU/CUDA setup |
| `ERR_TUNNEL` | Colab connection | Check ngrok URL |
