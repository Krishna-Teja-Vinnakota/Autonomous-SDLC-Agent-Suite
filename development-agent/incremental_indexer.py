"""
Incremental Indexing Service
Extends the existing RepoIndexer to support incremental updates based on file tracking
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from repo_indexer import RepoIndexer, CODE_EXTENSIONS, DEPENDENCY_FILES
from file_tracker import FileTracker, get_repo_url_from_path, get_relative_path
from qdrant_client.models import Filter, FieldCondition, MatchValue

class IncrementalIndexer(RepoIndexer):
    """
    Enhanced RepoIndexer with incremental update capabilities
    Maintains the same payload format but adds intelligent file tracking
    """
    
    def __init__(self, service_account_path: str, project_id: str, 
                 qdrant_url: str, qdrant_api_key: str, collection_name: str):
        # Initialize parent RepoIndexer
        super().__init__(service_account_path, project_id, qdrant_url, qdrant_api_key, collection_name)
        
        # Initialize file tracker
        self.file_tracker = FileTracker()
        
    def start_developer_session(self, repo_path: str, jira_ticket: str, developer_id: str) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Called when developer starts working with the agent
        
        Flow:
        1. Get repository identifier from cloned path
        2. Check MongoDB for files changed by other developers  
        3. Refresh embeddings for those stale files using existing payload format
        4. Return session information
        """
        print(f"🚀 Starting developer session")
        print(f"   Developer: {developer_id}")
        print(f"   Ticket: {jira_ticket}")
        print(f"   Repository: {repo_path}")
        
        try:
            repo_url = get_repo_url_from_path(repo_path)
            print(f"📁 Repository identifier: {repo_url}")
            
            # Check for tracked files that need embedding refresh
            tracked_files = self.file_tracker.get_stale_files(repo_url, developer_id)
            
            refreshed_count = 0
            if tracked_files:
                print(f"🔄 Found {len(tracked_files)} files that need embedding refresh")
                refreshed_count = self._refresh_stale_embeddings(repo_path, repo_url, tracked_files)
                print(f"✅ Refreshed embeddings for {refreshed_count} files")
            else:
                print("✅ No tracked files found - all embeddings are current")
            
            # Check if repository is indexed at all
            is_indexed = self._check_repo_has_embeddings(repo_url)
            
            session_info = {
                'status': 'ready',
                'repo_url': repo_url,
                'repo_path': repo_path,
                'is_indexed': is_indexed,
                'tracked_files_found': len(tracked_files),
                'embeddings_refreshed': refreshed_count,
                'developer_id': developer_id,
                'jira_ticket': jira_ticket,
                'message': f"Session ready. Repository {'is indexed' if is_indexed else 'needs initial indexing'}"
            }
            
            return session_info
            
        except Exception as e:
            print(f"❌ Error in developer session setup: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'repo_path': repo_path
            }
    
    def _check_repo_has_embeddings(self, repo_url: str) -> bool:
        """Check if repository has any embeddings in Qdrant"""
        try:
            repo_filter = Filter(
                must=[
                    FieldCondition(
                        key="repo_path",
                        match=MatchValue(value=repo_url)
                    )
                ]
            )
            
            # Check if any points exist for this repo
            result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=repo_filter,
                limit=1,
                with_payload=False
            )
            
            return len(result[0]) > 0
            
        except Exception as e:
            print(f"⚠ Warning: Could not check repo embeddings: {e}")
            return False
    
    def _refresh_stale_embeddings(self, repo_path: str, repo_url: str, stale_files: List[Dict]) -> int:
        """
        Refresh embeddings for files that are stale
        Uses the SAME payload format as existing RepoIndexer
        """
        refreshed_count = 0
        
        for file_info in stale_files:
            file_path = file_info['_id']  # This is the relative file_path from grouping
            full_file_path = os.path.join(repo_path, file_path)
            modification_type = file_info['modification_type']
            
            # Get existing embedding IDs from MongoDB record (if available)
            existing_embedding_ids = file_info.get('embedding_ids', [])
            
            try:
                print(f"  🔄 Processing: {file_path}")
                
                # Step 1: Delete old embeddings for this file (using stored IDs if available)
                deleted_count = self._delete_file_embeddings(repo_url, file_path, existing_embedding_ids)
                
                # Step 2: Create new embeddings if file exists and wasn't deleted
                if modification_type != 'deleted' and os.path.exists(full_file_path):
                    if self._should_index_file(Path(full_file_path)):
                        # Use existing RepoIndexer methods to create embeddings
                        # with the SAME payload format
                        new_embedding_id = self._create_single_file_embedding(full_file_path, file_path, repo_url)
                        if new_embedding_id:
                            refreshed_count += 1
                            print(f"    ✓ Refreshed: {file_path} (new ID: {new_embedding_id})")
                        else:
                            print(f"    ❌ Failed to create embedding: {file_path}")
                    else:
                        print(f"    ⏭️ Skipped non-indexable file: {file_path}")
                else:
                    print(f"    🗑️ Removed embeddings for deleted/missing file: {file_path}")
                    
            except Exception as e:
                print(f"    ❌ Failed to refresh {file_path}: {e}")
        
        return refreshed_count
    
    def _delete_file_embeddings(self, repo_url: str, file_path: str, embedding_ids: list = None):
        """Delete existing embeddings for a specific file using stored embedding IDs"""
        try:
            deleted_count = 0
            
            # Method 1: Delete by stored embedding IDs (most reliable)
            if embedding_ids:
                print(f"    🎯 Deleting embeddings by stored IDs: {embedding_ids}")
                try:
                    # Delete specific embedding IDs
                    self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=embedding_ids
                    )
                    deleted_count = len(embedding_ids)
                    print(f"    ✅ Deleted {deleted_count} embeddings by ID for {file_path}")
                    return deleted_count
                    
                except Exception as id_error:
                    print(f"    ⚠ Error deleting by ID, trying metadata method: {id_error}")
            
            # Method 2: Fallback - delete by metadata (for compatibility with old data)
            print(f"    🔍 Searching for embeddings by metadata for {file_path}")
            
            # Method 2.1: Search by file_path ONLY to find ALL embeddings regardless of repo_path
            print(f"    🔍 Searching for ALL embeddings with file_path='{file_path}' (any repo_path)")
            try:
                file_only_filter = Filter(
                    must=[
                        FieldCondition(key="file_path", match=MatchValue(value=file_path))
                    ]
                )
                
                # Get ALL embeddings for this file_path (regardless of repo_path)
                scroll_result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=file_only_filter,
                    limit=100,
                    with_payload=True  # Get payload to see repo_path variants
                )
                
                if scroll_result[0]:
                    all_file_embeddings = scroll_result[0]
                    print(f"    🔍 Found {len(all_file_embeddings)} total embeddings for {file_path}")
                    
                    # Show what we found
                    for emb in all_file_embeddings:
                        repo_path_found = emb.payload.get('repo_path', 'unknown')
                        indexed_at = emb.payload.get('indexed_at', 'unknown')
                        print(f"      - ID {emb.id}: repo_path='{repo_path_found}', indexed_at='{indexed_at}'")
                    
                    # Delete ALL of them
                    all_ids = [point.id for point in all_file_embeddings]
                    self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=all_ids
                    )
                    deleted_count = len(all_ids)
                    print(f"    🗑️ Deleted ALL {deleted_count} embeddings for {file_path}")
                    
                else:
                    print(f"    ℹ️ No embeddings found for file_path='{file_path}'")
                    
            except Exception as search_error:
                print(f"    ❌ Error searching for all embeddings: {search_error}")
                
                # Fallback: Try multiple repo_path formats
                possible_repo_paths = [
                    repo_url,  # Current format: https://github.com/...
                    f"C:\\Users\\b.m.reddy\\Documents\\SDLC-Automation\\FMCG-mobile",  # Old local path
                    f"local_repo_FMCG-mobile"  # Old fallback format
                ]
                
                for repo_path_variant in possible_repo_paths:
                    try:
                        file_filter = Filter(
                            must=[
                                FieldCondition(key="repo_path", match=MatchValue(value=repo_path_variant)),
                                FieldCondition(key="file_path", match=MatchValue(value=file_path))
                            ]
                        )
                        
                        scroll_result = self.qdrant_client.scroll(
                            collection_name=self.collection_name,
                            scroll_filter=file_filter,
                            limit=100,
                            with_payload=False
                        )
                        
                        if scroll_result[0]:
                            found_ids = [point.id for point in scroll_result[0]]
                            print(f"    🔍 Found {len(found_ids)} embeddings with repo_path='{repo_path_variant}'")
                            
                            self.qdrant_client.delete(
                                collection_name=self.collection_name,
                                points_selector=found_ids
                            )
                            deleted_count += len(found_ids)
                            print(f"    🗑️ Deleted {len(found_ids)} embeddings for {file_path}")
                            
                    except Exception as variant_error:
                        print(f"    ⚠ No embeddings found for repo_path='{repo_path_variant}'")
                        continue
            
            if deleted_count > 0:
                print(f"    ✅ Total deleted embeddings for {file_path}: {deleted_count}")
            else:
                print(f"    ℹ️ No existing embeddings found for {file_path}")
            
            return deleted_count
            
        except Exception as e:
            print(f"    ❌ Error: Could not delete old embeddings for {file_path}: {e}")
            return 0
    
    def _create_single_file_embedding(self, full_file_path: str, relative_file_path: str, repo_url: str) -> int:
        """
        Create embedding for a single file using EXISTING payload format
        This maintains compatibility with your current system
        """
        import time
        max_retries = 5
        wait_time = 15  # seconds
        
        for attempt in range(max_retries):
            try:
                # Read file content
                with open(full_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if not content.strip():
                    print(f"    ⏭️ Skipping empty file: {relative_file_path}")
                    return None
                
                file_path_obj = Path(full_file_path)
                file_name = file_path_obj.name
                file_extension = file_path_obj.suffix
                
                # Create file data dict (same format as existing RepoIndexer)
                file_data = {
                    'file_path': relative_file_path,
                    'file_name': file_name,
                    'file_extension': file_extension,
                    'file_content': content,
                    'file_size_lines': len(content.split('\n')),
                    'is_dependency': file_name in DEPENDENCY_FILES,
                    'absolute_path': str(full_file_path),
                    'repo_path': repo_url  # Use repo_url as identifier
                }
                
                # Generate summary using existing method (Gemini 2.5 Pro)
                summary = self.generate_file_summary(content, relative_file_path)
                
                # Extract metadata using existing method
                metadata = self.extract_metadata(content, file_extension)
                
                # Create embedding text using existing method
                embedding_text = self.create_embedding_text(file_data, summary, metadata)
                
                # Generate embedding using existing method (Vertex AI) with retry logic
                embedding = self.embeddings.embed_query(embedding_text)
                
                # Create payload with EXACT same format as existing system
                payload = {
                    'file_path': file_data['file_path'],
                    'file_name': file_data['file_name'],
                    'file_extension': file_data['file_extension'],
                    'file_content': file_data['file_content'],
                    'file_summary': summary,
                    'file_size_lines': file_data['file_size_lines'],
                    'primary_functions': metadata['primary_functions'],
                    'dependencies': metadata['dependencies'],
                    'classes': metadata['classes'],
                    'is_dependency': file_data['is_dependency'],
                    'repo_path': file_data['repo_path'],
                    'indexed_at': datetime.now().isoformat(),
                }
                
                # Get next available ID
                next_id = self._get_next_point_id()
                
                # Create point and upsert
                from qdrant_client.models import PointStruct
                point = PointStruct(
                    id=next_id,
                    vector=embedding,
                    payload=payload
                )
                
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[point]
                )
                
                return next_id  # Return the embedding ID
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a quota/rate limit error
                if ('quota' in error_msg or 'rate' in error_msg or '429' in error_msg or 
                    'resource_exhausted' in error_msg or 'timeout' in error_msg or
                    'read operation timed out' in error_msg):
                    
                    if attempt < max_retries - 1:
                        print(f"    ⚠️ Quota/Rate limit hit while creating embedding for {relative_file_path}. "
                              f"Waiting {wait_time}s... (Retry {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"    ❌ Max retries ({max_retries}) reached for {relative_file_path} due to quota limits")
                        return None
                else:
                    # For non-quota errors, fail immediately
                    print(f"    ❌ Error creating embedding for {relative_file_path}: {e}")
                    return None
        
        # Should not reach here, but just in case
        return None
    
    def _get_next_point_id(self) -> int:
        """
        Get the next available ID for a point
        Simple implementation - you might want to make this more robust
        """
        import time
        return int(time.time() * 1000000)  # Use microsecond timestamp as ID
    
    def track_file_modification(self, repo_path: str, modified_file_path: str, 
                              developer_id: str, jira_ticket: str, 
                              modification_type: str = 'updated',
                              embedding_ids: list = None):
        """
        Track that a file has been modified by the current developer
        Called when the agent modifies files during its workflow
        """
        try:
            repo_url = get_repo_url_from_path(repo_path)
            relative_path = get_relative_path(modified_file_path, repo_path)
            
            # Track in MongoDB with embedding IDs
            self.file_tracker.track_file_modification(
                repo_url=repo_url,
                file_path=relative_path,
                developer_id=developer_id,
                jira_ticket=jira_ticket,
                modification_type=modification_type,
                embedding_ids=embedding_ids  # ✨ NEW: Pass embedding IDs
            )
            
        except Exception as e:
            print(f"❌ Error tracking file modification: {e}")
    
    def get_repository_tracking_stats(self, repo_path: str) -> Dict[str, Any]:
        """Get tracking statistics for a repository"""
        try:
            repo_url = get_repo_url_from_path(repo_path)
            return self.file_tracker.get_repository_stats(repo_url)
        except Exception as e:
            return {'error': str(e)}

def create_incremental_indexer(service_account_path: str, project_id: str,
                              qdrant_url: str, qdrant_api_key: str, 
                              collection_name: str) -> IncrementalIndexer:
    """Factory function to create an incremental indexer"""
    return IncrementalIndexer(service_account_path, project_id, qdrant_url, qdrant_api_key, collection_name)

