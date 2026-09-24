# Project Structure

## Directory Layout

```
AutoSDLC-Test-Agent/
│
├── app.py                      # Main Streamlit application entry point
├── setup.py                    # Installation and setup script
├── validate.py                 # Validation script for testing components
├── requirements.txt            # Python dependencies
├── config.env.example          # Environment variable template
│
├── .gitignore                  # Git ignore rules
├── .streamlit/                 # Streamlit configuration
│   └── config.toml            # UI theme and server settings
│
├── tools/                      # Core tool modules
│   ├── __init__.py            # Module exports
│   ├── git_tool.py            # GitHub repository cloning
│   ├── unzip_tool.py          # ZIP file extraction
│   ├── file_indexer.py        # File analysis and categorization
│   └── config.py              # Configuration management
│
├── workspaces/                 # Sandboxed execution environments (gitignored)
│   └── run_<uuid>/            # Individual run workspaces
│       └── project/           # Cloned/uploaded project files
│
├── temp/                       # Temporary file storage (gitignored)
│
└── docs/                       # Documentation
    ├── README.md              # Main documentation
    ├── QUICKSTART.md          # Quick start guide
    └── PROJECT_STRUCTURE.md  # This file
```

---

## Core Components

### 1. Streamlit UI (`app.py`)
- **Purpose**: Main user interface for the application
- **Features**:
  - Four input methods (GitHub, ZIP, Folder, Single File)
  - Real-time processing status updates
  - Project analytics dashboard
  - Session management
- **Lines of Code**: ~620
- **Key Functions**:
  - `handle_github_input()` - Process GitHub URLs
  - `handle_zip_upload()` - Process ZIP files
  - `handle_folder_upload()` - Process folder uploads
  - `handle_single_file_upload()` - Process single files
  - `index_project()` - Index project files
  - `display_index_results()` - Show analytics

### 2. Git Tool (`tools/git_tool.py`)
- **Purpose**: Handle GitHub repository operations
- **Features**:
  - URL validation
  - Repository cloning (shallow by default)
  - Metadata extraction
  - Error handling and cleanup
- **Key Class**: `GitTool`
- **Key Methods**:
  - `validate_github_url()` - Validate GitHub URLs
  - `clone_repository()` - Clone repositories
  - `get_repo_name_from_url()` - Extract repo name

### 3. Unzip Tool (`tools/unzip_tool.py`)
- **Purpose**: Safely handle ZIP file operations
- **Features**:
  - File validation
  - Security checks (size, path traversal)
  - Safe extraction
  - Streamlit file handling
- **Key Class**: `UnzipTool`
- **Security Limits**:
  - Max file size: 500 MB
  - Max extracted size: 1 GB
  - Max files: 10,000
- **Key Methods**:
  - `validate_zip_file()` - Validate before extraction
  - `extract_zip()` - Safe extraction
  - `save_uploaded_zip()` - Handle Streamlit uploads

### 4. File Indexer (`tools/file_indexer.py`)
- **Purpose**: Analyze and categorize project files
- **Features**:
  - File categorization (Python, JS, TS, etc.)
  - Line counting
  - Directory tree building
  - Smart ignore rules
- **Key Classes**:
  - `FileInfo` - Data class for file information
  - `IndexResult` - Data class for indexing results
  - `FileIndexer` - Main indexer class
- **Categories Supported**: 15+ file types
- **Key Methods**:
  - `index_directory()` - Complete directory analysis
  - `get_file_category()` - Categorize files
  - `count_lines()` - Count lines in text files
  - `build_directory_tree()` - Generate tree structure

### 5. Configuration (`tools/config.py`)
- **Purpose**: Centralized configuration management
- **Features**:
  - Environment variable support
  - Validation
  - Default values
  - Path management
- **Key Class**: `Config`
- **Configuration Domains**:
  - Google Cloud / Vertex AI
  - File upload limits
  - Logging
  - Git settings
  - Test execution (future)

---

## File Categories

The indexer recognizes these file categories:

| Category       | Extensions                                    |
|----------------|-----------------------------------------------|
| Python         | `.py`                                         |
| JavaScript     | `.js`, `.jsx`                                 |
| TypeScript     | `.ts`, `.tsx`                                 |
| Test           | `.test.js`, `.spec.ts`, etc.                 |
| HTML/CSS       | `.html`, `.css`, `.scss`, `.sass`, `.less`   |
| Config         | `.json`, `.yaml`, `.toml`, `.ini`, `.xml`    |
| Documentation  | `.md`, `.rst`, `.txt`                        |
| Database       | `.sql`, `.db`, `.sqlite`                     |
| Script         | `.sh`, `.bat`, `.ps1`                        |
| Java           | `.java`                                       |
| C/C++          | `.c`, `.cpp`                                  |
| C#             | `.cs`                                         |
| Go             | `.go`                                         |
| Rust           | `.rs`                                         |
| Ruby           | `.rb`                                         |
| PHP            | `.php`                                        |
| Swift          | `.swift`                                      |
| Kotlin         | `.kt`                                         |

---

## Ignored Directories

The following directories are automatically ignored during indexing:

- `__pycache__`
- `node_modules`
- `.git`
- `.venv`, `venv`, `env`
- `.pytest_cache`
- `.coverage`, `coverage`
- `dist`, `build`
- `.next`, `.nuxt`
- `.idea`, `.vscode`
- `vendor`

---

## Sandboxing Strategy

### Workspace Isolation
- Each run gets unique UUID-based workspace: `/workspaces/run_<uuid>/project`
- Projects copied to isolated directories
- No direct access to user file system
- Cleanup support for failed operations

### Security Measures
1. **Input Validation**: All inputs validated before processing
2. **Size Limits**: Enforced file and archive size limits
3. **Path Validation**: Prevention of directory traversal attacks
4. **Error Handling**: Comprehensive error handling with cleanup
5. **Logging**: All operations logged for audit trail

---

## Data Flow

### 1. GitHub Repository Flow
```
User Input (URL)
    ↓
GitTool.validate_github_url()
    ↓
Create sandbox: /workspaces/run_<uuid>/project
    ↓
GitTool.clone_repository()
    ↓
FileIndexer.index_directory()
    ↓
Display results
```

### 2. ZIP Upload Flow
```
User Upload (ZIP file)
    ↓
UnzipTool.save_uploaded_zip()
    ↓
UnzipTool.validate_zip_file()
    ↓
Create sandbox: /workspaces/run_<uuid>/project
    ↓
UnzipTool.extract_zip()
    ↓
FileIndexer.index_directory()
    ↓
Display results
```

### 3. Folder/File Upload Flow
```
User Upload (Files)
    ↓
Create sandbox: /workspaces/run_<uuid>/project
    ↓
Copy files preserving structure
    ↓
FileIndexer.index_directory()
    ↓
Display results
```

---

## Error Handling Strategy

### Layers of Error Handling

1. **Input Validation Layer**
   - Validate URLs, file formats, sizes
   - Return clear error messages
   - No processing on invalid input

2. **Processing Layer**
   - Try-catch blocks around all operations
   - Detailed error logging
   - Cleanup on failure

3. **Cleanup Layer**
   - Remove partial files on failure
   - Clean temporary directories
   - Preserve workspace for debugging if needed

4. **User Feedback Layer**
   - Status messages in UI
   - Success/error/warning indicators
   - Processing logs

---

## Session Management

### Session State Variables
- `run_id`: Unique identifier for current run
- `project_path`: Path to sandboxed project
- `index_result`: File indexing results
- `processing_status`: List of status messages
- `metadata`: Additional run metadata

### Session Lifecycle
1. User opens app → Initialize session state
2. User provides input → Generate run ID
3. Process input → Update status messages
4. Display results → Show analytics
5. Reset button → Clear session, start new run

---

## Testing & Validation

### Setup Script (`setup.py`)
- Python version check (3.9+)
- Git installation check
- Directory creation
- Dependency installation
- Import verification
- Tools module validation

### Validation Script (`validate.py`)
- Directory structure verification
- Module import tests
- GitTool functionality tests
- UnzipTool functionality tests
- FileIndexer functionality tests
- Config validation tests

### Running Tests
```bash
# Setup and install
python setup.py

# Validate installation
python validate.py
```

---

## Future Extensions

### Phase 2: Test Generation
- LLM integration (Vertex AI Gemini)
- Test case generation for Jest/Pytest
- Context-aware test creation
- Template system

### Phase 3: Test Execution
- Jest runner integration
- Pytest runner integration
- Sandboxed execution
- Output capture and parsing

### Phase 4: Agent Orchestration
- LangGraph integration
- Multi-agent workflow
- Decision-making logic
- Iterative improvement

### Phase 5: Production Features
- CI/CD integration
- API endpoints
- Report generation
- Custom test strategies

---

## Performance Considerations

### Current Optimizations
- Shallow Git clones (depth=1)
- Streaming file processing
- Efficient directory traversal
- Smart ignore rules for large directories

### Future Optimizations
- Parallel file processing
- Caching of indexing results
- Incremental indexing
- Background processing

---

## Security Considerations

### Input Security
- URL validation
- File size limits
- Path traversal prevention
- ZIP bomb protection

### Execution Security
- Sandboxed workspaces
- No direct file system access
- Process isolation (future)
- Resource limits

### Data Security
- No persistent storage of user code
- Workspace cleanup
- Secure credential handling
- Environment variable isolation

---

## Monitoring & Logging

### Logging Levels
- **INFO**: Normal operations (cloning, indexing, etc.)
- **WARNING**: Non-critical issues (ignored files, etc.)
- **ERROR**: Failures and exceptions
- **DEBUG**: Detailed debugging information

### Log Format
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### What Gets Logged
- All tool operations
- File processing steps
- Error details
- User actions
- System events

---

## Dependencies

### Core Dependencies
- `streamlit` - UI framework
- `GitPython` - Git operations
- `google-cloud-aiplatform` - Vertex AI (future)
- `pytest` - Test execution (future)
- `python-dotenv` - Environment variables

### Development Dependencies
- `pytest` - Testing
- `pytest-cov` - Coverage
- `typing-extensions` - Type hints

---

## Configuration Files

### `.gitignore`
- Python artifacts
- Virtual environments
- IDE files
- Generated workspaces
- Temporary files
- Logs

### `.streamlit/config.toml`
- UI theme settings
- Server configuration
- Upload size limits
- Security settings

### `config.env.example`
- Environment variable template
- Google Cloud configuration
- Application settings
- Defaults and limits

---

## Module Interdependencies

```
app.py
├── tools.git_tool (GitTool)
├── tools.unzip_tool (UnzipTool)
├── tools.file_indexer (FileIndexer)
└── tools.config (Config)

tools/__init__.py
├── .git_tool
├── .unzip_tool
└── .file_indexer

Each tool module:
├── Independent functionality
├── Comprehensive error handling
├── Logging integration
└── Type hints and documentation
```

---

## Code Quality Standards

### Documentation
- Module-level docstrings
- Class-level docstrings
- Method-level docstrings
- Inline comments for complex logic

### Type Hints
- All function signatures typed
- Return types specified
- Optional types where applicable
- Tuple return types documented

### Error Handling
- Try-catch blocks
- Cleanup on failure
- Meaningful error messages
- Logging of errors

### Code Style
- PEP 8 compliant
- Consistent naming
- Modular design
- Single responsibility principle

---

**Status**: Phase 1 Complete ✓

**Next Phase**: Test Generation with LLM Integration

