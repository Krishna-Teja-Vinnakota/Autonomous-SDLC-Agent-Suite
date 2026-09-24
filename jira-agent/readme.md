# Jira Tickets Agent

## Overview

The Jira Tickets Agent is an AI-assisted Streamlit application that automates generation of Epics, user stories, and implementation tasks from raw requirements. It compresses and analyzes requirements with an LLM, supports a human-in-the-loop review flow, persists useful patterns for reuse, and can optionally create JIRA tickets for Epics, Stories and Tasks.

This repository contains the Streamlit app and helper logic to run the full SDLC automation workflow locally.

## Technologies

- UI / App: Streamlit (Python)
- AI / LLM: `langchain` / Vertex AI client (`langchain_google_vertexai`) integration (configurable)
- Persistence: SQLite (local file `sdlc_context.sqlite` created automatically)
- Optional Integrations: JIRA REST API (via `jira` Python package)

## Prerequisites

- Python 3.8 or higher (3.10+ recommended)
- pip package manager
- Git (for cloning repository)
- (Optional) Google Cloud Vertex AI access and a service account JSON if using `ChatVertexAI`
- (Optional) JIRA account and API token for automatic ticket creation

## Usage

### Clone the repository

```bash
git clone <your-repository-url>
cd <your-repo-folder>
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

If this repo includes `requirements.txt`, install it with:

```bash
pip install -r requirements.txt
```


### Configure credentials and environment

Set required environment variables or update the top of `Jira_Tickets_Agent.py` to point to your credentials. Typical variables:

- `SERVICE_ACCOUNT_FILE` — path to Google service account JSON (optional for Vertex AI)
- `API_TOKEN` — JIRA API token (required for ticket creation)
- `JIRA_URL` — base URL of your Jira instance (e.g. `https://your-domain.atlassian.net/`)
- `JIRA_EMAIL` — email of the Jira user used for API authentication
- `PROJECT_KEY` — Jira project key to create issues in

### Start the app

```bash
streamlit run Jira_Tickets_Agent.py
```

Open the local Streamlit URL (printed in the terminal). Paste your requirements into the text area and click "Start Workflow". The app will run the AI workflow, present generated stories for review, and optionally create JIRA tickets.



## Output and persistence

- `sdlc_output_enhanced.json` — final structured JSON exported by the app.
- `sdlc_context.sqlite` — local SQLite database used for caching requirement patterns, story templates, and tech context (tables: `requirement_patterns`, `story_templates`, `tech_context_cache`, `compressed_requirements`).


## Example quick usage

1. Clone repo and create a virtual environment.
2. Install dependencies.
3. Set `GOOGLE_APPLICATION_CREDENTIALS` (if using Vertex AI) and JIRA-related environment variables (if using ticket creation).
4. Run `streamlit run Jira_Tickets_Agent.py` and paste a requirement into the UI.


