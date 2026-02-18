# Pytest Setup Guide

This project is configured with pytest for testing. This guide explains how to use pytest in this project.

## Installation

Pytest and related plugins are already included in `requirements.txt`. To install:

```bash
pip install -r requirements.txt
```

## Configuration

The project includes:
- **pytest.ini** - Main pytest configuration file
- **conftest.py** - Shared fixtures and test configuration
- **tests/** - Directory for test files

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_example.py

# Run tests matching a pattern
pytest -k "test_name"

# Run tests in a specific directory
pytest tests/
```

### Coverage Reports

```bash
# Run tests with coverage
pytest --cov=. --cov-report=html --cov-report=term

# View coverage report
# Open coverage/htmlcov/index.html in your browser
```

### Parallel Execution

```bash
# Run tests in parallel (faster)
pytest -n auto

# Or specify number of workers
pytest -n 4
```

### Test Markers

Tests can be marked and run selectively:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests excluding slow ones
pytest -m "not slow"
```

Available markers:
- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.requires_vertex_ai` - Tests requiring Vertex AI
- `@pytest.mark.requires_network` - Tests requiring network access

## Writing Tests

### Basic Test Structure

```python
import pytest

def test_something():
    """Test description"""
    assert 1 + 1 == 2
```

### Using Fixtures

```python
import pytest

@pytest.mark.unit
def test_with_temp_dir(temp_dir):
    """Test using temporary directory fixture"""
    test_file = temp_dir / "test.txt"
    test_file.write_text("Hello")
    assert test_file.exists()
```

### Available Fixtures

From `conftest.py`:
- `project_root` - Project root directory
- `temp_dir` - Temporary directory (auto-cleaned)
- `temp_workspace` - Temporary workspace directory
- `sample_project_structure` - Sample project structure for testing
- `mock_vertex_ai_config` - Mock Vertex AI configuration
- `sample_git_repo` - Sample git repository structure

### Test Organization

- Test files should be named `test_*.py` or `*_test.py`
- Test classes should be named `Test*`
- Test functions should be named `test_*`
- Place test files in the `tests/` directory or alongside source files

## Example Test File

```python
"""
Example test file
"""
import pytest
from pathlib import Path

@pytest.mark.unit
def test_example():
    """Simple example test"""
    assert 1 + 1 == 2

@pytest.mark.unit
def test_path_operations(temp_dir):
    """Example test using fixtures"""
    test_file = temp_dir / "test.txt"
    test_file.write_text("Hello, pytest!")
    
    assert test_file.exists()
    assert test_file.read_text() == "Hello, pytest!"
```

## Pytest Plugins Installed

- **pytest** - Core testing framework
- **pytest-cov** - Coverage reporting
- **pytest-mock** - Mocking utilities
- **pytest-asyncio** - Async test support
- **pytest-timeout** - Test timeout handling
- **pytest-xdist** - Parallel test execution

## Troubleshooting

### Tests not discovered
- Ensure test files are named `test_*.py` or `*_test.py`
- Check that test functions start with `test_`
- Verify `pytest.ini` configuration

### Import errors
- Ensure project root is in Python path
- Check that `conftest.py` is in the root directory
- Verify all dependencies are installed

### Coverage not working
- Ensure `pytest-cov` is installed
- Check coverage configuration in `pytest.ini`

## Next Steps

1. Write tests for your modules in the `tests/` directory
2. Use markers to categorize tests
3. Run tests regularly during development
4. Check coverage reports to identify untested code

For more information, see the [pytest documentation](https://docs.pytest.org/).

