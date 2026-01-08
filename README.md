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
