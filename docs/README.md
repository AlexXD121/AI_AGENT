# Sovereign-Doc Documentation

Comprehensive guides for installing, configuring, and using Sovereign-Doc.

---

## Quick Links

| Guide | Description | When to Read |
|-------|-------------|--------------|
| **[Installation Guide](INSTALLATION.md)** | Complete setup from zero to processing | First-time setup |
| **[Configuration Guide](CONFIGURATION_GUIDE.md)** | Hardware tuning and optimization | After installation |
| **[Colab Setup](COLAB_SETUP.md)** | Hybrid cloud architecture guide | Want free GPU power |
| **[Troubleshooting](TROUBLESHOOTING.md)** | Common issues and solutions | When things break |

---

## Getting Started (5-Minute Quickstart)

```bash
# 1. Clone and setup
git clone <repo-url>
cd sovereign-doc
setup_local_env.bat  # Windows

# 2. Start vector database
docker-compose up -d

# 3. Run app
streamlit run app.py

# 4. Upload PDF and process!
```

**Full details:** [Installation Guide](INSTALLATION.md)

---

## Documentation Structure

### For New Users

1. **Start here:** [Installation Guide](INSTALLATION.md)
   - Prerequisites
   - Step-by-step setup
   - Verification
   - First document processing

2. **Then:** [Configuration Guide](CONFIGURATION_GUIDE.md)
   - Choose processing mode for your hardware
   - Performance tuning
   - Accuracy vs speed tradeoffs

3. **Optional:** [Colab Setup](COLAB_SETUP.md)
   - Only if you want free cloud GPU
   - Hybrid architecture explanation

4. **Keep handy:** [Troubleshooting](TROUBLESHOOTING.md)
   - Reference when errors occur

### For Developers

- **Architecture:** See `ARCHITECTURE.md` (if exists)
- **API Reference:** See `API.md` (if exists)
- **Contributing:** See `../CONTRIBUTING.md` (if exists)

---

## Hardware Requirements

| Component | Minimum | Recommended | Optimal |
|-----------|---------|-------------|---------|
| **RAM** | 8GB | 16GB | 32GB+ |
| **CPU** | 4 cores | 8 cores | 16+ cores |
| **GPU** | None (CPU only) | GTX 1660 (6GB VRAM) | RTX 3080+ (10GB+) |
| **Storage** | 10GB free | 50GB free | 100GB+ SSD |
| **Internet** | Optional | Optional | Required for Colab |

**See:** [Configuration Guide - Hardware Profiles](CONFIGURATION_GUIDE.md#hardware-profiles)

---

## Processing Modes

| Mode | Hardware Needed | Speed | Accuracy | Use Case |
|------|-----------------|-------|----------|----------|
| **ocr_only** | 8GB RAM | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Budget systems, clean docs |
| **hybrid** | 16GB RAM | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Most users (default) |
| **local_gpu** | 16GB RAM + GPU | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Power users, batch processing |
| **colab_brain** | 8GB RAM + Internet | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Best accuracy, zero cost |

**See:** [Configuration Guide - Processing Modes](CONFIGURATION_GUIDE.md#processing-modes)

---

## Common Workflows

### First-Time Setup

1. Install prerequisites (Python, Docker)
2. Run `setup_local_env.bat`
3. Start Qdrant: `docker-compose up -d`
4. Configure `config.yaml` for your hardware
5. Verify: `python verify_full_integration.py`
6. Launch: `streamlit run app.py`

**Guide:** [Installation](INSTALLATION.md)

### Processing a Single Document

1. Start app: `streamlit run app.py`
2. Upload PDF
3. Click "Analyze Document"
4. Review results on dashboard
5. Resolve conflicts (if any)
6. Save to knowledge base

### Batch Processing Invoices

1. Place PDFs in `test_data/invoices/`
2. Run: `python demos/demo_invoices.py test_data/invoices/`
3. Review batch report
4. Fix any failures
5. Export results

**Demo:** See `demos/README.md`

### Setting Up Colab Brain

1. Sign up for ngrok (free)
2. Upload `notebooks/sovereign_brain.ipynb` to Colab
3. Set `NGROK_TOKEN` in Colab secrets
4. Run notebook
5. Copy ngrok URL
6. Update `config.yaml` with URL
7. Test connection

**Guide:** [Colab Setup](COLAB_SETUP.md)

---

## Troubleshooting Quick Reference

| Symptom | Probable Cause | Quick Fix |
|---------|----------------|-----------|
| "Connection refused" | Qdrant not running | `docker-compose up -d` |
| Button disabled | RAM critical | Close apps, click "Clean Memory" |
| Slow processing | Wrong mode for hardware | Check [Configuration Guide](CONFIGURATION_GUIDE.md) |
| "Poppler error" | Missing dependency | Install Poppler ([instructions](TROUBLESHOOTING.md#error-pdfinfonotinstallederror-or-poppler-not-found)) |
| Colab disconnect | ngrok tunnel expired | Rerun Colab, update URL |

**Full guide:** [Troubleshooting](TROUBLESHOOTING.md)

---

## Configuration Examples

### Budget Laptop (8GB RAM, No GPU)

```yaml
processing:
  mode: "ocr_only"
  batch_size: 1

hardware:
  available_ram_gb: 8

recovery:
  enable_streaming: true
```

### Gaming PC (16GB RAM, GTX 1660)

```yaml
processing:
  mode: "hybrid"
  batch_size: 2

hardware:
  available_ram_gb: 16
  has_gpu: true
```

### Workstation (32GB RAM, RTX 3080)

```yaml
processing:
  mode: "local_gpu"
  batch_size: 4

hardware:
  available_ram_gb: 32
  gpu_vram_gb: 12
```

**More templates:** [Configuration Guide](CONFIGURATION_GUIDE.md#configuration-templates)

---

## Additional Resources

### Official

- **GitHub Repository:** https://github.com/yourusername/sovereign-doc
- **Issue Tracker:** https://github.com/yourusername/sovereign-doc/issues
- **Discussions:** https://github.com/yourusername/sovereign-doc/discussions

### Community

- **Discord:** (link if exists)
- **Reddit:** (link if exists)
- **Blog:** (link if exists)

### Related Projects

- **LangGraph:** https://github.com/langchain-ai/langgraph
- **Qdrant:** https://qdrant.tech/
- **PaddleOCR:** https://github.com/PaddlePaddle/PaddleOCR
- **Ultralytics:** https://github.com/ultralytics/ultralytics

---

## Contributing to Documentation

Found an error or want to improve these docs?

1. Fork the repository
2. Edit files in `docs/`
3. Submit a pull request

**Style guide:**
- Use clear, concise language
- Include code examples
- Add screenshots where helpful
- Test all commands before documenting

---

## Document Index

### Setup & Installation
- [Installation Guide](INSTALLATION.md) - Complete setup instructions
- [Colab Setup](COLAB_SETUP.md) - Cloud GPU integration

### Configuration & Tuning
- [Configuration Guide](CONFIGURATION_GUIDE.md) - Hardware optimization
- [Troubleshooting](TROUBLESHOOTING.md) - Problem solving

### Usage
- `../demos/README.md` - Demo scripts
- `../tests/benchmarks/README.md` - Benchmarking (if exists)

### Development
- `../CONTRIBUTING.md` - Contributing guidelines (if exists)
- `../ARCHITECTURE.md` - System design (if exists)

---

## Version Information

**Documentation Version:** 1.0  
**Last Updated:** 2026-01-16  
**Sovereign-Doc Version:** Check `git describe --tags`

---

## License

Same as the main project. See `../LICENSE` for details.
