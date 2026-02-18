"""
Coverage Parser
Parses coverage data from Jest and pytest-cov
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class FileCoverage:
    """Coverage data for a single file"""
    file_path: str
    lines_covered: int
    lines_total: int
    coverage_percent: float
    branches_covered: int = 0
    branches_total: int = 0
    functions_covered: int = 0
    functions_total: int = 0


@dataclass
class CoverageReport:
    """Unified coverage report"""
    framework: str  # jest or pytest
    total_coverage: float
    lines_covered: int
    lines_total: int
    branches_covered: int
    branches_total: int
    functions_covered: int
    functions_total: int
    file_coverage: List[FileCoverage]
    raw_data: Optional[Dict[str, Any]] = None


class CoverageParser:
    """
    Parser for test coverage reports
    Supports Jest and pytest-cov
    """
    
    @staticmethod
    def parse_jest_coverage(project_path: Path) -> Optional[CoverageReport]:
        """
        Parse Jest coverage from coverage-final.json
        
        Args:
            project_path: Path to project directory
            
        Returns:
            Optional[CoverageReport]: Parsed coverage or None
        """
        try:
            # Jest coverage is typically in coverage/coverage-final.json
            # Try multiple possible locations
            possible_locations = [
                project_path / "coverage" / "coverage-final.json",
                project_path / "coverage-final.json",
                project_path / ".coverage" / "coverage-final.json",
            ]
            
            coverage_file = None
            for location in possible_locations:
                if location.exists():
                    coverage_file = location
                    break
            
            if not coverage_file:
                # Only log at debug level - coverage might not be generated if tests failed early
                # or if coverage wasn't requested
                logger.debug(f"Jest coverage file not found. Checked: {[str(loc) for loc in possible_locations]}")
                return None
            
            logger.info(f"Parsing Jest coverage from: {coverage_file}")
            
            with open(coverage_file, 'r', encoding='utf-8') as f:
                coverage_data = json.load(f)
            
            logger.info(f"Found {len(coverage_data)} file(s) in coverage data")
            
            # Parse Jest coverage format
            file_coverage_list = []
            total_lines_covered = 0
            total_lines = 0
            total_branches_covered = 0
            total_branches = 0
            total_functions_covered = 0
            total_functions = 0
            
            # Patterns to exclude from coverage calculation
            test_file_patterns = [
                '.test.', '.spec.', '__tests__', '.test.js', '.test.jsx', 
                '.test.ts', '.test.tsx', '.spec.js', '.spec.jsx', '.spec.ts', '.spec.tsx'
            ]
            
            # Config and workspace file patterns to exclude
            exclude_patterns = [
                'workspaces/',  # Exclude workspace files
                'temp/',  # Exclude temp files
                'node_modules/',  # Exclude dependencies
                'coverage/',  # Exclude coverage reports
                'babel.config.js',  # Exclude config files
                '.config.js',  # Exclude all config files
                'jest.config.js',
                'jest.setup.js',
                'package.json',
                'package-lock.json',
            ]
            
            source_files_count = 0
            test_files_count = 0
            excluded_files_count = 0
            
            for file_path, file_data in coverage_data.items():
                # Skip test files in coverage calculation (they're not source code)
                is_test_file = any(pattern in file_path for pattern in test_file_patterns)
                
                if is_test_file:
                    test_files_count += 1
                    logger.debug(f"Excluding test file from coverage: {file_path}")
                    continue
                
                # Skip config files, workspace files, and other non-source files
                should_exclude = any(pattern in file_path for pattern in exclude_patterns)
                
                if should_exclude:
                    excluded_files_count += 1
                    logger.debug(f"Excluding non-source file from coverage: {file_path}")
                    continue
                
                source_files_count += 1
                
                # Extract metrics
                statements = file_data.get('s', {})
                branches = file_data.get('b', {})
                functions = file_data.get('f', {})
                
                # Count covered lines
                lines_covered = sum(1 for count in statements.values() if count > 0)
                lines_total = len(statements)
                
                # Count covered branches
                branches_covered = sum(
                    sum(1 for hit in branch_hits if hit > 0)
                    for branch_hits in branches.values()
                )
                branches_total = sum(len(branch_hits) for branch_hits in branches.values())
                
                # Count covered functions
                functions_covered = sum(1 for count in functions.values() if count > 0)
                functions_total = len(functions)
                
                # Calculate coverage percentage
                coverage_percent = (lines_covered / lines_total * 100) if lines_total > 0 else 0
                
                file_coverage = FileCoverage(
                    file_path=file_path,
                    lines_covered=lines_covered,
                    lines_total=lines_total,
                    coverage_percent=coverage_percent,
                    branches_covered=branches_covered,
                    branches_total=branches_total,
                    functions_covered=functions_covered,
                    functions_total=functions_total
                )
                
                file_coverage_list.append(file_coverage)
                
                # Aggregate totals
                total_lines_covered += lines_covered
                total_lines += lines_total
                total_branches_covered += branches_covered
                total_branches += branches_total
                total_functions_covered += functions_covered
                total_functions += functions_total
            
            logger.info(f"Coverage calculation: {source_files_count} source file(s), {test_files_count} test file(s) excluded, {excluded_files_count} config/workspace file(s) excluded")
            
            if source_files_count == 0:
                logger.warning("No source files found in coverage data. Jest may only be collecting coverage from test files.")
                logger.warning("Ensure Jest config includes source files in collectCoverageFrom (excluding test files)")
            
            # Calculate total coverage
            total_coverage = (total_lines_covered / total_lines * 100) if total_lines > 0 else 0
            
            report = CoverageReport(
                framework='jest',
                total_coverage=total_coverage,
                lines_covered=total_lines_covered,
                lines_total=total_lines,
                branches_covered=total_branches_covered,
                branches_total=total_branches,
                functions_covered=total_functions_covered,
                functions_total=total_functions,
                file_coverage=file_coverage_list,
                raw_data=coverage_data
            )
            
            logger.info(f"Jest coverage parsed: {total_coverage:.2f}%")
            return report
            
        except Exception as e:
            logger.error(f"Error parsing Jest coverage: {e}")
            return None
    
    @staticmethod
    def parse_pytest_coverage(project_path: Path) -> Optional[CoverageReport]:
        """
        Parse pytest coverage from .coverage or coverage.json
        
        Args:
            project_path: Path to project directory
            
        Returns:
            Optional[CoverageReport]: Parsed coverage or None
        """
        try:
            # Try coverage.json first (if pytest-cov with --cov-report=json)
            coverage_json = project_path / "coverage.json"
            
            if coverage_json.exists():
                return CoverageParser._parse_pytest_json(coverage_json)
            
            # Try parsing from pytest output (if available)
            # This would be from stdout/stderr captured during execution
            logger.warning("pytest-cov JSON report not found, coverage unavailable")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing pytest coverage: {e}")
            return None
    
    @staticmethod
    def _parse_pytest_json(coverage_file: Path) -> Optional[CoverageReport]:
        """Parse pytest coverage.json format"""
        try:
            with open(coverage_file, 'r', encoding='utf-8') as f:
                coverage_data = json.load(f)
            
            # Parse coverage.py JSON format
            file_coverage_list = []
            total_lines_covered = 0
            total_lines = 0
            
            files = coverage_data.get('files', {})
            
            for file_path, file_data in files.items():
                summary = file_data.get('summary', {})
                
                lines_covered = summary.get('covered_lines', 0)
                lines_total = summary.get('num_statements', 0)
                coverage_percent = summary.get('percent_covered', 0)
                
                file_coverage = FileCoverage(
                    file_path=file_path,
                    lines_covered=lines_covered,
                    lines_total=lines_total,
                    coverage_percent=coverage_percent
                )
                
                file_coverage_list.append(file_coverage)
                
                total_lines_covered += lines_covered
                total_lines += lines_total
            
            # Get total from summary
            totals = coverage_data.get('totals', {})
            total_coverage = totals.get('percent_covered', 0)
            
            if total_coverage == 0 and total_lines > 0:
                total_coverage = (total_lines_covered / total_lines * 100)
            
            report = CoverageReport(
                framework='pytest',
                total_coverage=total_coverage,
                lines_covered=total_lines_covered,
                lines_total=total_lines,
                branches_covered=0,
                branches_total=0,
                functions_covered=0,
                functions_total=0,
                file_coverage=file_coverage_list,
                raw_data=coverage_data
            )
            
            logger.info(f"Pytest coverage parsed: {total_coverage:.2f}%")
            return report
            
        except Exception as e:
            logger.error(f"Error parsing pytest JSON: {e}")
            return None
    
    @staticmethod
    def parse_coverage_from_output(output: str, framework: str) -> Optional[CoverageReport]:
        """
        Parse coverage from command output (fallback)
        
        Args:
            output: Command stdout/stderr
            framework: 'jest' or 'pytest'
            
        Returns:
            Optional[CoverageReport]: Parsed coverage or None
        """
        try:
            if framework == 'jest':
                return CoverageParser._parse_jest_output(output)
            elif framework == 'pytest':
                return CoverageParser._parse_pytest_output(output)
            else:
                return None
        except Exception as e:
            logger.error(f"Error parsing coverage from output: {e}")
            return None
    
    @staticmethod
    def _parse_jest_output(output: str) -> Optional[CoverageReport]:
        """Parse Jest coverage from text output"""
        try:
            # Look for coverage summary in output
            # Pattern: "All files      |   85.71 |      100 |   83.33 |   85.71 |"
            pattern = r'All files\s+\|\s+([\d.]+)\s+\|\s+([\d.]+)\s+\|\s+([\d.]+)\s+\|\s+([\d.]+)'
            match = re.search(pattern, output)
            
            if match:
                statements_pct = float(match.group(1))
                branches_pct = float(match.group(2))
                functions_pct = float(match.group(3))
                lines_pct = float(match.group(4))
                
                # Use statements percentage as total coverage
                return CoverageReport(
                    framework='jest',
                    total_coverage=statements_pct,
                    lines_covered=0,  # Unknown from text
                    lines_total=0,
                    branches_covered=0,
                    branches_total=0,
                    functions_covered=0,
                    functions_total=0,
                    file_coverage=[]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing Jest output: {e}")
            return None
    
    @staticmethod
    def _parse_pytest_output(output: str) -> Optional[CoverageReport]:
        """Parse pytest coverage from text output"""
        try:
            # Look for coverage line
            # Pattern: "TOTAL                            100      0   100%"
            pattern = r'TOTAL\s+(\d+)\s+(\d+)\s+([\d.]+)%'
            match = re.search(pattern, output)
            
            if match:
                statements = int(match.group(1))
                missed = int(match.group(2))
                coverage_pct = float(match.group(3))
                
                return CoverageReport(
                    framework='pytest',
                    total_coverage=coverage_pct,
                    lines_covered=statements - missed,
                    lines_total=statements,
                    branches_covered=0,
                    branches_total=0,
                    functions_covered=0,
                    functions_total=0,
                    file_coverage=[]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing pytest output: {e}")
            return None

