# Test Suite

This directory contains the test suite for the SDLC Testing Agent project.

## Running Tests

### Run all tests
```bash
pytest
```

### Run tests with coverage
```bash
pytest --cov=. --cov-report=html --cov-report=term
```

### Run specific test file
```bash
pytest tests/test_specific_module.py
```

### Run tests matching a pattern
```bash
pytest -k "test_name_pattern"
```

### Run tests in parallel (faster)
```bash
pytest -n auto
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run tests with verbose output
```bash
pytest -v
```

### Run tests and stop on first failure
```bash
pytest -x
```

## Test Organization

- `test_*.py` - Test files should follow this naming convention
- Tests are organized by module/component
- Use markers to categorize tests:
  - `@pytest.mark.unit` - Fast unit tests
  - `@pytest.mark.integration` - Integration tests
  - `@pytest.mark.slow` - Slow running tests
  - `@pytest.mark.requires_vertex_ai` - Tests requiring Vertex AI
  - `@pytest.mark.requires_network` - Tests requiring network access

## Example Test

```python
import pytest
from tools.git_tool import GitTool

@pytest.mark.unit
def test_git_tool_initialization():
    """Test that GitTool can be initialized"""
    tool = GitTool()
    assert tool is not None
```

## Coverage

Coverage reports are generated in the `coverage/` directory. Open `coverage/htmlcov/index.html` in a browser to view the HTML coverage report.

