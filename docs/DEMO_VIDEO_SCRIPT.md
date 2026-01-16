# Sovereign-Doc Demo Video Script

**Duration:** ~5 minutes  
**Objective:** Showcase the complete document intelligence pipeline from setup to advanced features

---

## Opening (15 seconds)

**VISUAL:**
- Fade in to desktop with terminal and logo
- Title card: "Sovereign-Doc: Privacy-First Document Intelligence"
- Subtitle: "Zero-Cost, Local-First, AI-Powered"

**NARRATION:**
> "Welcome to Sovereign-Doc - a next-generation document processing system that keeps your data private while delivering enterprise-grade accuracy."

---

## Scene 1: Quick Setup (45 seconds)

### A. Environment Setup (20 sec)

**VISUAL:**
- Open terminal in project directory
- Show `docker-compose.yml` briefly
- Run commands with clear output

**COMMANDS:**
```bash
# Start vector database
docker-compose up -d

# Verify Qdrant
curl http://localhost:6333/healthz

# Check Python environment
python --version
```

**NARRATION:**
> "Setup is simple. Start the Qdrant vector database with one command. No cloud accounts, no API keys - everything runs locally."

### B. Application Launch (25 sec)

**VISUAL:**
- Run Streamlit app
- Show startup log rolling through
- App opens in browser with sleek dark theme

**COMMANDS:**
```bash
# Launch application
streamlit run app.py
```

**NARRATION:**
> "The application bootstraps automatically - loading configuration, validating hardware, and initializing AI models. Within seconds, you have a production-ready document intelligence system."

**HIGHLIGHT:**
- Point out the "System Initialized" log
- Show RAM usage in sidebar

---

## Scene 2: The Happy Path - Clean Document (90 seconds)

### A. Upload Document (15 sec)

**VISUAL:**
- Drag-and-drop a clean, professional invoice PDF
- Show file upload progress
- Highlight the elegant file uploader design

**NARRATION:**
> "Let's process a standard business invoice. Just drag and drop - the system automatically validates the file and prepares it for analysis."

### B. Processing Workflow (45 sec)

**VISUAL:**
- Click "Analyze Document"
- Show processing stages in real-time:
  - ✅ Layout Detection (2 sec) - "Analyzing structure..."
  - ✅ OCR Extraction (3 sec) - "Extracting text..."
  - ✅ Vision Analysis (4 sec) - "Deep learning analysis..."
  - ✅ Validation (2 sec) - "Verifying accuracy..."

**NARRATION:**
> "Sovereign-Doc uses a multi-agent pipeline: First, layout detection identifies document structure. Then OCR extracts text. Vision AI provides cross-validation. Finally, our validation agent checks for conflicts."

**HIGHLIGHT:**
- Briefly show the LangGraph workflow diagram overlay (optional)

### C. Dashboard Results (30 sec)

**VISUAL:**
- Dashboard loads with metrics
- Pan through sections:
  - **Confidence: 95.2%** (large, prominent)
  - **Regions Extracted: 47** 
  - **Conflicts: 0** (green badge)
- Show extracted data table with invoice details
- Expand a region to show bbox overlay on document

**NARRATION:**
> "The dashboard presents comprehensive results: overall confidence, extracted regions, and any conflicts detected. For this clean document, we achieved 95% confidence with zero conflicts - ready for automated processing."

**HIGHLIGHT:**
- Point to "Save to Knowledge Base" button
- Click and show success message

---

## Scene 3: The Edge Case - Challenging Document (75 seconds)

### A. Upload Challenging Document (10 sec)

**VISUAL:**
- Upload a blurry, skewed scan (handwritten invoice or low-quality receipt)
- Show file preview with visible quality issues

**NARRATION:**
> "Real-world documents aren't always perfect. Let's test with a challenging scan - low resolution, handwriting, and skew."

### B. Graceful Degradation in Action (35 sec)

**VISUAL:**
- Processing starts
- Show "System Monitor" warning sidebar:
  - ⚠️ "Low confidence detected - engaging fallback"
  - ⚠️ "Using OCR-only mode due to resource constraints"
- Processing completes

**NARRATION:**
> "The system adapts automatically. When quality is low, it engages fallback strategies. The health monitor detected resource pressure and switched to OCR-only mode to ensure completion."

### C. Conflict Resolution (30 sec)

**VISUAL:**
- Dashboard shows: **Confidence: 67.3%** (yellow)
- **Conflicts: 3** (yellow badge)
- Expand conflict details panel:
  ```
  Conflict 1: Invoice Total
    OCR:    "$1,234.56"
    Vision: "$1,234.50"
    Similarity: 71%
  ```
- Show user can manually resolve

**NARRATION:**
> "When OCR and Vision agents disagree, conflicts are flagged. The user can review and resolve them manually - perfect for critical documents that require human validation."

**HIGHLIGHT:**
- Click "Mark as Resolved" on a conflict
- Show updated confidence score

---

## Scene 4: The Cloud Brain - Hybrid Architecture (60 seconds)

### A. Colab Setup (25 sec)

**VISUAL:**
- Split screen: Local app on left, Google Colab on right
- In Colab: `sovereign_brain.ipynb` is running
- Show ngrok tunnel output:
  ```
  Public URL: https://xxxx-xx-xx.ngrok-free.app
  Running on GPU: Tesla T4
  ```

**NARRATION:**
> "Need more power? Sovereign-Doc supports a hybrid architecture. Run the Vision Brain in Google Colab - free GPU, zero infrastructure cost. An encrypted tunnel secures the connection."

### B. Token Authentication (15 sec)

**VISUAL:**
- Show `config.yaml` on local machine:
  ```yaml
  llm:
    base_url: "https://xxxx.ngrok-free.app"
  ```
- Show Colab secrets with `ACCESS_TOKEN` set

**NARRATION:**
> "Security is built-in: token-based authentication ensures only your local body can talk to your cloud brain. Zero trust architecture."

### C. Vision in Action (20 sec)

**VISUAL:**
- Process a document with charts/graphs
- Show Vision Agent result highlighting detected charts
- Dashboard shows enriched metadata

**NARRATION:**
> "The Vision Agent runs on the T4 GPU, analyzing charts, signatures, and complex layouts - capabilities that would be cost-prohibitive to run locally for many users."

---

## Scene 5: RAG & Memory - Query Your Documents (45 seconds)

### A. Build Knowledge Base (15 sec)

**VISUAL:**
- Process 3 documents quickly (show cache hits for 2nd/3rd)
- Each document saved to Qdrant
- Show knowledge base count: "3 documents indexed"

**NARRATION:**
> "Processed documents are automatically indexed to Qdrant. Notice the speed - cached results mean reprocessing is instant."

### B. Natural Language Query (30 sec)

**VISUAL:**
- Show query interface (or use terminal if not in UI)
- Type: "What was the total invoice amount from Acme Corp?"
- Show RAG retrieval:
  - Search vector store
  - Retrieve relevant chunks
  - LLM generates answer
- Display: 
  ```
  Answer: The invoice from Acme Corp dated 2024-01-15 
  totaled $1,234.56 for consulting services.
  
  Source: invoice_acme_20240115.pdf, Page 1
  ```

**NARRATION:**
> "Query your entire document corpus with natural language. The RAG system retrieves relevant context and generates accurate answers with citations."

**HIGHLIGHT:**
- Show the similarity scores in search results
- Emphasize source citation

---

## Scene 6: Performance & Monitoring (30 seconds)

### A. System Monitor (15 sec)

**VISUAL:**
- Show sidebar metrics:
  - RAM: 6.2 / 16 GB (39%)
  - CPU: 45%
  - Temp: 62°C
  - Status: ✅ Healthy
- Show "Clean Memory" button action
- RAM drops to 4.1 GB

**NARRATION:**
> "Built-in health monitoring tracks resources in real-time. One-click memory cleanup keeps the system running smoothly even on modest hardware."

### B. Cache Statistics (15 sec)

**VISUAL:**
- Show cache stats (or run `cache.get_stats()` in console):
  ```
  Cache Hit Rate: 67%
  Total Hits: 8
  Size: 124 MB
  Entries: 12
  ```

**NARRATION:**
> "Intelligent caching delivers 50x speedups on repeated documents. The system learns and optimizes automatically."

---

## Scene 7: Benchmarks & Validation (30 seconds)

**VISUAL:**
- Terminal: Run `python scripts/validate_release.py`
- Show validation pipeline progress:
  ```
  ✅ Environment Check: PASS
  ✅ Integration Tests: PASS (8/8)
  ✅ Security Audit: PASS
  ✅ Benchmarks: PASS
  ✅ Compliance: PASS (16/16)
  
  ✅ RELEASE CANDIDATE READY
  ```
- Briefly show benchmark visualizations (charts)

**NARRATION:**
> "Production quality is validated continuously. Automated benchmarks measure accuracy, integration tests verify functionality, and compliance checks ensure all requirements are met."

**HIGHLIGHT:**
- Flash `compliance_matrix.md` showing 100% pass rate

---

## Closing: Key Features Recap (30 seconds)

**VISUAL:**
- Montage of features with text overlays:

**NARRATION:**
> "Sovereign-Doc delivers enterprise features with zero cost:

✅ **100% Local** - Your data never leaves your machine  
✅ **Multi-Agent Pipeline** - Layout, OCR, Vision, Validation  
✅ **Hybrid Cloud** - Optional GPU acceleration via Colab  
✅ **RAG Search** - Query your document library  
✅ **Production Ready** - Benchmarked, tested, validated  
✅ **Resource Aware** - Adaptive performance on any hardware  

All free. All open-source. All sovereign."

**VISUAL:**
- Logo + GitHub URL
- Fade to black

**END SCREEN:**
```
Sovereign-Doc
Privacy-First Document Intelligence

GitHub: github.com/yourusername/sovereign-doc
Docs: /docs
License: MIT

Built with LangGraph, Qdrant, PaddleOCR
```

---

## Production Notes

### Recording Tips

1. **Screen Resolution:** 1920x1080 minimum
2. **Terminal Font:** Use a large, readable font (16pt+)
3. **Cursor Highlighting:** Enable cursor highlight for visibility
4. **Slow Down:** Commands should be typed slowly or appear character-by-character
5. **Clean Desktop:** Minimal distractions, dark theme throughout

### Required Assets

- ✅ Clean invoice PDF (professional, typed text)
- ✅ Challenging document (blurry, handwritten, or skewed)
- ✅ Document with charts/graphs (for vision demo)
- ✅ Background music (subtle, non-distracting)
- ✅ Logo/brand assets
- ✅ Workflow diagram (optional for overlay)

### Editing Notes

- **Pace:** Keep moving - 5 min max total runtime
- **Cuts:** Cut out long processing waits (use time-lapse or progress bar)
- **Callouts:** Use arrows/highlights to draw attention to key features
- **Music:** Fade out during narration, subtle background otherwise
- **Captions:** Add for key technical terms
- **Thumbnails:** Create 3-5 freeze frames for YouTube thumbnail options

### Test Run Checklist

- [ ] Docker running (Qdrant accessible)
- [ ] Colab notebook pre-warmed (avoid cold start)
- [ ] Sample documents staged
- [ ] Cache cleared (for clean demo)
- [ ] Logs configured (INFO level, not DEBUG)
- [ ] Screen recording software tested
- [ ] Audio levels verified
- [ ] Dry run completed

---

## Alternative: Quick 2-Minute Version

For social media or quick demos:

**1. Setup (15 sec)** - Docker + Streamlit launch  
**2. Upload & Process (30 sec)** - One clean document  
**3. Dashboard (30 sec)** - Results overview  
**4. Hybrid Mode (20 sec)** - Colab connection demo  
**5. Features Flash (25 sec)** - Key capabilities montage

**Total:** 2 minutes

---

**End of Script**
