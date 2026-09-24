"""
Vertex AI Gemini Configuration and Client
Handles authentication and interaction with Google's Gemini LLM
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class VertexAIConfig:
    """
    Configuration class for Vertex AI Gemini
    Manages credentials, project settings, and model configuration
    """
    
    def __init__(self):
        """Initialize Vertex AI configuration from environment variables"""
        self.project_id: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location: str = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
        self.credentials_path: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # Auto-detect credentials file if not set and exists in project root
        if not self.credentials_path:
            project_root = Path(__file__).parent.parent
            # Check for common credential file names
            credential_files = [
                project_root / "credentials.json",
                project_root / "service-account-key.json",
            ]
            for cred_file in credential_files:
                if cred_file.exists():
                    self.credentials_path = str(cred_file)
                    logger.info(f"Auto-detected credentials file: {cred_file}")
                    break
        
        # Auto-detect project ID from credentials file if available
        if not self.project_id and self.credentials_path:
            try:
                import json
                with open(self.credentials_path, 'r') as f:
                    cred_data = json.load(f)
                    if 'project_id' in cred_data:
                        self.project_id = cred_data['project_id']
                        logger.info(f"Auto-detected project ID from credentials: {self.project_id}")
            except Exception as e:
                logger.debug(f"Could not read project_id from credentials: {e}")
        
        # Model configuration - prefer gemini-2.0-flash, fallback to gemini-2.5-pro
        model_env = os.getenv("VERTEX_AI_MODEL", "").strip()
        if model_env:
            self.model_name = model_env
        else:
            # Default to gemini-2.0-flash, fallback to gemini-2.5-pro if not available
            self.model_name = "gemini-2.0-flash"
        self.temperature: float = float(os.getenv("VERTEX_AI_TEMPERATURE", "0.3"))
        self.max_output_tokens: int = int(os.getenv("VERTEX_AI_MAX_TOKENS", "2048"))
        self.top_p: float = float(os.getenv("VERTEX_AI_TOP_P", "0.95"))
        self.top_k: int = int(os.getenv("VERTEX_AI_TOP_K", "40"))
        
        # Validation flags
        self._is_configured = False
        self._validation_errors: List[str] = []
        
        # Validate on initialization
        self._validate()
    
    def _validate(self) -> None:
        """Validate configuration and set flags"""
        self._validation_errors = []
        
        # Check project ID
        if not self.project_id:
            self._validation_errors.append("GOOGLE_CLOUD_PROJECT environment variable not set")
        
        # Check credentials
        if not self.credentials_path:
            self._validation_errors.append("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        elif not Path(self.credentials_path).exists():
            self._validation_errors.append(f"Credentials file not found: {self.credentials_path}")
        
        # Check parameter ranges
        if not 0.0 <= self.temperature <= 2.0:
            self._validation_errors.append("Temperature must be between 0.0 and 2.0")
        
        if self.max_output_tokens < 1:
            self._validation_errors.append("Max output tokens must be positive")
        
        if not 0.0 <= self.top_p <= 1.0:
            self._validation_errors.append("Top-p must be between 0.0 and 1.0")
        
        if self.top_k < 1:
            self._validation_errors.append("Top-k must be positive")
        
        self._is_configured = len(self._validation_errors) == 0
    
    def is_configured(self) -> bool:
        """Check if Vertex AI is properly configured"""
        return self._is_configured
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors"""
        return self._validation_errors.copy()
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Get generation configuration for Gemini"""
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }
    
    def __repr__(self) -> str:
        """String representation of configuration"""
        return (
            f"VertexAIConfig("
            f"project={self.project_id}, "
            f"location={self.location}, "
            f"model={self.model_name}, "
            f"configured={self._is_configured})"
        )


class GeminiClient:
    """
    Client for interacting with Vertex AI Gemini
    Provides high-level interface for LLM operations
    """
    
    def __init__(self, config: VertexAIConfig):
        """
        Initialize Gemini client
        
        Args:
            config: VertexAIConfig instance
        """
        self.config = config
        self._model = None
        self._initialized = False
        
        if config.is_configured():
            self._initialize()
    
    def _initialize(self) -> None:
        """Initialize Vertex AI and create model instance"""
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            
            # Initialize Vertex AI with credentials
            if self.config.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.config.credentials_path
            
            vertexai.init(
                project=self.config.project_id,
                location=self.config.location
            )
            
            # Create model instance with fallback logic
            try:
                self._model = GenerativeModel(self.config.model_name)
                self._initialized = True
                logger.info(f"Initialized Vertex AI Gemini: {self.config.model_name}")
            except Exception as model_error:
                # Fallback to gemini-2.5-pro if gemini-2.0-flash not available
                if "gemini-2.0-flash" in self.config.model_name.lower():
                    logger.warning(f"Model {self.config.model_name} not available, trying gemini-2.5-pro")
                    try:
                        self._model = GenerativeModel("gemini-2.5-pro")
                        self._initialized = True
                        logger.info("Initialized Vertex AI Gemini: gemini-2.5-pro (fallback)")
                    except Exception as fallback_error:
                        logger.error(f"Failed to initialize fallback model: {fallback_error}")
                        raise model_error
                else:
                    raise
            
        except ImportError as e:
            logger.error(f"Failed to import Vertex AI libraries: {e}")
            raise ImportError(
                "Vertex AI libraries not found. Install with: pip install google-cloud-aiplatform"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if client is ready to use"""
        return self._initialized and self._model is not None
    
    def generate_content(
        self,
        prompt: str,
        generation_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate content using Gemini
        
        Args:
            prompt: Text prompt for generation
            generation_config: Optional custom generation config
            
        Returns:
            str: Generated text response
            
        Raises:
            RuntimeError: If client not initialized
            Exception: If generation fails
        """
        if not self.is_ready():
            raise RuntimeError("Gemini client not initialized. Check configuration.")
        
        try:
            # Use custom config or default
            config = generation_config or self.config.get_generation_config()
            
            logger.debug(f"Generating content with prompt length: {len(prompt)}")
            
            # Generate content
            response = self._model.generate_content(
                prompt,
                generation_config=config
            )
            
            # Extract text from response
            if response and response.text:
                logger.info("Content generated successfully")
                return response.text
            else:
                logger.warning("Empty response from Gemini")
                return ""
                
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
    
    def generate_content_stream(
        self,
        prompt: str,
        generation_config: Optional[Dict[str, Any]] = None
    ):
        """
        Generate content with streaming (for future use)
        
        Args:
            prompt: Text prompt for generation
            generation_config: Optional custom generation config
            
        Yields:
            str: Chunks of generated text
            
        Raises:
            RuntimeError: If client not initialized
        """
        if not self.is_ready():
            raise RuntimeError("Gemini client not initialized. Check configuration.")
        
        try:
            config = generation_config or self.config.get_generation_config()
            
            response_stream = self._model.generate_content(
                prompt,
                generation_config=config,
                stream=True
            )
            
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise


def get_gemini_client() -> Optional[GeminiClient]:
    """
    Factory function to create and return a GeminiClient
    
    Returns:
        Optional[GeminiClient]: Client instance if configured, None otherwise
    """
    try:
        config = VertexAIConfig()
        
        if not config.is_configured():
            errors = config.get_validation_errors()
            logger.warning(f"Vertex AI not configured: {errors}")
            return None
        
        client = GeminiClient(config)
        
        if client.is_ready():
            return client
        else:
            logger.warning("Gemini client created but not ready")
            return None
            
    except Exception as e:
        logger.error(f"Failed to create Gemini client: {e}")
        return None

