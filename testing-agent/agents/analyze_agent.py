"""
Project Analysis Agent
Uses Vertex AI Gemini to analyze project structure and detect languages, frameworks, and test setup
"""

import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from config.vertex_ai import GeminiClient
from tools.file_indexer import IndexResult, FileInfo, FileIndexer

logger = logging.getLogger(__name__)


@dataclass
class ProjectAnalysisResult:
    """Data class for project analysis results"""
    languages: List[str]
    frameworks: List[str]
    test_setup: Dict[str, Any]
    confidence: str  # high, medium, low
    summary: str
    raw_response: Optional[str] = None


class AnalyzeAgent:
    """
    Agent for analyzing project structure using Gemini LLM
    Detects languages, frameworks, and existing test setup
    """
    
    def __init__(self, gemini_client: GeminiClient):
        """
        Initialize analyze agent
        
        Args:
            gemini_client: Initialized GeminiClient instance
        """
        self.client = gemini_client
        
    def analyze_project(
        self,
        index_result: IndexResult,
        project_path: Path,
        main_project_path: Optional[Path] = None
    ) -> Optional[ProjectAnalysisResult]:
        """
        Analyze project to detect languages, frameworks, and test setup
        
        Args:
            index_result: File indexing results
            project_path: Path to workspace project directory
            main_project_path: Optional path to main project directory (where test files are saved)
            
        Returns:
            Optional[ProjectAnalysisResult]: Analysis results or None if failed
        """
        try:
            logger.info("Starting project analysis with Gemini")
            
            # Create project summary (not full content)
            project_summary = self._create_project_summary(index_result, project_path, main_project_path)
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(project_summary)
            
            # Generate analysis using Gemini
            logger.debug("Sending analysis request to Gemini")
            response = self.client.generate_content(prompt)
            
            if not response:
                logger.error("Empty response from Gemini")
                return None
            
            # Parse response
            analysis = self._parse_analysis_response(response, index_result)
            
            if analysis:
                logger.info(f"Analysis complete: {len(analysis.languages)} language(s), {len(analysis.frameworks)} framework(s)")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            return None
    
    def _create_project_summary(
        self,
        index_result: IndexResult,
        project_path: Path,
        main_project_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Create a summary of the project for analysis
        Does NOT include full file contents, only metadata
        
        Args:
            index_result: File indexing results
            project_path: Path to workspace project directory
            main_project_path: Optional path to main project directory (where test files are saved)
            
        Returns:
            Dict: Project summary
        """
        summary = {
            "total_files": index_result.total_files,
            "total_lines": index_result.total_lines,
            "files_by_category": index_result.files_by_category,
            "files_by_extension": index_result.files_by_extension,
            "file_structure": [],
            "config_files": [],
            "package_files": [],
            "test_files": []
        }
        
        # Analyze file structure (names and paths only, no content)
        for file_info in index_result.file_list:
            file_entry = {
                "path": file_info.relative_path,
                "extension": file_info.extension,
                "category": file_info.category,
                "size": file_info.size,
                "lines": file_info.lines
            }
            
            # Identify important files
            filename = Path(file_info.relative_path).name.lower()
            file_path_lower = str(file_info.relative_path).lower()
            
            # Comprehensive test framework config files detection
            test_config_patterns = [
                # JavaScript/TypeScript test configs
                'jest.config.js', 'jest.config.ts', 'jest.config.json',
                'vitest.config.js', 'vitest.config.ts',
                'mocha.config.js', 'mocha.opts',
                'karma.config.js', 'karma.conf.js',
                'cypress.config.js', 'cypress.json',
                'playwright.config.js', 'playwright.config.ts',
                # Python test configs
                'pytest.ini', 'setup.cfg', 'tox.ini', 'pyproject.toml',
                'conftest.py', 'pytest.ini', 'setup.py',
                # Other test configs
                '.testrc', '.testrc.js', '.testrc.json',
                'test.config.js', 'test.config.ts'
            ]
            
            # Config files (including test framework configs)
            config_files_list = [
                'package.json', 'tsconfig.json', 'setup.py', 'requirements.txt',
                'webpack.config.js', 'vite.config.js', 'next.config.js',
                '.babelrc', 'babel.config.js', 'rollup.config.js',
                'webpack.config.ts', 'vite.config.ts'
            ] + test_config_patterns
            
            if filename in config_files_list or any(pattern in filename for pattern in test_config_patterns):
                config_entry = {
                    "name": filename,
                    "path": file_info.relative_path
                }
                
                # Mark as test config if it's a test framework config
                if filename in test_config_patterns or any(pattern in filename for pattern in test_config_patterns):
                    config_entry["is_test_config"] = True
                
                summary["config_files"].append(config_entry)
                
                # Try to read small config files
                try:
                    full_path = project_path / file_info.relative_path
                    if file_info.size < 50000:  # Only read files < 50KB
                        content = full_path.read_text(encoding='utf-8', errors='ignore')
                        summary["config_files"][-1]["content"] = content[:2000]  # First 2000 chars
                except Exception as e:
                    logger.debug(f"Could not read config file {filename}: {e}")
            
            # Package/dependency files - check for test scripts and dependencies
            if filename in ['package.json', 'requirements.txt', 'pyproject.toml', 'Pipfile', 'package-lock.json']:
                package_entry = {
                    "name": filename,
                    "path": file_info.relative_path
                }
                
                # Read package.json to check for test scripts and dependencies
                if filename == 'package.json':
                    try:
                        full_path = project_path / file_info.relative_path
                        if file_info.size < 50000:
                            import json
                            content = full_path.read_text(encoding='utf-8', errors='ignore')
                            try:
                                package_data = json.loads(content)
                                # Check for test scripts
                                scripts = package_data.get('scripts', {})
                                test_scripts = {k: v for k, v in scripts.items() if 'test' in k.lower()}
                                if test_scripts:
                                    package_entry["test_scripts"] = test_scripts
                                
                                # Check for test-related dependencies
                                deps = package_data.get('dependencies', {})
                                dev_deps = package_data.get('devDependencies', {})
                                all_deps = {**deps, **dev_deps}
                                test_deps = {
                                    k: v for k, v in all_deps.items() 
                                    if any(test_fw in k.lower() for test_fw in ['jest', 'mocha', 'jasmine', 'karma', 'vitest', 'cypress', 'playwright', 'testing-library', 'enzyme', 'chai', 'sinon'])
                                }
                                if test_deps:
                                    package_entry["test_dependencies"] = test_deps
                                
                                package_entry["content"] = content[:2000]
                            except json.JSONDecodeError:
                                package_entry["content"] = content[:2000]
                    except Exception as e:
                        logger.debug(f"Could not read package.json: {e}")
                
                summary["package_files"].append(package_entry)
            
            # Test files - comprehensive detection
            if file_info.category == 'Test':
                summary["test_files"].append(file_entry)
            
            # Add to general structure
            summary["file_structure"].append(file_entry)
        
        # Limit structure list for token efficiency
        summary["file_structure"] = summary["file_structure"][:100]
        
        # Additional direct file system checks for test configs (in case they weren't indexed)
        test_config_files_to_check = [
            'jest.config.js', 'jest.config.ts', 'jest.config.json',
            'vitest.config.js', 'vitest.config.ts',
            'pytest.ini', 'setup.cfg', 'tox.ini',
            'mocha.config.js', 'karma.config.js',
            'cypress.config.js', 'playwright.config.js'
        ]
        
        for config_file in test_config_files_to_check:
            config_path = project_path / config_file
            if config_path.exists() and config_path.is_file():
                # Check if already in config_files
                already_found = any(
                    cf.get('name', '').lower() == config_file.lower() 
                    for cf in summary["config_files"]
                )
                if not already_found:
                    summary["config_files"].append({
                        "name": config_file,
                        "path": str(config_path.relative_to(project_path)),
                        "is_test_config": True
                    })
                    try:
                        if config_path.stat().st_size < 50000:
                            content = config_path.read_text(encoding='utf-8', errors='ignore')
                            summary["config_files"][-1]["content"] = content[:2000]
                    except Exception as e:
                        logger.debug(f"Could not read test config {config_file}: {e}")
        
        # Check for test directories
        test_dirs_to_check = ['__tests__', 'tests', 'test', 'spec', '__spec__']
        for test_dir_name in test_dirs_to_check:
            test_dir_path = project_path / test_dir_name
            if test_dir_path.exists() and test_dir_path.is_dir():
                # Count test files in directory
                test_files_in_dir = list(test_dir_path.rglob('*'))
                test_file_count = sum(1 for f in test_files_in_dir if f.is_file() and not FileIndexer.should_ignore(f, project_path))
                if test_file_count > 0:
                    summary["test_directories"] = summary.get("test_directories", [])
                    summary["test_directories"].append({
                        "name": test_dir_name,
                        "path": str(test_dir_path.relative_to(project_path)),
                        "test_file_count": test_file_count
                    })
        
        # Also check main_project_path for test files (where they're actually saved)
        if main_project_path and main_project_path != project_path:
            test_file_patterns = ['*.test.js', '*.test.jsx', '*.test.ts', '*.test.tsx', 
                                '*.spec.js', '*.spec.jsx', '*.spec.ts', '*.spec.tsx']
            for pattern in test_file_patterns:
                for test_file in main_project_path.glob(pattern):
                    if test_file.is_file():
                        # Check if already in test_files
                        rel_path = str(test_file.relative_to(main_project_path))
                        already_found = any(
                            tf.get('path', '') == rel_path 
                            for tf in summary["test_files"]
                        )
                        if not already_found:
                            summary["test_files"].append({
                                "path": rel_path,
                                "extension": test_file.suffix,
                                "category": "Test",
                                "size": test_file.stat().st_size,
                                "lines": len(test_file.read_text(encoding='utf-8', errors='ignore').splitlines())
                            })
                            logger.debug(f"Found test file in main_project_path: {test_file}")
        
        return summary
    
    def _build_analysis_prompt(self, project_summary: Dict[str, Any]) -> str:
        """
        Build analysis prompt for Gemini
        
        Args:
            project_summary: Project summary dict
            
        Returns:
            str: Formatted prompt
        """
        prompt = f"""You are an expert software engineer analyzing a project structure.

Project Summary:
- Total Files: {project_summary['total_files']}
- Total Lines of Code: {project_summary['total_lines']}
- Files by Category: {json.dumps(project_summary['files_by_category'], indent=2)}
- Files by Extension: {json.dumps(project_summary['files_by_extension'], indent=2)}

Configuration Files Found:
{json.dumps(project_summary['config_files'], indent=2)}

Test Files Found: {len(project_summary['test_files'])}
Test Files List: {json.dumps([tf['path'] for tf in project_summary['test_files'][:20]], indent=2) if project_summary['test_files'] else '[]'}

Test Directories Found: {len(project_summary.get('test_directories', []))}
Test Directories: {json.dumps(project_summary.get('test_directories', []), indent=2)}

Test Framework Config Files Found: {len([cf for cf in project_summary['config_files'] if cf.get('is_test_config', False)])}
Test Config Files: {json.dumps([cf for cf in project_summary['config_files'] if cf.get('is_test_config', False)], indent=2)}

Package Files with Test Info:
{json.dumps([pf for pf in project_summary['package_files'] if 'test_scripts' in pf or 'test_dependencies' in pf], indent=2)}

File Structure Sample (first 100 files):
{json.dumps(project_summary['file_structure'][:50], indent=2)}

Based on this project structure, analyze and determine:

1. **Programming Languages**: Which languages are used? (JavaScript, TypeScript, Python, etc.)
2. **Frameworks**: Which frameworks/libraries are present? (React, Node.js, Express, Django, Flask, etc.)
3. **Test Setup**: 
   - Check the "Test Files Found" count and list above
   - Check the "Test Framework Config Files Found" list above
   - Check the "Package Files with Test Info" for test scripts and dependencies
   - Check the "Test Directories" list above
   - Determine what testing frameworks are already configured (Jest, Pytest, Mocha, Vitest, etc.)
   - If test files exist, set has_tests to true
   - If test framework configs exist, include them in test_frameworks
   - If package.json has test scripts or test dependencies, include those frameworks

IMPORTANT: If you see test files (.test.js, .spec.js, test_*.py, etc.), test directories (__tests__/, tests/), test config files (jest.config.js, pytest.ini), or test scripts/dependencies in package.json, you MUST report them. Do NOT say "No testing frameworks" if any of these exist.

Provide your analysis in the following JSON format ONLY (no extra text):

{{
  "languages": ["language1", "language2"],
  "frameworks": ["framework1", "framework2"],
  "test_setup": {{
    "has_tests": true/false,
    "test_frameworks": ["framework1"],
    "test_file_count": number,
    "test_coverage": "high/medium/low/none"
  }},
  "confidence": "high/medium/low",
  "summary": "Brief 2-3 sentence summary of the project"
}}

Respond with ONLY the JSON object, nothing else."""

        return prompt
    
    def _parse_analysis_response(self, response: str, index_result: Optional[IndexResult] = None) -> Optional[ProjectAnalysisResult]:
        """
        Parse Gemini response into structured analysis result
        
        Args:
            response: Raw response from Gemini
            
        Returns:
            Optional[ProjectAnalysisResult]: Parsed result or None
        """
        try:
            # Extract JSON from response
            response = response.strip()
            
            # Handle markdown code blocks
            if response.startswith("```"):
                # Remove markdown code fences
                lines = response.split('\n')
                json_lines = []
                in_json = False
                
                for line in lines:
                    if line.strip().startswith("```"):
                        in_json = not in_json
                        continue
                    if in_json or (line.strip().startswith("{") or json_lines):
                        json_lines.append(line)
                        if line.strip().endswith("}") and line.strip().count("}") >= line.strip().count("{"):
                            break
                
                response = '\n'.join(json_lines)
            
            # Find JSON object
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                logger.error("No JSON object found in response")
                return None
            
            json_str = response[start_idx:end_idx + 1]
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Validate required fields
            required_fields = ['languages', 'frameworks', 'test_setup', 'confidence', 'summary']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field in response: {field}")
                    return None
            
            # Post-process to ensure test detection is accurate
            # If test files were found but AI didn't report them, fix it
            test_setup = data.get('test_setup', {})
            
            # Verify test detection using index_result
            if index_result:
                test_file_count = index_result.files_by_category.get('Test', 0)
                if test_file_count > 0:
                    # Ensure has_tests is true if test files exist
                    test_setup['has_tests'] = True
                    # Ensure test_file_count is set
                    if not test_setup.get('test_file_count') or test_setup.get('test_file_count', 0) == 0:
                        test_setup['test_file_count'] = test_file_count
                    
                    # If no test frameworks detected but test files exist, try to infer
                    if not test_setup.get('test_frameworks') or len(test_setup.get('test_frameworks', [])) == 0:
                        # Check file extensions to infer framework
                        test_files = [f for f in index_result.file_list if f.category == 'Test']
                        frameworks_detected = set()
                        for test_file in test_files:
                            ext = test_file.extension.lower()
                            if ext in ['.js', '.jsx', '.ts', '.tsx']:
                                if '.test.' in test_file.relative_path.lower() or '.spec.' in test_file.relative_path.lower():
                                    frameworks_detected.add('Jest')  # Default for JS/TS
                            elif ext == '.py':
                                frameworks_detected.add('Pytest')  # Default for Python
                        
                        if frameworks_detected:
                            test_setup['test_frameworks'] = list(frameworks_detected)
            
            # Ensure has_tests is set correctly if test_frameworks exist
            if test_setup.get('test_frameworks') and len(test_setup.get('test_frameworks', [])) > 0:
                test_setup['has_tests'] = True
            
            # Create result object
            result = ProjectAnalysisResult(
                languages=data['languages'],
                frameworks=data['frameworks'],
                test_setup=test_setup,
                confidence=data['confidence'],
                summary=data['summary'],
                raw_response=response
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return None
    
    def format_analysis_for_display(self, analysis: ProjectAnalysisResult) -> str:
        """
        Format analysis result for display
        
        Args:
            analysis: Analysis result
            
        Returns:
            str: Formatted string for display
        """
        lines = []
        lines.append("=" * 60)
        lines.append("PROJECT ANALYSIS")
        lines.append("=" * 60)
        lines.append("")
        
        # Languages
        lines.append(f"Languages Detected ({len(analysis.languages)}):")
        for lang in analysis.languages:
            lines.append(f"  - {lang}")
        lines.append("")
        
        # Frameworks
        lines.append(f"Frameworks Detected ({len(analysis.frameworks)}):")
        if analysis.frameworks:
            for fw in analysis.frameworks:
                lines.append(f"  - {fw}")
        else:
            lines.append("  - None detected")
        lines.append("")
        
        # Test setup
        lines.append("Test Setup:")
        test_setup = analysis.test_setup
        lines.append(f"  - Tests Present: {'Yes' if test_setup.get('has_tests') else 'No'}")
        
        if test_setup.get('test_frameworks'):
            lines.append(f"  - Test Frameworks: {', '.join(test_setup['test_frameworks'])}")
        
        if test_setup.get('test_file_count'):
            lines.append(f"  - Test Files: {test_setup['test_file_count']}")
        
        lines.append(f"  - Test Coverage: {test_setup.get('test_coverage', 'unknown')}")
        lines.append("")
        
        # Confidence and summary
        lines.append(f"Analysis Confidence: {analysis.confidence.upper()}")
        lines.append("")
        lines.append("Summary:")
        lines.append(f"  {analysis.summary}")
        lines.append("")
        lines.append("=" * 60)
        
        return '\n'.join(lines)

