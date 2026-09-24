# Automated Test Design Agent

## Overview

The **Automated Test Design Agent** (AutoSDLC-Test-Agent) is an AI-assisted Streamlit application that automates the generation of unit, integration, and feature tests for software projects. It accepts source code via GitHub URL, ZIP upload, folder upload, or single-file upload, analyzes the codebase with an LLM, designs a test strategy, generates production-ready tests, executes them, and produces a unified coverage report — all through an interactive web UI.

This repository contains the Streamlit app and the full agent pipeline to run the automated testing workflow locally.

## Technologies

| Layer | Technology |
|---|---|
| **UI / App** | Streamlit (Python) |
| **AI / LLM** | Vertex AI Gemini via `google-cloud-aiplatform` and `langchain-google-vertexai` |
| **Workflow Orchestration** | LangGraph / LangChain |
| **Git Operations** | GitPython |
| **Testing Execution** | Jest / Playwright (for target JS/TS projects), pytest (for Python targets) |
| **Visualization** | Plotly |

## Prerequisites

- **Python 3.9** or higher (3.10+ recommended)
- **pip** package manager
- **Git** (for cloning repositories)
- (Optional) **Google Cloud Vertex AI** access and a service-account JSON key if using Gemini AI analysis
- (Optional) **Node.js / npm** if the target project uses JavaScript/TypeScript test runners

## Project Structure

```
Automated_test_design_agent/
├── app.py                  # Main Streamlit application entry point
├── agents/                 # AI agent modules
│   ├── analyze_agent.py            # Project analysis agent
│   ├── strategy_agent.py           # Test strategy design agent
│   ├── test_generator_agent.py     # Test code generation agent
│   ├── test_executor_agent.py      # Test execution agent
│   ├── failure_analyzer_agent.py   # Failure diagnosis agent
│   ├── report_agent.py             # Unified report generation agent
│   └── environment_setup_agent.py  # Environment setup agent
├── tools/                  # Utility tools
│   ├── git_tool.py                 # Git clone helper
│   ├── unzip_tool.py               # ZIP extraction helper
│   ├── file_indexer.py             # File indexing & categorization
│   ├── context_builder.py          # Context building for LLM
│   ├── context_parser.py           # Context parsing
│   ├── coverage_parser.py          # Coverage report parser
│   ├── command_executor.py         # Shell command executor
│   ├── test_rules_validator.py     # Test rules validation
│   └── testing_rules.py            # Testing rule definitions
├── config/                 # Configuration
│   ├── vertex_ai.py                # Vertex AI client & config
│   ├── vertex_ai_config_check.py   # Config verification script
│   └── testing_patterns.py         # Testing infrastructure detection
├── workflows/              # Workflow orchestration
│   └── langgraph_flow.py           # LangGraph-based workflow
├── components/             # UI components
├── e2e/                    # End-to-end test examples
├── mocks/                  # Mock server setup (MSW)
├── tests/                  # Project test suite
├── Documents/              # Project documentation
├── .github/                # GitHub Actions workflows
├── requirements.txt        # Python dependencies
├── setup.py                # Setup & verification script
└── .gitignore              # Git ignore rules
```

## Usage

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd Automated_test_design_agent
```

### 2. Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python -m venv .venv
source .venv/bin/activate
```

### 3. Install required packages

```bash
pip install -r requirements.txt
```

### 4. Configure credentials and environment

Set the required environment variables for Vertex AI (optional — the app also works without AI if you skip LLM-powered analysis):

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to your Google Cloud service-account JSON key |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID |
| `GOOGLE_CLOUD_REGION` | Vertex AI region (default: `us-central1`) |
| `VERTEX_AI_MODEL` | Model name (default: `gemini-2.0-flash`) |

**Windows (PowerShell):**

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\credentials.json"
$env:GOOGLE_CLOUD_PROJECT="your-project-id"
```

**Linux / macOS:**

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

Or create a `.env` file in the project root:

```env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_CLOUD_PROJECT=your-project-id
VERTEX_AI_MODEL=gemini-2.0-flash
```

### 5. Run the setup verification (optional)

```bash
python setup.py
```

This checks Python version, Git installation, directory structure, and dependency imports.

### 6. Start the app

```bash
streamlit run app.py
```

Open the local Streamlit URL (printed in the terminal, typically `http://localhost:8501`).

## How It Works

1. **Upload your project** — Provide source code via GitHub URL, ZIP file, folder upload, or single file.
2. **File indexing** — The app scans and categorizes all project files.
3. **AI analysis** — Vertex AI Gemini analyzes the codebase to detect languages, frameworks, and architecture patterns.
4. **Test strategy** — The strategy agent designs a testing plan covering unit, integration, and feature tests.
5. **Test generation** — The generator agent produces production-ready test files.
6. **Test execution** — Generated tests are executed in a sandboxed workspace.
7. **Failure analysis** — Any failures are diagnosed and fixes are suggested.
8. **Report** — A unified report with coverage metrics and Plotly visualizations is generated.

## Example Quick Usage

1. Clone the repo and create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. (Optional) Set `GOOGLE_APPLICATION_CREDENTIALS` for AI-powered analysis.
4. Run `streamlit run app.py`.
5. Upload a project (GitHub URL, ZIP, or folder) and click through the workflow.
