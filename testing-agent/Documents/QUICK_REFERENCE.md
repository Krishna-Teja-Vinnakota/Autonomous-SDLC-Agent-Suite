# Quick Reference - AutoSDLC Test Agent

## 🚀 Getting Started

### Basic Usage (No AI)
```bash
# Install
pip install -r requirements.txt

# Run
streamlit run app.py

# Upload project and analyze!
```

### With AI Analysis
```bash
# Configure
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json

# Test
python test_vertex_ai.py

# Run
streamlit run app.py
```

---

## 📁 Project Structure

```
AutoSDLC-Test-Agent/
├── app.py                    # Main Streamlit app
├── config/
│   └── vertex_ai.py         # Vertex AI integration
├── agents/
│   └── analyze_agent.py     # Project analysis agent
├── tools/
│   ├── git_tool.py          # GitHub cloning
│   ├── unzip_tool.py        # ZIP extraction
│   ├── file_indexer.py      # File analysis
│   └── config.py            # Configuration
├── test_vertex_ai.py        # AI tests
└── validate.py              # System tests
```

---

## 🔑 Key Commands

### Testing
```bash
# Validate system
python validate.py

# Test Vertex AI
python test_vertex_ai.py

# Run app
streamlit run app.py
```

### Configuration
```bash
# Copy env template
cp config.env.example .env

# Edit configuration
nano .env
```

---

## 🎯 Input Methods

| Method | Use Case | Command |
|--------|----------|---------|
| **GitHub** | Public repos | Enter URL in UI |
| **ZIP** | Compressed projects | Upload .zip file |
| **Folder** | Multiple files | Select all files |
| **Single File** | Quick test | Upload one file |

---

## 🤖 AI Analysis Output

### What You Get
- ✅ **Languages:** JavaScript, TypeScript, Python, etc.
- ✅ **Frameworks:** React, Node.js, Django, Flask, etc.
- ✅ **Test Setup:** Jest, Pytest, coverage assessment
- ✅ **Summary:** Intelligent project description
- ✅ **Confidence:** High/Medium/Low scoring

### What's Sent to AI
- ❌ **NOT sent:** Full source code
- ✅ **Sent:** File names, structure, extensions
- ✅ **Sent:** Small config files (< 2KB, truncated)
- ✅ **Sent:** Statistics (file counts, lines, etc.)

---

## ⚙️ Environment Variables

### Required (for AI)
```bash
GOOGLE_CLOUD_PROJECT           # Your GCP project ID
GOOGLE_APPLICATION_CREDENTIALS # Path to credentials.json
```

### Optional
```bash
GOOGLE_CLOUD_REGION=us-central1           # GCP region
VERTEX_AI_MODEL=gemini-1.5-flash          # Model name
VERTEX_AI_TEMPERATURE=0.3                 # 0.0-2.0
VERTEX_AI_MAX_TOKENS=2048                 # Output limit
```

---

## 🐛 Troubleshooting

### "Vertex AI not configured"
```bash
# Check env vars
echo $GOOGLE_CLOUD_PROJECT
echo $GOOGLE_APPLICATION_CREDENTIALS

# Test config
python test_vertex_ai.py
```

### "Credentials file not found"
```bash
# Use absolute path
export GOOGLE_APPLICATION_CREDENTIALS=/full/path/to/creds.json

# Verify file exists
ls -l $GOOGLE_APPLICATION_CREDENTIALS
```

### "Permission denied" / "403 Forbidden"
```bash
# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:your-sa@project.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### Port already in use
```bash
# Use different port
streamlit run app.py --server.port=8502
```

---

## 💰 Cost Estimates

| Project Size | Files | Est. Cost |
|--------------|-------|-----------|
| Small | 50 | $0.01-0.02 |
| Medium | 500 | $0.05-0.10 |
| Large | 5000 | $0.20-0.50 |

*Using gemini-1.5-flash model*

---

## 📊 File Categories

| Category | Extensions |
|----------|-----------|
| Python | `.py` |
| JavaScript | `.js`, `.jsx` |
| TypeScript | `.ts`, `.tsx` |
| Test | `.test.js`, `.spec.ts` |
| Config | `.json`, `.yaml`, `.toml` |
| Documentation | `.md`, `.rst` |

---

## 🔒 Security Checklist

- [ ] Credentials in `.env` (not hardcoded)
- [ ] `.env` in `.gitignore`
- [ ] Service account with minimal permissions
- [ ] Credentials file outside repository
- [ ] Regular key rotation

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| `README.md` | Main documentation |
| `QUICKSTART.md` | 5-minute setup |
| `INSTALLATION.md` | Detailed install |
| `VERTEX_AI_SETUP.md` | AI configuration |
| `PHASE2_SUMMARY.md` | Latest features |
| `PROJECT_STRUCTURE.md` | Architecture |

---

## 🎓 Common Tasks

### Add New Language Support
Edit `tools/file_indexer.py` → `CATEGORY_MAP`

### Change AI Model
Edit `.env` → `VERTEX_AI_MODEL=gemini-1.5-pro`

### Adjust AI Temperature
Edit `.env` → `VERTEX_AI_TEMPERATURE=0.5` (higher = more creative)

### View Logs
Check terminal output where `streamlit run app.py` is running

---

## 📞 Quick Help

### Test Everything
```bash
python validate.py          # System validation
python test_vertex_ai.py    # AI validation
streamlit run app.py        # Start app
```

### Reset Session
Click "🔄 Reset Session" in sidebar

### View Status
Check "Processing Status" section in UI

---

## ✅ Quick Validation

```bash
# 1. System ready?
python validate.py
# Expected: 6/6 tests passed

# 2. AI ready? (optional)
python test_vertex_ai.py
# Expected: 6/6 tests passed

# 3. Run app
streamlit run app.py
# Expected: Opens in browser

# 4. Upload project
# Expected: Analysis appears automatically
```

---

## 🔗 Useful Links

- **Vertex AI Console:** https://console.cloud.google.com/vertex-ai
- **API Library:** https://console.cloud.google.com/apis/library
- **Billing:** https://console.cloud.google.com/billing
- **Gemini Docs:** https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini

---

**Need more help?** See full documentation in respective .md files!

---

*AutoSDLC Test Agent - Quick Reference v2.0*

