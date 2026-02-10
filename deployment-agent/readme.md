# Cloud Deployment Agent

## Overview
The Cloud Deployment Agent is an intelligent automation tool designed to facilitate seamless deployment of applications to Google Cloud Platform (GCP). It streamlines the deployment process by integrating with GitHub repositories, allowing users to configure and monitor their deployments in real-time. This solution enhances operational efficiency and reduces the complexity of cloud deployments.

## Technologies:

- **Cloud Provider:** GCP
- **Key Services:** Google Cloud Build, Google Cloud Run
- **Languages:** Python

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Git

## Usage

### Clone the repository:

```bash
git clone [your-repository-url]
```

### Create and activate a virtual environment (recommended):

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux/MacOS
python -m venv .venv
source .venv/bin/activate
```

### Install required packages:

```bash
pip install -r requirements.txt
```

### Start the deployment agent:

```bash
python main.py
```

Follow the prompts to enter your GitHub repository URL and branch name. The agent will handle the deployment process and provide real-time monitoring of the build status.

### Monitor deployment progress:

The deployment progress can be monitored in real-time using the monitoring script:

```bash
python moniter.py
```

This will display the current status of your deployment and any logs generated during the process.
