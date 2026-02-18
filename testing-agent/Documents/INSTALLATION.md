# Installation Guide

Complete installation and setup guide for AutoSDLC Test Agent.

---

## Prerequisites

### Required
- **Python 3.9 or higher**
  - Download: https://www.python.org/downloads/
  - Verify: `python --version`

### Optional
- **Git** (for GitHub repository cloning)
  - Download: https://git-scm.com/downloads
  - Verify: `git --version`

### System Requirements
- **OS**: Windows 10+, macOS 10.14+, Linux (Ubuntu 18.04+)
- **RAM**: 2 GB minimum (4 GB recommended)
- **Disk Space**: 500 MB + space for projects
- **Internet**: Required for package installation and GitHub cloning

---

## Installation Methods

### Method 1: Automated Setup (Recommended)

1. **Navigate to project directory**
   ```bash
   cd "path/to/AutoSDLC-Test-Agent"
   ```

2. **Run setup script**
   ```bash
   python setup.py
   ```

   This will:
   - Check Python version
   - Check Git installation
   - Create necessary directories
   - Install all dependencies
   - Verify installation

3. **Run validation tests**
   ```bash
   python validate.py
   ```

   Expected output: `6/6 tests passed`

### Method 2: Manual Setup

1. **Create virtual environment** (recommended)

   **Windows (PowerShell/CMD):**
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

   **macOS/Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create workspace directories**
   ```bash
   mkdir workspaces
   mkdir temp
   ```

4. **Configure environment** (optional)
   ```bash
   cp config.env.example .env
   # Edit .env with your settings
   ```

5. **Verify installation**
   ```bash
   python validate.py
   ```

---

## Configuration

### Environment Variables

Copy the example configuration file:
```bash
cp config.env.example .env
```

Edit `.env` with your settings:

```ini
# Google Cloud (for future Vertex AI integration)
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Vertex AI
VERTEX_AI_MODEL=gemini-pro
VERTEX_AI_TEMPERATURE=0.7
VERTEX_AI_MAX_TOKENS=2048

# Application Limits
MAX_UPLOAD_SIZE_MB=500
MAX_EXTRACTED_SIZE_MB=1024
MAX_FILES_PER_ARCHIVE=10000

# Logging
LOG_LEVEL=INFO
```

**Note**: Environment variables are optional for Phase 1 (File Indexing).

---

## Running the Application

### Start Streamlit Server

```bash
streamlit run app.py
```

The application will open in your browser at:
```
http://localhost:8501
```

### Custom Port

```bash
streamlit run app.py --server.port=8080
```

### Debug Mode

```bash
streamlit run app.py --logger.level=debug
```

---

## Verification

### Quick Test

1. **Start the application**
   ```bash
   streamlit run app.py
   ```

2. **Test with a single file**
   - Select "Single File" input method
   - Upload any `.py`, `.js`, or `.ts` file
   - Click "Upload & Process"
   - Verify analytics are displayed

3. **Test with GitHub repository** (requires Git)
   - Select "GitHub Repository"
   - Enter: `https://github.com/octocat/Hello-World`
   - Click "Clone & Process"
   - Verify project is analyzed

### Validation Script

Run comprehensive tests:
```bash
python validate.py
```

Expected output:
```
[PASS] - Directory Structure
[PASS] - Module Imports
[PASS] - GitTool
[PASS] - UnzipTool
[PASS] - FileIndexer
[PASS] - Config

Results: 6/6 tests passed
[SUCCESS] All validation tests passed!
```

---

## Troubleshooting

### Python Version Issues

**Problem**: `Python 3.9+ required`

**Solution**:
1. Install Python 3.9 or higher from python.org
2. Use `python3` command instead of `python`
3. Create alias: `alias python=python3`

### Module Not Found

**Problem**: `ModuleNotFoundError: No module named 'streamlit'`

**Solution**:
```bash
# Ensure virtual environment is activated
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Permission Errors (Windows)

**Problem**: `cannot be loaded because running scripts is disabled`

**Solution**:
Run PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port Already in Use

**Problem**: `Address already in use: 8501`

**Solution**:
```bash
# Use different port
streamlit run app.py --server.port=8502
```

Or kill existing Streamlit process:
```bash
# Windows
taskkill /F /IM streamlit.exe

# macOS/Linux
pkill -f streamlit
```

### Git Not Found

**Problem**: `Git not found` when cloning repositories

**Solution**:
1. Install Git from https://git-scm.com/downloads
2. Restart terminal/command prompt
3. Verify: `git --version`

**Note**: Git is optional. You can use ZIP/folder/file upload instead.

### Import Errors

**Problem**: `name 'Tuple' is not defined`

**Solution**:
This is already fixed in the current version. If you encounter this:
1. Pull latest changes
2. Or manually add to imports: `from typing import Tuple`

### Encoding Errors (Windows)

**Problem**: `UnicodeEncodeError` in console

**Solution**:
This is cosmetic and doesn't affect functionality. The application handles it gracefully.

For cleaner output:
```powershell
# Set console encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## Uninstallation

### Remove Virtual Environment

```bash
# Deactivate first
deactivate

# Remove directory
# Windows
rmdir /s venv

# macOS/Linux
rm -rf venv
```

### Remove Workspaces

```bash
# Windows
rmdir /s workspaces temp

# macOS/Linux
rm -rf workspaces temp
```

### Complete Cleanup

```bash
# Remove all generated files
# Windows
rmdir /s venv workspaces temp

# macOS/Linux
rm -rf venv workspaces temp
rm -rf tools/__pycache__
rm -rf .streamlit/secrets.toml
```

---

## Upgrading

### Update Dependencies

```bash
# Activate virtual environment
# Then:
pip install -r requirements.txt --upgrade
```

### Verify After Upgrade

```bash
python validate.py
```

---

## Development Setup

### Install in Editable Mode

```bash
pip install -e .
```

### Install Development Dependencies

Add to `requirements.txt` or install separately:
```bash
pip install pytest pytest-cov black flake8 mypy
```

### Run Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black .
```

### Linting

```bash
flake8 .
```

---

## IDE Setup

### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Python Docstring Generator

**Settings** (`.vscode/settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

### PyCharm

1. Open project
2. Configure Python interpreter → Select virtual environment
3. Enable "Python Integrated Tools" → Pytest

---

## Docker Setup (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t autosdlc-agent .
docker run -p 8501:8501 autosdlc-agent
```

---

## Next Steps

After successful installation:

1. **Read Documentation**
   - [README.md](README.md) - Complete documentation
   - [QUICKSTART.md](QUICKSTART.md) - Quick start guide
   - [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Architecture details

2. **Try Examples**
   - Upload a small project
   - Clone a public GitHub repository
   - Explore the analytics dashboard

3. **Configure for Your Use Case**
   - Set environment variables
   - Adjust file size limits
   - Configure logging level

4. **Explore Features**
   - Test all four input methods
   - Review file categorization
   - Check processing logs

---

## Support

### Getting Help

1. **Check Troubleshooting Section** (above)
2. **Review Error Messages** in UI and console
3. **Check Logs** for detailed error information
4. **Run Validation** to identify issues

### Common Issues

Most issues are related to:
- Python version (must be 3.9+)
- Virtual environment not activated
- Missing dependencies
- Port conflicts

Run `python validate.py` to diagnose issues.

---

## Version Information

**Current Version**: 1.0.0 (Phase 1)
**Python Support**: 3.9+
**OS Support**: Windows, macOS, Linux

---

**Installation Complete!** 🎉

Run `streamlit run app.py` to get started.

