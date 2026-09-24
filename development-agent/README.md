# Developer Agent

## Overview

Developer Agent V2.0 is an AI-powered FastAPI application that automates JIRA ticket resolution through intelligent code analysis and modification. It fetches JIRA ticket details, uses semantic search over vector-embedded codebases to identify relevant files, generates targeted code modifications with an LLM, validates changes against ticket requirements with auto-fix capabilities, and creates GitHub pull requests — all with a human-in-the-loop approval flow at critical stages.

This repository contains the FastAPI backend, LangGraph agent workflow, vector search services, and a static frontend to run the full developer automation workflow locally.

## Technologies

- UI / App: Vanilla HTML / CSS / JavaScript (static files served by FastAPI)
- Backend / API: FastAPI, Uvicorn
- Workflow Engine: LangGraph (`langgraph`) with checkpoints and interrupts
- AI / LLM: `langchain` / Vertex AI client (`langchain_google_vertexai`) — Gemini 2.5 Pro (generation), text-embedding-004 (embeddings)
- Vector Database: Qdrant (`qdrant-client`) for semantic code search
- File Tracking: MongoDB (`pymongo`) — tracks file modifications across developers
- Version Control: GitPython (local git ops), PyGithub (GitHub API for PR creation)
- Optional Integrations: JIRA REST API for ticket fetching, GitHub API for automated PR creation

## Prerequisites

- Python 3.10 or higher (3.8+ minimum)
- pip package manager
- Git (for cloning repository)
- MongoDB instance (local or Atlas)
- Qdrant vector database instance (cloud or self-hosted)
- Google Cloud Vertex AI access and a service account JSON for Gemini / embeddings
- GitHub personal access token with repo permissions
- JIRA account and API token for ticket fetching

## Usage

### Clone the repository

```bash
git clone <your-repository-url>
cd <your-repo-folder>/backend
```

### Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python -m venv .venv
source .venv/bin/activate
```

### Install required packages

```bash
pip install -r requirements.txt
```

### Configure credentials and environment

Create a `.env` file in the `backend/` directory with the following variables:

- `MONGODB_URI` — MongoDB connection string (e.g. `mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/`)
- `JIRA_BASE_URL` — base URL of your JIRA instance (e.g. `https://your-domain.atlassian.net`)
- `JIRA_EMAIL` — email of the JIRA user used for API authentication
- `JIRA_API_TOKEN` — JIRA API token
- `GITHUB_TOKEN` — GitHub personal access token
- `GITHUB_REPO_URL` — GitHub repository URL (e.g. `https://github.com/your-org/your-repo`)
- `GITHUB_BASE_BRANCH` — base branch for pull requests (default: `main`)
- `QDRANT_URL` — Qdrant instance URL
- `QDRANT_API_KEY` — Qdrant API key
- `QDRANT_COLLECTION_NAME` — Qdrant collection name (default: `code_repository`)
- `VERTEX_AI_CREDENTIALS_PATH` — path to Google Cloud service account JSON
- `VERTEX_AI_PROJECT_ID` — Google Cloud project ID

### Index a repository (first-time setup)

Before the agent can search your codebase, create vector embeddings:

```bash
python create_new_embeddings.py /path/to/your/repo
```

### Start the app

```bash
python api_server.py
```

Open **http://localhost:8000** in your browser. Enter a JIRA ticket ID and the local repository path, then click **Start Workflow**. The app will run the AI workflow, present identified files and generated code changes for review, and optionally create a GitHub pull request.

## Output and persistence

- **MongoDB** (database: `SDLC`, collection: `tracking`) — stores file modification records across developer sessions, used for incremental embedding refresh so every developer works against an up-to-date codebase index.
- **Qdrant** — stores vector embeddings with rich payloads (file content, AI-generated summaries, metadata such as functions, classes, and dependencies) for semantic code search.

## Example quick usage

1. Clone the repo and create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Create a `.env` file with MongoDB, JIRA, GitHub, Qdrant, and Vertex AI credentials.
4. Run `python create_new_embeddings.py /path/to/target/repo` to index the target codebase.
5. Run `python api_server.py` and open **http://localhost:8000** in your browser.
6. Enter a JIRA ticket ID, review identified files, approve code changes, and the agent creates a PR automatically.
