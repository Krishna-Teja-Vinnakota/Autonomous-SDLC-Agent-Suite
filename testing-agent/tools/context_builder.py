"""
Context Builder for Dependency-Aware Test Generation
Phase 1: Implements dependency-aware context building with import resolution
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import deque
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ContextBuildResult:
    """Result of context building operation"""
    context_bundle: Dict[str, str]  # filepath -> content
    files_included: List[str]  # List of relative file paths
    total_chars: int  # Total characters across all files
    truncated_files: List[str]  # Files that were truncated
    missing_imports: List[str]  # Imports that could not be resolved


def extract_imports(file_path: Path, content: str) -> List[str]:
    """
    Extract import statements from TS/TSX/JS/JSX files.
    
    Patterns to match:
    - import { X } from './relative'
    - import X from '../parent/file'
    - import * as X from './module'
    - const X = require('./file')  (optional, for legacy code)
    
    Args:
        file_path: Path to the file being parsed
        content: File content to parse
    
    Returns:
        List of import paths (e.g., ['./Button', '../hooks/useAuth'])
    """
    # Match ES6 imports
    import_pattern = r"import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+\w+|\w+))*\s+from\s+)?['\"]([^'\"]+)['\"]"
    
    # Match require statements (optional)
    require_pattern = r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
    
    imports = []
    imports.extend(re.findall(import_pattern, content))
    imports.extend(re.findall(require_pattern, content))
    
    # Filter to only relative imports (starts with . or ..)
    relative_imports = [imp for imp in imports if imp.startswith('.')]
    
    logger.debug(f"Extracted {len(relative_imports)} relative imports from {file_path.name}")
    return relative_imports


def resolve_import(
    import_path: str,
    from_file: Path,
    project_root: Path
) -> Optional[Path]:
    """
    Resolve a relative import to an actual file path.
    
    Algorithm:
    1. Resolve relative to from_file's directory
    2. Try extensions: .ts, .tsx, .js, .jsx
    3. Try index files: index.ts, index.tsx, index.js, index.jsx
    4. Return None if not found
    
    Args:
        import_path: Import path (e.g., './ui/Icon')
        from_file: Path to the file containing the import
        project_root: Root directory of the project
    
    Returns:
        Absolute Path to resolved file, or None if not found
    
    Example:
        from_file = 'src/components/Button.tsx'
        import_path = './ui/Icon'
        → Try: src/components/ui/Icon.ts
        → Try: src/components/ui/Icon.tsx
        → Try: src/components/ui/Icon/index.tsx
    """
    from_dir = from_file.parent
    target = (from_dir / import_path).resolve()
    
    # Try direct extensions
    for ext in ['.ts', '.tsx', '.js', '.jsx']:
        candidate = target.with_suffix(ext)
        if candidate.exists() and candidate.is_relative_to(project_root):
            logger.debug(f"Resolved {import_path} -> {candidate.relative_to(project_root)}")
            return candidate
    
    # Try with extension if target already has one
    if target.suffix and target.exists() and target.is_relative_to(project_root):
        logger.debug(f"Resolved {import_path} -> {target.relative_to(project_root)}")
        return target
    
    # Try index files if target is a directory
    if target.is_dir():
        for ext in ['.ts', '.tsx', '.js', '.jsx']:
            index_file = target / f'index{ext}'
            if index_file.exists() and index_file.is_relative_to(project_root):
                logger.debug(f"Resolved {import_path} -> {index_file.relative_to(project_root)} (index)")
                return index_file
    
    logger.debug(f"Could not resolve import: {import_path} from {from_file.relative_to(project_root)}")
    return None


def build_dependency_graph(
    target_file: Path,
    project_root: Path,
    max_depth: int
) -> List[Path]:
    """
    Build dependency graph using BFS traversal.
    
    Args:
        target_file: Absolute path to the target file
        project_root: Root directory of the project
        max_depth: Maximum import traversal depth
    
    Returns:
        List of Path objects in priority order:
        - Level 1: Direct imports from target
        - Level 2: Imports from level 1 files
        - ... up to max_depth
    """
    visited: Set[Path] = set()
    queue = deque([(target_file, 0)])  # (file, depth)
    dependency_order = []
    
    while queue:
        current_file, current_depth = queue.popleft()
        
        if current_file in visited or current_depth > max_depth:
            continue
        
        visited.add(current_file)
        if current_file != target_file:  # Don't include target itself
            dependency_order.append(current_file)
        
        # Only traverse deeper if within depth limit
        if current_depth < max_depth:
            try:
                content = current_file.read_text(encoding='utf-8', errors='ignore')
                imports = extract_imports(current_file, content)
                
                for imp in imports:
                    resolved = resolve_import(imp, current_file, project_root)
                    if resolved and resolved not in visited:
                        queue.append((resolved, current_depth + 1))
                        
            except Exception as e:
                logger.warning(f"Error reading {current_file}: {e}")
                continue
    
    logger.info(f"Built dependency graph: {len(dependency_order)} dependencies found")
    return dependency_order


def read_and_truncate(file_path: Path, max_chars: int) -> str:
    """
    Read file and truncate to max_chars.
    
    Args:
        file_path: Path to file to read
        max_chars: Maximum characters to return
    
    Returns:
        File content (truncated if necessary)
    """
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        if len(content) > max_chars:
            return content[:max_chars] + "\n... [truncated]"
        return content
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return f"// Error reading file: {e}"


def should_exclude(file_path: Path) -> bool:
    """
    Check if file should be excluded from context.
    
    Args:
        file_path: Path to check
    
    Returns:
        True if file should be excluded
    """
    exclude_patterns = [
        'node_modules', '.next', 'dist', 'build', 'coverage',
        '.test.', '.spec.', '__tests__', '__mocks__',
        '.d.ts', '__pycache__', '.git', '.vscode'
    ]
    path_str = str(file_path)
    return any(pattern in path_str for pattern in exclude_patterns)


def find_same_folder_utilities(target_file: Path, project_root: Path) -> List[Path]:
    """
    Find utility files in the same folder as target.
    
    Args:
        target_file: The target file
        project_root: Root directory of the project
    
    Returns:
        List of utility file paths in the same folder
    """
    same_folder = target_file.parent
    utility_patterns = ['hook', 'util', 'helper', 'store', 'context', 'service']
    
    utilities = []
    
    # Check if folder exists
    if not same_folder.exists() or not same_folder.is_dir():
        return utilities
    
    # Iterate through files in the same folder
    for pattern in ['*.ts', '*.tsx', '*.js', '*.jsx']:
        for file in same_folder.glob(pattern):
            if file == target_file or should_exclude(file):
                continue
            if any(util_pattern in file.stem.lower() for util_pattern in utility_patterns):
                utilities.append(file)
    
    logger.debug(f"Found {len(utilities)} utility files in {same_folder.relative_to(project_root)}")
    return utilities


def build_context_bundle(
    project_root: Path,
    target_file: str,
    index_result,  # IndexResult type (avoid circular import)
    pinned_files: List[str] = None,
    depth: int = 2,
    max_files: int = 25,
    max_chars_per_file: int = 2000,
    max_total_chars: int = 25000
) -> ContextBuildResult:
    """
    Build a dependency-aware context bundle for a target file.
    
    Args:
        project_root: Root directory of the project
        target_file: Relative path to the target file (e.g., 'src/components/Button.tsx')
        index_result: Existing IndexResult from file_indexer
        pinned_files: Files to always include (user-selected)
        depth: Maximum import traversal depth (default: 2)
        max_files: Maximum number of files to include
        max_chars_per_file: Max characters per individual file
        max_total_chars: Total character budget across all files
    
    Returns:
        ContextBuildResult with context bundle and metadata
    """
    pinned_files = pinned_files or []
    context_bundle = {}
    total_chars = 0
    files_added = 0
    truncated_files = []
    missing_imports = []
    files_included = []
    
    target_path = project_root / target_file
    
    logger.info(f"Building context bundle for: {target_file}")
    logger.info(f"Budget: {max_files} files, {max_total_chars} total chars, {max_chars_per_file} per file")
    
    # Priority 1: Pinned files (always include)
    for pinned in pinned_files:
        if files_added >= max_files or total_chars >= max_total_chars:
            logger.info(f"Budget exhausted during pinned files phase")
            break
        
        pinned_path = project_root / pinned
        if not pinned_path.exists():
            logger.warning(f"Pinned file not found: {pinned}")
            continue
        
        if should_exclude(pinned_path):
            logger.debug(f"Skipping excluded pinned file: {pinned}")
            continue
        
        # Read and check if truncation is needed
        try:
            full_content = pinned_path.read_text(encoding='utf-8', errors='ignore')
            was_truncated = len(full_content) > max_chars_per_file
            content = full_content[:max_chars_per_file] + "\n... [truncated]" if was_truncated else full_content
            
            if was_truncated:
                truncated_files.append(pinned)
            
            context_bundle[pinned] = content
            files_included.append(pinned)
            total_chars += len(content)
            files_added += 1
            logger.debug(f"Added pinned file: {pinned} ({len(content)} chars)")
        except Exception as e:
            logger.error(f"Error reading pinned file {pinned}: {e}")
            continue
    
    # Priority 2: Target file itself
    if files_added < max_files and total_chars < max_total_chars:
        if target_path.exists() and not should_exclude(target_path):
            if target_file not in context_bundle:
                try:
                    full_content = target_path.read_text(encoding='utf-8', errors='ignore')
                    was_truncated = len(full_content) > max_chars_per_file
                    content = full_content[:max_chars_per_file] + "\n... [truncated]" if was_truncated else full_content
                    
                    if was_truncated:
                        truncated_files.append(target_file)
                    
                    if total_chars + len(content) <= max_total_chars:
                        context_bundle[target_file] = content
                        files_included.append(target_file)
                        total_chars += len(content)
                        files_added += 1
                        logger.debug(f"Added target file: {target_file} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading target file: {e}")
    
    # Priority 3: Dependency graph
    if files_added < max_files and total_chars < max_total_chars:
        try:
            # Build dependency graph and track missing imports
            dependencies = []
            visited: Set[Path] = set()
            queue = deque([(target_path, 0)])
            
            while queue:
                current_file, current_depth = queue.popleft()
                
                if current_file in visited or current_depth > depth:
                    continue
                
                visited.add(current_file)
                if current_file != target_path:  # Don't include target itself
                    dependencies.append(current_file)
                
                # Only traverse deeper if within depth limit
                if current_depth < depth:
                    try:
                        content = current_file.read_text(encoding='utf-8', errors='ignore')
                        imports = extract_imports(current_file, content)
                        
                        for imp in imports:
                            resolved = resolve_import(imp, current_file, project_root)
                            if resolved and resolved not in visited:
                                queue.append((resolved, current_depth + 1))
                            elif not resolved:
                                # Track missing import
                                try:
                                    from_rel = str(current_file.relative_to(project_root))
                                    missing_imports.append(f"{imp} (from {from_rel})")
                                except ValueError:
                                    missing_imports.append(f"{imp} (from {current_file.name})")
                                
                    except Exception as e:
                        logger.warning(f"Error reading {current_file}: {e}")
                        continue
            
            logger.info(f"Built dependency graph: {len(dependencies)} dependencies found")
            
            # Add dependencies to context
            for dep_path in dependencies:
                if files_added >= max_files or total_chars >= max_total_chars:
                    logger.info(f"Budget exhausted during dependency phase")
                    break
                
                # Skip if already added (pinned or target)
                try:
                    rel_path = str(dep_path.relative_to(project_root))
                except ValueError:
                    continue  # Outside project root
                
                if rel_path in context_bundle:
                    continue
                
                # Skip excluded patterns
                if should_exclude(dep_path):
                    continue
                
                try:
                    full_content = dep_path.read_text(encoding='utf-8', errors='ignore')
                    was_truncated = len(full_content) > max_chars_per_file
                    content = full_content[:max_chars_per_file] + "\n... [truncated]" if was_truncated else full_content
                    
                    if was_truncated:
                        truncated_files.append(rel_path)
                    
                    # Check if adding this file would exceed budget
                    if total_chars + len(content) > max_total_chars:
                        logger.info(f"Would exceed total char budget, stopping at {files_added} files")
                        break
                    
                    context_bundle[rel_path] = content
                    files_included.append(rel_path)
                    total_chars += len(content)
                    files_added += 1
                    logger.debug(f"Added dependency: {rel_path} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading dependency {rel_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error building dependency graph: {e}")
    
    # Priority 4: Same-folder utilities (if budget allows)
    if files_added < max_files and total_chars < max_total_chars:
        try:
            same_folder_files = find_same_folder_utilities(target_path, project_root)
            
            for util_path in same_folder_files:
                if files_added >= max_files or total_chars >= max_total_chars:
                    logger.info(f"Budget exhausted during utility phase")
                    break
                
                try:
                    rel_path = str(util_path.relative_to(project_root))
                except ValueError:
                    continue
                
                if rel_path in context_bundle:
                    continue
                
                try:
                    full_content = util_path.read_text(encoding='utf-8', errors='ignore')
                    was_truncated = len(full_content) > max_chars_per_file
                    content = full_content[:max_chars_per_file] + "\n... [truncated]" if was_truncated else full_content
                    
                    if was_truncated:
                        truncated_files.append(rel_path)
                    
                    if total_chars + len(content) > max_total_chars:
                        break
                    
                    context_bundle[rel_path] = content
                    files_included.append(rel_path)
                    total_chars += len(content)
                    files_added += 1
                    logger.debug(f"Added utility: {rel_path} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading utility {rel_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error finding same-folder utilities: {e}")
    
    logger.info(f"Built context bundle: {files_added} files, {total_chars} chars")
    
    return ContextBuildResult(
        context_bundle=context_bundle,
        files_included=files_included,
        total_chars=total_chars,
        truncated_files=truncated_files,
        missing_imports=missing_imports
    )


# ============================================================================
# Backward Compatibility Wrapper for existing app.py integration
# ============================================================================

class ContextBuilder:
    """
    Backward-compatible wrapper class for the function-based implementation.
    Maintains compatibility with existing app.py code.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize context builder.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
    
    def build_context_bundle(
        self,
        target_file: str,
        index_result,
        pinned_files: List[str] = None,
        depth: int = 2,
        max_files: int = 25,
        max_chars_per_file: int = 2000,
        max_total_chars: int = 25000
    ) -> ContextBuildResult:
        """
        Build context bundle for target file with dependency awareness.
        
        Args:
            target_file: Target file path (relative to project root)
            index_result: Project indexing results
            pinned_files: Files to always include (optional)
            depth: How deep to traverse import graph (default 2)
            max_files: Maximum number of files to include (default 25)
            max_chars_per_file: Max characters per file (default 2000)
            max_total_chars: Max total characters (default 25000)
            
        Returns:
            ContextBuildResult: Result object with context bundle and metadata
        """
        return build_context_bundle(
            project_root=self.project_root,
        target_file=target_file,
        index_result=index_result,
        pinned_files=pinned_files,
        depth=depth,
        max_files=max_files,
        max_chars_per_file=max_chars_per_file,
        max_total_chars=max_total_chars
    )
