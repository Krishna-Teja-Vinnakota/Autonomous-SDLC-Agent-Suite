"""
AutoSDLC-Test-Agent - Streamlit UI
Main entry point for the autonomous SDLC testing agent
"""

import streamlit as st
import uuid
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from tools.git_tool import GitTool
from tools.unzip_tool import UnzipTool
from tools.file_indexer import FileIndexer
from config.vertex_ai import get_gemini_client
from config.testing_patterns import (
    detect_test_infrastructure, 
    get_mock_factory_names, 
    get_test_utils_exports
)
from agents.analyze_agent import AnalyzeAgent, ProjectAnalysisResult
from agents.strategy_agent import StrategyAgent, TestStrategyResult
from agents.test_generator_agent import TestGeneratorAgent, GeneratedTest
from agents.test_executor_agent import TestExecutorAgent, TestExecutionResult
from agents.failure_analyzer_agent import FailureAnalyzerAgent
from agents.report_agent import ReportAgent
from workflows.langgraph_flow import WorkflowOrchestrator, WorkflowState
import plotly.graph_objects as go
import plotly.express as px

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
WORKSPACE_ROOT = Path("workspaces")
TEMP_DIR = Path("temp")


def get_session_state():
    """Get session state, using fallback if not available"""
    # Initialize fallback state if needed
    if not hasattr(st, '_fallback_state'):
        st._fallback_state = {
            'run_id': None,
            'project_path': None,
            'index_result': None,
            'analysis_result': None,
            'processing_status': [],
            'metadata': {},
            'gemini_available': None,
            'test_strategy_result': None,
            'generated_tests': None,
            'execution_results': {},
            'failure_analyses': {},
            'unified_report': None,
            'workflow_result': None,
            'workflow_state': None,
            'infrastructure': None
        }
    
    # Try to use real session state, fall back to dict if it fails
    try:
        # Test if session state is functional by trying to check for a key
        # This will fail if session state is not properly initialized
        _ = 'run_id' in st.session_state
        return st.session_state
    except (AttributeError, RuntimeError, KeyError, Exception):
        # Session state not available or not functional, use fallback
        return st._fallback_state


def safe_get(key, default=None):
    """Safely get a value from session state"""
    session_state = get_session_state()
    try:
        # Try dictionary access first (works for fallback dict)
        if isinstance(session_state, dict):
            return session_state.get(key, default)
        # Try attribute access (works for real session state)
        return getattr(session_state, key, default)
    except (AttributeError, KeyError, RuntimeError):
        return default


def init_session_state():
    """Initialize Streamlit session state variables"""
    session_state = get_session_state()
    
    # Initialize all variables if they don't exist
    defaults = {
        'run_id': None,
        'project_path': None,
        'index_result': None,
        'analysis_result': None,
        'processing_status': [],
        'metadata': {},
        'gemini_available': None,
        'test_strategy_result': None,
        'generated_tests': None,
        'execution_results': {},
        'failure_analyses': {},
        'unified_report': None,
        'workflow_result': None,
        'workflow_state': None,
        'infrastructure': None,
        'test_levels_to_run': ['unit', 'integration', 'feature'],  # Initialize test levels
        'auto_run_workflow': False
    }
    
    for key, default_value in defaults.items():
        try:
            # Check if key exists
            if isinstance(session_state, dict):
                if key not in session_state:
                    session_state[key] = default_value
            else:
                # For real session state, try to get the value
                try:
                    _ = getattr(session_state, key)
                except AttributeError:
                    # Key doesn't exist, set it
                    setattr(session_state, key, default_value)
        except (AttributeError, KeyError, RuntimeError):
            # If setting fails, try dictionary assignment
            try:
                session_state[key] = default_value
            except (AttributeError, KeyError, RuntimeError):
                pass  # Skip if we can't set it


def safe_set(key, value):
    """Safely set a value in session state"""
    session_state = get_session_state()
    try:
        if isinstance(session_state, dict):
            session_state[key] = value
        else:
            setattr(session_state, key, value)
    except (AttributeError, KeyError, RuntimeError):
        # If setting fails, try to use fallback
        if not hasattr(st, '_fallback_state'):
            st._fallback_state = {}
        st._fallback_state[key] = value


def add_status(message: str, status: str = "info"):
    """
    Add a status message to the processing status list
    
    Args:
        message: Status message
        status: Status type (info, success, error, warning)
    """
    session_state = get_session_state()
    try:
        processing_status = safe_get('processing_status', [])
        if not isinstance(processing_status, list):
            processing_status = []
        processing_status.append({
            'message': message,
            'status': status
        })
        safe_set('processing_status', processing_status)
    except (AttributeError, KeyError, RuntimeError):
        # Fallback: create new list
        safe_set('processing_status', [{
            'message': message,
            'status': status
        }])


def create_sandbox_workspace(run_id: str) -> Path:
    """
    Create a sandbox workspace for the current run
    
    Args:
        run_id: Unique run identifier
        
    Returns:
        Path: Path to the project directory
    """
    workspace_path = WORKSPACE_ROOT / f"run_{run_id}"
    project_path = workspace_path / "project"
    project_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Created sandbox workspace: {workspace_path}")
    return project_path


def copy_file_to_sandbox(source_file: Path, project_path: Path) -> bool:
    """
    Copy a single file to the sandbox
    
    Args:
        source_file: Source file path
        project_path: Destination project path
        
    Returns:
        bool: Success status
    """
    try:
        dest_file = project_path / source_file.name
        shutil.copy2(source_file, dest_file)
        logger.info(f"Copied file: {source_file.name}")
        return True
    except Exception as e:
        logger.error(f"Error copying file: {e}")
        return False


def copy_folder_to_sandbox(source_folder: Path, project_path: Path) -> bool:
    """
    Copy a folder recursively to the sandbox
    
    Args:
        source_folder: Source folder path
        project_path: Destination project path
        
    Returns:
        bool: Success status
    """
    try:
        # Copy all contents of the source folder
        for item in source_folder.rglob('*'):
            if item.is_file():
                relative_path = item.relative_to(source_folder)
                dest_file = project_path / relative_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
        
        logger.info(f"Copied folder: {source_folder}")
        return True
    except Exception as e:
        logger.error(f"Error copying folder: {e}")
        return False


def handle_github_input(repo_url: str) -> bool:
    """
    Handle GitHub repository URL input
    
    Args:
        repo_url: GitHub repository URL
        
    Returns:
        bool: Success status
    """
    try:
        add_status("Starting GitHub repository clone...", "info")
        
        # Create sandbox workspace
        run_id = str(uuid.uuid4())
        st.session_state.run_id = run_id
        project_path = create_sandbox_workspace(run_id)
        st.session_state.project_path = project_path
        
        add_status(f"Created sandbox workspace: run_{run_id}", "success")
        
        # Clone repository
        add_status(f"Cloning repository: {repo_url}", "info")
        success, message, metadata = GitTool.clone_repository(repo_url, project_path)
        
        if not success:
            add_status(f"Failed to clone repository: {message}", "error")
            return False
        
        add_status(f"Successfully cloned repository", "success")
        st.session_state.metadata = metadata
        
        # Index files
        indexing_success = index_project(project_path)
        
        # Auto-run workflow if enabled
        if indexing_success and safe_get('auto_run_workflow', False):
            selected_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
            level_names = ', '.join([lvl.title() for lvl in selected_levels])
            add_status(f"Auto-running workflow for {level_names} tests...", "info")
            execute_full_workflow(project_path)
        
        return indexing_success
        
    except Exception as e:
        add_status(f"Error processing GitHub repository: {str(e)}", "error")
        logger.error(f"Error in handle_github_input: {e}")
        return False


def handle_zip_upload(uploaded_file) -> bool:
    """
    Handle ZIP file upload
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        bool: Success status
    """
    try:
        add_status("Starting ZIP file processing...", "info")
        
        # Create sandbox workspace
        run_id = str(uuid.uuid4())
        st.session_state.run_id = run_id
        project_path = create_sandbox_workspace(run_id)
        st.session_state.project_path = project_path
        
        add_status(f"Created sandbox workspace: run_{run_id}", "success")
        
        # Save uploaded ZIP file
        temp_dir = TEMP_DIR / run_id
        add_status("Saving uploaded ZIP file...", "info")
        success, message, zip_path = UnzipTool.save_uploaded_zip(uploaded_file, temp_dir)
        
        if not success:
            add_status(f"Failed to save ZIP file: {message}", "error")
            return False
        
        add_status("ZIP file saved successfully", "success")
        
        # Extract ZIP file
        add_status("Extracting ZIP file...", "info")
        success, message, metadata = UnzipTool.extract_zip(zip_path, project_path)
        
        if not success:
            add_status(f"Failed to extract ZIP file: {message}", "error")
            return False
        
        add_status(f"Successfully extracted ZIP file", "success")
        st.session_state.metadata = metadata
        
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Index files
        indexing_success = index_project(project_path)
        
        # Auto-run workflow if enabled
        if indexing_success and safe_get('auto_run_workflow', False):
            selected_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
            level_names = ', '.join([lvl.title() for lvl in selected_levels])
            add_status(f"Auto-running workflow for {level_names} tests...", "info")
            execute_full_workflow(project_path)
        
        return indexing_success
        
    except Exception as e:
        add_status(f"Error processing ZIP file: {str(e)}", "error")
        logger.error(f"Error in handle_zip_upload: {e}")
        return False


def handle_folder_upload(uploaded_files) -> bool:
    """
    Handle folder upload (multiple files)
    
    Args:
        uploaded_files: List of Streamlit UploadedFile objects
        
    Returns:
        bool: Success status
    """
    try:
        add_status("Starting folder upload processing...", "info")
        
        # Create sandbox workspace
        run_id = str(uuid.uuid4())
        st.session_state.run_id = run_id
        project_path = create_sandbox_workspace(run_id)
        st.session_state.project_path = project_path
        
        add_status(f"Created sandbox workspace: run_{run_id}", "success")
        
        # Save all uploaded files
        add_status(f"Uploading {len(uploaded_files)} files...", "info")
        
        for uploaded_file in uploaded_files:
            # Preserve directory structure from file name
            file_parts = Path(uploaded_file.name).parts
            dest_file = project_path / Path(*file_parts)
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dest_file, 'wb') as f:
                f.write(uploaded_file.getbuffer())
        
        add_status(f"Successfully uploaded {len(uploaded_files)} files", "success")
        
        st.session_state.metadata = {
            'uploaded_files': len(uploaded_files)
        }
        
        # Index files
        indexing_success = index_project(project_path)
        
        # Auto-run workflow if enabled
        if indexing_success and safe_get('auto_run_workflow', False):
            selected_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
            level_names = ', '.join([lvl.title() for lvl in selected_levels])
            add_status(f"Auto-running workflow for {level_names} tests...", "info")
            execute_full_workflow(project_path)
        
        return indexing_success
        
    except Exception as e:
        add_status(f"Error processing folder upload: {str(e)}", "error")
        logger.error(f"Error in handle_folder_upload: {e}")
        return False


def index_single_file(file_path: Path, project_path: Path) -> bool:
    """
    Fast indexing for single file uploads (optimized for speed)
    
    Args:
        file_path: Path to the single file
        project_path: Project root path
        
    Returns:
        bool: Success status
    """
    try:
        from tools.file_indexer import FileInfo, IndexResult
        
        # Skip status messages for single file to reduce overhead
        # add_status("Indexing file...", "info")
        
        # Get file info quickly (single stat call)
        stat_result = file_path.stat()
        size = stat_result.st_size
        extension = file_path.suffix.lower() or 'no_extension'
        category = FileIndexer.get_file_category(file_path)
        relative_path = str(file_path.relative_to(project_path))
        
        # Count lines only if it's a text file and reasonably sized (< 500KB for single files)
        # Reduced threshold for single files to speed up processing
        lines = None
        if size < 512 * 1024 and extension in FileIndexer.TEXT_EXTENSIONS:  # Only count lines for files < 500KB
            lines = FileIndexer.count_lines(file_path)
        
        # Create file info
        file_info = FileInfo(
            path=str(file_path),
            relative_path=relative_path,
            size=size,
            extension=extension,
            category=category,
            lines=lines
        )
        
        # Create minimal index result (avoid defaultdict overhead)
        files_by_category = {category: 1}
        files_by_extension = {extension: 1}
        
        index_result = IndexResult(
            total_files=1,
            total_size=size,
            total_lines=lines or 0,
            files_by_category=files_by_category,
            files_by_extension=files_by_extension,
            file_list=[file_info],
            directory_tree={'files': [file_path.name], 'dirs': {}}  # Minimal tree
        )
        
        safe_set('index_result', index_result)
        
        add_status(f"Successfully indexed file: {file_path.name}", "success")
        if lines:
            add_status(f"Lines of code: {lines:,}", "info")
        
        return True
        
    except Exception as e:
        add_status(f"Error indexing file: {str(e)}", "error")
        logger.error(f"Error in index_single_file: {e}")
        return False


def handle_single_file_upload(uploaded_file) -> bool:
    """
    Handle single file upload (optimized for speed)
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        bool: Success status
    """
    try:
        add_status("Starting single file upload...", "info")
        
        # Create sandbox workspace
        run_id = str(uuid.uuid4())
        safe_set('run_id', run_id)
        project_path = create_sandbox_workspace(run_id)
        safe_set('project_path', project_path)
        
        add_status(f"Created sandbox workspace: run_{run_id}", "success")
        
        # Save uploaded file
        add_status(f"Uploading file: {uploaded_file.name}", "info")
        dest_file = project_path / uploaded_file.name
        
        with open(dest_file, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        add_status(f"Successfully uploaded file: {uploaded_file.name}", "success")
        
        safe_set('metadata', {
            'filename': uploaded_file.name,
            'size': uploaded_file.size
        })
        
        # Use fast single-file indexing instead of full directory scan
        indexing_success = index_single_file(dest_file, project_path)
        
        # Automatically trigger AI analysis after indexing (if Gemini is available)
        if indexing_success:
            index_result = safe_get('index_result')
            if index_result:
                # Check Gemini availability and run analysis
                if safe_get('gemini_available') is None:
                    gemini_client = get_gemini_client()
                    safe_set('gemini_available', gemini_client is not None and gemini_client.is_ready() if gemini_client else False)
                
                if safe_get('gemini_available'):
                    analyze_project_with_ai(project_path, index_result)
                
                # Auto-run workflow if enabled
                if safe_get('auto_run_workflow', False):
                    add_status("Auto-running full workflow...", "info")
                    execute_full_workflow(project_path)
        
        return indexing_success
        
    except Exception as e:
        add_status(f"Error processing single file: {str(e)}", "error")
        logger.error(f"Error in handle_single_file_upload: {e}")
        return False


def analyze_project_with_ai(project_path: Path, index_result) -> None:
    """
    Analyze project using Vertex AI Gemini
    
    Args:
        project_path: Path to project directory
        index_result: File indexing results
    """
    try:
        # Check if Gemini is available (cached check)
        if st.session_state.gemini_available is None:
            add_status("Checking Vertex AI Gemini availability...", "info")
            gemini_client = get_gemini_client()
            st.session_state.gemini_available = gemini_client is not None
            
            if not st.session_state.gemini_available:
                add_status("Vertex AI not configured - skipping AI analysis", "warning")
                add_status("To enable: Set GOOGLE_APPLICATION_CREDENTIALS", "info")
                return
        elif not st.session_state.gemini_available:
            # Already know it's not available
            return
        
        # Get Gemini client
        add_status("Starting AI-powered project analysis...", "info")
        gemini_client = get_gemini_client()
        
        if not gemini_client or not gemini_client.is_ready():
            add_status("Gemini client not ready - skipping analysis", "warning")
            st.session_state.gemini_available = False
            return
        
        # Create analyze agent
        analyze_agent = AnalyzeAgent(gemini_client)
        
        # Run analysis
        add_status("Analyzing project with Gemini AI...", "info")
        analysis_result = analyze_agent.analyze_project(index_result, project_path)
        
        if analysis_result:
            st.session_state.analysis_result = analysis_result
            
            # Add summary to status
            add_status("AI Analysis complete!", "success")
            add_status(f"Detected: {', '.join(analysis_result.languages)}", "info")
            if analysis_result.frameworks:
                add_status(f"Frameworks: {', '.join(analysis_result.frameworks)}", "info")
        else:
            add_status("AI analysis failed - check logs", "warning")
            
    except Exception as e:
        logger.error(f"Error in AI analysis: {e}")
        add_status(f"AI analysis error: {str(e)}", "warning")


def index_project(project_path: Path) -> bool:
    """
    Index project files
    
    Args:
        project_path: Path to project directory
        
    Returns:
        bool: Success status
    """
    try:
        add_status("Starting file indexing...", "info")
        
        success, message, index_result = FileIndexer.index_directory(
            project_path,
            include_lines=True
        )
        
        if not success:
            add_status(f"Failed to index files: {message}", "error")
            return False
        
        st.session_state.index_result = index_result
        
        add_status(f"Successfully indexed {index_result.total_files} files", "success")
        add_status(f"Total size: {FileIndexer.format_size(index_result.total_size)}", "info")
        add_status(f"Total lines of code: {index_result.total_lines:,}", "info")
        
        # Detect testing infrastructure
        add_status("Detecting testing infrastructure...", "info")
        infrastructure = detect_test_infrastructure(project_path)
        st.session_state.infrastructure = infrastructure
        
        # Log infrastructure summary
        if infrastructure.has_msw() or infrastructure.has_factories():
            add_status("Testing infrastructure detected!", "success")
            if infrastructure.has_msw():
                add_status(f"Found MSW with {len(infrastructure.msw_handlers)} handler file(s)", "info")
            if infrastructure.has_factories():
                add_status(f"Found {len(infrastructure.factories)} mock factory file(s)", "info")
        else:
            add_status("No testing infrastructure detected - will use basic setup", "info")
        
        # Note: AI analysis now handled by workflow orchestrator
        # Keeping this for backward compatibility but workflow handles it
        
        return True
        
    except Exception as e:
        add_status(f"Error indexing project: {str(e)}", "error")
        logger.error(f"Error in index_project: {e}")
        return False


def display_index_results():
    """Display file indexing results in the UI"""
    if st.session_state.index_result is None:
        return
    
    result = st.session_state.index_result
    
    st.subheader("📊 Project Analysis")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", result.total_files)
    with col2:
        st.metric("Total Size", FileIndexer.format_size(result.total_size))
    with col3:
        st.metric("Lines of Code", f"{result.total_lines:,}")
    with col4:
        st.metric("Categories", len(result.files_by_category))
    
    # Infrastructure Detection Section
    infrastructure = safe_get('infrastructure')
    if infrastructure:
        with st.expander("🧪 Detected Testing Infrastructure", expanded=True):
            infra_summary = infrastructure.get_summary()
            
            # Color-code based on findings
            if "⚠ No testing infrastructure" in infra_summary:
                st.warning("**No testing infrastructure detected**")
                st.info("Tests will be generated with basic setup. Consider adding:")
                st.markdown("""
                - `jest.config.js` for Jest configuration
                - `mocks/server.ts` for MSW API mocking
                - `mocks/factories/` for mock data factories
                - `test-utils.tsx` for custom render utilities
                """)
            else:
                st.success("**Testing infrastructure detected:**")
                st.code(infra_summary, language='text')
                
                # Show specific details in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    if infrastructure.has_msw():
                        st.metric("MSW Handlers", len(infrastructure.msw_handlers))
                        with st.expander("View handler files"):
                            for handler in infrastructure.msw_handlers:
                                st.text(f"• {handler}")
                
                with col2:
                    if infrastructure.has_factories():
                        st.metric("Mock Factories", len(infrastructure.factories))
                        with st.expander("View factory files"):
                            # Try to extract factory function names
                            project_path = safe_get('project_path')
                            if project_path:
                                factory_names = get_mock_factory_names(project_path)
                                if factory_names:
                                    st.info("**Available factory functions:**")
                                    for factory in factory_names[:10]:  # Show first 10
                                        st.text(f"• {factory}()")
                                    if len(factory_names) > 10:
                                        st.text(f"... and {len(factory_names) - 10} more")
                                else:
                                    st.info("**Factory files:**")
                                    for factory_file in infrastructure.factories:
                                        st.text(f"• {factory_file}")
                            else:
                                st.info("**Factory files:**")
                                for factory_file in infrastructure.factories:
                                    st.text(f"• {factory_file}")
                
                # Test utilities
                if infrastructure.test_utils:
                    project_path = safe_get('project_path')
                    if project_path:
                        utils = get_test_utils_exports(project_path)
                        if utils:
                            st.info(f"**Test utilities available:** {', '.join(utils[:5])}")
                            if len(utils) > 5:
                                st.caption(f"... and {len(utils) - 5} more utilities")
                        else:
                            st.info("**Test utilities file detected**")
                    else:
                        st.info("**Test utilities file detected**")
    
    # Files by category
    st.subheader("📁 Files by Category")
    category_data = sorted(
        result.files_by_category.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    for category, count in category_data:
        st.text(f"{category}: {count} files")
    
    # Files by extension
    st.subheader("📝 Top File Extensions")
    extension_data = sorted(
        result.files_by_extension.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]  # Top 10
    
    for extension, count in extension_data:
        st.text(f"{extension}: {count} files")
    
    # Testing Infrastructure Metrics (if detected)
    infrastructure = safe_get('infrastructure')
    if infrastructure and (infrastructure.has_msw() or infrastructure.has_factories()):
        st.divider()
        st.subheader("🧪 Testing Infrastructure Summary")
        
        metrics_cols = st.columns(4)
        with metrics_cols[0]:
            st.metric("Jest Config", "✓" if infrastructure.jest_config else "✗")
        with metrics_cols[1]:
            st.metric("MSW Handlers", len(infrastructure.msw_handlers) if infrastructure.has_msw() else 0)
        with metrics_cols[2]:
            st.metric("Factories", len(infrastructure.factories) if infrastructure.has_factories() else 0)
        with metrics_cols[3]:
            st.metric("Test Utils", "✓" if infrastructure.test_utils else "✗")
    
    # ═══════════════════════════════════════════════════════════════════════
    # SINGLE-TARGET TEST GENERATION (with full repo context)
    # ═══════════════════════════════════════════════════════════════════════
    st.subheader("🎯 Generate Single Feature Test (Advanced)")
    st.caption("Select a single file and generate test(s) with full repository context")
    
    with st.container():
        # Filter to TS/TSX/JS/JSX files only
        source_files = [
            f.relative_path for f in result.file_list
            if f.extension in ['.ts', '.tsx', '.js', '.jsx'] and
            f.category != 'Test'  # Exclude test files
        ]
        
        if not source_files:
            st.warning("No TypeScript/JavaScript source files found for test generation")
        else:
            # Target file selection
            col1, col2 = st.columns([2, 1])
            
            with col1:
                target_file = st.selectbox(
                    "📄 Select target file for test generation",
                    options=source_files,
                    help="Choose the file you want to generate a test for"
                )
            
            with col2:
                st.metric("Source Files Available", len(source_files))
            
            # ===== NEW: Test Level Selection =====
            st.markdown("---")
            st.markdown("### 🎯 Test Levels to Generate")
            
            col1, col2 = st.columns(2)
            
            with col1:
                generate_unit = st.checkbox(
                    "🔹 Unit Test",
                    value=False,
                    help="Generate unit test with minimal context (imports only)"
                )
                if generate_unit:
                    st.caption("Creates: `*.test.tsx` - Fast, isolated tests")
            
            with col2:
                generate_feature = st.checkbox(
                    "💎 Feature Test",
                    value=True,
                    help="Generate feature test with full repository context"
                )
                if generate_feature:
                    st.caption("Creates: `*.feature.test.tsx` - Comprehensive tests")
            
            if not generate_unit and not generate_feature:
                st.warning("⚠️ Please select at least one test level to generate")
            
            # Optional pinned files
            with st.expander("📌 Pin Additional Context Files (Optional)", expanded=False):
                st.caption("Force-include specific files in context (factories, test-utils, etc.)")
                
                pinned_files = st.multiselect(
                    "Select files to always include",
                    options=[f for f in source_files if f != target_file],
                    help="These files will be included regardless of import relationships"
                )
                
                if pinned_files:
                    st.success(f"✓ {len(pinned_files)} file(s) pinned")
            
            # Context configuration
            with st.expander("⚙️ Context Configuration", expanded=False):
                st.caption("Adjust how much context to include")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    context_depth = st.slider(
                        "Import depth",
                        min_value=1,
                        max_value=5,
                        value=3,
                        help="How deep to traverse import graph (1=direct, 2=transitive, 3=deep, 4=very deep, 5=extreme)"
                    )
                    
                    max_context_files = st.slider(
                        "Max files",
                        min_value=5,
                        max_value=100,
                        value=50,
                        help="Maximum number of files to include in context"
                    )
                
                with col2:
                    max_chars_per_file = st.slider(
                        "Max chars per file",
                        min_value=1000,
                        max_value=10000,
                        value=3000,
                        step=500,
                        help="Truncate each file to this length"
                    )
                    
                    max_total_chars = st.slider(
                        "Max total chars",
                        min_value=10000,
                        max_value=100000,
                        value=50000,
                        step=5000,
                        help="Total character budget for all context"
                    )
                
                # Token estimation with warning for high usage
                estimated_tokens = max_total_chars // 4 + 2000
                if estimated_tokens > 50000:
                    st.warning(f"⚠️ **High token count:** ~{estimated_tokens:,} tokens - This will be expensive!")
                    st.caption(f"Estimated cost: ~${estimated_tokens * 0.000001:.4f} per test generation")
                else:
                    st.info(f"**Estimated tokens:** ~{estimated_tokens:,} total")
                    st.caption(f"Estimated cost: ~${estimated_tokens * 0.000001:.4f} per test generation")
            
            # Generate button
            st.markdown("---")
            
            generate_col1, generate_col2, generate_col3 = st.columns([2, 1, 1])
            
            with generate_col1:
                generate_single = st.button(
                    f"🚀 Generate {'Both' if (generate_unit and generate_feature) else 'Unit' if generate_unit else 'Feature'} Test{'s' if (generate_unit and generate_feature) else ''}",
                    type="primary",
                    use_container_width=True,
                    help="Generate selected test type(s) with repository context",
                    disabled=(not generate_unit and not generate_feature)
                )
            
            with generate_col2:
                if st.button("🔍 Preview Context", use_container_width=True):
                    st.session_state['preview_context'] = True
            
            with generate_col3:
                cost = 0.01 if (generate_unit or generate_feature) else 0
                cost = 0.02 if (generate_unit and generate_feature) else cost
                st.metric("Est. Cost", f"~${cost:.2f}")
            
            # Preview context (if requested)
            if st.session_state.get('preview_context', False):
                with st.spinner("Building context preview..."):
                    try:
                        from tools.context_builder import ContextBuilder
                        
                        workspace_path = safe_get('project_path')
                        if workspace_path:
                            builder = ContextBuilder(workspace_path)
                            context_result = builder.build_context_bundle(
                                target_file=target_file,
                                index_result=result,
                                pinned_files=pinned_files,
                                depth=context_depth,
                                max_files=max_context_files,
                                max_chars_per_file=max_chars_per_file,
                                max_total_chars=max_total_chars
                            )
                            
                            with st.expander("📋 Context Preview", expanded=True):
                                st.success(f"✓ Context built: {len(context_result.files_included)} files, {context_result.total_chars:,} chars")
                                
                                st.markdown("**Files included:**")
                                for idx, file in enumerate(context_result.files_included, 1):
                                    st.text(f"{idx}. {file}")
                                
                                if context_result.truncated_files:
                                    st.warning(f"⚠️ {len(context_result.truncated_files)} files truncated")
                                
                                if context_result.missing_imports:
                                    with st.expander(f"⚠️ {len(context_result.missing_imports)} unresolved imports"):
                                        for missing in context_result.missing_imports[:10]:
                                            st.text(f"• {missing}")
                            
                            st.session_state['preview_context'] = False
                    
                    except Exception as e:
                        st.error(f"Error building context: {e}")
                        st.session_state['preview_context'] = False
            
            # ===== FIXED: Generate test(s) with proper file saving =====
            if generate_single:
                test_levels_to_generate = []
                if generate_unit:
                    test_levels_to_generate.append('unit')
                if generate_feature:
                    test_levels_to_generate.append('feature')
                
                if not test_levels_to_generate:
                    st.error("Please select at least one test level")
                else:
                    workspace_path = safe_get('project_path')
                    
                    if not workspace_path:
                        st.error("❌ Project path not found")
                    else:
                        from tools.context_builder import ContextBuilder
                        from agents.test_generator_agent import TestGeneratorAgent
                        from agents.strategy_agent import TestStrategy
                        from config.vertex_ai import get_gemini_client
                        
                        # Build context once (used for both test types if applicable)
                        with st.spinner(f"📦 Building dependency-aware context..."):
                            try:
                                builder = ContextBuilder(workspace_path)
                                context_result = builder.build_context_bundle(
                                    target_file=target_file,
                                    index_result=result,
                                    pinned_files=pinned_files,
                                    depth=context_depth,
                                    max_files=max_context_files,
                                    max_chars_per_file=max_chars_per_file,
                                    max_total_chars=max_total_chars
                                )
                                
                                st.success(f"✓ Context: {len(context_result.files_included)} files, {context_result.total_chars:,} chars")
                            except Exception as e:
                                st.error(f"❌ Error building context: {e}")
                                context_result = None
                        
                        if context_result:
                            # Initialize Gemini client
                            gemini_client = get_gemini_client()
                            
                            if not gemini_client:
                                st.error("❌ Gemini client not configured. Check GOOGLE_CLOUD_PROJECT and credentials.")
                            else:
                                generator = TestGeneratorAgent(gemini_client)
                                target_path = Path(target_file)
                                generated_tests_info = []
                                
                                # Read source file once
                                source_path = workspace_path / target_file
                                source_content = source_path.read_text(encoding='utf-8', errors='ignore')
                                
                                # ===== GENERATE TESTS FOR EACH SELECTED LEVEL =====
                                for idx, test_level in enumerate(test_levels_to_generate, 1):
                                    level_emoji = "🔹" if test_level == "unit" else "💎"
                                    
                                    with st.spinner(f"{level_emoji} Generating {test_level} test ({idx}/{len(test_levels_to_generate)})..."):
                                        try:
                                            # Create appropriate file name based on test level
                                            if test_level == 'unit':
                                                test_file_name = f"{target_path.stem}.test{target_path.suffix}"
                                            else:  # feature
                                                test_file_name = f"{target_path.stem}.feature.test{target_path.suffix}"
                                            
                                            test_file_path = str(target_path.parent / test_file_name)
                                            
                                            # Create test strategy
                                            st.info(f"📋 Creating {test_level} test strategy...")
                                            
                                            # For unit tests, use minimal context (direct imports only)
                                            # For feature tests, use full context
                                            related_contents = context_result.context_bundle
                                            if test_level == 'unit':
                                                # Unit tests: only use pinned files and direct imports (depth 1)
                                                limited_builder = ContextBuilder(workspace_path)
                                                limited_context = limited_builder.build_context_bundle(
                                                    target_file=target_file,
                                                    index_result=result,
                                                    pinned_files=pinned_files,
                                                    depth=1,  # Only direct imports for unit tests
                                                    max_files=10,  # Fewer files for unit tests
                                                    max_chars_per_file=max_chars_per_file,
                                                    max_total_chars=15000  # Smaller budget for unit tests
                                                )
                                                related_contents = limited_context.context_bundle
                                            
                                            strategy = TestStrategy(
                                                source_file=target_file,
                                                test_file=test_file_path,
                                                test_level=test_level,
                                                framework='jest',
                                                priority='high',
                                                test_type=test_level,
                                                needs_mocks=(test_level == 'unit'),
                                                complexity='simple' if test_level == 'unit' else 'moderate',
                                                rationale=f"{test_level.title()} test for {target_file}",
                                                related_files=list(related_contents.keys())
                                            )
                                            
                                            st.success(f"✓ Strategy: {test_file_name}")
                                            
                                            # Generate test
                                            st.info(f"🤖 Generating {test_level} test with AI...")
                                            
                                            test_content = generator._generate_test_content(
                                                strategy=strategy,
                                                source_content=source_content,
                                                analysis_result=None,
                                                coverage_info=None,
                                                related_contents=related_contents,
                                                project_path=workspace_path
                                            )
                                            
                                            if test_content:
                                                # ===== FIXED: Save to BOTH workspace AND project folder =====
                                                # Save to workspace (for execution)
                                                test_output_path = workspace_path / test_file_path
                                                test_output_path.parent.mkdir(parents=True, exist_ok=True)
                                                test_output_path.write_text(test_content, encoding='utf-8')
                                                
                                                original_project = safe_get('uploaded_folder_path') or safe_get('original_project_path')
                                                if original_project and original_project != str(workspace_path):
                                                    main_test_path = Path(original_project) / test_file_path
                                                    main_test_path.parent.mkdir(parents=True, exist_ok=True)
                                                    main_test_path.write_text(test_content, encoding='utf-8')
                                                    logger.info(f"Also saved to main project: {main_test_path}")

                                                # ALSO save to actual project folder (user's local files)
                                                # This is what was missing!
                                                project_path = safe_get('run_id')
                                                if project_path:
                                                    # If run_id exists, save to that location too
                                                    project_test_path = Path(workspace_path) / test_file_path
                                                    if project_test_path != test_output_path:
                                                        project_test_path.parent.mkdir(parents=True, exist_ok=True)
                                                        project_test_path.write_text(test_content, encoding='utf-8')
                                                
                                                st.success(f"✅ {test_level.title()} test generated and saved: {test_file_path}")
                                                logger.info(f"Test file saved to: {test_output_path}")
                                                
                                                # Store info for display later
                                                generated_tests_info.append({
                                                    'level': test_level,
                                                    'file_path': test_file_path,
                                                    'file_name': test_file_name,
                                                    'content': test_content,
                                                    'context_files': len(related_contents),
                                                    'context_chars': sum(len(c) for c in related_contents.values())
                                                })
                                            else:
                                                st.error(f"❌ {test_level.title()} test generation failed - no content returned")
                                        
                                        except Exception as e:
                                            st.error(f"❌ Error generating {test_level} test: {e}")
                                            import traceback
                                            with st.expander("🐛 Error Details"):
                                                st.code(traceback.format_exc())
                                
                                # ===== DISPLAY ALL GENERATED TESTS =====
                                if generated_tests_info:
                                    st.markdown("---")
                                    st.markdown("## 📄 Generated Tests")
                                    
                                    # Create tabs for each generated test
                                    if len(generated_tests_info) == 1:
                                        # Single test - no tabs needed
                                        test_info = generated_tests_info[0]
                                        level_emoji = "🔹" if test_info['level'] == "unit" else "💎"
                                        
                                        st.markdown(f"### {level_emoji} {test_info['level'].title()} Test")
                                        
                                        with st.expander("📄 Test Code", expanded=True):
                                            st.code(test_info['content'], language='typescript')
                                        
                                        with st.expander("📊 Generation Details"):
                                            st.markdown(f"""
                                            **Target File:** `{target_file}`  
                                            **Test File:** `{test_info['file_path']}`  
                                            **Test Level:** {test_info['level'].title()}  
                                            **Context Files:** {test_info['context_files']}  
                                            **Context Size:** {test_info['context_chars']:,} characters  
                                            **Pinned Files:** {len(pinned_files)}  
                                            **Import Depth:** {context_depth if test_info['level'] == 'feature' else 1}  
                                            """)
                                        
                                        # FIXED: Download button always visible
                                        st.download_button(
                                            label=f"💾 Download {test_info['level'].title()} Test",
                                            data=test_info['content'],
                                            file_name=test_info['file_name'],
                                            mime="text/plain",
                                            key=f"download_single_{test_info['level']}"
                                        )
                                    
                                    else:
                                        # Multiple tests - use tabs
                                        tab_labels = [f"{('🔹' if t['level'] == 'unit' else '💎')} {t['level'].title()}" for t in generated_tests_info]
                                        tabs = st.tabs(tab_labels)
                                        
                                        for tab_idx, (tab, test_info) in enumerate(zip(tabs, generated_tests_info)):
                                            with tab:
                                                with st.expander("📄 Test Code", expanded=True):
                                                    st.code(test_info['content'], language='typescript')
                                                
                                                with st.expander("📊 Generation Details"):
                                                    st.markdown(f"""
                                                    **Target File:** `{target_file}`  
                                                    **Test File:** `{test_info['file_path']}`  
                                                    **Test Level:** {test_info['level'].title()}  
                                                    **Context Files:** {test_info['context_files']}  
                                                    **Context Size:** {test_info['context_chars']:,} characters  
                                                    **Pinned Files:** {len(pinned_files)}  
                                                    **Import Depth:** {context_depth if test_info['level'] == 'feature' else 1}  
                                                    """)
                                                
                                                # FIXED: Download button with unique key for each tab
                                                st.download_button(
                                                    label=f"💾 Download {test_info['level'].title()} Test",
                                                    data=test_info['content'],
                                                    file_name=test_info['file_name'],
                                                    mime="text/plain",
                                                    key=f"download_tab_{test_info['level']}_{tab_idx}"
                                                )
                                    
                                    # Summary at the bottom
                                    st.markdown("---")
                                    
                                    # ===== ADDED: Download All Button (when multiple tests) =====
                                    if len(generated_tests_info) > 1:
                                        st.markdown("### 📦 Download All Tests")
                                        
                                        col1, col2, col3 = st.columns([1, 1, 1])
                                        
                                        # Individual downloads in columns
                                        for col, test_info in zip([col1, col2], generated_tests_info):
                                            with col:
                                                level_emoji = "🔹" if test_info['level'] == "unit" else "💎"
                                                st.download_button(
                                                    label=f"{level_emoji} Download {test_info['level'].title()}",
                                                    data=test_info['content'],
                                                    file_name=test_info['file_name'],
                                                    mime="text/plain",
                                                    key=f"download_footer_{test_info['level']}",
                                                    use_container_width=True
                                                )
                                        
                                        st.markdown("")  # Spacing
                                    
                                    # Summary metrics
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("Tests Generated", len(generated_tests_info))
                                    
                                    with col2:
                                        total_lines = sum(len(t['content'].splitlines()) for t in generated_tests_info)
                                        st.metric("Total Lines", total_lines)
                                    
                                    with col3:
                                        test_types = ", ".join([t['level'].title() for t in generated_tests_info])
                                        st.metric("Test Types", test_types)
                                    
                                    # Show where files were saved
                                    st.info(f"📁 Files saved to: `{workspace_path}`")
                                    
                                    # Show context info (shared for all tests)
                                    with st.expander("📊 Context Information"):
                                        st.markdown(f"""
                                        **Context Files Included:** {len(context_result.files_included)}  
                                        **Total Context Size:** {context_result.total_chars:,} characters  
                                        """)
                                        
                                        st.markdown("**Files in context:**")
                                        for idx, file in enumerate(context_result.files_included, 1):
                                            st.text(f"{idx}. {file}")
                                        
                                        if context_result.truncated_files:
                                            st.warning(f"⚠️ {len(context_result.truncated_files)} files were truncated to fit budget")
                                        
                                        if context_result.missing_imports:
                                            st.warning(f"⚠️ {len(context_result.missing_imports)} imports could not be resolved")
    
    # File list (expandable)
    with st.expander("📄 View All Files"):
        for file_info in sorted(result.file_list, key=lambda x: x.relative_path):
            lines_info = f" ({file_info.lines} lines)" if file_info.lines else ""
            st.text(f"{file_info.relative_path} - {FileIndexer.format_size(file_info.size)}{lines_info}")



def create_coverage_chart(unified_report):
    """Create coverage bar chart using Plotly"""
    if not unified_report or not unified_report.coverage_reports:
        return None
    
    frameworks = []
    coverages = []
    
    for framework, cov_data in unified_report.coverage_reports.items():
        frameworks.append(framework.upper())
        coverages.append(cov_data['total_coverage'])
    
    fig = go.Figure(data=[
        go.Bar(
            x=frameworks,
            y=coverages,
            text=[f"{c:.1f}%" for c in coverages],
            textposition='auto',
            marker=dict(
                color=coverages,
                colorscale=[[0, '#ef4444'], [0.5, '#f59e0b'], [1, '#10b981']],
                cmin=0,
                cmax=100
            )
        )
    ])
    
    fig.update_layout(
        title="Code Coverage by Framework",
        xaxis_title="Framework",
        yaxis_title="Coverage %",
        yaxis=dict(range=[0, 100]),
        height=400,
        template="plotly_white"
    )
    
    return fig


def create_pass_fail_chart(unified_report):
    """Create pass/fail pie chart using Plotly"""
    if not unified_report:
        return None
    
    labels = []
    values = []
    colors = []
    
    if unified_report.passed > 0:
        labels.append('Passed')
        values.append(unified_report.passed)
        colors.append('#10b981')
    
    if unified_report.failed > 0:
        labels.append('Failed')
        values.append(unified_report.failed)
        colors.append('#ef4444')
    
    if unified_report.skipped > 0:
        labels.append('Skipped')
        values.append(unified_report.skipped)
        colors.append('#f59e0b')
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        hole=0.4,
        textinfo='label+percent+value'
    )])
    
    fig.update_layout(
        title=f"Test Results Distribution ({unified_report.total_tests} total)",
        height=400,
        template="plotly_white"
    )
    
    return fig


def display_test_level_summary():
    """Display test-level summary with tabs"""
    workflow_state = safe_get('workflow_state')
    if not workflow_state or not hasattr(workflow_state, 'execution_results_by_level'):
        return
    
    results_by_level = workflow_state.execution_results_by_level
    if not results_by_level:
        return
    
    st.markdown("---")
    st.subheader("🎯 Test Results by Level")
    
    # Create tabs for each test level
    test_levels = [level for level in ['unit', 'integration', 'feature'] if level in results_by_level and results_by_level[level]]
    
    if not test_levels:
        return
    
    tabs = st.tabs([f"{'🔹' if lvl=='unit' else '🔷' if lvl=='integration' else '💎'} {lvl.title()}" for lvl in test_levels])
    
    for i, test_level in enumerate(test_levels):
        with tabs[i]:
            level_results = results_by_level[test_level]
            
            # Aggregate metrics for this level
            level_total = 0
            level_passed = 0
            level_failed = 0
            level_skipped = 0
            
            for framework, result in level_results.items():
                level_total += result.total_tests
                level_passed += result.passed
                level_failed += result.failed
                level_skipped += result.skipped
            
            level_pass_rate = (level_passed / level_total * 100) if level_total > 0 else 0
            
            # Display level summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Tests", level_total)
            with col2:
                st.metric("✅ Passed", level_passed)
            with col3:
                st.metric("❌ Failed", level_failed)
            with col4:
                st.metric("Pass Rate", f"{level_pass_rate:.1f}%")
            
            # Display framework results for this level
            st.markdown(f"### Results by Framework")
            for framework, result in level_results.items():
                with st.expander(f"📦 {framework.upper()} - {result.total_tests} tests", expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Passed", result.passed)
                    with col2:
                        st.metric("Failed", result.failed)
                    with col3:
                        st.metric("Skipped", result.skipped)
                    with col4:
                        st.metric("Duration", f"{result.duration:.2f}s")
                    
                    if result.test_cases:
                        st.markdown("**Test Cases:**")
                        for tc in result.test_cases[:10]:  # Show first 10
                            status_icon = "✅" if tc.status == 'passed' else "❌" if tc.status == 'failed' else "⏭️"
                            st.text(f"{status_icon} {tc.name}")
                        
                        if len(result.test_cases) > 10:
                            st.info(f"... and {len(result.test_cases) - 10} more test cases")

def display_unified_report():
    """Display unified report with visualizations"""
    if not st.session_state.unified_report:
        return
    
    report = st.session_state.unified_report
    
    st.markdown("---")
    st.subheader("📊 Unified Test Report")
    
    # Summary banner
    if report.failed == 0:
        st.success(report.summary)
    else:
        st.warning(report.summary)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tests", report.total_tests)
    with col2:
        st.metric("Pass Rate", f"{report.pass_rate:.1f}%")
    with col3:
        st.metric("Coverage", f"{report.total_coverage:.1f}%")
    with col4:
        st.metric("Status", "✅ Pass" if report.failed == 0 else "❌ Fail")
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Pass/Fail Pie Chart
        pie_chart = create_pass_fail_chart(report)
        if pie_chart:
            st.plotly_chart(pie_chart, use_container_width=True)
    
    with col2:
        # Coverage Bar Chart
        if report.coverage_reports:
            coverage_chart = create_coverage_chart(report)
            if coverage_chart:
                st.plotly_chart(coverage_chart, use_container_width=True)
        else:
            st.info("No coverage data available. Run tests with coverage enabled.")
    
    # NEW: Test-level breakdown visualizations
    if report.results_by_level:
        st.markdown("### 📈 Test Results by Level")
        
        # Create bar chart for test levels
        import plotly.graph_objects as go
        
        levels = list(report.results_by_level.keys())
        passed_counts = [report.results_by_level[lvl]['passed'] for lvl in levels]
        failed_counts = [report.results_by_level[lvl]['failed'] for lvl in levels]
        
        fig = go.Figure(data=[
            go.Bar(name='Passed', x=levels, y=passed_counts, marker_color='#10b981'),
            go.Bar(name='Failed', x=levels, y=failed_counts, marker_color='#ef4444')
        ])
        
        fig.update_layout(
            barmode='stack',
            title="Test Results by Level",
            xaxis_title="Test Level",
            yaxis_title="Number of Tests",
            height=400,
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Coverage by level
        if report.coverage_by_level:
            st.markdown("### 📊 Coverage by Test Level")
            
            levels = list(report.coverage_by_level.keys())
            coverages = [report.coverage_by_level[lvl] for lvl in levels]
            
            fig2 = go.Figure(data=[
                go.Bar(
                    x=levels,
                    y=coverages,
                    text=[f"{c:.1f}%" for c in coverages],
                    textposition='auto',
                    marker=dict(
                        color=coverages,
                        colorscale=[[0, '#ef4444'], [0.5, '#f59e0b'], [1, '#10b981']],
                        cmin=0,
                        cmax=100
                    )
                )
            ])
            
            fig2.update_layout(
                title="Code Coverage by Test Level",
                xaxis_title="Test Level",
                yaxis_title="Coverage %",
                yaxis=dict(range=[0, 100]),
                height=400,
                template="plotly_white"
            )
            
            st.plotly_chart(fig2, use_container_width=True)
    
    # Download reports
    st.markdown("### 📥 Download Reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # JSON download
        import json
        json_data = json.dumps(report.__dict__, indent=2, default=str)
        st.download_button(
            label="⬇️ Download JSON Report",
            data=json_data,
            file_name=f"test-report-{report.timestamp[:10]}.json",
            mime="application/json"
        )
    
    with col2:
        # HTML download
        report_agent = ReportAgent(st.session_state.project_path)
        html_file = st.session_state.project_path / "reports" / "test-report.html"
        if html_file.exists():
            with open(html_file, 'r', encoding='utf-8') as f:
                html_data = f.read()
            st.download_button(
                label="⬇️ Download HTML Report",
                data=html_data,
                file_name=f"test-report-{report.timestamp[:10]}.html",
                mime="text/html"
            )


def display_execution_results():
    """Display test execution results"""
    if not st.session_state.execution_results:
        return
    
    st.markdown("---")
    st.subheader("🏃 Test Execution Results")
    
    for framework, result in st.session_state.execution_results.items():
        st.markdown(f"### {framework.upper()} Results")
        
        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total", result.total_tests)
        with col2:
            st.metric("✅ Passed", result.passed)
        with col3:
            st.metric("❌ Failed", result.failed)
        with col4:
            st.metric("⏭️ Skipped", result.skipped)
        with col5:
            st.metric("⏱️ Duration", f"{result.duration:.2f}s")
        
        # Status
        if result.success:
            st.success(f"All tests passed! ✓")
        else:
            st.error(f"{result.failed} test(s) failed")
        
        # Retry information
        if result.attempt > 1:
            st.info(f"Completed on attempt {result.attempt}/{result.max_attempts}")
        
        if result.timed_out:
            st.warning("⚠️ Execution timed out")
        
        # Test cases
        if result.test_cases:
            with st.expander(f"📋 Test Cases ({len(result.test_cases)})"):
                for tc in result.test_cases:
                    status_icon = "✅" if tc.status == 'passed' else "❌" if tc.status == 'failed' else "⏭️"
                    st.text(f"{status_icon} {tc.name} ({tc.duration:.3f}s)")
                    if tc.error_message:
                        with st.expander(f"Error: {tc.name}"):
                            st.code(tc.error_message, language='text')
        
        # Execution logs
        with st.expander("📝 Execution Logs"):
            if result.stdout:
                st.text_area("Standard Output", result.stdout, height=200)
            if result.stderr:
                st.text_area("Standard Error", result.stderr, height=200)
        
        # Jest JSON Output (if available)
        if framework == 'jest':
            project_path = safe_get('project_path')
            if project_path:
                jest_json_file = project_path / 'jest-results.json'
                jest_json_report = project_path / 'reports' / 'jest-results.json'
                
                # Check both locations
                json_file_to_show = None
                if jest_json_report.exists():
                    json_file_to_show = jest_json_report
                elif jest_json_file.exists():
                    json_file_to_show = jest_json_file
                
                if json_file_to_show:
                    try:
                        with open(json_file_to_show, 'r', encoding='utf-8') as f:
                            jest_json_data = json.load(f)
                        
                        with st.expander("📄 Jest JSON Output"):
                            st.json(jest_json_data)
                            
                            # Download button for JSON
                            json_str = json.dumps(jest_json_data, indent=2)
                            st.download_button(
                                label="⬇️ Download Jest JSON",
                                data=json_str,
                                file_name="jest-results.json",
                                mime="application/json",
                                key=f"download_jest_json_{framework}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to read Jest JSON file: {e}")
        
        # Failure analysis
        if framework in st.session_state.failure_analyses:
            analysis = st.session_state.failure_analyses[framework]
            
            st.markdown("### 🔍 Failure Analysis")
            
            # Severity badge
            severity_colors = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }
            severity_icon = severity_colors.get(analysis.severity, '⚪')
            st.markdown(f"**Severity:** {severity_icon} {analysis.severity.upper()}")
            
            # Summary
            st.info(analysis.summary)
            
            # Likely causes
            if analysis.likely_causes:
                st.markdown("**Likely Causes:**")
                for cause in analysis.likely_causes:
                    st.markdown(f"- {cause}")
            
            # Recommendations
            if analysis.recommendations:
                st.markdown("**Recommendations:**")
                for rec in analysis.recommendations:
                    st.markdown(f"- {rec}")
            
            # Affected tests
            if analysis.affected_tests:
                with st.expander(f"Affected Tests ({len(analysis.affected_tests)})"):
                    for test in analysis.affected_tests[:20]:
                        st.text(f"- {test}")
        
        st.markdown("---")


def display_generated_tests():
    """Display generated test files with download options"""
    if st.session_state.generated_tests is None:
        return
    
    st.markdown("---")
    st.subheader("🧪 Generated Tests")
    
    generated_tests = st.session_state.generated_tests
    successful_tests = [t for t in generated_tests if t.success]
    failed_tests = [t for t in generated_tests if not t.success]
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Test Files", len(generated_tests))
    with col2:
        st.metric("Successful", len(successful_tests))
    with col3:
        st.metric("Failed", len(failed_tests))
    with col4:
        total_tests = sum(t.test_count for t in successful_tests)
        st.metric("Total Tests", total_tests)
    
    # Successful tests
    if successful_tests:
        st.markdown("### ✅ Successfully Generated")
        
        for test in successful_tests:
            with st.expander(f"📄 {test.test_file_path} ({test.test_count} tests)"):
                st.markdown(f"**Source:** `{test.source_file_path}`")
                st.markdown(f"**Framework:** {test.framework.upper()}")
                st.markdown(f"**Test Count:** {test.test_count}")
                
                # Code preview
                st.code(test.test_content, language='javascript' if test.framework == 'jest' else 'python')
                
                # Download button
                st.download_button(
                    label=f"⬇️ Download {Path(test.test_file_path).name}",
                    data=test.test_content,
                    file_name=Path(test.test_file_path).name,
                    mime='text/plain',
                    key=f"download_{test.test_file_path}"
                )
    
    # Failed tests
    if failed_tests:
        st.markdown("### ⚠️ Failed to Generate")
        
        for test in failed_tests:
            with st.expander(f"❌ {test.test_file_path}"):
                st.markdown(f"**Source:** `{test.source_file_path}`")
                if test.error_message:
                    st.error(f"Error: {test.error_message}")


def display_ai_analysis():
    """Display AI-powered analysis results"""
    if st.session_state.analysis_result is None:
        return
    
    analysis = st.session_state.analysis_result
    
    st.markdown("---")
    st.subheader("🤖 AI-Powered Analysis (Gemini)")
    
    # Confidence badge
    confidence_colors = {
        "high": "🟢",
        "medium": "🟡",
        "low": "🔴"
    }
    confidence_icon = confidence_colors.get(analysis.confidence.lower(), "⚪")
    st.markdown(f"**Confidence:** {confidence_icon} {analysis.confidence.upper()}")
    
    # Summary
    st.markdown("**Summary:**")
    st.info(analysis.summary)
    
    # Languages and Frameworks in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔤 Languages Detected:**")
        if analysis.languages:
            for lang in analysis.languages:
                st.markdown(f"- {lang}")
        else:
            st.text("None detected")
    
    with col2:
        st.markdown("**⚙️ Frameworks Detected:**")
        if analysis.frameworks:
            for fw in analysis.frameworks:
                st.markdown(f"- {fw}")
        else:
            st.text("None detected")
    
    # Test Setup
    st.markdown("**🧪 Test Setup:**")
    test_setup = analysis.test_setup
    
    # Check for actual test files in the project to verify AI analysis
    # This ensures we show accurate data even if AI missed something
    index_result = safe_get('index_result')
    actual_test_count = 0
    if index_result:
        actual_test_count = index_result.files_by_category.get('Test', 0)
    
    # Also check for generated tests
    generated_tests = safe_get('generated_tests', [])
    generated_test_count = len([t for t in generated_tests if t.success]) if generated_tests else 0
    
    # Use the maximum of AI-detected, indexed, or generated tests
    test_count = max(
        test_setup.get('test_file_count', 0),
        actual_test_count,
        generated_test_count
    )
    has_tests = test_count > 0 or test_setup.get('has_tests', False) or generated_test_count > 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tests Present", "Yes ✓" if has_tests else "No ✗")
    
    with col2:
        st.metric("Test Files", test_count)
    
    with col3:
        # Show coverage from unified report if available, otherwise from analysis
        unified_report = safe_get('unified_report')
        if unified_report and unified_report.total_coverage > 0:
            coverage_display = f"{unified_report.total_coverage:.1f}%"
        else:
            coverage = test_setup.get('test_coverage', 'unknown')
            coverage_display = coverage.title() if coverage != 'unknown' else 'None'
        st.metric("Coverage", coverage_display)
    
    # Test frameworks
    test_frameworks = test_setup.get('test_frameworks', [])
    # Also check generated tests for frameworks
    if generated_tests:
        generated_frameworks = set(t.framework for t in generated_tests if t.success)
        if generated_frameworks:
            test_frameworks = list(set(test_frameworks) | generated_frameworks)
    
    if test_frameworks:
        st.markdown("**Test Frameworks:**")
        for fw in test_frameworks:
            st.markdown(f"- {fw}")


def execute_full_workflow(project_path: Path, test_levels: Optional[List[str]] = None) -> None:
    """
    Execute full workflow using LangGraph-style orchestration
    UI never executes code directly - all execution goes through workflow
    
    Args:
        project_path: Path to workspace project directory (temporary)
        test_levels: Optional list of test levels to run ['unit', 'integration', 'feature']
                     If None, uses levels from session state or defaults to all
    """
    try:
        # Get test levels from parameter or session state
        if test_levels is None:
            test_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
        
        # Ensure we have valid test levels
        if not test_levels:
            test_levels = ['unit', 'integration', 'feature']
        
        # Log selected test levels
        level_names = ', '.join([lvl.title() for lvl in test_levels])
        add_status(f"Starting automated workflow for: {level_names}", "info")
        
        # Main project path is the root directory (where app.py is)
        # This is where test files will be saved and executed
        main_project_path = Path(__file__).parent
        
        # Create workflow orchestrator with both paths
        orchestrator = WorkflowOrchestrator(project_path, main_project_path=main_project_path)
        
        # Execute workflow (all stages)
        result = orchestrator.execute(test_levels=test_levels)
        
        # Store results
        st.session_state.workflow_result = result
        st.session_state.workflow_state = result.state
        
        # Update session state with workflow results
        if result.state.index_result:
            st.session_state.index_result = result.state.index_result
        
        if result.state.analysis_result:
            st.session_state.analysis_result = result.state.analysis_result
        
        if result.state.strategy_result:
            st.session_state.test_strategy_result = result.state.strategy_result
        
        if result.state.generated_tests:
            st.session_state.generated_tests = result.state.generated_tests
        
        if result.state.execution_results:
            st.session_state.execution_results = result.state.execution_results
        
        if result.state.unified_report:
            st.session_state.unified_report = result.state.unified_report
        
        # Update analysis result to reflect generated tests
        if result.state.generated_tests and st.session_state.analysis_result:
            # Update test_setup in analysis_result to reflect generated tests
            generated_tests = result.state.generated_tests
            successful_tests = [t for t in generated_tests if t.success]
            if successful_tests:
                test_setup = st.session_state.analysis_result.test_setup
                test_setup['has_tests'] = True
                test_setup['test_file_count'] = len(successful_tests)
                # Add frameworks from generated tests
                frameworks = set(test_setup.get('test_frameworks', []))
                frameworks.update(t.framework for t in successful_tests)
                test_setup['test_frameworks'] = list(frameworks)
        
        # Update status
        if result.success:
            add_status(f"Workflow completed successfully in {result.duration:.2f}s", "success")
        else:
            add_status(f"Workflow completed with warnings: {result.message}", "warning")
        
        # Log any errors/warnings
        for error in result.state.errors:
            add_status(f"Error: {error}", "error")
        
        for warning in result.state.warnings:
            add_status(f"Warning: {warning}", "warning")
        
    except Exception as e:
        logger.error(f"Workflow error: {e}")
        add_status(f"Workflow error: {str(e)}", "error")


def generate_tests_for_project(project_path: Path, index_result, analysis_result) -> None:
    """
    Generate tests for the project
    
    Args:
        project_path: Path to project directory
        index_result: File indexing results
        analysis_result: Project analysis results
    """
    try:
        # Check if Gemini is available
        if not st.session_state.gemini_available:
            add_status("Vertex AI required for test generation - skipping", "warning")
            return
        
        # Get Gemini client
        gemini_client = get_gemini_client()
        if not gemini_client or not gemini_client.is_ready():
            add_status("Gemini client not ready - skipping test generation", "warning")
            return
        
        # Create strategy agent
        add_status("Determining test strategy...", "info")
        strategy_agent = StrategyAgent(gemini_client)
        
        # Determine test strategy
        test_strategy = strategy_agent.determine_test_strategy(
            index_result,
            analysis_result,
            project_path
        )
        
        if not test_strategy or test_strategy.total_files_to_test == 0:
            add_status("No testable files found", "warning")
            return
        
        st.session_state.test_strategy_result = test_strategy
        add_status(f"Test strategy ready: {test_strategy.total_files_to_test} files to test", "success")
        
        # Generate tests
        add_status("Generating tests with Gemini AI...", "info")
        test_generator = TestGeneratorAgent(gemini_client)
        
        # Limit to first 10 files for demo
        strategies_to_generate = test_strategy.strategies[:10]
        add_status(f"Generating tests for {len(strategies_to_generate)} files...", "info")
        
        generated_tests = test_generator.generate_tests(
            strategies_to_generate,
            project_path,
            analysis_result
        )
        
        st.session_state.generated_tests = generated_tests
        
        # Summary
        successful_tests = sum(1 for t in generated_tests if t.success)
        total_test_count = sum(t.test_count for t in generated_tests if t.success)
        
        add_status(f"Test generation complete!", "success")
        add_status(f"Generated: {successful_tests}/{len(generated_tests)} test files", "info")
        add_status(f"Total tests created: {total_test_count}", "info")
        
    except Exception as e:
        logger.error(f"Error generating tests: {e}")
        add_status(f"Test generation error: {str(e)}", "error")


def execute_tests_for_project_deprecated(project_path: Path) -> None:
    """
    Execute generated tests
    
    Args:
        project_path: Path to project directory
    """
    try:
        add_status("Starting test execution...", "info")
        
        # Create executor
        executor = TestExecutorAgent(project_path)
        
        # Determine which frameworks to run
        frameworks_to_test = []
        
        if st.session_state.generated_tests:
            # Check which frameworks were used
            jest_tests = any(t.framework == 'jest' for t in st.session_state.generated_tests if t.success)
            pytest_tests = any(t.framework == 'pytest' for t in st.session_state.generated_tests if t.success)
            
            if jest_tests and executor.can_execute_jest():
                frameworks_to_test.append('jest')
            elif jest_tests:
                add_status("Jest tests found but npx not available", "warning")
            
            if pytest_tests and executor.can_execute_pytest():
                frameworks_to_test.append('pytest')
            elif pytest_tests:
                add_status("Pytest tests found but pytest not available", "warning")
        
        if not frameworks_to_test:
            add_status("No executable tests found", "warning")
            return
        
        # Execute tests for each framework
        for framework in frameworks_to_test:
            add_status(f"Executing {framework.upper()} tests...", "info")
            
            result = executor.execute_tests(framework, timeout=300)
            
            st.session_state.execution_results[framework] = result
            
            if result.success:
                add_status(f"{framework.upper()}: All {result.passed} tests passed! ✓", "success")
            else:
                add_status(f"{framework.upper()}: {result.failed}/{result.total_tests} tests failed", "error")
            
            # Analyze failures if any
            if result.failed > 0:
                add_status(f"Analyzing {framework.upper()} failures...", "info")
                
                gemini_client = get_gemini_client() if st.session_state.gemini_available else None
                analyzer = FailureAnalyzerAgent(gemini_client)
                
                analysis = analyzer.analyze_failures(result)
                if analysis:
                    st.session_state.failure_analyses[framework] = analysis
                    add_status(f"Failure analysis complete: {analysis.severity} severity", "warning")
        
        add_status("Test execution complete!", "success")
        
        # Generate unified report
        add_status("Generating report with coverage...", "info")
        report_agent = ReportAgent(project_path)
        unified_report = report_agent.generate_unified_report(st.session_state.execution_results)
        st.session_state.unified_report = unified_report
        
        # Save reports
        json_file = report_agent.save_json_report(unified_report)
        html_file = report_agent.save_html_report(unified_report)
        add_status(f"Reports saved: {json_file.name}, {html_file.name}", "success")
        
    except Exception as e:
        logger.error(f"Error executing tests: {e}")
        add_status(f"Test execution error: {str(e)}", "error")


def reset_session():
    """Reset session state for new run"""
    st.session_state.run_id = None
    st.session_state.project_path = None
    st.session_state.index_result = None
    st.session_state.analysis_result = None
    st.session_state.test_strategy_result = None
    st.session_state.generated_tests = None
    st.session_state.execution_results = {}
    st.session_state.failure_analyses = {}
    st.session_state.unified_report = None
    st.session_state.processing_status = []
    st.session_state.metadata = {}
    st.session_state.gemini_available = None
    st.session_state.infrastructure = None


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="AutoSDLC Test Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Header
    st.title("🤖 AutoSDLC Test Agent")
    st.markdown("**Autonomous SDLC Testing Agent with LangGraph Orchestration**")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.info("Upload your project to begin analysis")
        
        # Auto-run workflow option
        auto_run_workflow = st.checkbox(
            "🚀 Auto-run workflow after indexing",
            value=False,
            help="Automatically execute the full testing workflow (Analysis → Generation → Execution) after file indexing completes"
        )
        safe_set('auto_run_workflow', auto_run_workflow)
        
        # NEW: Test Level Selection
        st.markdown("---")
        st.subheader("🎯 Test Levels")
        
        # Get current selection or default to all levels
        current_selection = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
        if not current_selection or (isinstance(current_selection, list) and len(current_selection) == 0):
            current_selection = ['unit', 'integration', 'feature']
            safe_set('test_levels_to_run', current_selection)  # Ensure it's set
        
        # Ensure current_selection is a list
        if not isinstance(current_selection, list):
            current_selection = [current_selection] if current_selection else ['unit', 'integration', 'feature']
        
        test_levels_to_run = st.multiselect(
            "Select test levels to execute:",
            options=["unit", "integration", "feature"],
            default=current_selection,
            key="test_levels_multiselect",  # Add key for proper state management
            help="🔹 Unit: Fast, isolated tests\n🔷 Integration: Multi-module tests with MSW\n💎 Feature: Complete user workflows (E2E-lite)"
        )
        
        # Always update session state when selection changes
        if test_levels_to_run:
            safe_set('test_levels_to_run', test_levels_to_run)
            logger.info(f"✅ UI: Test levels updated to: {test_levels_to_run}")
        else:
            # If nothing selected, default to all
            safe_set('test_levels_to_run', ['unit', 'integration', 'feature'])
            logger.info(f"⚠️ UI: No test levels selected, defaulting to all")
        
        # Quick action buttons for common scenarios
        st.markdown("**Quick Actions:**")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔹 Unit Only", use_container_width=True, 
                        help="Fast: Run only unit tests"):
                safe_set('test_levels_to_run', ['unit'])
                logger.info(f"✅ UI Button: Set test_levels_to_run = ['unit']")
                st.rerun()
        
        with col2:
            if st.button("🔷 Integration", use_container_width=True,
                        help="Focus: Run integration tests only"):
                safe_set('test_levels_to_run', ['integration'])
                logger.info(f"✅ UI Button: Set test_levels_to_run = ['integration']")
                st.rerun()
        
        if st.button("💎 Feature Only", use_container_width=True,
                    help="Complete: Run feature-level tests only"):
            safe_set('test_levels_to_run', ['feature'])
            logger.info(f"✅ UI Button: Set test_levels_to_run = ['feature']")
            st.rerun()
        
        if st.button("🎯 All Levels", use_container_width=True,
                    help="Run all test levels (unit → integration → feature)"):
            safe_set('test_levels_to_run', ['unit', 'integration', 'feature'])
            logger.info(f"✅ UI Button: Set test_levels_to_run = ['unit', 'integration', 'feature']")
            st.rerun()
        
        st.markdown("---")
        
        if st.button("🔄 Reset Session", type="secondary", use_container_width=True):
            reset_session()
            st.rerun()
        
        st.markdown("---")
        st.subheader("📋 Status")
        run_id = safe_get('run_id')
        if run_id:
            st.success(f"Run ID: {run_id[:8]}...")
            st.text(f"Workspace: run_{run_id[:8]}...")
            
            # Show selected test levels
            selected_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
            if selected_levels:
                level_icons = {'unit': '🔹', 'integration': '🔷', 'feature': '💎'}
                level_display = ' '.join([f"{level_icons.get(lvl, '•')} {lvl.title()}" for lvl in selected_levels])
                st.info(f"Test Levels: {level_display}")
        else:
            st.warning("No active session")
    
    # Main content
    if safe_get('index_result') is None:
        # Input selection
        st.header("📥 Input Source")
        
        input_method = st.radio(
            "Choose input method:",
            ["GitHub Repository", "ZIP Upload", "Folder Upload", "Single File"],
            horizontal=True
        )
        
        st.markdown("---")
        
        # GitHub Repository Input
        if input_method == "GitHub Repository":
            st.subheader("🔗 GitHub Repository")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                repo_url = st.text_input(
                    "Repository URL",
                    placeholder="https://github.com/username/repository"
                )
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                process_btn = st.button("Clone & Process", type="primary", use_container_width=True)
            
            if process_btn:
                if not repo_url:
                    st.error("Please enter a GitHub repository URL")
                elif not GitTool.validate_github_url(repo_url):
                    st.error("Invalid GitHub URL format")
                else:
                    with st.spinner("Processing repository..."):
                        handle_github_input(repo_url)
                    st.rerun()
        
        # ZIP Upload
        elif input_method == "ZIP Upload":
            st.subheader("📦 ZIP File Upload")
            
            uploaded_file = st.file_uploader(
                "Upload ZIP file",
                type=['zip'],
                help="Upload a ZIP file containing your project"
            )
            
            if uploaded_file is not None:
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("Extract & Process", type="primary", use_container_width=True):
                        with st.spinner("Processing ZIP file..."):
                            handle_zip_upload(uploaded_file)
                        st.rerun()
        
        # Folder Upload
        elif input_method == "Folder Upload":
            st.subheader("📁 Folder Upload")
            st.info("💡 Select multiple files to upload an entire folder structure")
            
            uploaded_files = st.file_uploader(
                "Upload files",
                accept_multiple_files=True,
                help="Select all files from your project folder"
            )
            
            if uploaded_files:
                st.success(f"Selected {len(uploaded_files)} files")
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("Upload & Process", type="primary", use_container_width=True):
                        with st.spinner("Processing files..."):
                            handle_folder_upload(uploaded_files)
                        st.rerun()
        
        # Single File Upload
        elif input_method == "Single File":
            st.subheader("📄 Single File Upload")
            
            uploaded_file = st.file_uploader(
                "Upload file",
                help="Upload a single source file for analysis"
            )
            
            if uploaded_file is not None:
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("Upload & Process", type="primary", use_container_width=True):
                        with st.spinner("Processing file..."):
                            handle_single_file_upload(uploaded_file)
                        st.rerun()
        
        # Processing Status
        processing_status = safe_get('processing_status', [])
        if processing_status:
            st.markdown("---")
            st.subheader("📊 Processing Status")
            
            for status_item in processing_status:
                message = status_item['message']
                status = status_item['status']
                
                if status == "success":
                    st.success(message)
                elif status == "error":
                    st.error(message)
                elif status == "warning":
                    st.warning(message)
                else:
                    st.info(message)
    
    else:
        # Display results
        display_index_results()
        
        # Display AI analysis if available
        display_ai_analysis()
        
        # NEW: Display test-level summary (tabs) if available
        display_test_level_summary()
        
        # Test generation section - Show workflow button if indexed (workflow handles AI analysis internally)
        index_result = safe_get('index_result')
        workflow_result = safe_get('workflow_result')
        project_path = safe_get('project_path')
        
        if index_result and project_path:
            workflow_result = safe_get('workflow_result')
            generated_tests = safe_get('generated_tests', [])
            unified_report = safe_get('unified_report')
            
            # Only show workflow section if workflow hasn't run yet, or if there are results to show
            if workflow_result is None:
                st.markdown("---")
                st.subheader("🧪 Automated Testing Workflow")
                
                # Show workflow button - workflow will handle AI analysis, test generation, execution
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("🚀 Run Workflow", type="primary", use_container_width=True):
                        selected_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
                        level_names = ', '.join([lvl.title() for lvl in selected_levels])
                        with st.spinner(f"Running workflow for {level_names} tests (this may take a few minutes)..."):
                            # FIXED: Explicitly pass test_levels to ensure user selection is respected
                            execute_full_workflow(project_path, test_levels=selected_levels)
                        st.rerun()
                
                # Show selected test levels
                selected_levels = safe_get('test_levels_to_run', ['unit', 'integration', 'feature'])
                level_icons = {'unit': '🔹', 'integration': '🔷', 'feature': '💎'}
                level_display = ' → '.join([f"{level_icons.get(lvl, '•')}{lvl.title()}" for lvl in selected_levels])
                
                gemini_available = safe_get('gemini_available')
                if gemini_available:
                    st.info(f"💡 Workflow will execute: AI Analysis → Test Strategy → {level_display} → Reporting")
                else:
                    st.warning("⚠️ Vertex AI not configured. Workflow will run with limited AI features. To enable full AI capabilities, set GOOGLE_APPLICATION_CREDENTIALS environment variable.")
            elif workflow_result or generated_tests or unified_report:
                # Only show section header if there's content to display
                # Display generated tests
                display_generated_tests()
                
                # Workflow results are already displayed if workflow ran
                # Show individual sections if available
                if workflow_result:
                    # Display unified report
                    display_unified_report()
                    
                    # Display execution results
                    display_execution_results()
                elif generated_tests:
                    # Tests generated but not executed yet
                    st.info("💡 Run 'Full Workflow' to execute tests and generate reports")
        
        st.markdown("---")
        
        # Metadata
        metadata = safe_get('metadata', {})
        if metadata:
            with st.expander("ℹ️ Metadata"):
                st.json(metadata)
        
        # Processing Status History
        with st.expander("📝 Processing Log"):
            processing_status = safe_get('processing_status', [])
            for status_item in processing_status:
                st.text(f"[{status_item['status'].upper()}] {status_item['message']}")
        
        # Next steps
        execution_results = safe_get('execution_results', {})
        workflow_result = safe_get('workflow_result')
        generated_tests = safe_get('generated_tests')
        analysis_result = safe_get('analysis_result')
        if execution_results:
            successful = all(r.success for r in execution_results.values())
            if successful:
                st.success("🎉 All tests passed! Your code is working correctly.")
            else:
                st.warning("⚠️ Some tests failed. Review the analysis above for recommendations.")
        elif workflow_result:
            if workflow_result.success:
                st.success("🎉 Workflow completed successfully! Review results above.")
            else:
                st.warning(f"⚠️ Workflow completed with issues: {workflow_result.message}")
        elif generated_tests:
            st.info("✅ Tests generated! Run 'Full Workflow' to execute and report.")
        elif analysis_result:
            st.info("✅ Project analyzed! Run 'Full Workflow' for complete automation.")
        else:
            st.info("✅ Project indexed! Run 'Full Workflow' for end-to-end automation.")


if __name__ == "__main__":
    main()