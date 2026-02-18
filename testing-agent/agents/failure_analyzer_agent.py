"""
Failure Analyzer Agent
Analyzes test failures and provides insights using AI
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from config.vertex_ai import GeminiClient
from agents.test_executor_agent import TestExecutionResult, TestCase

logger = logging.getLogger(__name__)


@dataclass
class FailureAnalysis:
    """Analysis of test failures"""
    summary: str
    likely_causes: List[str]
    recommendations: List[str]
    affected_tests: List[str]
    severity: str  # critical, high, medium, low
    is_environment_issue: bool = False  # NEW: Flag for environment/setup issues
    should_retry: bool = True  # NEW: Flag for retry recommendation


class FailureAnalyzerAgent:
    """
    Agent for analyzing test failures
    Provides insights and recommendations
    """
    
    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        """
        Initialize failure analyzer
        
        Args:
            gemini_client: Optional Gemini client for AI analysis
        """
        self.client = gemini_client
    
    def analyze_failures(
        self,
        execution_result: TestExecutionResult
    ) -> Optional[FailureAnalysis]:
        """
        Analyze test failures
        
        Args:
            execution_result: Test execution result
            
        Returns:
            Optional[FailureAnalysis]: Analysis or None
        """
        if execution_result.failed == 0:
            logger.info("No failures to analyze")
            return None
        
        logger.info(f"Analyzing {execution_result.failed} test failures")
        
        # Get failed test cases
        failed_tests = [tc for tc in execution_result.test_cases if tc.status == 'failed']
        
        if not failed_tests:
            # Try basic analysis from output
            return self._basic_failure_analysis(execution_result)
        
        # If AI available, use it
        if self.client and self.client.is_ready():
            return self._ai_failure_analysis(execution_result, failed_tests)
        else:
            return self._basic_failure_analysis(execution_result, failed_tests)
    
    def _basic_failure_analysis(
        self,
        execution_result: TestExecutionResult,
        failed_tests: Optional[List[TestCase]] = None
    ) -> FailureAnalysis:
        """Basic failure analysis without AI"""
        
        # Analyze common patterns
        likely_causes = []
        recommendations = []
        affected_tests = []
        
        if failed_tests:
            affected_tests = [tc.name for tc in failed_tests]
            
            # Check for common error patterns
            error_messages = [tc.error_message for tc in failed_tests if tc.error_message]
            all_errors = '\n'.join(error_messages)
            
            # Pattern matching
            if 'timeout' in all_errors.lower():
                likely_causes.append("Tests timing out")
                recommendations.append("Increase timeout values or optimize slow operations")
            
            if 'cannot find module' in all_errors.lower() or 'importerror' in all_errors.lower():
                likely_causes.append("Missing dependencies")
                recommendations.append("Install missing packages: npm install or pip install")
            
            # NEW: Environment/setup failures
            if 'msw' in all_errors.lower() or 'mock service worker' in all_errors.lower():
                likely_causes.append("MSW (Mock Service Worker) not properly configured")
                recommendations.append("Ensure MSW is installed and server is set up in test files")
            
            if 'setuptest' in all_errors.lower() or 'jest.setup' in all_errors.lower():
                likely_causes.append("Test setup file missing or misconfigured")
                recommendations.append("Check setupTests.ts or jest.setup.js configuration")
            
            if 'fixture' in all_errors.lower() and execution_result.framework == 'pytest':
                likely_causes.append("Pytest fixture not defined or unavailable")
                recommendations.append("Check conftest.py for required fixtures")
            
            if 'jsdom' in all_errors.lower():
                likely_causes.append("Test environment not configured for DOM testing")
                recommendations.append("Set testEnvironment: 'jsdom' in jest.config.js")
            
            if 'render is not defined' in all_errors.lower() or '@testing-library' in all_errors.lower():
                likely_causes.append("React Testing Library not properly imported")
                recommendations.append("Ensure @testing-library/react is installed and imported")
            
            if 'assertion' in all_errors.lower() or 'expected' in all_errors.lower():
                likely_causes.append("Assertion failures")
                recommendations.append("Review test expectations and actual implementation")
            
            if 'network' in all_errors.lower() or 'connection' in all_errors.lower():
                likely_causes.append("Network/connection issues")
                recommendations.append("Check external service availability or mock API calls")
            
            if not likely_causes:
                likely_causes.append("Test logic or implementation mismatch")
                recommendations.append("Review failing test cases and implementation details")
        else:
            # No specific failed tests, check stderr
            stderr = execution_result.stderr.lower()
            stdout = execution_result.stdout.lower() if execution_result.stdout else ""
            combined_output = stderr + " " + stdout
            
            if 'no tests found' in stderr:
                likely_causes.append("No tests found or executed")
                recommendations.append("Verify test files are in correct location and properly named")
            elif 'syntax error' in stderr:
                likely_causes.append("Syntax errors in test files")
                recommendations.append("Fix syntax errors in test or source files")
            elif 'configuration' in combined_output and 'error' in combined_output:
                likely_causes.append("Test framework configuration error")
                recommendations.append("Check jest.config.js or pytest.ini configuration")
            elif 'module not found' in combined_output or 'cannot find' in combined_output:
                likely_causes.append("Missing test dependencies")
                recommendations.append("Install required packages: npm install or pip install")
            else:
                likely_causes.append("Test execution error")
                recommendations.append("Check error output for specific issues")
        
        # Determine severity
        failure_rate = execution_result.failed / max(execution_result.total_tests, 1)
        if failure_rate >= 0.5:
            severity = 'critical'
        elif failure_rate >= 0.3:
            severity = 'high'
        elif failure_rate >= 0.1:
            severity = 'medium'
        else:
            severity = 'low'
        
        summary = f"{execution_result.failed} out of {execution_result.total_tests} tests failed ({failure_rate:.1%})"
        
        # Determine if this is an environment issue (should not retry immediately)
        is_environment_issue = any(
            keyword in cause.lower() 
            for cause in likely_causes 
            for keyword in ['msw', 'setup', 'fixture', 'configuration', 'environment', 'dependencies']
        )
        
        # Decide if retry is recommended
        should_retry = not is_environment_issue and failure_rate < 0.8
        
        return FailureAnalysis(
            summary=summary,
            likely_causes=likely_causes,
            recommendations=recommendations,
            affected_tests=affected_tests,
            severity=severity,
            is_environment_issue=is_environment_issue,
            should_retry=should_retry
        )
    
    def _ai_failure_analysis(
        self,
        execution_result: TestExecutionResult,
        failed_tests: List[TestCase]
    ) -> Optional[FailureAnalysis]:
        """AI-powered failure analysis"""
        
        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(execution_result, failed_tests)
            
            # Generate analysis
            response = self.client.generate_content(prompt)
            
            if not response:
                logger.warning("Empty response from AI, falling back to basic analysis")
                return self._basic_failure_analysis(execution_result, failed_tests)
            
            # Parse response
            analysis = self._parse_analysis_response(response, failed_tests)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self._basic_failure_analysis(execution_result, failed_tests)
    
    def _build_analysis_prompt(
        self,
        execution_result: TestExecutionResult,
        failed_tests: List[TestCase]
    ) -> str:
        """Build prompt for AI analysis"""
        
        # Collect error details (limit to avoid token overflow)
        error_details = []
        for test in failed_tests[:10]:  # Limit to 10 failed tests
            detail = f"Test: {test.name}\n"
            if test.file:
                detail += f"File: {test.file}\n"
            if test.error_message:
                detail += f"Error: {test.error_message[:500]}\n"  # Limit error message
            error_details.append(detail)
        
        prompt = f"""You are an expert software test engineer. Analyze the following test failures and provide insights.

Test Framework: {execution_result.framework}
Total Tests: {execution_result.total_tests}
Passed: {execution_result.passed}
Failed: {execution_result.failed}
Skipped: {execution_result.skipped}

Failed Tests:
{''.join(error_details)}

Stderr Output (first 1000 chars):
{execution_result.stderr[:1000]}

Provide analysis in JSON format:
{{
  "summary": "Brief summary of failures",
  "likely_causes": ["cause 1", "cause 2"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "severity": "critical/high/medium/low"
}}

Respond with ONLY the JSON object."""

        return prompt
    
    def _parse_analysis_response(
        self,
        response: str,
        failed_tests: List[TestCase]
    ) -> FailureAnalysis:
        """Parse AI analysis response"""
        
        try:
            import json
            
            # Extract JSON
            response = response.strip()
            if '```' in response:
                # Remove markdown code fences
                lines = response.split('\n')
                json_lines = []
                in_json = False
                
                for line in lines:
                    if line.strip().startswith('```'):
                        if in_json:
                            break
                        else:
                            in_json = True
                            continue
                    if in_json:
                        json_lines.append(line)
                
                response = '\n'.join(json_lines)
            
            # Find JSON object
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx + 1]
                data = json.loads(json_str)
                
                return FailureAnalysis(
                    summary=data.get('summary', 'Test failures detected'),
                    likely_causes=data.get('likely_causes', []),
                    recommendations=data.get('recommendations', []),
                    affected_tests=[tc.name for tc in failed_tests],
                    severity=data.get('severity', 'medium')
                )
        
        except Exception as e:
            logger.warning(f"Failed to parse AI response: {e}")
        
        # Fallback
        return FailureAnalysis(
            summary="AI analysis unavailable",
            likely_causes=["Analysis failed"],
            recommendations=["Review error messages manually"],
            affected_tests=[tc.name for tc in failed_tests],
            severity='medium'
        )
    
    def format_analysis(self, analysis: FailureAnalysis) -> str:
        """Format analysis for display"""
        
        lines = []
        lines.append("=" * 60)
        lines.append("FAILURE ANALYSIS")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Summary: {analysis.summary}")
        lines.append(f"Severity: {analysis.severity.upper()}")
        lines.append("")
        
        if analysis.likely_causes:
            lines.append("Likely Causes:")
            for i, cause in enumerate(analysis.likely_causes, 1):
                lines.append(f"  {i}. {cause}")
            lines.append("")
        
        if analysis.recommendations:
            lines.append("Recommendations:")
            for i, rec in enumerate(analysis.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        if analysis.affected_tests:
            lines.append(f"Affected Tests ({len(analysis.affected_tests)}):")
            for test in analysis.affected_tests[:10]:  # Show first 10
                lines.append(f"  - {test}")
            if len(analysis.affected_tests) > 10:
                lines.append(f"  ... and {len(analysis.affected_tests) - 10} more")
            lines.append("")
        
        lines.append("=" * 60)
        
        return '\n'.join(lines)

