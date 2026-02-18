"""
Configuration package for AutoSDLC-Test-Agent
Contains Vertex AI and other configuration modules
"""

from .vertex_ai import VertexAIConfig, get_gemini_client

__all__ = ['VertexAIConfig', 'get_gemini_client']

