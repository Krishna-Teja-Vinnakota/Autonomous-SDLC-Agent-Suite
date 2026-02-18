"""
Configuration management for AutoSDLC Test Agent
Centralizes all configuration settings with environment variable support
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Central configuration class for the application
    Provides access to all configurable parameters
    """
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent
    WORKSPACE_ROOT = PROJECT_ROOT / "workspaces"
    TEMP_DIR = PROJECT_ROOT / "temp"
    
    # Google Cloud / Vertex AI Configuration
    GOOGLE_CLOUD_PROJECT: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_REGION: str = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    # Vertex AI Model Configuration
    VERTEX_AI_MODEL: str = os.getenv("VERTEX_AI_MODEL", "gemini-pro")
    VERTEX_AI_TEMPERATURE: float = float(os.getenv("VERTEX_AI_TEMPERATURE", "0.7"))
    VERTEX_AI_MAX_TOKENS: int = int(os.getenv("VERTEX_AI_MAX_TOKENS", "2048"))
    
    # File Upload Limits
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    MAX_EXTRACTED_SIZE_MB: int = int(os.getenv("MAX_EXTRACTED_SIZE_MB", "1024"))
    MAX_FILES_PER_ARCHIVE: int = int(os.getenv("MAX_FILES_PER_ARCHIVE", "10000"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Git Configuration
    GIT_CLONE_DEPTH: int = int(os.getenv("GIT_CLONE_DEPTH", "1"))
    GIT_TIMEOUT: int = int(os.getenv("GIT_TIMEOUT", "300"))  # seconds
    
    # Test Generation Configuration (for future use)
    JEST_TIMEOUT: int = int(os.getenv("JEST_TIMEOUT", "60"))  # seconds
    PYTEST_TIMEOUT: int = int(os.getenv("PYTEST_TIMEOUT", "60"))  # seconds
    
    @classmethod
    def validate(cls) -> tuple[bool, list[str]]:
        """
        Validate configuration settings
        
        Returns:
            tuple[bool, list[str]]: (is_valid, error_messages)
        """
        errors = []
        
        # Validate paths exist or can be created
        try:
            cls.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
            cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Failed to create workspace directories: {e}")
        
        # Validate numeric ranges
        if cls.MAX_UPLOAD_SIZE_MB < 1:
            errors.append("MAX_UPLOAD_SIZE_MB must be at least 1")
        
        if cls.MAX_EXTRACTED_SIZE_MB < 1:
            errors.append("MAX_EXTRACTED_SIZE_MB must be at least 1")
        
        if cls.MAX_FILES_PER_ARCHIVE < 1:
            errors.append("MAX_FILES_PER_ARCHIVE must be at least 1")
        
        if not 0.0 <= cls.VERTEX_AI_TEMPERATURE <= 2.0:
            errors.append("VERTEX_AI_TEMPERATURE must be between 0.0 and 2.0")
        
        if cls.VERTEX_AI_MAX_TOKENS < 1:
            errors.append("VERTEX_AI_MAX_TOKENS must be at least 1")
        
        return len(errors) == 0, errors
    
    @classmethod
    def get_vertex_ai_config(cls) -> dict:
        """
        Get Vertex AI configuration as a dictionary
        
        Returns:
            dict: Vertex AI configuration
        """
        return {
            'project': cls.GOOGLE_CLOUD_PROJECT,
            'region': cls.GOOGLE_CLOUD_REGION,
            'model': cls.VERTEX_AI_MODEL,
            'temperature': cls.VERTEX_AI_TEMPERATURE,
            'max_tokens': cls.VERTEX_AI_MAX_TOKENS,
        }
    
    @classmethod
    def get_file_limits(cls) -> dict:
        """
        Get file upload limits as a dictionary
        
        Returns:
            dict: File upload limits
        """
        return {
            'max_upload_size_bytes': cls.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
            'max_extracted_size_bytes': cls.MAX_EXTRACTED_SIZE_MB * 1024 * 1024,
            'max_files_per_archive': cls.MAX_FILES_PER_ARCHIVE,
        }


# Validate configuration on import
is_valid, validation_errors = Config.validate()
if not is_valid:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Configuration validation errors: {validation_errors}")

