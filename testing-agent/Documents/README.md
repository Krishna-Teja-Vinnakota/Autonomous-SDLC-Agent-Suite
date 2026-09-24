# AutoSDLC Test Agent

**Autonomous SDLC Testing Agent with LangGraph Orchestration**

A production-ready, modular system for automated software testing using LangGraph-style agent orchestration, Streamlit UI, and Vertex AI Gemini LLM.

---

## 🎯 Overview

AutoSDLC Test Agent is an autonomous testing agent designed to:
- Analyze codebases from multiple input sources
- Generate comprehensive test suites
- Execute tests in sandboxed environments
- Provide intelligent feedback and recommendations

**Current Phase:** Base Infrastructure (File Indexing)

---

## 🏗️ Architecture

### Core Components

```
AutoSDLC-Test-Agent/
├── app.py                    # Streamlit UI entry point
├── tools/                    # Modular tool library
│   ├── __init__.py
│   ├── git_tool.py          # GitHub repository cloning
│   ├── unzip_tool.py        # ZIP file handling
│   └── file_indexer.py      # File analysis and indexing
├── workspaces/              # Sandboxed execution environments
│   └── run_<uuid>/          # Individual run workspaces
│       └── project/         # Project files
├── temp/                    # Temporary file storage
├── requirements.txt         # Python dependencies
└── README.md
```

### Design Principles

- **Modular Architecture**: Clean separation of concerns with independent tools
- **Safety First**: Sandboxed execution in isolated workspaces
- **Error Handling**: Comprehensive error handling and validation at every layer
- **Scalability**: Designed for future LangGraph orchestration and LLM integration
- **Production Ready**: Logging, type hints, docstrings, and best practices throughout

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Git (for GitHub repository cloning)
- 500 MB+ free disk space

### Installation

1. **Clone or download this repository**

```bash
cd AutoSDLC-Test-Agent
```

2. **Create a virtual environment** (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

### Running the Application

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

### Optional: Configure Vertex AI

For AI-powered analysis, configure Vertex AI Gemini:

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Test configuration
python test_vertex_ai.py
```

See [VERTEX_AI_SETUP.md](VERTEX_AI_SETUP.md) for detailed setup instructions.

---

## 📥 Input Methods

The agent supports four input methods:

### 1. **GitHub Repository**
- Clone public GitHub repositories directly
- Shallow clone (depth=1) for efficiency
- Automatic metadata extraction (commit, author, branch)

**Example:**
```
https://github.com/username/repository
```

### 2. **ZIP Upload**
- Upload compressed project archives
- Automatic extraction with safety validation
- Protection against zip bombs and path traversal
- Max file size: 500 MB
- Max extracted size: 1 GB

### 3. **Folder Upload**
- Upload multiple files preserving directory structure
- Suitable for projects without version control
- Maintains folder hierarchy

### 4. **Single File**
- Analyze individual source files
- Quick testing and validation
- Useful for standalone scripts

---

## 🔧 Features

### Current (Phase 1 & 2)

✅ **Multi-Source Input**
- GitHub repository cloning
- ZIP file extraction
- Folder upload with structure preservation
- Single file upload

✅ **Sandboxed Workspaces**
- Isolated execution environments
- UUID-based run identifiers
- Clean workspace management

✅ **Comprehensive File Indexing**
- Automatic file categorization (Python, JavaScript, TypeScript, etc.)
- Line counting for source files
- File size analysis
- Extension-based classification
- Directory tree visualization

✅ **Real-Time Status Updates**
- Step-by-step processing feedback
- Success/error/warning indicators
- Detailed processing logs

✅ **Project Analytics**
- Total files, size, and lines of code
- Files by category and extension
- Detailed file listings

✅ **AI-Powered Analysis**
- Vertex AI Gemini integration
- Automatic language detection (JS/TS/Python/etc.)
- Framework identification (React/Node/Django/Flask/etc.)
- Test setup analysis (Jest/Pytest/existing tests)
- Intelligent project summaries
- Privacy-focused (only file summaries sent, not full code)

✅ **Autonomous Test Generation**
- Smart test strategy determination
- Jest test generation for JS/TS/React
- Pytest test generation for Python
- React Testing Library for components
- One test file per source file
- Never overwrites existing files
- Downloadable from UI
- Context-aware, high-quality tests

✅ **Autonomous Test Execution**
- Safe subprocess execution (no shell=True)
- Command allowlist security
- Automatic retry (up to 3 attempts)
- Jest and Pytest execution
- Captures stdout, stderr, exit codes
- Parses test results (pass/fail/skip)
- Per-run timeout enforcement
- AI-powered failure analysis
- Execution logs display

✅ **Coverage and Reporting**
- Jest coverage parsing
- Pytest-cov coverage parsing
- Unified test reports (JSON & HTML)
- Interactive Plotly visualizations
- Coverage bar charts
- Pass/fail pie charts
- Downloadable reports
- Coverage metrics (lines, branches, functions)

✅ **LangGraph-Style Orchestration (NEW!)**
- Workflow orchestration with shared state
- Stage-based execution (6 stages)
- Automatic retry guards (max 3)
- Cleanup logic guarantees
- Security hardening
- UI never executes code directly
- End-to-end automation

### Planned Features

✅ **Phase 2: Intelligent Analysis (COMPLETE)**
- Vertex AI Gemini integration ✓
- Language & framework detection ✓
- Test setup analysis ✓
- Project understanding ✓

✅ **Phase 2.5: Test Generation (COMPLETE)**
- LLM-powered test case generation ✓
- Jest for JavaScript/TypeScript/React ✓
- Pytest for Python ✓
- Context-aware test creation ✓
- One test file per source file ✓
- React Testing Library integration ✓
- Download generated tests ✓

🔜 **Phase 3: Test Execution**
- Sandboxed test execution
- Real-time output streaming
- Coverage reporting

🔜 **Phase 4: LangGraph Orchestration**
- Multi-agent workflow
- Intelligent decision-making
- Iterative test improvement

🔜 **Phase 5: Advanced Features**
- Vertex AI Gemini integration
- Custom test strategies
- CI/CD integration
- Report generation

---

## 🛡️ Safety Features

### Sandboxing
- All projects copied to isolated `/workspaces/run_<uuid>/project` directories
- No direct access to user file system
- Automatic cleanup capabilities

### Validation
- GitHub URL validation
- ZIP file safety checks (size limits, path traversal protection)
- File extension validation
- Directory traversal prevention

### Security Limits
- Max ZIP file size: 500 MB
- Max extracted size: 1 GB
- Max files per archive: 10,000
- Ignored directories: `node_modules`, `.git`, `__pycache__`, etc.

---

## 📊 File Categorization

The indexer automatically categorizes files:

| Category | Extensions |
|----------|-----------|
| **Python** | `.py` |
| **JavaScript** | `.js`, `.jsx` |
| **TypeScript** | `.ts`, `.tsx` |
| **Tests** | `.test.js`, `.spec.ts`, etc. |
| **HTML/CSS** | `.html`, `.css`, `.scss` |
| **Config** | `.json`, `.yaml`, `.toml` |
| **Documentation** | `.md`, `.rst`, `.txt` |
| **Database** | `.sql`, `.db` |
| **Scripts** | `.sh`, `.bat`, `.ps1` |

---

## 🧪 Usage Example

1. **Launch the application**
   ```bash
   streamlit run app.py
   ```

2. **Select input method**
   - Choose "GitHub Repository" for public repos
   - Or upload a ZIP/folder/file

3. **Process your project**
   - Enter GitHub URL or upload files
   - Click "Clone & Process" / "Extract & Process"

4. **View results**
   - Project analytics dashboard
   - File categorization
   - Processing logs
   - Directory structure

5. **Reset for new run**
   - Click "Reset Session" in sidebar

---

## 🔍 Technical Details

### Tools Module

#### `GitTool`
- **Purpose**: Clone GitHub repositories
- **Key Methods**:
  - `validate_github_url()`: URL validation
  - `clone_repository()`: Repository cloning with metadata
  - `get_repo_name_from_url()`: Extract repo name
- **Features**: Shallow cloning, branch selection, error handling

#### `UnzipTool`
- **Purpose**: Handle ZIP file operations
- **Key Methods**:
  - `validate_zip_file()`: Safety validation
  - `extract_zip()`: Safe extraction
  - `save_uploaded_zip()`: Streamlit file handling
- **Safety**: Size limits, path traversal prevention, zip bomb protection

#### `FileIndexer`
- **Purpose**: Analyze and categorize project files
- **Key Methods**:
  - `index_directory()`: Complete directory analysis
  - `get_file_category()`: File categorization
  - `count_lines()`: Line counting for text files
  - `build_directory_tree()`: Tree structure generation
- **Features**: Smart categorization, ignored directories, line counting

---

## 🐛 Error Handling

All tools implement comprehensive error handling:

- **Validation**: Input validation before processing
- **Try-Catch**: Exception handling at every layer
- **Cleanup**: Automatic cleanup on failure
- **Logging**: Detailed error logging
- **User Feedback**: Clear error messages in UI

---

## 📝 Logging

Structured logging throughout the application:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

- **INFO**: Normal operations
- **WARNING**: Non-critical issues
- **ERROR**: Failures and exceptions
- **DEBUG**: Detailed debugging information

---

## 🚧 Roadmap

### Phase 1: Base Infrastructure ✅ (COMPLETE)
- [x] Project structure
- [x] Input handling (4 methods)
- [x] Sandboxed workspaces
- [x] File indexing
- [x] Streamlit UI

### Phase 2: Intelligent Analysis ✅ (COMPLETE)
- [x] Vertex AI Gemini integration
- [x] Language detection
- [x] Framework identification
- [x] Test setup analysis
- [x] Intelligent summaries

### Phase 2.5: Test Generation ✅ (COMPLETE)
- [x] LLM-powered test case generation ✓
- [x] Jest for JavaScript/TypeScript/React ✓
- [x] Pytest for Python ✓
- [x] Context-aware test creation ✓
- [x] One test file per source file ✓
- [x] React Testing Library integration ✓
- [x] Download generated tests ✓

### Phase 3: Test Execution ✅ (COMPLETE)
- [x] Jest execution with retry ✓
- [x] Pytest execution with retry ✓
- [x] Safe subprocess (no shell=True) ✓
- [x] Result parsing ✓
- [x] Failure analysis ✓

### Phase 4: Coverage & Reporting ✅ (COMPLETE)
- [x] Jest coverage parsing ✓
- [x] Pytest coverage parsing ✓
- [x] Unified reports (JSON & HTML) ✓
- [x] Plotly visualizations ✓
- [x] Downloadable reports ✓

### Phase 5: LangGraph Orchestration ✅ (COMPLETE)
- [x] Workflow orchestration ✓
- [x] Shared state management ✓
- [x] Retry guards (max 3) ✓
- [x] Cleanup logic ✓
- [x] Security hardening ✓
- [x] UI never executes code directly ✓
- [ ] LLM integration (Vertex AI Gemini)
- [ ] Jest test generation
- [ ] Pytest test generation
- [ ] Test case templates

### Phase 3: Test Execution
- [ ] Jest runner integration
- [ ] Pytest runner integration
- [ ] Output capture and parsing
- [ ] Coverage reporting

### Phase 4: Agent Orchestration
- [ ] LangGraph integration
- [ ] Multi-agent workflow
- [ ] Decision-making logic
- [ ] Iterative improvement

### Phase 5: Production Features
- [ ] CI/CD integration
- [ ] Custom test strategies
- [ ] Report generation
- [ ] API endpoints

---

## 🤝 Contributing

This project follows enterprise-grade development practices:

- Clean, modular code architecture
- Comprehensive error handling
- Type hints and documentation
- Logging and monitoring
- Security best practices

---

## 📄 License

This project is built as a production-ready SDLC testing agent.

---

## 🙋 Support

For issues, questions, or contributions, please refer to the project documentation.

---

**Built with:**
- 🎨 Streamlit for UI
- 🔧 Python 3.9+
- 🤖 Google Vertex AI (Gemini)
- 🧪 Jest & Pytest
- 🔄 LangGraph (planned)

**Status:** Base Infrastructure Complete ✅

---

*AutoSDLC Test Agent - Autonomous testing for modern software development*

