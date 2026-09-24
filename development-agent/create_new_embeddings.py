"""
Standalone script to create vector embeddings freshly for a folder.
Uses repo_indexer; does not affect the existing workflow or incremental indexer.

Usage (run from backend or project root):
  python create_new_embeddings.py <folder_name>

Example:
  python create_new_embeddings.py web-app
"""
import os
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent

# Load .env from backend directory
from dotenv import load_dotenv
load_dotenv(_script_dir / ".env")

# Resolve folder from the cwd where the user runs the script (before importing indexer)
def _get_repo_path():
    if len(sys.argv) < 2:
        return None
    return Path(sys.argv[1].strip()).resolve()

from repo_indexer import create_indexer


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_new_embeddings.py <folder_name>")
        print("Example: python create_new_embeddings.py web-app")
        sys.exit(1)

    repo_path = _get_repo_path()
    if not repo_path.exists():
        print(f"Error: path does not exist: {repo_path}")
        sys.exit(1)
    if not repo_path.is_dir():
        print(f"Error: not a directory: {repo_path}")
        sys.exit(1)

    service_account_path = os.getenv("VERTEX_AI_CREDENTIALS_PATH", "gen-lang-client-0375456222-003d04a91a5d.json")
    project_id = os.getenv("VERTEX_AI_PROJECT_ID", "dg-assistant-451309")
    qdrant_url = os.getenv("QDRANT_URL", "").strip()
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip()
    collection_name = os.getenv("QDRANT_COLLECTION_NAME", "FMCG_embeddings")

    if not qdrant_url or not qdrant_api_key:
        print("Error: Set QDRANT_URL and QDRANT_API_KEY in .env")
        sys.exit(1)
    if not os.path.isabs(service_account_path) and not os.path.exists(service_account_path):
        service_account_path = str(_script_dir / service_account_path)
    if not os.path.exists(service_account_path):
        print(f"Error: credentials file not found: {service_account_path}")
        sys.exit(1)

    indexer = create_indexer(
        str(service_account_path), project_id,
        qdrant_url, qdrant_api_key, collection_name
    )
    result = indexer.index_repository(str(repo_path), force_reindex=True)

    if result.get("success"):
        print(f"Done. Files indexed: {result.get('files_indexed', 0)}")
    else:
        print(f"Failed: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
