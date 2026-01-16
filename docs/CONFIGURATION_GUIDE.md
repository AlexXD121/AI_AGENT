# Configuration & Tuning Guide

Optimize Sovereign-Doc for your specific hardware and use case.

---

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Processing Modes](#processing-modes)
- [Hardware Profiles](#hardware-profiles)
- [Performance Tuning](#performance-tuning)
- [Accuracy vs Speed Tradeoffs](#accuracy-vs-speed-tradeoffs)
- [Advanced Settings](#advanced-settings)

---

## Configuration Overview

Sovereign-Doc uses `config.yaml` for all system settings. The file is organized into logical sections:

```yaml
# High-level processing behavior
processing:
  mode: "hybrid"
  batch_size: 2
  max_workers: 2

# Hardware capabilities
hardware:
  available_ram_gb: 16
  has_gpu: true

# Model thresholds
ocr:
  confidence_threshold: 0.6
  
vision:
  confidence_threshold: 0.7

# Conflict detection
validation:
  conflict_threshold: 0.7
```

---

## Processing Modes

Choose based on your hardware and accuracy needs:

### 1. `ocr_only` - Lightweight Mode

**Use when:**
- Low RAM (< 8GB)
- No GPU available
- Speed is critical
- Documents are clean/high-quality

**Configuration:**
```yaml
processing:
  mode: "ocr_only"
  batch_size: 2
  max_workers: 1

hardware:
  available_ram_gb: 8
  has_gpu: false
```

**Performance:**
- Speed: ⭐⭐⭐⭐⭐ (2-3 sec/page)
- Accuracy: ⭐⭐⭐ (good for typed text, struggles with handwriting/complex layouts)
- RAM: 2-4GB

### 2. `hybrid` - Balanced Mode (Default)

**Use when:**
- Medium RAM (8-16GB)
- May have GPU, may not
- Want good accuracy without heavy resources
- Mix of document types

**Configuration:**
```yaml
processing:
  mode: "hybrid"
  batch_size: 2
  max_workers: 2
  use_quantization: true

hardware:
  available_ram_gb: 16
  has_gpu: auto  # Auto-detect
```

**Performance:**
- Speed: ⭐⭐⭐⭐ (5-8 sec/page)
- Accuracy: ⭐⭐⭐⭐ (very good)
- RAM: 6-10GB

### 3. `local_gpu` - High Performance Mode

**Use when:**
- High RAM (16GB+)
- NVIDIA GPU with 8GB+ VRAM
- Maximum accuracy needed
- Processing large batches

**Configuration:**
```yaml
processing:
  mode: "local_gpu"
  batch_size: 4
  max_workers: 4
  use_quantization: false

hardware:
  available_ram_gb: 32
  has_gpu: true
  gpu_vram_gb: 12
```

**Performance:**
- Speed: ⭐⭐⭐⭐⭐ (2-3 sec/page)
- Accuracy: ⭐⭐⭐⭐⭐ (excellent)
- RAM: 12-20GB
- VRAM: 6-12GB

### 4. `colab_brain` - Cloud Hybrid Mode

**Use when:**
- Any local hardware
- Want best accuracy
- OK with internet dependency
- Free Colab GPU (T4)

**Configuration:**
```yaml
processing:
  mode: "colab_brain"

llm:
  provider: "vllm"
  base_url: "https://xxxx.ngrok-free.app"  # Your Colab URL
```

**Performance:**
- Speed: ⭐⭐⭐⭐ (5-10 sec/page, varies with internet)
- Accuracy: ⭐⭐⭐⭐⭐ (excellent)
- RAM: 4-8GB local
- Internet: Required

---

## Hardware Profiles

### Low-End System (8GB RAM, No GPU)

**Example:** Laptop, budget desktop

```yaml
processing:
  mode: "ocr_only"
  batch_size: 1
  max_workers: 1
  use_quantization: true

hardware:
  available_ram_gb: 8
  has_gpu: false

recovery:
  enable_streaming: true
  stream_threshold_pages: 5  # Stream docs > 5 pages
```

**Expected Performance:**
- Simple PDF: 2-3 sec/page
- Complex PDF: 5-8 sec/page
- 100-page document: ~10 minutes

### Mid-Range System (16GB RAM, GTX 1660 or similar)

**Example:** Gaming PC, workstation

```yaml
processing:
  mode: "hybrid"
  batch_size: 2
  max_workers: 2
  use_quantization: true

hardware:
  available_ram_gb: 16
  has_gpu: true
  gpu_vram_gb: 6

vision:
  enabled: true
  confidence_threshold: 0.7
```

**Expected Performance:**
- Simple PDF: 3-5 sec/page
- Complex PDF: 8-12 sec/page
- 100-page document: ~15 minutes

### High-End System (32GB RAM, RTX 3080+)

**Example:** Deep learning workstation, gaming rig

```yaml
processing:
  mode: "local_gpu"
  batch_size: 4
  max_workers: 4
  use_quantization: false

hardware:
  available_ram_gb: 32
  has_gpu: true
  gpu_vram_gb: 12

ocr:
  use_gpu: true
  batch_size: 4

vision:
  use_gpu: true
  batch_size: 2
```

**Expected Performance:**
- Simple PDF: 1-2 sec/page
- Complex PDF: 3-5 sec/page
- 100-page document: ~5 minutes

### Server / Cloud (64GB+ RAM, A100 GPU)

**Example:** AWS p3.2xlarge, production server

```yaml
processing:
  mode: "local_gpu"
  batch_size: 8
  max_workers: 8
  use_quantization: false

hardware:
  available_ram_gb: 64
  has_gpu: true
  gpu_vram_gb: 40

recovery:
  enable_checkpointing: true
  checkpoint_interval: 50  # Checkpoint every 50 pages
```

**Expected Performance:**
- Simple PDF: 0.5-1 sec/page
- Complex PDF: 2-3 sec/page
- 1000-page document: ~30 minutes

---

## Performance Tuning

### Optimize Batch Size

**Rule of thumb:**
- **Low RAM (8GB):** `batch_size: 1`
- **Medium RAM (16GB):** `batch_size: 2`
- **High RAM (32GB+):** `batch_size: 4-8`

**Test optimal batch size:**
```bash
# Try different values and time
python -m tests.benchmarks.run_validation

# Check "Processing Time Analysis" in report
```

### Optimize Worker Count

**Rule of thumb:**
- `max_workers = CPU cores / 2`

**Auto-detect:**
```yaml
processing:
  max_workers: auto  # System will detect optimal count
```

**Manual:**
```yaml
processing:
  max_workers: 4  # For 8-core CPU
```

### Enable/Disable Streaming

**Use streaming for:**
- Low RAM systems
- Very large documents (> 50 pages)
- Preventing OOM crashes

**Configuration:**
```yaml
recovery:
  enable_streaming: true
  stream_threshold_pages: 20  # Stream if doc > 20 pages
  stream_batch_size: 5  # Process 5 pages at a time
```

---

## Accuracy vs Speed Tradeoffs

### Maximum Speed (Sacrifice some accuracy)

```yaml
processing:
  mode: "ocr_only"
  batch_size: 4

ocr:
  confidence_threshold: 0.5  # Lower = faster, less filtering

validation:
  enable_conflict_detection: false  # Skip validation
```

**Use for:**
- Prototyping
- High-volume, low-accuracy needs
- Pre-screening documents

### Maximum Accuracy (Slower)

```yaml
processing:
  mode: "local_gpu"  # or colab_brain
  batch_size: 1  # More careful processing

ocr:
  confidence_threshold: 0.8  # Higher = more filtering

vision:
  confidence_threshold: 0.8
  
validation:
  conflict_threshold: 0.5  # Lower = more conflicts flagged
  enable_conflict_detection: true
```

**Use for:**
- Financial documents
- Legal contracts
- Medical records
- Critical data extraction

### Balanced (Recommended)

```yaml
processing:
  mode: "hybrid"
  batch_size: 2

ocr:
  confidence_threshold: 0.6

vision:
  confidence_threshold: 0.7
  
validation:
  conflict_threshold: 0.7
```

---

## Advanced Settings

### Conflict Detection Tuning

**Conflict threshold** determines when OCR and Vision disagreements are flagged:

```yaml
validation:
  conflict_threshold: 0.7  # 0.0 = flag everything, 1.0 = flag nothing
```

**Lower threshold (0.3-0.5):**
- ✅ Catches more potential errors
- ❌ More false positives
- **Use for:** Critical documents

**Medium threshold (0.6-0.8):**
- ✅ Balanced
- **Use for:** General documents (default)

**Higher threshold (0.9-1.0):**
- ✅ Only high-confidence conflicts
- ❌ May miss subtle errors
- **Use for:** High-volume processing

### System Monitor Tuning

**Adjust health check thresholds:**

```yaml
monitoring:
  ram_warning_threshold: 0.75  # Warn at 75% RAM
  ram_critical_threshold: 0.95  # Block at 95% RAM
  
  cpu_temp_warning: 70  # Warn at 70°C
  cpu_temp_critical: 80  # Cool-down at 80°C
  
  enable_auto_cleanup: true
  cleanup_interval_minutes: 30
```

### Recovery & Checkpointing

**For large batch jobs:**

```yaml
recovery:
  enable_checkpointing: true
  checkpoint_interval: 100  # Save state every 100 pages
  checkpoint_dir: "checkpoints/"
  
  enable_auto_recovery: true  # Resume from last checkpoint on crash
```

### Model Selection

**Override default models:**

```yaml
ocr:
  model: "paddleocr"  # or "tesseract", "easyocr"
  language: "en"  # or "ch", "fr", "de", etc.

vision:
  model: "llava-v1.6-mistral-7b"
  # or: "llava-v1.5-13b", "bakllava", etc.

layout:
  model: "yolov8n"  # n=nano, s=small, m=medium, l=large
  # Larger = more accurate but slower
```

---

## Configuration Templates

### Template 1: Budget Laptop

```yaml
processing:
  mode: "ocr_only"
  batch_size: 1
  max_workers: 1

hardware:
  available_ram_gb: 8
  has_gpu: false

recovery:
  enable_streaming: true
  stream_threshold_pages: 10

validation:
  conflict_threshold: 0.8
```

### Template 2: Gaming PC

```yaml
processing:
  mode: "hybrid"
  batch_size: 2
  max_workers: 2
  use_quantization: true

hardware:
  available_ram_gb: 16
  has_gpu: true

validation:
  conflict_threshold: 0.7
```

### Template 3: Workstation

```yaml
processing:
  mode: "local_gpu"
  batch_size: 4
  max_workers: 4

hardware:
  available_ram_gb: 32
  has_gpu: true
  gpu_vram_gb: 12

recovery:
  enable_checkpointing: true
  checkpoint_interval: 100
```

### Template 4: Cloud (Colab Brain)

```yaml
processing:
  mode: "colab_brain"
  batch_size: 2

llm:
  provider: "vllm"
  base_url: "https://YOUR-NGROK-URL.ngrok-free.app"

hardware:
  available_ram_gb: 8  # Local RAM
  has_gpu: false  # Local GPU
```

---

## Testing Your Configuration

After changing config.yaml:

1. **Run verification:**
   ```bash
   python verify_full_integration.py
   ```

2. **Benchmark performance:**
   ```bash
   python tests/benchmarks/run_validation.py
   ```
   Check `reports/figures/latency_distribution.png`

3. **Test with real document:**
   ```bash
   streamlit run app.py
   # Upload a test PDF
   ```

4. **Monitor resources:**
   - Check sidebar in Streamlit
   - Watch RAM/CPU/GPU usage

5. **Tune and repeat** until optimal

---

## Next Steps

- ✅ **Set up for your hardware:** Use templates above
- ✅ **Benchmark:** Run validation suite
- ✅ **Troubleshoot:** [Troubleshooting Guide](TROUBLESHOOTING.md)
- ✅ **Deploy:** [Installation Guide](INSTALLATION.md)
