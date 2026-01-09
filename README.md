# Sovereign-Doc

Zero-Cost, Privacy-First Multi-Modal Document Intelligence System

## Project Structure

```
sober/
├── colab_brain/              # Remote GPU-accelerated vision processing
│   └── __init__.py
├── local_body/               # Local privacy-first processing
│   ├── agents/              # Processing agents (OCR, Vision, Layout, etc.)
│   │   ├── __init__.py
│   │   └── base.py          # Base agent interface
│   ├── core/                # Core data models and utilities
│   │   ├── __init__.py
│   │   ├── datamodels.py    # Pydantic data models
│   │   ├── config_manager.py # Configuration management
│   │   └── logging_setup.py  # Logging configuration
│   ├── database/            # Vector store integrations
│   │   └── __init__.py
│   ├── ui/                  # Streamlit UI components
│   │   └── __init__.py
│   └── utils/               # Utility functions
│       └── __init__.py
├── data/                    # Data directories
│   ├── input/              # Input documents
│   ├── output/             # Processed outputs
│   ├── temp/               # Temporary files
│   └── logs/               # System logs
├── tests/                   # Test suite
│   └── __init__.py
├── config.yaml             # System configuration
└── requirements.txt        # Python dependencies
```

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure System**
   - Edit `config.yaml` for your hardware and preferences
   - Set environment variables for sensitive settings (e.g., `SOVEREIGN_NGROK_URL`)

3. **Initialize Logging**
   ```python
   from local_body.core.logging_setup import setup_logging
   setup_logging()
   ```

## ⚠️ Python Compatibility Warning

**FastEmbed Requires Python 3.8 - 3.12**

The `fastembed` library (used for document embeddings) requires Python <3.13 due to `onnxruntime` dependency limitations. If you're running Python 3.14+, you have two options:

### Option 1: Docker-Based Testing (Recommended)

Use the provided Docker test runner that creates a Python 3.12 environment:

**Windows:**
```bash
run_tests_docker.bat
```

**Linux/Mac:**
```bash
chmod +x run_tests_docker.sh
./run_tests_docker.sh
```

This will:
1. Build a Docker image with Python 3.12
2. Install all dependencies including `fastembed`
3. Run the test suite with proper network access to Qdrant

### Option 2: Create Python 3.12 Virtual Environment

```bash
# Using conda
conda create -n sovereign-doc python=3.12
conda activate sovereign-doc
pip install -r requirements.txt
pip install fastembed==0.6.1

# Using pyenv
pyenv install 3.12.0
pyenv virtualenv 3.12.0 sovereign-doc
pyenv activate sovereign-doc
pip install -r requirements.txt
pip install fastembed==0.6.1
```

## Running Tests

### With Docker (Python 3.14+ Compatible)
```bash
# Windows
run_tests_docker.bat

# Linux/Mac
./run_tests_docker.sh
```

### With Local Python 3.12
```bash
pytest tests/ -v
```

## Infrastructure Setup

### Qdrant Vector Database

Start the Qdrant service using Docker Compose:

```bash
docker-compose up -d
```

Verify it's running:
```bash
curl http://localhost:6333/healthz
```

Stop the service:
```bash
docker-compose down
```

## Core Components

### Data Models (`local_body/core/datamodels.py`)
- **Document**: Complete document with pages and metadata
- **Page**: Single page with detected regions
- **Region**: Detected region with bounding box and content
- **Conflict**: Detected discrepancy between extraction methods
- **ConflictResolution**: Resolution of detected conflicts

### Base Agent (`local_body/agents/base.py`)
Abstract base class for all processing agents with:
- `async def process(document: Document) -> Any`
- `confidence_score() -> float`
- Configuration management

### Configuration (`local_body/core/config_manager.py`)
- YAML-based configuration
- Environment variable overrides
- Hardware detection and validation

### Logging (`local_body/core/logging_setup.py`)
- Console and file logging with rotation
- Structured agent activity logging
- Performance metrics tracking

## Next Steps

See `tasks.md` for the complete implementation roadmap.
