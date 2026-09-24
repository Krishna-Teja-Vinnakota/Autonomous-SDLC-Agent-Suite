"""
Test Strategy Agent
Analyzes project to determine which files should be tested and how
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Literal
from pathlib import Path
from dataclasses import dataclass, asdict

from config.vertex_ai import GeminiClient
from tools.file_indexer import IndexResult, FileInfo
from agents.analyze_agent import ProjectAnalysisResult

logger = logging.getLogger(__name__)

# Define test level types
TestLevel = Literal["unit", "integration", "feature"]


@dataclass
class TestStrategy:
    """Test strategy for a specific file or group of files"""
    source_file: str  # Primary source file
    test_file: str
    priority: str  # high, medium, low
    test_type: str  # unit, integration, component, feature
    test_level: TestLevel  # NEW: unit, integration, or feature
    framework: str  # jest, pytest
    needs_mocks: bool
    complexity: str  # simple, moderate, complex
    rationale: str
    related_files: List[str] = None  # NEW: For integration/feature tests


@dataclass
class TestStrategyResult:
    """Overall test strategy for the project"""
    strategies: List[TestStrategy]
    total_files_to_test: int
    estimated_tests: int
    summary: str


class StrategyAgent:
    """
    Agent for determining test strategy
    Analyzes project structure and decides what to test
    """
    
    def __init__(self, gemini_client: GeminiClient):
        """
        Initialize strategy agent
        
        Args:
            gemini_client: Initialized GeminiClient instance
        """
        self.client = gemini_client
    
    def determine_test_strategy(
        self,
        index_result: IndexResult,
        analysis_result: Optional[ProjectAnalysisResult],
        project_path: Path,
        requested_test_levels: Optional[List[str]] = None  # NEW: User's requested test levels
    ) -> Optional[TestStrategyResult]:
        """
        Determine test strategy for the project
        
        Args:
            index_result: File indexing results
            analysis_result: Project analysis results
            project_path: Path to project directory
            requested_test_levels: User-requested test levels (e.g., ['unit'], ['feature'], or ['unit', 'integration', 'feature'])
            
        Returns:
            Optional[TestStrategyResult]: Test strategy or None if failed
        """
        try:
            logger.info("Determining test strategy")
            
            # Identify testable files
            testable_files = self._identify_testable_files(index_result)
            
            if not testable_files:
                logger.warning("No testable files found")
                return TestStrategyResult(
                    strategies=[],
                    total_files_to_test=0,
                    estimated_tests=0,
                    summary="No testable files found in project"
                )
            
            # Create strategy summary
            strategy_summary = self._create_strategy_summary(
                testable_files,
                analysis_result,
                project_path
            )
            
            # Generate strategies using AI
            strategies = self._generate_strategies_with_ai(
                strategy_summary,
                testable_files,
                analysis_result
            )
            
            if not strategies:
                # Fallback to basic strategy with user's requested levels
                strategies = self._generate_basic_strategies(
                    testable_files, 
                    analysis_result,
                    requested_test_levels=requested_test_levels
                )
            else:
                # Apply user's requested test levels to AI-generated strategies
                if requested_test_levels:
                    strategies = self._apply_requested_test_levels(strategies, requested_test_levels)
            
            # Calculate estimates
            total_files = len(strategies)
            estimated_tests = sum(self._estimate_test_count(s) for s in strategies)
            
            result = TestStrategyResult(
                strategies=strategies,
                total_files_to_test=total_files,
                estimated_tests=estimated_tests,
                summary=f"Generated test strategy for {total_files} files with ~{estimated_tests} tests"
            )
            
            logger.info(f"Test strategy complete: {total_files} files to test")
            return result
            
        except Exception as e:
            logger.error(f"Error determining test strategy: {e}")
            return None
    
    def _apply_requested_test_levels(
        self,
        strategies: List[TestStrategy],
        requested_test_levels: List[str]
    ) -> List[TestStrategy]:
        """
        Apply user's requested test levels to existing strategies.
        If user requests specific levels, all strategies are set to those levels.
        
        Args:
            strategies: List of generated strategies
            requested_test_levels: User-requested test levels
            
        Returns:
            List[TestStrategy]: Updated strategies with correct test levels and file paths
        """
        if not requested_test_levels or len(requested_test_levels) > 1:
            # User wants multiple levels or all levels - keep auto-classification
            return strategies
        
        # User wants a specific single level - apply it to all strategies
        requested_level = requested_test_levels[0]
        logger.info(f"User requested {requested_level} tests only - applying to all {len(strategies)} strategies")
        
        updated_strategies = []
        for strategy in strategies:
            # Update test level
            old_level = strategy.test_level
            strategy.test_level = requested_level
            
            # Update test file path based on new level
            source_path = Path(strategy.source_file)
            
            if strategy.framework == 'jest':
                # Jest/React/TypeScript naming
                if requested_level == 'integration':
                    new_test_file = str(source_path.parent / f"{source_path.stem}.integration.test{source_path.suffix}")
                elif requested_level == 'feature':
                    new_test_file = str(source_path.parent / f"{source_path.stem}.feature.test{source_path.suffix}")
                else:  # unit
                    new_test_file = str(source_path.parent / f"{source_path.stem}.test{source_path.suffix}")
            else:  # pytest
                # Pytest naming
                if requested_level == 'integration':
                    new_test_file = str(source_path.parent / f"test_{source_path.stem}_integration.py")
                elif requested_level == 'feature':
                    new_test_file = str(source_path.parent / f"test_{source_path.stem}_feature.py")
                else:  # unit
                    new_test_file = str(source_path.parent / f"test_{source_path.name}")
            
            strategy.test_file = new_test_file
            
            # Update rationale
            strategy.rationale = f"{requested_level.title()} test for {strategy.source_file} (user requested {requested_level})"
            
            logger.debug(f"Updated {strategy.source_file}: {old_level} -> {requested_level}, test file: {new_test_file}")
            updated_strategies.append(strategy)
        
        return updated_strategies
    
    def _identify_testable_files(self, index_result: IndexResult) -> List[FileInfo]:
        """
        Identify files that should have tests
        
        Args:
            index_result: File indexing results
            
        Returns:
            List[FileInfo]: Testable files
        """
        testable_files = []
        
        for file_info in index_result.file_list:
            # Skip test files themselves
            if file_info.category == 'Test':
                continue
            
            # Skip config files
            if file_info.category == 'Config':
                continue
            
            # Skip documentation
            if file_info.category == 'Documentation':
                continue
            
            # Include source code files
            if file_info.category in ['Python', 'JavaScript', 'TypeScript']:
                # Skip very small files (likely not worth testing)
                if file_info.lines and file_info.lines < 10:
                    continue
                
                # Skip certain paths
                relative_path_lower = file_info.relative_path.lower()
                skip_patterns = [
                    'node_modules', 'venv', '__pycache__', 'dist', 'build',
                    '.next', 'coverage', 'migrations', 'config'
                ]
                
                if any(pattern in relative_path_lower for pattern in skip_patterns):
                    continue
                
                testable_files.append(file_info)
        
        # Limit to reasonable number
        if len(testable_files) > 50:
            logger.info(f"Limiting testable files from {len(testable_files)} to 50")
            # Prioritize by lines of code (more complex files first)
            testable_files.sort(key=lambda f: f.lines or 0, reverse=True)
            testable_files = testable_files[:50]
        
        return testable_files
    
    def _create_strategy_summary(
        self,
        testable_files: List[FileInfo],
        analysis_result: Optional[ProjectAnalysisResult],
        project_path: Path
    ) -> Dict[str, Any]:
        """Create summary for strategy generation"""
        summary = {
            "testable_files": [],
            "languages": analysis_result.languages if analysis_result else [],
            "frameworks": analysis_result.frameworks if analysis_result else [],
            "test_setup": analysis_result.test_setup if analysis_result else {}
        }
        
        for file_info in testable_files[:20]:  # Limit for token efficiency
            summary["testable_files"].append({
                "path": file_info.relative_path,
                "category": file_info.category,
                "lines": file_info.lines,
                "size": file_info.size
            })
        
        return summary
    
    def _generate_strategies_with_ai(
        self,
        strategy_summary: Dict[str, Any],
        testable_files: List[FileInfo],
        analysis_result: Optional[ProjectAnalysisResult]
    ) -> List[TestStrategy]:
        """
        Generate strategies using AI (placeholder for future AI implementation)
        Currently returns empty to fallback to basic strategy
        """
        # TODO: Implement AI-powered strategy generation with Gemini
        # For now, return empty to use basic strategy
        return []
    
    def _generate_basic_strategies(
        self,
        testable_files: List[FileInfo],
        analysis_result: Optional[ProjectAnalysisResult],
        requested_test_levels: Optional[List[str]] = None
    ) -> List[TestStrategy]:
        """
        Generate basic test strategies without AI
        Uses heuristics to determine what to test
        
        Args:
            testable_files: Files that need testing
            analysis_result: Project analysis (optional)
            requested_test_levels: User-requested test levels (NEW)
        """
        strategies = []
        has_react = analysis_result and 'React' in analysis_result.frameworks if analysis_result else False
        
        # Create directory mapping for related file detection
        files_by_dir = {}
        for file_info in testable_files:
            dir_path = str(Path(file_info.relative_path).parent)
            if dir_path not in files_by_dir:
                files_by_dir[dir_path] = []
            files_by_dir[dir_path].append(file_info)
        
        # Generate strategies with test level classification
        for file_info in testable_files:
            source_path = Path(file_info.relative_path)
            
            # Determine test framework
            if file_info.category in ['JavaScript', 'TypeScript']:
                framework = 'jest'
                
                # Determine test file path (will be updated after test_level classification)
                if source_path.suffix in ['.tsx', '.jsx'] and has_react:
                    # React component - will determine naming after level classification
                    test_type = 'component'
                else:
                    # Regular JS/TS
                    test_type = 'unit'
                
                # FIXED: Determine test level respecting user's request
                if requested_test_levels and len(requested_test_levels) == 1:
                    # User requested a specific level - use it
                    test_level = requested_test_levels[0]
                else:
                    # User wants all levels or multiple levels - use auto-classification
                    test_level = self._classify_test_level(file_info, source_path, files_by_dir)
                
                # Now determine test file path based on test level
                if test_level == 'integration':
                    test_file = str(source_path.parent / f"{source_path.stem}.integration.test{source_path.suffix}")
                elif test_level == 'feature':
                    test_file = str(source_path.parent / f"{source_path.stem}.feature.test{source_path.suffix}")
                else:  # unit
                    test_file = str(source_path.parent / f"{source_path.stem}.test{source_path.suffix}")
            
            elif file_info.category == 'Python':
                framework = 'pytest'
                test_type = 'unit'
                
                # FIXED: Determine test level respecting user's request
                if requested_test_levels and len(requested_test_levels) == 1:
                    # User requested a specific level - use it
                    test_level = requested_test_levels[0]
                else:
                    # User wants all levels or multiple levels - use auto-classification
                    test_level = self._classify_test_level(file_info, source_path, files_by_dir)
                
                # Pytest convention with level suffix
                if test_level == 'integration':
                    test_file = str(source_path.parent / f"test_{source_path.stem}_integration.py")
                elif test_level == 'feature':
                    test_file = str(source_path.parent / f"test_{source_path.stem}_feature.py")
                else:  # unit
                    test_file = str(source_path.parent / f"test_{source_path.name}")
            
            else:
                continue
            
            # Determine priority based on file size/complexity
            lines = file_info.lines or 0
            if lines > 200:
                priority = 'high'
                complexity = 'complex'
            elif lines > 100:
                priority = 'medium'
                complexity = 'moderate'
            else:
                priority = 'low'
                complexity = 'simple'
            
            # Check if file might need mocks (heuristic)
            needs_mocks = lines > 50  # Simple heuristic
            
            # For integration/feature tests, identify related files
            related_files = None
            if test_level in ['integration', 'feature']:
                related_files = self._find_related_files(file_info, files_by_dir)
            
            # Create rationale
            if requested_test_levels and len(requested_test_levels) == 1:
                rationale = f"{test_level.title()} test for {file_info.category} file (user requested {test_level})"
            else:
                rationale = f"{test_level.title()} {test_type} test for {file_info.category} file ({lines} lines)"
            
            strategy = TestStrategy(
                source_file=file_info.relative_path,
                test_file=test_file,
                priority=priority,
                test_type=test_type,
                test_level=test_level,
                framework=framework,
                needs_mocks=needs_mocks,
                complexity=complexity,
                rationale=rationale,
                related_files=related_files
            )
            
            strategies.append(strategy)
        
        return strategies
    
    def _classify_test_level(
        self,
        file_info: FileInfo,
        source_path: Path,
        files_by_dir: Dict[str, List[FileInfo]]
    ) -> TestLevel:
        """
        Classify test level based on file characteristics
        
        This is ONLY used when user doesn't specify a preference (multi-level or all levels).
        When user selects a specific level, this function is bypassed.
        
        Rules:
        - Utilities/helpers → unit
        - React components → feature (DEFAULT for user-facing components)
        - Feature folder with multiple related files → feature
        - Python API/services → integration
        - Simple isolated utilities → unit
        """
        file_name_lower = source_path.name.lower()
        dir_path = str(source_path.parent)
        
        # Check for utility/helper patterns (unit tests only for pure utilities)
        if any(pattern in file_name_lower for pattern in ['util', 'helper', 'constant', 'config', 'type', '.d.ts']):
            return 'unit'
        
        # Check for test utilities (should be unit)
        if 'test' in dir_path.lower() or '__tests__' in dir_path.lower():
            return 'unit'
        
        # DEFAULT: React/Next.js components → FEATURE testing
        # This is the key change - all React components default to feature tests
        if source_path.suffix in ['.tsx', '.jsx']:
            # Check if it's in a component directory (strong indicator of feature)
            if any(indicator in dir_path.lower() for indicator in ['component', 'page', 'view', 'screen', 'feature', 'module']):
                return 'feature'
            
            # Check for feature folder patterns with multiple related files
            dir_files = files_by_dir.get(dir_path, [])
            if len(dir_files) >= 2:  # Even 2 files can be a feature
                return 'feature'
            
            # DEFAULT for any React component: FEATURE testing
            # This ensures SelectSize and similar components get feature tests
            logger.info(f"Defaulting React component {source_path.name} to FEATURE level testing")
            return 'feature'
        
        # Check for Python service/API patterns (integration)
        if source_path.suffix == '.py':
            if any(pattern in file_name_lower for pattern in ['api', 'service', 'handler', 'controller']):
                return 'integration'
        
        # Default to unit for isolated non-React files (pure JS/TS utilities)
        return 'unit'
    
    def _find_related_files(
        self,
        file_info: FileInfo,
        files_by_dir: Dict[str, List[FileInfo]]
    ) -> List[str]:
        """Find related files for integration/feature tests"""
        source_path = Path(file_info.relative_path)
        dir_path = str(source_path.parent)
        
        # Get files in same directory
        dir_files = files_by_dir.get(dir_path, [])
        
        # Find related files (limit to 7 for integration, 12 for feature)
        related = []
        base_name = source_path.stem.lower()
        
        for f in dir_files:
            if f.relative_path == file_info.relative_path:
                continue
            
            f_path = Path(f.relative_path)
            f_name = f_path.stem.lower()
            
            # Check for related patterns
            if (base_name in f_name or f_name in base_name or
                any(pattern in f_name for pattern in ['hook', 'api', 'service', 'store', 'util'])):
                related.append(f.relative_path)
                
                if len(related) >= 7:
                    break
        
        return related if related else None
    
    def _estimate_test_count(self, strategy: TestStrategy) -> int:
        """Estimate number of tests for a file"""
        if strategy.complexity == 'complex':
            return 8
        elif strategy.complexity == 'moderate':
            return 5
        else:
            return 3
    
    def format_strategy_summary(self, result: TestStrategyResult) -> str:
        """Format strategy result for display"""
        lines = []
        lines.append("=" * 60)
        lines.append("TEST GENERATION STRATEGY")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Files to test: {result.total_files_to_test}")
        lines.append(f"Estimated tests: {result.estimated_tests}")
        lines.append("")
        lines.append("Strategy breakdown:")
        
        # Group by framework
        jest_strategies = [s for s in result.strategies if s.framework == 'jest']
        pytest_strategies = [s for s in result.strategies if s.framework == 'pytest']
        
        if jest_strategies:
            lines.append(f"  Jest tests: {len(jest_strategies)} files")
        if pytest_strategies:
            lines.append(f"  Pytest tests: {len(pytest_strategies)} files")
        
        lines.append("")
        lines.append("Test level breakdown:")
        unit_tests = len([s for s in result.strategies if s.test_level == 'unit'])
        integration_tests = len([s for s in result.strategies if s.test_level == 'integration'])
        feature_tests = len([s for s in result.strategies if s.test_level == 'feature'])
        
        if unit_tests:
            lines.append(f"  Unit tests: {unit_tests} files")
        if integration_tests:
            lines.append(f"  Integration tests: {integration_tests} files")
        if feature_tests:
            lines.append(f"  Feature tests: {feature_tests} files")
        
        lines.append("")
        lines.append("Priority breakdown:")
        high_priority = len([s for s in result.strategies if s.priority == 'high'])
        medium_priority = len([s for s in result.strategies if s.priority == 'medium'])
        low_priority = len([s for s in result.strategies if s.priority == 'low'])
        
        if high_priority:
            lines.append(f"  High priority: {high_priority} files")
        if medium_priority:
            lines.append(f"  Medium priority: {medium_priority} files")
        if low_priority:
            lines.append(f"  Low priority: {low_priority} files")
        
        lines.append("")
        lines.append("=" * 60)
        
        return '\n'.join(lines)
    
    def group_strategies_by_level(self, strategies: List[TestStrategy]) -> Dict[TestLevel, List[TestStrategy]]:
        """Group strategies by test level"""
        grouped = {
            'unit': [],
            'integration': [],
            'feature': []
        }
        
        for strategy in strategies:
            grouped[strategy.test_level].append(strategy)
        
        return grouped