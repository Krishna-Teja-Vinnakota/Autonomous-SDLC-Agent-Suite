# 🚀 Quick Start Guide

Get AutoSDLC Test Agent running in 5 minutes!

---

## Step 1: Install Python

Ensure Python 3.9 or higher is installed:

```bash
python --version
```

If not installed, download from [python.org](https://www.python.org/downloads/)

---

## Step 2: Set Up Virtual Environment

### Windows (PowerShell/CMD)

```powershell
# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\activate
```

### macOS/Linux

```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate
```

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Streamlit (UI framework)
- GitPython (GitHub integration)
- Google Cloud AI Platform (for future LLM features)
- Pytest (for future test execution)

---

## Step 4: Launch the Application

```bash
streamlit run app.py
```

The application will automatically open in your browser at:
```
http://localhost:8501
```

---

## Step 5: Upload Your First Project

### Option A: GitHub Repository

1. Select **"GitHub Repository"**
2. Enter repository URL:
   ```
   https://github.com/username/repository
   ```
3. Click **"Clone & Process"**

### Option B: ZIP File

1. Select **"ZIP Upload"**
2. Click **"Browse files"** and select your `.zip` file
3. Click **"Extract & Process"**

### Option C: Folder

1. Select **"Folder Upload"**
2. Click **"Browse files"** and select multiple files (Ctrl+A or Cmd+A)
3. Click **"Upload & Process"**

### Option D: Single File

1. Select **"Single File"**
2. Click **"Browse files"** and select a single `.py`, `.js`, `.ts`, etc. file
3. Click **"Upload & Process"**

---

## 🎉 That's It!

You should now see:
- ✅ Project analysis dashboard
- 📊 File statistics
- 📁 File categorization
- 📝 Processing logs

---

## Next Steps

### For Development:

```bash
# Install in editable mode
pip install -e .

# Run with debugging
streamlit run app.py --logger.level=debug
```

### For Production:

```bash
# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run with custom port
streamlit run app.py --server.port=8080
```

---

## Common Issues

### Port Already in Use

```bash
streamlit run app.py --server.port=8502
```

### Module Not Found

```bash
pip install -r requirements.txt --upgrade
```

### Permission Errors (Windows)

Run PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 🆘 Need Help?

- Check the full [README.md](README.md)
- Review error messages in the UI
- Check the terminal/console for detailed logs

---

**Happy Testing! 🤖**

