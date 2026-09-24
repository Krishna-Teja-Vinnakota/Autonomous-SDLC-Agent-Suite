"""
Example test file demonstrating pytest usage
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


@pytest.mark.unit
def test_sample_project_structure(sample_project_structure):
    """Example test using sample project fixture"""
    assert sample_project_structure.exists()
    assert (sample_project_structure / "main.py").exists()
    assert (sample_project_structure / "src" / "module.py").exists()

