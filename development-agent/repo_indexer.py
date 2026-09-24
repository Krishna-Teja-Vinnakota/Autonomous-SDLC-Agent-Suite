"""
Repository Indexer - Creates vector embeddings for all code files
Stores in Qdrant for semantic search
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import traceback

from langchain_google_vertexai import VertexAIEmbeddings, ChatVertexAI
from langchain_core.messages import HumanMessage
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


# File extensions to index (programming files)
CODE_EXTENSIONS = {
    '.js', '.jsx', '.ts', '.tsx',  # JavaScript/TypeScript
    '.py', '.pyw',                  # Python
    '.java', '.kt', '.scala',       # JVM languages
    '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp',  # C/C++
    '.cs',                          # C#
    '.go',                          # Go
    '.rs',                          # Rust
    '.rb',                          # Ruby
    '.php',                         # PHP
    '.swift',                       # Swift
    '.m', '.mm',                    # Objective-C
    '.pl', '.pm',                   # Perl
    '.r', '.R',                     # R
    '.sh', '.bash', '.zsh',         # Shell
    '.sql',                         # SQL
    '.html', '.htm',                # HTML
    '.css', '.scss', '.sass', '.less',  # Stylesheets
    '.json', '.yaml', '.yml', '.xml', '.toml',  # Config
    '.md', '.mdx', '.rst',          # Documentation
    '.vue',                         # Vue
    '.svelte',                      # Svelte
    '.dart',                        # Dart
    '.lua',                         # Lua
    '.groovy',                      # Groovy
}

# Dependency/config files (index but mark as context-only)
DEPENDENCY_FILES = {
    'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'requirements.txt', 'Pipfile', 'Pipfile.lock', 'poetry.lock', 'setup.py', 'pyproject.toml',
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle',
    'Cargo.toml', 'Cargo.lock',
    'go.mod', 'go.sum',
    'composer.json', 'composer.lock',
    'Gemfile', 'Gemfile.lock',
    '.env.template', '.env.example',
    'tsconfig.json', 'jsconfig.json',
    'webpack.config.js', 'vite.config.js', 'rollup.config.js',
    'docker-compose.yml', 'Dockerfile',
    'Makefile', 'CMakeLists.txt',
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '__pycache__', '.git', '.svn', '.hg',
    'venv', '.venv', 'env', '.env',
    'dist', 'build', 'target', 'out', 'bin',
    '.idea', '.vscode', '.vs',
    'coverage', '.coverage', '.pytest_cache', '.tox',
    'vendor', 'bower_components',
}

# Binary/media files to skip
SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.exe', '.dll', '.so', '.dylib',
    '.pyc', '.pyo', '.class', '.o', '.obj',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
}


class RepoIndexer:
    """Indexes repository files into Qdrant vector database"""
    
    def __init__(self, service_account_path: str, project_id: str, 
                 qdrant_url: str, qdrant_api_key: str, collection_name: str):
        """Initialize the indexer with Vertex AI and Qdrant credentials"""
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
        
        # Initialize embedding model
        self.embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004",
            project=project_id
        )
        
        # Initialize LLM for summary generation
        self.llm = ChatVertexAI(
            model="gemini-2.5-pro",
            project=project_id,
            temperature=0.1,
            max_tokens=5000
        )
        
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key
        )
        
        self.collection_name = collection_name
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            from qdrant_client.models import PayloadSchemaType
            
            collections = self.qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                # text-embedding-004 produces 768-dimensional vectors
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
                )
                print(f"✓ Created Qdrant collection: {self.collection_name}")
            else:
                print(f"✓ Using existing Qdrant collection: {self.collection_name}")
            
            # Always ensure payload index exists for filtering
            try:
                self.qdrant_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="repo_path",
                    field_schema=PayloadSchemaType.KEYWORD
                )
                print(f"✓ Created payload index for repo_path field")
            except Exception as idx_error:
                # Index might already exist, that's fine
                error_msg = str(idx_error).lower()
                if "already" in error_msg or "exist" in error_msg:
                    print(f"✓ Payload index for repo_path already exists")
                else:
                    print(f"⚠ Warning creating index: {str(idx_error)}")
                
        except Exception as e:
            print(f"✗ Error setting up collection: {str(e)}")
            raise
    
    def scan_repository(self, repo_path: str) -> List[Dict[str, Any]]:
        """Scan repository and collect all relevant files"""
        files_data = []
        repo_path = Path(repo_path).resolve()
        
        print(f"🔍 Scanning repository: {repo_path}")
        
        for root, dirs, files in os.walk(repo_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            
            root_path = Path(root)
            
            for file in files:
                file_path = root_path / file
                relative_path = file_path.relative_to(repo_path)
                
                # Check if file should be indexed
                if not self._should_index_file(file_path):
                    continue
                
                try:
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Skip empty files
                    if not content.strip():
                        continue
                    
                    # Check if it's a dependency file
                    is_dependency = file in DEPENDENCY_FILES
                    
                    files_data.append({
                        'file_path': str(relative_path).replace('\\', '/'),
                        'file_name': file,
                        'file_extension': file_path.suffix,
                        'file_content': content,
                        'file_size_lines': len(content.split('\n')),
                        'is_dependency': is_dependency,
                        'absolute_path': str(file_path),
                        'repo_path': str(repo_path)
                    })
                    
                except Exception as e:
                    print(f"⚠ Warning: Could not read {relative_path}: {str(e)}")
                    continue
        
        print(f"✓ Found {len(files_data)} files to index")
        return files_data
    
    def _should_index_file(self, file_path: Path) -> bool:
        """Determine if a file should be indexed"""
        # Check extension
        if file_path.suffix.lower() in SKIP_EXTENSIONS:
            return False
        
        # Check if it's a code file or dependency file
        if file_path.suffix.lower() in CODE_EXTENSIONS or file_path.name in DEPENDENCY_FILES:
            return True
        
        return False
    
    def generate_file_summary(self, file_content: str, file_path: str, retry_count: int = 15) -> str:
        """Generate AI summary of file content with retry logic"""
        for attempt in range(retry_count):
            try:
                # For large files, take more content for better summary
                lines = file_content.split('\n')
                total_lines = len(lines)
                
                if total_lines > 1000:
                    # For very large files, sample from beginning, middle, and end
                    sample_size = 500
                    beginning = '\n'.join(lines[:sample_size])
                    middle_start = total_lines // 2 - sample_size // 2
                    middle = '\n'.join(lines[middle_start:middle_start + sample_size])
                    end = '\n'.join(lines[-sample_size:])
                    content_preview = f"{beginning}\n\n[...middle section...]\n\n{middle}\n\n[...end section...]\n\n{end}"
                    file_info = f" (Large file: {total_lines} lines, showing samples)"
                else:
                    content_preview = file_content[:8000] if len(file_content) > 8000 else file_content
                    file_info = f" ({total_lines} lines)"
                
                prompt = f"""Analyze this code file and provide a detailed 3-4 sentence summary.

File: {file_path}{file_info}

Code:
```
{content_preview}
```

Provide a comprehensive summary that includes:
1. The main purpose and functionality of this file
2. Key functions, components, classes, or modules it contains
3. What role it plays in the application architecture
4. Any important business logic or features it implements

Be specific and detailed. Summary:"""

                messages = [HumanMessage(content=prompt)]
                response = self.llm.invoke(messages)
                summary = response.content.strip()
                
                # Add small delay to avoid rate limits
                time.sleep(2)
                
                return summary
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for quota/rate limit errors
                if 'quota' in error_msg or 'rate' in error_msg or '429' in error_msg or 'resource_exhausted' in error_msg:
                    wait_time = 15
                    print(f"⚠ Quota limit hit for {file_path}. Waiting {wait_time}s before retry {attempt + 1}/15...")
                    time.sleep(wait_time)
                    
                    if attempt == retry_count - 1:
                        print(f"⚠ Max retries reached for {file_path}. Using fallback summary.")
                        return f"Code file: {file_path} - Unable to generate AI summary due to quota limits"
                else:
                    print(f"⚠ Warning: Could not generate summary for {file_path}: {str(e)}")
                    return f"Code file: {file_path}"
        
        return f"Code file: {file_path}"
    
    def extract_metadata(self, file_content: str, file_extension: str) -> Dict[str, Any]:
        """Extract metadata from file content"""
        metadata = {
            'primary_functions': [],
            'dependencies': [],
            'classes': [],
        }
        
        try:
            lines = file_content.split('\n')
            
            # Extract based on file type
            if file_extension in ['.js', '.jsx', '.ts', '.tsx']:
                # JavaScript/TypeScript
                for line in lines[:100]:  # Check first 100 lines
                    line_stripped = line.strip()
                    if line_stripped.startswith('import ') or line_stripped.startswith('require('):
                        metadata['dependencies'].append(line_stripped[:100])
                    if 'function ' in line or 'const ' in line and '=>' in line:
                        metadata['primary_functions'].append(line_stripped[:100])
                    if 'class ' in line or 'export default' in line:
                        metadata['classes'].append(line_stripped[:100])
            
            elif file_extension == '.py':
                # Python
                for line in lines[:100]:
                    line_stripped = line.strip()
                    if line_stripped.startswith('import ') or line_stripped.startswith('from '):
                        metadata['dependencies'].append(line_stripped[:100])
                    if line_stripped.startswith('def '):
                        metadata['primary_functions'].append(line_stripped[:100])
                    if line_stripped.startswith('class '):
                        metadata['classes'].append(line_stripped[:100])
            
            # Limit to first 10 items each
            metadata['primary_functions'] = metadata['primary_functions'][:10]
            metadata['dependencies'] = metadata['dependencies'][:10]
            metadata['classes'] = metadata['classes'][:5]
            
        except Exception as e:
            print(f"⚠ Warning: Could not extract metadata: {str(e)}")
        
        return metadata
    
    def create_embedding_text(self, file_data: Dict[str, Any], summary: str, metadata: Dict[str, Any]) -> str:
        """Create text to embed (combines all relevant information)"""
        parts = [
            f"File: {file_data['file_path']}",
            f"Name: {file_data['file_name']}",
            f"Summary: {summary}",
        ]
        
        if metadata['dependencies']:
            parts.append(f"Dependencies: {', '.join(metadata['dependencies'][:5])}")
        
        if metadata['primary_functions']:
            parts.append(f"Functions: {', '.join(metadata['primary_functions'][:5])}")
        
        if metadata['classes']:
            parts.append(f"Classes: {', '.join(metadata['classes'][:3])}")
        
        # Include full file content for better semantic matching
        # For very large files, use summary more heavily
        if len(file_data['file_content']) > 50000:
            # For huge files, embed summary + first/last sections
            content = file_data['file_content']
            parts.append(f"\nContent (Large file - key sections):\n{content[:25000]}\n[...]\n{content[-25000:]}")
        else:
            parts.append(f"\nContent:\n{file_data['file_content']}")
        
        return "\n".join(parts)
    
    def index_repository(self, repo_path: str, force_reindex: bool = True) -> Dict[str, Any]:
        """Index entire repository into Qdrant"""
        try:
            start_time = datetime.now()
            print(f"\n{'='*60}")
            print(f"🚀 Starting repository indexing")
            print(f"{'='*60}\n")
            
            # Delete existing points for this repo if force_reindex
            if force_reindex:
                print(f"🗑️ Clearing existing index for: {repo_path}")
                try:
                    # Delete all points with this repo_path
                    self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector={
                            "filter": {
                                "must": [
                                    {
                                        "key": "repo_path",
                                        "match": {"value": str(Path(repo_path).resolve())}
                                    }
                                ]
                            }
                        }
                    )
                    print("✓ Cleared existing index")
                except Exception as e:
                    print(f"⚠ Warning: Could not clear index: {str(e)}")
            
            # Scan repository
            files_data = self.scan_repository(repo_path)
            
            if not files_data:
                return {
                    "success": False,
                    "error": "No files found to index",
                    "files_indexed": 0
                }
            
            # Process files in batches
            points = []
            total_files = len(files_data)
            
            print(f"\n📝 Processing {total_files} files...\n")
            
            for idx, file_data in enumerate(files_data, 1):
                retry_count = 15
                processed = False
                
                for attempt in range(retry_count):
                    try:
                        print(f"[{idx}/{total_files}] Processing: {file_data['file_path']} ({file_data['file_size_lines']} lines)")
                        
                        # Generate summary with retry logic
                        summary = self.generate_file_summary(
                            file_data['file_content'],
                            file_data['file_path'],
                            retry_count=15
                        )
                        
                        # Extract metadata
                        metadata = self.extract_metadata(
                            file_data['file_content'],
                            file_data['file_extension']
                        )
                        
                        # Create embedding text
                        embedding_text = self.create_embedding_text(file_data, summary, metadata)
                        
                        # Generate embedding with retry logic
                        try:
                            embedding = self.embeddings.embed_query(embedding_text)
                            # Small delay after successful embedding
                            time.sleep(1)
                        except Exception as embed_error:
                            error_msg = str(embed_error).lower()
                            if 'quota' in error_msg or 'rate' in error_msg or '429' in error_msg or 'resource_exhausted' in error_msg:
                                wait_time = 15
                                print(f"  ⚠ Embedding quota limit. Waiting {wait_time}s... (attempt {attempt + 1}/15)")
                                time.sleep(wait_time)
                                
                                if attempt == retry_count - 1:
                                    raise embed_error
                                continue
                            else:
                                raise embed_error
                        
                        # Create payload
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
                        
                        # Create point
                        point = PointStruct(
                            id=idx,
                            vector=embedding,
                            payload=payload
                        )
                        
                        points.append(point)
                        processed = True
                        
                        # Upload in batches of 20 (smaller batches to avoid issues)
                        if len(points) >= 20:
                            self.qdrant_client.upsert(
                                collection_name=self.collection_name,
                                points=points
                            )
                            print(f"  ✓ Uploaded batch ({len(points)} files)")
                            points = []
                            # Small delay after batch upload
                            time.sleep(2)
                        
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        error_msg = str(e).lower()
                        if attempt < retry_count - 1 and ('quota' in error_msg or 'rate' in error_msg or '429' in error_msg or 'resource_exhausted' in error_msg):
                            wait_time = 15
                            print(f"  ⚠ Error processing {file_data['file_path']}. Waiting {wait_time}s... (attempt {attempt + 1}/15)")
                            print(f"     Error: {str(e)}")
                            time.sleep(wait_time)
                        else:
                            print(f"  ✗ Failed to process {file_data['file_path']}: {str(e)}")
                            if attempt == retry_count - 1:
                                traceback.print_exc()
                            break
            
            # Upload remaining points
            if points:
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                print(f"  ✓ Uploaded final batch ({len(points)} files)")
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            print(f"\n{'='*60}")
            print(f"✅ Indexing complete!")
            print(f"{'='*60}")
            print(f"📊 Total files indexed: {total_files}")
            print(f"⏱️ Time taken: {elapsed_time:.2f} seconds")
            print(f"📦 Collection: {self.collection_name}")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "files_indexed": total_files,
                "time_taken": elapsed_time,
                "repo_path": str(Path(repo_path).resolve())
            }
            
        except Exception as e:
            print(f"\n✗ Indexing failed: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "files_indexed": 0
            }


def create_indexer(service_account_path: str, project_id: str,
                   qdrant_url: str, qdrant_api_key: str, 
                   collection_name: str) -> RepoIndexer:
    """Factory function to create a repo indexer"""
    return RepoIndexer(service_account_path, project_id, qdrant_url, qdrant_api_key, collection_name)

