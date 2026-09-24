# Vertex AI Gemini Setup Guide

Complete guide to configuring Vertex AI Gemini for intelligent project analysis.

---

## Overview

The AutoSDLC Test Agent uses Google's Vertex AI Gemini to provide intelligent analysis of your projects, detecting:
- **Programming Languages** (JavaScript, TypeScript, Python, etc.)
- **Frameworks** (React, Node.js, Express, Django, Flask, etc.)
- **Test Setup** (Jest, Pytest, existing test files, coverage)

---

## Prerequisites

### 1. Google Cloud Account
- Active Google Cloud account
- Billing enabled (Vertex AI requires billing)
- Project created

### 2. Enable APIs
Enable the following APIs in your Google Cloud project:
- Vertex AI API
- Cloud AI Platform API

**Enable via Console:**
```
https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
```

**Enable via gcloud CLI:**
```bash
gcloud services enable aiplatform.googleapis.com
```

### 3. Service Account Setup

Create a service account with Vertex AI permissions:

```bash
# Set your project ID
export PROJECT_ID=your-project-id

# Create service account
gcloud iam service-accounts create autosdlc-agent \
    --display-name="AutoSDLC Test Agent" \
    --project=$PROJECT_ID

# Grant Vertex AI User role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:autosdlc-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Create and download key
gcloud iam service-accounts keys create ~/autosdlc-credentials.json \
    --iam-account=autosdlc-agent@${PROJECT_ID}.iam.gserviceaccount.com
```

---

## Configuration

### Step 1: Set Environment Variables

**Option A: Using .env file (Recommended)**

Create a `.env` file in the project root:

```bash
# Copy example
cp config.env.example .env

# Edit .env file
nano .env
```

Set the following variables:

```ini
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/autosdlc-credentials.json

# Model Configuration
VERTEX_AI_MODEL=gemini-1.5-flash
VERTEX_AI_TEMPERATURE=0.3
VERTEX_AI_MAX_TOKENS=2048
```

**Option B: Export in shell**

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_REGION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/autosdlc-credentials.json
```

**Windows (PowerShell):**
```powershell
$env:GOOGLE_CLOUD_PROJECT="your-project-id"
$env:GOOGLE_CLOUD_REGION="us-central1"
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\autosdlc-credentials.json"
```

### Step 2: Verify Configuration

Run the test script:

```bash
python test_vertex_ai.py
```

Expected output:
```
[PASS] - Configuration Check
[PASS] - Import Test
[PASS] - VertexAIConfig Test
[PASS] - GeminiClient Test
[PASS] - Content Generation Test
[PASS] - AnalyzeAgent Structure Test

Results: 6/6 tests passed
[SUCCESS] All tests passed!
```

---

## Model Selection

### Available Models

| Model | Use Case | Speed | Cost |
|-------|----------|-------|------|
| `gemini-1.5-flash` | Fast analysis (Recommended) | Very Fast | Lower |
| `gemini-1.5-pro` | Complex analysis | Moderate | Higher |
| `gemini-pro` | Legacy support | Moderate | Moderate |

**Recommendation:** Use `gemini-1.5-flash` for project analysis (default).

### Model Configuration

Adjust model parameters in `.env`:

```ini
# Model selection
VERTEX_AI_MODEL=gemini-1.5-flash

# Temperature (0.0-2.0): Lower = more focused, Higher = more creative
VERTEX_AI_TEMPERATURE=0.3

# Max output tokens
VERTEX_AI_MAX_TOKENS=2048

# Top-p sampling (0.0-1.0)
VERTEX_AI_TOP_P=0.95

# Top-k sampling
VERTEX_AI_TOP_K=40
```

---

## Usage

### In Streamlit UI

1. **Start the application:**
   ```bash
   streamlit run app.py
   ```

2. **Upload a project** (GitHub, ZIP, Folder, or File)

3. **Automatic Analysis:**
   - If Vertex AI is configured, analysis runs automatically
   - Results display in "🤖 AI-Powered Analysis" section

4. **View Results:**
   - Languages detected
   - Frameworks identified
   - Test setup analysis
   - Confidence level
   - Summary

### What Gets Analyzed

The agent sends **file summaries only** (not full content) including:
- File structure and names
- File extensions and categories
- Config file contents (package.json, requirements.txt, etc.)
- Number of test files
- Lines of code statistics

**Privacy:** Your actual source code is NOT sent to the LLM, only metadata.

---

## Troubleshooting

### Error: "GOOGLE_CLOUD_PROJECT not set"

**Solution:**
```bash
export GOOGLE_CLOUD_PROJECT=your-actual-project-id
```

Verify:
```bash
echo $GOOGLE_CLOUD_PROJECT
```

### Error: "Credentials file not found"

**Solution:**
1. Verify file path is correct
2. Use absolute path
3. Check file permissions

```bash
# Verify file exists
ls -l /path/to/credentials.json

# Use absolute path
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"
```

### Error: "Permission denied" or "403 Forbidden"

**Cause:** Service account lacks permissions

**Solution:**
```bash
# Grant Vertex AI User role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:autosdlc-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

### Error: "Vertex AI API not enabled"

**Solution:**
```bash
gcloud services enable aiplatform.googleapis.com --project=$PROJECT_ID
```

Or enable via Console:
https://console.cloud.google.com/apis/library/aiplatform.googleapis.com

### Error: "Region not supported"

**Solution:** Use a supported region:
- `us-central1` (recommended)
- `us-east1`
- `us-west1`
- `europe-west1`
- `asia-northeast1`

```bash
export GOOGLE_CLOUD_REGION=us-central1
```

### Application works but no AI analysis

**Check if configured:**
- Look for "Checking Vertex AI Gemini availability..." in status
- If warning appears: "Vertex AI not configured - skipping AI analysis"

**Solution:**
1. Verify all environment variables are set
2. Restart Streamlit application
3. Run `python test_vertex_ai.py`

---

## Cost Management

### Pricing

Vertex AI Gemini pricing (as of 2024):
- **Input:** ~$0.00025 per 1K characters
- **Output:** ~$0.0005 per 1K characters

**Typical Analysis Cost:**
- Small project (50 files): ~$0.01-0.02
- Medium project (500 files): ~$0.05-0.10
- Large project (5000 files): ~$0.20-0.50

### Cost Optimization

1. **Use gemini-1.5-flash** (faster and cheaper)
2. **File summaries only** (no full content sent)
3. **Smart config file limits** (only reads small config files)
4. **Token limits** configured to 2048 (adjustable)

### Monitor Usage

Check usage in Google Cloud Console:
```
https://console.cloud.google.com/billing
```

Set budget alerts:
```
https://console.cloud.google.com/billing/budgets
```

---

## Security Best Practices

### 1. Credentials Management

**✅ DO:**
- Store credentials outside repository
- Use `.env` file (in `.gitignore`)
- Use service account with minimal permissions
- Rotate keys periodically

**❌ DON'T:**
- Commit credentials to Git
- Share credentials publicly
- Use personal account credentials
- Give excessive permissions

### 2. Service Account Permissions

**Minimum Required:**
- `roles/aiplatform.user` - Use Vertex AI models

**Optional (for monitoring):**
- `roles/monitoring.viewer` - View metrics

### 3. API Key Rotation

Rotate service account keys regularly:

```bash
# Create new key
gcloud iam service-accounts keys create new-key.json \
    --iam-account=autosdlc-agent@${PROJECT_ID}.iam.gserviceaccount.com

# Update GOOGLE_APPLICATION_CREDENTIALS
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/new-key.json

# Delete old key
gcloud iam service-accounts keys delete OLD_KEY_ID \
    --iam-account=autosdlc-agent@${PROJECT_ID}.iam.gserviceaccount.com
```

---

## Advanced Configuration

### Custom Generation Config

Modify `config/vertex_ai.py` for advanced control:

```python
# Lower temperature for more deterministic results
VERTEX_AI_TEMPERATURE=0.1

# Higher token limit for detailed analysis
VERTEX_AI_MAX_TOKENS=4096

# Adjust sampling parameters
VERTEX_AI_TOP_P=0.9
VERTEX_AI_TOP_K=20
```

### Custom Analysis Prompts

Modify `agents/analyze_agent.py` method `_build_analysis_prompt()` to customize analysis focus.

### Regional Endpoints

For better performance, use nearest region:

```bash
# US
GOOGLE_CLOUD_REGION=us-central1

# Europe
GOOGLE_CLOUD_REGION=europe-west1

# Asia
GOOGLE_CLOUD_REGION=asia-northeast1
```

---

## Verification Checklist

Before using Vertex AI features:

- [ ] Google Cloud project created
- [ ] Billing enabled
- [ ] Vertex AI API enabled
- [ ] Service account created
- [ ] Service account has `aiplatform.user` role
- [ ] Credentials JSON downloaded
- [ ] `GOOGLE_CLOUD_PROJECT` environment variable set
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` environment variable set
- [ ] Credentials file exists at specified path
- [ ] `python test_vertex_ai.py` passes all tests
- [ ] Streamlit app shows AI analysis results

---

## Example Output

When configured correctly, you'll see:

```
🤖 AI-Powered Analysis (Gemini)

Confidence: 🟢 HIGH

Summary:
This is a React-based web application with TypeScript. It uses Jest for testing 
and has a well-structured component hierarchy. The project includes API integration 
and state management.

🔤 Languages Detected:          ⚙️ Frameworks Detected:
- TypeScript                    - React
- JavaScript                    - Node.js
- CSS                          - Express

🧪 Test Setup:
Tests Present: Yes ✓
Test Files: 24
Coverage: Medium

Test Frameworks:
- Jest
- React Testing Library
```

---

## Support

### Documentation
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini API Reference](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
- [Service Accounts Guide](https://cloud.google.com/iam/docs/service-accounts)

### Common Resources
- [Google Cloud Console](https://console.cloud.google.com)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
- [API Library](https://console.cloud.google.com/apis/library)

---

**Ready to analyze!** 🤖

Run `python test_vertex_ai.py` to verify your setup, then `streamlit run app.py` to start analyzing projects!

