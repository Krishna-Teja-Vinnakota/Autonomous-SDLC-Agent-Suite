"""
Test Executor Agent
Executes generated tests with retry logic and result parsing
"""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from tools.command_executor import CommandExecutor, CommandResult
from agents.test_generator_agent import GeneratedTest

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """Individual test case result"""
    name: str
    status: str  # passed, failed, skipped
    duration: float
    error_message: Optional[str] = None
    file: Optional[str] = None


@dataclass
class TestExecutionResult:
    """Result of test execution"""
    framework: str  # jest or pytest
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration: float
    exit_code: int
    success: bool
    test_cases: List[TestCase] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    attempt: int = 1
    max_attempts: int = 3
    timed_out: bool = False


class TestExecutorAgent:
    """
    Agent for executing tests with retry logic
    Parses test output and provides structured results
    """
    
    MAX_RETRIES = 3
    
    def __init__(self, project_path: Path):
        """
        Initialize test executor
        
        Args:
            project_path: Path to project directory
        """
        self.project_path = project_path
        self.executor = CommandExecutor(project_path)
    
    def execute_tests(
        self,
        framework: str,
        timeout: int = 300,
        generated_tests: Optional[List[GeneratedTest]] = None,
        test_level: Optional[str] = None  # NEW: unit, integration, or feature
    ) -> TestExecutionResult:
        """
        Execute tests with retry logic
        
        Args:
            framework: 'jest' or 'pytest'
            timeout: Timeout per attempt in seconds
            generated_tests: Optional list of generated test files to execute (if None, searches for all test files)
            test_level: Optional test level (unit, integration, feature) for execution optimization
            
        Returns:
            TestExecutionResult: Execution result
        """
        level_info = f" ({test_level} level)" if test_level else ""
        logger.info(f"Executing {framework} tests{level_info} with retry (max {self.MAX_RETRIES} attempts)")
        
        # Adjust retries based on test level
        max_retries = self.MAX_RETRIES
        if test_level == 'integration':
            max_retries = 2  # Integration tests get 2 retries
        elif test_level == 'feature':
            max_retries = 2  # Feature tests get 2 retries
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"Attempt {attempt}/{max_retries}")
            
            try:
                result = self._execute_single_attempt(framework, timeout, attempt, generated_tests, test_level)
                
                if result.success or attempt == max_retries:
                    # Success or final attempt
                    return result
                
                # Failed but have retries left
                logger.warning(f"Attempt {attempt} failed, retrying...")
                
            except Exception as e:
                logger.error(f"Error in attempt {attempt}: {e}")
                
                if attempt == max_retries:
                    # Return error result on final attempt
                    return TestExecutionResult(
                        framework=framework,
                        total_tests=0,
                        passed=0,
                        failed=0,
                        skipped=0,
                        duration=0,
                        exit_code=-1,
                        success=False,
                        stderr=str(e),
                        attempt=attempt,
                        max_attempts=max_retries
                    )
        
        # Should not reach here
        return TestExecutionResult(
            framework=framework,
            total_tests=0,
            passed=0,
            failed=0,
            skipped=0,
            duration=0,
            exit_code=-1,
            success=False,
            attempt=max_retries,
            max_attempts=max_retries
        )
    
    def _execute_single_attempt(
        self,
        framework: str,
        timeout: int,
        attempt: int,
        generated_tests: Optional[List[GeneratedTest]] = None,
        test_level: Optional[str] = None
    ) -> TestExecutionResult:
        """Execute single test attempt"""
        
        if framework == 'jest':
            return self._execute_jest(timeout, attempt, generated_tests, test_level)
        elif framework == 'pytest':
            return self._execute_pytest(timeout, attempt, generated_tests, test_level)
        else:
            raise ValueError(f"Unknown framework: {framework}")
    
    def _execute_jest(self, timeout: int, attempt: int, generated_tests: Optional[List[GeneratedTest]] = None, test_level: Optional[str] = None) -> TestExecutionResult:
        """Execute Jest tests with coverage"""
        
        # Check if npm is available
        npm_available = self.executor.check_command_available('npm')
        npx_available = self.executor.check_command_available('npx')
        
        if not npm_available and not npx_available:
            logger.error("Neither npm nor npx available")
            return TestExecutionResult(
                framework='jest',
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration=0,
                exit_code=-1,
                success=False,
                stderr="npm or npx command not available. Install Node.js and npm.",
                attempt=attempt,
                max_attempts=self.MAX_RETRIES
            )
        
        # Check if package.json exists
        package_json = self.project_path / 'package.json'
        
        # Prefer npx jest for better JSON output control (--outputFile works better)
        # Only use npm test if npx is not available
        use_npm = npm_available and package_json.exists() and not npx_available
        
        # If package.json doesn't exist but we have test files, set up Jest automatically
        if not package_json.exists() and npm_available:
            logger.info("package.json not found in workspace, setting up Jest automatically")
            self._setup_jest_in_workspace()
            # Recheck after setup
            if package_json.exists() and not npx_available:
                use_npm = True
        
        # Use generated test files if provided, otherwise search for all test files
        if generated_tests:
            # Filter for Jest framework and successful tests
            framework_tests = [t for t in generated_tests if t.framework == 'jest' and t.success]
            if framework_tests:
                # Use the specific test files that were generated
                test_files = []
                for gen_test in framework_tests:
                    test_path = self.project_path / gen_test.test_file_path
                    if test_path.exists():
                        test_files.append(test_path)
                        logger.info(f"Using generated test file: {gen_test.test_file_path}")
                    else:
                        logger.warning(f"Generated test file not found on disk: {test_path}")
                
                if not test_files:
                    logger.warning("Generated test files not found on disk")
                    return TestExecutionResult(
                        framework='jest',
                        total_tests=0,
                        passed=0,
                        failed=0,
                        skipped=0,
                        duration=0,
                        exit_code=-1,
                        success=False,
                        stderr="Generated Jest test files not found on disk",
                        attempt=attempt,
                        max_attempts=self.MAX_RETRIES
                    )
            else:
                logger.warning(f"No successful Jest tests in generated_tests, searching for all test files")
                test_files = self._find_test_files()
        else:
            # Fallback: search for all test files
            logger.info("No generated tests provided, searching for all test files in project directory")
            test_files = self._find_test_files()
        
        if not test_files:
            logger.warning("No test files found in project directory")
            return TestExecutionResult(
                framework=framework,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration=0,
                exit_code=-1,
                success=False,
                stderr="No test files found in project directory",
                attempt=attempt,
                max_attempts=self.MAX_RETRIES
            )
        
        logger.info(f"Found {len(test_files)} test file(s) to execute: {[str(f.relative_to(self.project_path)) for f in test_files[:5]]}")
        
        # Create JSON output file path
        json_output_file = self.project_path / 'jest-results.json'
        
        # Build command with JSON output and coverage
        # Add execution mode based on test level
        if use_npm:
            # Use npm test with coverage flags and explicit test file paths
            logger.info("Using npm test to execute Jest tests")
            command = self._build_jest_command_with_files(test_files, use_npm=True, json_output_file=json_output_file, test_level=test_level)
        else:
            # Use npx jest with coverage and explicit test file paths
            logger.info("Using npx jest to execute Jest tests")
            command = self._build_jest_command_with_files(test_files, use_npm=False, json_output_file=json_output_file, test_level=test_level)
        
        # Execute Jest command
        cmd_result = self.executor.execute(command, timeout=timeout)
        
        # Extract and save JSON output
        json_str = None
        
        # For npx jest with --outputFile, JSON should already be in the file
        if not use_npm and json_output_file.exists():
            try:
                json_str = json_output_file.read_text(encoding='utf-8')
                json.loads(json_str)  # Validate it's valid JSON
                logger.info(f"Read Jest JSON from output file: {json_output_file}")
            except Exception as e:
                logger.warning(f"Failed to read JSON from output file: {e}")
                json_str = None
        
        # If we don't have JSON from file, try to extract from stdout/stderr
        if not json_str:
            # First, try to extract JSON from stdout
            if cmd_result.stdout:
                try:
                    # Try to parse stdout as JSON directly
                    json.loads(cmd_result.stdout)
                    json_str = cmd_result.stdout
                    logger.info("Found valid JSON in Jest stdout")
                except json.JSONDecodeError:
                    # Try to extract JSON from mixed output
                    json_str = self._extract_json_from_output(cmd_result.stdout)
                    if json_str:
                        logger.info("Extracted JSON from Jest stdout")
            
            # If no JSON in stdout, check stderr (Jest might output JSON to stderr in some cases)
            if not json_str and cmd_result.stderr:
                try:
                    json.loads(cmd_result.stderr)
                    json_str = cmd_result.stderr
                    logger.info("Found valid JSON in Jest stderr")
                except json.JSONDecodeError:
                    json_str_from_stderr = self._extract_json_from_output(cmd_result.stderr)
                    if json_str_from_stderr:
                        json_str = json_str_from_stderr
                        logger.info("Extracted JSON from Jest stderr")
        
        # Save JSON to file if we found valid JSON
        if json_str:
            try:
                json_output_file.write_text(json_str, encoding='utf-8')
                logger.info(f"Saved Jest JSON output to file: {json_output_file}")
                
                # Also copy to reports directory for UI access
                reports_dir = self.project_path / 'reports'
                reports_dir.mkdir(exist_ok=True)
                jest_json_report = reports_dir / 'jest-results.json'
                shutil.copy2(json_output_file, jest_json_report)
                logger.info(f"Copied Jest JSON to reports directory: {jest_json_report}")
                
                # Update cmd_result with extracted JSON for parsing
                from tools.command_executor import CommandResult
                cmd_result = CommandResult(
                    command=cmd_result.command,
                    exit_code=cmd_result.exit_code,
                    stdout=json_str,  # Use extracted JSON
                    stderr=cmd_result.stderr,
                    duration=cmd_result.duration,
                    success=cmd_result.success,
                    timed_out=cmd_result.timed_out
                )
            except Exception as e:
                logger.warning(f"Failed to save Jest JSON output: {e}")
        else:
            logger.warning("No valid JSON found in Jest output (stdout or stderr)")
            # Log more details for debugging
            if cmd_result.stdout:
                logger.debug(f"Jest stdout length: {len(cmd_result.stdout)} chars")
                logger.debug(f"Jest stdout (first 1000 chars): {cmd_result.stdout[:1000]}")
            if cmd_result.stderr:
                logger.debug(f"Jest stderr length: {len(cmd_result.stderr)} chars")
                logger.debug(f"Jest stderr (first 1000 chars): {cmd_result.stderr[:1000]}")
            if not cmd_result.stdout and not cmd_result.stderr:
                logger.warning("Jest produced no output at all (stdout and stderr are empty)")
        
        # Parse JSON output
        test_result = self._parse_jest_output(cmd_result, attempt)
        
        return test_result
    
    def _find_test_files(self) -> List[Path]:
        """
        Find all test files in the project directory
        
        Returns:
            List[Path]: List of test file paths
        """
        test_files = []
        
        # Test file patterns
        test_patterns = [
            '**/*.test.js',
            '**/*.test.jsx',
            '**/*.test.ts',
            '**/*.test.tsx',
            '**/*.spec.js',
            '**/*.spec.jsx',
            '**/*.spec.ts',
            '**/*.spec.tsx',
        ]
        
        for pattern in test_patterns:
            found = list(self.project_path.glob(pattern))
            test_files.extend(found)
        
        # Also check root directory (not just subdirectories)
        for pattern in ['*.test.js', '*.test.jsx', '*.test.ts', '*.test.tsx', '*.spec.js', '*.spec.jsx']:
            found = list(self.project_path.glob(pattern))
            test_files.extend(found)
        
        # Remove duplicates and sort
        test_files = sorted(set(test_files))
        
        # Filter out node_modules and other ignored directories
        filtered_files = []
        for test_file in test_files:
            # Check if file is in an ignored directory
            try:
                relative = test_file.relative_to(self.project_path)
                parts = relative.parts
                if 'node_modules' not in parts and 'coverage' not in parts:
                    filtered_files.append(test_file)
            except ValueError:
                continue
        
        return filtered_files
    
    def _build_jest_command_with_files(self, test_files: List[Path], use_npm: bool = True, json_output_file: Optional[Path] = None, test_level: Optional[str] = None) -> List[str]:
        """
        Build Jest command with explicit test file paths
        
        Args:
            test_files: List of test file paths
            use_npm: Whether to use npm test or npx jest
            json_output_file: Optional path to save JSON output file
            test_level: Optional test level for execution mode
            
        Returns:
            List[str]: Command parts
        """
        if use_npm:
            # npm test -- --coverage --json <test_files>
            # Note: Don't use --silent with npm test as it can suppress JSON output
            # We'll extract JSON from stdout/stderr after execution
            # since npm doesn't support --outputFile directly
            command = ['npm', 'test', '--', '--coverage', '--json']
            
            # Add execution mode based on test level
            if test_level in ['integration', 'feature']:
                command.append('--runInBand')  # Run serially for integration/feature tests
                logger.info(f"Adding --runInBand for {test_level} tests (sequential execution)")
            # For npm test, we'll save stdout to file after execution
            # since npm doesn't support --outputFile directly
        else:
            # npx jest --coverage --json --no-cache --ci <test_files>
            # Use --outputFile to ensure JSON is always written to file
            command = ['npx', 'jest', '--coverage', '--json', '--no-cache', '--ci']
            
            # Add execution mode based on test level
            if test_level in ['integration', 'feature']:
                command.append('--runInBand')  # Run serially for integration/feature tests
                logger.info(f"Adding --runInBand for {test_level} tests (sequential execution)")
            
            if json_output_file:
                command.extend(['--outputFile', str(json_output_file)])
        
        # Add test file paths (relative to project_path)
        for test_file in test_files:
            try:
                relative_path = test_file.relative_to(self.project_path)
                command.append(str(relative_path))
            except ValueError:
                # If relative path fails, use absolute path
                command.append(str(test_file))
        
        return command
    
    def _setup_jest_in_workspace(self) -> bool:
        """Set up Jest configuration in workspace if needed"""
        try:
            import json
            import shutil
            from pathlib import Path
            
            # Check if we have Jest setup files in the root directory
            root_path = Path(__file__).parent.parent
            root_package_json = root_path / 'package.json'
            root_jest_config = root_path / 'jest.config.js'
            root_babel_config = root_path / 'babel.config.js'
            root_jest_setup = root_path / 'jest.setup.js'
            
            # Copy package.json if it exists in root
            if root_package_json.exists():
                shutil.copy2(root_package_json, self.project_path / 'package.json')
                logger.info("Copied package.json to workspace")
            
            # Copy jest.config.js if it exists
            if root_jest_config.exists():
                shutil.copy2(root_jest_config, self.project_path / 'jest.config.js')
                logger.info("Copied jest.config.js to workspace")
            
            # Copy babel.config.js if it exists
            if root_babel_config.exists():
                shutil.copy2(root_babel_config, self.project_path / 'babel.config.js')
                logger.info("Copied babel.config.js to workspace")
            
            # Copy jest.setup.js if it exists
            if root_jest_setup.exists():
                shutil.copy2(root_jest_setup, self.project_path / 'jest.setup.js')
                logger.info("Copied jest.setup.js to workspace")
            
            # Copy components/ui directory if it exists (for React components)
            root_components = root_path / 'components'
            if root_components.exists():
                dest_components = self.project_path / 'components'
                shutil.copytree(root_components, dest_components, dirs_exist_ok=True)
                logger.info("Copied components directory to workspace")
            
            # Install dependencies if package.json was copied
            if (self.project_path / 'package.json').exists():
                logger.info("Installing npm dependencies in workspace...")
                install_cmd = ['npm', 'install']
                install_result = self.executor.execute(install_cmd, timeout=300)
                if install_result.success:
                    logger.info("Successfully installed npm dependencies")
                else:
                    logger.warning(f"npm install had issues: {install_result.stderr}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Jest in workspace: {e}")
            return False
    
    def _execute_pytest(self, timeout: int, attempt: int, generated_tests: Optional[List[GeneratedTest]] = None, test_level: Optional[str] = None) -> TestExecutionResult:
        """Execute Pytest tests"""
        
        # Check if pytest is available
        if not self.executor.check_command_available('pytest'):
            logger.error("pytest not available")
            return TestExecutionResult(
                framework='pytest',
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration=0,
                exit_code=-1,
                success=False,
                stderr="pytest command not available. Install pytest.",
                attempt=attempt,
                max_attempts=self.MAX_RETRIES
            )
        
        # Use generated test files if provided, otherwise search for all test files
        if generated_tests:
            # Filter for pytest framework and successful tests
            framework_tests = [t for t in generated_tests if t.framework == 'pytest' and t.success]
            if framework_tests:
                # Use the specific test files that were generated
                test_files = []
                for gen_test in framework_tests:
                    test_path = self.project_path / gen_test.test_file_path
                    if test_path.exists():
                        test_files.append(test_path)
                        logger.info(f"Using generated test file: {gen_test.test_file_path}")
                    else:
                        logger.warning(f"Generated test file not found on disk: {test_path}")
                
                if not test_files:
                    logger.warning("Generated test files not found on disk")
                    return TestExecutionResult(
                        framework='pytest',
                        total_tests=0,
                        passed=0,
                        failed=0,
                        skipped=0,
                        duration=0,
                        exit_code=-1,
                        success=False,
                        stderr="Generated pytest test files not found on disk",
                        attempt=attempt,
                        max_attempts=self.MAX_RETRIES
                    )
            else:
                logger.warning(f"No successful pytest tests in generated_tests, searching for all test files")
                test_files = self._find_pytest_test_files()
        else:
            # Fallback: search for all test files
            logger.info("No generated tests provided, searching for all test files in project directory")
            test_files = self._find_pytest_test_files()
        
        if not test_files:
            logger.warning("No pytest test files found in project directory")
            return TestExecutionResult(
                framework='pytest',
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration=0,
                exit_code=-1,
                success=False,
                stderr="No pytest test files found in project directory",
                attempt=attempt,
                max_attempts=self.MAX_RETRIES
            )
        
        logger.info(f"Found {len(test_files)} pytest test file(s) to execute: {[str(f.relative_to(self.project_path)) for f in test_files[:5]]}")
        
        # Build command with verbose output and explicit test file paths
        pytest_options = {
            'verbose': True,
            'traceback': True,
            'no_color': True
        }
        
        # Add execution markers based on test level
        if test_level == 'integration':
            pytest_options['markers'] = 'integration'
        elif test_level == 'feature':
            pytest_options['markers'] = 'feature'
        
        command = self.executor.build_pytest_command(pytest_options)
        
        # Add test file paths
        for test_file in test_files:
            try:
                relative_path = test_file.relative_to(self.project_path)
                command.append(str(relative_path))
            except ValueError:
                command.append(str(test_file))
        
        # Execute
        cmd_result = self.executor.execute(command, timeout=timeout)
        
        # Parse output
        test_result = self._parse_pytest_output(cmd_result, attempt)
        
        return test_result
    
    def _find_pytest_test_files(self) -> List[Path]:
        """
        Find all pytest test files in the project directory
        
        Returns:
            List[Path]: List of test file paths
        """
        test_files = []
        
        # Pytest test file patterns
        test_patterns = [
            '**/test_*.py',
            '**/*_test.py',
            '**/tests/**/*.py',
        ]
        
        for pattern in test_patterns:
            found = list(self.project_path.glob(pattern))
            test_files.extend(found)
        
        # Remove duplicates and sort
        test_files = sorted(set(test_files))
        
        # Filter out node_modules and other ignored directories
        filtered_files = []
        for test_file in test_files:
            try:
                relative = test_file.relative_to(self.project_path)
                parts = relative.parts
                if 'node_modules' not in parts and 'coverage' not in parts and '__pycache__' not in parts:
                    filtered_files.append(test_file)
            except ValueError:
                continue
        
        return filtered_files
    
    def _parse_jest_output(
        self,
        cmd_result: CommandResult,
        attempt: int
    ) -> TestExecutionResult:
        """Parse Jest JSON output"""
        
        # Initialize result
        result = TestExecutionResult(
            framework='jest',
            total_tests=0,
            passed=0,
            failed=0,
            skipped=0,
            duration=cmd_result.duration,
            exit_code=cmd_result.exit_code,
            success=cmd_result.success,
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            attempt=attempt,
            max_attempts=self.MAX_RETRIES,
            timed_out=cmd_result.timed_out
        )
        
        try:
            # Try to parse JSON output
            if cmd_result.stdout:
                # Jest might output errors/warnings before JSON, so extract JSON from stdout
                json_str = self._extract_json_from_output(cmd_result.stdout)
                
                if json_str:
                    json_data = json.loads(json_str)
                    
                    result.total_tests = json_data.get('numTotalTests', 0)
                    result.passed = json_data.get('numPassedTests', 0)
                    result.failed = json_data.get('numFailedTests', 0)
                    result.skipped = json_data.get('numPendingTests', 0)
                    
                    # Parse test cases
                    test_results = json_data.get('testResults', [])
                    for test_file in test_results:
                        file_path = test_file.get('name', '')
                        
                        for assertion in test_file.get('assertionResults', []):
                            test_case = TestCase(
                                name=assertion.get('fullName', assertion.get('title', 'Unknown')),
                                status=assertion.get('status', 'unknown'),
                                duration=assertion.get('duration', 0) / 1000.0,  # Convert ms to seconds
                                file=file_path,
                                error_message=self._extract_jest_error(assertion)
                            )
                            result.test_cases.append(test_case)
                    
                    result.success = result.failed == 0
                    logger.debug(f"Successfully parsed Jest JSON: {result.total_tests} tests, {result.passed} passed, {result.failed} failed")
                else:
                    # No JSON found, fallback to text parsing
                    logger.warning("No JSON found in Jest output, falling back to text parsing")
                    logger.info(f"Jest stdout length: {len(cmd_result.stdout) if cmd_result.stdout else 0} chars")
                    logger.info(f"Jest stderr length: {len(cmd_result.stderr) if cmd_result.stderr else 0} chars")
                    if cmd_result.stdout:
                        logger.info(f"Jest stdout (first 1000 chars):\n{cmd_result.stdout[:1000]}")
                    if cmd_result.stderr:
                        logger.info(f"Jest stderr (first 1000 chars):\n{cmd_result.stderr[:1000]}")
                    result = self._parse_jest_text_output(cmd_result, result)
            else:
                # No stdout, check stderr
                logger.warning("No stdout from Jest, checking stderr")
                logger.debug(f"Jest stderr: {cmd_result.stderr[:500]}")
                result = self._parse_jest_text_output(cmd_result, result)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Jest JSON output: {e}")
            logger.info(f"Jest stdout length: {len(cmd_result.stdout) if cmd_result.stdout else 0} chars")
            logger.info(f"Jest stderr length: {len(cmd_result.stderr) if cmd_result.stderr else 0} chars")
            if cmd_result.stdout:
                logger.info(f"Jest stdout (first 1000 chars):\n{cmd_result.stdout[:1000]}")
            if cmd_result.stderr:
                logger.info(f"Jest stderr (first 1000 chars):\n{cmd_result.stderr[:1000]}")
            # Fallback to text parsing
            result = self._parse_jest_text_output(cmd_result, result)
        except Exception as e:
            logger.error(f"Error parsing Jest output: {e}", exc_info=True)
            logger.info(f"Jest stdout length: {len(cmd_result.stdout) if cmd_result.stdout else 0} chars")
            logger.info(f"Jest stderr length: {len(cmd_result.stderr) if cmd_result.stderr else 0} chars")
            if cmd_result.stdout:
                logger.info(f"Jest stdout (first 1000 chars):\n{cmd_result.stdout[:1000]}")
            if cmd_result.stderr:
                logger.info(f"Jest stderr (first 1000 chars):\n{cmd_result.stderr[:1000]}")
            # Fallback to text parsing
            result = self._parse_jest_text_output(cmd_result, result)
        
        return result
    
    def _extract_json_from_output(self, output: str) -> Optional[str]:
        """
        Extract JSON from Jest output that may contain errors/warnings before JSON
        
        Args:
            output: Raw Jest output
            
        Returns:
            Optional[str]: Extracted JSON string or None
        """
        if not output:
            return None
        
        # Try to find JSON object in output
        # Jest JSON output starts with '{' and ends with '}'
        # It might be preceded by error messages or warnings
        
        # Find the first '{' that looks like JSON start
        start_idx = output.find('{')
        if start_idx == -1:
            return None
        
        # Find matching closing brace
        brace_count = 0
        end_idx = start_idx
        
        for i in range(start_idx, len(output)):
            if output[i] == '{':
                brace_count += 1
            elif output[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break
        
        if brace_count == 0:
            json_str = output[start_idx:end_idx + 1]
            # Validate it's actually JSON
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass
        
        # Alternative: Look for JSON in lines (Jest might output JSON on separate lines)
        lines = output.split('\n')
        json_lines = []
        in_json = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('{'):
                in_json = True
                json_lines = [stripped]
            elif in_json:
                json_lines.append(stripped)
                if stripped.endswith('}') and stripped.count('}') >= stripped.count('{'):
                    # Might be end of JSON
                    json_str = '\n'.join(json_lines)
                    try:
                        json.loads(json_str)
                        return json_str
                    except json.JSONDecodeError:
                        continue
        
        return None
    
    def _parse_jest_text_output(
        self,
        cmd_result: CommandResult,
        result: TestExecutionResult
    ) -> TestExecutionResult:
        """Fallback text parsing for Jest when JSON parsing fails"""
        
        output = (cmd_result.stdout or '') + '\n' + (cmd_result.stderr or '')
        
        # Try multiple patterns to extract test summary
        patterns = [
            # Pattern 1: "Tests:       1 failed, 2 passed, 3 total"
            r'Tests:\s+(?:(\d+)\s+failed,\s*)?(?:(\d+)\s+passed,\s*)?(\d+)\s+total',
            # Pattern 2: "PASS" or "FAIL" with test counts
            r'(?:PASS|FAIL).*?(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+total',
            # Pattern 3: Jest summary format
            r'(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+total',
            # Pattern 4: Simple counts
            r'(\d+)\s+passed.*?(\d+)\s+failed',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    try:
                        # Try to extract numbers
                        if 'failed' in pattern.lower() and 'passed' in pattern.lower():
                            failed = int(groups[0] or 0) if 'failed' in match.group(0).lower() else 0
                            passed = int(groups[1] or 0) if 'passed' in match.group(0).lower() else 0
                            total = int(groups[2] or 0) if len(groups) > 2 else (failed + passed)
                        else:
                            # Generic extraction
                            numbers = [int(g) for g in groups if g and g.isdigit()]
                            if len(numbers) >= 2:
                                passed = numbers[0]
                                failed = numbers[1]
                                total = numbers[2] if len(numbers) > 2 else (passed + failed)
                            else:
                                continue
                        
                        result.failed = failed
                        result.passed = passed
                        result.total_tests = total
                        result.success = failed == 0
                        logger.info(f"Extracted test counts from text: {total} total, {passed} passed, {failed} failed")
                        break
                    except (ValueError, IndexError):
                        continue
        
        # If we couldn't extract counts, try more aggressive parsing
        if result.total_tests == 0:
            # Try to find any test-related patterns
            # Look for test file names or test descriptions
            test_file_pattern = r'\.test\.(js|jsx|ts|tsx)'
            test_files = re.findall(test_file_pattern, output, re.IGNORECASE)
            if test_files:
                logger.info(f"Found {len(test_files)} test file(s) mentioned in output")
            
            # Look for PASS/FAIL indicators
            pass_count = len(re.findall(r'\bPASS\b', output, re.IGNORECASE))
            fail_count = len(re.findall(r'\bFAIL\b', output, re.IGNORECASE))
            
            if pass_count > 0 or fail_count > 0:
                result.passed = pass_count
                result.failed = fail_count
                result.total_tests = pass_count + fail_count
                result.success = fail_count == 0
                logger.info(f"Extracted from PASS/FAIL indicators: {result.total_tests} tests, {result.passed} passed, {result.failed} failed")
            
            # Look for test suite/test case patterns
            test_suite_pattern = r'Test Suites:\s+(\d+)\s+(?:passed|failed|total)'
            test_case_pattern = r'Tests:\s+(\d+)\s+(?:passed|failed|total)'
            
            suite_match = re.search(test_suite_pattern, output, re.IGNORECASE)
            case_match = re.search(test_case_pattern, output, re.IGNORECASE)
            
            if case_match:
                total = int(case_match.group(1))
                if total > 0:
                    result.total_tests = total
                    logger.info(f"Found test count from Jest summary: {total}")
            
            # If still no counts, check exit code and log output for debugging
            if result.total_tests == 0:
                if cmd_result.exit_code != 0:
                    # Tests likely failed but we couldn't parse the output
                    logger.warning("Could not parse Jest output, but exit code indicates failure")
                    logger.warning("This might indicate a Jest configuration or execution error")
                    # Log full output for debugging (truncated to avoid log spam)
                    if cmd_result.stdout:
                        logger.warning(f"Jest stdout (last 2000 chars):\n{cmd_result.stdout[-2000:]}")
                    if cmd_result.stderr:
                        logger.warning(f"Jest stderr (last 2000 chars):\n{cmd_result.stderr[-2000:]}")
                    result.success = False
                    # Try to extract at least error information
                    if cmd_result.stderr:
                        result.stderr = cmd_result.stderr
                    if cmd_result.stdout:
                        result.stdout = cmd_result.stdout
                else:
                    logger.warning("Could not parse Jest output, but exit code is 0 (success)")
                    # Maybe tests passed but output format is unexpected
                    result.success = True
        
        return result
    
    def _parse_pytest_output(
        self,
        cmd_result: CommandResult,
        attempt: int
    ) -> TestExecutionResult:
        """Parse Pytest output"""
        
        # Initialize result
        result = TestExecutionResult(
            framework='pytest',
            total_tests=0,
            passed=0,
            failed=0,
            skipped=0,
            duration=cmd_result.duration,
            exit_code=cmd_result.exit_code,
            success=cmd_result.success,
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            attempt=attempt,
            max_attempts=self.MAX_RETRIES,
            timed_out=cmd_result.timed_out
        )
        
        output = cmd_result.stdout + cmd_result.stderr
        
        # Parse test cases from verbose output
        # Pattern: "test_file.py::test_name PASSED" or "FAILED"
        test_pattern = re.compile(r'([\w/_.]+\.py)::([\w_]+)\s+(PASSED|FAILED|SKIPPED)')
        
        for match in test_pattern.finditer(output):
            file_path = match.group(1)
            test_name = match.group(2)
            status = match.group(3).lower()
            
            test_case = TestCase(
                name=test_name,
                status=status,
                duration=0,  # Pytest doesn't provide per-test duration in verbose mode
                file=file_path
            )
            
            result.test_cases.append(test_case)
        
        # Parse summary
        # Pattern: "=== 2 failed, 3 passed in 1.23s ==="
        summary_pattern = re.search(
            r'=+\s*(?:(\d+)\s+failed)?,?\s*(?:(\d+)\s+passed)?,?\s*(?:(\d+)\s+skipped)?\s+in\s+([\d.]+)s',
            output
        )
        
        if summary_pattern:
            result.failed = int(summary_pattern.group(1) or 0)
            result.passed = int(summary_pattern.group(2) or 0)
            result.skipped = int(summary_pattern.group(3) or 0)
            result.total_tests = result.failed + result.passed + result.skipped
            result.success = result.failed == 0
        else:
            # Count from parsed test cases
            result.passed = sum(1 for tc in result.test_cases if tc.status == 'passed')
            result.failed = sum(1 for tc in result.test_cases if tc.status == 'failed')
            result.skipped = sum(1 for tc in result.test_cases if tc.status == 'skipped')
            result.total_tests = len(result.test_cases)
            result.success = result.failed == 0
        
        return result
    
    def _extract_jest_error(self, assertion: dict) -> Optional[str]:
        """Extract error message from Jest assertion"""
        if assertion.get('status') == 'failed':
            failure_messages = assertion.get('failureMessages', [])
            if failure_messages:
                return '\n'.join(failure_messages)
        return None
    
    def can_execute_jest(self) -> bool:
        """Check if Jest can be executed"""
        # Check for npm (preferred for local Jest installations)
        npm_available = self.executor.check_command_available('npm')
        npx_available = self.executor.check_command_available('npx')
        
        logger.info(f"Checking Jest availability: npm={npm_available}, npx={npx_available}, project_path={self.project_path}")
        
        # If npm is available, check if package.json exists in workspace
        if npm_available:
            package_json = self.project_path / 'package.json'
            if package_json.exists():
                logger.info("✓ Found package.json in workspace, Jest can be executed via npm")
                return True
            else:
                logger.info(f"package.json not found at {package_json}")
            
            # Also check if Jest test files exist (we can set up Jest on the fly)
            # Look for .test.js, .test.jsx, .spec.js, .spec.jsx files
            test_patterns = ['**/*.test.js', '**/*.test.jsx', '**/*.spec.js', '**/*.spec.jsx']
            test_files = []
            for pattern in test_patterns:
                found = list(self.project_path.glob(pattern))
                test_files.extend(found)
                if found:
                    logger.info(f"Found test files matching {pattern}: {[str(f.relative_to(self.project_path)) for f in found]}")
            
            # Also check in current directory (not just subdirectories)
            for pattern in ['*.test.js', '*.test.jsx', '*.spec.js', '*.spec.jsx']:
                found = list(self.project_path.glob(pattern))
                test_files.extend(found)
                if found:
                    logger.info(f"Found test files matching {pattern} in root: {[str(f.relative_to(self.project_path)) for f in found]}")
            
            if test_files:
                logger.info(f"✓ Found {len(test_files)} Jest test file(s), Jest can be executed via npm/npx")
                return True
            else:
                logger.info(f"No test files found in {self.project_path}")
        
        # Fallback to npx check (can run Jest without local installation)
        if npx_available:
            logger.info("✓ npx available, Jest can be executed via npx")
            return True
        
        logger.warning("✗ Neither npm nor npx available, Jest cannot be executed")
        return False
    
    def can_execute_pytest(self) -> bool:
        """Check if Pytest can be executed"""
        return self.executor.check_command_available('pytest')

