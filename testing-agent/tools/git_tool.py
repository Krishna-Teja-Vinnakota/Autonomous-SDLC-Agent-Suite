"""
Git Tool for cloning GitHub repositories
Handles repository cloning with proper error handling and validation
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple
from git import Repo, GitCommandError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitTool:
    """
    Tool for handling Git repository operations
    Provides safe cloning with error handling and cleanup
    """

    @staticmethod
    def validate_github_url(url: str) -> bool:
        """
        Validate if the provided URL is a valid GitHub URL
        
        Args:
            url: GitHub repository URL
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not url:
            return False
        
        valid_prefixes = [
            'https://github.com/',
            'http://github.com/',
            'git@github.com:',
            'git://github.com/'
        ]
        
        return any(url.startswith(prefix) for prefix in valid_prefixes)

    @staticmethod
    def clone_repository(
        repo_url: str,
        target_path: Path,
        branch: Optional[str] = None,
        depth: Optional[int] = 1
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Clone a GitHub repository to the target path
        
        Args:
            repo_url: GitHub repository URL
            target_path: Destination path for cloning
            branch: Optional specific branch to clone
            depth: Clone depth (default 1 for shallow clone)
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (success, message, metadata)
        """
        try:
            # Validate URL
            if not GitTool.validate_github_url(repo_url):
                return False, f"Invalid GitHub URL: {repo_url}", None

            # Ensure target path exists
            target_path.mkdir(parents=True, exist_ok=True)

            # Check if target path is empty
            if any(target_path.iterdir()):
                return False, f"Target path is not empty: {target_path}", None

            logger.info(f"Cloning repository: {repo_url} to {target_path}")

            # Clone repository
            clone_kwargs = {
                'depth': depth,
                'single-branch': True
            }
            
            if branch:
                clone_kwargs['branch'] = branch

            repo = Repo.clone_from(repo_url, str(target_path), **clone_kwargs)

            # Gather metadata
            metadata = {
                'repo_url': repo_url,
                'branch': branch or repo.active_branch.name,
                'commit_hash': repo.head.commit.hexsha,
                'commit_message': repo.head.commit.message.strip(),
                'author': str(repo.head.commit.author),
                'commit_date': repo.head.commit.committed_datetime.isoformat(),
            }

            logger.info(f"Successfully cloned repository to {target_path}")
            return True, f"Successfully cloned repository", metadata

        except GitCommandError as e:
            error_msg = f"Git command error: {str(e)}"
            logger.error(error_msg)
            
            # Cleanup on failure
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            
            return False, error_msg, None

        except Exception as e:
            error_msg = f"Unexpected error while cloning: {str(e)}"
            logger.error(error_msg)
            
            # Cleanup on failure
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            
            return False, error_msg, None

    @staticmethod
    def get_repo_name_from_url(repo_url: str) -> Optional[str]:
        """
        Extract repository name from GitHub URL
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Optional[str]: Repository name or None
        """
        try:
            # Remove .git suffix if present
            url = repo_url.rstrip('/')
            if url.endswith('.git'):
                url = url[:-4]
            
            # Extract repo name
            parts = url.split('/')
            if len(parts) >= 2:
                return parts[-1]
            
            return None
        except Exception as e:
            logger.error(f"Error extracting repo name: {e}")
            return None

