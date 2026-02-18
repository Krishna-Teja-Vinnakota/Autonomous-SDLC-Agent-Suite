"""
Report Agent
Generates unified test reports with coverage and visualizations
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

from agents.test_executor_agent import TestExecutionResult
from tools.coverage_parser import CoverageReport, CoverageParser

logger = logging.getLogger(__name__)


@dataclass
class UnifiedTestReport:
    """Unified test report combining execution and coverage"""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    pass_rate: float
    total_coverage: float
    execution_results: Dict[str, Any]
    coverage_reports: Dict[str, Any]
    test_cases: List[Dict[str, Any]]
    summary: str
    # NEW: Test-level breakdowns
    results_by_level: Dict[str, Dict[str, Any]] = None  # {level: {total, passed, failed, ...}}
    coverage_by_level: Dict[str, float] = None  # {level: coverage%}


class ReportAgent:
    """
    Agent for generating comprehensive test reports
    Combines execution results with coverage data
    """
    
    def __init__(self, project_path: Path, main_project_path: Optional[Path] = None):
        """
        Initialize report agent
        
        Args:
            project_path: Path to workspace project directory
            main_project_path: Optional path to main project directory (where coverage is generated)
        """
        self.project_path = project_path
        self.main_project_path = main_project_path
        self.reports_dir = project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True)
    
    def generate_unified_report(
        self,
        execution_results: Dict[str, TestExecutionResult],
        project_name: str = "Project",
        execution_results_by_level: Optional[Dict[str, Dict[str, TestExecutionResult]]] = None
    ) -> UnifiedTestReport:
        """
        Generate unified test report
        
        Args:
            execution_results: Test execution results by framework
            project_name: Name of the project
            
        Returns:
            UnifiedTestReport: Complete report
        """
        logger.info("Generating unified test report")
        
        # Aggregate test metrics
        total_tests = 0
        passed = 0
        failed = 0
        skipped = 0
        test_cases = []
        
        execution_data = {}
        
        for framework, result in execution_results.items():
            total_tests += result.total_tests
            passed += result.passed
            failed += result.failed
            skipped += result.skipped
            
            # Collect test cases
            for tc in result.test_cases:
                test_cases.append({
                    'name': tc.name,
                    'status': tc.status,
                    'duration': tc.duration,
                    'file': tc.file,
                    'framework': framework,
                    'error': tc.error_message
                })
            
            execution_data[framework] = {
                'total': result.total_tests,
                'passed': result.passed,
                'failed': result.failed,
                'skipped': result.skipped,
                'duration': result.duration,
                'success': result.success
            }
        
        # Calculate pass rate
        pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        
        # Parse coverage
        coverage_reports_data = {}
        total_coverage = 0.0
        coverage_count = 0
        
        for framework in execution_results.keys():
            coverage = self._parse_coverage(framework)
            if coverage:
                coverage_reports_data[framework] = {
                    'total_coverage': coverage.total_coverage,
                    'lines_covered': coverage.lines_covered,
                    'lines_total': coverage.lines_total,
                    'branches_covered': coverage.branches_covered,
                    'branches_total': coverage.branches_total,
                    'functions_covered': coverage.functions_covered,
                    'functions_total': coverage.functions_total,
                    'file_count': len(coverage.file_coverage)
                }
                total_coverage += coverage.total_coverage
                coverage_count += 1
        
        # Average coverage across frameworks
        avg_coverage = (total_coverage / coverage_count) if coverage_count > 0 else 0
        
        # Generate summary
        summary = self._generate_summary(
            total_tests, passed, failed, skipped, pass_rate, avg_coverage
        )
        
        # NEW: Generate test-level breakdowns if available
        results_by_level = None
        coverage_by_level = None
        
        if execution_results_by_level:
            results_by_level = {}
            coverage_by_level = {}
            
            for level, level_results in execution_results_by_level.items():
                level_total = 0
                level_passed = 0
                level_failed = 0
                level_skipped = 0
                level_coverage_sum = 0
                level_coverage_count = 0
                
                for framework, result in level_results.items():
                    level_total += result.total_tests
                    level_passed += result.passed
                    level_failed += result.failed
                    level_skipped += result.skipped
                    
                    # Parse coverage for this level-framework combo
                    coverage = self._parse_coverage(framework)
                    if coverage:
                        level_coverage_sum += coverage.total_coverage
                        level_coverage_count += 1
                
                level_pass_rate = (level_passed / level_total * 100) if level_total > 0 else 0
                level_avg_coverage = (level_coverage_sum / level_coverage_count) if level_coverage_count > 0 else 0
                
                results_by_level[level] = {
                    'total': level_total,
                    'passed': level_passed,
                    'failed': level_failed,
                    'skipped': level_skipped,
                    'pass_rate': level_pass_rate
                }
                
                coverage_by_level[level] = level_avg_coverage
            
            logger.info(f"Generated test-level breakdowns: {list(results_by_level.keys())}")
        
        # Create report
        report = UnifiedTestReport(
            timestamp=datetime.now().isoformat(),
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            skipped=skipped,
            pass_rate=pass_rate,
            total_coverage=avg_coverage,
            execution_results=execution_data,
            coverage_reports=coverage_reports_data,
            test_cases=test_cases,
            summary=summary,
            results_by_level=results_by_level,
            coverage_by_level=coverage_by_level
        )
        
        logger.info(f"Report generated: {passed}/{total_tests} passed, {avg_coverage:.2f}% coverage")
        
        return report
    
    def _parse_coverage(self, framework: str) -> Optional[CoverageReport]:
        """Parse coverage for framework"""
        try:
            # Try main_project_path first (where Jest actually runs and generates coverage)
            # Then fall back to workspace project_path
            coverage_paths = []
            if self.main_project_path:
                coverage_paths.append(self.main_project_path)
            coverage_paths.append(self.project_path)
            
            for path in coverage_paths:
                if framework == 'jest':
                    coverage = CoverageParser.parse_jest_coverage(path)
                    if coverage:
                        logger.info(f"Found Jest coverage in: {path}")
                        return coverage
                elif framework == 'pytest':
                    coverage = CoverageParser.parse_pytest_coverage(path)
                    if coverage:
                        logger.info(f"Found pytest coverage in: {path}")
                        return coverage
            
            # No coverage found in any location
            logger.debug(f"No {framework} coverage found in checked paths: {coverage_paths}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {framework} coverage: {e}")
            return None
    
    def _generate_summary(
        self,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        pass_rate: float,
        coverage: float
    ) -> str:
        """Generate summary text"""
        lines = []
        
        if failed == 0:
            lines.append(f"✅ All {passed} tests passed!")
        else:
            lines.append(f"⚠️ {failed} out of {total} tests failed")
        
        lines.append(f"Pass rate: {pass_rate:.1f}%")
        
        if coverage > 0:
            if coverage >= 80:
                lines.append(f"✅ Excellent coverage: {coverage:.1f}%")
            elif coverage >= 60:
                lines.append(f"✓ Good coverage: {coverage:.1f}%")
            elif coverage >= 40:
                lines.append(f"⚠️ Moderate coverage: {coverage:.1f}%")
            else:
                lines.append(f"❌ Low coverage: {coverage:.1f}%")
        
        return " | ".join(lines)
    
    def save_json_report(self, report: UnifiedTestReport, filename: str = "test-report.json") -> Path:
        """
        Save report as JSON
        
        Args:
            report: Unified test report
            filename: Output filename
            
        Returns:
            Path: Path to saved file
        """
        output_file = self.reports_dir / filename
        
        report_data = asdict(report)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"JSON report saved: {output_file}")
        return output_file
    
    def save_html_report(self, report: UnifiedTestReport, filename: str = "test-report.html") -> Path:
        """
        Save report as HTML
        
        Args:
            report: Unified test report
            filename: Output filename
            
        Returns:
            Path: Path to saved file
        """
        output_file = self.reports_dir / filename
        
        html = self._generate_html(report)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"HTML report saved: {output_file}")
        return output_file
    
    def _generate_html(self, report: UnifiedTestReport) -> str:
        """Generate HTML report"""
        
        # Status emoji
        status_emoji = "✅" if report.failed == 0 else "⚠️"
        
        # Coverage color
        if report.total_coverage >= 80:
            coverage_color = "#10b981"  # green
        elif report.total_coverage >= 60:
            coverage_color = "#f59e0b"  # amber
        else:
            coverage_color = "#ef4444"  # red
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {report.timestamp}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9fafb;
        }}
        h1, h2 {{
            color: #1f2937;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .summary {{
            font-size: 18px;
            color: #4b5563;
            margin-top: 10px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .metric-label {{
            color: #6b7280;
            font-size: 14px;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .test-case {{
            padding: 10px;
            border-left: 3px solid #e5e7eb;
            margin: 5px 0;
        }}
        .test-passed {{
            border-left-color: #10b981;
            background-color: #f0fdf4;
        }}
        .test-failed {{
            border-left-color: #ef4444;
            background-color: #fef2f2;
        }}
        .test-skipped {{
            border-left-color: #f59e0b;
            background-color: #fffbeb;
        }}
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background-color: {coverage_color};
            transition: width 0.3s ease;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}
        th {{
            background-color: #f9fafb;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{status_emoji} Test Report</h1>
        <p class="summary">{report.summary}</p>
        <p style="color: #9ca3af;">Generated: {report.timestamp}</p>
    </div>

    <div class="metrics">
        <div class="metric-card">
            <div class="metric-label">Total Tests</div>
            <div class="metric-value">{report.total_tests}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">✅ Passed</div>
            <div class="metric-value" style="color: #10b981;">{report.passed}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">❌ Failed</div>
            <div class="metric-value" style="color: #ef4444;">{report.failed}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">⏭️ Skipped</div>
            <div class="metric-value" style="color: #f59e0b;">{report.skipped}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Pass Rate</div>
            <div class="metric-value">{report.pass_rate:.1f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Coverage</div>
            <div class="metric-value" style="color: {coverage_color};">{report.total_coverage:.1f}%</div>
        </div>
    </div>

    <div class="section">
        <h2>Coverage Details</h2>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {report.total_coverage}%;"></div>
        </div>
        <p style="margin-top: 10px; color: #6b7280;">
            Coverage: {report.total_coverage:.2f}%
        </p>
        
        <table>
            <tr>
                <th>Framework</th>
                <th>Lines</th>
                <th>Branches</th>
                <th>Functions</th>
                <th>Coverage</th>
            </tr>
"""
        
        for framework, cov_data in report.coverage_reports.items():
            lines_pct = (cov_data['lines_covered'] / cov_data['lines_total'] * 100) if cov_data['lines_total'] > 0 else 0
            html += f"""
            <tr>
                <td>{framework.upper()}</td>
                <td>{cov_data['lines_covered']}/{cov_data['lines_total']}</td>
                <td>{cov_data['branches_covered']}/{cov_data['branches_total']}</td>
                <td>{cov_data['functions_covered']}/{cov_data['functions_total']}</td>
                <td>{cov_data['total_coverage']:.1f}%</td>
            </tr>
"""
        
        html += """
        </table>
    </div>

    <div class="section">
        <h2>Test Cases</h2>
"""
        
        for tc in report.test_cases:
            status_class = f"test-{tc['status']}"
            status_icon = "✅" if tc['status'] == 'passed' else "❌" if tc['status'] == 'failed' else "⏭️"
            
            html += f"""
        <div class="test-case {status_class}">
            <strong>{status_icon} {tc['name']}</strong>
            <span style="color: #9ca3af; margin-left: 10px;">
                {tc['framework'].upper()} | {tc['duration']:.3f}s
            </span>
"""
            if tc.get('error'):
                html += f"""
            <pre style="background: #1f2937; color: #f3f4f6; padding: 10px; border-radius: 4px; margin-top: 10px; overflow-x: auto;">{tc['error']}</pre>
"""
            
            html += """
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        return html

