# Colab Brain Setup Guide

**Sovereign-Doc Hybrid Architecture:** Run the UI locally while leveraging Google Colab's free T4 GPU for heavy AI workloads.

---

## Why Use Colab Brain?

### The Problem
- Vision models (GPT-4V, LLaVA) require powerful GPUs
- Running them locally needs expensive hardware (RTX 3090+)
- Cloud APIs cost money ($0.02-0.05 per request)

### The Solution
- **Local Body:** Your computer runs the UI, orchestration, and lightweight OCR
- **Colab Brain:** Google Colab provides FREE T4 GPU for vision analysis and LLMs
- **Secure Tunnel:** ngrok connects the two via HTTPS

### Benefits
✅ **Zero Cost:** Uses Google Colab's free tier  
✅ **High Performance:** T4 GPU for vision models  
✅ **Privacy:** Your PDFs never leave your machine (only text queries sent to Colab)  
✅ **Scalable:** Upgrade to Colab Pro for faster GPUs  

---

## Architecture Overview

```
┌─────────────────────────┐         ┌──────────────────────────┐
│   YOUR COMPUTER         │         │   GOOGLE COLAB           │
│   (Local Body)          │         │   (Cloud Brain)          │
│                         │         │                          │
│  ┌──────────────────┐   │         │  ┌───────────────────┐   │
│  │  Streamlit UI    │   │         │  │  Vision Model     │   │
│  │  (Upload PDFs)   │   │         │  │  (LLaVA/GPT-4V)   │   │
│  └──────────────────┘   │         │  └───────────────────┘   │
│           │             │         │           ▲              │
│           ▼             │         │           │              │
│  ┌──────────────────┐   │         │  ┌───────────────────┐   │
│  │ DocumentWorkflow │───┼────────▶│  │  FastAPI Server   │   │
│  │  (Orchestrator)  │   │  HTTPS  │  │  (port 8000)      │   │
│  └──────────────────┘   │         │  └───────────────────┘   │
│           │             │         │           ▲              │
│           ▼             │         │           │              │
│  ┌──────────────────┐   │         │  ┌───────────────────┐   │
│  │  Qdrant Vector   │   │         │  │  ngrok Tunnel     │   │
│  │  Database        │   │         │  │  (Public URL)     │   │
│  └──────────────────┘   │         │  └───────────────────┘   │
└─────────────────────────┘         └──────────────────────────┘
```

---

## Setup Steps

### Prerequisites

- Google account (for Colab)
- ngrok account (free tier: https://dashboard.ngrok.com/signup)
- Sovereign-Doc installed locally (see [Installation Guide](INSTALLATION.md))

---

### Step 1: Get ngrok Auth Token

1. Sign up for ngrok: https://dashboard.ngrok.com/signup
2. Navigate to "Your Authtoken" page
3. Copy your token (looks like: `2abC123dEF...`)
4. **Keep this secret!** Do not commit to Git

---

### Step 2: Upload Notebook to Colab

1. Go to Google Colab: https://colab.research.google.com/
2. Click **File → Upload notebook**
3. Upload `notebooks/sovereign_brain.ipynb` from your local repository
4. **Alternatively:** Use the direct link if provided:
   ```
   https://colab.research.google.com/github/yourusername/sovereign-doc/blob/main/notebooks/sovereign_brain.ipynb
   ```

---

### Step 3: Set ngrok Token in Colab

1. In the Colab notebook, click the **🔑 Secrets** tab (left sidebar)
2. Add a new secret:
   - **Name:** `NGROK_TOKEN`
   - **Value:** Your ngrok auth token from Step 1
3. **Enable** "Notebook access" toggle

---

### Step 4: Run the Colab Notebook

1. **Connect to Runtime:**
   - Click **Runtime → Change runtime type**
   - **Hardware accelerator:** T4 GPU (or better if on Colab Pro)
   - Click **Save**

2. **Run all cells:**
   - Click **Runtime → Run all**
   - Or press `Ctrl+F9`

3. **Wait for initialization:**
   The notebook will:
   - Install dependencies (~2-3 minutes)
   - Download vision models (~1-2 minutes)
   - Start FastAPI server
   - Create ngrok tunnel

4. **Copy the ngrok URL:**
   Look for output like:
   ```
   ✅ Server running at: https://1234-56-78-90-12.ngrok-free.app
   🔗 Tunnel active: https://1234-56-78-90-12.ngrok-free.app
   ```
   
   **Copy this URL!** You'll need it for the next step.

---

### Step 5: Update Local Configuration

1. Open `config.yaml` in your local Sovereign-Doc installation

2. Find the `llm:` section and update `base_url`:
   ```yaml
   llm:
     provider: "vllm"
     model: "llava-v1.6-mistral-7b"
     base_url: "https://1234-56-78-90-12.ngrok-free.app"  # ← Paste your ngrok URL
     max_tokens: 512
   ```

3. Save the file

---

### Step 6: Verify Connection

1. **Start your local Streamlit app:**
   ```bash
   streamlit run app.py
   ```

2. **Upload a test PDF**

3. **Click "Analyze Document"**

4. **Check Colab logs:**
   - You should see requests appearing in the Colab notebook output
   - Example log: `POST /v1/embeddings 200 OK`

5. **Check local dashboard:**
   - Vision results should appear
   - If you see "Connection Refused" → check ngrok URL in config.yaml

---

## Troubleshooting

### Issue: "Tunnel Disconnected"

**Cause:** Colab runtime disconnected or ngrok tunnel expired  
**Solution:**
1. Go back to Colab
2. Click "Reconnect" if disconnected
3. Re-run the ngrok cell (or all cells)
4. Copy the NEW ngrok URL
5. Update config.yaml with the new URL

### Issue: "CUDA Out of Memory"

**Cause:** T4 GPU has only 16GB VRAM  
**Solution:**
1. In Colab notebook, find the model loading cell
2. Add quantization:
   ```python
   model = AutoModel.from_pretrained(
       "llava-hf/llava-v1.6-mistral-7b-hf",
       load_in_8bit=True  # ← Add this
   )
   ```
3. Restart runtime and re-run

### Issue: "ngrok Free Plan Limits"

**Cause:** ngrok free tier has request limits  
**Solution:**
- Upgrade to ngrok Pro ($8/month for higher limits)
- Or: Use Colab Pro ($10/month) which has better stability
- Or: Switch to local GPU if available

### Issue: "Rate Limit: 429 Too Many Requests"

**Cause:** Colab has usage limits on free tier  
**Solution:**
1. Wait 1 hour for rate limit reset
2. Reduce document batch size in config.yaml:
   ```yaml
   processing:
     batch_size: 1  # Process one page at a time
   ```

---

## Advanced Configuration

### Use Colab Pro for Better Performance

Upgrade to Colab Pro ($10/month) for:
- **A100 GPU** (10x faster than T4)
- **Longer runtimes** (24 hours vs 12 hours)
- **Background execution** (stays running when tab closed)

To use A100:
1. Go to **Runtime → Change runtime type**
2. Select **A100 GPU**
3. Re-run notebook

### Custom Model in Colab

To use a different vision model:

1. In Colab notebook, find model loading:
   ```python
   # Original
   model_name = "llava-hf/llava-v1.6-mistral-7b-hf"
   
   # Change to:
   model_name = "liuhaotian/llava-v1.5-13b"  # Larger model
   ```

2. Update config.yaml to match:
   ```yaml
   llm:
     model: "llava-v1.5-13b"
   ```

### Persistent Storage in Colab

To cache models and avoid re-downloading:

1. In Colab, mount Google Drive:
   ```python
   from google.colab import drive
   drive.mount('/content/drive')
   ```

2. Change cache directory:
   ```python
   os.environ['HF_HOME'] = '/content/drive/MyDrive/hf_cache'
   ```

---

## Security Considerations

### What Data is Sent to Colab?

- ✅ **Sent:** Text queries, extracted text snippets
- ❌ **NOT Sent:** Original PDF files, images (unless explicitly for vision analysis)
- ✅ **Encrypted:** All traffic via HTTPS through ngrok

### Best Practices

1. **Never commit ngrok token to Git:**
   - Add to `.gitignore`
   - Use Colab secrets only

2. **Monitor Colab logs:**
   - Check what requests are being made
   - Verify no sensitive data in logs

3. **For ultra-sensitive documents:**
   - Use `processing: mode: ocr_only` (no external API calls)
   - Or deploy your own GPU server instead of Colab

---

## Monitoring & Maintenance

### Check Colab Status

The notebook prints health checks every 5 minutes:
```
✓ Server healthy | Requests: 42 | Uptime: 2h 15m
```

If status stops updating → runtime disconnected, click "Reconnect"

### Restart Colab Brain

If performance degrades:

1. **Restart runtime:**
   - Click **Runtime → Restart runtime**
   - Re-run all cells

2. **Factory reset runtime:**
   - Click **Runtime → Factory reset runtime**
   - This clears all state and re-downloads models

---

## Cost Comparison

| Option | Hardware | Cost | Performance |
|--------|----------|------|-------------|
| **Colab Free** | T4 GPU | $0/month | Good (10-15 sec/page) |
| **Colab Pro** | A100 GPU | $10/month | Excellent (2-3 sec/page) |
| **Local RTX 3080** | 10GB VRAM | $500 one-time | Great (5-8 sec/page) |
| **Local RTX 4090** | 24GB VRAM | $1500 one-time | Excellent (2-3 sec/page) |
| **Cloud APIs (OpenAI)** | GPT-4V | $0.03/page | Best (1-2 sec/page) |

**Recommendation:** Start with Colab Free, upgrade to Pro if needed, buy local GPU if processing >1000 docs/month.

---

## FAQ

**Q: How long does the Colab runtime last?**  
A: Free tier: 12 hours max. Pro tier: 24 hours. You'll need to reconnect and get a new ngrok URL after timeout.

**Q: Can I use Colab for batch processing?**  
A: Yes, but keep free tier limits in mind. Process ~100-200 pages before hitting rate limits.

**Q: Is my data private?**  
A: PDFs stay local. Only text queries go to Colab via HTTPS. Google may log requests.

**Q: Can I host the "brain" on my own server instead?**  
A: Yes! The notebook is just a FastAPI server. Deploy anywhere (AWS, Azure, your own GPU server).

---

## Next Steps

- ✅ **Optimize config for your setup:** [Configuration Guide](CONFIGURATION_GUIDE.md)
- ✅ **Troubleshoot common issues:** [Troubleshooting](TROUBLESHOOTING.md)
- ✅ **Process your first document:** [Installation Guide](INSTALLATION.md)
