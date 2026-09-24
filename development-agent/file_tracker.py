"""
File Tracking Service for Incremental Indexing
Tracks which files have been modified across multiple developer sessions
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from config import db_config
import os
from pathlib import Path

class FileTracker:
    """Manages tracking of file changes across multiple developers"""
    
    def __init__(self):
        self.tracking_collection = db_config.get_tracking_collection()
        
        # Ensure MongoDB connection
        if not db_config.test_connection():
            raise Exception("Failed to connect to MongoDB for file tracking")
    
    def get_stale_files(self, repo_url: str, current_developer_id: str) -> List[Dict]:
        """
        Get ALL files tracked in MongoDB for this repository that need embedding refresh
        If files exist in tracking collection, they have been modified and need new embeddings
        """
        try:
            print(f"🔍 [MongoDB Query Debug]")
            print(f"   Repo URL: '{repo_url}'")
            print(f"   Looking for: ALL active files in MongoDB tracking collection for this repo")
            
            # Check what files are tracked in MongoDB for this repo
            total_for_repo = self.tracking_collection.count_documents({"repo_url": repo_url})
            active_for_repo = self.tracking_collection.count_documents({"repo_url": repo_url, "status": "active"})
            print(f"   Total records for this repo: {total_for_repo}")
            print(f"   Active records for this repo: {active_for_repo}")
            
            # MongoDB aggregation pipeline to find ALL active files for this repo
            pipeline = [
                # Match ALL active files in this repo (regardless of developer)
                {
                    "$match": {
                        "repo_url": repo_url,
                        "status": "active"
                    }
                },
                # Group by file_path to get latest modification per file
                {
                    "$group": {
                        "_id": "$file_path",
                        "latest_modification": {"$max": "$modified_at"},
                        "modification_type": {"$last": "$modification_type"},
                        "developer_id": {"$last": "$developer_id"},
                        "jira_ticket": {"$last": "$jira_ticket"},
                        "embedding_ids": {"$last": "$embedding_ids"}  # Include embedding IDs
                    }
                },
                # Sort by modification time (newest first)
                {
                    "$sort": {"latest_modification": -1}
                }
            ]
            
            result = list(self.tracking_collection.aggregate(pipeline))
            
            print(f"📊 Found {len(result)} files that need embedding refresh")
            if result:
                for file_info in result:
                    print(f"  - {file_info['_id']} (modified by {file_info['developer_id']} in {file_info['jira_ticket']})")
            else:
                print("   No tracked files found - checking sample records...")
                # Show a few sample records to debug
                sample_records = list(self.tracking_collection.find({"repo_url": repo_url}).limit(3))
                for record in sample_records:
                    print(f"   Sample: file={record.get('file_path')}, dev={record.get('developer_id')}, status={record.get('status')}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error querying tracked files: {e}")
            return []
    
    def track_file_modification(self, repo_url: str, file_path: str, 
                              developer_id: str, jira_ticket: str, 
                              modification_type: str = 'updated',
                              embedding_ids: list = None) -> bool:
        """
        Track when a file has been modified by current developer
        
        Args:
            repo_url: Repository URL or identifier
            file_path: Relative path of the file within repo
            developer_id: Unique identifier for the developer
            jira_ticket: Jira ticket ID being worked on
            modification_type: 'updated', 'added', 'deleted'
            embedding_ids: List of vector embedding IDs created for this file
        """
        try:
            # Step 1: Delete previous active records for this file instead of marking as superseded
            delete_result = self.tracking_collection.delete_many(
                {
                    'repo_url': repo_url,
                    'file_path': file_path,
                    'status': 'active'
                }
            )
            
            if delete_result.deleted_count > 0:
                print(f"🗑️ Deleted {delete_result.deleted_count} previous tracking records for {file_path}")
            
            # Step 2: Insert new tracking record with embedding IDs
            new_record = {
                'repo_url': repo_url,
                'file_path': file_path,
                'developer_id': developer_id,
                'jira_ticket': jira_ticket,
                'modification_type': modification_type,
                'modified_at': datetime.utcnow(),
                'status': 'active',
                'embedding_ids': embedding_ids or []  # Store vector embedding IDs
            }
            
            insert_result = self.tracking_collection.insert_one(new_record)
            
            print(f"📝 Tracked {modification_type}: {file_path} by {developer_id}")
            if embedding_ids:
                print(f"   📍 Stored embedding IDs: {embedding_ids}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error tracking file modification: {e}")
            return False
    
    def get_repository_stats(self, repo_url: str) -> Dict[str, Any]:
        """
        Get statistics about file modifications for a repository
        """
        try:
            pipeline = [
                {'$match': {'repo_url': repo_url, 'status': 'active'}},
                {'$group': {
                    '_id': '$developer_id',
                    'files_modified': {'$sum': 1},
                    'last_activity': {'$max': '$modified_at'}
                }},
                {'$sort': {'last_activity': -1}}
            ]
            
            developer_stats = list(self.tracking_collection.aggregate(pipeline))
            
            total_files = self.tracking_collection.count_documents({
                'repo_url': repo_url,
                'status': 'active'
            })
            
            return {
                'repo_url': repo_url,
                'active_developers': len(developer_stats),
                'developer_activity': developer_stats,
                'total_tracked_files': total_files
            }
            
        except Exception as e:
            print(f"❌ Error getting repository stats: {e}")
            return {
                'repo_url': repo_url,
                'error': str(e)
            }
    
    def clear_repository_tracking(self, repo_url: str) -> bool:
        """
        Clear all tracking records for a repository (useful for testing)
        """
        try:
            result = self.tracking_collection.delete_many({'repo_url': repo_url})
            print(f"🗑️ Cleared {result.deleted_count} tracking records for {repo_url}")
            return True
        except Exception as e:
            print(f"❌ Error clearing repository tracking: {e}")
            return False

def get_repo_url_from_path(repo_path: str) -> str:
    """
    Get repository URL/identifier for tracking purposes
    
    Priority:
    1. GITHUB_REPO_URL from environment (ensures consistency across developers)  
    2. Git remote URL from local repository
    3. Fallback to directory name
    """
    try:
        # Priority 1: Use GITHUB_REPO_URL from environment for consistency
        import os
        github_repo_url = os.getenv("GITHUB_REPO_URL")
        if github_repo_url and github_repo_url.strip():
            print(f"📍 Using GITHUB_REPO_URL from environment: {github_repo_url}")
            return github_repo_url.strip()
        
        # Priority 2: Try to get remote URL from git
        import subprocess
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            git_url = result.stdout.strip()
            print(f"📍 Using git remote URL: {git_url}")
            return git_url
        else:
            # Priority 3: Fallback to directory name
            fallback_id = f"local_repo_{os.path.basename(repo_path)}"
            print(f"⚠️ No git remote found, using fallback: {fallback_id}")
            return fallback_id
            
    except Exception as e:
        fallback_id = f"local_repo_{os.path.basename(repo_path)}"
        print(f"⚠️ Error getting repo URL, using fallback: {fallback_id} ({e})")
        return fallback_id

def get_relative_path(full_path: str, repo_path: str) -> str:
    """Get relative path from repository root"""
    return os.path.relpath(full_path, repo_path).replace('\\', '/')

# Global instance for easy access
file_tracker = FileTracker()

