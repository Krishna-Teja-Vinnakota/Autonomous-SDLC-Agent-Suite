"""
File Indexer for analyzing project structure and contents
Provides comprehensive file analysis and categorization
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging
from dataclasses import dataclass, asdict
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Data class for file information"""
    path: str
    relative_path: str
    size: int
    extension: str
    category: str
    lines: Optional[int] = None


@dataclass
class IndexResult:
    """Data class for indexing results"""
    total_files: int
    total_size: int
    total_lines: int
    files_by_category: Dict[str, int]
    files_by_extension: Dict[str, int]
    file_list: List[FileInfo]
    directory_tree: Dict[str, any]


class FileIndexer:
    """
    Tool for indexing and analyzing project files
    Categorizes files and provides project structure insights
    """

    # File categories
    CATEGORY_MAP = {
        # Source code
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.cs': 'C#',
        '.go': 'Go',
        '.rs': 'Rust',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        
        # Web
        '.html': 'HTML',
        '.htm': 'HTML',
        '.css': 'CSS',
        '.scss': 'CSS',
        '.sass': 'CSS',
        '.less': 'CSS',
        
        # Data/Config
        '.json': 'Config',
        '.yaml': 'Config',
        '.yml': 'Config',
        '.toml': 'Config',
        '.ini': 'Config',
        '.xml': 'Config',
        '.env': 'Config',
        
        # Documentation
        '.md': 'Documentation',
        '.rst': 'Documentation',
        '.txt': 'Documentation',
        
        # Tests
        '.test.js': 'Test',
        '.test.ts': 'Test',
        '.test.jsx': 'Test',
        '.test.tsx': 'Test',
        '.spec.js': 'Test',
        '.spec.ts': 'Test',
        
        # Database
        '.sql': 'Database',
        '.db': 'Database',
        '.sqlite': 'Database',
        
        # Other
        '.sh': 'Script',
        '.bat': 'Script',
        '.ps1': 'Script',
    }

    # Directories to ignore
    IGNORE_DIRS = {
        '__pycache__',
        'node_modules',
        '.git',
        '.venv',
        'venv',
        'env',
        '.pytest_cache',
        '.coverage',
        'dist',
        'build',
        '.next',
        '.nuxt',
        'coverage',
        '.idea',
        '.vscode',
        'vendor',
    }

    # Files to ignore
    IGNORE_FILES = {
        '.DS_Store',
        'Thumbs.db',
        '.gitignore',
        '.dockerignore',
    }

    # Extensions to count lines for
    TEXT_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
        '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt',
        '.html', '.css', '.scss', '.sass', '.less',
        '.json', '.yaml', '.yml', '.toml', '.xml',
        '.md', '.txt', '.sql', '.sh', '.bat'
    }

    @staticmethod
    def get_file_category(file_path: Path) -> str:
        """
        Determine file category based on extension
        
        Args:
            file_path: Path to file
            
        Returns:
            str: File category
        """
        name = file_path.name.lower()
        suffix = file_path.suffix.lower()
        
        # Check for test files first - comprehensive detection
        # Patterns: .test.js, .spec.js, test_*.py, *_test.py, files in __tests__/ or tests/ directories
        if '.test.' in name or '.spec.' in name:
            return 'Test'
        
        # Python test file patterns
        if name.startswith('test_') and suffix == '.py':
            return 'Test'
        if name.endswith('_test.py'):
            return 'Test'
        
        # Check if file is in a test directory
        try:
            parts = file_path.parts
            for part in parts:
                if part.lower() in ['__tests__', 'tests', 'test', 'spec']:
                    return 'Test'
        except Exception:
            pass
        
        # Check category map
        if suffix in FileIndexer.CATEGORY_MAP:
            return FileIndexer.CATEGORY_MAP[suffix]
        
        return 'Other'

    @staticmethod
    def count_lines(file_path: Path) -> Optional[int]:
        """
        Count lines in a text file (optimized for speed)
        
        Args:
            file_path: Path to file
            
        Returns:
            Optional[int]: Number of lines or None if unable to count
        """
        try:
            if file_path.suffix.lower() not in FileIndexer.TEXT_EXTENSIONS:
                return None
            
            # Optimized: read file in binary mode and count newlines (much faster)
            # This avoids UTF-8 decoding overhead for simple line counting
            # Count newline characters directly from binary data
            with open(file_path, 'rb') as f:
                # Read entire file in chunks for better performance on small files
                # For files < 500KB, reading all at once is faster than line-by-line
                data = f.read()
                if not data:
                    return 0
                # Count newlines (works for both \n and \r\n)
                count = data.count(b'\n')
                # If file doesn't end with newline, add 1 for the last line
                if not data.endswith(b'\n'):
                    count += 1
                return count
        except Exception as e:
            logger.debug(f"Could not count lines in {file_path}: {e}")
            return None

    @staticmethod
    def should_ignore(path: Path, root_path: Path) -> bool:
        """
        Check if path should be ignored
        
        Args:
            path: Path to check
            root_path: Root path of project
            
        Returns:
            bool: True if should be ignored
        """
        # Check if any parent directory is in ignore list
        try:
            relative = path.relative_to(root_path)
            for part in relative.parts:
                if part in FileIndexer.IGNORE_DIRS:
                    return True
        except ValueError:
            return False
        
        # Check if file is in ignore list
        if path.name in FileIndexer.IGNORE_FILES:
            return True
        
        return False

    @staticmethod
    def build_directory_tree(root_path: Path, max_depth: int = 3) -> Dict:
        """
        Build a directory tree structure
        
        Args:
            root_path: Root path to build tree from
            max_depth: Maximum depth to traverse
            
        Returns:
            Dict: Directory tree structure
        """
        def _build_tree(path: Path, current_depth: int) -> Dict:
            if current_depth > max_depth:
                return {}
            
            tree = {'files': [], 'dirs': {}}
            
            try:
                for item in sorted(path.iterdir()):
                    if FileIndexer.should_ignore(item, root_path):
                        continue
                    
                    if item.is_file():
                        tree['files'].append(item.name)
                    elif item.is_dir():
                        tree['dirs'][item.name] = _build_tree(item, current_depth + 1)
            except PermissionError:
                pass
            
            return tree
        
        return _build_tree(root_path, 0)

    @staticmethod
    def index_directory(
        root_path: Path,
        include_lines: bool = True
    ) -> Tuple[bool, str, Optional[IndexResult]]:
        """
        Index all files in a directory
        
        Args:
            root_path: Root directory to index
            include_lines: Whether to count lines in files
            
        Returns:
            Tuple[bool, str, Optional[IndexResult]]: (success, message, result)
        """
        try:
            if not root_path.exists():
                return False, f"Path does not exist: {root_path}", None

            if not root_path.is_dir():
                return False, f"Path is not a directory: {root_path}", None

            logger.info(f"Indexing directory: {root_path}")

            file_list: List[FileInfo] = []
            total_size = 0
            total_lines = 0
            files_by_category = defaultdict(int)
            files_by_extension = defaultdict(int)

            # Walk through directory
            for file_path in root_path.rglob('*'):
                # Skip ignored paths
                if FileIndexer.should_ignore(file_path, root_path):
                    continue

                # Only process files
                if not file_path.is_file():
                    continue

                try:
                    # Get file info
                    size = file_path.stat().st_size
                    extension = file_path.suffix.lower() or 'no_extension'
                    category = FileIndexer.get_file_category(file_path)
                    relative_path = str(file_path.relative_to(root_path))
                    
                    # Count lines if requested (skip for large files to improve performance)
                    lines = None
                    if include_lines:
                        # Skip line counting for files larger than 1MB to improve performance
                        if size < 1024 * 1024:  # Only count lines for files < 1MB
                            lines = FileIndexer.count_lines(file_path)
                            if lines:
                                total_lines += lines
                        else:
                            logger.debug(f"Skipping line count for large file: {file_path.name} ({size} bytes)")

                    # Create file info
                    file_info = FileInfo(
                        path=str(file_path),
                        relative_path=relative_path,
                        size=size,
                        extension=extension,
                        category=category,
                        lines=lines
                    )

                    file_list.append(file_info)
                    total_size += size
                    files_by_category[category] += 1
                    files_by_extension[extension] += 1

                except Exception as e:
                    logger.warning(f"Error processing file {file_path}: {e}")
                    continue

            # Build directory tree
            directory_tree = FileIndexer.build_directory_tree(root_path)

            # Create result
            result = IndexResult(
                total_files=len(file_list),
                total_size=total_size,
                total_lines=total_lines,
                files_by_category=dict(files_by_category),
                files_by_extension=dict(files_by_extension),
                file_list=file_list,
                directory_tree=directory_tree
            )

            logger.info(f"Successfully indexed {len(file_list)} files")
            return True, f"Successfully indexed {len(file_list)} files", result

        except Exception as e:
            error_msg = f"Error indexing directory: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        Format byte size to human-readable string
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            str: Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

