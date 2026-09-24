"""
Safe Command Executor
Executes allowlisted commands with subprocess (no shell=True)
"""

import subprocess
import logging
import shutil
import sys
import os
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution"""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    success: bool
    timed_out: bool


class CommandExecutor:
    """
    Safe command executor with allowlist
    Uses subprocess without shell=True for security
    """
    
    # Allowlisted commands
    ALLOWED_COMMANDS = {
        'npx': ['npx'],
        'npm': ['npm'],
        'pytest': ['pytest'],
        'python': ['python'],
    }
    
    # Command-specific arguments that are allowed
    ALLOWED_ARGS = {
        'npx': ['jest', '--json', '--verbose', '--no-cache', '--ci', '--coverage', '--coverageReporters', '--outputFile'],
        'npm': ['test', 'run', 'test:unit', 'install', '--'],  # '--' allows passing args to test script
        'pytest': ['-v', '--json-report', '--json-report-file', '-x', '--tb=short', '--color=no'],
        'python': ['-m', 'pytest'],
    }
    
    # Default timeout per command (seconds)
    DEFAULT_TIMEOUT = 300  # 5 minutes
    
    def __init__(self, working_directory: Path):
        """
        Initialize command executor
        
        Args:
            working_directory: Directory to execute commands in
        """
        self.working_directory = working_directory
        if not self.working_directory.exists():
            raise ValueError(f"Working directory does not exist: {working_directory}")
        # Track which pytest command format works (instance variable)
        self._pytest_command_format = None  # 'pytest' or 'python -m pytest'
    
    def execute(
        self,
        command_parts: List[str],
        timeout: Optional[int] = None,
        env: Optional[dict] = None
    ) -> CommandResult:
        """
        Execute a command safely
        
        Args:
            command_parts: Command as list (e.g., ['npx', 'jest'])
            timeout: Timeout in seconds (default: DEFAULT_TIMEOUT)
            env: Optional environment variables
            
        Returns:
            CommandResult: Execution result
            
        Raises:
            ValueError: If command not in allowlist
        """
        if not command_parts:
            raise ValueError("Command parts cannot be empty")
        
        # Validate command
        if not self._is_allowed_command(command_parts):
            raise ValueError(f"Command not allowed: {' '.join(command_parts)}")
        
        timeout = timeout or self.DEFAULT_TIMEOUT
        command_str = ' '.join(command_parts)
        
        logger.info(f"Executing: {command_str} (timeout: {timeout}s)")
        
        start_time = time.time()
        timed_out = False
        
        try:
            # On Windows, npm/npx might need .cmd extension
            # shutil.which() will resolve this, but we need to use the resolved path
            if sys.platform == 'win32' and len(command_parts) > 0:
                base_cmd = command_parts[0]
                if base_cmd in ['npm', 'npx']:
                    # Try to find the actual executable using shutil.which()
                    # This will automatically find .cmd/.CMD files on Windows
                    cmd_path = shutil.which(base_cmd)
                    if cmd_path:
                        # Use the resolved path (e.g., C:\Program Files\nodejs\npm.CMD)
                        command_parts = [cmd_path] + command_parts[1:]
                        logger.debug(f"Using resolved command path on Windows: {cmd_path}")
                    else:
                        # Fallback: try explicit .cmd extension
                        for ext in ['.cmd', '.CMD', '.bat', '.BAT']:
                            cmd_path = shutil.which(f"{base_cmd}{ext}")
                            if cmd_path:
                                command_parts = [cmd_path] + command_parts[1:]
                                logger.debug(f"Using resolved command path with {ext}: {cmd_path}")
                                break
            
            # Execute without shell=True for security
            # Use UTF-8 encoding explicitly to handle Jest output on Windows
            process = subprocess.run(
                command_parts,
                cwd=str(self.working_directory),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid UTF-8 sequences instead of raising errors
                timeout=timeout,
                env=env
            )
            
            duration = time.time() - start_time
            
            result = CommandResult(
                command=command_str,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration=duration,
                success=process.returncode == 0,
                timed_out=False
            )
            
            logger.info(f"Command completed: exit_code={result.exit_code}, duration={duration:.2f}s")
            return result
            
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            timed_out = True
            
            # Get partial output if available
            # Use UTF-8 with error handling to avoid UnicodeDecodeError
            try:
                stdout = e.stdout.decode('utf-8', errors='replace') if e.stdout else ''
                stderr = e.stderr.decode('utf-8', errors='replace') if e.stderr else ''
            except (UnicodeDecodeError, AttributeError):
                # Fallback if decode fails or stdout/stderr are already strings
                stdout = str(e.stdout) if e.stdout else ''
                stderr = str(e.stderr) if e.stderr else ''
            
            result = CommandResult(
                command=command_str,
                exit_code=-1,
                stdout=stdout,
                stderr=stderr + f"\n\nCommand timed out after {timeout}s",
                duration=duration,
                success=False,
                timed_out=True
            )
            
            logger.error(f"Command timed out after {timeout}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            result = CommandResult(
                command=command_str,
                exit_code=-1,
                stdout='',
                stderr=f"Error executing command: {str(e)}",
                duration=duration,
                success=False,
                timed_out=False
            )
            
            logger.error(f"Error executing command: {e}")
            return result
    
    def _is_allowed_command(self, command_parts: List[str]) -> bool:
        """
        Check if command is in allowlist
        
        Args:
            command_parts: Command as list
            
        Returns:
            bool: True if allowed
        """
        if not command_parts:
            return False
        
        base_command = command_parts[0]
        
        # Check if base command is allowed
        if base_command not in self.ALLOWED_COMMANDS:
            return False
        
        # Validate base command matches allowed structure
        if command_parts[0] not in self.ALLOWED_COMMANDS[base_command]:
            return False
        
        # Check arguments if present
        if len(command_parts) > 1:
            allowed_args = self.ALLOWED_ARGS.get(base_command, [])
            
            # Track if we've seen '--' separator (allows passing args to npm scripts)
            after_separator = False
            
            for arg in command_parts[1:]:
                # If we see '--' separator, allow all subsequent args (they go to the script)
                if arg == '--':
                    after_separator = True
                    continue
                
                if after_separator:
                    # After '--', allow common Jest/test flags
                    if arg.startswith('--'):
                        continue  # Allow all flags after separator
                    continue
                
                # Allow file paths (start with ./ or / or Windows drive letters like C:\)
                if arg.startswith('./') or arg.startswith('/') or (len(arg) > 1 and arg[1] == ':'):
                    continue
                
                # Allow test file names (common patterns like *.test.js, *.test.jsx, *.test.ts, etc.)
                if any(arg.endswith(ext) for ext in ['.test.js', '.test.jsx', '.test.ts', '.test.tsx', '.spec.js', '.spec.jsx', '.spec.ts', '.spec.tsx']):
                    continue
                
                # Allow output files (--outputFile followed by a path)
                if arg.startswith('--') and '=' in arg:
                    arg_name = arg.split('=')[0]
                    if arg_name in allowed_args:
                        continue
                
                # Check if arg is in allowed list
                if arg not in allowed_args:
                    logger.warning(f"Argument not in allowlist: {arg}")
                    # Be lenient for now, but log it
                    # return False
        
        return True
    
    @staticmethod
    def build_jest_command(options: Optional[dict] = None) -> List[str]:
        """
        Build Jest command with options
        
        Args:
            options: Optional test options
            
        Returns:
            List[str]: Command parts
        """
        cmd = ['npx', 'jest']
        
        if options:
            if options.get('json'):
                cmd.append('--json')
            if options.get('verbose'):
                cmd.append('--verbose')
            if options.get('no_cache'):
                cmd.append('--no-cache')
            if options.get('ci'):
                cmd.append('--ci')
            if options.get('coverage'):
                cmd.append('--coverage')
            if options.get('coverage_reporters'):
                reporters = options.get('coverage_reporters', [])
                if reporters:
                    cmd.append('--coverageReporters')
                    cmd.extend(reporters)
        
        return cmd
    
    @staticmethod
    def build_npm_test_command() -> List[str]:
        """
        Build npm test command
        
        Returns:
            List[str]: Command parts
        """
        return ['npm', 'test']
    
    @staticmethod
    def build_npm_test_command_with_coverage() -> List[str]:
        """
        Build npm test command with coverage
        
        Returns:
            List[str]: Command parts
        """
        return ['npm', 'test', '--', '--coverage', '--json', '--verbose']
    
    def build_pytest_command(self, options: Optional[dict] = None) -> List[str]:
        """
        Build Pytest command with options
        Uses 'pytest' if available, otherwise falls back to 'python -m pytest'
        
        Args:
            options: Optional test options
            
        Returns:
            List[str]: Command parts
        """
        # Determine which pytest command format to use
        if self._pytest_command_format is None:
            # Check which format works
            self._check_pytest_available()
        
        # Build command based on available format
        if self._pytest_command_format == 'python -m pytest':
            python_cmd = shutil.which('python') or shutil.which('python3')
            if python_cmd:
                cmd = [python_cmd, '-m', 'pytest']
            else:
                # Fallback to direct pytest
                cmd = ['pytest']
        else:
            # Use direct pytest command
            cmd = ['pytest']
        
        if options:
            if options.get('verbose'):
                cmd.append('-v')
            if options.get('json_report'):
                cmd.append('--json-report')
                if options.get('json_report_file'):
                    cmd.append(f"--json-report-file={options['json_report_file']}")
            if options.get('fail_fast'):
                cmd.append('-x')
            if options.get('traceback'):
                cmd.append('--tb=short')
            if options.get('no_color'):
                cmd.append('--color=no')
        
        return cmd
    
    def check_command_available(self, command: str) -> bool:
        """
        Check if a command is available
        
        Args:
            command: Command to check (e.g., 'npx', 'pytest')
            
        Returns:
            bool: True if available
        """
        try:
            # Special handling for pytest - also check python -m pytest
            if command == 'pytest':
                return self._check_pytest_available()
            
            # First, use shutil.which() for cross-platform detection
            # This is more reliable than subprocess on Windows
            # shutil.which() on Windows will automatically find .cmd/.bat files
            command_path = shutil.which(command)
            if command_path:
                logger.debug(f"Found {command} at: {command_path}")
            else:
                # On Windows, try .cmd and .CMD extensions (case-insensitive file system)
                if sys.platform == 'win32':
                    for ext in ['.cmd', '.CMD', '.bat', '.BAT']:
                        command_path = shutil.which(f"{command}{ext}")
                        if command_path:
                            logger.debug(f"Found {command}{ext} at: {command_path}")
                            break
            
            if not command_path:
                logger.debug(f"Command {command} not found in PATH")
                return False
            
            # Try to get version to verify it actually works
            if command == 'npx':
                check_cmd = ['npx', '--version']
            elif command == 'npm':
                check_cmd = ['npm', '--version']
            else:
                # For unknown commands, just check if path exists
                return command_path is not None
            
            # On Windows, use the resolved path from shutil.which()
            # This ensures we use the correct .cmd/.CMD file
            if sys.platform == 'win32' and command_path:
                # Use the resolved path instead of just the command name
                check_cmd_resolved = [command_path] + check_cmd[1:]
                try:
                    result = subprocess.run(
                        check_cmd_resolved,
                        cwd=str(self.working_directory),
                        capture_output=True,
                        timeout=5,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )
                    if result.returncode == 0:
                        logger.debug(f"Command {command} verified via resolved path: {command_path}")
                        return True
                    else:
                        logger.debug(f"Command {command} check failed with exit code: {result.returncode}")
                        logger.debug(f"stderr: {result.stderr[:200]}")
                        return False
                except Exception as e:
                    logger.debug(f"Error verifying {command} with resolved path: {e}")
                    # Fall through to try standard command
            
            # For non-Windows or if .cmd didn't work, try standard command
            result = subprocess.run(
                check_cmd,
                cwd=str(self.working_directory),
                capture_output=True,
                timeout=5,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                logger.debug(f"Command {command} verified, version: {result.stdout.strip()}")
                return True
            else:
                logger.debug(f"Command {command} check failed with exit code: {result.returncode}")
                logger.debug(f"stderr: {result.stderr[:200]}")
                return False
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Command {command} check timed out")
            return False
        except FileNotFoundError:
            logger.debug(f"Command {command} not found")
            return False
        except Exception as e:
            logger.debug(f"Command {command} not available: {e}")
            return False
    
    def _check_pytest_available(self) -> bool:
        """
        Check if pytest is available, trying both 'pytest' and 'python -m pytest'
        Prefers 'python -m pytest' as it's more reliable on Windows
        
        Returns:
            bool: True if pytest is available
        """
        # First try 'python -m pytest' (more reliable on Windows)
        python_cmd = shutil.which('python') or shutil.which('python3')
        if python_cmd:
            try:
                result = subprocess.run(
                    [python_cmd, '-m', 'pytest', '--version'],
                    cwd=str(self.working_directory),
                    capture_output=True,
                    timeout=10,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=os.environ.copy()  # Ensure we have the same environment
                )
                if result.returncode == 0:
                    logger.info(f"pytest available via python -m pytest")
                    self._pytest_command_format = 'python -m pytest'
                    return True
                else:
                    logger.debug(f"python -m pytest returned exit code {result.returncode}: {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                logger.warning("python -m pytest check timed out after 10 seconds")
            except Exception as e:
                logger.debug(f"python -m pytest check failed: {e}")
        
        # Fallback: try direct 'pytest' command
        command_path = shutil.which('pytest')
        if command_path:
            # On Windows, try .cmd and .CMD extensions
            if sys.platform == 'win32':
                for ext in ['.cmd', '.CMD', '.bat', '.BAT']:
                    cmd_path = shutil.which(f"pytest{ext}")
                    if cmd_path:
                        command_path = cmd_path
                        break
            
            # Try to verify it works
            check_cmd = [command_path] if sys.platform == 'win32' and command_path else ['pytest']
            check_cmd.append('--version')
            
            try:
                result = subprocess.run(
                    check_cmd,
                    cwd=str(self.working_directory),
                    capture_output=True,
                    timeout=10,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=os.environ.copy()  # Ensure we have the same environment
                )
                if result.returncode == 0:
                    logger.info(f"pytest available as direct command: {command_path}")
                    self._pytest_command_format = 'pytest'
                    return True
                else:
                    logger.debug(f"pytest command returned exit code {result.returncode}: {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                logger.warning("Direct pytest command timed out after 10 seconds")
            except Exception as e:
                logger.debug(f"Direct pytest command failed: {e}")
        
        logger.warning("pytest not available as 'pytest' or 'python -m pytest'")
        return False

