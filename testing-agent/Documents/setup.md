# Complete Setup Guide

Comprehensive setup instructions for AutoSDLC Test Agent with LangGraph-style orchestration.

---

## 📋 Prerequisites

### **Required**

- **Python 3.9+**
  - Download: https://www.python.org/downloads/
  - Verify: `python --version`

- **Node.js & npm** (for Jest tests)
  - Download: https://nodejs.org/
  - Verify: `node --version` and `npm --version`

- **Git** (optional, for GitHub cloning)
  - Download: https://git-scm.com/downloads
  - Verify: `git --version`

### **Optional (for AI features)**

- **Google Cloud Account** (for Vertex AI Gemini)
- **Service Account Credentials** (JSON file)

---

## 🚀 Installation

### **Step 1: Clone/Download Project**

```bash
cd "path/to/AutoSDLC-Test-Agent"
```

### **Step 2: Create Virtual Environment**

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### **Step 3: Install Dependencies**

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `streamlit` - UI framework
- `plotly` - Visualizations
- `google-cloud-aiplatform` - Vertex AI
- `GitPython` - Git operations
- `pytest` - Python testing

### **Step 4: Verify Installation**

```bash
python validate.py
```

Expected: `6/6 tests passed`

---

## ⚙️ Configuration

### **Basic Configuration (No AI)**

The system works without AI configuration for basic operations:

```bash
# No configuration needed!
streamlit run app.py
```

### **AI Configuration (Optional)**

For AI-powered analysis and test generation:

**1. Set Environment Variables:**

**Windows (PowerShell):**
```powershell
$env:GOOGLE_CLOUD_PROJECT="your-project-id"
$env:GOOGLE_CLOUD_REGION="us-central1"
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\credentials.json"
```

**macOS/Linux:**
```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_REGION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

**2. Test Configuration:**

```bash
python test_vertex_ai.py
```

Expected: `6/6 tests passed`

**3. Get Credentials:**

See `VERTEX_AI_SETUP.md` for detailed instructions.

---

## 🎯 Quick Start

### **1. Launch Application**

```bash
streamlit run app.py
```

Opens at: `http://localhost:8501`

### **2. Upload Project**

Choose one:
- **GitHub Repository** - Enter URL
- **ZIP Upload** - Upload `.zip` file
- **Folder Upload** - Select multiple files
- **Single File** - Upload one file

### **3. Run Full Workflow**

Click **"🚀 Run Full Workflow"** button

**Workflow Stages:**
1. 📁 **Indexing** - Analyze project structure
2. 🤖 **Analyzing** - AI-powered analysis (if configured)
3. 🎯 **Strategizing** - Determine test strategy
4. ✍️ **Generating** - Generate test files
5. 🏃 **Executing** - Run tests
6. 📊 **Reporting** - Generate reports

### **4. View Results**

- **Unified Report** - Summary with visualizations
- **Coverage Charts** - Interactive Plotly charts
- **Test Cases** - Individual test results
- **Download Reports** - JSON & HTML

---

## 🔧 Advanced Configuration

### **Workflow Settings**

Edit `workflows/langgraph_flow.py`:

```python
# Timeout settings
MAX_EXECUTION_TIME = 300.0  # 5 minutes per test
WORKFLOW_TIMEOUT = 1800.0    # 30 minutes overall

# Retry settings
MAX_RETRIES = 3              # Max retries per stage
```

### **Security Settings**

Edit `tools/command_executor.py`:

```python
# Command allowlist
ALLOWED_COMMANDS = {
    'npx': ['npx'],
    'npm': ['npm'],
    'pytest': ['pytest'],
    'python': ['python'],
}

# Timeout
DEFAULT_TIMEOUT = 300  # 5 minutes
```

### **Coverage Settings**

**Jest (`package.json`):**
```json
{
  "jest": {
    "collectCoverage": true,
    "coverageDirectory": "coverage",
    "coverageReporters": ["json", "html"]
  }
}
```

**Pytest (`pytest.ini`):**
```ini
[tool:pytest]
addopts = --cov=. --cov-report=json
```

---

## 🏗️ Project Structure

```
AutoSDLC-Test-Agent/
├── app.py                      # Streamlit UI
├── workflows/
│   └── langgraph_flow.py      # Workflow orchestration
├── agents/
│   ├── analyze_agent.py       # Project analysis
│   ├── strategy_agent.py      # Test strategy
│   ├── test_generator_agent.py # Test generation
│   ├── test_executor_agent.py  # Test execution
│   ├── failure_analyzer_agent.py # Failure analysis
│   └── report_agent.py        # Report generation
├── tools/
│   ├── git_tool.py            # Git operations
│   ├── unzip_tool.py          # ZIP handling
│   ├── file_indexer.py        # File analysis
│   ├── command_executor.py    # Safe command execution
│   └── coverage_parser.py     # Coverage parsing
├── config/
│   └── vertex_ai.py           # Vertex AI config
└── workspaces/                # Sandboxed runs
    └── run_<uuid>/
        └── project/
```

---

## 🔒 Security Features

### **Implemented**

- ✅ **Command allowlist** - Only approved commands
- ✅ **No shell=True** - Prevents injection
- ✅ **Timeout protection** - Prevents hangs
- ✅ **Retry limits** - Prevents loops
- ✅ **Sandboxing** - Isolated execution
- ✅ **Input validation** - Safe inputs
- ✅ **Path sanitization** - No traversal
- ✅ **Resource limits** - Prevents DoS

### **Architecture**

- ✅ **UI never executes code directly**
- ✅ **All execution through workflow**
- ✅ **Shared state management**
- ✅ **Retry guards**
- ✅ **Cleanup logic**

See `SECURITY.md` for details.

---

## 📊 Workflow Stages

### **Stage 1: Indexing**
- Analyzes project structure
- Categorizes files
- Counts lines of code
- **Required:** Yes

### **Stage 2: Analyzing**
- AI-powered language detection
- Framework identification
- Test setup analysis
- **Required:** No (optional)

### **Stage 3: Strategizing**
- Determines test strategy
- Identifies testable files
- Assigns priorities
- **Required:** No (optional)

### **Stage 4: Generating**
- Generates Jest tests
- Generates Pytest tests
- Saves test files
- **Required:** No (optional)

### **Stage 5: Executing**
- Runs Jest tests
- Runs Pytest tests
- Captures results
- **Required:** No (optional)

### **Stage 6: Reporting**
- Generates unified report
- Creates visualizations
- Saves JSON/HTML
- **Required:** No (optional)

---

## 🐛 Troubleshooting

### **"Command not allowed"**

**Cause:** Command not in allowlist

**Solution:**
- Check `tools/command_executor.py`
- Verify command is in `ALLOWED_COMMANDS`
- Add to allowlist if needed (with caution)

### **"Workflow timeout"**

**Cause:** Execution exceeded 30 minutes

**Solution:**
- Reduce test scope
- Optimize slow tests
- Increase timeout (if safe)

### **"Max retries exceeded"**

**Cause:** Stage failed 3 times

**Solution:**
- Check error messages
- Fix underlying issues
- Review logs

### **"npx not found"**

**Cause:** Node.js not installed

**Solution:**
```bash
# Install Node.js
# https://nodejs.org/

# Verify
npx --version
```

### **"pytest not found"**

**Cause:** pytest not installed

**Solution:**
```bash
pip install pytest
pytest --version
```

---

## 📈 Performance Tips

### **Optimize Workflow**

1. **Limit test generation:**
   - Default: 10 files
   - Adjust in workflow

2. **Use coverage selectively:**
   - Only when needed
   - Increases execution time

3. **Configure timeouts:**
   - Match your test duration
   - Prevent unnecessary waits

### **Resource Management**

1. **Cleanup workspaces:**
   - Old runs accumulate
   - Delete periodically

2. **Monitor disk usage:**
   - Workspaces can grow
   - Clean up regularly

3. **Limit concurrent runs:**
   - One workflow at a time
   - Prevents resource contention

---

## ✅ Verification Checklist

### **Installation**

- [ ] Python 3.9+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `python validate.py` passes

### **Configuration**

- [ ] Environment variables set (if using AI)
- [ ] Credentials file exists (if using AI)
- [ ] `python test_vertex_ai.py` passes (if using AI)

### **Runtime**

- [ ] Application launches
- [ ] Can upload projects
- [ ] Workflow executes
- [ ] Reports generate
- [ ] Downloads work

---

## 🎓 Next Steps

1. **Read Documentation:**
   - `README.md` - Overview
   - `QUICKSTART.md` - Quick start
   - `SECURITY.md` - Security details

2. **Try Examples:**
   - Upload a small project
   - Run full workflow
   - Review reports

3. **Customize:**
   - Adjust timeouts
   - Configure coverage
   - Customize reports

---

## 📚 Documentation

- **Main:** `README.md`
- **Quick Start:** `QUICKSTART.md`
- **Installation:** `INSTALLATION.md`
- **Security:** `SECURITY.md`
- **Vertex AI:** `VERTEX_AI_SETUP.md`
- **Test Generation:** `TEST_GENERATION_GUIDE.md`
- **Test Execution:** `TEST_EXECUTION_GUIDE.md`
- **Coverage:** `COVERAGE_AND_REPORTING.md`

---

**Setup Complete!** 🎉

Run `streamlit run app.py` to get started!

