# Running the Sovereign-Doc UI

This guide explains how to run the Streamlit UI for Sovereign-Doc.

## Prerequisites

### 1. Install System Dependencies

**For PDF rendering (pdf2image), you need poppler-utils:**

**Windows:**
```powershell
# Download poppler from: https://github.com/oschwartz10612/poppler-windows/releases/
# Extract and add bin folder to PATH
```

**macOS:**
```bash
brew install poppler
```

**Linux:**
```bash
sudo apt-get install poppler-utils
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Running the UI

### Start Qdrant (Vector Database)

```bash
docker-compose up -d qdrant
```

### Start Ollama (Local LLM - Optional)

```bash
# If using Cloud Brain, Ollama is optional
ollama serve
```

### Launch Streamlit UI

```bash
streamlit run app.py
```

The UI will open at `http://localhost:8501`

## UI Features

### Three-Column Layout

1. **Left Panel (50%)** - Document Viewer
   - PDF page rendering
   - Bounding boxes with confidence colors:
     - 🟢 Green: >90% confidence
     - 🟡 Yellow: 70-90% confidence
     - 🔴 Red: <70% confidence
   - Region type labels
   - Page navigation slider

2. **Center Panel (30%)** - Extraction Results
   - Processing stage indicator
   - OCR text by region
   - Vision analysis summaries
   - Validation metrics

3. **Right Panel (20%)** - Conflict Monitor
   - Active conflicts count
   - Conflict cards with OCR vs Vision values
   - Impact scores
   - Resolution buttons (Task 9.2)

### Configuration (Sidebar)

- Processing mode selection
- Confidence thresholds
- Batch size
- Cache management
- System status

## Development Mode

For development with auto-reload:

```bash
streamlit run app.py --server.runOnSave true
```

## Troubleshooting

### "pdf2image not available"

Install poppler-utils (see Prerequisites) and pdf2image:
```bash
pip install pdf2image
```

### "No module named 'streamlit'"

Install Streamlit:
```bash
pip install streamlit>=1.30.0
```

### "Qdrant connection error"

Ensure Qdrant is running:
```bash
docker-compose up -d qdrant
# Check: http://localhost:6333/dashboard
```

## Next Steps

- **Task 9.2**: Conflict resolution interface
- **Task 9.3**: Document upload & processing integration
- **Task 9.4**: Export functionality
