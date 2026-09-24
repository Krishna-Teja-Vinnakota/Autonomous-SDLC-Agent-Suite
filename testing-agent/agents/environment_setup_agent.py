"""
Environment Setup Agent
Configures test environment for integration and feature tests
Handles MSW, pytest fixtures, and test setup files
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from config.vertex_ai import GeminiClient

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentSetupResult:
    """Result of environment setup"""
    success: bool
    test_level: str  # unit, integration, feature
    framework: str  # jest or pytest
    setup_files: List[str]  # Files created/modified
    message: str
    error: Optional[str] = None


class EnvironmentSetupAgent:
    """
    Agent for setting up test environment
    Configures MSW, fixtures, and other test dependencies
    """
    
    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        """
        Initialize environment setup agent
        
        Args:
            gemini_client: Optional Gemini client for AI-assisted setup
        """
        self.client = gemini_client
    
    def setup_environment(
        self,
        test_level: str,
        framework: str,
        project_path: Path,
        strategies: List[Any]
    ) -> EnvironmentSetupResult:
        """
        Setup environment for test level
        
        Args:
            test_level: unit, integration, or feature
            framework: jest or pytest
            project_path: Path to project directory
            strategies: Test strategies for this level
            
        Returns:
            EnvironmentSetupResult: Setup result
        """
        logger.info(f"Setting up environment for {test_level} tests with {framework}")
        
        try:
            setup_files = []
            
            # Unit tests need minimal setup
            if test_level == 'unit':
                return EnvironmentSetupResult(
                    success=True,
                    test_level=test_level,
                    framework=framework,
                    setup_files=[],
                    message="No special setup needed for unit tests"
                )
            
            # Integration and feature tests need environment setup
            if framework == 'jest':
                setup_files = self._setup_jest_integration_environment(
                    project_path, test_level, strategies
                )
            elif framework == 'pytest':
                setup_files = self._setup_pytest_integration_environment(
                    project_path, test_level, strategies
                )
            
            return EnvironmentSetupResult(
                success=True,
                test_level=test_level,
                framework=framework,
                setup_files=setup_files,
                message=f"Environment setup complete for {test_level} {framework} tests"
            )
            
        except Exception as e:
            logger.error(f"Environment setup error: {e}")
            return EnvironmentSetupResult(
                success=False,
                test_level=test_level,
                framework=framework,
                setup_files=[],
                message="Environment setup failed",
                error=str(e)
            )
    
    def _setup_jest_integration_environment(
        self,
        project_path: Path,
        test_level: str,
        strategies: List[Any]
    ) -> List[str]:
        """Setup Jest environment for integration/feature tests"""
        setup_files = []
        
        # Check if setupTests.ts exists, create if needed
        setup_tests_path = project_path / 'setupTests.ts'
        if not setup_tests_path.exists():
            self._create_setup_tests_file(setup_tests_path)
            setup_files.append(str(setup_tests_path))
            logger.info(f"Created setupTests.ts")
        
        # For integration/feature tests, ensure MSW setup exists
        if test_level in ['integration', 'feature']:
            # Create MSW handlers directory
            msw_dir = project_path / 'mocks'
            msw_dir.mkdir(exist_ok=True)
            
            # Create handlers.ts for MSW
            handlers_path = msw_dir / 'handlers.ts'
            if not handlers_path.exists():
                self._create_msw_handlers(handlers_path)
                setup_files.append(str(handlers_path))
                logger.info(f"Created MSW handlers")
            
            # Create server.ts for MSW
            server_path = msw_dir / 'server.ts'
            if not server_path.exists():
                self._create_msw_server(server_path)
                setup_files.append(str(server_path))
                logger.info(f"Created MSW server")
        
        # Ensure jest.setup.js has proper environment configuration
        jest_setup_path = project_path / 'jest.setup.js'
        if jest_setup_path.exists():
            self._update_jest_setup_for_integration(jest_setup_path, test_level)
            logger.info(f"Updated jest.setup.js for {test_level} tests")
        
        return setup_files
    
    def _setup_pytest_integration_environment(
        self,
        project_path: Path,
        test_level: str,
        strategies: List[Any]
    ) -> List[str]:
        """Setup pytest environment for integration/feature tests"""
        setup_files = []
        
        # Create/update conftest.py for fixtures
        conftest_path = project_path / 'conftest.py'
        if not conftest_path.exists():
            self._create_pytest_conftest(conftest_path, test_level)
            setup_files.append(str(conftest_path))
            logger.info(f"Created conftest.py with fixtures")
        else:
            # Update existing conftest with integration fixtures
            self._update_pytest_conftest(conftest_path, test_level)
            logger.info(f"Updated conftest.py for {test_level} tests")
        
        # For integration tests, create fixtures directory
        if test_level in ['integration', 'feature']:
            fixtures_dir = project_path / 'tests' / 'fixtures'
            fixtures_dir.mkdir(parents=True, exist_ok=True)
            
            # Create fixture file
            fixture_init = fixtures_dir / '__init__.py'
            if not fixture_init.exists():
                fixture_init.write_text("# Test fixtures\n")
                setup_files.append(str(fixture_init))
        
        return setup_files
    
    def _create_setup_tests_file(self, path: Path) -> None:
        """Create setupTests.ts for Jest"""
        content = """// Jest setup file for integration and feature tests
import '@testing-library/jest-dom';

// Setup MSW (Mock Service Worker) for API mocking
// Uncomment if using MSW:
// import { server } from './mocks/server';
// 
// beforeAll(() => server.listen());
// afterEach(() => server.resetHandlers());
// afterAll(() => server.close());

// Global test timeout for integration tests
jest.setTimeout(10000);
"""
        path.write_text(content, encoding='utf-8')
    
    def _create_msw_handlers(self, path: Path) -> None:
        """Create MSW handlers template"""
        content = """// MSW API handlers for integration tests
import { rest } from 'msw';

export const handlers = [
  // Example API handler - replace with your actual API endpoints
  rest.get('/api/data', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: 'mocked response'
      })
    );
  }),
  
  rest.post('/api/data', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        success: true
      })
    );
  }),
];
"""
        path.write_text(content, encoding='utf-8')
    
    def _create_msw_server(self, path: Path) -> None:
        """Create MSW server configuration"""
        content = """// MSW server setup
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Setup mock server with handlers
export const server = setupServer(...handlers);
"""
        path.write_text(content, encoding='utf-8')
    
    def _update_jest_setup_for_integration(self, path: Path, test_level: str) -> None:
        """Update jest.setup.js for integration tests"""
        try:
            content = path.read_text(encoding='utf-8')
            
            # Check if timeout is already set
            if 'setTimeout' not in content:
                # Add timeout configuration
                timeout_config = "\n// Increased timeout for integration/feature tests\njest.setTimeout(15000);\n"
                content += timeout_config
                path.write_text(content, encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not update jest.setup.js: {e}")
    
    def _create_pytest_conftest(self, path: Path, test_level: str) -> None:
        """Create conftest.py with pytest fixtures"""
        content = """# Pytest configuration and fixtures
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    \"\"\"Fixture providing project root path\"\"\"
    return Path(__file__).parent


@pytest.fixture(scope="function")
def mock_data():
    \"\"\"Fixture providing mock data for tests\"\"\"
    return {
        "test_data": "mock value",
        "status": "success"
    }


# Integration test fixtures
@pytest.fixture(scope="module")
def integration_setup():
    \"\"\"Setup for integration tests\"\"\"
    # Setup code here
    yield
    # Teardown code here


# Feature test fixtures
@pytest.fixture(scope="session")
def feature_setup():
    \"\"\"Setup for feature tests\"\"\"
    # Setup code here
    yield
    # Teardown code here


# Increase timeout for integration/feature tests
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "feature: mark test as feature test"
    )
"""
        path.write_text(content, encoding='utf-8')
    
    def _update_pytest_conftest(self, path: Path, test_level: str) -> None:
        """Update existing conftest.py with integration fixtures"""
        try:
            content = path.read_text(encoding='utf-8')
            
            # Check if integration fixtures already exist
            if 'integration_setup' not in content and test_level == 'integration':
                fixture_code = """

# Integration test fixtures (auto-added)
@pytest.fixture(scope="module")
def integration_setup():
    \"\"\"Setup for integration tests\"\"\"
    yield
"""
                content += fixture_code
                path.write_text(content, encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not update conftest.py: {e}")
    
    def ensure_jest_config_for_integration(self, project_path: Path) -> bool:
        """Ensure jest.config.js has proper settings for integration tests"""
        jest_config_path = project_path / 'jest.config.js'
        
        if not jest_config_path.exists():
            logger.warning("jest.config.js not found")
            return False
        
        try:
            content = jest_config_path.read_text(encoding='utf-8')
            
            # Check if testEnvironment is set to jsdom (needed for React tests)
            if 'testEnvironment' not in content or 'jsdom' not in content:
                logger.info("jest.config.js may need testEnvironment: 'jsdom' for integration tests")
            
            return True
        except Exception as e:
            logger.error(f"Error checking jest.config.js: {e}")
            return False
