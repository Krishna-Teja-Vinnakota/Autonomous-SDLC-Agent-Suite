"""
Vector Search - Semantic search over indexed repository
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_google_vertexai import VertexAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


class VectorSearch:
    """Handles semantic search over indexed repositories"""
    
    def __init__(self, service_account_path: str, project_id: str,
                 qdrant_url: str, qdrant_api_key: str, collection_name: str):
        """Initialize vector search with credentials"""
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
        
        # Initialize embedding model (same as indexer)
        self.embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004",
            project=project_id
        )
        
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key
        )
        
        self.collection_name = collection_name
    
    def search_relevant_files(self, query: str, repo_path: str, 
                             top_k: int = 12, 
                             include_dependencies: bool = True) -> List[Dict[str, Any]]:
        """
        Search for files relevant to the query
        
        Args:
            query: Search query (typically Jira ticket content)
            repo_path: Repository path to filter by
            top_k: Number of results to return
            include_dependencies: Whether to include dependency files in results
            
        Returns:
            List of file data dictionaries
        """
        try:
            print(f"\n🔍 Searching for relevant files...")
            print(f"Query: {query[:100]}...")
            print(f"Repo: {repo_path}")
            print(f"Top K: {top_k}\n")
            
            # Create query embedding
            query_vector = self.embeddings.embed_query(query)
            
            # Create filter for repo_path - try multiple formats to catch all embeddings
            import os
            github_repo_url = os.getenv("GITHUB_REPO_URL", "")
            
            possible_repo_paths = [
                str(Path(repo_path).resolve()),  # Original logic
                github_repo_url,  # GitHub URL from env
                f"C:\\Users\\b.m.reddy\\Documents\\SDLC-Automation\\FMCG-mobile",  # Old local path
                f"local_repo_FMCG-mobile"  # Old fallback format
            ]
            
            # Remove duplicates and empty values
            unique_repo_paths = list(set([p for p in possible_repo_paths if p]))
            
            print(f"🔍 Searching with multiple repo_path formats: {unique_repo_paths}")
            
            # Create OR filter to match any of the possible repo paths
            repo_filter = Filter(
                should=[
                    FieldCondition(
                        key="repo_path", 
                        match=MatchValue(value=path)
                    ) for path in unique_repo_paths
                ]
            )
            
            # Search Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=repo_filter,
                limit=top_k,
                with_payload=True
            )
            
            # Process results
            results = []
            for idx, result in enumerate(search_results, 1):
                payload = result.payload
                score = result.score
                
                # Skip dependency files if not requested
                if not include_dependencies and payload.get('is_dependency', False):
                    continue
                
                file_data = {
                    'file_path': payload['file_path'],
                    'file_name': payload['file_name'],
                    'file_extension': payload['file_extension'],
                    'file_content': payload['file_content'],
                    'file_summary': payload['file_summary'],
                    'file_size_lines': payload['file_size_lines'],
                    'primary_functions': payload.get('primary_functions', []),
                    'dependencies': payload.get('dependencies', []),
                    'classes': payload.get('classes', []),
                    'is_dependency': payload.get('is_dependency', False),
                    'similarity_score': score,
                    'rank': idx,
                    'vector_db_id': result.id  # ✨ NEW: Capture the vector DB ID
                }
                
                results.append(file_data)
                
                print(f"[{idx}] {payload['file_path']} (score: {score:.4f}, ID: {result.id})")
                print(f"    Summary: {payload['file_summary'][:100]}...")
            
            print(f"\n✓ Found {len(results)} relevant files\n")
            
            return results
            
        except Exception as e:
            print(f"✗ Search error: {str(e)}")
            raise
    
    def search_with_filters(self, query: str, repo_path: str,
                           file_extensions: Optional[List[str]] = None,
                           exclude_paths: Optional[List[str]] = None,
                           top_k: int = 12) -> List[Dict[str, Any]]:
        """
        Advanced search with filters
        
        Args:
            query: Search query
            repo_path: Repository path
            file_extensions: Only include files with these extensions (e.g., ['.js', '.jsx'])
            exclude_paths: Exclude files matching these paths (e.g., ['test/', 'spec/'])
            top_k: Number of results
            
        Returns:
            List of file data dictionaries
        """
        try:
            # Get all results first
            all_results = self.search_relevant_files(query, repo_path, top_k=top_k * 2)
            
            # Apply filters
            filtered_results = []
            
            for result in all_results:
                # Filter by extension
                if file_extensions:
                    if result['file_extension'] not in file_extensions:
                        continue
                
                # Filter by path exclusion
                if exclude_paths:
                    should_exclude = False
                    for exclude_path in exclude_paths:
                        if exclude_path in result['file_path']:
                            should_exclude = True
                            break
                    if should_exclude:
                        continue
                
                filtered_results.append(result)
                
                if len(filtered_results) >= top_k:
                    break
            
            return filtered_results
            
        except Exception as e:
            print(f"✗ Search with filters error: {str(e)}")
            raise
    
    def get_file_by_path(self, repo_path: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific file by its path
        
        Args:
            repo_path: Repository path
            file_path: Relative file path within repo
            
        Returns:
            File data dictionary or None if not found
        """
        try:
            # Create filter
            file_filter = Filter(
                must=[
                    FieldCondition(
                        key="repo_path",
                        match=MatchValue(value=str(Path(repo_path).resolve()))
                    ),
                    FieldCondition(
                        key="file_path",
                        match=MatchValue(value=file_path)
                    )
                ]
            )
            
            # Search with dummy vector (we're filtering by exact match)
            dummy_vector = [0.0] * 768
            
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=dummy_vector,
                query_filter=file_filter,
                limit=1,
                with_payload=True
            )
            
            if results:
                payload = results[0].payload
                return {
                    'file_path': payload['file_path'],
                    'file_name': payload['file_name'],
                    'file_extension': payload['file_extension'],
                    'file_content': payload['file_content'],
                    'file_summary': payload['file_summary'],
                    'file_size_lines': payload['file_size_lines'],
                    'primary_functions': payload.get('primary_functions', []),
                    'dependencies': payload.get('dependencies', []),
                    'classes': payload.get('classes', []),
                    'is_dependency': payload.get('is_dependency', False),
                }
            
            return None
            
        except Exception as e:
            print(f"✗ Get file error: {str(e)}")
            return None
    
    def check_repo_indexed(self, repo_path: str) -> bool:
        """Check if a repository is already indexed"""
        try:
            # Try to get count of points for this repo
            repo_filter = Filter(
                must=[
                    FieldCondition(
                        key="repo_path",
                        match=MatchValue(value=str(Path(repo_path).resolve()))
                    )
                ]
            )
            
            # Use scroll to count
            result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=repo_filter,
                limit=1,
                with_payload=False
            )
            
            return len(result[0]) > 0
            
        except Exception as e:
            print(f"⚠ Warning: Could not check if repo is indexed: {str(e)}")
            return False


def create_vector_search(service_account_path: str, project_id: str,
                        qdrant_url: str, qdrant_api_key: str,
                        collection_name: str) -> VectorSearch:
    """Factory function to create vector search instance"""
    return VectorSearch(service_account_path, project_id, qdrant_url, qdrant_api_key, collection_name)


