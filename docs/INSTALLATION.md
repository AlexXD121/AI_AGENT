# Installation Guide

Complete guide for setting up Sovereign-Doc from scratch on your local machine.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

- **Python 3.10 or higher** (3.11/3.12 recommended)
  - Download from: https://www.python.org/downloads/
  - Verify: `python --version`

- **Docker Desktop** (for Qdrant vector database)
  - Download from: https://www.docker.com/products/docker-desktop
  - Verify: `docker --version`

- **Git** (for cloning repository)
  - Download from: https://git-scm.com/downloads
  - Verify: `git --version`

### Optional (Recommended)

- **NVIDIA GPU with CUDA** (for local GPU processing)
  - CUDA Toolkit 11.8 or higher
  - cuDNN 8.x
  - Verify: `nvidia-smi`

- **Poppler** (for PDF rendering)
  - **Windows:** Download from https://github.com/oschwartz10612/poppler-windows/releases
  - **Linux:** `sudo apt-get install poppler-utils`
  - **macOS:** `brew install poppler`

- **Tesseract OCR** (optional, for OCR fallback)
  - **Windows:** https://github.com/UB-Mannheim/tesseract/wiki
  - **Linux:** `sudo apt-get install tesseract-ocr`
  - **macOS:** `brew install tesseract`

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/sovereign-doc.git
cd sovereign-doc
```

---

## Step 2: Set Up Python Environment

### Windows

Run the provided setup script:

```cmd
setup_local_env.bat
```

This script will:
1. Create a virtual environment in `venv/`
2. Activate the environment
3. Upgrade pip
4. Install all dependencies from `requirements.txt`

**Manual Setup (if script fails):**
```cmd
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 3: Start Vector Database (Qdrant)

Sovereign-Doc uses Qdrant for document storage and semantic search.

### Using Docker Compose (Recommended)

```bash
docker-compose up -d
```

This starts:
- **Qdrant** on `http://localhost:6333`
- **Qdrant Web UI** on `http://localhost:6334`

### Verify Qdrant is Running

Open your browser and navigate to:
```
http://localhost:6334
```

You should see the Qdrant dashboard.

**Or check via command line:**
```bash
curl http://localhost:6333/healthz
# Expected output: {"status":"ok"}
```

---

## Step 4: Configure the System

### Basic Configuration

The system uses `config.yaml` for all settings. For first-time setup:

1. Copy the example config (if provided):
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Minimum required settings:**
   ```yaml
   processing:
     mode: "hybrid"  # or "ocr_only" for CPU-only systems
   
   qdrant:
     url: "http://localhost:6333"
   
   hardware:
     available_ram_gb: 16  # Adjust to your system
   ```

3. **For low-end hardware (8GB RAM):**
   ```yaml
   processing:
     mode: "ocr_only"
     batch_size: 1
   
   hardware:
     available_ram_gb: 8
   ```

---

## Step 5: Install Optional Dependencies

### For GPU Support (Local Processing)

If you have an NVIDIA GPU and want to use local GPU processing:

```bash
# Install PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Install GPU-enabled PaddlePaddle
pip install paddlepaddle-gpu
```

### For Complete OCR/Vision Stack

```bash
# Install all AI models (large download ~5GB)
pip install ultralytics paddleocr transformers
```

---

## Step 6: Verify Installation

Run the integration verification script:

```bash
python verify_full_integration.py
```

**Expected output:**
```
✓ Python version: 3.11.x
✓ All core dependencies installed
✓ Qdrant connected successfully
✓ Config loaded: config.yaml
✓ Hardware detected: 16GB RAM, NVIDIA RTX 3080
✓ SystemMonitor initialized
✓ DocumentLoader working
✓ DocumentWorkflow compiled

========================================
✅ Installation verified successfully!
========================================
```

If you see any ❌ errors, check the [Troubleshooting Guide](TROUBLESHOOTING.md).

---

## Step 7: Run the Application

### Start the Streamlit UI

```bash
streamlit run app.py
```

The application will open in your browser at:
```
http://localhost:8501
```

### Test Document Processing

1. Upload a PDF document
2. Click "Analyze Document"
3. Wait for processing to complete
4. View results on the dashboard

---

## Step 8: Set Up Colab Brain (Optional)

For enhanced vision and LLM capabilities using Google Colab's free GPU:

See the [Colab Setup Guide](COLAB_SETUP.md) for detailed instructions.

---

## Installation Verification Checklist

- [ ] Python 3.10+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`pip list` shows pydantic, streamlit, langgraph, etc.)
- [ ] Docker running with Qdrant container
- [ ] Qdrant accessible at http://localhost:6333
- [ ] config.yaml configured
- [ ] verify_full_integration.py passes all checks
- [ ] Streamlit app launches successfully
- [ ] Sample document processes without errors

---

## Quick Start Commands

```bash
# Clone and setup (one-time)
git clone <repo-url>
cd sovereign-doc
setup_local_env.bat  # Windows
# or: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Start services
docker-compose up -d

# Run app
streamlit run app.py

# Run demos
python demos/demo_financial.py test_data/sample.pdf

# Run benchmarks
python tests/benchmarks/run_validation.py
```

---

## Minimal Installation (No GPU)

For CPU-only systems or testing:

```bash
# Install minimal dependencies only
pip install pydantic loguru pyyaml psutil streamlit langgraph opencv-python pdf2image

# Set config to OCR-only mode
# config.yaml:
#   processing:
#     mode: "ocr_only"

# Start without vector DB
streamlit run app.py
```

---

## Upgrade Installation

To update Sovereign-Doc to the latest version:

```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart services
docker-compose restart
```

---

## Uninstallation

To completely remove Sovereign-Doc:

```bash
# Stop Docker containers
docker-compose down -v

# Remove virtual environment
rm -rf venv/  # Linux/macOS
# or
rmdir /s venv  # Windows

# Remove project directory
cd ..
rm -rf sovereign-doc/
```

---

## Next Steps

- ✅ **Configure for your hardware:** [Configuration Guide](CONFIGURATION_GUIDE.md)
- ✅ **Set up Colab Brain:** [Colab Setup](COLAB_SETUP.md)
- ✅ **Troubleshoot issues:** [Troubleshooting](TROUBLESHOOTING.md)
- ✅ **Run demos:** See `demos/README.md`

---

## Support

- **Issues:** https://github.com/yourusername/sovereign-doc/issues
- **Discussions:** https://github.com/yourusername/sovereign-doc/discussions
- **Documentation:** https://sovereign-doc.readthedocs.io
