"""
LangGraph-style Workflow Orchestration
Manages end-to-end testing workflow with state management, retries, and cleanup
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from tools.file_indexer import FileIndexer, IndexResult
from config.vertex_ai import get_gemini_client
from agents.analyze_agent import AnalyzeAgent, ProjectAnalysisResult
from agents.strategy_agent import StrategyAgent, TestStrategyResult, TestStrategy
from agents.test_generator_agent import TestGeneratorAgent, GeneratedTest
from agents.test_executor_agent import TestExecutorAgent, TestExecutionResult
from agents.failure_analyzer_agent import FailureAnalyzerAgent
from agents.report_agent import ReportAgent, UnifiedTestReport
from agents.environment_setup_agent import EnvironmentSetupAgent, EnvironmentSetupResult

logger = logging.getLogger(__name__)


class WorkflowStage(Enum):
    """Workflow stages"""
    INITIALIZED = "initialized"
    INDEXING = "indexing"
    ANALYZING = "analyzing"
    STRATEGIZING = "strategizing"
    GENERATING = "generating"
    EXECUTING = "executing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CLEANUP = "cleanup"


@dataclass
class WorkflowState:
    """Shared state for workflow orchestration"""
    # Identification
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_path: Path = None  # Workspace project path (temporary)
    main_project_path: Path = None  # Main project path (outside workspace, for test files)
    
    # Stage tracking
    current_stage: WorkflowStage = WorkflowStage.INITIALIZED
    completed_stages: List[WorkflowStage] = field(default_factory=list)
    failed_stages: List[WorkflowStage] = field(default_factory=list)
    
    # Retry tracking
    retry_count: int = 0
    max_retries: int = 3
    stage_retries: Dict[str, int] = field(default_factory=dict)
    
    # Execution limits
    max_execution_time: float = 300.0  # 5 minutes per test
    start_time: float = field(default_factory=time.time)
    
    # Data storage
    index_result: Optional[IndexResult] = None
    analysis_result: Optional[ProjectAnalysisResult] = None
    strategy_result: Optional[TestStrategyResult] = None
    
    # NEW: Test-level organized data
    test_plan: Dict[str, List[TestStrategy]] = field(default_factory=dict)  # {level: [strategies]}
    generated_tests: List[GeneratedTest] = field(default_factory=list)
    generated_tests_by_level: Dict[str, List[GeneratedTest]] = field(default_factory=dict)  # {level: [tests]}
    execution_results: Dict[str, TestExecutionResult] = field(default_factory=dict)  # {framework: result}
    execution_results_by_level: Dict[str, Dict[str, TestExecutionResult]] = field(default_factory=dict)  # {level: {framework: result}}
    environment_setup_results: Dict[str, EnvironmentSetupResult] = field(default_factory=dict)  # {level: result}
    
    unified_report: Optional[UnifiedTestReport] = None
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # NEW: Test level filtering
    test_levels_filter: Optional[List[str]] = None  # If set, only run these levels
    
    # Cleanup flags
    needs_cleanup: bool = False
    cleanup_completed: bool = False
    
    def add_error(self, error: str):
        """Add error to state"""
        self.errors.append(f"[{self.current_stage.value}] {error}")
        logger.error(f"Workflow error: {error}")
    
    def add_warning(self, warning: str):
        """Add warning to state"""
        self.warnings.append(f"[{self.current_stage.value}] {warning}")
        logger.warning(f"Workflow warning: {warning}")
    
    def can_retry(self) -> bool:
        """Check if workflow can retry"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry count"""
        self.retry_count += 1
        stage_key = self.current_stage.value
        self.stage_retries[stage_key] = self.stage_retries.get(stage_key, 0) + 1
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since start"""
        return time.time() - self.start_time
    
    def is_timeout(self) -> bool:
        """Check if workflow has timed out"""
        # Overall timeout: 30 minutes
        return self.get_elapsed_time() > 1800.0


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    success: bool
    state: WorkflowState
    message: str
    duration: float


class WorkflowOrchestrator:
    """
    LangGraph-style workflow orchestrator
    Manages end-to-end testing workflow with state, retries, and cleanup
    """
    
    def __init__(self, project_path: Path, main_project_path: Optional[Path] = None):
        """
        Initialize workflow orchestrator
        
        Args:
            project_path: Path to workspace project directory (temporary)
            main_project_path: Path to main project directory (outside workspace, for test files)
        """
        self.project_path = project_path
        # If main_project_path not provided, use the parent of workspaces directory
        if main_project_path is None:
            # Default to root directory (where app.py is)
            main_project_path = Path(__file__).parent.parent
        self.main_project_path = main_project_path
        self.state = WorkflowState(
            project_path=project_path,
            main_project_path=main_project_path
        )
        
        # Define workflow stages
        self.stages = [
            self._stage_indexing,
            self._stage_analyzing,
            self._stage_strategizing,
            self._stage_generating,
            self._stage_executing,
            self._stage_reporting,
        ]
    
    def execute(self, test_levels: Optional[List[str]] = None) -> WorkflowResult:
        """
        Execute complete workflow
        
        Args:
            test_levels: Optional list of test levels to execute ['unit', 'integration', 'feature']
                        If None, executes all levels
        
        Returns:
            WorkflowResult: Workflow execution result
        """
        # Store test levels filter in state
        if test_levels:
            self.state.test_levels_filter = test_levels
            logger.info(f"Starting workflow: {self.state.workflow_id} - Levels: {', '.join(test_levels)}")
        else:
            self.state.test_levels_filter = None
            logger.info(f"Starting workflow: {self.state.workflow_id} - All levels")
        
        try:
            # Execute stages sequentially
            for stage_func in self.stages:
                if self.state.is_timeout():
                    self.state.add_error("Workflow timeout exceeded")
                    return self._create_result(False, "Workflow timed out")
                
                # Update current stage
                stage_name = stage_func.__name__.replace('_stage_', '')
                self.state.current_stage = WorkflowStage[stage_name.upper()]
                
                # Execute stage with retry guard
                success = self._execute_stage_with_retry(stage_func)
                
                if not success:
                    # Stage failed after retries
                    self.state.failed_stages.append(self.state.current_stage)
                    
                    # Check if we can continue
                    if not self._can_continue_after_failure():
                        return self._create_result(False, f"Workflow failed at {self.state.current_stage.value}")
                    
                    # Continue with next stage
                    self.state.add_warning(f"Stage {self.state.current_stage.value} failed, continuing...")
                
                # Mark stage as completed
                self.state.completed_stages.append(self.state.current_stage)
            
            # Mark as completed
            self.state.current_stage = WorkflowStage.COMPLETED
            
            return self._create_result(True, "Workflow completed successfully")
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            self.state.add_error(str(e))
            self.state.current_stage = WorkflowStage.FAILED
            return self._create_result(False, f"Workflow error: {str(e)}")
        
        finally:
            # Always cleanup
            self._cleanup()
    
    def _execute_stage_with_retry(self, stage_func: Callable) -> bool:
        """
        Execute stage with retry logic
        
        Args:
            stage_func: Stage function to execute
            
        Returns:
            bool: Success status
        """
        max_stage_retries = 3
        
        for attempt in range(max_stage_retries):
            try:
                logger.info(f"Executing {self.state.current_stage.value} (attempt {attempt + 1}/{max_stage_retries})")
                
                result = stage_func()
                
                if result:
                    return True
                
                # Stage failed, retry if possible
                if attempt < max_stage_retries - 1:
                    self.state.increment_retry()
                    logger.warning(f"Stage {self.state.current_stage.value} failed, retrying...")
                    time.sleep(1)  # Brief delay before retry
                else:
                    self.state.add_error(f"Stage {self.state.current_stage.value} failed after {max_stage_retries} attempts")
                    return False
                    
            except Exception as e:
                logger.error(f"Error in {self.state.current_stage.value}: {e}")
                self.state.add_error(f"Exception in {self.state.current_stage.value}: {str(e)}")
                
                if attempt < max_stage_retries - 1:
                    self.state.increment_retry()
                    time.sleep(1)
                else:
                    return False
        
        return False
    
    def _stage_indexing(self) -> bool:
        """Stage 1: File indexing"""
        try:
            logger.info("Stage: Indexing project files")
            
            success, message, index_result = FileIndexer.index_directory(
                self.project_path,
                include_lines=True
            )
            
            if not success:
                self.state.add_error(f"Indexing failed: {message}")
                return False
            
            self.state.index_result = index_result
            logger.info(f"Indexing complete: {index_result.total_files} files")
            return True
            
        except Exception as e:
            self.state.add_error(f"Indexing error: {str(e)}")
            return False
    
    def _stage_analyzing(self) -> bool:
        """Stage 2: AI-powered analysis"""
        try:
            logger.info("Stage: Analyzing project with AI")
            
            if not self.state.index_result:
                self.state.add_warning("No index result, skipping analysis")
                return True  # Non-critical
            
            gemini_client = get_gemini_client()
            if not gemini_client or not gemini_client.is_ready():
                self.state.add_warning("Gemini not available, skipping AI analysis")
                return True  # Non-critical
            
            analyze_agent = AnalyzeAgent(gemini_client)
            analysis_result = analyze_agent.analyze_project(
                self.state.index_result,
                self.project_path,
                main_project_path=self.main_project_path
            )
            
            if analysis_result:
                self.state.analysis_result = analysis_result
                logger.info(f"Analysis complete: {len(analysis_result.languages)} language(s)")
            
            return True  # Analysis is optional
            
        except Exception as e:
            self.state.add_warning(f"Analysis error (non-critical): {str(e)}")
            return True  # Non-critical stage
    
    def _stage_strategizing(self) -> bool:
        """Stage 3: Test strategy determination"""
        try:
            logger.info("Stage: Determining test strategy")
            
            if not self.state.index_result:
                self.state.add_error("No index result for strategy")
                return False
            
            gemini_client = get_gemini_client()
            if not gemini_client or not gemini_client.is_ready():
                self.state.add_warning("Gemini not available, using basic strategy")
                # Use basic strategy (non-critical)
                return True
            
            strategy_agent = StrategyAgent(gemini_client)
            
            # FIXED: Pass user's requested test levels to the strategy agent
            strategy_result = strategy_agent.determine_test_strategy(
                self.state.index_result,
                self.state.analysis_result,
                self.project_path,
                requested_test_levels=self.state.test_levels_filter  # NEW: Pass user selection
            )
            
            if strategy_result:
                self.state.strategy_result = strategy_result
                logger.info(f"Strategy complete: {strategy_result.total_files_to_test} files to test")
                
                # Group strategies by test level
                self.state.test_plan = strategy_agent.group_strategies_by_level(strategy_result.strategies)

                # Log test level breakdown
                for level, strategies in self.state.test_plan.items():
                    if strategies:
                        logger.info(f"  {level.upper()} tests: {len(strategies)} files")

                # FIXED: Simple filtering only - no promotion logic
                # The strategy agent already handles user's requested test levels
                if self.state.test_levels_filter:
                    filtered_plan = {
                        level: strategies
                        for level, strategies in self.state.test_plan.items()
                        if level in self.state.test_levels_filter
                    }
                    
                    self.state.test_plan = filtered_plan
                    logger.info(f"Applied test level filter: {', '.join(self.state.test_levels_filter)}")
                    
                    # Log filtered breakdown
                    for level, strategies in self.state.test_plan.items():
                        if strategies:
                            logger.info(f"  Filtered {level.upper()} tests: {len(strategies)} files")
            
            return True
            
        except Exception as e:
            self.state.add_error(f"Strategy error: {str(e)}")
            return False
    
    def _stage_generating(self) -> bool:
        """Stage 4: Test generation (now with test-level support)"""
        try:
            logger.info("Stage: Generating tests by level")
            
            if not self.state.strategy_result or not self.state.strategy_result.strategies:
                self.state.add_warning("No test strategy, skipping generation")
                return True  # Non-critical
            
            gemini_client = get_gemini_client()
            if not gemini_client or not gemini_client.is_ready():
                self.state.add_warning("Gemini not available, skipping test generation")
                return True  # Non-critical
            
            test_generator = TestGeneratorAgent(gemini_client)
            all_generated_tests = []
            
            # Generate tests by level: unit → integration → feature
            # Use filtered levels if specified, otherwise all levels
            if self.state.test_levels_filter:
                test_levels = [lvl for lvl in ['unit', 'integration', 'feature'] if lvl in self.state.test_levels_filter]
            else:
                test_levels = ['unit', 'integration', 'feature']
            
            for level in test_levels:
                level_strategies = self.state.test_plan.get(level, [])
                if not level_strategies:
                    continue
                
                logger.info(f"Generating {level} tests for {len(level_strategies)} files")
                
                # Limit strategies per level for demo
                max_per_level = {'unit': 5, 'integration': 3, 'feature': 2}
                strategies_to_generate = level_strategies[:max_per_level.get(level, 5)]
                
                # Generate tests for this level
                generated_tests = test_generator.generate_tests(
                    strategies_to_generate,
                    self.main_project_path,  # Save tests outside workspace
                    self.state.analysis_result,
                    workspace_path=self.project_path  # For reading source files
                )
                
                # Store by level
                self.state.generated_tests_by_level[level] = generated_tests
                all_generated_tests.extend(generated_tests)
                
                successful = sum(1 for t in generated_tests if t.success)
                logger.info(f"  {level.upper()}: {successful}/{len(generated_tests)} tests generated")
            
            self.state.generated_tests = all_generated_tests
            
            total_successful = sum(1 for t in all_generated_tests if t.success)
            logger.info(f"Generation complete: {total_successful}/{len(all_generated_tests)} total tests generated")
            
            return True  # Generation is optional
            
        except Exception as e:
            self.state.add_warning(f"Generation error (non-critical): {str(e)}")
            return True  # Non-critical stage
    
    def _stage_executing(self) -> bool:
        """Stage 5: Test execution (now with test-level support)"""
        try:
            # Show only selected levels in log message
            if self.state.test_levels_filter:
                level_display = ' → '.join([lvl.title() for lvl in self.state.test_levels_filter])
                logger.info(f"Stage: Executing tests by level ({level_display})")
            else:
                logger.info("Stage: Executing tests by level (unit → integration → feature)")
            
            if not self.state.generated_tests:
                reason = "No generated tests to execute"
                logger.warning(reason)
                self.state.add_warning(reason)
                return True  # Non-critical
            
            # Use main_project_path for test execution (tests are saved outside workspace)
            executor = TestExecutorAgent(self.main_project_path)
            environment_agent = EnvironmentSetupAgent(get_gemini_client())
            
            # Execute tests by level: unit → integration → feature
            # Use filtered levels if specified, otherwise all levels
            if self.state.test_levels_filter:
                test_levels = [lvl for lvl in ['unit', 'integration', 'feature'] if lvl in self.state.test_levels_filter]
            else:
                test_levels = ['unit', 'integration', 'feature']
            
            for test_level in test_levels:
                level_tests = self.state.generated_tests_by_level.get(test_level, [])
                if not level_tests:
                    continue
                
                successful_tests = [t for t in level_tests if t.success]
                if not successful_tests:
                    logger.info(f"Skipping {test_level} tests: No successful test generation")
                    continue
                
                logger.info(f"Executing {test_level.upper()} tests: {len(successful_tests)} test file(s)")
                
                # Get frameworks for this level
                frameworks_for_level = set(t.framework for t in successful_tests)
                
                if not self.state.execution_results_by_level.get(test_level):
                    self.state.execution_results_by_level[test_level] = {}
                
                for framework in frameworks_for_level:
                    try:
                        # Step 1: Environment Setup (for integration/feature tests)
                        if test_level in ['integration', 'feature']:
                            logger.info(f"Setting up environment for {test_level} {framework} tests")
                            level_strategies = self.state.test_plan.get(test_level, [])
                            env_result = environment_agent.setup_environment(
                                test_level, framework, self.main_project_path, level_strategies
                            )
                            self.state.environment_setup_results[f"{test_level}_{framework}"] = env_result
                            
                            if not env_result.success:
                                logger.warning(f"Environment setup failed for {test_level} {framework}: {env_result.error}")
                                self.state.add_warning(f"Environment setup failed for {test_level} {framework}")
                        
                        # Step 2: Execute tests for this level
                        logger.info(f"Executing {framework} {test_level} tests")
                        
                        # Filter tests for this framework at this level
                        framework_level_tests = [t for t in successful_tests if t.framework == framework]
                        
                        # Adjust timeout based on test level
                        timeout = {
                            'unit': 180,  # 3 minutes for unit tests
                            'integration': 300,  # 5 minutes for integration tests
                            'feature': 600  # 10 minutes for feature tests
                        }.get(test_level, 300)
                        
                        result = executor.execute_tests(
                            framework,
                            timeout=timeout,
                            generated_tests=framework_level_tests,
                            test_level=test_level
                        )
                        
                        if result:
                            # Store by level and framework
                            self.state.execution_results_by_level[test_level][framework] = result
                            # Also store in flat structure for backward compatibility
                            self.state.execution_results[f"{test_level}_{framework}"] = result
                            
                            if result.success:
                                logger.info(f"{test_level.upper()} {framework.upper()}: ✓ All {result.passed} tests passed")
                            else:
                                logger.warning(f"{test_level.upper()} {framework.upper()}: ✗ {result.failed}/{result.total_tests} tests failed")
                        
                    except Exception as e:
                        error_msg = f"Error executing {test_level} {framework} tests: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        self.state.add_error(error_msg)
            
            # Log execution summary
            total_executed = sum(len(results) for results in self.state.execution_results_by_level.values())
            logger.info(f"Execution stage complete: {total_executed} level-framework combination(s) executed")
            
            for level, results in self.state.execution_results_by_level.items():
                for framework, result in results.items():
                    logger.info(f"  {level.upper()} {framework}: {result.total_tests} tests, {result.passed} passed, {result.failed} failed")
            
            return True  # Execution is optional
            
        except Exception as e:
            error_msg = f"Execution stage error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.state.add_error(error_msg)
            return True  # Non-critical stage
    
    def _stage_reporting(self) -> bool:
        """Stage 6: Report generation"""
        try:
            logger.info("Stage: Generating reports")
            
            if not self.state.execution_results:
                # Provide detailed diagnostics
                diagnostic_msg = "No execution results available for reporting"
                logger.warning(diagnostic_msg)
                
                # Check why execution didn't produce results
                reasons = []
                
                if not self.state.generated_tests:
                    reasons.append("No tests were generated in the generation stage")
                else:
                    successful_tests = [t for t in self.state.generated_tests if t.success]
                    if not successful_tests:
                        reasons.append(f"All {len(self.state.generated_tests)} generated tests failed")
                    else:
                        reasons.append(f"Only {len(successful_tests)}/{len(self.state.generated_tests)} tests were successful")
                        
                        # Check if execution was attempted
                        frameworks_in_tests = set(t.framework for t in successful_tests)
                        if frameworks_in_tests:
                            reasons.append(f"Frameworks with successful tests: {', '.join(frameworks_in_tests)}")
                            
                            # Check for common issues
                            if 'jest' in frameworks_in_tests:
                                # Use main_project_path for test execution (tests are saved outside workspace)
                                executor = TestExecutorAgent(self.main_project_path)
                                npm_available = executor.executor.check_command_available('npm')
                                npx_available = executor.executor.check_command_available('npx')
                                if not npm_available and not npx_available:
                                    reasons.append("Jest execution skipped: npm/npx not available")
                            
                            if 'pytest' in frameworks_in_tests:
                                # Use main_project_path for test execution (tests are saved outside workspace)
                                executor = TestExecutorAgent(self.main_project_path)
                                if not executor.can_execute_pytest():
                                    reasons.append("Pytest execution skipped: pytest not available")
                
                # Check for execution errors
                execution_errors = [e for e in self.state.errors if 'executing' in e.lower() or 'execution' in e.lower()]
                if execution_errors:
                    reasons.append(f"Execution errors occurred: {len(execution_errors)} error(s)")
                
                detailed_msg = f"{diagnostic_msg}. Reasons: {'; '.join(reasons)}"
                logger.warning(detailed_msg)
                self.state.add_warning(detailed_msg)
                return True  # Non-critical
            
            # Validate execution results
            valid_results = {}
            for framework, result in self.state.execution_results.items():
                if result is None:
                    logger.warning(f"Skipping {framework} result: None")
                    continue
                if not hasattr(result, 'total_tests'):
                    logger.warning(f"Skipping {framework} result: Invalid result object")
                    continue
                valid_results[framework] = result
            
            if not valid_results:
                logger.warning("No valid execution results after validation")
                self.state.add_warning("Execution results exist but are invalid, skipping reporting")
                return True
            
            logger.info(f"Generating unified report for {len(valid_results)} framework(s)")
            
            # Pass main_project_path so ReportAgent can find coverage files
            report_agent = ReportAgent(self.project_path, main_project_path=self.main_project_path)
            unified_report = report_agent.generate_unified_report(
                valid_results,
                execution_results_by_level=self.state.execution_results_by_level
            )
            
            if unified_report is None:
                error_msg = "Report generation returned None"
                logger.error(error_msg)
                self.state.add_error(error_msg)
                return True  # Non-critical
            
            self.state.unified_report = unified_report
            
            # Save reports
            try:
                json_file = report_agent.save_json_report(unified_report)
                logger.info(f"Saved JSON report: {json_file}")
            except Exception as e:
                logger.warning(f"Failed to save JSON report: {e}")
                self.state.add_warning(f"JSON report save failed: {str(e)}")
            
            try:
                html_file = report_agent.save_html_report(unified_report)
                logger.info(f"Saved HTML report: {html_file}")
            except Exception as e:
                logger.warning(f"Failed to save HTML report: {e}")
                self.state.add_warning(f"HTML report save failed: {str(e)}")
            
            logger.info(f"Reporting complete: {unified_report.total_tests} total tests, {unified_report.passed} passed, {unified_report.failed} failed")
            return True
            
        except Exception as e:
            error_msg = f"Reporting stage error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.state.add_error(error_msg)
            return True  # Non-critical stage
    
    def _can_continue_after_failure(self) -> bool:
        """Determine if workflow can continue after stage failure"""
        # Critical stages that must succeed
        critical_stages = [
            WorkflowStage.INDEXING,
        ]
        
        if self.state.current_stage in critical_stages:
            return False
        
        # Other stages are optional
        return True
    
    def _cleanup(self):
        """Cleanup resources"""
        if self.state.cleanup_completed:
            return
        
        logger.info("Cleaning up workflow resources")
        
        try:
            # Mark for cleanup
            self.state.needs_cleanup = True
            
            # Cleanup logic here (if needed)
            # - Close file handles
            # - Release resources
            # - etc.
            
            self.state.cleanup_completed = True
            logger.info("Cleanup complete")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def _create_result(self, success: bool, message: str) -> WorkflowResult:
        """Create workflow result"""
        duration = self.state.get_elapsed_time()
        return WorkflowResult(
            success=success,
            state=self.state,
            message=message,
            duration=duration
        )
    
    def get_state(self) -> WorkflowState:
        """Get current workflow state"""
        return self.state